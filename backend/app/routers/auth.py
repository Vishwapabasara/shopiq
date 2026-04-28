import hashlib
import hmac as hmac_lib   # ← renamed to avoid shadowing
import secrets
import urllib.parse
import re
import logging
import inspect
from datetime import datetime, timezone, timedelta

import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse, JSONResponse

from app.config import settings
from app.dependencies import get_db
from app.utils.crypto import encrypt_token, decrypt_token
from app.utils.shopify_client import get_shop_info
from app.services.session_manager import create_session as create_db_session, get_session, delete_session

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


# ✅ NEW: Webhook registration function
async def register_gdpr_webhooks(shop_domain: str, access_token: str) -> dict:
    """
    Register Shopify's mandatory GDPR compliance webhooks.
    Required for App Store approval.
    
    Returns dict with registration status for each webhook.
    """
    # BACKEND_URL must be a public HTTPS URL reachable by Shopify.
    # Set BACKEND_URL in .env to your live deployment URL.
    backend_url = (settings.BACKEND_URL or settings.APP_URL).rstrip('/')
    
    webhooks_to_register = [
        {
            "topic": "customers/data_request",
            "address": f"{backend_url}/webhooks/customers/data_request",
            "format": "json"
        },
        {
            "topic": "customers/redact",
            "address": f"{backend_url}/webhooks/customers/redact",
            "format": "json"
        },
        {
            "topic": "shop/redact",
            "address": f"{backend_url}/webhooks/shop/redact",
            "format": "json"
        }
    ]
    
    results = {}
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # First, get list of existing webhooks
        try:
            list_response = await client.get(
                f"https://{shop_domain}/admin/api/2025-01/webhooks.json",
                headers={"X-Shopify-Access-Token": access_token}
            )
            existing_webhooks = list_response.json().get("webhooks", [])
        except Exception as e:
            logger.error(f"Could not list existing webhooks: {e}")
            existing_webhooks = []
        
        # Register each webhook
        for webhook_data in webhooks_to_register:
            topic = webhook_data["topic"]
            address = webhook_data["address"]
            
            try:
                # Check if already exists
                already_exists = any(
                    w.get("topic") == topic and w.get("address") == address
                    for w in existing_webhooks
                )
                
                if already_exists:
                    logger.info(f"ℹ️ Webhook already exists: {topic}")
                    results[topic] = "already_exists"
                    continue
                
                # Register the webhook
                response = await client.post(
                    f"https://{shop_domain}/admin/api/2025-01/webhooks.json",
                    headers={
                        "X-Shopify-Access-Token": access_token,
                        "Content-Type": "application/json"
                    },
                    json={"webhook": webhook_data}
                )
                
                if response.status_code == 201:
                    logger.info(f"✅ Successfully registered: {topic}")
                    results[topic] = "registered"
                elif response.status_code == 422:
                    # Already exists or validation error
                    error_msg = response.json().get("errors", {})
                    logger.info(f"ℹ️ Webhook {topic}: {error_msg}")
                    results[topic] = "already_exists"
                else:
                    logger.error(f"❌ Failed to register {topic}: {response.status_code} - {response.text}")
                    results[topic] = f"failed_{response.status_code}"
                    
            except Exception as e:
                logger.error(f"❌ Exception registering {topic}: {e}")
                results[topic] = f"error_{str(e)[:50]}"
    
    return results


# ── GET /shopify/install ──────────────────────────────────────────────────────

