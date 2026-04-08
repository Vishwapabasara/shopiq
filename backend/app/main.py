import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings

# 1. CREATE APP FIRST
app = FastAPI(title="ShopIQ API", version="1.0.0")

# 2. ADD MIDDLEWARE
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SESSION_SECRET,
    max_age=86400,
    same_site="lax",
    https_only=True,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175",
        "https://shopiq-iota.vercel.app",
        settings.APP_URL,
        "*"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. CONFIGURE LOGGING
logging.basicConfig(
    level=settings.LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)
logger.info("🚀 ShopIQ starting up...")

# 4. INCLUDE ROUTERS
from app.routers import auth, audit
app.include_router(auth.router)
app.include_router(audit.router)

if settings.DEV_MODE:
    from app.dev.dev_router import router as dev_router
    app.include_router(dev_router)

# 5. NOW ADD ROUTES (after app is created!)
@app.get("/", response_class=HTMLResponse)
async def root(shop: str = None, embedded: str = None, host: str = None):
    """
    Root endpoint - Shopify embedded app entry point
    """
    logger.info(f"🏠 Root accessed - shop: {shop}, embedded: {embedded}")
    
    if shop and embedded == "1":
        # Embedded in Shopify admin
        from app.dependencies import get_db
        from app.routers.auth import aw
        
        db = await get_db()
        tenant = await aw(db.tenants.find_one({"shop_domain": shop}))
        
        if tenant:
            # Shop is installed - use App Bridge to navigate
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
        
        // Use Shopify App Bridge to redirect
        const AppBridge = window['app-bridge'];
        const createApp = AppBridge.default;
        const Redirect = AppBridge.actions.Redirect;
        
        const app = createApp({{
            apiKey: '{settings.SHOPIFY_API_KEY}',
            host: host || btoa(shop + '/admin'),
        }});
        
        const redirect = Redirect.create(app);
        
        // Redirect to external frontend
        redirect.dispatch(Redirect.Action.REMOTE, {{
            url: 'https://shopiq-iota.vercel.app/dashboard?shop=' + shop,
            newContext: true
        }});
    </script>
</body>
</html>
            """)
        else:
            # Not installed - start OAuth
            logger.info(f"⚠️ Shop {shop} not installed")
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
    
    # Not embedded - show landing page
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
            
            // Validate shop name
            if (!/^[a-zA-Z0-9][a-zA-Z0-9\-]*$/.test(shop)) {
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
    return {"status": "ok", "dev_mode": settings.DEV_MODE}


@app.on_event("startup")
async def startup():
    if not settings.DEV_MODE:
        from app.dependencies import create_indexes
        await create_indexes()
    else:
        print("🛠  DEV MODE active — /dev/* routes enabled")
        print("   Frontend → http://localhost:5173 (or 5174)")
        print("   Click '⚡ Launch with mock data' to start")