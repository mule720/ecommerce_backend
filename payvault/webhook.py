"""
PayVault webhook receiver for e-commerce.
Handles 'payment.confirmed' events to mark orders as paid.
"""
import hmac
import hashlib
import json

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods


@csrf_exempt
@require_http_methods(['POST'])
def payvault_webhook(request):
    body      = request.body
    signature = request.headers.get('X-Webhook-Signature', '')
    secret    = getattr(settings, 'PAYVAULT_WEBHOOK_SECRET', '')

    if secret:
        expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return JsonResponse({'detail': 'Invalid signature.'}, status=403)

    try:
        payload = json.loads(body)
    except ValueError:
        return JsonResponse({'detail': 'Invalid JSON.'}, status=400)

    event_type  = payload.get('event')
    session_ref = payload.get('session_reference') or payload.get('session_id')

    if event_type == 'payment.confirmed' and session_ref:
        from payment_service.models import Payment
        from order_service.models import Order

        payment = Payment.objects.filter(
            transaction_id__contains=session_ref,
            status='processing',
        ).first()

        if not payment:
            # Try matching via order merchant_reference stored by e-commerce
            payment = Payment.objects.filter(
                status='processing',
                order__order_number=payload.get('merchant_reference', ''),
            ).first()

        if payment:
            payment.status = 'completed'
            payment.save(update_fields=['status', 'updated_at'])

            order = payment.order
            order.payment_status = Order.PaymentStatus.PAID
            order.status = Order.OrderStatus.CONFIRMED
            order.save(update_fields=['payment_status', 'status', 'updated_at'])

    return JsonResponse({'received': True})
