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
        messages = "; ".join(e.get("message", str(e)) for e in errors)
        raise Exception(f"Shopify billing error: {messages}")

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


# ── Usage period helpers ──────────────────────────────────────────────────────

def calculate_usage_period() -> tuple:
    now = datetime.utcnow()
    period_start = datetime(now.year, now.month, 1)
    if now.month == 12:
        period_end = datetime(now.year + 1, 1, 1) - timedelta(days=1)
    else:
        period_end = datetime(now.year, now.month + 1, 1) - timedelta(days=1)
    return period_start, period_end


def _resolve_plan(tenant: Dict) -> Dict:
    plan_type = tenant.get("plan", "free")
    if plan_type == "starter":
        plan_type = "free"
    return PLANS.get(plan_type, PLANS["free"])


# ── Generic limit check helper ────────────────────────────────────────────────

def _check_limit(used: int, limit: int, reason: str, message: str, plan: Dict, usage: Dict) -> Optional[Dict]:
    if limit != -1 and used >= limit:
        return {
            "allowed": False,
            "reason": reason,
            "message": message,
            "limits": plan,
            "usage": usage,
        }
    return None


# ── Audit usage ───────────────────────────────────────────────────────────────

async def check_usage_limits(tenant: Dict) -> Dict:
    plan = _resolve_plan(tenant)
    usage = tenant.get("usage", {})

    audits_used = usage.get("audits_used_this_month", 0)
    audit_limit = plan["audits_per_month"]

    block = _check_limit(
        audits_used, audit_limit,
        "audit_limit_exceeded",
        f"You've used all {audit_limit} audits this month. Upgrade to run more.",
        plan, usage,
    )
    if block:
        return block

    return {"allowed": True, "limits": plan, "usage": usage}


# ── Copy generation usage ─────────────────────────────────────────────────────

async def check_copy_limit(tenant: Dict) -> Dict:
    plan = _resolve_plan(tenant)
    usage = tenant.get("usage", {})

    used = usage.get("copy_generations_used_this_month", 0)
    limit = plan.get("copy_generations_per_month", -1)

    block = _check_limit(
        used, limit,
        "copy_limit_exceeded",
        f"You've used all {limit} AI copy generations this month. Upgrade for more.",
        plan, usage,
    )
    if block:
        return block

    return {"allowed": True, "limits": plan, "usage": usage}


# ── AI fix usage ──────────────────────────────────────────────────────────────

async def check_fix_limit(tenant: Dict) -> Dict:
    plan = _resolve_plan(tenant)
    usage = tenant.get("usage", {})

    used = usage.get("ai_fixes_used_this_month", 0)
    limit = plan.get("ai_fixes_per_month", -1)

    block = _check_limit(
        used, limit,
        "fix_limit_exceeded",
        f"You've used all {limit} AI fixes this month. Upgrade for more.",
        plan, usage,
    )
    if block:
        return block

    return {"allowed": True, "limits": plan, "usage": usage}


# ── Increment helpers ─────────────────────────────────────────────────────────

async def increment_usage(tenant_id: ObjectId, audits: int = 0, products: int = 0,
                          copy_generations: int = 0, ai_fixes: int = 0):
    from app.dependencies import get_db
    db = await get_db()
    period_start, period_end = calculate_usage_period()

    inc: Dict = {}
    if audits:
        inc["usage.audits_used_this_month"] = audits
    if products:
        inc["usage.products_scanned_this_month"] = products
    if copy_generations:
        inc["usage.copy_generations_used_this_month"] = copy_generations
    if ai_fixes:
        inc["usage.ai_fixes_used_this_month"] = ai_fixes

    update: Dict = {"$set": {
        "usage.period_start": period_start,
        "usage.period_end": period_end,
        "usage.last_updated": datetime.utcnow(),
    }}
    if inc:
        update["$inc"] = inc

    await db.tenants.update_one({"_id": tenant_id}, update)


# ── Plan change preview ───────────────────────────────────────────────────────

