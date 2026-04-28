from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Shopify
    SHOPIFY_API_KEY: str = ""
    SHOPIFY_API_SECRET: str = ""
    # In app/config.py
    SHOPIFY_SCOPES: str = "read_products,write_products,read_orders,read_inventory"

    # App
    APP_URL: str = "http://localhost:8000"
    BACKEND_URL: str = ""  # Public HTTPS URL Shopify uses for webhook callbacks; falls back to APP_URL
    SESSION_SECRET: str = "dev-secret-replace-in-production"
    FRONTEND_URL: str = "https://shopiq-iota.vercel.app"

    # MongoDB
    MONGO_URI: str = "mongodb://localhost:27017/shopiq"

    # Redis / Celery
    REDIS_URL: str = "redis://localhost:6379/0"

    # OpenAI / Gemini
    GEMINI_API_KEY: str = "AIzaSyDdiCcgA5reJd8bkZudLLnpOel7WuuC_m4"

    # SerpAPI — used by PricePulse for Google Shopping competitor discovery
    SERPAPI_KEY: str = ""

    # Encryption
    TOKEN_ENCRYPTION_KEY: str = ""

    # SendGrid
    SENDGRID_API_KEY: str = ""
    FROM_EMAIL: str = "noreply@shopiq.app"

    # AWS S3
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    S3_BUCKET: str = "shopiq-reports"

    # Stripe
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""

    # Dev mode — set to false in production
    DEV_MODE: bool = False

    # Set to False to bypass Shopify billing (manual DB upgrades only).
    # Required when app is a Custom App (not a Partners app) — custom apps
    # cannot call appSubscriptionCreate. Set BILLING_ENABLED=true once the
    # app is migrated to the Shopify Partners dashboard.
    BILLING_ENABLED: bool = False

    # Admin panel credentials — set both in env vars to enable admin access
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = ""

    # Logging
    LOG_LEVEL: str = "INFO"

     # Celery configuration
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

PLANS = {
    "free": {
        "name": "Free",
        "price": 0,
        # Monthly action limits (-1 = unlimited)
        "audits_per_month": 10,
        "copy_generations_per_month": 10,
        "ai_fixes_per_month": 10,
        "exports_per_month": 10,
        "scheduled_checks_per_month": 0,
        # Products scanned per audit run (0 = full scan)
        "audit_batch_size": 10,
        # Audit history entries shown
        "history_audits": 1,
        "features": [
            "10 audits per month",
            "10 products scanned per audit (rotating batch)",
            "10 AI copy generations per month",
            "Basic score dashboard",
            "Latest audit only",
        ],
    },
    "pro": {
        "name": "Pro",
        "price": 29.00,
        "interval": "EVERY_30_DAYS",
        "trial_days": 7,
        "audits_per_month": 100,
        "copy_generations_per_month": 200,
        "ai_fixes_per_month": 200,
        "exports_per_month": 100,
        "scheduled_checks_per_month": 100,
        "audit_batch_size": 0,
        "history_audits": -1,
        "features": [
            "100 audits per month",
            "Full product scan per audit",
            "200 AI copy generations per month",
            "200 AI fixes per month",
            "Full audit history & charts",
            "Product filtering & sorting",
            "Scheduled monitoring",
            "Export reports",
            "Priority support",
        ],
    },
    "enterprise": {
        "name": "Enterprise",
        "price": 199.00,
        "interval": "EVERY_30_DAYS",
        "trial_days": 14,
        "audits_per_month": -1,
        "copy_generations_per_month": -1,
        "ai_fixes_per_month": -1,
        "exports_per_month": -1,
        "scheduled_checks_per_month": -1,
        "audit_batch_size": 0,
        "history_audits": -1,
        "features": [
            "Unlimited audits",
            "Unlimited AI copy generations",
            "Unlimited AI fixes",
            "Multi-store support",
            "Team & user access",
            "Priority processing queue",
            "Custom reporting & PDF exports",
            "API & webhook access",
            "Dedicated support",
        ],
    },
}
