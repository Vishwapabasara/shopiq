from celery import Celery
from app.config import settings

celery_app = Celery(
    "shopiq",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.workers.audit_worker"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,                    # Only ack after completion
    worker_prefetch_multiplier=1,           # One task at a time per worker
    result_expires=86400,                   # Results kept for 24 hours

    # Beat schedule for monthly auto-audits
    beat_schedule={
        "monthly-auto-audit": {
            "task": "app.workers.audit_worker.run_scheduled_audits",
            "schedule": 60 * 60 * 24 * 30,  # every 30 days
        }
    },
)
