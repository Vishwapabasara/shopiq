import jwt
from fastapi import Request, HTTPException
from app.config import settings
from app.dependencies import get_db


async def get_current_tenant_from_session_token(request: Request):
    authorization = request.headers.get("authorization", "")

    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing Shopify session token")

    token = authorization.split(" ", 1)[1]

    try:
        payload = jwt.decode(
            token,
            settings.SHOPIFY_API_SECRET,
            algorithms=["HS256"],
            audience=settings.SHOPIFY_API_KEY,
            options={"verify_exp": True},
        )
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid Shopify session token: {str(e)}")

    dest = payload.get("dest", "")
    shop = dest.replace("https://", "").replace("http://", "").strip("/")

    if not shop.endswith(".myshopify.com"):
        raise HTTPException(status_code=401, detail="Invalid shop in session token")

    db = await get_db()
    tenant = await db.tenants.find_one({"shop_domain": shop})

    if not tenant:
        raise HTTPException(status_code=401, detail="Shop not installed")

    return tenant