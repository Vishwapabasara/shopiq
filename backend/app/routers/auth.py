import hashlib
import hmac
import secrets
import urllib.parse
import re
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
    if not _valid_shop(shop):
        raise HTTPException(400, "Invalid shop domain")
    state = secrets.token_urlsafe(32)
    request.session["oauth_state"] = state
    request.session["oauth_shop"] = shop
    params = {
        "client_id": settings.SHOPIFY_API_KEY,
        "scope": settings.SHOPIFY_SCOPES,
        "redirect_uri": f"{settings.APP_URL}/auth/shopify/callback",
        "state": state,
    }
    auth_url = f"https://{shop}/admin/oauth/authorize?" + urllib.parse.urlencode(params)
    return RedirectResponse(url=auth_url, status_code=302)


@router.get("/shopify/callback")
async def callback(
    request: Request,
    shop: str = Query(...),
    code: str = Query(...),
    state: str = Query(...),
    hmac: str = Query(...),
):
    if state != request.session.get("oauth_state"):
        raise HTTPException(403, "State mismatch — possible CSRF")
    if not _valid_shop(shop):
        raise HTTPException(400, "Invalid shop domain")
    if not _verify_hmac(dict(request.query_params), settings.SHOPIFY_API_SECRET):
        raise HTTPException(403, "HMAC verification failed")

    async with httpx.AsyncClient() as client:
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

    shop_info = {}
    try:
        shop_info = await get_shop_info(shop, access_token)
    except Exception:
        pass

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

    request.session["shop"] = shop
    request.session.pop("oauth_state", None)
    request.session.pop("oauth_shop", None)
    return RedirectResponse(url=f"{settings.APP_URL}/dashboard", status_code=302)


@router.get("/me")
async def me(request: Request):
    shop = request.session.get("shop")
    if not shop:
        return {"authenticated": False}
    db = await get_db()
    tenant = await aw(db.tenants.find_one({"shop_domain": shop}, {"access_token": 0}))
    if not tenant:
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
    request.session.clear()
    return {"ok": True}
