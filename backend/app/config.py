from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Shopify
    SHOPIFY_API_KEY: str = ""
    SHOPIFY_API_SECRET: str = ""
    # In app/config.py
    SHOPIFY_SCOPES: str = "read_products,read_inventory,read_orders,read_collections"

    # App
    APP_URL: str = "http://localhost:8000"
    SESSION_SECRET: str = "dev-secret-replace-in-production"

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
