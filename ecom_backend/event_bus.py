"""Shared event bus publisher utilities for E-commerce service."""
import uuid
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from celery import current_app
from django.conf import settings

logger = logging.getLogger(__name__)


def build_event_envelope(
    event_type: str,
    payload: Dict[str, Any],
    trace_id: Optional[str] = None,
    source: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a standard cross-system event envelope."""
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "event_version": "1.0",
        "source": source or getattr(settings, "SYSTEM_NAME", "ecommerce"),
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "trace_id": trace_id or str(uuid.uuid4()),
        "payload": payload,
    }


def publish_event(
    target_queue: str,
    event_type: str,
    payload: Dict[str, Any],
    trace_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Publish an event to a target queue in RabbitMQ via Celery."""
    event = build_event_envelope(event_type=event_type, payload=payload, trace_id=trace_id)
    try:
        current_app.send_task(
            "event_bus.consume_event",
            args=[event],
            queue=target_queue,
        )
        logger.info("Published event=%s to queue=%s", event_type, target_queue)
    except Exception as exc:
        # Keep checkout/order APIs working even when broker is down.
        # Event publishing is best-effort for local/dev until infra is ready.
        logger.warning(
            "Event publish skipped (queue=%s, event=%s): %s",
            target_queue,
            event_type,
            exc,
        )
    return event
