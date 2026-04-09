import hashlib
import hmac as hmac_lib   # ← renamed to avoid shadowing
import secrets
import urllib.parse
import re
import logging
import inspect
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse, JSONResponse

from app.config import settings
from app.dependencies import get_db
from app.utils.crypto import encrypt_token
from app.utils.shopify_client import get_shop_info

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)


async def aw(result):
    if inspect.isawaitable(result):
        return await result
    return result


def _now():
    return datetime.now(timezone.utc)


def _valid_shop(shop: str) -> bool:
    return bool(re.match(r'^[a-zA-Z0-9][a-zA-Z0-9\-]*\.myshopify\.com$', shop))


def _verify_hmac(query_params: dict, secret: str) -> bool:
    params = {k: v for k, v in query_params.items() if k != "hmac"}
    received = query_params.get("hmac", "")
    message = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
    expected = hmac_lib.new(   # ← use renamed import
        secret.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    return hmac_lib.compare_digest(expected, received)


# ── GET /shopify/install ──────────────────────────────────────────────────────

@router.get("/shopify/install")
async def install(request: Request, shop: str = Query(...)):
    logger.info(f"🚀 Install initiated for shop: {shop}")

    if not _valid_shop(shop):
        raise HTTPException(400, "Invalid shop domain")

    state = secrets.token_urlsafe(32)
    request.session["oauth_state"] = state
    request.session["oauth_shop"] = shop

    logger.info(f"📝 Generated state: {state[:10]}...")
    logger.info(f"✅ Stored in session")

    params = {
        "client_id": settings.SHOPIFY_API_KEY,
        "scope": settings.SHOPIFY_SCOPES,
        "redirect_uri": f"{settings.APP_URL}/auth/shopify/callback",
        "state": state,
    }

    auth_url = f"https://{shop}/admin/oauth/authorize?" + urllib.parse.urlencode(params)
    logger.info(f"🔗 Redirecting to Shopify OAuth: scope={settings.SHOPIFY_SCOPES}")

    return RedirectResponse(url=auth_url, status_code=302)


# ── GET /shopify/callback ─────────────────────────────────────────────────────

@router.get("/shopify/callback")
async def callback(
    request: Request,
    shop: str = Query(...),
    code: str = Query(...),
    state: str = Query(...),
    hmac: str = Query(...),    # ← keep as query param name (Shopify requires it)
):
    logger.info(f"🔙 Callback received for shop: {shop}")

    stored_state = request.session.get("oauth_state")
    if state != stored_state:
        logger.error(f"❌ STATE MISMATCH!")
        raise HTTPException(403, "State mismatch — possible CSRF")
    logger.info("✅ State matched")

    if not _valid_shop(shop):
        raise HTTPException(400, "Invalid shop domain")

    # Use hmac_lib for verification (not the query param)
    if not _verify_hmac(dict(request.query_params), settings.SHOPIFY_API_SECRET):
        logger.error(f"❌ HMAC verification failed")
        raise HTTPException(403, "HMAC verification failed")
    logger.info("✅ HMAC verified")

    # Exchange code for access token
    async with httpx.AsyncClient() as client:
        logger.info(f"🔑 Exchanging code for access token...")
        resp = await client.post(
            f"https://{shop}/admin/oauth/access_token",
            json={
                "client_id": settings.SHOPIFY_API_KEY,
                "client_secret": settings.SHOPIFY_API_SECRET,
                "code": code,
            },
        )
        resp.raise_for_status()
        token_data = resp.json()

    access_token = token_data["access_token"]
    scopes = token_data.get("scope", "")
    logger.info(f"✅ Access token obtained, scopes: {scopes}")

    if not scopes:
        logger.error("❌ Empty scopes returned from Shopify — check app configuration")

    # Get shop info
    shop_info = {}
    try:
        shop_info = await get_shop_info(shop, access_token)
        logger.info(f"✅ Shop info retrieved: {shop_info.get('name', 'N/A')}")
    except Exception as e:
        logger.warning(f"⚠️ Failed to get shop info: {e}")

    # Save to database
    db = await get_db()
    await aw(db.tenants.update_one(
        {"shop_domain": shop},
        {"$set": {
            "shop_domain": shop,
            "access_token": encrypt_token(access_token),
            "scopes": scopes,
            "plan": "starter",
            "modules_enabled": ["audit"],
            "shop_name": shop_info.get("name", shop),
            "shop_email": shop_info.get("email", ""),
            "updated_at": _now(),
        }, "$setOnInsert": {"installed_at": _now()}},
        upsert=True,
    ))
    logger.info(f"✅ Tenant record updated in database")

    request.session["shop"] = shop
    request.session.pop("oauth_state", None)
    request.session.pop("oauth_shop", None)
    logger.info(f"✅ OAuth flow completed for {shop}")

    frontend_url = f"{settings.FRONTEND_URL}/auth/callback?shop={shop}&success=true"
    return RedirectResponse(url=frontend_url, status_code=302)


# ── GET /me ───────────────────────────────────────────────────────────────────

@router.get("/me")
async def me(request: Request):
    shop = request.session.get("shop")

    if not shop:
        return JSONResponse(
            status_code=401,
            content={"authenticated": False, "error": "No active session"}
        )

    db = await get_db()
    tenant = await aw(db.tenants.find_one(
        {"shop_domain": shop},
        {"access_token": 0}
    ))

    if not tenant:
        return JSONResponse(
            status_code=404,
            content={"authenticated": False, "error": "Shop not found"}
        )

    return {
        "authenticated": True,
        "shop_domain": tenant["shop_domain"],
        "shop_name": tenant.get("shop_name", shop),
        "shop_email": tenant.get("shop_email", ""),
        "plan": tenant.get("plan", "starter"),
        "modules_enabled": tenant.get("modules_enabled", ["audit"]),
        "installed_at": tenant.get("installed_at").isoformat() if tenant.get("installed_at") else None,
    }


# ── POST /session ─────────────────────────────────────────────────────────────

@router.post("/session")
async def create_session(request: Request, shop: str = Query(...)):
    logger.info(f"📝 Session creation requested for: {shop}")

    if not _valid_shop(shop):
        raise HTTPException(400, "Invalid shop domain")

    db = await get_db()
    tenant = await aw(db.tenants.find_one({"shop_domain": shop}))

    if not tenant:
        raise HTTPException(404, "Shop not found - please install the app first")

    request.session["shop"] = shop
    logger.info(f"✅ Session created for {shop}")

    return {"success": True, "shop": shop, "authenticated": True}


# ── POST /logout (once only) ──────────────────────────────────────────────────

@router.post("/logout")
async def logout(request: Request):
    shop = request.session.get("shop", "unknown")
    logger.info(f"👋 Logout for shop: {shop}")
    request.session.clear()
    return {"success": True, "message": "Logged out successfully"}


# ── GET /verify ───────────────────────────────────────────────────────────────

@router.get("/verify")
async def verify_shop(shop: str = Query(...)):
    if not _valid_shop(shop):
        raise HTTPException(400, "Invalid shop domain")

    db = await get_db()
    tenant = await aw(db.tenants.find_one({"shop_domain": shop}, {"_id": 1}))

    return {"shop": shop, "installed": tenant is not None}


# ── POST /login ───────────────────────────────────────────────────────────────

@router.post("/login")
async def login(request: Request, shop: str = Query(...)):
    logger.info(f"🔐 Login requested for shop: {shop}")

    if not _valid_shop(shop):
        raise HTTPException(400, "Invalid shop domain")

    db = await get_db()
    tenant = await aw(db.tenants.find_one({"shop_domain": shop}))

    install_url = f"{settings.APP_URL}/auth/shopify/install?shop={shop}"

    return {
        "success": True,
        "shop": shop,
        "installed": tenant is not None,
        "install_url": install_url,
        "action": "redirect"
    }


# ── POST /force-reinstall ─────────────────────────────────────────────────────

@router.post("/force-reinstall")
async def force_reinstall(request: Request):
    shop = request.session.get("shop")
    if not shop:
        raise HTTPException(401, "Not authenticated")

    db = await get_db()
    await aw(db.tenants.delete_one({"shop_domain": shop}))
    logger.info(f"🗑️ Deleted tenant: {shop}")
    request.session.clear()

    return {"success": True, "message": "Tenant deleted. Please reinstall the app."}


# ── GET /test-install-url ─────────────────────────────────────────────────────

@router.get("/test-install-url")
async def test_install_url(shop: str = "test.myshopify.com"):
    params = {
        "client_id": settings.SHOPIFY_API_KEY,
        "scope": settings.SHOPIFY_SCOPES,
        "redirect_uri": f"{settings.APP_URL}/auth/shopify/callback",
        "state": "test-state-123",
    }
    auth_url = f"https://{shop}/admin/oauth/authorize?" + urllib.parse.urlencode(params)

    return {
        "shopify_api_key": settings.SHOPIFY_API_KEY[:10] + "...",
        "shopify_scopes": settings.SHOPIFY_SCOPES,
        "app_url": settings.APP_URL,
        "full_oauth_url": auth_url,
    }