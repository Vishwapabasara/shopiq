from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId
import inspect
import logging

from app.dependencies import get_db, get_current_tenant
from app.config import settings

router = APIRouter(prefix="/stock", tags=["stock"])
logger = logging.getLogger(__name__)


async def aw(result):
    if inspect.isawaitable(result):
        return await result
    return result


@router.post("/analyze")
async def trigger_analysis(tenant: dict = Depends(get_current_tenant)):
    db = await get_db()

    running = await aw(db.stock_analyses.find_one({
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
        "total_skus": 0,
        "skus_urgent": 0,
        "skus_healthy": 0,
        "skus_monitor": 0,
        "skus_dead_stock": 0,
        "total_revenue_at_risk": 0.0,
        "dead_stock_value": 0.0,
        "total_inventory_value": 0.0,
        "capital_efficiency": 0.0,
        "currency": "USD",
        "avg_days_to_stockout": 0.0,
        "products": [],
        "insights": [],
        "orders_analyzed": 0,
        "triggered_by": "manual",
        "celery_task_id": None,
        "created_at": now,
        "completed_at": None,
        "error_message": None,
    }
    result = await aw(db.stock_analyses.insert_one(doc))
    analysis_id = str(result.inserted_id)

    from app.workers.stock_worker import analyze_stock_task
    encrypted_token = tenant.get("access_token", "")
    task = analyze_stock_task.delay(analysis_id, tenant["shop_domain"], encrypted_token)

    await aw(db.stock_analyses.update_one(
        {"_id": ObjectId(analysis_id)},
        {"$set": {"celery_task_id": task.id}},
    ))

    logger.info(f"📋 Stock analysis {analysis_id} queued for {tenant['shop_domain']}")
    return {"analysis_id": analysis_id, "status": "queued", "message": "Stock analysis started"}


@router.post("/seed-demo")
async def seed_demo(tenant: dict = Depends(get_current_tenant)):
    """Insert pre-computed demo analysis directly into MongoDB (bypasses Celery)."""
    db = await get_db()
    from app.workers.stock_worker import _build_mock_results
    now = datetime.utcnow()

    demo_doc = {
        "tenant_id": str(tenant["_id"]),
        "shop_domain": tenant["shop_domain"],
        "status": "complete",
        "triggered_by": "demo",
        "celery_task_id": None,
        "created_at": now,
        "completed_at": now,
        "error_message": None,
        **_build_mock_results(),
    }

    result = await aw(db.stock_analyses.insert_one(demo_doc))
    analysis_id = str(result.inserted_id)
    logger.info(f"🌱 Demo stock analysis {analysis_id} seeded for {tenant['shop_domain']}")
    return {"analysis_id": analysis_id, "status": "complete", "message": "Demo data loaded"}


@router.get("/latest")
async def get_latest(tenant: dict = Depends(get_current_tenant)):
    db = await get_db()
    doc = await aw(db.stock_analyses.find_one(
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
    cursor = db.stock_analyses.find(
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
        doc = await aw(db.stock_analyses.find_one({"_id": ObjectId(analysis_id)}))
    except Exception:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if not doc or doc["tenant_id"] != str(tenant["_id"]):
        raise HTTPException(status_code=404, detail="Analysis not found")
    if doc["status"] not in ("queued", "running"):
        return {"status": doc["status"], "message": "Analysis already finished"}

    celery_task_id = doc.get("celery_task_id")
    if celery_task_id:
        try:
            from app.workers.celery_app import celery_app
            celery_app.control.revoke(celery_task_id, terminate=True, signal="SIGTERM")
        except Exception:
            pass

    await aw(db.stock_analyses.update_one(
        {"_id": ObjectId(analysis_id)},
        {"$set": {"status": "failed", "error_message": "Cancelled by user"}},
    ))
    logger.info(f"🛑 Stock analysis {analysis_id} cancelled by user")
    return {"status": "failed", "message": "Analysis cancelled"}


@router.get("/{analysis_id}/status")
async def get_status(analysis_id: str, tenant: dict = Depends(get_current_tenant)):
    db = await get_db()
    try:
        doc = await aw(db.stock_analyses.find_one({"_id": ObjectId(analysis_id)}))
    except Exception:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if not doc or doc["tenant_id"] != str(tenant["_id"]):
        raise HTTPException(status_code=404, detail="Analysis not found")
    return {
        "analysis_id": analysis_id,
        "status": doc["status"],
        "total_skus": doc.get("total_skus", 0),
        "error_message": doc.get("error_message"),
    }


@router.get("/{analysis_id}/results")
async def get_results(analysis_id: str, tenant: dict = Depends(get_current_tenant)):
    db = await get_db()
    try:
        doc = await aw(db.stock_analyses.find_one({"_id": ObjectId(analysis_id)}))
    except Exception:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if not doc or doc["tenant_id"] != str(tenant["_id"]):
        raise HTTPException(status_code=404, detail="Analysis not found")
    if doc["status"] != "complete":
        raise HTTPException(status_code=400, detail="Analysis not yet complete")
    doc["_id"] = str(doc["_id"])
    return doc
