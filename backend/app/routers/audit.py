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
    """Handle both motor (async) and mongomock (sync) cursors."""
    try:
        return await cursor.to_list(length=length)
    except TypeError:
        # mongomock cursor is synchronous
        return list(cursor)


@router.post("/run", response_model=AuditRunResponse)
async def trigger_audit(tenant: dict = Depends(get_current_tenant)):
    """Trigger a new audit for the authenticated shop"""
    logger.info(f"🔍 Audit triggered for shop: {tenant.get('shop_domain')}")
    
    db = await get_db()

    # Check if audit already running
    running = await aw(db.audits.find_one({
        "tenant_id": str(tenant["_id"]),
        "status": {"$in": [AuditStatus.QUEUED.value, AuditStatus.RUNNING.value]},
    }))
    
    if running:
        logger.warning(f"⚠️ Audit already in progress: {running.get('_id')}")
        raise HTTPException(409, "An audit is already in progress for this store")

    # Create audit document
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
        # Queue the Celery task
        logger.info(f"📤 Queuing Celery task for audit {audit_id}")
        
        task = run_audit_task.delay(
            audit_id,
            tenant["shop_domain"],
            tenant["access_token"],
        )
        
        logger.info(f"✅ Celery task queued: {task.id}")

        # Store task ID
        await aw(db.audits.update_one(
            {"_id": result.inserted_id},
            {"$set": {"celery_task_id": task.id}}
        ))
        
        logger.info(f"✅ Audit {audit_id} started successfully")

        return AuditRunResponse(
            audit_id=audit_id,
            status=AuditStatus.QUEUED,
            message="Audit started — this takes 2–5 minutes depending on your product count",
        )
        
    except Exception as e:
        logger.error(f"❌ Failed to queue audit task: {e}")
        
        # Mark audit as failed
        await aw(db.audits.update_one(
            {"_id": result.inserted_id},
            {"$set": {
                "status": AuditStatus.FAILED.value,
                "error_message": f"Failed to start: {str(e)}"
            }}
        ))
        
        raise HTTPException(500, f"Failed to start audit: {str(e)}")


@router.get("/{audit_id}/status", response_model=AuditStatusResponse)
async def get_audit_status(audit_id: str, tenant: dict = Depends(get_current_tenant)):
    """Get status of a running or completed audit"""
    logger.debug(f"📊 Status check for audit: {audit_id}")
    
    db = await get_db()
    
    try:
        audit = await aw(db.audits.find_one({
            "_id": ObjectId(audit_id),
            "tenant_id": str(tenant["_id"]),
        }))
    except Exception as e:
        logger.error(f"❌ Error fetching audit {audit_id}: {e}")
        raise HTTPException(500, f"Database error: {str(e)}")
    
    if not audit:
        logger.warning(f"⚠️ Audit not found: {audit_id}")
        raise HTTPException(404, "Audit not found")

    status_response = AuditStatusResponse(
        audit_id=audit_id,
        status=audit["status"],
        products_scanned=audit.get("products_scanned", 0),
        overall_score=audit.get("overall_score"),
        completed_at=audit.get("completed_at"),
        error_message=audit.get("error_message"),
    )
    
    logger.debug(f"📊 Audit {audit_id} status: {audit['status']}")
    
    return status_response


@router.get("/{audit_id}/results")
async def get_audit_results(
    audit_id: str,
    severity: str | None = None,
    sort: str = "score_asc",
    limit: int = 50,
    offset: int = 0,
    tenant: dict = Depends(get_current_tenant),
):
    """Get results from a completed audit"""
    logger.info(f"📊 Fetching results for audit: {audit_id}")
    
    db = await get_db()
    
    try:
        audit = await aw(db.audits.find_one({
            "_id": ObjectId(audit_id),
            "tenant_id": str(tenant["_id"]),
        }))
    except Exception as e:
        logger.error(f"❌ Error fetching audit results: {e}")
        raise HTTPException(500, f"Database error: {str(e)}")
    
    if not audit:
        raise HTTPException(404, "Audit not found")

    if audit["status"] != AuditStatus.COMPLETE.value:
        logger.warning(f"⚠️ Audit {audit_id} not complete yet: {audit['status']}")
        raise HTTPException(400, f"Audit not complete yet (status: {audit['status']})")

    products = audit.get("product_results", [])
    logger.info(f"📦 Found {len(products)} products in audit {audit_id}")

    # Filter by severity
    if severity in ("critical", "warning", "info"):
        products = [p for p in products if any(i["severity"] == severity for i in p.get("issues", []))]

    # Sort
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


@router.get("/{audit_id}/product/{product_id}")
async def get_product_detail(
    audit_id: str,
    product_id: str,
    tenant: dict = Depends(get_current_tenant),
):
    """Get detailed information about a specific product in an audit"""
    db = await get_db()
    audit = await aw(db.audits.find_one({
        "_id": ObjectId(audit_id),
        "tenant_id": str(tenant["_id"]),
    }))
    
    if not audit:
        raise HTTPException(404, "Audit not found")

    product = next(
        (p for p in audit.get("product_results", []) if p["shopify_product_id"] == product_id),
        None
    )
    
    if not product:
        raise HTTPException(404, "Product not found in this audit")
    
    return product


@router.get("/history")
async def get_audit_history(
    tenant: dict = Depends(get_current_tenant),
    limit: int = 10,
):
    """Get audit history for the current shop"""
    logger.info(f"📜 Fetching audit history for tenant: {tenant.get('shop_domain')}")
    
    db = await get_db()
    cursor = db.audits.find(
        {"tenant_id": str(tenant["_id"]), "status": AuditStatus.COMPLETE.value},
        {"_id": 1, "overall_score": 1, "category_scores": 1,
         "products_scanned": 1, "critical_count": 1, "created_at": 1, "completed_at": 1}
    ).sort("created_at", -1).limit(limit)

    history = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        history.append(doc)
    
    logger.info(f"📜 Found {len(history)} completed audits")
    return {"history": history}