@router.get("/shopify/install")
async def install(request: Request, shop: str = Query(...), host: str = Query(None)):
    logger.info(f"🚀 Install initiated for shop: {shop}")

    if not _valid_shop(shop):
        raise HTTPException(400, "Invalid shop domain")

    state = secrets.token_urlsafe(32)

    # Store in DB instead of session (more reliable cross-origin)
    db = await get_db()
    await aw(db.oauth_states.update_one(
        {"shop": shop},
        {"$set": {
            "shop": shop,
            "state": state,
            "host": host or "",
            "created_at": _now()
        }},
        upsert=True
    ))

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
    hmac: str = Query(...),
):
    logger.info(f"🔙 Callback received for shop: {shop}")

    # Verify state from DB
    db = await get_db()
    stored = await aw(db.oauth_states.find_one({"shop": shop}))

    if not stored or stored.get("state") != state:
        logger.error(f"❌ STATE MISMATCH! stored={stored}")
        raise HTTPException(403, "State mismatch — possible CSRF")

    host = stored.get("host") or ""

    # Clean up used state
    await aw(db.oauth_states.delete_one({"shop": shop}))
    logger.info("✅ State matched and cleaned up")

    if not _valid_shop(shop):
        raise HTTPException(400, "Invalid shop domain")

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

    # Verify critical scopes were granted
    required_scopes = {"read_products", "write_products"}
    granted_scopes = set(scopes.split(","))
    if not required_scopes.issubset(granted_scopes):
        missing = required_scopes - granted_scopes
        logger.error(f"❌ CRITICAL: Missing required scopes: {missing}")
        logger.error(f"Requested: {settings.SHOPIFY_SCOPES}, Granted: {scopes}")
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/auth/error?reason=missing_scopes&missing={','.join(missing)}",
            status_code=302
        )
    logger.info(f"✅ All required scopes granted: {scopes}")

    # Get shop info
    shop_info = {}
    try:
        shop_info = await get_shop_info(shop, access_token)
        logger.info(f"✅ Shop info retrieved: {shop_info.get('name', 'N/A')}")
    except Exception as e:
        logger.warning(f"⚠️ Failed to get shop info: {e}")

    # Calculate billing period for new tenant initialization
    now = datetime.utcnow()
    period_start = datetime(now.year, now.month, 1)
    period_end = (
        datetime(now.year + 1, 1, 1) - timedelta(days=1)
        if now.month == 12
        else datetime(now.year, now.month + 1, 1) - timedelta(days=1)
    )

    # Save tenant to DB
    await aw(db.tenants.update_one(
        {"shop_domain": shop},
        {
            "$set": {
                "shop_domain": shop,
                "access_token": encrypt_token(access_token),
                "scopes": scopes,
                "modules_enabled": ["audit"],
                "shop_name": shop_info.get("name", shop),
                "shop_email": shop_info.get("email", ""),
                "updated_at": _now(),
            },
            "$setOnInsert": {
                "installed_at": _now(),
                "plan": "free",
                "subscription_status": "active",
                "usage": {
                    "audits_used_this_month": 0,
                    "products_scanned_this_month": 0,
                    "copy_generations_used_this_month": 0,
                    "ai_fixes_used_this_month": 0,
                    "period_start": period_start,
                    "period_end": period_end,
                    "last_updated": now,
                },
                "scan_state": {
                    "cursor": 0,
                    "scanned_product_ids": [],
                    "all_known_product_ids": [],
                    "last_scan_at": None,
                    "total_products": 0,
                },
            },
        },
        upsert=True,
    ))
    logger.info(f"✅ Tenant record updated in database")

    # ✅ NEW: Register GDPR compliance webhooks
    logger.info(f"🔗 Registering GDPR webhooks for {shop}")
    try:
        webhook_results = await register_gdpr_webhooks(shop, access_token)
        logger.info(f"✅ Webhooks registered: {webhook_results}")
    except Exception as webhook_error:
        logger.warning(f"⚠️ Webhook registration failed (non-critical): {webhook_error}")
        # Don't fail the OAuth flow if webhooks fail - they can be retried

    # Get tenant_id for session creation
    tenant_doc = await aw(db.tenants.find_one({"shop_domain": shop}, {"_id": 1}))
    tenant_id = str(tenant_doc["_id"])

    # Create database-backed session
    session_id = await create_db_session(
        shop_domain=shop,
        tenant_id=tenant_id,
        duration_days=30
    )

    # Store session in cookie
    request.session["session_id"] = session_id
    request.session["shop_domain"] = shop
    request.session["tenant_id"] = tenant_id

    logger.info(f"✅ Session created and stored in cookie: {session_id}")
    logger.info(f"✅ OAuth flow completed for {shop}")

    redirect_url = f"{settings.FRONTEND_URL}/auth/callback?shop={shop}&host={host}"
    logger.info(f"🔄 Redirecting to: {redirect_url}")
    return RedirectResponse(url=redirect_url, status_code=302)


# ── GET /me ───────────────────────────────────────────────────────────────────

@router.get("/me")
async def get_current_user(request: Request):
    from app.dependencies import get_current_tenant
    from app.shopify_session import get_current_tenant_from_session_token

    authorization = request.headers.get("authorization", "")

    try:
        if authorization.lower().startswith("bearer "):
            tenant = await get_current_tenant_from_session_token(request)
        else:
            tenant = await get_current_tenant(request)

        return {
            "authenticated": True,
            "shop_domain": tenant["shop_domain"],
            "shop_name": tenant.get("shop_name", tenant["shop_domain"]),
            "plan": tenant.get("plan", "starter"),
            "email": tenant.get("shop_email", ""),
            "scope_issue": tenant.get("scope_issue", False),
            "missing_scopes": tenant.get("missing_scopes", []),
        }

    except Exception:
        return {"authenticated": False}
