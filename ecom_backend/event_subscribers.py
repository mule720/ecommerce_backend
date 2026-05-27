"""
E-commerce — Event Subscribers
================================
Listens on the 'ecommerce.events' RabbitMQ queue.

Handled events:
  VendorPayoutCompleted  ← Payment System credited vendor wallet
  VendorPayoutFailed     ← Payment System could not process payout
  WalletBalanceUpdated   ← Any wallet balance changed (vendor or customer)
  PaymentCompleted       ← Payment System processed an order payment
  RefundProcessed        ← Payment System processed a refund
  ShipmentCreated        ← Shipping System created a shipment (attach tracking)
  ShipmentDelivered      ← Shipping System confirmed delivery → trigger payout
  JournalEntryPosted     ← ERP posted a journal entry
"""

import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="event_bus.consume_event", bind=True, max_retries=3, default_retry_delay=60)
def consume_event(self, event: dict):
    """Generic event consumer for events routed to ecommerce.events queue."""
    event_type = event.get("event_type")
    logger.info(
        "[ecommerce] consumed event_type=%s event_id=%s",
        event_type, event.get("event_id"),
    )
    handlers = {
        "VendorPayoutCompleted": handle_vendor_payout_completed,
        "VendorPayoutFailed":    handle_vendor_payout_failed,
        "WalletBalanceUpdated":  handle_wallet_balance_updated,
        "PaymentCompleted":      handle_payment_completed,
        "RefundProcessed":       handle_refund_processed,
        "ShipmentCreated":       handle_shipment_created,
        "ShipmentDelivered":     handle_shipment_delivered,
        "JournalEntryPosted":    handle_journal_entry_posted,
    }
    handler = handlers.get(event_type)
    if handler:
        try:
            return handler(event)
        except Exception as exc:
            logger.error(
                "[ecommerce] handler failed event_type=%s: %s — retry %s/%s",
                event_type, exc, self.request.retries, self.max_retries,
            )
            raise self.retry(exc=exc)

    logger.info("[ecommerce] no handler for event_type=%s", event_type)
    return {"status": "ignored", "event_type": event_type}


# ── Payout pipeline ───────────────────────────────────────────────────────────

def handle_vendor_payout_completed(event: dict):
    """Payment System credited vendor wallet → mark payout as paid."""
    payload   = event.get("payload", {})
    payout_id = payload.get("payout_id")
    if not payout_id:
        return {"status": "ignored", "reason": "missing payout_id"}

    from payment_service.models import VendorPayout
    from django.utils import timezone
    VendorPayout.objects.filter(id=payout_id).update(
        status=VendorPayout.PayoutStatus.PAID,
        payment_system_reference=payload.get("transaction_ref", ""),
        processed_at=timezone.now(),
    )
    logger.info(
        "[ecommerce] VendorPayoutCompleted payout_id=%s vendor=%s net=%s",
        payout_id, payload.get("vendor_phone"), payload.get("net_amount"),
    )
    return {"status": "processed", "event_type": "VendorPayoutCompleted"}


def handle_vendor_payout_failed(event: dict):
    """Payment System rejected payout → mark as failed."""
    payload   = event.get("payload", {})
    payout_id = payload.get("payout_id")
    reason    = payload.get("reason", "Unknown error from Payment System")
    if not payout_id:
        return {"status": "ignored", "reason": "missing payout_id"}

    from payment_service.models import VendorPayout
    VendorPayout.objects.filter(id=payout_id).update(
        status=VendorPayout.PayoutStatus.FAILED,
        failure_reason=reason,
    )
    logger.error("[ecommerce] VendorPayoutFailed payout_id=%s reason=%s", payout_id, reason)
    return {"status": "processed", "event_type": "VendorPayoutFailed"}


# ── Wallet sync ───────────────────────────────────────────────────────────────

