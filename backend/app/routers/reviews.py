"""
ReviewReply AI — REST Router
──────────────────────────────
POST /reviews/generate        — start response generation for stored reviews
POST /reviews/seed-demo       — seed demo reviews and trigger generation
GET  /reviews/latest          — latest batch for this tenant
GET  /reviews/{id}/status     — poll generation progress
GET  /reviews/{id}/results    — full results when complete
PATCH /reviews/{id}/review/{rid} — save in-place edit + approve
POST /reviews/{id}/post       — mark selected reviews as posted
POST /reviews/{id}/cancel     — cancel in-progress generation
"""
import inspect
import logging
from datetime import datetime

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.dependencies import get_current_tenant, get_db
from app.utils.crypto import decrypt_token

router = APIRouter(prefix="/reviews", tags=["reviews"])
logger = logging.getLogger(__name__)


async def aw(result):
    if inspect.isawaitable(result):
        return await result
    return result


# ── Request models ────────────────────────────────────────────────────────────

class EditReviewRequest(BaseModel):
    edited_response: str


class PostRequest(BaseModel):
    review_ids: list[str]


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _dispatch_batch(db, tenant_id: str, shop_domain: str, access_token: str, reviews: list[dict]) -> str:
    """Insert a new batch doc and queue the Celery task. Returns batch_id."""
    now = datetime.utcnow()
    doc = {
        "tenant_id": tenant_id,
        "shop_domain": shop_domain,
        "status": "queued",
        "brand_voice": None,
        "reviews_count": len(reviews),
        "responses_generated": 0,
        "reviews": reviews,
        "celery_task_id": None,
        "created_at": now,
        "completed_at": None,
        "error_message": None,
    }
    result = await aw(db.review_batches.insert_one(doc))
    batch_id = str(result.inserted_id)

    from app.workers.review_worker import run_review_task
    task = run_review_task.delay(batch_id, shop_domain, access_token)
    await aw(db.review_batches.update_one(
        {"_id": result.inserted_id},
        {"$set": {"celery_task_id": task.id}},
    ))
    return batch_id


# ── POST /reviews/seed-demo ───────────────────────────────────────────────────

@router.post("/seed-demo")
async def seed_demo(tenant: dict = Depends(get_current_tenant)):
    db = await get_db()
    tenant_id = str(tenant["_id"])

    running = await aw(db.review_batches.find_one({
        "tenant_id": tenant_id,
        "status": {"$in": ["queued", "running"]},
    }))
    if running:
        return {"batch_id": str(running["_id"]), "status": running["status"], "message": "Already in progress"}

    # Try to get real product titles from latest audit for realistic demo reviews
    products = []
    try:
        audit = await aw(db.audits.find_one(
            {"tenant_id": tenant_id, "status": "complete"},
            sort=[("completed_at", -1)],
        ))
        if audit:
            products = [
                {"id": pr.get("shopify_product_id", ""), "title": pr.get("title", ""), "images": [{"src": pr.get("image_url")}] if pr.get("image_url") else []}
                for pr in audit.get("product_results", [])[:5]
            ]
    except Exception:
        pass

    from app.services.review_service import make_demo_reviews
    reviews = make_demo_reviews(products)

    raw_token = tenant.get("access_token", "")
    access_token = decrypt_token(raw_token) if raw_token not in ("mock_token_not_real", "") else raw_token

    batch_id = await _dispatch_batch(db, tenant_id, tenant["shop_domain"], raw_token, reviews)
    logger.info(f"🌱 [ReviewReply] Demo batch {batch_id} seeded with {len(reviews)} reviews")
    return {"batch_id": batch_id, "status": "queued", "message": f"Generating responses for {len(reviews)} demo reviews"}


# ── POST /reviews/generate ────────────────────────────────────────────────────

@router.post("/generate")
async def generate(tenant: dict = Depends(get_current_tenant)):
    """Re-run generation on the latest batch (regenerates all responses)."""
    db = await get_db()
    tenant_id = str(tenant["_id"])

    running = await aw(db.review_batches.find_one({
        "tenant_id": tenant_id,
        "status": {"$in": ["queued", "running"]},
    }))
    if running:
        return {"batch_id": str(running["_id"]), "status": running["status"], "message": "Already in progress"}

    latest = await aw(db.review_batches.find_one(
        {"tenant_id": tenant_id},
        sort=[("created_at", -1)],
    ))
    if not latest:
        raise HTTPException(400, "No reviews found — use seed-demo first")

    # Reset statuses for re-generation
    reviews = [
        {**r, "ai_response": None, "edited_response": None, "status": "pending"}
        for r in latest.get("reviews", [])
    ]
    raw_token = tenant.get("access_token", "")
    batch_id = await _dispatch_batch(db, tenant_id, tenant["shop_domain"], raw_token, reviews)
    return {"batch_id": batch_id, "status": "queued", "message": "Re-generating responses"}


