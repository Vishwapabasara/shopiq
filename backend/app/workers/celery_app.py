import logging
from celery import Celery
from app.config import settings

# Configure logging
logger = logging.getLogger(__name__)

# Print for debugging during module load
print("=" * 60)
print("🔧 CELERY APP INITIALIZATION")
print(f"📡 Broker URL: {settings.REDIS_URL[:30]}..." if settings.REDIS_URL else "❌ NO REDIS_URL")
print(f"📡 Backend URL: {settings.REDIS_URL[:30]}..." if settings.REDIS_URL else "❌ NO REDIS_URL")
print("=" * 60)

# Create Celery app
celery_app = Celery(
    "shopiq",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.workers.audit_worker",
        "app.workers.returns_worker",
        "app.workers.stock_worker",
        "app.workers.price_worker",
    ],
)

# Celery configuration
celery_app.conf.update(
    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    
    # Timezone
    timezone="UTC",
    enable_utc=True,
    
    # Task tracking
    task_track_started=True,
    task_send_sent_event=True,  # ✅ Log when tasks are sent
    
    # Reliability
    task_acks_late=True,  # Only ack after completion
    worker_prefetch_multiplier=1,  # One task at a time per worker
    result_expires=86400,  # Results kept for 24 hours
    
    # Logging
    worker_log_format='[%(asctime)s: %(levelname)s/%(processName)s] %(message)s',
    worker_task_log_format='[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s',
    
    # Connection retry
    broker_connection_retry_on_startup=True,
    
    # Beat schedule for monthly auto-audits
    beat_schedule={
        "monthly-auto-audit": {
            "task": "app.workers.audit_worker.run_scheduled_audits",
            "schedule": 60 * 60 * 24 * 30,  # every 30 days
        }
    },
)

logger.info("✅ Celery app configured successfully")