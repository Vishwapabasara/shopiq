from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from fastapi import Request, HTTPException
from bson import ObjectId
from app.config import settings
from app.utils.crypto import decrypt_token
import inspect
import hmac
import hashlib
import base64
import json
import time

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


def _validate_session_token(token: str) -> dict | None:
    """Validate Shopify session token JWT. Returns payload dict or None."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header_b64, payload_b64, sig_b64 = parts
        signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
        digest = hmac.new(
            settings.SHOPIFY_API_SECRET.encode("utf-8"),
            signing_input,
            hashlib.sha256,
        ).digest()
        expected = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("utf-8")
        if not hmac.compare_digest(expected, sig_b64):
            return None
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
        if payload.get("exp", 0) < time.time():
            return None
        if payload.get("aud") != settings.SHOPIFY_API_KEY:
            return None
        return payload
    except Exception:
        return None


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

    # Method 0: Shopify session token (embedded app — Authorization: Bearer <jwt>)
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        payload = _validate_session_token(auth_header[7:])
        if payload:
            dest = payload.get("dest", "")
            token_shop = dest.replace("https://", "").replace("http://", "").rstrip("/")
            if token_shop:
                tenant = await aw(db.tenants.find_one({"shop_domain": token_shop}))
                if tenant:
                    access_token = tenant.get("access_token", "")
                    tenant["_token"] = decrypt_token(access_token) if access_token and access_token not in ("mock_token_not_real", "") else access_token
                    return tenant

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
