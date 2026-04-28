"""
Admin panel API — protected by a hardcoded username/password that issues
a short-lived HMAC token. All endpoints require X-Admin-Token header.
"""
import base64
import hashlib
import hmac as hmac_lib
import logging
import time
from datetime import datetime

from bson import ObjectId
from fastapi import APIRouter, Body, Depends, Header, HTTPException
from pydantic import BaseModel

from app.config import PLANS, settings
from app.dependencies import get_db

router = APIRouter(prefix="/admin", tags=["admin"])
logger = logging.getLogger(__name__)

ADMIN_TOKEN_TTL = 24 * 3600  # 24 hours


# ── Token helpers ─────────────────────────────────────────────────────────────

def _make_token() -> str:
    ts = str(int(time.time()))
    sig = hmac_lib.new(
        settings.SESSION_SECRET.encode(),
        f"shopiq_admin:{ts}".encode(),
        hashlib.sha256,
    ).hexdigest()
    raw = f"shopiq_admin:{ts}:{sig}"
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def _verify_token(token: str) -> bool:
    try:
        padded = token + "=" * (-len(token) % 4)
        raw = base64.urlsafe_b64decode(padded.encode()).decode()
        parts = raw.split(":", 2)
        if len(parts) != 3 or parts[0] != "shopiq_admin":
            return False
        _, ts, sig = parts
        if int(time.time()) - int(ts) > ADMIN_TOKEN_TTL:
            return False
        expected = hmac_lib.new(
            settings.SESSION_SECRET.encode(),
            f"shopiq_admin:{ts}".encode(),
            hashlib.sha256,
        ).hexdigest()
        return hmac_lib.compare_digest(expected, sig)
    except Exception:
        return False


def require_admin(x_admin_token: str = Header(None)) -> bool:
    if not x_admin_token or not _verify_token(x_admin_token):
        raise HTTPException(status_code=401, detail="Admin authentication required")
    return True


# ── Auth ──────────────────────────────────────────────────────────────────────

class LoginBody(BaseModel):
    username: str
    password: str


@router.post("/login")
async def admin_login(body: LoginBody):
    if not settings.ADMIN_PASSWORD:
        raise HTTPException(503, "Admin access is not configured on this server. Set ADMIN_PASSWORD.")
    if body.username != settings.ADMIN_USERNAME or body.password != settings.ADMIN_PASSWORD:
        raise HTTPException(401, "Invalid credentials")
    token = _make_token()
    logger.info("Admin login successful")
    return {"token": token, "expires_in": ADMIN_TOKEN_TTL}


# ── Stats ─────────────────────────────────────────────────────────────────────

@router.get("/stats")
async def get_stats(_: bool = Depends(require_admin)):
    db = await get_db()
    now = datetime.utcnow()

    # Plan distribution
    plan_counts: dict = {}
    async for doc in db.tenants.aggregate([{"$group": {"_id": "$plan", "count": {"$sum": 1}}}]):
        key = doc["_id"] or "free"
        if key == "starter":
            key = "free"
        plan_counts[key] = plan_counts.get(key, 0) + doc["count"]

    total_stores = sum(plan_counts.values())
    mrr = sum(
        PLANS.get(k, {}).get("price", 0) * v
        for k, v in plan_counts.items()
    )

    # Subscription health
    active_trials = await db.tenants.count_documents({
        "subscription_status": "trial",
        "trial_ends_at": {"$gt": now},
    })
    past_due = await db.tenants.count_documents({"subscription_status": "past_due"})

    # New stores this month
    month_start = datetime(now.year, now.month, 1)
    new_this_month = await db.tenants.count_documents({"installed_at": {"$gte": month_start}})

    # Aggregate usage this month
    usage_totals = {"total_audits": 0, "total_copy": 0}
    async for doc in db.tenants.aggregate([{
        "$group": {
            "_id": None,
            "total_audits": {"$sum": "$usage.audits_used_this_month"},
            "total_copy": {"$sum": "$usage.copy_generations_used_this_month"},
        }
    }]):
        usage_totals = doc

    return {
        "total_stores": total_stores,
        "stores_by_plan": {
            "free": plan_counts.get("free", 0),
            "pro": plan_counts.get("pro", 0),
            "enterprise": plan_counts.get("enterprise", 0),
        },
        "mrr": round(mrr, 2),
        "active_trials": active_trials,
        "past_due": past_due,
        "new_this_month": new_this_month,
        "total_audits_this_month": usage_totals.get("total_audits", 0),
        "total_copy_this_month": usage_totals.get("total_copy", 0),
    }


# ── Tenants ───────────────────────────────────────────────────────────────────

