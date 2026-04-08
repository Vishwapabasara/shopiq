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
    Root endpoint - handles embedded app loading from Shopify admin
    """
    logger.info(f"🏠 Root accessed - shop: {shop}, embedded: {embedded}")
    
    # If accessed from Shopify admin (embedded mode)
    if shop and embedded == "1":
        # Check if shop is installed
        from app.dependencies import get_db
        from app.routers.auth import aw
        
        db = await get_db()
        tenant = await aw(db.tenants.find_one({"shop_domain": shop}))
        
        if tenant:
            # Shop is installed, redirect to frontend
            return HTMLResponse(content=f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ShopIQ</title>
</head>
<body style="margin:0;padding:0">
    <div style="display:flex;justify-content:center;align-items:center;height:100vh;font-family:sans-serif">
        <div style="text-align:center">
            <h2>Loading ShopIQ...</h2>
            <p>Redirecting to dashboard...</p>
        </div>
    </div>
    
    <script>
        window.top.location.href = 'https://shopiq-iota.vercel.app/dashboard?shop={shop}';
    </script>
</body>
</html>
            """)
        else:
            # Shop not installed, redirect to OAuth
            logger.info(f"⚠️ Shop {shop} not installed, redirecting to OAuth")
            return RedirectResponse(url=f"/auth/shopify/install?shop={shop}")
    
    # Regular web access (not embedded)
    return HTMLResponse(content="""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ShopIQ - Shopify Product Auditor</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .container {
            text-align: center;
            max-width: 600px;
            padding: 2rem;
        }
        h1 { font-size: 3rem; margin-bottom: 1rem; }
        p { font-size: 1.2rem; margin-bottom: 2rem; opacity: 0.9; }
        .install-form {
            background: rgba(255,255,255,0.1);
            padding: 2rem;
            border-radius: 1rem;
            backdrop-filter: blur(10px);
        }
        input {
            padding: 1rem;
            font-size: 1rem;
            border: none;
            border-radius: 0.5rem;
            width: 100%;
            max-width: 300px;
            margin-bottom: 1rem;
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
        }
        button:hover { transform: scale(1.05); }
    </style>
</head>
<body>
    <div class="container">
        <h1>ShopIQ</h1>
        <p>AI-powered product auditing for Shopify stores</p>
        
        <div class="install-form">
            <h2>Install on your store</h2>
            <input 
                type="text" 
                id="shop-input" 
                placeholder="your-store.myshopify.com"
            />
            <br>
            <button onclick="install()">Install App</button>
        </div>
    </div>
    
    <script>
        function install() {
            const shop = document.getElementById('shop-input').value.trim();
            if (!shop) {
                alert('Please enter your shop domain');
                return;
            }
            
            let formattedShop = shop.toLowerCase();
            if (!formattedShop.includes('.myshopify.com')) {
                formattedShop = formattedShop + '.myshopify.com';
            }
            
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