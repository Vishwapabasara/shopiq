from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId
import inspect
import logging

from app.dependencies import get_db, get_current_tenant
from app.config import settings

router = APIRouter(prefix="/returns", tags=["returns"])
logger = logging.getLogger(__name__)


async def aw(result):
    if inspect.isawaitable(result):
        return await result
    return result


@router.post("/analyze")
async def trigger_analysis(tenant: dict = Depends(get_current_tenant)):
    db = await get_db()

    # Return existing in-progress analysis
    running = await aw(db.return_analyses.find_one({
        "tenant_id": str(tenant["_id"]),
        "status": {"$in": ["queued", "running"]},
    }))
    if running:
        return {
            "analysis_id": str(running["_id"]),
            "status": running["status"],
            "message": "Analysis already in progress",
        }

    now = datetime.utcnow()
    doc = {
        "tenant_id": str(tenant["_id"]),
        "shop_domain": tenant["shop_domain"],
        "status": "queued",
        "orders_analyzed": 0,
        "total_refunded": 0,
        "return_rate": 0.0,
        "total_refund_value": 0.0,
        "currency": "USD",
        "reason_breakdown": {},
        "top_returned_products": [],
        "flagged_customers": [],
        "monthly_trend": [],
        "insights": [],
        "triggered_by": "manual",
        "celery_task_id": None,
        "created_at": now,
        "completed_at": None,
        "error_message": None,
    }
    result = await aw(db.return_analyses.insert_one(doc))
    analysis_id = str(result.inserted_id)

    from app.workers.returns_worker import analyze_returns_task
    encrypted_token = tenant.get("access_token", "")
    task = analyze_returns_task.delay(analysis_id, tenant["shop_domain"], encrypted_token)

    await aw(db.return_analyses.update_one(
        {"_id": ObjectId(analysis_id)},
        {"$set": {"celery_task_id": task.id}},
    ))

    logger.info(f"📋 Return analysis {analysis_id} queued for {tenant['shop_domain']}")
    return {"analysis_id": analysis_id, "status": "queued", "message": "Return analysis started"}


@router.get("/latest")
async def get_latest(tenant: dict = Depends(get_current_tenant)):
    db = await get_db()
    doc = await aw(db.return_analyses.find_one(
        {"tenant_id": str(tenant["_id"])},
        sort=[("created_at", -1)],
    ))
    if not doc:
        return None
    doc["_id"] = str(doc["_id"])
    return doc


@router.get("/history")
async def get_history(tenant: dict = Depends(get_current_tenant)):
    db = await get_db()
    cursor = db.return_analyses.find(
        {"tenant_id": str(tenant["_id"]), "status": "complete"},
        sort=[("created_at", -1)],
        limit=10,
    )
    history = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        history.append(doc)
    return {"history": history}


@router.post("/{analysis_id}/cancel")
async def cancel_analysis(analysis_id: str, tenant: dict = Depends(get_current_tenant)):
    db = await get_db()
    try:
        doc = await aw(db.return_analyses.find_one({"_id": ObjectId(analysis_id)}))
    except Exception:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if not doc or doc["tenant_id"] != str(tenant["_id"]):
        raise HTTPException(status_code=404, detail="Analysis not found")
    if doc["status"] not in ("queued", "running"):
        return {"status": doc["status"], "message": "Analysis already finished"}

    # Revoke Celery task if we have the ID
    celery_task_id = doc.get("celery_task_id")
    if celery_task_id:
        try:
            from app.workers.celery_app import celery_app
            celery_app.control.revoke(celery_task_id, terminate=True, signal="SIGTERM")
        except Exception:
            pass

    await aw(db.return_analyses.update_one(
        {"_id": ObjectId(analysis_id)},
        {"$set": {"status": "failed", "error_message": "Cancelled by user"}},
    ))
    logger.info(f"🛑 Analysis {analysis_id} cancelled by user")
    return {"status": "failed", "message": "Analysis cancelled"}


@router.get("/{analysis_id}/status")
async def get_status(analysis_id: str, tenant: dict = Depends(get_current_tenant)):
    db = await get_db()
    try:
        doc = await aw(db.return_analyses.find_one({"_id": ObjectId(analysis_id)}))
    except Exception:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if not doc or doc["tenant_id"] != str(tenant["_id"]):
        raise HTTPException(status_code=404, detail="Analysis not found")
    return {
        "analysis_id": analysis_id,
        "status": doc["status"],
        "orders_analyzed": doc.get("orders_analyzed", 0),
        "error_message": doc.get("error_message"),
    }


