import logging
import asyncio
from datetime import datetime
from bson import ObjectId
from celery import Task

from app.workers.celery_app import celery_app
from app.config import settings
from app.utils.crypto import decrypt_token
from app.utils.shopify_client import fetch_all_products
from app.services.audit_engine import run_full_audit
from app.models.schemas import AuditStatus

logger = logging.getLogger(__name__)

# Print for debugging
print("=" * 50)
print("🔧 AUDIT WORKER MODULE LOADED")
print("=" * 50)


def get_sync_db():
    """Get synchronous MongoDB connection for Celery worker"""
    from pymongo import MongoClient
    client = MongoClient(settings.MONGODB_URL)
    return client.get_default_database()


@celery_app.task(bind=True, name='app.workers.audit_worker.run_audit_task')
def run_audit_task(self: Task, audit_id: str, shop_domain: str, encrypted_token: str):
    """
    Run product audit task in Celery worker
    Uses synchronous operations for Celery compatibility
    """
    logger.info(f"🚀 Task received for audit: {audit_id}")
    logger.info(f"📦 Shop: {shop_domain}")
    
    try:
        # Update status to running (synchronous)
        db = get_sync_db()
        db.audits.update_one(
            {"_id": ObjectId(audit_id)},
            {"$set": {
                "status": AuditStatus.RUNNING.value,
                "updated_at": datetime.utcnow()
            }}
        )
        logger.info(f"✅ Audit {audit_id} marked as RUNNING")
        
        # Decrypt access token
        logger.info("🔑 Decrypting access token...")
        access_token = decrypt_token(encrypted_token)
        logger.info("✅ Access token decrypted")
        
        # Run async audit in new event loop
        logger.info("🏃 Starting audit async operations...")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                _run_audit_async(audit_id, shop_domain, access_token, db)
            )
            logger.info(f"✅ Audit {audit_id} completed successfully")
            return result
        finally:
            loop.close()
            
    except Exception as exc:
        logger.error(f"❌ Audit {audit_id} failed: {exc}", exc_info=True)
        
        # Mark as failed (synchronous)
        try:
            db = get_sync_db()
            db.audits.update_one(
                {"_id": ObjectId(audit_id)},
                {"$set": {
                    "status": AuditStatus.FAILED.value,
                    "error_message": str(exc),
                    "completed_at": datetime.utcnow()
                }}
            )
            logger.info(f"✅ Audit {audit_id} marked as FAILED")
        except Exception as e:
            logger.error(f"❌ Failed to mark audit as failed: {e}")
        
        raise


async def _run_audit_async(audit_id: str, shop_domain: str, access_token: str, db):
    """Run the actual audit with async operations"""
    
    # Fetch products from Shopify
    logger.info(f"📦 Fetching products from Shopify for {shop_domain}...")
    products = await fetch_all_products(shop_domain, access_token)
    logger.info(f"✅ Fetched {len(products)} products")
    
    # Update progress
    db.audits.update_one(
        {"_id": ObjectId(audit_id)},
        {"$set": {"products_scanned": len(products)}}
    )
    
    # Run audit engine
    logger.info(f"⚙️ Running audit engine on {len(products)} products...")
    audit_results = await run_full_audit(products)
    logger.info(f"✅ Audit engine completed")
    
    # Save results to database
    logger.info(f"💾 Saving audit results to database...")
    db.audits.update_one(
        {"_id": ObjectId(audit_id)},
        {"$set": {
            "status": AuditStatus.COMPLETE.value,
            "products_scanned": len(products),
            "product_results": audit_results["products"],
            "overall_score": audit_results["overall_score"],
            "category_scores": audit_results.get("category_scores", {}),
            "critical_count": audit_results.get("critical_count", 0),
            "warning_count": audit_results.get("warning_count", 0),
            "info_count": audit_results.get("info_count", 0),
            "completed_at": datetime.utcnow()
        }}
    )
    
    logger.info(f"✅ Audit {audit_id} results saved")
    
    return {
        "audit_id": audit_id,
        "products_scanned": len(products),
        "overall_score": audit_results["overall_score"]
    }


@celery_app.task(name='app.workers.audit_worker.run_scheduled_audits')
def run_scheduled_audits():
    """Run scheduled monthly audits"""
    logger.info("🔄 Running scheduled audits...")
    
    db = get_sync_db()
    
    # Find tenants that need monthly audits
    # ... your scheduling logic ...
    
    logger.info("✅ Scheduled audits completed")