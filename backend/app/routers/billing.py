import logging
import inspect
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from bson import ObjectId
from fastapi.responses import RedirectResponse

from app.dependencies import get_db, get_current_tenant
from app.services.billing import (
    create_subscription_charge,
    activate_charge,
    cancel_subscription,
    get_current_charge,
)
from app.config import PLANS, settings

router = APIRouter(prefix="/billing", tags=["billing"])
logger = logging.getLogger(__name__)


async def aw(result):
    if inspect.isawaitable(result):
        return await result
    return result


@router.get("/plans")
async def get_plans():
    """Get all available plans"""
    return {"plans": PLANS}


@router.get("/usage")
async def get_usage(tenant: dict = Depends(get_current_tenant)):
    """Get current usage and limits for all modules"""
    plan_type = tenant.get("plan", "free")
    if plan_type == "starter":
        plan_type = "free"
    plan = PLANS.get(plan_type, PLANS["free"])
    usage = tenant.get("usage", {})
    scan_state = tenant.get("scan_state", {})

    return {
        "plan": plan_type,
        "limits": {
            "audits_per_month": plan["audits_per_month"],
            "copy_generations_per_month": plan.get("copy_generations_per_month", -1),
            "ai_fixes_per_month": plan.get("ai_fixes_per_month", -1),
            "exports_per_month": plan.get("exports_per_month", -1),
            "audit_batch_size": plan.get("audit_batch_size", 0),
            "history_audits": plan.get("history_audits", -1),
        },
        "usage": {
            "audits_used": usage.get("audits_used_this_month", 0),
            "products_scanned": usage.get("products_scanned_this_month", 0),
            "copy_generations_used": usage.get("copy_generations_used_this_month", 0),
            "ai_fixes_used": usage.get("ai_fixes_used_this_month", 0),
            "period_start": usage.get("period_start"),
            "period_end": usage.get("period_end"),
        },
        "scan_state": {
            "total_products": scan_state.get("total_products", 0),
            "cursor": scan_state.get("cursor", 0),
            "scanned_product_ids": scan_state.get("scanned_product_ids", []),
        },
        "subscription": {
            "status": tenant.get("subscription_status", "active"),
            "trial_ends_at": tenant.get("trial_ends_at"),
            "cancel_at_period_end": tenant.get("cancel_at_period_end", False),
        },
    }


@router.post("/subscribe/{plan_type}")
async def create_subscription(
    plan_type: str,
    tenant: dict = Depends(get_current_tenant)
):
    """Create a subscription for a plan"""
    if plan_type not in PLANS:
        raise HTTPException(400, "Invalid plan type")

    # Test mode: bypass Shopify billing and activate plan directly
    if settings.DEV_MODE:
        logger.info(f"🧪 TEST MODE: Bypassing Shopify billing for {tenant['shop_domain']} → {plan_type}")
        plan_config = PLANS[plan_type]
        trial_days = plan_config.get("trial_days", 0)
        trial_ends_at = datetime.utcnow() + timedelta(days=trial_days) if trial_days > 0 else None

        db = await get_db()
        await aw(db.tenants.update_one(
            {"_id": tenant["_id"]},
            {"$set": {
                "plan": plan_type,
                "subscription_status": "trial" if trial_days > 0 else "active",
                "trial_ends_at": trial_ends_at,
                "shopify_charge_id": f"test_charge_{plan_type}_{int(datetime.utcnow().timestamp())}",
                "activated_on": datetime.utcnow(),
            }}
        ))
        logger.info(f"✅ Test subscription activated: {tenant['shop_domain']} → {plan_type}")
        return {
            "success": True,
            "test_mode": True,
            "plan": plan_type,
            "plan_name": plan_config["name"],
            "message": f"Successfully upgraded to {plan_config['name']} plan!",
            "redirect_url": None
        }

    if plan_type == "free":
        db = await get_db()
        await aw(db.tenants.update_one(
            {"_id": tenant["_id"]},
            {"$set": {"plan": "free", "subscription_status": "active", "shopify_charge_id": None}}
        ))
        return {"success": True, "plan": "free"}

    try:
        charge = await create_subscription_charge(
            tenant["shop_domain"],
            tenant["_token"],
            plan_type
        )

        db = await get_db()
        await aw(db.tenants.update_one(
            {"_id": tenant["_id"]},
            {"$set": {"pending_charge_id": charge["id"], "pending_plan": plan_type}}
        ))

        logger.info(f"✅ Charge created for {tenant['shop_domain']}: {plan_type}")
        return {
            "success": True,
            "confirmation_url": charge["confirmation_url"],
            "charge_id": charge["id"]
        }

    except Exception as e:
        logger.error(f"❌ Failed to create subscription: {e}")
        raise HTTPException(500, f"Failed to create subscription: {str(e)}")


