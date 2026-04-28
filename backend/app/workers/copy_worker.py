"""
BulkCopy AI — Celery Worker
────────────────────────────
1. Fetch all products from Shopify
2. Extract brand voice from top-described products
3. Generate copy for selected/filtered products in batches
4. Update DB with live progress so the frontend can poll
"""
import asyncio
import logging
from datetime import datetime

from bson import ObjectId
from celery import Task

from app.workers.celery_app import celery_app
from app.config import settings
from app.utils.crypto import decrypt_token
from app.utils.shopify_client import fetch_all_products
from app.services.audit_rules import strip_html

logger = logging.getLogger(__name__)

print("=" * 50)
print("🔧 COPY WORKER MODULE LOADED")
print("=" * 50)


def get_sync_db():
    from pymongo import MongoClient
    client = MongoClient(settings.MONGO_URI)
    return client.get_default_database()


@celery_app.task(bind=True, name="app.workers.copy_worker.run_copy_task")
def run_copy_task(
    self: Task,
    session_id: str,
    shop_domain: str,
    encrypted_token: str,
    product_ids: list | None,
    filter_mode: str,
    max_products: int,
):
    logger.info(f"🚀 [BulkCopy] Task received — session {session_id}, shop {shop_domain}")
    db = get_sync_db()

    try:
        db.copy_sessions.update_one(
            {"_id": ObjectId(session_id)},
            {"$set": {"status": "running", "updated_at": datetime.utcnow()}},
        )

        access_token = decrypt_token(encrypted_token)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(
                _run_copy_async(
                    session_id, shop_domain, access_token,
                    product_ids, filter_mode, max_products, db,
                )
            )
            logger.info(f"✅ [BulkCopy] Session {session_id} completed")
        finally:
            loop.close()

    except Exception as exc:
        logger.error(f"❌ [BulkCopy] Session {session_id} failed: {exc}", exc_info=True)
        try:
            db.copy_sessions.update_one(
                {"_id": ObjectId(session_id)},
                {"$set": {
                    "status": "failed",
                    "error_message": str(exc),
                    "completed_at": datetime.utcnow(),
                }},
            )
        except Exception as e:
            logger.error(f"❌ Failed to mark session as failed: {e}")


async def _run_copy_async(
    session_id: str,
    shop_domain: str,
    access_token: str,
    product_ids: list | None,
    filter_mode: str,
    max_products: int,
    db,
):
    from app.services.copy_service import (
        extract_brand_voice,
        generate_copy_for_product,
        _fallback_copy_result,
    )
    from google import genai

    # ── Step 1: fetch all products ─────────────────────────────────────────────
    logger.info(f"📦 [BulkCopy] Fetching products for {shop_domain}")
    all_products = await fetch_all_products(shop_domain, access_token)
    logger.info(f"✅ [BulkCopy] Fetched {len(all_products)} products")

    # ── Step 2: select which products to process ───────────────────────────────
    if filter_mode == "selected" and product_ids:
        pid_set = {str(p) for p in product_ids}
        products = [p for p in all_products if str(p.get("id", "")) in pid_set]
    elif filter_mode == "low_score":
        # Prioritise products with the shortest / missing descriptions
        products = sorted(
            all_products,
            key=lambda p: len(strip_html(p.get("body_html") or "").strip()),
        )[:max_products]
    else:  # 'all'
        products = all_products[:max_products]

    if not products:
        raise ValueError("No products found to process")

    db.copy_sessions.update_one(
        {"_id": ObjectId(session_id)},
        {"$set": {"products_requested": len(products)}},
    )
    logger.info(f"🎯 [BulkCopy] Processing {len(products)} products (mode={filter_mode})")

    # ── Step 3: extract brand voice ────────────────────────────────────────────
    logger.info("🔍 [BulkCopy] Extracting brand voice...")
    brand_voice = await extract_brand_voice(all_products)
    db.copy_sessions.update_one(
        {"_id": ObjectId(session_id)},
        {"$set": {"brand_voice": brand_voice}},
    )
    logger.info(f"✅ [BulkCopy] Brand voice: {brand_voice.get('summary', '')[:80]}")

    # ── Step 4: load latest audit scores for score delta display ───────────────
    audit_scores = _get_latest_audit_scores(db, session_id)

    # ── Step 5: generate copy in batches, persist progress per batch ───────────
    if not settings.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY not configured")

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    results: list[dict] = []
    batch_size = 8

    for i in range(0, len(products), batch_size):
        batch = products[i:i + batch_size]
        batch_num = i // batch_size + 1
        num_batches = (len(products) + batch_size - 1) // batch_size
        logger.info(f"📦 [BulkCopy] Batch {batch_num}/{num_batches} — {len(batch)} products")

        tasks = [generate_copy_for_product(client, p, brand_voice) for p in batch]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

        for product, copy_result in zip(batch, batch_results):
            pid = str(product.get("id", ""))
            if isinstance(copy_result, Exception):
                logger.error(f"❌ [BulkCopy] Exception for {pid}: {copy_result}")
                copy_result = _fallback_copy_result(product.get("title", ""))

            images = product.get("images") or []
            image_url = images[0].get("src") if images else None

            results.append({
                "product_id": pid,
                "title": product.get("title", ""),
                "handle": product.get("handle", ""),
                "image_url": image_url,
                "current_description": product.get("body_html") or "",
                "current_score": audit_scores.get(pid),
                "generated_description": copy_result.get("body_html", ""),
                "predicted_score": copy_result.get("predicted_content_score", 70),
                "seo_title": copy_result.get("seo_title", ""),
                "meta_description": copy_result.get("meta_description", ""),
                "key_improvements": copy_result.get("key_improvements", []),
                "status": "pending",
                "edited_description": None,
            })

        # Persist progress so the frontend poll shows live count
        db.copy_sessions.update_one(
            {"_id": ObjectId(session_id)},
            {"$set": {"products_generated": len(results), "results": results}},
        )
        logger.info(f"✅ [BulkCopy] Progress: {len(results)}/{len(products)}")

        if i + batch_size < len(products):
            await asyncio.sleep(1.0)

    db.copy_sessions.update_one(
        {"_id": ObjectId(session_id)},
        {"$set": {
            "status": "complete",
            "products_generated": len(results),
            "results": results,
            "completed_at": datetime.utcnow(),
        }},
    )
    logger.info(f"🏁 [BulkCopy] Session {session_id} complete — {len(results)} products generated")


def _get_latest_audit_scores(db, session_id: str) -> dict:
    """Return {product_id: score} from the latest completed audit for this tenant."""
    try:
        session = db.copy_sessions.find_one({"_id": ObjectId(session_id)}, {"tenant_id": 1})
        if not session:
            return {}
        audit = db.audits.find_one(
            {"tenant_id": session.get("tenant_id", ""), "status": "complete"},
            sort=[("completed_at", -1)],
        )
        if not audit:
            return {}
        return {
            str(pr.get("shopify_product_id", "")): pr.get("score", 0)
            for pr in audit.get("product_results", [])
            if pr.get("shopify_product_id")
        }
    except Exception as e:
        logger.warning(f"⚠️ [BulkCopy] Could not fetch audit scores: {e}")
        return {}
