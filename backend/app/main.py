from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings

app = FastAPI(title="ShopIQ API", version="1.0.0")

# Sessions — must come before CORS
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SESSION_SECRET,
    max_age=86400,
     same_site="lax",  # Important for OAuth
    https_only=True,  # Must be True in production     # allows cross-port cookie sharing in dev
)

# CORS — allow all localhost ports used by Vite
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175",
        settings.APP_URL,
        "*"
    ],
    allow_credentials=True,    # required for cookies to be sent cross-origin
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=settings.LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)
logger.info("🚀 ShopIQ starting up...")

from app.routers import auth, audit
app.include_router(auth.router)
app.include_router(audit.router)

if settings.DEV_MODE:
    from app.dev.dev_router import router as dev_router
    app.include_router(dev_router)

@app.on_event("startup")
async def startup():
    if not settings.DEV_MODE:
        from app.dependencies import create_indexes
        await create_indexes()
    else:
        print("🛠  DEV MODE active — /dev/* routes enabled")
        print("   Frontend → http://localhost:5173 (or 5174)")
        print("   Click '⚡ Launch with mock data' to start")

@app.get("/health")
async def health():
    return {"status": "ok", "dev_mode": settings.DEV_MODE}