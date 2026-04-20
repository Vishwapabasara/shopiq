import logging
import httpx
from typing import Optional, Dict
from datetime import datetime, timedelta
from bson import ObjectId
from app.config import settings, PLANS

logger = logging.getLogger(__name__)
SHOPIFY_API_VERSION = "2026-04"


async def create_subscription_charge(
    shop_domain: str,
    access_token: str,
    plan_type: str
) -> Dict:
    """Create a recurring subscription using GraphQL API"""
    plan = PLANS.get(plan_type)
    if not plan or plan["price"] == 0:
        raise ValueError("Cannot create charge for free plan")

    mutation = """
    mutation AppSubscriptionCreate(
        $name: String!,
        $lineItems: [AppSubscriptionLineItemInput!]!,
        $returnUrl: URL!,
        $test: Boolean,
        $trialDays: Int
    ) {
      appSubscriptionCreate(
          name: $name,
          returnUrl: $returnUrl,
          lineItems: $lineItems,
          test: $test,
          trialDays: $trialDays
      ) {
        userErrors { field message }
        confirmationUrl
        appSubscription { id status }
      }
    }
    """

    variables = {
        "name": f"ShopIQ {plan['name']} Plan",
        "returnUrl": f"{settings.APP_URL}/billing/callback",
        "test": settings.DEV_MODE,
        "trialDays": plan.get("trial_days", 7),
        "lineItems": [{
            "plan": {
                "appRecurringPricingDetails": {
                    "price": {
                        "amount": plan["price"],
                        "currencyCode": "USD"
                    },
                    "interval": "EVERY_30_DAYS"
                }
            }
        }]
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://{shop_domain}/admin/api/{SHOPIFY_API_VERSION}/graphql.json",
            json={"query": mutation, "variables": variables},
            headers={
                "X-Shopify-Access-Token": access_token,
                "Content-Type": "application/json",
            }
        )
        resp.raise_for_status()
        data = resp.json()

    errors = data.get("data", {}).get("appSubscriptionCreate", {}).get("userErrors", [])
    if errors:
        raise Exception(f"Shopify billing error: {errors}")

    result = data["data"]["appSubscriptionCreate"]
    subscription = result["appSubscription"]
    logger.info(f"✅ Subscription created for {shop_domain}: {subscription['id']}")

    return {
        "id": subscription["id"],
        "confirmation_url": result["confirmationUrl"],
        "status": subscription["status"]
    }


async def activate_charge(
    shop_domain: str,
    access_token: str,
    charge_id: str
) -> Dict:
    """
    With GraphQL billing, activation is automatic after merchant approves.
    Just verify and return the subscription status.
    """
    return await get_current_charge(shop_domain, access_token, charge_id) or {}


async def cancel_subscription(
    shop_domain: str,
    access_token: str,
    subscription_id: str
) -> bool:
    """Cancel a subscription using GraphQL"""
    mutation = """
    mutation AppSubscriptionCancel($id: ID!) {
      appSubscriptionCancel(id: $id) {
        userErrors { field message }
        appSubscription { id status }
      }
    }
    """

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://{shop_domain}/admin/api/{SHOPIFY_API_VERSION}/graphql.json",
            json={"query": mutation, "variables": {"id": subscription_id}},
            headers={
                "X-Shopify-Access-Token": access_token,
                "Content-Type": "application/json",
            }
        )
        resp.raise_for_status()
        data = resp.json()

    errors = data.get("data", {}).get("appSubscriptionCancel", {}).get("userErrors", [])
    if errors:
        raise Exception(f"Cancel error: {errors}")

    logger.info(f"✅ Subscription cancelled for {shop_domain}: {subscription_id}")
    return True


async def get_current_charge(
    shop_domain: str,
    access_token: str,
    subscription_id: str
) -> Optional[Dict]:
    """Get current subscription status using GraphQL"""
    query = """
    query GetSubscription($id: ID!) {
      node(id: $id) {
        ... on AppSubscription {
          id
          status
          trialDays
          currentPeriodEnd
          lineItems {
            plan {
              pricingDetails {
                ... on AppRecurringPricing {
                  price { amount currencyCode }
                  interval
                }
              }
            }
          }
        }
      }
    }
    """

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://{shop_domain}/admin/api/{SHOPIFY_API_VERSION}/graphql.json",
            json={"query": query, "variables": {"id": subscription_id}},
            headers={
                "X-Shopify-Access-Token": access_token,
                "Content-Type": "application/json",
            }
        )
        resp.raise_for_status()
        data = resp.json()

    return data.get("data", {}).get("node")


# ── Usage tracking (unchanged) ────────────────────────────────────────────────

def calculate_usage_period() -> tuple:
    now = datetime.utcnow()
    period_start = datetime(now.year, now.month, 1)
    if now.month == 12:
        period_end = datetime(now.year + 1, 1, 1) - timedelta(days=1)
    else:
        period_end = datetime(now.year, now.month + 1, 1) - timedelta(days=1)
    return period_start, period_end


async def check_usage_limits(tenant: Dict) -> Dict:
    plan_type = tenant.get("plan", "free")
    if plan_type == "starter":
        plan_type = "free"

    plan = PLANS.get(plan_type, PLANS.get("free"))
    if not plan:
        return {"allowed": False, "reason": "Invalid plan", "limits": {}, "usage": {}}

    usage = tenant.get("usage", {})
    audits_used = usage.get("audits_used_this_month", 0)
    products_scanned = usage.get("products_scanned_this_month", 0)
    audit_limit = plan["audits_per_month"]

    if audit_limit != -1 and audits_used >= audit_limit:
        return {
            "allowed": False,
            "reason": "audit_limit_exceeded",
            "message": f"You've used all {audit_limit} audits this month. Upgrade to run more.",
            "limits": plan,
            "usage": usage,
        }

    product_limit = plan["max_products"]
    if product_limit != -1 and products_scanned >= (product_limit * 2):
        return {
            "allowed": False,
            "reason": "product_limit_exceeded",
            "message": f"Product limit reached. Upgrade to scan more.",
            "limits": plan,
            "usage": usage,
        }

    return {
        "allowed": True,
        "warning": products_scanned >= product_limit if product_limit != -1 else False,
        "limits": plan,
        "usage": usage,
    }


async def increment_usage(tenant_id: ObjectId, audits: int = 0, products: int = 0):
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


async def reset_monthly_usage():
    from app.dependencies import get_db
    db = await get_db()
    period_start, period_end = calculate_usage_period()
    result = await db.tenants.update_many(
        {},
        {"$set": {
            "usage.audits_used_this_month": 0,
            "usage.products_scanned_this_month": 0,
            "usage.period_start": period_start,
            "usage.period_end": period_end,
            "usage.last_updated": datetime.utcnow()
        }}
    )
    logger.info(f"✅ Reset usage for {result.modified_count} tenants")
    return result.modified_count