@router.get("/tenants")
async def list_tenants(
    search: str = "",
    plan: str = "",
    status: str = "",
    page: int = 1,
    limit: int = 25,
    _: bool = Depends(require_admin),
):
    db = await get_db()

    query: dict = {}
    if search:
        query["$or"] = [
            {"shop_domain": {"$regex": search, "$options": "i"}},
            {"shop_name": {"$regex": search, "$options": "i"}},
        ]
    if plan:
        query["plan"] = plan
    if status:
        query["subscription_status"] = status

    total = await db.tenants.count_documents(query)
    skip = (page - 1) * limit

    tenants = []
    async for t in db.tenants.find(query, {
        "_id": 1, "shop_domain": 1, "shop_name": 1,
        "plan": 1, "subscription_status": 1,
        "trial_ends_at": 1, "installed_at": 1, "activated_on": 1,
        "usage": 1, "pending_downgrade_plan": 1, "shopify_charge_id": 1,
    }).sort("installed_at", -1).skip(skip).limit(limit):
        plan_key = t.get("plan", "free")
        if plan_key == "starter":
            plan_key = "free"
        plan_cfg = PLANS.get(plan_key, PLANS["free"])
        usage = t.get("usage", {})

        def _iso(v):
            return v.isoformat() if isinstance(v, datetime) else v

        tenants.append({
            "id": str(t["_id"]),
            "shop_domain": t.get("shop_domain", ""),
            "shop_name": t.get("shop_name", ""),
            "plan": plan_key,
            "subscription_status": t.get("subscription_status", "active"),
            "trial_ends_at": _iso(t.get("trial_ends_at")),
            "installed_at": _iso(t.get("installed_at")),
            "activated_on": _iso(t.get("activated_on")),
            "pending_downgrade_plan": t.get("pending_downgrade_plan"),
            "shopify_charge_id": t.get("shopify_charge_id"),
            "usage": {
                "audits_used": usage.get("audits_used_this_month", 0),
                "audits_limit": plan_cfg["audits_per_month"],
                "copy_used": usage.get("copy_generations_used_this_month", 0),
                "copy_limit": plan_cfg.get("copy_generations_per_month", 0),
                "last_updated": _iso(usage.get("last_updated")),
            },
        })

    return {"tenants": tenants, "total": total, "page": page, "pages": max(1, (total + limit - 1) // limit)}


@router.patch("/tenants/{tenant_id}/plan")
async def override_plan(
    tenant_id: str,
    body: dict = Body(...),
    _: bool = Depends(require_admin),
):
    db = await get_db()
    new_plan = body.get("plan")
    if not new_plan or new_plan not in PLANS:
        raise HTTPException(400, "Invalid plan")

    try:
        oid = ObjectId(tenant_id)
    except Exception:
        raise HTTPException(400, "Invalid tenant ID")

    tenant = await db.tenants.find_one({"_id": oid}, {"plan": 1, "shop_domain": 1})
    if not tenant:
        raise HTTPException(404, "Tenant not found")

    old_plan = tenant.get("plan", "free")
    now = datetime.utcnow()

    await db.tenants.update_one(
        {"_id": oid},
        {
            "$set": {
                "plan": new_plan,
                "subscription_status": "active",
                "shopify_charge_id": f"admin_override_{int(now.timestamp())}",
                "activated_on": now,
            },
            "$unset": {
                "pending_downgrade_plan": "",
                "pending_downgrade_at": "",
                "cancel_at_period_end": "",
            },
        },
    )

    await db.subscription_events.insert_one({
        "tenant_id": tenant_id,
        "shop_domain": tenant.get("shop_domain", ""),
        "event_type": "admin_override",
        "from_plan": old_plan,
        "to_plan": new_plan,
        "amount": 0.0,
        "metadata": {"admin": True},
        "created_at": now,
    })

    logger.info(f"Admin plan override: {tenant.get('shop_domain')} {old_plan} → {new_plan}")
    return {"success": True, "plan": new_plan}


# ── Subscription Events ───────────────────────────────────────────────────────

@router.get("/events")
async def list_events(
    page: int = 1,
    limit: int = 30,
    _: bool = Depends(require_admin),
):
    db = await get_db()
    total = await db.subscription_events.count_documents({})
    skip = (page - 1) * limit

    # Collect events
    raw_events = []
    async for e in db.subscription_events.find({}).sort("created_at", -1).skip(skip).limit(limit):
        raw_events.append(e)

    # Batch-resolve shop domains for events that don't already have one
    missing_ids = [
        e["tenant_id"] for e in raw_events
        if not e.get("shop_domain") and e.get("tenant_id")
    ]
    domain_map: dict = {}
    for tid in set(missing_ids):
        try:
            t = await db.tenants.find_one({"_id": ObjectId(tid)}, {"shop_domain": 1})
            if t:
                domain_map[tid] = t.get("shop_domain", "")
        except Exception:
            pass

    events = []
    for e in raw_events:
        created_at = e.get("created_at")
        tid = e.get("tenant_id", "")
        events.append({
            "id": str(e["_id"]),
            "tenant_id": tid,
            "shop_domain": e.get("shop_domain") or domain_map.get(tid, ""),
            "event_type": e.get("event_type", ""),
            "from_plan": e.get("from_plan"),
            "to_plan": e.get("to_plan", ""),
            "amount": e.get("amount", 0.0),
            "created_at": created_at.isoformat() if isinstance(created_at, datetime) else created_at,
        })

    return {"events": events, "total": total, "page": page, "pages": max(1, (total + limit - 1) // limit)}
