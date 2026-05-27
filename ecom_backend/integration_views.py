"""REST integration endpoints used by external systems.

This module exposes webhook-style endpoints that allow third-party systems
(payment gateways, shipping partners, and ERP tools) to push updates into the
platform. It also exposes inventory reserve/release endpoints for external
orchestrators.
"""
import json
from decimal import Decimal

from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from ecom_backend.event_bus import publish_event
from order_service.models import Order
from payment_service.models import Payment, Refund, VendorPayout
from product_service.inventory_ops import reserve_inventory_lines, release_inventory_lines
from shipping_service.models import Shipment, ShipmentEvent


def _parse_json(request):
    """Safely parse the request body into a Python dictionary/list.

    Returns:
        Parsed JSON object when valid.
        None when payload is invalid JSON.
    """
    try:
        # Decode request bytes and parse JSON. Empty payload becomes {}.
        return json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        # Returning None allows callers to respond with a clean 400 error.
        return None


def _authorized(request):
    """Validate the shared integration token (if configured).

    When ``INTEGRATION_SHARED_TOKEN`` is not set, authorization is treated as
    open for local development convenience.
    """
    expected = getattr(settings, "INTEGRATION_SHARED_TOKEN", "")
    if not expected:
        # No token configured -> do not block integration traffic.
        return True
    provided = request.headers.get("X-Integration-Token", "")
    return provided == expected


@csrf_exempt
@require_POST
def payment_webhook(request):
    """Handle payment-provider events and synchronize order/payment states."""
    # 1) Reject unauthorized calls before any processing.
    if not _authorized(request):
        return JsonResponse({"error": "unauthorized"}, status=401)

    # 2) Validate JSON payload shape.
    data = _parse_json(request)
    if data is None:
        return JsonResponse({"error": "invalid_json"}, status=400)

    # 3) Normalize common fields from incoming event envelope.
    event_type = data.get("event_type")
    payload = data.get("payload", data)
    order_id = payload.get("order_id")
    tx = payload.get("transaction_id")

    # 4) Locate payment using transaction id first, then fallback to order id.
    payment = None
    if tx:
        payment = Payment.objects.filter(transaction_id=tx).first()
    if not payment and order_id:
        payment = Payment.objects.filter(order_id=order_id).order_by("-created_at").first()

    # 5) Resolve order either from payment relation or directly by id.
    order = None
    if payment:
        order = payment.order
    elif order_id:
        order = Order.objects.filter(pk=order_id).first()

    # 6) Apply business transitions based on incoming event type.
    if event_type == "PaymentCompleted":
        if payment:
            payment.status = "completed"
            payment.gateway_transaction_id = payload.get("gateway_transaction_id", payment.gateway_transaction_id)
            payment.payment_gateway_response = payload
            payment.save(update_fields=["status", "gateway_transaction_id", "payment_gateway_response", "updated_at"])
        if order:
            # Mark order as paid and advance from pending to confirmed.
            order.payment_status = Order.PaymentStatus.PAID
            if order.status == Order.OrderStatus.PENDING:
                order.status = Order.OrderStatus.CONFIRMED
            order.save(update_fields=["payment_status", "status", "updated_at"])

    elif event_type == "PaymentFailed":
        if payment:
            payment.status = "failed"
            payment.payment_gateway_response = payload
            payment.save(update_fields=["status", "payment_gateway_response", "updated_at"])
        if order:
            order.payment_status = Order.PaymentStatus.FAILED
            order.save(update_fields=["payment_status", "updated_at"])

    elif event_type == "RefundProcessed":
        # Finalize refund records and align parent payment/order states.
        refund_id = payload.get("refund_id")
        refund = Refund.objects.filter(pk=refund_id).first() if refund_id else None
        if refund:
            refund.status = "completed"
            refund.save(update_fields=["status", "updated_at"])
        if payment:
            payment.status = "refunded"
            payment.save(update_fields=["status", "updated_at"])
        if order:
            order.payment_status = Order.PaymentStatus.REFUNDED
            order.status = Order.OrderStatus.REFUNDED
            order.save(update_fields=["payment_status", "status", "updated_at"])

    elif event_type == "VendorPayoutCompleted":
        # Close payout workflow for vendor settlements.
        payout_id = payload.get("payout_id")
        payout = VendorPayout.objects.filter(pk=payout_id).first() if payout_id else None
        if payout:
            payout.status = "completed"
            payout.bank_reference = payload.get("bank_reference", payout.bank_reference)
            payout.processed_at = timezone.now()
            payout.save(update_fields=["status", "bank_reference", "processed_at"])

    # Always acknowledge receipt so upstream can stop retrying.
    return JsonResponse({"status": "ok", "event_type": event_type})


