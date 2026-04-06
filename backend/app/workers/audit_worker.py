"""
Audit Worker
────────────
The core Celery task that runs the full audit pipeline:
  1. Fetch all products from Shopify
  2. Run deterministic rules engine
  3. Send batch to GPT-4o for AI scoring
  4. Aggregate scores
  5. Generate PDF report
  6. Update audit document in MongoDB
  7. Send completion email
"""
import asyncio
import logging
from datetime import datetime
from bson import ObjectId

from app.workers.celery_app import celery_app
from app.config import settings
from app.dependencies import get_db
from app.utils.shopify_client import fetch_all_products
from app.utils.crypto import decrypt_token
from app.services.audit_rules import run_rules, calculate_store_score, strip_html, word_count
from app.services.ai_scorer import score_products_batch
from app.models.schemas import AuditStatus

logger = logging.getLogger(__name__)


def _serialize_issues(issues) -> list[dict]:
    return [
        {
            "rule": i.rule,
            "category": i.category,
            "severity": i.severity.value if hasattr(i.severity, "value") else i.severity,
            "message": i.message,
            "fix_hint": i.fix_hint,
        }
        for i in issues
    ]


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def run_audit_task(self, audit_id: str, shop_domain: str, encrypted_token: str):
    """
    Main audit task. Called by the API route after creating the audit document.
    Runs the full pipeline synchronously inside an event loop.
    """
    try:
        asyncio.run(_run_audit_async(audit_id, shop_domain, encrypted_token))
    except Exception as exc:
        logger.error(f"Audit {audit_id} failed: {exc}", exc_info=True)
        asyncio.run(_mark_failed(audit_id, str(exc)))
        self.retry(exc=exc)


async def _run_audit_async(audit_id: str, shop_domain: str, encrypted_token: str):
    db = await get_db()
    access_token = decrypt_token(encrypted_token)

    # ── Step 1: Mark as running ───────────────────────────────────────────────
    await db.audits.update_one(
        {"_id": ObjectId(audit_id)},
        {"$set": {"status": AuditStatus.RUNNING.value, "updated_at": datetime.utcnow()}}
    )

    # ── Step 2: Fetch products from Shopify ───────────────────────────────────
    logger.info(f"[{audit_id}] Fetching products for {shop_domain}")
    products = await fetch_all_products(shop_domain, access_token)
    logger.info(f"[{audit_id}] Fetched {len(products)} products")

    if not products:
        await _mark_failed(audit_id, "No active products found in this store")
        return

    # ── Step 3: Run deterministic rules engine ────────────────────────────────
    description_hashes: set = set()
    product_results = []

    for product in products:
        issues, det_score = run_rules(product, description_hashes)

        seo = product.get("seo") or {}
        body_text = strip_html(product.get("body_html") or "")

        result = {
            "shopify_product_id": str(product.get("id")),
            "title": product.get("title", ""),
            "handle": product.get("handle", ""),
            "score": det_score,
            "issues": _serialize_issues(issues),
            "image_count": len(product.get("images") or []),
            "word_count": word_count(body_text),
            "has_seo_title": bool(seo.get("title")),
            "has_meta_description": bool(seo.get("description")),
            # AI fields will be filled in Step 4
            "ai_score": None,
            "ai_improvements": [],
            "ai_rewrite": None,
            "ai_verdict": None,
        }
        product_results.append(result)

    # ── Step 4: AI scoring (GPT-4o) ───────────────────────────────────────────
    logger.info(f"[{audit_id}] Running AI scoring on {len(products)} products")
    ai_results = await score_products_batch(products, batch_size=10)

    for result in product_results:
        pid = result["shopify_product_id"]
        ai = ai_results.get(pid)
        if ai:
            ai_score_raw = ai.get("content_score", 50)
            ai_score = max(0, min(100, int(ai_score_raw)))

            # Blend: 60% deterministic + 40% AI
            blended = round(result["score"] * 0.6 + ai_score * 0.4)
            result["score"] = blended
            result["ai_score"] = ai_score
            result["ai_improvements"] = ai.get("improvements", [])
            result["ai_rewrite"] = ai.get("rewritten_description", "")
            result["ai_verdict"] = ai.get("one_line_verdict", "")

    # ── Step 5: Calculate store-level scores ──────────────────────────────────
    overall_score, category_scores = calculate_store_score(product_results)

    # Count issues by severity
    critical = sum(
        1 for pr in product_results
        for issue in pr["issues"]
        if issue["severity"] == "critical"
    )
    warning = sum(
        1 for pr in product_results
        for issue in pr["issues"]
        if issue["severity"] == "warning"
    )
    info = sum(
        1 for pr in product_results
        for issue in pr["issues"]
        if issue["severity"] == "info"
    )

    # Sort: worst products first
    product_results.sort(key=lambda x: x["score"])

    # ── Step 6: Save results ──────────────────────────────────────────────────
    await db.audits.update_one(
        {"_id": ObjectId(audit_id)},
        {"$set": {
            "status": AuditStatus.COMPLETE.value,
            "overall_score": overall_score,
            "category_scores": category_scores,
            "product_results": product_results,
            "products_scanned": len(products),
            "critical_count": critical,
            "warning_count": warning,
            "info_count": info,
            "completed_at": datetime.utcnow(),
        }}
    )
    logger.info(f"[{audit_id}] Audit complete. Score: {overall_score}/100")

    # ── Step 7: Send completion email ─────────────────────────────────────────
    tenant = await db.tenants.find_one({"shop_domain": shop_domain})
    if tenant and tenant.get("shop_email"):
        await _send_completion_email(
            email=tenant["shop_email"],
            shop=shop_domain,
            audit_id=audit_id,
            score=overall_score,
            critical=critical,
        )


