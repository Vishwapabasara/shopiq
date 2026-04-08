import hashlib
import hmac
import secrets
import urllib.parse
import re
import logging
import inspect
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

from app.config import settings
from app.dependencies import get_db
from app.utils.crypto import encrypt_token
from app.utils.shopify_client import get_shop_info

router = APIRouter(prefix="/auth", tags=["auth"])

# Create logger
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
    expected = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, received)


@router.get("/shopify/install")
async def install(request: Request, shop: str = Query(...)):
    logger.info(f"🚀 Install initiated for shop: {shop}")
    
    if not _valid_shop(shop):
        logger.error(f"❌ Invalid shop domain: {shop}")
        raise HTTPException(400, "Invalid shop domain")
    
    state = secrets.token_urlsafe(32)
    
    # Log session before storing
    logger.info(f"📝 Generated state: {state[:10]}...")
    logger.info(f"🍪 Session ID before: {request.session.get('_session_id', 'NO SESSION')}")
    
    request.session["oauth_state"] = state
    request.session["oauth_shop"] = shop
    
    # Log session after storing
    logger.info(f"✅ Stored state in session: {request.session.get('oauth_state', 'FAILED')[:10]}...")
    logger.info(f"✅ Stored shop in session: {request.session.get('oauth_shop', 'FAILED')}")
    logger.info(f"🍪 Full session data: {dict(request.session)}")
    
    params = {
        "client_id": settings.SHOPIFY_API_KEY,
        "scope": settings.SHOPIFY_SCOPES,
        "redirect_uri": f"{settings.APP_URL}/auth/shopify/callback",
        "state": state,
    }
    
    auth_url = f"https://{shop}/admin/oauth/authorize?" + urllib.parse.urlencode(params)
    logger.info(f"🔗 Redirecting to: {auth_url}")
    
    return RedirectResponse(url=auth_url, status_code=302)


@router.get("/shopify/callback")
async def callback(
    request: Request,
    shop: str = Query(...),
    code: str = Query(...),
    state: str = Query(...),
    hmac: str = Query(...),
):
    logger.info(f"🔙 Callback received for shop: {shop}")
    logger.info(f"📥 Received state: {state[:10]}...")
    logger.info(f"🍪 Session ID on callback: {request.session.get('_session_id', 'NO SESSION')}")
    logger.info(f"🍪 Full session data on callback: {dict(request.session)}")
     logger.info(f"✅ OAuth flow completed successfully for {shop}")
    
    stored_state = request.session.get("oauth_state")
    logger.info(f"💾 Stored state from session: {stored_state[:10] if stored_state else 'NONE'}...")
    
    if state != stored_state:
        logger.error(f"❌ STATE MISMATCH!")
        logger.error(f"   Received: {state[:10]}...")
        logger.error(f"   Expected: {stored_state[:10] if stored_state else 'NONE'}...")
        logger.error(f"   Session contents: {dict(request.session)}")
        raise HTTPException(403, "State mismatch — possible CSRF")
    
    logger.info("✅ State matched successfully")
    
    if not _valid_shop(shop):
        logger.error(f"❌ Invalid shop domain: {shop}")
        raise HTTPException(400, "Invalid shop domain")
    
    if not _verify_hmac(dict(request.query_params), settings.SHOPIFY_API_SECRET):
        logger.error(f"❌ HMAC verification failed")
        raise HTTPException(403, "HMAC verification failed")
    
    logger.info("✅ HMAC verified successfully")

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

    shop_info = {}
    try:
        shop_info = await get_shop_info(shop, access_token)
        logger.info(f"✅ Shop info retrieved: {shop_info.get('name', 'N/A')}")
    except Exception as e:
        logger.warning(f"⚠️ Failed to get shop info: {e}")

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
    
    logger.info(f"✅ OAuth flow completed successfully for {shop}")
    
     return RedirectResponse(
        url=f"https://shopiq-iota.vercel.app/dashboard?shop={shop}",  # Update this URL
        status_code=302
    )


@router.get("/me")
async def me(request: Request):
    shop = request.session.get("shop")
    if not shop:
        logger.info("ℹ️ /me called but no shop in session")
        return {"authenticated": False}
    db = await get_db()
    tenant = await aw(db.tenants.find_one({"shop_domain": shop}, {"access_token": 0}))
    if not tenant:
        logger.warning(f"⚠️ Shop {shop} in session but not in database")
        return {"authenticated": False}
    return {
        "authenticated": True,
        "shop_domain": tenant["shop_domain"],
        "shop_name": tenant.get("shop_name", shop),
        "plan": tenant.get("plan", "starter"),
        "modules_enabled": tenant.get("modules_enabled", ["audit"]),
    }


@router.post("/logout")
async def logout(request: Request):
    shop = request.session.get("shop", "unknown")
    logger.info(f"👋 Logout for shop: {shop}")
    request.session.clear()
    return {"ok": True}