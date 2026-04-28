"""
Account profile — aggregates tenant info, usage, audit history, and achievements.
GET /account/profile
"""
import logging
import inspect
from datetime import datetime

from fastapi import APIRouter, Depends
from bson import ObjectId

from app.config import PLANS
from app.dependencies import get_db, get_current_tenant

router = APIRouter(prefix="/account", tags=["account"])
logger = logging.getLogger(__name__)


async def aw(result):
    if inspect.isawaitable(result):
        return await result
    return result


def _compute_achievements(history: list, total_copy_sessions: int) -> list:
    """
    Derive achievements from audit history and usage.
    Each achievement: { id, title, description, icon, unlocked, unlocked_at }
    """
    scores = [h.get("overall_score", 0) for h in history if h.get("overall_score") is not None]
    total_audits = len(history)

    # Check for 3+ consecutive improvements
    consistent = False
    if len(scores) >= 3:
        for i in range(len(scores) - 2):
            if scores[i] < scores[i + 1] < scores[i + 2]:
                consistent = True
                break

    # Zero critical issues in any audit
    all_clean = any(h.get("critical_count", 999) == 0 for h in history)

    defs = [
        {
            "id": "first_audit",
            "title": "First Audit",
            "description": "Ran your first store audit",
            "icon": "◈",
            "unlocked": total_audits >= 1,
            "unlocked_at": history[-1].get("created_at") if total_audits >= 1 else None,
        },
        {
            "id": "score_50",
            "title": "Getting There",
            "description": "Store score reached 50+",
            "icon": "◎",
            "unlocked": any(s >= 50 for s in scores),
            "unlocked_at": None,
        },
        {
            "id": "score_70",
            "title": "Strong Store",
            "description": "Store score reached 70+",
            "icon": "◉",
            "unlocked": any(s >= 70 for s in scores),
            "unlocked_at": None,
        },
        {
            "id": "score_90",
            "title": "Elite Store",
            "description": "Store score reached 90+",
            "icon": "★",
            "unlocked": any(s >= 90 for s in scores),
            "unlocked_at": None,
        },
        {
            "id": "ten_audits",
            "title": "Audit Veteran",
            "description": "Completed 10 audits",
            "icon": "▣",
            "unlocked": total_audits >= 10,
            "unlocked_at": None,
        },
        {
            "id": "copy_ai",
            "title": "AI Copywriter",
            "description": "Generated your first AI product descriptions",
            "icon": "◻",
            "unlocked": total_copy_sessions >= 1,
            "unlocked_at": None,
        },
        {
            "id": "all_clean",
            "title": "Zero Critical Issues",
            "description": "Achieved zero critical issues in an audit",
            "icon": "✦",
            "unlocked": all_clean,
            "unlocked_at": None,
        },
        {
            "id": "consistent",
            "title": "Consistent Improver",
            "description": "Score improved 3 audits in a row",
            "icon": "▲",
            "unlocked": consistent,
            "unlocked_at": None,
        },
    ]
    return defs


@router.get("/profile")
async def get_profile(tenant: dict = Depends(get_current_tenant)):
    db = await get_db()
    tenant_id = str(tenant["_id"])

    # ── Audit history (all completed, for achievements + chart) ──────────────────
    cursor = db.audits.find(
        {"tenant_id": tenant_id, "status": "complete"},
        {
            "_id": 1,
            "overall_score": 1,
            "category_scores": 1,
            "products_scanned": 1,
            "critical_count": 1,
            "warning_count": 1,
            "created_at": 1,
            "completed_at": 1,
        },
    ).sort("created_at", -1)

    try:
        all_audits = await cursor.to_list(length=200)
    except TypeError:
        all_audits = list(cursor)

    for a in all_audits:
        a["_id"] = str(a["_id"])
        if isinstance(a.get("created_at"), datetime):
            a["created_at"] = a["created_at"].isoformat()
        if isinstance(a.get("completed_at"), datetime):
            a["completed_at"] = a["completed_at"].isoformat()

    history_for_chart = list(reversed(all_audits[:20]))  # oldest-first, last 20

    # ── Audit summary stats ───────────────────────────────────────────────────────
    total_completed = len(all_audits)
    scores = [a["overall_score"] for a in all_audits if a.get("overall_score") is not None]
    best_score = max(scores) if scores else None
    latest_score = scores[0] if scores else None
    first_score = scores[-1] if len(scores) >= 2 else None
    score_improvement = (latest_score - first_score) if (latest_score is not None and first_score is not None) else None

    # ── Copy sessions count ───────────────────────────────────────────────────────
    try:
        total_copy = await aw(db.copy_sessions.count_documents(
            {"tenant_id": tenant_id, "status": "complete"}
        ))
    except Exception:
        total_copy = 0

    # ── Plan info ─────────────────────────────────────────────────────────────────
    plan_key = tenant.get("plan", "free")
    if plan_key == "starter":
        plan_key = "free"
    plan_config = PLANS.get(plan_key, PLANS["free"])
    usage = tenant.get("usage", {})
    scan_state = tenant.get("scan_state", {})

    # ── Subscription ─────────────────────────────────────────────────────────────
    trial_ends_at = tenant.get("trial_ends_at")
    installed_at = tenant.get("installed_at")

    return {
        # Store identity
        "shop_name": tenant.get("shop_name", tenant.get("shop_domain", "")),
        "shop_domain": tenant.get("shop_domain", ""),
        "shop_email": tenant.get("shop_email", ""),
        "installed_at": installed_at.isoformat() if isinstance(installed_at, datetime) else installed_at,

        # Plan
        "plan": plan_key,
        "plan_config": plan_config,
        "subscription": {
            "status": tenant.get("subscription_status", "active"),
            "trial_ends_at": trial_ends_at.isoformat() if isinstance(trial_ends_at, datetime) else trial_ends_at,
            "cancel_at_period_end": tenant.get("cancel_at_period_end", False),
            "shopify_charge_id": tenant.get("shopify_charge_id"),
        },

        # Usage (current month)
        "usage": {
            "audits_used": usage.get("audits_used_this_month", 0),
            "products_scanned": usage.get("products_scanned_this_month", 0),
            "copy_generations_used": usage.get("copy_generations_used_this_month", 0),
            "ai_fixes_used": usage.get("ai_fixes_used_this_month", 0),
            "period_start": usage.get("period_start").isoformat() if isinstance(usage.get("period_start"), datetime) else None,
            "period_end": usage.get("period_end").isoformat() if isinstance(usage.get("period_end"), datetime) else None,
        },
        "limits": {
            "audits_per_month": plan_config["audits_per_month"],
            "copy_generations_per_month": plan_config.get("copy_generations_per_month", -1),
            "ai_fixes_per_month": plan_config.get("ai_fixes_per_month", -1),
            "audit_batch_size": plan_config.get("audit_batch_size", 0),
        },

        # Scan progress
        "scan_state": {
            "total_products": scan_state.get("total_products", 0),
            "cursor": scan_state.get("cursor", 0),
        },

        # Audit stats
        "audit_stats": {
            "total_completed": total_completed,
            "best_score": best_score,
            "latest_score": latest_score,
            "first_score": first_score,
            "score_improvement": score_improvement,
            "total_copy_sessions": total_copy,
        },

        # Last 20 audits for chart (oldest first)
        "score_history": history_for_chart,

        # Achievements
        "achievements": _compute_achievements(all_audits, total_copy),
    }
