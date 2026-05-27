"""
Payment Service Models
Multi-vendor e-commerce payment management
"""
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from decimal import Decimal


class Payment(models.Model):
    """Payment model for orders"""

    class PaymentMethod(models.TextChoices):
        CREDIT_CARD = 'credit_card', _('Credit Card')
        DEBIT_CARD  = 'debit_card',  _('Debit Card')
        PAYPAL      = 'paypal',      _('PayPal')
        STRIPE      = 'stripe',      _('Stripe')
        BANK_TRANSFER    = 'bank_transfer',    _('Bank Transfer')
        MOBILE_MONEY     = 'mobile_money',     _('Mobile Money')
        CASH_ON_DELIVERY = 'cash_on_delivery', _('Cash on Delivery')
        WALLET = 'wallet', _('Wallet')

    class PaymentStatus(models.TextChoices):
        PENDING    = 'pending',    _('Pending')
        PROCESSING = 'processing', _('Processing')
        COMPLETED  = 'completed',  _('Completed')
        FAILED     = 'failed',     _('Failed')
        REFUNDED   = 'refunded',   _('Refunded')
        CANCELLED  = 'cancelled',  _('Cancelled')

    order    = models.ForeignKey('order_service.Order', on_delete=models.CASCADE, related_name='payments')
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='payments')
    amount   = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='ZMW')
    method   = models.CharField(max_length=30, choices=PaymentMethod.choices)
    status   = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
    transaction_id           = models.CharField(max_length=100, unique=True, blank=True)
    payment_gateway_response = models.JSONField(default=dict, blank=True)
    gateway_name             = models.CharField(max_length=50, blank=True)
    gateway_transaction_id   = models.CharField(max_length=100, blank=True)
    payment_system_reference = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payments'
        ordering = ['-created_at']

    def __str__(self):
        return f"Payment {self.transaction_id} — {self.amount} {self.currency}"


class Refund(models.Model):
    class RefundStatus(models.TextChoices):
        PENDING    = 'pending',    _('Pending')
        PROCESSING = 'processing', _('Processing')
        COMPLETED  = 'completed',  _('Completed')
        FAILED     = 'failed',     _('Failed')

    payment        = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name='refunds')
    order          = models.ForeignKey('order_service.Order', on_delete=models.CASCADE, related_name='refunds')
    amount         = models.DecimalField(max_digits=12, decimal_places=2)
    reason         = models.TextField()
    status         = models.CharField(max_length=20, choices=RefundStatus.choices, default=RefundStatus.PENDING)
    transaction_id = models.CharField(max_length=100, unique=True)
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'refunds'
        ordering = ['-created_at']


class SavedPaymentMethod(models.Model):
    """Saved payment methods for customers"""
    customer      = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='payment_methods')
    type          = models.CharField(max_length=50)
    last_four     = models.CharField(max_length=4)
    brand         = models.CharField(max_length=50, blank=True)
    expiry_month  = models.IntegerField()
    expiry_year   = models.IntegerField()
    is_default    = models.BooleanField(default=False)
    gateway_token = models.CharField(max_length=100)
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'customer_payment_methods'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.brand} **** {self.last_four}"


# ─────────────────────────────────────────────────────────────────────────────
# Vendor Payment Terms  —  admin-configurable per vendor
# ─────────────────────────────────────────────────────────────────────────────

class VendorPaymentTerms(models.Model):
    """
    Admin sets the payment terms for each vendor.

    Fields the admin controls:
      payout_period          — instant / daily / weekly / monthly
      payout_day             — weekday (0–6) or day-of-month (1–28)
      platform_fee_percentage — platform cut before crediting wallet
      min_payout_amount      — minimum pending balance needed to fire a batch
      currency               — payout currency
    """

    PAYOUT_PERIOD_CHOICES = [
        ('instant', 'Instant — wallet credited on delivery confirmation'),
        ('daily',   'Daily   — batched and paid at end of each day'),
        ('weekly',  'Weekly  — batched on a configured weekday'),
        ('monthly', 'Monthly — batched on a configured day each month'),
    ]

    vendor = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='payment_terms',
    )
    payout_period = models.CharField(
        max_length=20, choices=PAYOUT_PERIOD_CHOICES, default='daily',
    )
    payout_day = models.IntegerField(
        null=True, blank=True,
        help_text='Weekly → 0=Mon … 6=Sun.  Monthly → 1–28 (day of month).',
    )
    platform_fee_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('2.50'),
        help_text='% deducted as platform fee before crediting vendor wallet',
    )
    currency = models.CharField(max_length=3, default='ZMW')
    min_payout_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('1.00'),
        help_text='Minimum pending gross before a payout batch is triggered',
    )
    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'vendor_payment_terms'
        verbose_name        = 'Vendor Payment Terms'
        verbose_name_plural = 'Vendor Payment Terms'

    def __str__(self):
        name = getattr(self.vendor, 'get_full_name', lambda: '')() or self.vendor.email
        return f"{name} — {self.payout_period} | fee {self.platform_fee_percentage}%"


# ─────────────────────────────────────────────────────────────────────────────
# Vendor Payout  —  one record per commission event
# ─────────────────────────────────────────────────────────────────────────────

class VendorPayout(models.Model):
    """
    A single payout owed to a vendor after order delivery.

    Lifecycle:
      pending  →  waiting for next payout window (or instant)
      queued   →  VendorPayoutRequested event published to payment.events
      paid     →  Payment System sent VendorPayoutCompleted, wallet credited
      failed   →  Payment System sent VendorPayoutFailed
    """

    class PayoutStatus(models.TextChoices):
        PENDING = 'pending', _('Pending')
        QUEUED  = 'queued',  _('Queued — sent to Payment System')
        PAID    = 'paid',    _('Paid — wallet credited')
        FAILED  = 'failed',  _('Failed')

    vendor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='payouts',
    )
    payment_terms = models.ForeignKey(
        VendorPaymentTerms,
        on_delete=models.PROTECT,
        related_name='payouts',
        null=True,
        blank=True,
    )
    order_items = models.ManyToManyField('order_service.OrderItem', blank=True)
    source_reference = models.CharField(
        max_length=100,
        help_text='Order number that generated this payout',
    )

    # Amounts
    gross_amount = models.DecimalField(max_digits=12, decimal_places=2)
    platform_fee_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00'),
    )
    currency = models.CharField(max_length=3, default='ZMW')

    # Vendor's phone number — how Payment System identifies the wallet
    vendor_phone = models.CharField(max_length=20)

    status = models.CharField(
        max_length=20, choices=PayoutStatus.choices, default=PayoutStatus.PENDING,
    )

    # Filled in when Payment System confirms
    payment_system_reference = models.CharField(max_length=120, blank=True)
    event_trace_id           = models.CharField(max_length=100, blank=True)
    failure_reason           = models.TextField(blank=True)

    created_at   = models.DateTimeField(auto_now_add=True)
    queued_at    = models.DateTimeField(null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'vendor_payouts'
        verbose_name        = 'Vendor Payout'
        verbose_name_plural = 'Vendor Payouts'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['vendor', 'status']),
        ]

    def __str__(self):
        name = getattr(self.vendor, 'get_full_name', lambda: '')() or self.vendor.email
        return f"Payout {self.source_reference} → {name} | {self.gross_amount} {self.currency} [{self.status}]"