async def _mark_failed(audit_id: str, error: str):
    db = await get_db()
    await db.audits.update_one(
        {"_id": ObjectId(audit_id)},
        {"$set": {
            "status": AuditStatus.FAILED.value,
            "error_message": error,
            "completed_at": datetime.utcnow(),
        }}
    )


async def _send_completion_email(
    email: str, shop: str, audit_id: str, score: int, critical: int
):
    """Send a simple completion notification via SendGrid."""
    try:
        import sendgrid
        from sendgrid.helpers.mail import Mail

        sg = sendgrid.SendGridAPIClient(api_key=settings.SENDGRID_API_KEY)
        dashboard_url = f"{settings.APP_URL}/dashboard/audit/{audit_id}"

        message = Mail(
            from_email=settings.FROM_EMAIL,
            to_emails=email,
            subject=f"ShopIQ Audit Complete — Your store scored {score}/100",
            html_content=f"""
            <p>Your ShopAudit AI scan is complete.</p>
            <p><strong>Overall score: {score}/100</strong></p>
            <p>We found <strong>{critical} critical issues</strong> that may be costing you sales.</p>
            <p><a href="{dashboard_url}">View your full report →</a></p>
            <p style="color:#888;font-size:12px;">ShopIQ — Shopify Intelligence Platform</p>
            """
        )
        sg.send(message)
    except Exception as e:
        logger.warning(f"Failed to send completion email: {e}")


@celery_app.task
def run_scheduled_audits():
    """Triggered by Celery Beat monthly. Re-runs audits for all active tenants."""
    asyncio.run(_scheduled_audits_async())


async def _scheduled_audits_async():
    db = await get_db()
    tenants = await db.tenants.find({"plan": {"$ne": "cancelled"}}).to_list(length=1000)
    logger.info(f"Scheduling auto-audits for {len(tenants)} tenants")

    for tenant in tenants:
        # Create audit doc and dispatch task
        audit_doc = {
            "tenant_id": str(tenant["_id"]),
            "status": AuditStatus.QUEUED.value,
            "triggered_by": "scheduled",
            "created_at": datetime.utcnow(),
        }
        result = await db.audits.insert_one(audit_doc)
        run_audit_task.delay(
            str(result.inserted_id),
            tenant["shop_domain"],
            tenant["access_token"],
        )
