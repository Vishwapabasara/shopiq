from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId
import inspect
import logging

from app.dependencies import get_db, get_current_tenant

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
