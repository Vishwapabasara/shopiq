from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId
import inspect
import logging

from app.dependencies import get_db, get_current_tenant
from app.config import settings

router = APIRouter(prefix="/price", tags=["price"])
logger = logging.getLogger(__name__)


async def aw(result):
    if inspect.isawaitable(result):
        return await result
    return result


@router.post("/analyze")
async def trigger_analysis(tenant: dict = Depends(get_current_tenant)):
    db = await get_db()

    running = await aw(db.price_analyses.find_one({
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
        "total_products": 0,
        "products_analyzed": 0,
        "products_undercut": 0,
        "products_competitive": 0,
        "products_overpriced": 0,
        "products_no_data": 0,
        "avg_price_gap_pct": 0.0,
        "currency": "USD",
        "products": [],
        "top_competitors": [],
        "insights": [],
        "triggered_by": "manual",
        "celery_task_id": None,
        "created_at": now,
        "completed_at": None,
        "error_message": None,
        "serpapi_configured": bool(settings.SERPAPI_KEY),
    }
    result = await aw(db.price_analyses.insert_one(doc))
    analysis_id = str(result.inserted_id)

    from app.workers.price_worker import analyze_prices_task
    encrypted_token = tenant.get("access_token", "")
    task = analyze_prices_task.delay(analysis_id, tenant["shop_domain"], encrypted_token)

    await aw(db.price_analyses.update_one(
        {"_id": ObjectId(analysis_id)},
        {"$set": {"celery_task_id": task.id}},
    ))

    logger.info(f"💰 Price analysis {analysis_id} queued for {tenant['shop_domain']}")
    return {"analysis_id": analysis_id, "status": "queued", "message": "Price analysis started"}


@router.post("/seed-demo")
async def seed_demo(tenant: dict = Depends(get_current_tenant)):
    """Insert pre-computed demo analysis directly into MongoDB (bypasses Celery and SerpAPI)."""
    db = await get_db()
    from app.workers.price_worker import _build_mock_results
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
        "serpapi_configured": True,
        **_build_mock_results(),
    }

    result = await aw(db.price_analyses.insert_one(demo_doc))
    analysis_id = str(result.inserted_id)
    logger.info(f"🌱 Demo price analysis {analysis_id} seeded for {tenant['shop_domain']}")
    return {"analysis_id": analysis_id, "status": "complete", "message": "Demo data loaded"}


@router.get("/config")
async def get_config(tenant: dict = Depends(get_current_tenant)):
    """Return whether SerpAPI is configured for this deployment."""
    return {"serpapi_configured": bool(settings.SERPAPI_KEY)}


@router.get("/latest")
async def get_latest(tenant: dict = Depends(get_current_tenant)):
    db = await get_db()
    doc = await aw(db.price_analyses.find_one(
        {"tenant_id": str(tenant["_id"])},
        sort=[("created_at", -1)],
    ))
    if not doc:
        return None
    doc["_id"] = str(doc["_id"])
    return doc


@router.post("/{analysis_id}/cancel")
async def cancel_analysis(analysis_id: str, tenant: dict = Depends(get_current_tenant)):
    db = await get_db()
    try:
        doc = await aw(db.price_analyses.find_one({"_id": ObjectId(analysis_id)}))
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

    await aw(db.price_analyses.update_one(
        {"_id": ObjectId(analysis_id)},
        {"$set": {"status": "failed", "error_message": "Cancelled by user"}},
    ))
    return {"status": "failed", "message": "Analysis cancelled"}


@router.get("/{analysis_id}/status")
async def get_status(analysis_id: str, tenant: dict = Depends(get_current_tenant)):
    db = await get_db()
    try:
        doc = await aw(db.price_analyses.find_one({"_id": ObjectId(analysis_id)}))
    except Exception:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if not doc or doc["tenant_id"] != str(tenant["_id"]):
        raise HTTPException(status_code=404, detail="Analysis not found")
    return {
        "analysis_id": analysis_id,
        "status": doc["status"],
        "total_products": doc.get("total_products", 0),
        "products_analyzed": doc.get("products_analyzed", 0),
        "error_message": doc.get("error_message"),
    }


@router.get("/{analysis_id}/results")
async def get_results(analysis_id: str, tenant: dict = Depends(get_current_tenant)):
    db = await get_db()
    try:
        doc = await aw(db.price_analyses.find_one({"_id": ObjectId(analysis_id)}))
    except Exception:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if not doc or doc["tenant_id"] != str(tenant["_id"]):
        raise HTTPException(status_code=404, detail="Analysis not found")
    if doc["status"] != "complete":
        raise HTTPException(status_code=400, detail="Analysis not yet complete")
    doc["_id"] = str(doc["_id"])
    return doc
