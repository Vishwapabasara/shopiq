import logging
import asyncio
from datetime import datetime
from bson import ObjectId
from celery import Task

from app.workers.celery_app import celery_app
from app.config import settings
from app.utils.crypto import decrypt_token
from app.utils.shopify_client import fetch_all_products
from app.models.schemas import AuditStatus
from app.services.audit_rules import (
    run_rules, calculate_store_score, strip_html, word_count
)

logger = logging.getLogger(__name__)

print("=" * 50)
print("🔧 AUDIT WORKER MODULE LOADED")
print("=" * 50)


def get_sync_db():
    """Get synchronous MongoDB connection for Celery worker"""
    from pymongo import MongoClient
    client = MongoClient(settings.MONGO_URI)
    return client.get_default_database()


@celery_app.task(bind=True, name='app.workers.audit_worker.run_audit_task')
def run_audit_task(self: Task, audit_id: str, shop_domain: str, encrypted_token: str):
    """Run product audit task in Celery worker"""
    logger.info(f"🚀 Task received for audit: {audit_id}")
    logger.info(f"📦 Shop: {shop_domain}")

    try:
        db = get_sync_db()
        db.audits.update_one(
            {"_id": ObjectId(audit_id)},
            {"$set": {
                "status": AuditStatus.RUNNING.value,
                "updated_at": datetime.utcnow()
            }}
        )
        logger.info(f"✅ Audit {audit_id} marked as RUNNING")

        logger.info("🔑 Decrypting access token...")
        access_token = decrypt_token(encrypted_token)
        logger.info("✅ Access token decrypted")

        logger.info("🏃 Starting audit async operations...")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(
                _run_audit_async(audit_id, shop_domain, access_token, db)
            )
            logger.info(f"✅ Audit {audit_id} completed successfully")
            return result
        finally:
            loop.close()

    except Exception as exc:
        logger.error(f"❌ Audit {audit_id} failed: {exc}", exc_info=True)

        try:
            db = get_sync_db()
            db.audits.update_one(
                {"_id": ObjectId(audit_id)},
                {"$set": {
                    "status": AuditStatus.FAILED.value,
                    "error_message": str(exc),
                    "completed_at": datetime.utcnow()
                }}
            )
            logger.info(f"✅ Audit {audit_id} marked as FAILED")
        except Exception as e:
            logger.error(f"❌ Failed to mark audit as failed: {e}")

        raise


# Scaled-down per-category severity penalties (50-point scale)
_HALF_PENALTY = {"critical": 10, "warning": 5, "info": 2}


def _score_category_50(issues: list, category: str) -> int:
    """Deduct from 50 based on issues belonging to a specific category."""
    deductions = sum(
        _HALF_PENALTY.get(str(i.severity.value if hasattr(i.severity, "value") else i.severity), 2)
        for i in issues
        if (i.category if hasattr(i, "category") else "") == category
    )
    return max(0, 50 - deductions)


def _score_title_50(issues: list) -> int:
    """Deduct from 50 based only on title-related issues."""
    TITLE_RULES = {"title_too_short", "generic_title", "seo_title_too_short", "seo_title_too_long", "missing_seo_title"}
    deductions = sum(
        _HALF_PENALTY.get(str(i.severity.value if hasattr(i.severity, "value") else i.severity), 2)
        for i in issues
        if (i.rule if hasattr(i, "rule") else "") in TITLE_RULES
    )
    return max(0, 50 - deductions)


# Keywords in issue messages that indicate SEO/metadata gaps rather than
# show-stopping problems. These are downgraded to "warning" for products
# that are otherwise functional (score >= 50).
_SEO_KEYWORDS = ("description", "meta", "seo", "keywords", "alt text", "tag", "vendor", "type")


def _apply_severity_override(score: int, issues: list[dict]) -> list[dict]:
    """
    Downgrade 'critical' → 'warning' for SEO/metadata issues on products
    that are fundamentally functional (score ≥ 50).  Truly broken products
    (no images, no description at all) keep their critical status regardless.
    """
    if score >= 50:
        for issue in issues:
            if issue.get("severity") == "critical":
                msg = issue.get("message", "").lower()
                if any(kw in msg for kw in _SEO_KEYWORDS):
                    issue["severity"] = "warning"
    return issues


