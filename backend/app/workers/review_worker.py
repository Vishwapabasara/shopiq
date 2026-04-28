"""
ReviewReply AI — Celery Worker
────────────────────────────────
1. Load reviews (demo seed or stored)
2. Extract brand voice (reuse from latest copy session or audit products)
3. Generate AI responses in parallel batches
4. Update DB with live progress
"""
import asyncio
import logging
from datetime import datetime

from bson import ObjectId
from celery import Task

from app.workers.celery_app import celery_app
from app.config import settings
from app.utils.crypto import decrypt_token

logger = logging.getLogger(__name__)

print("=" * 50)
print("🔧 REVIEW WORKER MODULE LOADED")
print("=" * 50)


def get_sync_db():
    from pymongo import MongoClient
    client = MongoClient(settings.MONGO_URI)
    return client.get_default_database()


@celery_app.task(bind=True, name="app.workers.review_worker.run_review_task")
def run_review_task(
    self: Task,
    batch_id: str,
    shop_domain: str,
    encrypted_token: str,
):
    logger.info(f"🚀 [ReviewReply] Task received — batch {batch_id}, shop {shop_domain}")
    db = get_sync_db()

    try:
        db.review_batches.update_one(
            {"_id": ObjectId(batch_id)},
            {"$set": {"status": "running", "updated_at": datetime.utcnow()}},
        )

        access_token = decrypt_token(encrypted_token)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(
                _run_review_async(batch_id, shop_domain, access_token, db)
            )
            logger.info(f"✅ [ReviewReply] Batch {batch_id} completed")
        finally:
            loop.close()

    except Exception as exc:
        logger.error(f"❌ [ReviewReply] Batch {batch_id} failed: {exc}", exc_info=True)
        try:
            db.review_batches.update_one(
                {"_id": ObjectId(batch_id)},
                {"$set": {
                    "status": "failed",
                    "error_message": str(exc),
                    "completed_at": datetime.utcnow(),
                }},
            )
        except Exception as e:
            logger.error(f"❌ Failed to mark batch as failed: {e}")


async def _run_review_async(batch_id: str, shop_domain: str, access_token: str, db):
    from app.services.review_service import generate_responses_batch
    from app.services.copy_service import extract_brand_voice, _default_brand_voice

    # ── Load reviews stored on the batch ──────────────────────────────────────
    batch_doc = db.review_batches.find_one({"_id": ObjectId(batch_id)})
    reviews = batch_doc.get("reviews", [])
    if not reviews:
        raise ValueError("No reviews found in batch")

    db.review_batches.update_one(
        {"_id": ObjectId(batch_id)},
        {"$set": {"reviews_count": len(reviews)}},
    )
    logger.info(f"🎯 [ReviewReply] Generating responses for {len(reviews)} reviews")

    # ── Extract brand voice ────────────────────────────────────────────────────
    brand_voice = _get_brand_voice(db, batch_doc.get("tenant_id", ""), shop_domain, access_token)

    db.review_batches.update_one(
        {"_id": ObjectId(batch_id)},
        {"$set": {"brand_voice": brand_voice}},
    )
    logger.info(f"✅ [ReviewReply] Brand voice: {brand_voice.get('summary', '')[:60]}")

    # ── Generate responses in batches ──────────────────────────────────────────
    from google import genai
    if not settings.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY not configured")

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    from app.services.review_service import generate_review_response, _fallback_response
    from app.services.review_service import _detect_sentiment

    batch_size = 10
    for i in range(0, len(reviews), batch_size):
        batch = reviews[i:i + batch_size]
        tasks = [generate_review_response(client, r, brand_voice) for r in batch]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

        for review, result in zip(batch, batch_results):
            rid = review["review_id"]
            if isinstance(result, Exception):
                result = _fallback_response(review.get("rating", 3), "neutral")

            # Update this specific review in the array
            db.review_batches.update_one(
                {"_id": ObjectId(batch_id), "reviews.review_id": rid},
                {"$set": {
                    "reviews.$.ai_response": result.get("response", ""),
                    "reviews.$.sentiment": result.get("sentiment", _detect_sentiment(review.get("rating", 3), review.get("body", ""))),
                    "reviews.$.is_escalation": result.get("is_escalation", False),
                }},
            )

        generated_so_far = min(i + batch_size, len(reviews))
        db.review_batches.update_one(
            {"_id": ObjectId(batch_id)},
            {"$set": {"responses_generated": generated_so_far}},
        )
        logger.info(f"✅ [ReviewReply] Progress: {generated_so_far}/{len(reviews)}")

        if i + batch_size < len(reviews):
            await asyncio.sleep(0.5)

    db.review_batches.update_one(
        {"_id": ObjectId(batch_id)},
        {"$set": {
            "status": "complete",
            "responses_generated": len(reviews),
            "completed_at": datetime.utcnow(),
        }},
    )
    logger.info(f"🏁 [ReviewReply] Batch {batch_id} complete — {len(reviews)} responses generated")


def _get_brand_voice(db, tenant_id: str, shop_domain: str, access_token: str) -> dict:
    """Try to reuse brand voice from latest copy session; otherwise use defaults."""
    from app.services.copy_service import _default_brand_voice
    try:
        session = db.copy_sessions.find_one(
            {"tenant_id": tenant_id, "status": "complete"},
            sort=[("completed_at", -1)],
        )
        if session and session.get("brand_voice"):
            return session["brand_voice"]
    except Exception as e:
        logger.warning(f"⚠️ [ReviewReply] Could not load brand voice from copy session: {e}")
    return _default_brand_voice()
