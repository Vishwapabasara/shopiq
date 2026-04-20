import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from app.routers import auth, audit, billing, webhooks  # Add webhooks

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
from app.routers import auth, audit, billing
app.include_router(auth.router)
app.include_router(audit.router)
app.include_router(billing.router)
app.include_router(webhooks.router)

if settings.DEV_MODE:
    from app.dev.dev_router import router as dev_router
    app.include_router(dev_router)

# 6. DEFINE ROUTES

@app.get("/", response_class=HTMLResponse)
async def root(request: Request, shop: str = None, embedded: str = None, host: str = None):
    """
    Root endpoint - handles Shopify embedded app and landing page
    """
    logger.info(f"🏠 Root accessed - shop: {shop}, embedded: {embedded}, host: {host}")
    logger.info(f"🍪 Session data: {dict(request.session) if hasattr(request, 'session') else 'No session'}")

    # Shopify embedded app access
    if shop and embedded == "1":
        from app.dependencies import get_db
        from app.services.session_manager import get_session_by_shop

        db = await get_db()

        # Check if shop has an active session
        session = await get_session_by_shop(shop)

        if session:
            # Shop is authenticated - load app
            logger.info(f"✅ Shop {shop} has active session, loading app")

            # Restore session to request cookie
            request.session["session_id"] = session["session_id"]
            request.session["shop_domain"] = session["shop_domain"]
            request.session["tenant_id"] = session["tenant_id"]

            return HTMLResponse(content=f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ShopIQ</title>
    <script src="https://unpkg.com/@shopify/app-bridge@3"></script>
</head>
<body>
    <div style="display:flex;justify-content:center;align-items:center;height:100vh;font-family:sans-serif">
        <div style="text-align:center">
            <h2>Loading ShopIQ...</h2>
            <p>Please wait...</p>
        </div>
    </div>

    <script>
        const shop = '{shop}';
        const host = '{host or ""}';
        const sessionId = '{session["session_id"]}';

        // Store session in localStorage for persistence
        localStorage.setItem('shopiq_session', sessionId);
        localStorage.setItem('shopiq_shop', shop);

        const AppBridge = window['app-bridge'];
        const createApp = AppBridge.default;
        const Redirect = AppBridge.actions.Redirect;

        const app = createApp({{
            apiKey: '{settings.SHOPIFY_API_KEY}',
            host: host || btoa(shop + '/admin'),
        }});

        const redirect = Redirect.create(app);
        redirect.dispatch(Redirect.Action.REMOTE, {{
            url: '{settings.FRONTEND_URL}/dashboard?shop=' + shop + '&session=' + sessionId,
            newContext: false
        }});
    </script>
</body>
</html>
            """)
        else:
            # Shop not authenticated - start OAuth flow
            logger.info(f"⚠️ Shop {shop} not authenticated, redirecting to OAuth")
            return HTMLResponse(content=f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>ShopIQ - Install</title>
</head>
<body>
    <div style="display:flex;justify-content:center;align-items:center;height:100vh;font-family:sans-serif">
        <div style="text-align:center">
            <h2>Installing ShopIQ...</h2>
            <p>Redirecting to authorization...</p>
        </div>
    </div>
    <script>
        window.location.href = '/auth/shopify/install?shop={shop}';
    </script>
</body>
</html>
            """)
    
    # Landing page for direct web access
    return HTMLResponse(content="""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ShopIQ - Shopify Product Auditor</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .container { text-align: center; max-width: 600px; padding: 2rem; }
        h1 { font-size: 3rem; margin-bottom: 1rem; }
        p { font-size: 1.2rem; margin-bottom: 2rem; opacity: 0.9; }
        .install-form {
            background: rgba(255,255,255,0.1);
            padding: 2rem;
            border-radius: 1rem;
            backdrop-filter: blur(10px);
        }
        .input-group { display: flex; gap: 0.5rem; margin-bottom: 1rem; }
        input {
            padding: 1rem;
            font-size: 1rem;
            border: none;
            border-radius: 0.5rem;
            flex: 1;
        }
        .suffix {
            padding: 1rem;
            background: rgba(255,255,255,0.2);
            border-radius: 0.5rem;
            font-size: 0.9rem;
            display: flex;
            align-items: center;
        }
        button {
            background: white;
            color: #667eea;
            padding: 1rem 2rem;
            font-size: 1rem;
            font-weight: bold;
            border: none;
            border-radius: 0.5rem;
            cursor: pointer;
            transition: transform 0.2s;
            width: 100%;
        }
        button:hover { transform: scale(1.02); }
        .error { color: #ff6b6b; margin-top: 0.5rem; font-size: 0.9rem; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 ShopIQ</h1>
        <p>AI-powered product auditing for Shopify stores</p>
        
        <div class="install-form">
            <h2 style="margin-bottom: 1.5rem;">Install on your store</h2>
            <div class="input-group">
                <input 
                    type="text" 
                    id="shop-input" 
                    placeholder="your-store"
                />
                <span class="suffix">.myshopify.com</span>
            </div>
            <button onclick="install()">Install App</button>
            <div id="error" class="error"></div>
        </div>
    </div>
    
    <script>
        function install() {
            const input = document.getElementById('shop-input');
            const errorDiv = document.getElementById('error');
            const shop = input.value.trim();
            
            errorDiv.textContent = '';
            
            if (!shop) {
                errorDiv.textContent = 'Please enter your shop name';
                return;
            }
            
            if (!/^[a-zA-Z0-9][a-zA-Z0-9\\-]*$/.test(shop)) {
                errorDiv.textContent = 'Invalid shop name. Use only letters, numbers, and hyphens.';
                return;
            }
            
            const formattedShop = shop.toLowerCase() + '.myshopify.com';
            window.location.href = '/auth/shopify/install?shop=' + formattedShop;
        }
        
        document.getElementById('shop-input').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') install();
        });
    </script>
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