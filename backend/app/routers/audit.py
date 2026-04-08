from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId
import inspect
import logging

from app.dependencies import get_db, get_current_tenant
from app.models.schemas import AuditRunResponse, AuditStatusResponse, AuditStatus
from app.workers.audit_worker import run_audit_task

router = APIRouter(prefix="/audit", tags=["audit"])
logger = logging.getLogger(__name__)


async def aw(result):
    if inspect.isawaitable(result):
        return await result
    return result


async def _to_list(cursor, length=1000):
    try:
        return await cursor.to_list(length=length)
    except TypeError:
        return list(cursor)


# ── POST /run ─────────────────────────────────────────────────────────────────

@router.post("/run", response_model=AuditRunResponse)
async def trigger_audit(tenant: dict = Depends(get_current_tenant)):
    logger.info(f"🔍 Audit triggered for shop: {tenant.get('shop_domain')}")

    from app.workers.celery_app import celery_app
    logger.info(f"📡 Celery broker: {celery_app.conf.broker_url}")

    db = await get_db()

    running = await aw(db.audits.find_one({
        "tenant_id": str(tenant["_id"]),
        "status": {"$in": [AuditStatus.QUEUED.value, AuditStatus.RUNNING.value]},
    }))

    if running:
        raise HTTPException(409, "An audit is already in progress for this store")

    audit_doc = {
        "tenant_id": str(tenant["_id"]),
        "status": AuditStatus.QUEUED.value,
        "triggered_by": "manual",
        "products_scanned": 0,
        "critical_count": 0,
        "warning_count": 0,
        "info_count": 0,
        "product_results": [],
        "created_at": datetime.utcnow(),
    }

    result = await aw(db.audits.insert_one(audit_doc))
    audit_id = str(result.inserted_id)
    logger.info(f"📝 Audit document created: {audit_id}")

    try:
        task = run_audit_task.delay(
            audit_id,
            tenant["shop_domain"],
            tenant["access_token"],
        )
        logger.info(f"✅ Celery task queued: {task.id}")

        await aw(db.audits.update_one(
            {"_id": result.inserted_id},
            {"$set": {"celery_task_id": task.id}}
        ))

        return AuditRunResponse(
            audit_id=audit_id,
            status=AuditStatus.QUEUED,
            message="Audit started — this takes 2–5 minutes depending on your product count",
        )

    except Exception as e:
        logger.error(f"❌ Failed to queue audit task: {e}", exc_info=True)
        await aw(db.audits.update_one(
            {"_id": result.inserted_id},
            {"$set": {
                "status": AuditStatus.FAILED.value,
                "error_message": f"Failed to start: {str(e)}"
            }}
        ))
        raise HTTPException(500, f"Failed to start audit: {str(e)}")


# ── GET /test-celery  (specific — must be before /{audit_id}/...) ─────────────

