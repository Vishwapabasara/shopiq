import base64
import logging
import hmac
import hashlib
from fastapi import APIRouter, Request, HTTPException, Header
from datetime import datetime

from app.config import settings
from app.dependencies import get_db

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = logging.getLogger(__name__)


@router.get("/status")
async def webhook_status():
    """
    Public debug endpoint — confirms routes are live and shows expected webhook URLs.
    No auth required (Shopify must reach /webhooks/* without a session cookie).
    For full Shopify registration status use GET /auth/webhooks/status?shop=<shop>.
    """
    backend_url = (settings.BACKEND_URL or settings.APP_URL).rstrip("/")
    return {
        "status": "ok",
        "app_url": settings.APP_URL,
        "backend_url": settings.BACKEND_URL or "(not set — falling back to APP_URL)",
        "shopify_api_secret_configured": bool(settings.SHOPIFY_API_SECRET),
        "expected_webhook_urls": {
            "customers/data_request": f"{backend_url}/webhooks/customers/data_request",
            "customers/redact":       f"{backend_url}/webhooks/customers/redact",
            "shop/redact":            f"{backend_url}/webhooks/shop/redact",
        },
        "note": "Use POST /auth/webhooks/register?shop=<shop> to force-register webhooks",
    }


def verify_webhook(data: bytes, hmac_header: str) -> bool:
    """Verify Shopify webhook HMAC signature.
    Shopify sends X-Shopify-Hmac-Sha256 as Base64(HMAC-SHA256(secret, raw_body)).
    """
    digest = hmac.new(
        settings.SHOPIFY_API_SECRET.encode('utf-8'),
        data,
        hashlib.sha256
    ).digest()
    calculated = base64.b64encode(digest).decode('utf-8')
    return hmac.compare_digest(calculated, hmac_header)


@router.post("")
async def compliance_dispatcher(
    request: Request,
    x_shopify_hmac_sha256: str = Header(None),
    x_shopify_topic: str = Header(None),
):
    """
    Single compliance endpoint declared in shopify.app.toml.
    Shopify sends all 3 GDPR topics here; dispatched via X-Shopify-Topic header.
    """
    body = await request.body()

    if not x_shopify_hmac_sha256 or not verify_webhook(body, x_shopify_hmac_sha256):
        logger.error(f"❌ Invalid HMAC on compliance webhook (topic={x_shopify_topic})")
        raise HTTPException(status_code=401, detail="Invalid HMAC")

    data = await request.json()
    shop_domain = data.get("shop_domain")
    db = await get_db()

    if x_shopify_topic == "customers/data_request":
        logger.info(f"📋 Customer data request from {shop_domain}")
        await db.compliance_logs.insert_one({
            "type": "customer_data_request",
            "shop_domain": shop_domain,
            "customer_email": data.get("customer", {}).get("email"),
            "requested_at": datetime.utcnow(),
            "response": "No customer data stored by ShopIQ",
        })

    elif x_shopify_topic == "customers/redact":
        logger.info(f"🗑️ Customer redact from {shop_domain}")
        await db.compliance_logs.insert_one({
            "type": "customer_redact",
            "shop_domain": shop_domain,
            "customer_id": data.get("customer", {}).get("id"),
            "customer_email": data.get("customer", {}).get("email"),
            "requested_at": datetime.utcnow(),
            "action_taken": "No customer data stored - nothing to redact",
        })

    elif x_shopify_topic == "shop/redact":
        logger.info(f"🗑️ Shop redact for {shop_domain}")
        shop_id = data.get("shop_id")
        await db.compliance_logs.insert_one({
            "type": "shop_redact",
            "shop_domain": shop_domain,
            "shop_id": shop_id,
            "requested_at": datetime.utcnow(),
            "status": "pending_deletion",
        })
        await db.tenants.delete_one({"shop_domain": shop_domain})
        await db.audits.delete_many({"shop_domain": shop_domain})
        await db.sessions.delete_many({"shop_domain": shop_domain})
        await db.compliance_logs.update_one(
            {"shop_domain": shop_domain, "type": "shop_redact", "status": "pending_deletion"},
            {"$set": {"status": "completed", "deleted_at": datetime.utcnow()}},
        )
        logger.info(f"✅ Deleted all data for shop: {shop_domain}")

    else:
        logger.warning(f"⚠️ Unknown compliance topic: {x_shopify_topic}")

    return {"message": "ok"}


