import os
from celery import Celery

broker_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
celery_app = Celery("personal_os_worker", broker=broker_url)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)
