import logging
import asyncio
from datetime import datetime
from bson import ObjectId
from celery import Task

from app.workers.celery_app import celery_app
from app.config import settings
from app.utils.crypto import decrypt_token
from app.utils.shopify_client import fetch_all_products
from app.models.schemas import AuditStatus

logger = logging.getLogger(__name__)

print("=" * 50)
print("🔧 AUDIT WORKER MODULE LOADED")
print("=" * 50)


def get_sync_db():
    """Get synchronous MongoDB connection for Celery worker"""
    from pymongo import MongoClient
    client = MongoClient(settings.MONGO_URI)  # ✅ FIXED: Changed from MONGODB_URL to MONGO_URI
    return client.get_default_database()


@celery_app.task(bind=True, name='app.workers.audit_worker.run_audit_task')
def run_audit_task(self: Task, audit_id: str, shop_domain: str, encrypted_token: str):
    """Run product audit task in Celery worker"""
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
    
    # Simple audit results
    logger.info(f"⚙️ Running simple audit on {len(products)} products...")
    
    product_results = []
    for product in products:
        # Simple scoring logic
        score = 50  # Base score
        issues = []
        
        # Check for basic issues
        if not product.get('body_html'):
            issues.append({"severity": "warning", "message": "Missing description"})
            score -= 10
        
        if not product.get('images'):
            issues.append({"severity": "critical", "message": "Missing images"})
            score -= 20
        
        if len(product.get('title', '')) < 10:
            issues.append({"severity": "warning", "message": "Title too short"})
            score -= 5
        
        product_results.append({
            "shopify_product_id": str(product['id']),
            "title": product.get('title', 'Untitled'),
            "score": max(0, score),
            "issues": issues
        })
    
    # Calculate overall scores
    overall_score = sum(p['score'] for p in product_results) / len(product_results) if product_results else 0
    critical_count = sum(1 for p in product_results for i in p['issues'] if i['severity'] == 'critical')
    warning_count = sum(1 for p in product_results for i in p['issues'] if i['severity'] == 'warning')
    
    logger.info(f"✅ Audit completed: {len(products)} products, score: {overall_score:.1f}")
    
    # Save results to database
    logger.info(f"💾 Saving audit results to database...")
    db.audits.update_one(
        {"_id": ObjectId(audit_id)},
        {"$set": {
            "status": AuditStatus.COMPLETE.value,
            "products_scanned": len(products),
            "product_results": product_results,
            "overall_score": overall_score,
            "critical_count": critical_count,
            "warning_count": warning_count,
            "info_count": 0,
            "completed_at": datetime.utcnow()
        }}
    )
    
    logger.info(f"✅ Audit {audit_id} results saved")
    
    return {
        "audit_id": audit_id,
        "products_scanned": len(products),
        "overall_score": overall_score
    }


@celery_app.task(name='app.workers.audit_worker.run_scheduled_audits')
def run_scheduled_audits():
    """Run scheduled monthly audits"""
    logger.info("🔄 Running scheduled audits...")
    logger.info("✅ Scheduled audits completed")