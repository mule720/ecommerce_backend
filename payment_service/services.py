"""
Payment Service — Payout Services
===================================
Business logic for creating and dispatching vendor payouts.

Flow:
  1. Order delivered → create_vendor_payout() creates a VendorPayout (status: pending)
  2. Celery beat tasks call dispatch_due_payouts(period) at the scheduled time
  3. dispatch_due_payouts() publishes VendorPayoutRequested to payment.events
  4. Payment System credits the wallet and replies with VendorPayoutCompleted
  5. handle_payout_completed() (in event_subscribers) updates the record to 'paid'
"""

import logging
import uuid
from decimal import Decimal

from django.db import transaction as db_transaction
from django.utils import timezone

from ecom_backend.event_bus import publish_event
from .models import VendorPayout, VendorPaymentTerms

logger = logging.getLogger(__name__)


def create_vendor_payout(vendor, gross_amount: Decimal, source_reference: str,
                         order_items=None, currency: str = 'ZMW') -> VendorPayout:
    """
    Create a VendorPayout record after an order is delivered.
    Called from order_service when order status → delivered.

    If the vendor has instant payment terms the payout is dispatched
    immediately; otherwise it stays pending until the batch task runs.
    """
    terms = VendorPaymentTerms.objects.filter(vendor=vendor, is_active=True).first()

    # Fall back to safe defaults if no terms configured yet
    fee_pct   = terms.platform_fee_percentage if terms else Decimal('0.00')
    period    = terms.payout_period           if terms else 'daily'
    currency  = terms.currency                if terms else currency

    # Vendor phone — must be set on the user profile for Payment System routing
    vendor_phone = getattr(vendor, 'phone_number', '') or getattr(vendor, 'phone', '') or ''

    with db_transaction.atomic():
        payout = VendorPayout.objects.create(
            vendor=vendor,
            payment_terms=terms,
            source_reference=source_reference,
            gross_amount=gross_amount,
            platform_fee_percentage=fee_pct,
            currency=currency,
            vendor_phone=vendor_phone,
            status=VendorPayout.PayoutStatus.PENDING,
        )
        if order_items:
            payout.order_items.set(order_items)

    logger.info(
        "[ecommerce] VendorPayout created payout_id=%s vendor=%s amount=%s period=%s",
        payout.id, vendor_phone, gross_amount, period,
    )

    # Instant → dispatch right away
    if period == 'instant':
        _dispatch_payout(payout)

    return payout


def dispatch_due_payouts(period: str) -> dict:
    """
    Find all pending payouts for vendors whose payment_terms.payout_period == period
    and publish VendorPayoutRequested events to the Payment System.

    Called by Celery beat tasks (daily at 23:55, weekly Monday 23:55, monthly 1st 23:55).
    """
    if period not in ('daily', 'weekly', 'monthly'):
        raise ValueError(f"Unknown period: {period}")

    pending = VendorPayout.objects.filter(
        status=VendorPayout.PayoutStatus.PENDING,
        payment_terms__payout_period=period,
        payment_terms__is_active=True,
    ).select_related('vendor', 'payment_terms')

    # Also dispatch payouts without explicit terms that were created for this period default
    pending_no_terms = VendorPayout.objects.filter(
        status=VendorPayout.PayoutStatus.PENDING,
        payment_terms__isnull=True,
    )

    all_pending = list(pending) + list(pending_no_terms)
    if not all_pending:
        logger.info("[ecommerce] dispatch_due_payouts(%s): no pending payouts", period)
        return {'period': period, 'dispatched': 0}

    dispatched = 0
    for payout in all_pending:
        try:
            _dispatch_payout(payout)
            dispatched += 1
        except Exception as exc:
            logger.error(
                "[ecommerce] Failed to dispatch payout_id=%s: %s", payout.id, exc
            )

    logger.info("[ecommerce] dispatch_due_payouts(%s): dispatched %s", period, dispatched)
    return {'period': period, 'dispatched': dispatched}


def _dispatch_payout(payout: VendorPayout):
    """Publish VendorPayoutRequested to the Payment System event queue."""
    trace_id = str(uuid.uuid4())
    event = publish_event(
        target_queue='payment.events',
        event_type='VendorPayoutRequested',
        payload={
            'source_app':              'ecommerce',
            'payout_id':               str(payout.id),
            'vendor_phone':            payout.vendor_phone,
            'source_reference':        payout.source_reference,
            'gross_amount':            str(payout.gross_amount),
            'platform_fee_percentage': str(payout.platform_fee_percentage),
            'currency':                payout.currency,
            'description': (
                f"E-commerce commission for order {payout.source_reference}"
            ),
        },
        trace_id=trace_id,
    )
    payout.status         = VendorPayout.PayoutStatus.QUEUED
    payout.queued_at      = timezone.now()
    payout.event_trace_id = trace_id
    payout.save(update_fields=['status', 'queued_at', 'event_trace_id'])
    logger.info(
        "[ecommerce] VendorPayoutRequested published payout_id=%s vendor=%s",
        payout.id, payout.vendor_phone,
    )
    return event