@router.post("/seed-demo")
async def seed_demo(tenant: dict = Depends(get_current_tenant)):
    """Insert a pre-computed demo analysis directly into MongoDB (bypasses Celery)."""
    db = await get_db()
    now = datetime.utcnow()

    demo_doc = {
        "tenant_id": str(tenant["_id"]),
        "shop_domain": tenant["shop_domain"],
        "status": "complete",
        "orders_analyzed": 15,
        "total_refunded": 6,
        "return_rate": 40.0,
        "total_refund_value": 312.45,
        "currency": "USD",
        "reason_breakdown": {
            "size_fit": 2,
            "wrong_item": 1,
            "damaged": 1,
            "quality": 1,
            "not_needed": 1,
        },
        "top_returned_products": [
            {
                "product_id": "8001",
                "title": "Classic Slim Fit T-Shirt",
                "handle": "classic-slim-fit-t-shirt",
                "image_url": None,
                "total_orders": 4,
                "total_returns": 3,
                "return_rate": 75.0,
                "refund_value": 89.97,
                "top_reason": "size_fit",
            },
            {
                "product_id": "8002",
                "title": "Wireless Noise-Cancelling Headphones",
                "handle": "wireless-noise-cancelling-headphones",
                "image_url": None,
                "total_orders": 3,
                "total_returns": 2,
                "return_rate": 66.7,
                "refund_value": 159.98,
                "top_reason": "damaged",
            },
            {
                "product_id": "8003",
                "title": "Premium Leather Wallet",
                "handle": "premium-leather-wallet",
                "image_url": None,
                "total_orders": 5,
                "total_returns": 1,
                "return_rate": 20.0,
                "refund_value": 39.99,
                "top_reason": "wrong_item",
            },
            {
                "product_id": "8004",
                "title": "Running Sneakers Pro",
                "handle": "running-sneakers-pro",
                "image_url": None,
                "total_orders": 3,
                "total_returns": 0,
                "return_rate": 0.0,
                "refund_value": 0.0,
                "top_reason": "other",
            },
        ],
        "flagged_customers": [
            {
                "customer_id": "cust_001",
                "name": "Alice Brown",
                "email": "alice@example.com",
                "total_orders": 2,
                "total_returns": 2,
                "return_rate": 100.0,
                "risk_level": "high",
            },
            {
                "customer_id": "cust_002",
                "name": "Bob Smith",
                "email": "bob@example.com",
                "total_orders": 3,
                "total_returns": 1,
                "return_rate": 33.3,
                "risk_level": "medium",
            },
        ],
        "monthly_trend": [
            {"month": "2025-01", "orders": 4, "returns": 2, "return_rate": 50.0, "refund_value": 109.98},
            {"month": "2025-02", "orders": 5, "returns": 1, "return_rate": 20.0, "refund_value": 39.99},
            {"month": "2025-03", "orders": 6, "returns": 3, "return_rate": 50.0, "refund_value": 162.48},
        ],
        "insights": [
            "Return rate of 40.0% is above the e-commerce average — prioritise the top reasons below.",
            "33% of returns cite size/fit issues — consider adding a size guide to affected product listings.",
            '"Classic Slim Fit T-Shirt" has the highest return rate at 75.0% (3 of 4 orders).',
            "2 customer(s) flagged with a return rate above 30% — review their order history for potential abuse.",
        ],
        "triggered_by": "demo",
        "celery_task_id": None,
        "created_at": now,
        "completed_at": now,
        "error_message": None,
    }

    result = await aw(db.return_analyses.insert_one(demo_doc))
    analysis_id = str(result.inserted_id)
    logger.info(f"🌱 Demo analysis {analysis_id} seeded for {tenant['shop_domain']}")
    return {"analysis_id": analysis_id, "status": "complete", "message": "Demo data loaded"}


@router.get("/{analysis_id}/results")
async def get_results(analysis_id: str, tenant: dict = Depends(get_current_tenant)):
    db = await get_db()
    try:
        doc = await aw(db.return_analyses.find_one({"_id": ObjectId(analysis_id)}))
    except Exception:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if not doc or doc["tenant_id"] != str(tenant["_id"]):
        raise HTTPException(status_code=404, detail="Analysis not found")
    if doc["status"] != "complete":
        raise HTTPException(status_code=400, detail="Analysis not yet complete")
    doc["_id"] = str(doc["_id"])
    return doc
