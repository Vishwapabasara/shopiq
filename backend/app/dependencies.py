from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from fastapi import Request, HTTPException
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


# ── Auth dependency ───────────────────────────────────────────────────────────

async def get_current_tenant(request: Request) -> dict:
    shop = request.session.get("shop")
    if not shop:
        raise HTTPException(401, detail="Not authenticated")

    db = await get_db()
    tenant = await aw(db.tenants.find_one({"shop_domain": shop}))
    if not tenant:
        raise HTTPException(404, detail="Store not found — please reinstall the app")

    token = tenant.get("access_token", "")
    if token and token not in ("mock_token_not_real", ""):
        tenant["_token"] = decrypt_token(token)
    else:
        tenant["_token"] = token

    return tenant