@router.get("/callback")
async def billing_callback(
    charge_id: str = Query(...),
    tenant: dict = Depends(get_current_tenant)
):
    """Handle callback after merchant approves subscription"""
    try:
        # GraphQL: subscription is already active after merchant approves
        # charge_id is the GraphQL subscription ID (gid://shopify/AppSubscription/...)
        charge = await get_current_charge(
            tenant["shop_domain"],
            tenant["_token"],
            charge_id
        )

        trial_days = charge.get("trialDays", 0) if charge else 0
        trial_ends_at = datetime.utcnow() + timedelta(days=trial_days) if trial_days > 0 else None

        db = await get_db()
        plan_type = tenant.get("pending_plan", "starter")

        await aw(db.tenants.update_one(
            {"_id": tenant["_id"]},
            {
                "$set": {
                    "plan": plan_type,
                    "subscription_status": "trial" if trial_days > 0 else "active",
                    "shopify_charge_id": charge_id,
                    "trial_ends_at": trial_ends_at,
                    "activated_on": datetime.utcnow(),
                },
                "$unset": {"pending_charge_id": "", "pending_plan": ""}
            }
        ))

        logger.info(f"✅ Subscription activated for {tenant['shop_domain']}: {plan_type}")
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/dashboard?upgraded=true",
            status_code=302
        )

    except Exception as e:
        logger.error(f"❌ Failed to activate subscription: {e}")
        raise HTTPException(500, f"Failed to activate subscription: {str(e)}")

@router.post("/cancel")
async def cancel_subscription_endpoint(tenant: dict = Depends(get_current_tenant)):
    """Cancel current subscription"""
    charge_id = tenant.get("shopify_charge_id")

    if not charge_id:
        raise HTTPException(400, "No active subscription to cancel")

    try:
        await cancel_subscription(
            tenant["shop_domain"],
            tenant["_token"],
            charge_id
        )

        db = await get_db()
        await aw(db.tenants.update_one(
            {"_id": tenant["_id"]},
            {"$set": {"cancel_at_period_end": True, "cancelled_at": datetime.utcnow()}}
        ))

        logger.info(f"✅ Subscription cancelled for {tenant['shop_domain']}")
        return {"success": True, "message": "Subscription will be cancelled at the end of the billing period"}

    except Exception as e:
        logger.error(f"❌ Failed to cancel subscription: {e}")
        raise HTTPException(500, f"Failed to cancel subscription: {str(e)}")


@router.get("/status")
async def get_billing_status(tenant: dict = Depends(get_current_tenant)):
    """Get detailed billing status"""
    charge_id = tenant.get("shopify_charge_id")

    if not charge_id:
        return {
            "plan": tenant.get("plan", "free"),
            "status": "active",
            "is_trial": False,
        }

    try:
        charge = await get_current_charge(
            tenant["shop_domain"],
            tenant["_token"],
            charge_id
        )

        if not charge:
            db = await get_db()
            await aw(db.tenants.update_one(
                {"_id": tenant["_id"]},
                {"$set": {"plan": "free", "subscription_status": "active", "shopify_charge_id": None}}
            ))
            return {"plan": "free", "status": "active", "is_trial": False}

        return {
            "plan": tenant.get("plan"),
            "status": charge["status"],
            "is_trial": charge.get("trial_days", 0) > 0 and charge["status"] == "active",
            "trial_ends_at": tenant.get("trial_ends_at"),
            "billing_on": charge.get("billing_on"),
            "price": charge.get("price"),
            "cancel_at_period_end": tenant.get("cancel_at_period_end", False),
        }

    except Exception as e:
        logger.error(f"❌ Failed to get billing status: {e}")
        return {"plan": tenant.get("plan", "free"), "status": "unknown", "error": str(e)}
