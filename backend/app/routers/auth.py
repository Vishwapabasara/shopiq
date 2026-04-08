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
    expected = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, received)


@router.get("/shopify/install")
async def install(request: Request, shop: str = Query(...)):
    """Initiate Shopify OAuth flow"""
    logger.info(f"🚀 Install initiated for shop: {shop}")
    
    if not _valid_shop(shop):
        logger.error(f"❌ Invalid shop domain: {shop}")
        raise HTTPException(400, "Invalid shop domain")
    
    state = secrets.token_urlsafe(32)
    
    # Store state in session
    request.session["oauth_state"] = state
    request.session["oauth_shop"] = shop
    
    logger.info(f"📝 Generated state: {state[:10]}...")
    logger.info(f"✅ Stored in session")
    
    # Build Shopify OAuth URL
    params = {
        "client_id": settings.SHOPIFY_API_KEY,
        "scope": settings.SHOPIFY_SCOPES,
        "redirect_uri": f"{settings.APP_URL}/auth/shopify/callback",
        "state": state,
    }
    
    auth_url = f"https://{shop}/admin/oauth/authorize?" + urllib.parse.urlencode(params)
    logger.info(f"🔗 Redirecting to Shopify OAuth")
    
    return RedirectResponse(url=auth_url, status_code=302)


@router.get("/shopify/callback")
async def callback(
    request: Request,
    shop: str = Query(...),
    code: str = Query(...),
    state: str = Query(...),
    hmac: str = Query(...),
):
    """Handle Shopify OAuth callback"""
    logger.info(f"🔙 Callback received for shop: {shop}")
    
    # Verify state (CSRF protection)
    stored_state = request.session.get("oauth_state")
    
    if state != stored_state:
        logger.error(f"❌ STATE MISMATCH! Received: {state[:10]}, Expected: {stored_state[:10] if stored_state else 'NONE'}")
        raise HTTPException(403, "State mismatch — possible CSRF")
    
    logger.info("✅ State matched")
    
    # Verify shop domain
    if not _valid_shop(shop):
        logger.error(f"❌ Invalid shop domain: {shop}")
        raise HTTPException(400, "Invalid shop domain")
    
    # Verify HMAC signature
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

    # Set session
    request.session["shop"] = shop
    request.session.pop("oauth_state", None)
    request.session.pop("oauth_shop", None)
    
    logger.info(f"✅ OAuth flow completed for {shop}")
    
    # Redirect to frontend dashboard with token
    # Frontend will use this to establish authenticated session
    frontend_url = f"https://shopiq-iota.vercel.app/auth/callback?shop={shop}&success=true"
    
    return RedirectResponse(url=frontend_url, status_code=302)


@router.get("/me")
async def me(request: Request):
    """Get current authenticated user info"""
    shop = request.session.get("shop")
    
    if not shop:
        logger.info("ℹ️ /me called but no shop in session")
        return JSONResponse(
            status_code=401,
            content={"authenticated": False, "error": "No active session"}
        )
    
    db = await get_db()
    tenant = await aw(db.tenants.find_one(
        {"shop_domain": shop},
        {"access_token": 0}  # Don't return encrypted token
    ))
    
    if not tenant:
        logger.warning(f"⚠️ Shop {shop} in session but not in database")
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


@router.post("/session")
async def create_session(request: Request, shop: str = Query(...)):
    """
    Create a session for a shop (called by frontend after OAuth redirect)
    This allows the frontend to establish an authenticated session
    """
    logger.info(f"📝 Session creation requested for: {shop}")
    
    if not _valid_shop(shop):
        raise HTTPException(400, "Invalid shop domain")
    
    # Verify shop exists in database
    db = await get_db()
    tenant = await aw(db.tenants.find_one({"shop_domain": shop}))
    
    if not tenant:
        logger.warning(f"⚠️ Shop {shop} not found in database")
        raise HTTPException(404, "Shop not found - please install the app first")
    
    # Set session
    request.session["shop"] = shop
    logger.info(f"✅ Session created for {shop}")
    
    return {
        "success": True,
        "shop": shop,
        "authenticated": True
    }


@router.post("/logout")
async def logout(request: Request):
    """Clear session and log out"""
    shop = request.session.get("shop", "unknown")
    logger.info(f"👋 Logout for shop: {shop}")
    request.session.clear()
    return {"success": True, "message": "Logged out successfully"}


@router.get("/verify")
async def verify_shop(shop: str = Query(...)):
    """
    Verify if a shop has installed the app (public endpoint)
    Used by frontend before redirecting to OAuth
    """
    if not _valid_shop(shop):
        raise HTTPException(400, "Invalid shop domain")
    
    db = await get_db()
    tenant = await aw(db.tenants.find_one(
        {"shop_domain": shop},
        {"_id": 1}  # Only check existence
    ))
    
    return {
        "shop": shop,
        "installed": tenant is not None
    }

@router.post("/login")
async def login(request: Request, shop: str = Query(...)):
    """
    Login endpoint - used by frontend to initiate OAuth
    Returns the install URL for the frontend to redirect to
    """
    logger.info(f"🔐 Login requested for shop: {shop}")
    
    if not _valid_shop(shop):
        raise HTTPException(400, "Invalid shop domain")
    
    # Check if shop is already installed
    db = await get_db()
    tenant = await aw(db.tenants.find_one({"shop_domain": shop}))
    
    install_url = f"{settings.APP_URL}/auth/shopify/install?shop={shop}"
    
    return {
        "success": True,
        "shop": shop,
        "installed": tenant is not None,
        "install_url": install_url,
        "action": "redirect"  # Frontend should redirect to install_url
    }

 @router.post("/force-reinstall")
async def force_reinstall(request: Request):
    """Delete tenant and force reinstall"""
    shop = request.session.get("shop")
    if not shop:
        raise HTTPException(401, "Not authenticated")
    
    db = await get_db()
    result = await aw(db.tenants.delete_one({"shop_domain": shop}))
    
    logger.info(f"🗑️ Deleted tenant: {shop}")
    request.session.clear()
    
    return {"success": True, "message": "Tenant deleted. Please reinstall the app."}