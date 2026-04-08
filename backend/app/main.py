from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
import logging

logger = logging.getLogger(__name__)

# ... existing middleware setup ...

@app.get("/", response_class=HTMLResponse)
async def root(request: Request, shop: str = None, embedded: str = None):
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
            # Shop is installed, load the embedded app
            return HTMLResponse(content=f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ShopIQ</title>
    <script src="https://cdn.shopify.com/shopifycloud/app-bridge.js"></script>
</head>
<body>
    <div id="app-loading" style="display: flex; justify-content: center; align-items: center; height: 100vh; font-family: sans-serif;">
        <div style="text-align: center;">
            <h2>Loading ShopIQ...</h2>
            <p>Redirecting to dashboard...</p>
        </div>
    </div>
    
    <script>
        // Redirect to frontend
        const shop = '{shop}';
        window.top.location.href = 'https://shopiq-iota.vercel.app/dashboard?shop=' + shop;
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
        
        // Allow Enter key to submit
        document.getElementById('shop-input').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') install();
        });
    </script>
</body>
</html>
    """)

# Keep your existing health endpoint
@app.get("/health")
async def health():
    return {"status": "ok", "dev_mode": settings.DEV_MODE}