def preview_plan_change(tenant: Dict, new_plan_key: str) -> Dict:
    """
    Returns billing impact of a plan change before it's confirmed.
    Upgrade: proration math + trial info.
    Downgrade: effective date + features that will be lost.
    """
    old_plan_key = tenant.get("plan", "free")
    if old_plan_key == "starter":
        old_plan_key = "free"

    old_plan = PLANS.get(old_plan_key, PLANS["free"])
    new_plan = PLANS.get(new_plan_key, PLANS["free"])

    old_price = old_plan["price"]
    new_price = new_plan["price"]
    is_upgrade = new_price > old_price
    is_downgrade = new_price < old_price
    is_same = new_plan_key == old_plan_key

    now = datetime.utcnow()

    # Build features lost/gained lists
    old_features = set(old_plan.get("features", []))
    new_features = set(new_plan.get("features", []))
    features_lost = sorted(old_features - new_features)
    features_gained = sorted(new_features - old_features)

    # Usage warnings for downgrades
    usage = tenant.get("usage", {})
    usage_warnings: list[str] = []
    if is_downgrade or new_price == 0:
        copy_used = usage.get("copy_generations_used_this_month", 0)
        new_copy_limit = new_plan.get("copy_generations_per_month", 0)
        if new_copy_limit != -1 and copy_used < old_plan.get("copy_generations_per_month", 0):
            remaining = old_plan.get("copy_generations_per_month", 0) - copy_used
            if remaining > 0:
                usage_warnings.append(
                    f"You have {remaining} AI copy generations remaining this month — they will expire."
                )
        audits_used = usage.get("audits_used_this_month", 0)
        old_audit_limit = old_plan.get("audits_per_month", 0)
        if audits_used > 0 and old_audit_limit != -1:
            usage_warnings.append(
                f"You've run {audits_used} audit{'s' if audits_used != 1 else ''} this month — history will be hidden on the Free plan."
            )

    # Determine effective date
    period_end = tenant.get("current_period_end")
    if not period_end:
        # Estimate from activated_on
        activated = tenant.get("activated_on") or now
        if isinstance(activated, str):
            try:
                activated = datetime.fromisoformat(activated.replace("Z", "+00:00")).replace(tzinfo=None)
            except Exception:
                activated = now
        period_end = activated + timedelta(days=30)

    effective_date = period_end if (is_downgrade or is_same) else now
    days_until = max(0, (period_end - now).days) if is_downgrade else 0

    # Proration for paid → paid upgrades
    charge_today = 0.0
    credit = 0.0
    new_plan_prorated = 0.0
    days_remaining = 0

    if is_upgrade and old_price > 0 and new_price > 0:
        days_remaining = max(0, (period_end - now).days)
        days_in_period = 30
        credit = round((days_remaining / days_in_period) * old_price, 2)
        new_plan_prorated = round((days_remaining / days_in_period) * new_price, 2)
        charge_today = round(max(new_plan_prorated - credit, 0), 2)

    # Trial info for new paid subscriptions
    trial_days = new_plan.get("trial_days", 0) if (is_upgrade and old_price == 0) else 0
    trial_ends_at = (now + timedelta(days=trial_days)).date().isoformat() if trial_days > 0 else None
    first_charge_date = trial_ends_at or (now.date().isoformat() if is_upgrade else None)
    first_charge_amount = new_price if is_upgrade else 0.0

    return {
        "from_plan": old_plan_key,
        "to_plan": new_plan_key,
        "is_upgrade": is_upgrade,
        "is_downgrade": is_downgrade,
        "is_same_plan": is_same,
        # Billing
        "trial_days": trial_days,
        "trial_ends_at": trial_ends_at,
        "first_charge_date": first_charge_date,
        "first_charge_amount": first_charge_amount,
        "charge_today": charge_today,
        "credit": credit,
        "new_plan_prorated": new_plan_prorated,
        "days_remaining": days_remaining,
        # Timing
        "effective_immediately": is_upgrade,
        "effective_date": period_end.date().isoformat() if is_downgrade else None,
        "days_until_effective": days_until,
        # Consequences
        "features_lost": features_lost,
        "features_gained": features_gained,
        "usage_warnings": usage_warnings,
        # Plan info
        "new_plan_price": new_price,
        "new_plan_name": new_plan["name"],
    }


# ── Downgrade scheduling ──────────────────────────────────────────────────────

async def schedule_downgrade(tenant_id: ObjectId, new_plan_key: str, period_end: datetime):
    from app.dependencies import get_db
    db = await get_db()
    await db.tenants.update_one(
        {"_id": tenant_id},
        {"$set": {
            "pending_downgrade_plan": new_plan_key,
            "pending_downgrade_at": period_end,
            "cancel_at_period_end": True,
        }}
    )
    logger.info(f"📅 Downgrade scheduled: {tenant_id} → {new_plan_key} on {period_end.date()}")


async def cancel_scheduled_downgrade(tenant_id: ObjectId):
    from app.dependencies import get_db
    db = await get_db()
    await db.tenants.update_one(
        {"_id": tenant_id},
        {"$unset": {
            "pending_downgrade_plan": "",
            "pending_downgrade_at": "",
            "cancel_at_period_end": "",
        }}
    )
    logger.info(f"↩️ Downgrade cancelled for tenant: {tenant_id}")


async def apply_pending_downgrades():
    """Nightly job — apply any downgrades whose period_end has passed."""
    from app.dependencies import get_db
    db = await get_db()
    now = datetime.utcnow()
    cursor = db.tenants.find({
        "pending_downgrade_plan": {"$exists": True, "$ne": None},
        "pending_downgrade_at": {"$lte": now},
    })
    try:
        tenants = await cursor.to_list(length=500)
    except TypeError:
        tenants = list(cursor)

    count = 0
    for t in tenants:
        new_plan = t["pending_downgrade_plan"]
        await db.tenants.update_one(
            {"_id": t["_id"]},
            {
                "$set": {
                    "plan": new_plan,
                    "subscription_status": "active",
                    "shopify_charge_id": None,
                },
                "$unset": {
                    "pending_downgrade_plan": "",
                    "pending_downgrade_at": "",
                    "cancel_at_period_end": "",
                },
            }
        )
        await _log_subscription_event(db, str(t["_id"]), "plan_downgraded", t.get("plan"), new_plan)
        count += 1
        logger.info(f"✅ Applied downgrade: {t.get('shop_domain')} → {new_plan}")

    return count


async def _log_subscription_event(db, tenant_id: str, event_type: str,
                                   from_plan: Optional[str], to_plan: str,
                                   amount: float = 0.0, metadata: Optional[Dict] = None):
    await db.subscription_events.insert_one({
        "tenant_id": tenant_id,
        "event_type": event_type,
        "from_plan": from_plan,
        "to_plan": to_plan,
        "amount": amount,
        "metadata": metadata or {},
        "created_at": datetime.utcnow(),
    })


async def reset_monthly_usage():
    from app.dependencies import get_db
    db = await get_db()
    period_start, period_end = calculate_usage_period()
    result = await db.tenants.update_many(
        {},
        {"$set": {
            "usage.audits_used_this_month": 0,
            "usage.products_scanned_this_month": 0,
            "usage.copy_generations_used_this_month": 0,
            "usage.ai_fixes_used_this_month": 0,
            "usage.period_start": period_start,
            "usage.period_end": period_end,
            "usage.last_updated": datetime.utcnow(),
        }}
    )
    logger.info(f"✅ Reset usage for {result.modified_count} tenants")
    return result.modified_count