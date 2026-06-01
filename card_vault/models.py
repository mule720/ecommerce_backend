"""
Card Vault Models
=================
PCI DSS compliant card storage and immutable audit trail.

PCI DSS requirements:
  Req 3.4   — PAN stored encrypted (AES-256-GCM via crypto.py)
  Req 3.2.1 — CVV never stored (enforced in schema.py tokenize mutation)
  Req 10    — All payment operations logged in PaymentAuditLog (immutable)
"""
from django.db import models
from django.conf import settings


class CardVaultEntry(models.Model):
    """
    One tokenized card per row.
    The vault token is the only reference passed between services.
    The encrypted PAN is decrypted only inside the payment processor,
    briefly, in memory — it is never logged or returned to the API.
    """

    token     = models.CharField(max_length=64, unique=True, db_index=True)
    customer  = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='vault_cards'
    )

    # Display-safe (non-sensitive) fields
    pan_last_four = models.CharField(max_length=4)
    pan_bin       = models.CharField(max_length=8)   # First 6-8 digits, used for BIN routing
    card_brand    = models.CharField(max_length=20, default='unknown')

    # Encrypted sensitive fields (AES-256-GCM, never in plaintext at rest)
    encrypted_pan             = models.TextField()
    encrypted_expiry          = models.TextField()   # stored as "MM/YYYY"
    encrypted_cardholder_name = models.TextField()
    # CVV is NEVER stored — validated transiently then discarded

    is_default  = models.BooleanField(default=False)
    is_active   = models.BooleanField(default=True)
    key_version = models.IntegerField(default=1)     # incremented on key rotation

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'card_vault'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.card_brand.title()} **** {self.pan_last_four} (customer={self.customer_id})"


class PaymentAuditLog(models.Model):
    """
    Append-only audit trail for every payment operation (PCI DSS Req 10).
    Records are immutable — the save() override rejects any update attempt.
    """

    class Action(models.TextChoices):
        CARD_TOKENIZED    = 'card_tokenized',    'Card Tokenized'
        CARD_USED         = 'card_used',         'Card Used for Payment'
        CARD_DELETED      = 'card_deleted',      'Card Deleted'
        PAYMENT_INITIATED = 'payment_initiated', 'Payment Initiated'
        PAYMENT_COMPLETED = 'payment_completed', 'Payment Completed'
        PAYMENT_FAILED    = 'payment_failed',    'Payment Failed'
        REFUND_REQUESTED  = 'refund_requested',  'Refund Requested'
        WALLET_CREDITED   = 'wallet_credited',   'Wallet Credited'
        WALLET_DEBITED    = 'wallet_debited',    'Wallet Debited'
        PAYOUT_DISPATCHED = 'payout_dispatched', 'Vendor Payout Dispatched'

    action        = models.CharField(max_length=50, choices=Action.choices)
    actor         = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='payment_audit_logs'
    )
    resource_type = models.CharField(max_length=50, blank=True)
    resource_id   = models.CharField(max_length=100, blank=True)
    ip_address    = models.GenericIPAddressField(null=True, blank=True)
    metadata      = models.JSONField(default=dict, blank=True)
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'payment_audit_log'
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError('PaymentAuditLog records are immutable and cannot be updated.')
        super().save(*args, **kwargs)

    def __str__(self):
        return f'[{self.created_at}] {self.action} actor={self.actor_id}'