@csrf_exempt
@require_POST
def shipping_webhook(request):
    """Process shipment lifecycle updates from logistics providers."""
    # 1) Verify source.
    if not _authorized(request):
        return JsonResponse({"error": "unauthorized"}, status=401)

    # 2) Parse event data.
    data = _parse_json(request)
    if data is None:
        return JsonResponse({"error": "invalid_json"}, status=400)

    event_type = data.get("event_type")
    payload = data.get("payload", data)

    # 3) Resolve shipment by tracking number or associated order.
    shipment = None
    tracking = payload.get("tracking_number")
    if tracking:
        shipment = Shipment.objects.filter(tracking_number=tracking).first()

    if not shipment and payload.get("order_id"):
        shipment = Shipment.objects.filter(order_id=payload.get("order_id")).order_by("-created_at").first()

    if event_type in {"ShipmentStatusChanged", "ShipmentDelivered", "ShipmentCreated"} and shipment:
        new_status = payload.get("status")
        if event_type == "ShipmentDelivered":
            # Delivered event should force terminal delivered state.
            new_status = Shipment.ShipmentStatus.DELIVERED
        if new_status:
            shipment.status = new_status
            if new_status == Shipment.ShipmentStatus.DELIVERED:
                shipment.actual_delivery = timezone.now()
            shipment.save(update_fields=["status", "actual_delivery", "updated_at"])

        # Keep an immutable event history for audit and customer tracking.
        ShipmentEvent.objects.create(
            shipment=shipment,
            status=shipment.status,
            location=payload.get("location", ""),
            description=payload.get("description", event_type),
            timestamp=timezone.now(),
        )

        if shipment.order_id and shipment.status == Shipment.ShipmentStatus.DELIVERED:
            # Promote order to delivered once shipment completes.
            order = shipment.order
            order.status = Order.OrderStatus.DELIVERED
            order.save(update_fields=["status", "updated_at"])

    return JsonResponse({"status": "ok", "event_type": event_type})


@csrf_exempt
@require_POST
def erp_webhook(request):
    """Apply ERP-origin events such as accounting sync and tax updates."""
    if not _authorized(request):
        return JsonResponse({"error": "unauthorized"}, status=401)

    data = _parse_json(request)
    if data is None:
        return JsonResponse({"error": "invalid_json"}, status=400)

    event_type = data.get("event_type")
    payload = data.get("payload", data)

    if event_type == "JournalEntryPosted":
        # Mark order as ERP-synced once finance journal posting succeeds.
        order = Order.objects.filter(pk=payload.get("order_id")).first()
        if order:
            order.mark_erp_synced(reference=payload.get("journal_entry_id", ""))

    elif event_type == "TaxCalculated":
        # Apply tax calculation from ERP and recompute order total.
        order = Order.objects.filter(pk=payload.get("order_id")).first()
        if order and payload.get("tax_amount") is not None:
            tax_amount = Decimal(str(payload.get("tax_amount")))
            order.tax_amount = tax_amount
            order.calculate_total()
            order.save(update_fields=["tax_amount", "total", "updated_at"])

    return JsonResponse({"status": "ok", "event_type": event_type})


@csrf_exempt
@require_POST
def reserve_inventory_api(request):
    """Reserve stock quantities for external workflows (e.g., ERP/OMS)."""
    if not _authorized(request):
        return JsonResponse({"error": "unauthorized"}, status=401)

    data = _parse_json(request)
    if data is None:
        return JsonResponse({"error": "invalid_json"}, status=400)

    # Extract a traceable source reference and the target line items.
    source_reference = data.get("source_reference", "external-reserve")
    lines = data.get("lines", [])
    try:
        # Reserve each requested line atomically according to inventory rules.
        reserved = reserve_inventory_lines(
            lines=lines,
            source_reference=source_reference,
            context_message="Inventory reserved by external integration API",
        )
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    # Broadcast event so other consumers can react (analytics, ERP, etc).
    publish_event("erp.events", "InventoryReserved", {
        "source_reference": source_reference,
        "lines": lines,
    })
    return JsonResponse({"status": "ok", "reserved": reserved})


@csrf_exempt
@require_POST
def release_inventory_api(request):
    """Release previously reserved stock for external workflows."""
    if not _authorized(request):
        return JsonResponse({"error": "unauthorized"}, status=401)

    data = _parse_json(request)
    if data is None:
        return JsonResponse({"error": "invalid_json"}, status=400)

    # Use source reference for traceability in logs/audits.
    source_reference = data.get("source_reference", "external-release")
    lines = data.get("lines", [])
    try:
        # Reverse reservation records and restore available stock.
        released = release_inventory_lines(
            lines=lines,
            source_reference=source_reference,
            context_message="Inventory released by external integration API",
        )
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    # Emit asynchronous event for downstream systems.
    publish_event("erp.events", "InventoryReleased", {
        "source_reference": source_reference,
        "lines": lines,
    })
    return JsonResponse({"status": "ok", "released": released})
