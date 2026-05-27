"""Celery application for e-commerce backend."""
import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ecom_backend.settings")

app = Celery("ecom_backend", include=["ecom_backend.event_subscribers"])
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    """Simple debug task."""
    print(f"Request: {self.request!r}")