@router.get("/test-celery")
async def test_celery():
    from app.workers.celery_app import celery_app
    try:
        inspector = celery_app.control.inspect(timeout=3)
        active_workers = inspector.active() or {}
        registered_tasks = inspector.registered() or {}
        return {
            "success": True,
            "broker": str(celery_app.conf.broker_url)[:60],
            "active_workers": list(active_workers.keys()),
            "registered_tasks": registered_tasks,
        }
    except Exception as e:
        logger.error(f"❌ Celery test failed: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


# ── GET /history  (specific — must be before /{audit_id}/...) ────────────────

@router.get("/history")
async def get_audit_history(
    tenant: dict = Depends(get_current_tenant),
    limit: int = 10,
):
    logger.info(f"📜 Fetching audit history for: {tenant.get('shop_domain')}")
    db = await get_db()

    cursor = db.audits.find(
        {"tenant_id": str(tenant["_id"]), "status": AuditStatus.COMPLETE.value},
        {"_id": 1, "overall_score": 1, "category_scores": 1,
         "products_scanned": 1, "critical_count": 1, "created_at": 1, "completed_at": 1}
    ).sort("created_at", -1).limit(limit)

    docs = await _to_list(cursor)
    for doc in docs:
        doc["_id"] = str(doc["_id"])

    logger.info(f"📜 Found {len(docs)} completed audits")
    return {"history": docs}


# ── GET /{audit_id}/status ────────────────────────────────────────────────────

@router.get("/{audit_id}/status", response_model=AuditStatusResponse)
async def get_audit_status(audit_id: str, tenant: dict = Depends(get_current_tenant)):
    db = await get_db()
    try:
        audit = await aw(db.audits.find_one({
            "_id": ObjectId(audit_id),
            "tenant_id": str(tenant["_id"]),
        }))
    except Exception as e:
        raise HTTPException(500, f"Database error: {str(e)}")

    if not audit:
        raise HTTPException(404, "Audit not found")

    return AuditStatusResponse(
        audit_id=audit_id,
        status=audit["status"],
        products_scanned=audit.get("products_scanned", 0),
        overall_score=audit.get("overall_score"),
        completed_at=audit.get("completed_at"),
        error_message=audit.get("error_message"),
    )


# ── GET /{audit_id}/results ───────────────────────────────────────────────────

@router.get("/{audit_id}/results")
async def get_audit_results(
    audit_id: str,
    severity: str | None = None,
    sort: str = "score_asc",
    limit: int = 50,
    offset: int = 0,
    tenant: dict = Depends(get_current_tenant),
):
    db = await get_db()
    try:
        audit = await aw(db.audits.find_one({
            "_id": ObjectId(audit_id),
            "tenant_id": str(tenant["_id"]),
        }))
    except Exception as e:
        raise HTTPException(500, f"Database error: {str(e)}")

    if not audit:
        raise HTTPException(404, "Audit not found")

    if audit["status"] != AuditStatus.COMPLETE.value:
        raise HTTPException(400, f"Audit not complete yet (status: {audit['status']})")

    products = audit.get("product_results", [])

    if severity in ("critical", "warning", "info"):
        products = [p for p in products if any(
            i["severity"] == severity for i in p.get("issues", [])
        )]

    if sort == "score_asc":
        products.sort(key=lambda x: x["score"])
    elif sort == "score_desc":
        products.sort(key=lambda x: x["score"], reverse=True)
    elif sort == "alpha":
        products.sort(key=lambda x: x["title"].lower())

    total = len(products)
    paginated = products[offset:offset + limit]

    return {
        "audit_id": audit_id,
        "overall_score": audit.get("overall_score"),
        "category_scores": audit.get("category_scores"),
        "products_scanned": audit.get("products_scanned", 0),
        "critical_count": audit.get("critical_count", 0),
        "warning_count": audit.get("warning_count", 0),
        "info_count": audit.get("info_count", 0),
        "completed_at": audit.get("completed_at"),
        "total_filtered": total,
        "products": paginated,
        "pagination": {
            "offset": offset,
            "limit": limit,
            "total": total,
            "has_more": offset + limit < total,
        },
    }


# ── GET /{audit_id}/product/{product_id} ─────────────────────────────────────

@router.get("/{audit_id}/product/{product_id}")
async def get_product_detail(
    audit_id: str,
    product_id: str,
    tenant: dict = Depends(get_current_tenant),
):
    db = await get_db()
    audit = await aw(db.audits.find_one({
        "_id": ObjectId(audit_id),
        "tenant_id": str(tenant["_id"]),
    }))

    if not audit:
        raise HTTPException(404, "Audit not found")

    product = next(
        (p for p in audit.get("product_results", [])
         if p["shopify_product_id"] == product_id),
        None
    )

    if not product:
        raise HTTPException(404, "Product not found in this audit")

    return product


# ── POST /{audit_id}/reset ────────────────────────────────────────────────────

@router.post("/{audit_id}/reset")
async def reset_audit(audit_id: str, tenant: dict = Depends(get_current_tenant)):
    """Reset a stuck audit back to failed state"""
    logger.info(f"🔄 Resetting audit: {audit_id}")

    db = await get_db()

    result = await aw(db.audits.update_one(
        {
            "_id": ObjectId(audit_id),
            "tenant_id": str(tenant["_id"]),
        },
        {
            "$set": {
                "status": AuditStatus.FAILED.value,
                "error_message": "Audit was reset - please run a new audit"
            }
        }
    ))

    if result.matched_count == 0:
        raise HTTPException(404, "Audit not found")

    logger.info(f"✅ Audit {audit_id} reset to failed state")
    return {"success": True, "message": "Audit reset - you can now run a new audit"}