import logging
from datetime import datetime, timedelta
from typing import Optional, Dict
import httpx
from bson import ObjectId
from app.config import settings, PLANS

logger = logging.getLogger(__name__)


async def create_subscription_charge(
    shop_domain: str,
    access_token: str,
    plan_type: str
) -> Dict:
    """Create a Shopify recurring application charge"""
    plan = PLANS.get(plan_type)

    if not plan or plan["price"] == 0:
        raise ValueError("Cannot create charge for free plan")

    charge_data = {
        "recurring_application_charge": {
            "name": f"ShopIQ {plan['name']} Plan",
            "price": plan["price"],
            "return_url": f"{settings.APP_URL}/billing/callback",
            "trial_days": plan.get("trial_days", 0),
            "test": settings.DEV_MODE,
        }
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"https://{shop_domain}/admin/api/2024-01/recurring_application_charges.json",
            headers={
                "X-Shopify-Access-Token": access_token,
                "Content-Type": "application/json"
            },
            json=charge_data
        )
        response.raise_for_status()
        data = response.json()

    logger.info(f"✅ Subscription charge created for {shop_domain}: {plan_type}")
    return data["recurring_application_charge"]


async def activate_charge(
    shop_domain: str,
    access_token: str,
    charge_id: str
) -> Dict:
    """Activate a Shopify recurring application charge"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"https://{shop_domain}/admin/api/2024-01/recurring_application_charges/{charge_id}/activate.json",
            headers={
                "X-Shopify-Access-Token": access_token,
                "Content-Type": "application/json"
            },
            json={}
        )
        response.raise_for_status()
        data = response.json()

    logger.info(f"✅ Charge activated for {shop_domain}: {charge_id}")
    return data["recurring_application_charge"]


async def cancel_subscription(
    shop_domain: str,
    access_token: str,
    charge_id: str
) -> bool:
    """Cancel a Shopify recurring application charge"""
    async with httpx.AsyncClient() as client:
        response = await client.delete(
            f"https://{shop_domain}/admin/api/2024-01/recurring_application_charges/{charge_id}.json",
            headers={"X-Shopify-Access-Token": access_token}
        )
        response.raise_for_status()

    logger.info(f"✅ Subscription cancelled for {shop_domain}: {charge_id}")
    return True


async def get_current_charge(
    shop_domain: str,
    access_token: str,
    charge_id: str
) -> Optional[Dict]:
    """Get details of current charge"""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://{shop_domain}/admin/api/2024-01/recurring_application_charges/{charge_id}.json",
            headers={"X-Shopify-Access-Token": access_token}
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()["recurring_application_charge"]


def calculate_usage_period() -> tuple:
    """Calculate current billing period (first day of month to last day)"""
    now = datetime.utcnow()
    period_start = datetime(now.year, now.month, 1)
    if now.month == 12:
        period_end = datetime(now.year + 1, 1, 1) - timedelta(days=1)
    else:
        period_end = datetime(now.year, now.month + 1, 1) - timedelta(days=1)
    return period_start, period_end


async def check_usage_limits(tenant: Dict) -> Dict:
    """
    Check if tenant has exceeded usage limits.
    Returns: {"allowed": bool, "reason": str, "limits": {}, "usage": {}}
    """
    plan_type = tenant.get("plan", "free")
    plan = PLANS.get(plan_type)

    if not plan:
        logger.warning(f"Invalid or missing plan '{plan_type}' for tenant, defaulting to free")
        plan = PLANS.get("free")
        if not plan:
            return {
                "allowed": False,
                "reason": "Invalid plan",
                "message": "Invalid plan configuration. Please contact support.",
                "limits": {},
                "usage": {},
            }

    usage = tenant.get("usage", {})
    audits_used = usage.get("audits_used_this_month", 0)

    audit_limit = plan["audits_per_month"]
    if audit_limit != -1 and audits_used >= audit_limit:
        return {
            "allowed": False,
            "reason": "audit_limit_exceeded",
            "message": f"You've used all {audit_limit} audits this month. Upgrade to run more audits.",
            "limits": plan,
            "usage": usage,
        }

    product_limit = plan["max_products"]
    products_scanned = usage.get("products_scanned_this_month", 0)
    if product_limit != -1 and products_scanned >= product_limit:
        return {
            "allowed": False,
            "reason": "product_limit_exceeded",
            "message": f"You've scanned {product_limit} products this month. Upgrade for more.",
            "limits": plan,
            "usage": usage,
        }

    return {"allowed": True, "limits": plan, "usage": usage}


async def increment_usage(tenant_id: ObjectId, audits: int = 0, products: int = 0):
    """Increment usage counters for tenant"""
    from app.dependencies import get_db

    db = await get_db()
    period_start, period_end = calculate_usage_period()

    await db.tenants.update_one(
        {"_id": tenant_id},
        {
            "$inc": {
                "usage.audits_used_this_month": audits,
                "usage.products_scanned_this_month": products
            },
            "$set": {
                "usage.period_start": period_start,
                "usage.period_end": period_end,
                "usage.last_updated": datetime.utcnow()
            }
        }
    )
    logger.info(f"✅ Usage incremented for {tenant_id}: +{audits} audits, +{products} products")


async def reset_monthly_usage():
    """Reset usage counters for all tenants (run on 1st of each month)"""
    from app.dependencies import get_db

    db = await get_db()
    period_start, period_end = calculate_usage_period()

    result = await db.tenants.update_many(
        {},
        {
            "$set": {
                "usage.audits_used_this_month": 0,
                "usage.products_scanned_this_month": 0,
                "usage.period_start": period_start,
                "usage.period_end": period_end,
                "usage.last_updated": datetime.utcnow()
            }
        }
    )
    logger.info(f"✅ Reset usage for {result.modified_count} tenants")
    return result.modified_count
