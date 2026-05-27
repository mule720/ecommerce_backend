"""Security and reliability helpers for integration callbacks."""
import hashlib
import hmac
import json
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError
from django.utils import timezone

from gateway_service.models import CallbackAuditLog, CallbackReplayGuard, CallbackOutbox


def parse_payload(value):
    if isinstance(value, (dict, list)):
        return value
    if value in (None, ""):
        return {}
    if isinstance(value, str):
        return json.loads(value)
    return value


def source_hmac_secret(source_system: str) -> str:
    source_map = {
        "payment": getattr(settings, "PAYMENT_SYSTEM_HMAC_SECRET", ""),
        "shipping": getattr(settings, "SHIPPING_SYSTEM_HMAC_SECRET", ""),
        "erp": getattr(settings, "ERP_SYSTEM_HMAC_SECRET", ""),
    }
    return source_map.get(source_system, "") or getattr(settings, "INTEGRATION_HMAC_SECRET", "")


def _canonical(event_type: str, payload: dict, timestamp: int, nonce: str, idempotency_key: str) -> str:
    body = json.dumps(payload or {}, sort_keys=True, separators=(",", ":"))
    return f"{event_type}.{timestamp}.{nonce}.{idempotency_key}.{body}"


def verify_signature(source_system: str, event_type: str, payload: dict, timestamp: int, nonce: str, idempotency_key: str, signature: str) -> bool:
    secret = source_hmac_secret(source_system)
    if not secret:
        return False
    msg = _canonical(event_type, payload, timestamp, nonce, idempotency_key).encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, (signature or "").strip())


def validate_timestamp(timestamp: int) -> bool:
    max_skew = int(getattr(settings, "CALLBACK_MAX_SKEW_SECONDS", 300))
    now_ts = int(timezone.now().timestamp())
    return abs(now_ts - int(timestamp)) <= max_skew


def is_replayed_nonce(source_system: str, nonce: str) -> bool:
    if not nonce:
        return True
    now = timezone.now()
    CallbackReplayGuard.objects.filter(expires_at__lt=now).delete()
    ttl = int(getattr(settings, "CALLBACK_NONCE_TTL_SECONDS", 600))
    try:
        CallbackReplayGuard.objects.create(
            source_system=source_system,
            nonce=nonce,
            expires_at=now + timedelta(seconds=ttl),
        )
        return False
    except IntegrityError:
        return True


def integration_token_valid(token: str) -> bool:
    expected = getattr(settings, "INTEGRATION_SHARED_TOKEN", "")
    return (not expected) or (token == expected)


def get_or_create_audit(source_system: str, event_type: str, idempotency_key: str, payload: dict, nonce: str, callback_timestamp: int):
    existing = CallbackAuditLog.objects.filter(
        source_system=source_system,
        idempotency_key=idempotency_key,
    ).first()
    if existing:
        same = existing.event_type == event_type and existing.request_payload == (payload or {})
        return existing, True, same

    audit = CallbackAuditLog.objects.create(
        source_system=source_system,
        event_type=event_type,
        idempotency_key=idempotency_key,
        nonce=nonce or "",
        callback_timestamp=callback_timestamp or 0,
        request_payload=payload or {},
        status="accepted",
    )
    return audit, False, True


def mark_audit(audit: CallbackAuditLog, status: str, response_payload=None, error_message: str = "", signature_valid=None, token_valid=None):
    if audit is None:
        return
    audit.status = status
    if response_payload is not None:
        audit.response_payload = response_payload
    if error_message:
        audit.error_message = error_message
    if signature_valid is not None:
        audit.signature_valid = signature_valid
    if token_valid is not None:
        audit.token_valid = token_valid
    if status in {"processed", "rejected", "failed"}:
        audit.processed_at = timezone.now()
    audit.save()


def enqueue_outbox(destination_system: str, callback_url: str, event_type: str, payload: dict, trace_id: str = "", idempotency_key: str = ""):
    return CallbackOutbox.objects.create(
        destination_system=destination_system,
        callback_url=callback_url,
        event_type=event_type,
        payload=payload or {},
        trace_id=trace_id or "",
        idempotency_key=idempotency_key or str(uuid.uuid4()),
        next_attempt_at=timezone.now(),
        max_attempts=int(getattr(settings, "CALLBACK_OUTBOX_MAX_ATTEMPTS", 3)),
    )