# ── GET /reviews/latest ───────────────────────────────────────────────────────

@router.get("/latest")
async def latest(tenant: dict = Depends(get_current_tenant)):
    db = await get_db()
    batch = await aw(db.review_batches.find_one(
        {"tenant_id": str(tenant["_id"])},
        sort=[("created_at", -1)],
    ))
    if not batch:
        return None
    batch["_id"] = str(batch["_id"])
    return batch


# ── GET /reviews/{id}/status ──────────────────────────────────────────────────

@router.get("/{batch_id}/status")
async def status(batch_id: str, tenant: dict = Depends(get_current_tenant)):
    db = await get_db()
    batch = await aw(db.review_batches.find_one(
        {"_id": ObjectId(batch_id), "tenant_id": str(tenant["_id"])},
        {"status": 1, "reviews_count": 1, "responses_generated": 1, "error_message": 1},
    ))
    if not batch:
        raise HTTPException(404, "Batch not found")
    return {
        "batch_id": batch_id,
        "status": batch["status"],
        "reviews_count": batch.get("reviews_count", 0),
        "responses_generated": batch.get("responses_generated", 0),
        "error_message": batch.get("error_message"),
    }


# ── GET /reviews/{id}/results ─────────────────────────────────────────────────

@router.get("/{batch_id}/results")
async def results(batch_id: str, tenant: dict = Depends(get_current_tenant)):
    db = await get_db()
    batch = await aw(db.review_batches.find_one(
        {"_id": ObjectId(batch_id), "tenant_id": str(tenant["_id"])},
    ))
    if not batch:
        raise HTTPException(404, "Batch not found")
    batch["_id"] = str(batch["_id"])
    return batch


# ── PATCH /reviews/{id}/review/{rid} ─────────────────────────────────────────

@router.patch("/{batch_id}/review/{review_id}")
async def edit_review(
    batch_id: str,
    review_id: str,
    body: EditReviewRequest,
    tenant: dict = Depends(get_current_tenant),
):
    db = await get_db()
    result = await aw(db.review_batches.update_one(
        {"_id": ObjectId(batch_id), "tenant_id": str(tenant["_id"]), "reviews.review_id": review_id},
        {"$set": {
            "reviews.$.edited_response": body.edited_response,
            "reviews.$.status": "approved",
        }},
    ))
    if result.matched_count == 0:
        raise HTTPException(404, "Batch or review not found")
    return {"success": True}


# ── POST /reviews/{id}/post ───────────────────────────────────────────────────

@router.post("/{batch_id}/post")
async def post_reviews(
    batch_id: str,
    body: PostRequest,
    tenant: dict = Depends(get_current_tenant),
):
    """Mark selected reviews as posted (platform integration in future versions)."""
    db = await get_db()
    batch = await aw(db.review_batches.find_one(
        {"_id": ObjectId(batch_id), "tenant_id": str(tenant["_id"])},
        {"reviews": 1},
    ))
    if not batch:
        raise HTTPException(404, "Batch not found")

    rid_set = set(body.review_ids)
    posted = 0
    for r in batch.get("reviews", []):
        if r["review_id"] in rid_set:
            await aw(db.review_batches.update_one(
                {"_id": ObjectId(batch_id), "reviews.review_id": r["review_id"]},
                {"$set": {"reviews.$.status": "posted"}},
            ))
            posted += 1

    logger.info(f"✅ [ReviewReply] Marked {posted}/{len(body.review_ids)} reviews as posted for {tenant['shop_domain']}")
    return {"success": True, "posted": posted, "total": len(body.review_ids)}


# ── POST /reviews/{id}/cancel ─────────────────────────────────────────────────

@router.post("/{batch_id}/cancel")
async def cancel(batch_id: str, tenant: dict = Depends(get_current_tenant)):
    db = await get_db()
    batch = await aw(db.review_batches.find_one(
        {"_id": ObjectId(batch_id), "tenant_id": str(tenant["_id"])},
    ))
    if not batch:
        raise HTTPException(404, "Batch not found")
    if batch["status"] not in ("queued", "running"):
        return {"status": batch["status"], "message": "Batch already finished"}

    celery_task_id = batch.get("celery_task_id")
    if celery_task_id:
        try:
            from app.workers.celery_app import celery_app
            celery_app.control.revoke(celery_task_id, terminate=True, signal="SIGTERM")
        except Exception:
            pass

    await aw(db.review_batches.update_one(
        {"_id": ObjectId(batch_id)},
        {"$set": {"status": "failed", "error_message": "Cancelled by user"}},
    ))
    logger.info(f"🛑 [ReviewReply] Batch {batch_id} cancelled")
    return {"status": "failed", "message": "Generation cancelled"}
