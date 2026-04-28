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
    preview_plan_change,
    schedule_downgrade,
    cancel_scheduled_downgrade,
    _log_subscription_event,
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


@router.get("/preview")
async def preview_subscription_change(
    plan: str = Query(..., description="Target plan key: free, pro, enterprise"),
    tenant: dict = Depends(get_current_tenant),
):
    """Preview billing impact of a plan change before confirming."""
    if plan not in PLANS:
        raise HTTPException(400, "Invalid plan")
    return preview_plan_change(tenant, plan)


@router.get("/usage")
async def get_usage(tenant: dict = Depends(get_current_tenant)):
    """Get current usage and limits for all modules"""
    plan_type = tenant.get("plan", "free")
    if plan_type == "starter":
        plan_type = "free"
    plan = PLANS.get(plan_type, PLANS["free"])
    usage = tenant.get("usage", {})
    scan_state = tenant.get("scan_state", {})

    pending_at = tenant.get("pending_downgrade_at")

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
            "current_period_end": tenant.get("current_period_end"),
            "pending_downgrade_plan": tenant.get("pending_downgrade_plan"),
            "pending_downgrade_at": pending_at.isoformat() if pending_at else None,
        },
    }


@router.post("/subscribe/{plan_type}")
async def create_subscription(
    plan_type: str,
    tenant: dict = Depends(get_current_tenant)
):
    """Create or schedule a subscription change."""
    if plan_type not in PLANS:
        raise HTTPException(400, "Invalid plan type")

    preview = preview_plan_change(tenant, plan_type)
    is_downgrade = preview["is_downgrade"]
    old_price = PLANS.get(tenant.get("plan", "free"), PLANS["free"])["price"]
    db = await get_db()

    # ── Test / dev mode ────────────────────────────────────────────────────────
    if settings.DEV_MODE:
        plan_config = PLANS[plan_type]
        trial_days = plan_config.get("trial_days", 0)
        now = datetime.utcnow()

        if is_downgrade:
            # Schedule the downgrade for period end (estimated)
            activated = tenant.get("activated_on") or now
            if isinstance(activated, str):
                try:
                    activated = datetime.fromisoformat(activated.replace("Z", "+00:00")).replace(tzinfo=None)
                except Exception:
                    activated = now
            period_end = tenant.get("current_period_end") or (activated + timedelta(days=30))
            await schedule_downgrade(tenant["_id"], plan_type, period_end)
            await _log_subscription_event(
                db, str(tenant["_id"]), "downgrade_scheduled",
                tenant.get("plan"), plan_type, 0.0,
                {"period_end": period_end.isoformat(), "test_mode": True}
            )
            return {
                "success": True,
                "test_mode": True,
                "scheduled": True,
                "plan": plan_type,
                "effective_date": period_end.date().isoformat(),
                "message": f"Downgrade to {plan_config['name']} scheduled for {period_end.date()}."
            }

        trial_ends_at = now + timedelta(days=trial_days) if trial_days > 0 else None
        await aw(db.tenants.update_one(
            {"_id": tenant["_id"]},
            {"$set": {
                "plan": plan_type,
                "subscription_status": "trial" if trial_days > 0 else "active",
                "trial_ends_at": trial_ends_at,
                "shopify_charge_id": f"test_charge_{plan_type}_{int(now.timestamp())}",
                "activated_on": now,
            }}
        ))
        await _log_subscription_event(
            db, str(tenant["_id"]), "plan_upgraded",
            tenant.get("plan"), plan_type, plan_config["price"],
            {"test_mode": True}
        )
        return {
            "success": True,
            "test_mode": True,
            "plan": plan_type,
            "plan_name": plan_config["name"],
            "message": f"Successfully upgraded to {plan_config['name']} plan!",
            "redirect_url": None
        }

    # ── Production ─────────────────────────────────────────────────────────────
    if plan_type == "free" or is_downgrade:
        # Cancel the current Shopify subscription and schedule the downgrade
        charge_id = tenant.get("shopify_charge_id")
        period_end = tenant.get("current_period_end")
        if not period_end:
            activated = tenant.get("activated_on") or datetime.utcnow()
            if isinstance(activated, str):
                try:
                    activated = datetime.fromisoformat(activated.replace("Z", "+00:00")).replace(tzinfo=None)
                except Exception:
                    activated = datetime.utcnow()
            period_end = activated + timedelta(days=30)

        if charge_id and old_price > 0:
            try:
                await cancel_subscription(tenant["shop_domain"], tenant["_token"], charge_id)
            except Exception as e:
                logger.warning(f"⚠️ Could not cancel Shopify subscription {charge_id}: {e}")

        await schedule_downgrade(tenant["_id"], plan_type, period_end)
        await _log_subscription_event(
            db, str(tenant["_id"]), "downgrade_scheduled",
            tenant.get("plan"), plan_type, 0.0,
            {"period_end": period_end.isoformat() if hasattr(period_end, "isoformat") else str(period_end)}
        )
        return {
            "success": True,
            "scheduled": True,
            "plan": plan_type,
            "effective_date": period_end.date().isoformat() if hasattr(period_end, "date") else str(period_end),
            "message": f"Downgrade scheduled. Your current plan stays active until {period_end}."
        }

    try:
        charge = await create_subscription_charge(
            tenant["shop_domain"],
            tenant["_token"],
            plan_type
        )

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


@router.post("/cancel-downgrade")
async def cancel_downgrade_endpoint(tenant: dict = Depends(get_current_tenant)):
    """Cancel a previously scheduled downgrade and restore the subscription."""
    if not tenant.get("pending_downgrade_plan"):
        raise HTTPException(400, "No pending downgrade to cancel")

    db = await get_db()
    from_plan = tenant.get("plan", "free")
    await cancel_scheduled_downgrade(tenant["_id"])
    await _log_subscription_event(
        db, str(tenant["_id"]), "downgrade_cancelled",
        from_plan, from_plan, 0.0, {}
    )
    return {"success": True, "message": "Scheduled downgrade has been cancelled."}


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
        now = datetime.utcnow()
        trial_ends_at = now + timedelta(days=trial_days) if trial_days > 0 else None

        # Parse period end from Shopify response
        current_period_end = None
        raw_period_end = (charge or {}).get("currentPeriodEnd")
        if raw_period_end:
            try:
                current_period_end = datetime.fromisoformat(raw_period_end.replace("Z", "+00:00")).replace(tzinfo=None)
            except Exception:
                pass
        if not current_period_end:
            current_period_end = now + timedelta(days=30)

        db = await get_db()
        plan_type = tenant.get("pending_plan", "free")
        old_plan = tenant.get("plan", "free")

        await aw(db.tenants.update_one(
            {"_id": tenant["_id"]},
            {
                "$set": {
                    "plan": plan_type,
                    "subscription_status": "trial" if trial_days > 0 else "active",
                    "shopify_charge_id": charge_id,
                    "trial_ends_at": trial_ends_at,
                    "current_period_end": current_period_end,
                    "activated_on": now,
                },
                "$unset": {"pending_charge_id": "", "pending_plan": ""}
            }
        ))
        await _log_subscription_event(
            db, str(tenant["_id"]), "plan_upgraded",
            old_plan, plan_type,
            PLANS.get(plan_type, {}).get("price", 0.0),
            {"charge_id": charge_id, "trial_days": trial_days}
        )

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
