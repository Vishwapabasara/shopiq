from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from fastapi import Request, HTTPException
from bson import ObjectId
from app.config import settings
from app.utils.crypto import decrypt_token
import inspect

# ── Database ──────────────────────────────────────────────────────────────────

_client = None


def get_client():
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.MONGO_URI)
    return _client


async def get_db():
    db_name = settings.MONGO_URI.split("/")[-1].split("?")[0] or "shopiq"
    return get_client()[db_name]


async def aw(result):
    """Await if awaitable (motor), return directly if not (mongomock)."""
    if inspect.isawaitable(result):
        return await result
    return result


async def create_indexes():
    db = await get_db()
    await aw(db.tenants.create_index("shop_domain", unique=True))
    await aw(db.audits.create_index([("tenant_id", 1), ("created_at", -1)]))
    await aw(db.audits.create_index("status"))
    # Session indexes for fast lookup and auto-expiry
    await aw(db.sessions.create_index("session_id", unique=True))
    await aw(db.sessions.create_index([("shop_domain", 1), ("expires_at", -1)]))
    await aw(db.sessions.create_index("expires_at", expireAfterSeconds=0))


# ── Auth dependency ───────────────────────────────────────────────────────────

async def get_current_tenant(request: Request) -> dict:
    """Get current authenticated tenant with multi-method fallback"""
    from app.services.session_manager import get_session, get_session_by_shop

    db = await get_db()

    session_id = request.session.get("session_id")
    shop_domain = request.query_params.get("shop") or request.session.get("shop_domain")

    # Method 1: Session ID from cookie
    if session_id:
        session = await get_session(session_id)
        if session:
            tenant = await aw(db.tenants.find_one({"_id": ObjectId(session["tenant_id"])}))
            if tenant:
                request.session["session_id"] = session["session_id"]
                request.session["shop_domain"] = session["shop_domain"]
                request.session["tenant_id"] = session["tenant_id"]
                token = tenant.get("access_token", "")
                tenant["_token"] = decrypt_token(token) if token and token not in ("mock_token_not_real", "") else token
                return tenant

    # Method 2: Shop domain lookup
    if shop_domain:
        session = await get_session_by_shop(shop_domain)
        if session:
            request.session["session_id"] = session["session_id"]
            request.session["shop_domain"] = session["shop_domain"]
            request.session["tenant_id"] = session["tenant_id"]
            tenant = await aw(db.tenants.find_one({"_id": ObjectId(session["tenant_id"])}))
            if tenant:
                token = tenant.get("access_token", "")
                tenant["_token"] = decrypt_token(token) if token and token not in ("mock_token_not_real", "") else token
                return tenant

    raise HTTPException(status_code=401, detail="Not authenticated")
