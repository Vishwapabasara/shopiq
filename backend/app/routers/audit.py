from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from bson import ObjectId
import inspect
import logging

from app.dependencies import get_db, get_current_tenant
from app.models.schemas import AuditRunResponse, AuditStatusResponse, AuditStatus
from app.workers.audit_worker import run_audit_task
from app.utils.shopify_client import validate_scopes

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

    db = await get_db()

    # Pre-flight scope check
    missing = await validate_scopes(tenant["shop_domain"], tenant["_token"])
    if missing:
        logger.warning(f"⚠️ Missing scopes for {tenant['shop_domain']}: {missing}")
        await aw(db.tenants.update_one(
            {"_id": tenant["_id"]},
            {"$set": {"scope_issue": True, "missing_scopes": missing}}
        ))
        return JSONResponse(status_code=403, content={
            "error": "missing_scopes",
            "message": "App permissions need updating. Please reinstall to grant the required permissions.",
            "missing_scopes": missing,
            "action": "reinstall",
        })

    # Clear any previously flagged scope issue
    await aw(db.tenants.update_one(
        {"_id": tenant["_id"]},
        {"$unset": {"scope_issue": "", "missing_scopes": ""}}
    ))

    from app.workers.celery_app import celery_app
    logger.info(f"📡 Celery broker: {celery_app.conf.broker_url}")

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

@router.get("/{audit_id}/status")
async def get_audit_status(audit_id: str, tenant: dict = Depends(get_current_tenant)):
    """Get audit status"""
    logger.info(f"📊 Checking status for audit: {audit_id}")
    
    db = await get_db()
    
    try:
        audit = await aw(db.audits.find_one({
            "_id": ObjectId(audit_id),
            "tenant_id": str(tenant["_id"])
        }))
        
        if not audit:
            raise HTTPException(404, "Audit not found")
        
        # Convert ObjectId to string and prepare response
        return {
            "audit_id": str(audit["_id"]),
            "status": audit.get("status"),
            "products_scanned": audit.get("products_scanned", 0),
            "overall_score": audit.get("overall_score"),
            "completed_at": audit.get("completed_at").isoformat() if audit.get("completed_at") else None,
            "error_message": audit.get("error_message"),
            "critical_count": audit.get("critical_count", 0),
            "warning_count": audit.get("warning_count", 0),
        }
    except Exception as e:
        logger.error(f"❌ Error fetching audit status: {e}", exc_info=True)
        raise HTTPException(500, f"Error fetching audit status: {str(e)}")
# ── GET /{audit_id}/results ───────────────────────────────────────────────────

@router.get("/{audit_id}/results")
async def get_audit_results(
    audit_id: str,
    tenant: dict = Depends(get_current_tenant),
    sort: str = None,
    severity: str = None,
    limit: int = 100,
    offset: int = 0,
):
    """Get detailed audit results with optional sorting and pagination"""
    logger.info(f"📊 Fetching results for audit: {audit_id} (sort={sort}, severity={severity}, limit={limit}, offset={offset})")

    db = await get_db()

    try:
        audit = await aw(db.audits.find_one({
            "_id": ObjectId(audit_id),
            "tenant_id": str(tenant["_id"])
        }))

        if not audit:
            raise HTTPException(404, "Audit not found")

        # Get product results
        product_results = audit.get("product_results", [])

        # Apply severity filter
        if severity:
            product_results = [
                p for p in product_results
                if any(i.get("severity") == severity for i in p.get("issues", []))
            ]

        # Apply sorting if requested
        if sort:
            if sort == "score_asc":
                product_results = sorted(product_results, key=lambda x: x.get('score', 0))
            elif sort == "score_desc":
                product_results = sorted(product_results, key=lambda x: x.get('score', 0), reverse=True)
            elif sort == "title_asc":
                product_results = sorted(product_results, key=lambda x: x.get('title', '').lower())
            elif sort == "title_desc":
                product_results = sorted(product_results, key=lambda x: x.get('title', '').lower(), reverse=True)
        
        # Apply pagination
        total_products = len(product_results)
        paginated_results = product_results[offset:offset + limit]
        
        # Ensure all fields exist with defaults
        return {
            "audit_id": str(audit["_id"]),
            "status": audit.get("status", "unknown"),
            "products_scanned": audit.get("products_scanned", 0),
            "overall_score": audit.get("overall_score", 0),
            "category_scores": audit.get("category_scores", {}),
            "critical_count": audit.get("critical_count", 0),
            "warning_count": audit.get("warning_count", 0),
            "info_count": audit.get("info_count", 0),
            "product_results": paginated_results,  # ✅ PAGINATED
            "total_products": total_products,  # ✅ ADD TOTAL COUNT
            "created_at": audit.get("created_at").isoformat() if audit.get("created_at") else None,
            "completed_at": audit.get("completed_at").isoformat() if audit.get("completed_at") else None,
            "error_message": audit.get("error_message"),
        }
    except Exception as e:
        logger.error(f"❌ Error fetching audit results: {e}", exc_info=True)
        raise HTTPException(500, f"Error fetching results: {str(e)}")
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


@router.get("/debug-celery")
async def debug_celery():
    """Debug Celery connection"""
    from app.workers.celery_app import celery_app
    from celery import current_app
    
    try:
        # Get active tasks
        inspector = current_app.control.inspect()
        
        active = inspector.active()
        scheduled = inspector.scheduled()
        reserved = inspector.reserved()
        
        return {
            "broker": celery_app.conf.broker_url[:50],
            "backend": celery_app.conf.result_backend[:50],
            "active_tasks": active,
            "scheduled_tasks": scheduled,
            "reserved_tasks": reserved,
        }
    except Exception as e:
        return {"error": str(e)}