def handle_wallet_balance_updated(event: dict):
    """
    Real-time balance push from Payment System.
    Update the local wallet mirror so vendor/customer dashboards stay in sync.
    """
    payload   = event.get("payload", {})
    phone     = payload.get("vendor_phone", "")
    balance   = payload.get("balance", "0.00")
    available = payload.get("available_balance", "0.00")
    currency  = payload.get("currency", "ZMW")

    try:
        from wallet_service.models import Wallet
        from decimal import Decimal
        Wallet.objects.filter(phone_number=phone).update(
            balance=Decimal(balance),
            available_balance=Decimal(available),
            currency=currency,
        )
        logger.info("[ecommerce] WalletBalanceUpdated phone=%s balance=%s", phone, balance)
    except Exception as exc:
        logger.debug("[ecommerce] wallet_service mirror update skipped: %s", exc)

    return {"status": "processed", "event_type": "WalletBalanceUpdated"}


# ── Payment lifecycle ─────────────────────────────────────────────────────────

def handle_payment_completed(event: dict):
    """Payment System processed checkout payment → update order payment status."""
    payload  = event.get("payload", {})
    order_id = payload.get("order_id")
    tx_ref   = payload.get("gateway_transaction_id")

    if order_id:
        try:
            from order_service.models import Order
            Order.objects.filter(id=order_id).update(
                payment_status='completed',
                payment_reference=tx_ref or '',
            )
        except Exception as exc:
            logger.warning("[ecommerce] PaymentCompleted order update failed: %s", exc)

    logger.info("[ecommerce] PaymentCompleted order_id=%s tx=%s", order_id, tx_ref)
    return {"status": "processed", "event_type": "PaymentCompleted"}


def handle_refund_processed(event: dict):
    payload = event.get("payload", {})
    logger.info(
        "[ecommerce] RefundProcessed refund_id=%s order_id=%s",
        payload.get("refund_id"), payload.get("order_id"),
    )
    return {"status": "processed", "event_type": "RefundProcessed"}


# ── Shipping lifecycle ────────────────────────────────────────────────────────

def handle_shipment_created(event: dict):
    """Shipping System created shipment → attach tracking number to order."""
    payload         = event.get("payload", {})
    order_id        = payload.get("order_id")
    tracking_number = payload.get("tracking_number")

    if order_id and tracking_number:
        try:
            from order_service.models import Order
            Order.objects.filter(id=order_id).update(tracking_number=tracking_number)
        except Exception as exc:
            logger.warning("[ecommerce] ShipmentCreated tracking update failed: %s", exc)

    logger.info("[ecommerce] ShipmentCreated order_id=%s tracking=%s", order_id, tracking_number)
    return {"status": "processed", "event_type": "ShipmentCreated"}


def handle_shipment_delivered(event: dict):
    """
    Shipping System confirmed delivery.
    Mark order as delivered and create vendor payout records per vendor.
    """
    payload  = event.get("payload", {})
    order_id = payload.get("order_id")

    if order_id:
        try:
            from order_service.models import Order
            from payment_service.services import create_vendor_payout
            from decimal import Decimal

            order = Order.objects.filter(id=order_id).first()
            if order:
                order.status = 'delivered'
                order.save(update_fields=['status'])

                # One payout per vendor in this order
                vendors_seen = set()
                for item in order.items.select_related('vendor').all():
                    vendor = getattr(item, 'vendor', None)
                    if not vendor or vendor.id in vendors_seen:
                        continue
                    vendors_seen.add(vendor.id)

                    vendor_items = order.items.filter(vendor=vendor)
                    gross = sum(
                        (i.total_price for i in vendor_items if hasattr(i, 'total_price')),
                        Decimal('0.00'),
                    )
                    if gross > 0:
                        create_vendor_payout(
                            vendor=vendor,
                            gross_amount=gross,
                            source_reference=str(getattr(order, 'order_number', order_id)),
                            order_items=list(vendor_items),
                        )
        except Exception as exc:
            logger.error("[ecommerce] ShipmentDelivered payout creation failed: %s", exc)

    logger.info("[ecommerce] ShipmentDelivered order_id=%s", order_id)
    return {"status": "processed", "event_type": "ShipmentDelivered"}


# ── ERP ───────────────────────────────────────────────────────────────────────

def handle_journal_entry_posted(event: dict):
    payload = event.get("payload", {})
    logger.info("[ecommerce] JournalEntryPosted journal_id=%s", payload.get("journal_entry_id"))
    return {"status": "processed", "event_type": "JournalEntryPosted"}
