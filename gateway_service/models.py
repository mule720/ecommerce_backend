"""Gateway integration hardening models: audit, replay guard, idempotency and outbox."""
from django.db import models


class CallbackAuditLog(models.Model):
    STATUS_CHOICES = [
        ("accepted", "Accepted"),
        ("processed", "Processed"),
        ("rejected", "Rejected"),
        ("failed", "Failed"),
    ]

    source_system = models.CharField(max_length=30)
    event_type = models.CharField(max_length=80)
    idempotency_key = models.CharField(max_length=120)
    nonce = models.CharField(max_length=120, blank=True)
    callback_timestamp = models.BigIntegerField(default=0)
    signature_valid = models.BooleanField(default=False)
    token_valid = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="accepted")
    request_payload = models.JSONField(default=dict, blank=True)
    response_payload = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "gateway_callback_audit_logs"
        indexes = [
            models.Index(fields=["source_system", "event_type"]),
            models.Index(fields=["created_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["source_system", "idempotency_key"],
                name="uniq_callback_idempotency_per_source",
            )
        ]


class CallbackReplayGuard(models.Model):
    source_system = models.CharField(max_length=30)
    nonce = models.CharField(max_length=120)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "gateway_callback_replay_guard"
        constraints = [
            models.UniqueConstraint(
                fields=["source_system", "nonce"],
                name="uniq_callback_nonce_per_source",
            )
        ]


class CallbackOutbox(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("sent", "Sent"),
        ("failed", "Failed"),
        ("dead_letter", "Dead Letter"),
    ]

    destination_system = models.CharField(max_length=30)
    callback_url = models.URLField()
    event_type = models.CharField(max_length=80)
    payload = models.JSONField(default=dict, blank=True)
    idempotency_key = models.CharField(max_length=120, blank=True)
    trace_id = models.CharField(max_length=120, blank=True)
    attempts = models.IntegerField(default=0)
    max_attempts = models.IntegerField(default=3)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    next_attempt_at = models.DateTimeField(null=True, blank=True)
    last_response_code = models.IntegerField(null=True, blank=True)
    last_response_body = models.TextField(blank=True)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "gateway_callback_outbox"
        indexes = [
            models.Index(fields=["status", "next_attempt_at"]),
            models.Index(fields=["created_at"]),
        ]