# ── POST /session ─────────────────────────────────────────────────────────────

@router.post("/session")
async def create_session_endpoint(request: Request, shop: str = Query(...)):
    logger.info(f"📝 Session creation requested for: {shop}")

    if not _valid_shop(shop):
        raise HTTPException(400, "Invalid shop domain")

    db = await get_db()
    tenant = await aw(db.tenants.find_one({"shop_domain": shop}))

    if not tenant:
        raise HTTPException(404, "Shop not found - please install the app first")

    tenant_id = str(tenant["_id"])
    session_id = await create_db_session(shop_domain=shop, tenant_id=tenant_id, duration_days=30)

    request.session["session_id"] = session_id
    request.session["shop_domain"] = shop
    request.session["tenant_id"] = tenant_id
    logger.info(f"✅ Session created for {shop}: {session_id}")

    return {"success": True, "shop": shop, "session_id": session_id, "authenticated": True}


# ── POST /logout ──────────────────────────────────────────────────────────────

@router.post("/logout")
async def logout(request: Request):
    session_id = request.session.get("session_id")

    if session_id:
        await delete_session(session_id)
        logger.info(f"✅ Session deleted: {session_id}")

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


# ── GET /webhooks/status ──────────────────────────────────────────────────────

_GDPR_TOPICS = {"customers/data_request", "customers/redact", "shop/redact"}


@router.get("/webhooks/status")
async def webhook_status(shop: str = Query(...)):
    """
    Query Shopify's API and report which of the 3 mandatory GDPR webhooks
    are currently registered for the given shop.
    """
    if not _valid_shop(shop):
        raise HTTPException(400, "Invalid shop domain")

    db = await get_db()
    tenant = await aw(db.tenants.find_one({"shop_domain": shop}))
    if not tenant:
        raise HTTPException(404, "Shop not installed — complete OAuth first")

    raw_token = tenant.get("access_token", "")
    if not raw_token:
        raise HTTPException(400, "No access token stored for this shop")

    access_token = decrypt_token(raw_token)

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"https://{shop}/admin/api/2025-01/webhooks.json",
            headers={"X-Shopify-Access-Token": access_token},
        )

    if resp.status_code != 200:
        raise HTTPException(resp.status_code, f"Shopify API error: {resp.text}")

    all_webhooks = resp.json().get("webhooks", [])
    registered_topics = {w["topic"] for w in all_webhooks}

    gdpr_status = {
        topic: {
            "registered": topic in registered_topics,
            "webhook": next((w for w in all_webhooks if w["topic"] == topic), None),
        }
        for topic in _GDPR_TOPICS
    }

    return {
        "shop": shop,
        "backend_url_used": (settings.BACKEND_URL or settings.APP_URL).rstrip("/"),
        "all_gdpr_registered": _GDPR_TOPICS.issubset(registered_topics),
        "gdpr_status": gdpr_status,
        "all_webhooks": all_webhooks,
    }


# ── POST /webhooks/register ───────────────────────────────────────────────────

@router.post("/webhooks/register")
async def force_register_webhooks(shop: str = Query(...)):
    """
    Force (re-)registration of the 3 mandatory GDPR compliance webhooks.
    Use this for shops that installed before webhook registration was wired up,
    or after changing BACKEND_URL.
    """
    if not _valid_shop(shop):
        raise HTTPException(400, "Invalid shop domain")

    db = await get_db()
    tenant = await aw(db.tenants.find_one({"shop_domain": shop}))
    if not tenant:
        raise HTTPException(404, "Shop not installed — complete OAuth first")

    raw_token = tenant.get("access_token", "")
    if not raw_token:
        raise HTTPException(400, "No access token stored for this shop")

    access_token = decrypt_token(raw_token)

    results = await register_gdpr_webhooks(shop, access_token)

    all_ok = all(v in ("registered", "already_exists") for v in results.values())
    missing = [t for t, v in results.items() if v not in ("registered", "already_exists")]

    logger.info(f"{'✅' if all_ok else '❌'} Webhook re-registration for {shop}: {results}")

    return {
        "shop": shop,
        "results": results,
        "all_registered": all_ok,
        "missing": missing,
        "message": (
            "All 3 GDPR webhooks registered successfully"
            if all_ok
            else f"Failed topics: {missing} — check BACKEND_URL is a live public HTTPS URL"
        ),
    }