async def _run_audit_async(audit_id: str, shop_domain: str, access_token: str, db):
    """Run the actual audit: fetch → rules → AI → save → notify."""

    # ── 1. Fetch products ────────────────────────────────────────────────────────
    logger.info(f"📦 Fetching products from Shopify for {shop_domain}...")
    products = await fetch_all_products(shop_domain, access_token)
    logger.info(f"✅ Fetched {len(products)} products")

    db.audits.update_one(
        {"_id": ObjectId(audit_id)},
        {"$set": {"products_scanned": len(products)}}
    )

    # ── 2. Deterministic rules engine ────────────────────────────────────────────
    logger.info(f"⚙️ Running rules engine on {len(products)} products...")
    description_hashes: set = set()
    product_results = []

    for product in products:
        issues, score = run_rules(product, description_hashes)

        # Per-product breakdown scores (0–50 each)
        content_score = _score_category_50(issues, "content")
        visual_score  = _score_category_50(issues, "ux")
        title_score   = _score_title_50(issues)

        # Metadata snapshot
        body_text = strip_html(product.get("body_html") or "")
        wc = word_count(body_text)
        seo = product.get("seo") or {}
        images = product.get("images") or []
        image_url = images[0].get("src") if images else None

        # Serialize issues then apply score-based severity override
        serialized_issues = [i.model_dump() for i in issues]
        serialized_issues = _apply_severity_override(score, serialized_issues)

        product_results.append({
            "shopify_product_id": str(product["id"]),
            "title": product.get("title", "Untitled"),
            "handle": product.get("handle", ""),
            "score": score,
            "issues": serialized_issues,
            "image_count": len(images),
            "word_count": wc,
            "has_seo_title": bool(seo.get("title")),
            "has_meta_description": bool(seo.get("description")),
            "image_url": image_url,
            # Per-category breakdown (0–50 scale)
            "content_score": content_score,
            "visual_score": visual_score,
            "title_score": title_score,
            # AI fields populated in step 3
            "ai_score": None,
            "ai_improvements": [],
            "ai_rewrite": None,
            "ai_verdict": None,
        })

    logger.info(f"✅ Rules engine complete — {len(product_results)} products scored")

    # ── 3. AI scoring with Gemini ────────────────────────────────────────────────
    logger.info(f"🤖 Running Gemini AI scoring on {len(products)} products...")
    try:
        from app.services.ai_scorer import score_products_batch
        ai_results = await score_products_batch(products)

        for pr in product_results:
            ai = ai_results.get(pr["shopify_product_id"])
            if ai:
                pr["ai_score"]        = ai.get("content_score")
                pr["ai_improvements"] = ai.get("improvements", [])
                pr["ai_rewrite"]      = ai.get("rewritten_description", "")
                pr["ai_verdict"]      = ai.get("one_line_verdict", "")

        logger.info(f"✅ AI scoring complete — {len(ai_results)} products scored")
    except Exception as e:
        logger.error(f"❌ AI scoring failed (continuing with deterministic scores): {e}", exc_info=True)

    # ── 4. Aggregate scores ──────────────────────────────────────────────────────
    overall_score, category_scores = calculate_store_score(product_results)
    # Count products with at least one issue of each severity (not total issues)
    critical_count = sum(1 for p in product_results if any(i.get("severity") == "critical" for i in p.get("issues", [])))
    warning_count  = sum(1 for p in product_results if any(i.get("severity") == "warning"  for i in p.get("issues", [])))
    info_count     = sum(1 for p in product_results if any(i.get("severity") == "info"     for i in p.get("issues", [])))

    logger.info(
        f"📊 Audit summary — score: {overall_score}, "
        f"critical: {critical_count}, warning: {warning_count}, info: {info_count}"
    )

    # ── 5. Save to database ──────────────────────────────────────────────────────
    logger.info("💾 Saving audit results to database...")
    db.audits.update_one(
        {"_id": ObjectId(audit_id)},
        {"$set": {
            "status": AuditStatus.COMPLETE.value,
            "products_scanned": len(products),
            "product_results": product_results,
            "overall_score": overall_score,
            "category_scores": category_scores,
            "critical_count": critical_count,
            "warning_count": warning_count,
            "info_count": info_count,
            "completed_at": datetime.utcnow()
        }}
    )
    logger.info(f"✅ Audit {audit_id} results saved")

    # ── 5b. Update products scanned usage ────────────────────────────────────────
    try:
        tenant = db.tenants.find_one({"shop_domain": shop_domain})
        if tenant:
            db.tenants.update_one(
                {"_id": tenant["_id"]},
                {"$inc": {"usage.products_scanned_this_month": len(products)}}
            )
            logger.info(f"✅ Usage updated: {len(products)} products scanned for {shop_domain}")
    except Exception as e:
        logger.warning(f"⚠️ Failed to update product usage: {e}")

    # ── 6. Email notification ────────────────────────────────────────────────────
    try:
        tenant = db.tenants.find_one({"shop_domain": shop_domain})
        if tenant and tenant.get("shop_email"):
            from app.services.email import send_audit_complete_email
            send_audit_complete_email(
                shop_domain=shop_domain,
                shop_email=tenant["shop_email"],
                audit_id=audit_id,
                overall_score=float(overall_score),
                critical_count=critical_count,
                warning_count=warning_count,
            )
        else:
            logger.info(f"ℹ️ No shop email found for {shop_domain} — skipping notification")
    except Exception as e:
        logger.error(f"❌ Email notification failed (audit still complete): {e}")

    return {
        "audit_id": audit_id,
        "products_scanned": len(products),
        "overall_score": overall_score,
    }


@celery_app.task(name='app.workers.audit_worker.run_scheduled_audits')
def run_scheduled_audits():
    """Run scheduled monthly audits"""
    logger.info("🔄 Running scheduled audits...")
    logger.info("✅ Scheduled audits completed")