@router.post("/customers/data_request")
async def customer_data_request(
    request: Request,
    x_shopify_hmac_sha256: str = Header(None)
):
    """
    GDPR: Customer requests their data
    Required by Shopify for GDPR compliance
    """
    body = await request.body()
    
    # Verify webhook authenticity
    if not x_shopify_hmac_sha256 or not verify_webhook(body, x_shopify_hmac_sha256):
        logger.error("❌ Invalid webhook HMAC")
        raise HTTPException(status_code=401, detail="Invalid HMAC")
    
    data = await request.json()
    shop_domain = data.get("shop_domain")
    customer_email = data.get("customer", {}).get("email")
    
    logger.info(f"📋 Customer data request: {customer_email} from {shop_domain}")
    
    # ShopIQ doesn't store customer data, only product/audit data
    # Log the request for compliance records
    db = await get_db()
    await db.compliance_logs.insert_one({
        "type": "customer_data_request",
        "shop_domain": shop_domain,
        "customer_email": customer_email,
        "requested_at": datetime.utcnow(),
        "response": "No customer data stored by ShopIQ"
    })
    
    # Return 200 to acknowledge receipt
    return {"message": "Customer data request received"}


@router.post("/customers/redact")
async def customer_redact(
    request: Request,
    x_shopify_hmac_sha256: str = Header(None)
):
    """
    GDPR: Customer requests data deletion
    Required by Shopify for GDPR compliance
    """
    body = await request.body()
    
    if not x_shopify_hmac_sha256 or not verify_webhook(body, x_shopify_hmac_sha256):
        logger.error("❌ Invalid webhook HMAC")
        raise HTTPException(status_code=401, detail="Invalid HMAC")
    
    data = await request.json()
    shop_domain = data.get("shop_domain")
    customer_id = data.get("customer", {}).get("id")
    customer_email = data.get("customer", {}).get("email")
    
    logger.info(f"🗑️ Customer redact request: {customer_email} from {shop_domain}")
    
    # ShopIQ doesn't store customer-specific data
    # Only store owner/shop data and product audit results
    # Log the request for compliance
    db = await get_db()
    await db.compliance_logs.insert_one({
        "type": "customer_redact",
        "shop_domain": shop_domain,
        "customer_id": customer_id,
        "customer_email": customer_email,
        "requested_at": datetime.utcnow(),
        "action_taken": "No customer data stored - nothing to redact"
    })
    
    return {"message": "Customer redact request received"}


@router.post("/shop/redact")
async def shop_redact(
    request: Request,
    x_shopify_hmac_sha256: str = Header(None)
):
    """
    GDPR: Store uninstalled, requests data deletion
    Required by Shopify for GDPR compliance
    """
    body = await request.body()
    
    if not x_shopify_hmac_sha256 or not verify_webhook(body, x_shopify_hmac_sha256):
        logger.error("❌ Invalid webhook HMAC")
        raise HTTPException(status_code=401, detail="Invalid HMAC")
    
    data = await request.json()
    shop_domain = data.get("shop_domain")
    shop_id = data.get("shop_id")
    
    logger.info(f"🗑️ Shop redact request: {shop_domain}")
    
    # Delete all shop data after 48 hours (Shopify allows up to 48h)
    db = await get_db()
    
    # Log the request
    await db.compliance_logs.insert_one({
        "type": "shop_redact",
        "shop_domain": shop_domain,
        "shop_id": shop_id,
        "requested_at": datetime.utcnow(),
        "status": "pending_deletion"
    })
    
    # Delete tenant data
    await db.tenants.delete_one({"shop_domain": shop_domain})
    
    # Delete all audits for this shop
    await db.audits.delete_many({"shop_domain": shop_domain})
    
    # Delete all sessions
    await db.sessions.delete_many({"shop_domain": shop_domain})
    
    logger.info(f"✅ Deleted all data for shop: {shop_domain}")
    
    # Mark as completed
    await db.compliance_logs.update_one(
        {
            "shop_domain": shop_domain,
            "type": "shop_redact",
            "status": "pending_deletion"
        },
        {"$set": {
            "status": "completed",
            "deleted_at": datetime.utcnow()
        }}
    )
    
    return {"message": "Shop data deleted successfully"}