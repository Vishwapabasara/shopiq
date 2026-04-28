import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from app.routers import auth, audit, billing, webhooks, returns, stock, price, copy, reviews, account, admin

from app.config import settings

# 1. CREATE APP FIRST
app = FastAPI(title="ShopIQ API", version="1.0.0")

# 2. ADD SESSION MIDDLEWARE
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SESSION_SECRET,
    max_age=86400 * 30,
    same_site="none",
    https_only=True,
    session_cookie="shopiq_session",
)

# 3. ADD CORS MIDDLEWARE
# CORS middleware
allowed_origins = [
    "https://shopiq-iota.vercel.app",
    "https://shopiq-production.up.railway.app",
    "https://admin.shopify.com",
]

# Add FRONTEND_URL if it's set and different
if settings.FRONTEND_URL and settings.FRONTEND_URL not in allowed_origins:
    allowed_origins.append(settings.FRONTEND_URL)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Set-Cookie"],
)

# 4. CONFIGURE LOGGING
logging.basicConfig(
    level=settings.LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)
logger.info("🚀 ShopIQ starting up...")

# 5. INCLUDE ROUTERS
app.include_router(auth.router)
app.include_router(audit.router)
app.include_router(billing.router)
app.include_router(webhooks.router)
app.include_router(returns.router)
app.include_router(stock.router)
app.include_router(price.router)
app.include_router(copy.router)
app.include_router(reviews.router)
app.include_router(account.router)
app.include_router(admin.router)

if settings.DEV_MODE:
    from app.dev.dev_router import router as dev_router
    app.include_router(dev_router)

# 6. DEFINE ROUTES

@app.get("/")
async def root(request: Request, shop: str = None, embedded: str = None, host: str = None):
    """
    Root endpoint - handles Shopify embedded app and landing page.
    Uses HTTP 302 redirects (not JS redirects) so the browser lands on
    the final URL in one step — App Bridge CDN needs ?shop=&host= to be
    present on the very first page parse, before any JS runs.
    """
    logger.info(f"🏠 Root accessed - shop: {shop}, embedded: {embedded}, host: {host}")

    # Shopify embedded app access
    if shop and embedded == "1":
        from app.services.session_manager import get_session_by_shop

        session = await get_session_by_shop(shop)

        if session:
            logger.info(f"✅ Shop {shop} has active session, redirecting to app")

            # Refresh the server-side session into the cookie so the React
            # frontend can authenticate via cookie on its first /auth/me call.
            request.session["session_id"] = session["session_id"]
            request.session["shop_domain"] = session["shop_domain"]
            request.session["tenant_id"] = session["tenant_id"]

            # HTTP 302 → browser goes straight to the React SPA with the
            # required App Bridge params already in the URL.
            frontend_url = f"{settings.FRONTEND_URL}/dashboard?shop={shop}&host={host or ''}"
            return RedirectResponse(url=frontend_url, status_code=302)
        else:
            logger.info(f"⚠️ Shop {shop} not authenticated, starting OAuth")
            return RedirectResponse(url=f"/auth/shopify/install?shop={shop}", status_code=302)
    
    # Landing page for direct web access.
    # Installation must be initiated from the Shopify App Store — no manual
    # shop-domain entry is allowed per Shopify App Store requirements.
    # TODO: replace the href below with the live Shopify App Store listing URL.
    app_store_url = "https://apps.shopify.com/shopiq"
    return HTMLResponse(content=f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ShopIQ - Shopify Product Auditor</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }}
        .container {{ text-align: center; max-width: 560px; padding: 2rem; }}
        h1 {{ font-size: 3rem; margin-bottom: 1rem; }}
        p {{ font-size: 1.2rem; margin-bottom: 2rem; opacity: 0.9; }}
        .card {{
            background: rgba(255,255,255,0.1);
            padding: 2rem;
            border-radius: 1rem;
            backdrop-filter: blur(10px);
        }}
        .btn {{
            display: inline-block;
            background: white;
            color: #667eea;
            padding: 1rem 2rem;
            font-size: 1rem;
            font-weight: bold;
            border-radius: 0.5rem;
            text-decoration: none;
            transition: transform 0.2s;
        }}
        .btn:hover {{ transform: scale(1.02); }}
        .note {{ margin-top: 1rem; font-size: 0.85rem; opacity: 0.75; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>ShopIQ</h1>
        <p>AI-powered product auditing for Shopify stores</p>
        <div class="card">
            <p style="margin-bottom:1.5rem;">Install ShopIQ directly from the Shopify App Store.</p>
            <a class="btn" href="{app_store_url}">Add app on Shopify</a>
            <p class="note">You will be guided through authorisation on the next screen.</p>
        </div>
    </div>
</body>
</html>
    """)


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "ok", "dev_mode": settings.DEV_MODE}


@app.on_event("startup")
async def startup():
    """Startup event handler"""
    if not settings.DEV_MODE:
        from app.dependencies import create_indexes
        await create_indexes()
        logger.info("✅ Production mode - indexes created")
    else:
        logger.info("🛠  DEV MODE active — /dev/* routes enabled")
        logger.info("   Frontend → http://localhost:5173")