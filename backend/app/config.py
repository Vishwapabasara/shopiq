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
    SESSION_SECRET: str = "dev-secret-replace-in-production"
    FRONTEND_URL: str = "https://shopiq-iota.vercel.app"

    # MongoDB
    MONGO_URI: str = "mongodb://localhost:27017/shopiq"

    # Redis / Celery
    REDIS_URL: str = "redis://localhost:6379/0"

    # OpenAI
    GEMINI_API_KEY: str = "AIzaSyDdiCcgA5reJd8bkZudLLnpOel7WuuC_m4"

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
        "audits_per_month": 6,
        "max_products": 50,
        "features": [
            "6 audits per month",
            "Up to 50 products",
            "Basic scoring",
            "Email support"
        ]
    },
    "starter": {
        "name": "Starter",
        "price": 0,
        "audits_per_month": 6,
        "max_products": 50,
        "features": [
            "6 audits per month",
            "Up to 50 products",
            "Basic scoring",
            "Email support"
        ]
    },
    "pro": {
        "name": "Professional",
        "price": 29.00,
        "interval": "EVERY_30_DAYS",
        "audits_per_month": 50,
        "max_products": 1000,
        "trial_days": 7,
        "features": [
            "50 audits per month",
            "Up to 1,000 products",
            "AI-powered scoring",
            "Email notifications",
            "Scheduled audits",
            "Priority support",
            "Product detail analysis"
        ]
    },
    "enterprise": {
        "name": "Enterprise",
        "price": 99.00,
        "interval": "EVERY_30_DAYS",
        "audits_per_month": -1,
        "max_products": -1,
        "trial_days": 14,
        "features": [
            "Unlimited audits",
            "Unlimited products",
            "AI-powered scoring",
            "Scheduled audits (weekly/daily)",
            "White-label PDF reports",
            "API access",
            "Dedicated support",
            "Custom integrations"
        ]
    }
}
