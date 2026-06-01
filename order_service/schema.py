"""
Order Service GraphQL Schema
GraphQL API for order management
"""
import graphene
from graphene import relay
from graphene_django import DjangoObjectType
from graphene_django.filter import DjangoFilterConnectionField
from django.db import transaction
from django_filters import FilterSet, CharFilter, NumberFilter, DateFromToRangeFilter
from datetime import datetime
from decimal import Decimal
import uuid
from graphql_relay import from_global_id
from .models import Order, OrderItem, ReturnRequest, OrderTimeline, VendorOrder
from cart_service.models import Cart as ShoppingCart
from .order_mutations import (
    CreateOrderFromCheckoutMutation, UpdateOrderStatusMutation, 
    ConfirmOrderDeliveryMutation, ReleaseVendorPayoutMutation,
    OrderTimelineType, VendorOrderType, OrderMutation
)
# Note: Cart types are imported lazily in the Query class to avoid circular imports
from product_service.inventory_ops import reserve_inventory_lines, release_inventory_lines
from ecom_backend.event_bus import publish_event
import logging
import json
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)


def _notify_integrated_services(order, order_payload, items_payload):
    """
    Fire-and-forget HTTP calls to payment, shipping and ERP services.
    Runs in a background thread so it never blocks the order response.
    """
    from django.conf import settings

    shared_token = getattr(settings, 'INTEGRATION_SHARED_TOKEN', '')
    headers = {
        'Content-Type': 'application/json',
        'X-Internal-Token': shared_token,
    }

    # ── 1. Notify Payment System ────────────────────────────────────────────
    payment_url = getattr(settings, 'PAYMENT_SYSTEM_WEBHOOK_URL', '')
    if payment_url:
        try:
            payload = json.dumps({
                'event': 'order_placed',
                'order_id': str(order.id),
                'order_number': order.order_number,
                'amount': str(order.total),
                'currency': order.currency,
                'customer_email': order.shipping_email if hasattr(order, 'shipping_email') else '',
            }).encode()
            req = urllib.request.Request(
                f'{payment_url}/api/webhooks/order-placed/',
                data=payload, headers=headers, method='POST',
            )
            urllib.request.urlopen(req, timeout=5)
            logger.info('Payment system notified for order %s', order.order_number)
        except Exception as exc:
            logger.warning('Could not notify payment system: %s', exc)

    # ── 2. Notify Shipping System ───────────────────────────────────────────
    shipping_url = getattr(settings, 'SHIPPING_SYSTEM_WEBHOOK_URL', '')
    if shipping_url:
        try:
            payload = json.dumps({
                'event': 'order_placed',
                'order_id': str(order.id),
                'order_number': order.order_number,
                'sender_name': 'Ecommerce Warehouse',
                'sender_address': getattr(settings, 'WAREHOUSE_ADDRESS', ''),
                'recipient_name': f"{order.shipping_first_name} {order.shipping_last_name}",
                'recipient_address': order.shipping_address,
                'recipient_phone': order.shipping_phone if hasattr(order, 'shipping_phone') else '',
                'recipient_city': order.shipping_city,
                'weight': sum(
                    float(item.get('weight', 0.5)) * item.get('quantity', 1)
                    for item in items_payload
                ),
                'items': items_payload,
            }).encode()
            req = urllib.request.Request(
                f'{shipping_url}/api/webhooks/order-placed/',
                data=payload, headers=headers, method='POST',
            )
            urllib.request.urlopen(req, timeout=5)
            logger.info('Shipping system notified for order %s', order.order_number)
        except Exception as exc:
            logger.warning('Could not notify shipping system: %s', exc)

    # ── 3. Notify ERP System ────────────────────────────────────────────────
    erp_url = getattr(settings, 'ERP_SYSTEM_WEBHOOK_URL', '')
    if erp_url:
        try:
            payload = json.dumps({
                'event': 'order_placed',
                'order_id': str(order.id),
                'order_number': order.order_number,
                'subtotal': str(order.subtotal),
                'total': str(order.total),
                'currency': order.currency,
                'items': items_payload,
            }).encode()
            req = urllib.request.Request(
                f'{erp_url}/api/webhooks/ecommerce-order/',
                data=payload, headers=headers, method='POST',
            )
            urllib.request.urlopen(req, timeout=5)
            logger.info('ERP system notified for order %s', order.order_number)
        except Exception as exc:
            logger.warning('Could not notify ERP system: %s', exc)


def _decode_graphql_id(value):
    """Accept raw int/string IDs or Relay global IDs and return int."""
    if isinstance(value, int):
        return value
    if value is None:
        raise ValueError("Missing id")

    raw = str(value)
    if raw.isdigit():
        return int(raw)

    try:
        _, decoded = from_global_id(raw)
        if str(decoded).isdigit():
            return int(decoded)
    except Exception:
        pass

    raise ValueError("Invalid id format")


# Forward declarations for type references
class OrderTimelineTypeLocal(DjangoObjectType):
    """GraphQL type for OrderTimeline"""
    class Meta:
        model = OrderTimeline
        fields = ['id', 'event_type', 'status', 'description', 'actor', 'created_at']


class VendorOrderTypeLocal(DjangoObjectType):
    """GraphQL type for VendorOrder"""
    vendor_name = graphene.String()
    
    class Meta:
        model = VendorOrder
        fields = ['id', 'vendor', 'status', 'subtotal', 'commission_amount', 'payout_amount', 'payout_status', 'created_at']
        interfaces = (relay.Node,)
    
    def resolve_vendor_name(self, info):
        return self.vendor.username if self.vendor else None


class OrderItemType(DjangoObjectType):
    """GraphQL type for OrderItem model"""
    class Meta:
        """Defines the purpose and behavior of the `Meta` class."""
        model = OrderItem
        fields = "__all__"
        interfaces = (relay.Node,)


class OrderType(DjangoObjectType):
    """GraphQL type for Order model"""
    class Meta:
        """Defines the purpose and behavior of the `Meta` class."""
        model = Order
        fields = "__all__"
        interfaces = (relay.Node,)
    
    items = graphene.List(OrderItemType)
    timeline = graphene.List(OrderTimelineTypeLocal)
    vendor_orders = graphene.List(VendorOrderTypeLocal)
    
    def resolve_items(self, info):
        """Resolver for the GraphQL field `items`."""
        return self.items.all()
    
    def resolve_timeline(self, info):
        """Resolver for the GraphQL field `timeline`."""
        return self.timeline.all()
    
    def resolve_vendor_orders(self, info):
        """Resolver for the GraphQL field `vendor_orders`."""
        return self.vendor_orders.all()


class ReturnRequestType(DjangoObjectType):
    """GraphQL type for ReturnRequest model"""
    class Meta:
        """Defines the purpose and behavior of the `Meta` class."""
        model = ReturnRequest
        fields = "__all__"


# Filters
class OrderFilter(FilterSet):
    """Filter for Order queries"""
    status = CharFilter(field_name='status')
    payment_status = CharFilter(field_name='payment_status')
    created_at = DateFromToRangeFilter()
    
    class Meta:
        """Defines the purpose and behavior of the `Meta` class."""
        model = Order
        fields = ['status', 'payment_status']


class Query(graphene.ObjectType):
    """Order Service Queries"""
    
    # Order queries
    all_orders = DjangoFilterConnectionField(
        OrderType,
        filterset_class=OrderFilter
    )
    order = relay.Node.Field(OrderType)
    order_by_number = graphene.Field(
        OrderType,
        order_number=graphene.String(required=True)
    )
    my_orders = graphene.List(OrderType)
    orders_by_vendor = graphene.List(
        OrderType,
        vendor_id=graphene.ID(required=True)
    )
    order_details = graphene.Field(
        OrderType,
        order_id=graphene.Int(required=True)
    )
    order_timeline = graphene.List(
        OrderTimelineTypeLocal,
        order_id=graphene.Int(required=True)
    )
    
    # Return requests
    return_requests = graphene.List(
        ReturnRequestType,
        order_item_id=graphene.ID(required=True)
    )
    my_vendor_return_requests = graphene.List(ReturnRequestType)
    
    # Resolvers
    def resolve_all_orders(self, info, **kwargs):
        """Resolver for the GraphQL field `all orders`."""
        return Order.objects.all()
    
    def resolve_order_by_number(self, info, order_number):
        """Resolver for the GraphQL field `order by number`."""
        try:
            return Order.objects.get(order_number=order_number)
        except Order.DoesNotExist:
            return None
    
    def resolve_my_orders(self, info):
        """Resolver for the GraphQL field `my orders`."""
        user = info.context.user
        if user.is_anonymous:
            raise Exception('Not logged in!')
        return Order.objects.filter(customer=user)
    
    def resolve_orders_by_vendor(self, info, vendor_id):
        """Resolver for the GraphQL field `orders by vendor`."""
        try:
            vendor_id_int = int(vendor_id)
            return Order.objects.filter(items__vendor_id=vendor_id_int).distinct()
        except (ValueError, TypeError):
            return Order.objects.none()
    
    def resolve_return_requests(self, info, order_item_id):
        """Resolver for the GraphQL field `return requests`."""
        try:
            resolved_id = _decode_graphql_id(order_item_id)
            return ReturnRequest.objects.filter(order_item_id=resolved_id)
        except (ValueError, TypeError):
            return ReturnRequest.objects.none()

    def resolve_my_vendor_return_requests(self, info):
        """Return requests for products owned by currently authenticated vendor."""
        user = info.context.user
        if user.is_anonymous:
            raise Exception('Not logged in!')

        return ReturnRequest.objects.filter(
            order_item__vendor=user
        ).select_related('order_item', 'order_item__order', 'customer').order_by('-created_at')
    
    def resolve_order_details(self, info, order_id):
        """Get order with all related data"""
        user = info.context.user
        try:
            order = Order.objects.prefetch_related(
                'items',
                'items__vendor',
                'timeline',
                'vendor_orders'
            ).get(id=order_id)
            
            # Check permission
            is_vendor = order.items.filter(vendor=user).exists()
            if not (order.customer == user or is_vendor or user.is_staff):
                return None
            
            return order
        except Order.DoesNotExist:
            return None
    
    def resolve_order_timeline(self, info, order_id):
        """Get order status timeline"""
        user = info.context.user
        try:
            order = Order.objects.get(id=order_id)
            
            # Check permission
            is_vendor = order.items.filter(vendor=user).exists()
            if not (order.customer == user or is_vendor or user.is_staff):
                return []
            
            return order.timeline.all()
        except Order.DoesNotExist:
            return []


# Mutations
class CreateOrderFromCartMutation(graphene.Mutation):
    """Create an order from cart items"""
    class Arguments:
        """Defines the purpose and behavior of the `Arguments` class."""
        shipping_first_name = graphene.String(required=True)
        shipping_last_name = graphene.String(required=True)
        shipping_email = graphene.String(required=True)
        shipping_phone = graphene.String(required=True)
        shipping_address = graphene.String(required=True)
        shipping_city = graphene.String(required=True)
        shipping_state = graphene.String(required=True)
        shipping_country = graphene.String(required=True)
        shipping_postal_code = graphene.String(required=True)
        notes = graphene.String()
        payment_method = graphene.String(required=False)
        defer_inventory_reservation = graphene.Boolean(required=False)
    
    order = graphene.Field(OrderType)
    success = graphene.Boolean()
    message = graphene.String()
    
    @classmethod
    def mutate(cls, root, info, **kwargs):
        """Executes mutation business rules and returns the mutation response object."""
        from ecom_backend.query_optimization import get_optimized_orders
        
        user = info.context.user
        if user.is_anonymous:
            raise Exception('Not logged in!')
        
        # Use optimized query to get cart with products
        cart = ShoppingCart.objects.prefetch_related(
            'items',
            'items__product',
            'items__product__vendor'
        ).filter(customer_id=user.id).first()

        # Fallback: in checkout flow, cart may already be attached to
        # an active checkout session for this user.
        if not cart or not cart.items.exists():
            try:
                from checkout_service.models import CheckoutSession
                checkout_session = (
                    CheckoutSession.objects
                    .select_related('cart')
                    .filter(customer_id=user.id, status='active')
                    .exclude(cart__isnull=True)
                    .order_by('-created_at')
                    .first()
                )
                if checkout_session and checkout_session.cart and checkout_session.cart.items.exists():
                    cart = checkout_session.cart
            except Exception:
                pass

        if not cart or not cart.items.exists():
            raise Exception('Cart is empty')
        
        # Generate order number
        order_number = f"ORD-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"

        # Prepare inventory reservation data (batch operation)
        defer_inventory_reservation = kwargs.get('defer_inventory_reservation', False)
        reservation_lines = [
            {
                'sku': cart_item.product.sku,
                'quantity': cart_item.quantity,
                'vendor_id': cart_item.product.vendor_id,
            }
            for cart_item in cart.items.all()
        ]
        
        if not defer_inventory_reservation:
            reserve_inventory_lines(
                lines=reservation_lines,
                source_reference=order_number,
                context_message='Inventory reserved for placed order',
            )
        
        # Calculate totals (single operation)
        subtotal = cart.get_total()
        tax_amount = subtotal * Decimal('0.1')
        shipping_amount = Decimal('10.00') if subtotal < Decimal('100.00') else Decimal('0.00')
        total = subtotal + tax_amount + shipping_amount

        payment_method = (kwargs.get('payment_method') or 'wallet').strip().lower()
        allowed_payment_methods = {'wallet', 'card', 'mobile_money', 'bank_transfer'}
        if payment_method not in allowed_payment_methods:
            raise Exception('Invalid payment method')

        wallet = None
        can_hold_wallet_funds = False
        if payment_method == 'wallet':
            from wallet_service.models import Wallet

            wallet, _ = Wallet.objects.get_or_create(customer=user)
            can_hold_wallet_funds = wallet.balance >= total
        
        with transaction.atomic():
            # Create order with all fields in one operation
            order = Order.objects.create(
                order_number=order_number,
                customer=user,
                subtotal=subtotal,
                tax_amount=tax_amount,
                shipping_amount=shipping_amount,
                total=total,
                shipping_first_name=kwargs['shipping_first_name'],
                shipping_last_name=kwargs['shipping_last_name'],
                shipping_email=kwargs['shipping_email'],
                shipping_phone=kwargs['shipping_phone'],
                shipping_address=kwargs['shipping_address'],
                shipping_city=kwargs['shipping_city'],
                shipping_state=kwargs['shipping_state'],
                shipping_country=kwargs['shipping_country'],
                shipping_postal_code=kwargs['shipping_postal_code'],
                billing_first_name=kwargs['shipping_first_name'],
                billing_last_name=kwargs['shipping_last_name'],
                billing_email=kwargs['shipping_email'],
                billing_phone=kwargs['shipping_phone'],
                billing_address=kwargs['shipping_address'],
                billing_city=kwargs['shipping_city'],
                billing_state=kwargs['shipping_state'],
                billing_country=kwargs['shipping_country'],
                billing_postal_code=kwargs['shipping_postal_code'],
                payment_method=payment_method,
                notes=kwargs.get('notes', '')
            )

            # For wallet payments, validate and debit immediately (escrow hold behavior).
            if payment_method == 'wallet' and wallet is not None and can_hold_wallet_funds:
                from wallet_service.models import WalletTransaction

                wallet.balance = wallet.balance - total
                wallet.pending_balance = wallet.pending_balance + total
                wallet.save(update_fields=['balance', 'pending_balance', 'updated_at'])

                WalletTransaction.objects.create(
                    wallet=wallet,
                    type=WalletTransaction.TransactionType.DEBIT,
                    amount=total,
                    status=WalletTransaction.TransactionStatus.COMPLETED,
                    description=f"Order payment hold for {order.order_number}",
                    reference=order.order_number,
                )

                order.payment_status = Order.PaymentStatus.PAID
                order.escrow_status = Order.EscrowStatus.HELD
                order.save(update_fields=['payment_status', 'escrow_status', 'updated_at'])

            # Graceful fallback when wallet integration/balance isn't ready yet.
            # Keep order placement successful and let payment be completed later.
            if payment_method == 'wallet' and not can_hold_wallet_funds:
                order.payment_status = Order.PaymentStatus.PENDING
                order.escrow_status = Order.EscrowStatus.PENDING
                existing_notes = order.notes or ''
                fallback_note = ' | wallet_precheck_skipped: insufficient balance, payment deferred'
                order.notes = f"{existing_notes}{fallback_note}"[:2000]
                order.save(update_fields=['payment_status', 'escrow_status', 'notes', 'updated_at'])
            
            # Batch create order items (bulk_create for performance)
            order_items = []
            for cart_item in cart.items.all():
                product = cart_item.product
                primary_image = product.images.filter(is_primary=True).first() or product.images.first()
                order_items.append(OrderItem(
                    order=order,
                    vendor=product.vendor,
                    product_name=product.name,
                    product_image=primary_image.image.url if primary_image and primary_image.image else '',
                    sku=product.sku,
                    quantity=cart_item.quantity,
                    price=product.price,
                    tax_amount=product.price * cart_item.quantity * Decimal('0.1'),
                    total=(product.price * cart_item.quantity) + (product.price * cart_item.quantity * Decimal('0.1'))
                ))
            
            # Use bulk_create for better performance (single DB insert)
            if order_items:
                OrderItem.objects.bulk_create(order_items)
            
            # Clear cart
            cart.items.all().delete()

        # Batch event publishing (reduced API calls)
        items_payload = [
            {
                'sku': item.sku,
                'quantity': item.quantity,
                'unit_price': str(item.price),
                'vendor_id': item.vendor_id,
                'total': str(item.total),
            }
            for item in order.items.all()
        ]
        
        order_payload = {
            'order_id': str(order.id),
            'order_number': order.order_number,
            'customer_id': str(order.customer_id),
            'currency': order.currency,
            'subtotal': str(order.subtotal),
            'tax_amount': str(order.tax_amount),
            'shipping_amount': str(order.shipping_amount),
            'total': str(order.total),
            'status': order.status,
            'payment_status': order.payment_status,
            'payment_method': order.payment_method,
            'shipping_address': {
                'first_name': order.shipping_first_name,
                'last_name': order.shipping_last_name,
                'email': order.shipping_email,
                'phone': order.shipping_phone,
                'address': order.shipping_address,
                'city': order.shipping_city,
                'state': order.shipping_state,
                'country': order.shipping_country,
                'postal_code': order.shipping_postal_code,
            },
            'items': items_payload,
        }

        # Single event with tax calculation
        publish_event('erp.events', 'TaxCalculationRequested', {
            'order_id': str(order.id),
            'order_number': order.order_number,
            'subtotal': str(order.subtotal),
            'currency': order.currency,
            'shipping_country': order.shipping_country,
            'shipping_state': order.shipping_state,
            'items': items_payload,
        })
        
        if defer_inventory_reservation:
            publish_event('erp.events', 'InventoryReserved', {
                'order_id': str(order.id),
                'order_number': order.order_number,
                'source_reference': order.order_number,
                'lines': reservation_lines,
            })
        
        # Publish events to RabbitMQ
        for queue in ['payment.events', 'shipping.events', 'erp.events']:
            publish_event(queue, 'OrderPlaced', order_payload)

        # ── Direct HTTP notifications to integrated services ──────────────
        # These are fire-and-forget: a failure must not block the order response.
        import threading
        threading.Thread(
            target=_notify_integrated_services,
            args=(order, order_payload, items_payload),
            daemon=True,
        ).start()

        return CreateOrderFromCartMutation(
            order=order,
            success=True,
            message='Order created successfully'
        )


class UpdateOrderStatusMutation(graphene.Mutation):
    """Update order status"""
    class Arguments:
        """Defines the purpose and behavior of the `Arguments` class."""
        order_id = graphene.ID(required=True)
        status = graphene.String(required=True)
    
    order = graphene.Field(OrderType)
    
    @classmethod
    def mutate(cls, root, info, order_id, status):
        """Executes mutation business rules and returns the mutation response object."""
        try:
            order = Order.objects.get(pk=int(order_id))
            previous_status = order.status
            order.status = status
            order.save()

            payload = {
                'order_id': str(order.id),
                'order_number': order.order_number,
                'previous_status': previous_status,
                'current_status': order.status,
                'payment_status': order.payment_status,
            }
            publish_event('payment.events', 'OrderStatusChanged', payload)
            publish_event('shipping.events', 'OrderStatusChanged', payload)
            publish_event('erp.events', 'OrderStatusChanged', payload)

            if status == Order.OrderStatus.CANCELLED and previous_status != Order.OrderStatus.CANCELLED:
                release_lines = [
                    {'sku': item.sku, 'quantity': item.quantity, 'vendor_id': item.vendor_id}
                    for item in order.items.all()
                ]
                release_inventory_lines(
                    lines=release_lines,
                    source_reference=order.order_number,
                    context_message='Inventory released due to order cancellation',
                )
                publish_event('erp.events', 'InventoryReleased', {
                    'order_id': str(order.id),
                    'order_number': order.order_number,
                    'reason': 'order_cancelled',
                })

            return UpdateOrderStatusMutation(order=order)
        except (Order.DoesNotExist, ValueError):
            raise Exception('Order not found')


class CreateReturnRequestMutation(graphene.Mutation):
    """Create a return request"""
    class Arguments:
        """Defines the purpose and behavior of the `Arguments` class."""
        order_item_id = graphene.ID(required=True)
        reason = graphene.String(required=True)
        refund_amount = graphene.Decimal(required=True)
    
    return_request = graphene.Field(ReturnRequestType)
    
    @classmethod
    def mutate(cls, root, info, order_item_id, reason, refund_amount):
        """Executes mutation business rules and returns the mutation response object."""
        user = info.context.user
        if user.is_anonymous:
            raise Exception('Not logged in!')
        
        try:
            resolved_order_item_id = _decode_graphql_id(order_item_id)
            order_item = OrderItem.objects.select_related('order').get(pk=resolved_order_item_id)
        except (OrderItem.DoesNotExist, ValueError):
            raise Exception('Order item not found')

        if order_item.order.customer_id != user.id:
            raise Exception('You can only return products from your own orders')

        has_open_request = ReturnRequest.objects.filter(
            order_item=order_item,
            customer=user,
            status__in=[
                ReturnRequest.ReturnStatus.PENDING,
                ReturnRequest.ReturnStatus.APPROVED,
            ]
        ).exists()
        if has_open_request:
            raise Exception('Return request already exists for this item')
        
        return_request = ReturnRequest.objects.create(
            order_item=order_item,
            customer=user,
            reason=reason,
            refund_amount=refund_amount
        )

        publish_event('notification.events', 'ReturnRequested', {
            'return_request_id': str(return_request.id),
            'order_item_id': str(order_item.id),
            'order_number': order_item.order.order_number,
            'vendor_id': str(order_item.vendor_id),
            'customer_id': str(user.id),
            'reason': reason,
            'refund_amount': str(refund_amount),
            'status': return_request.status,
        })
        
        return CreateReturnRequestMutation(return_request=return_request)


class UpdateReturnStatusMutation(graphene.Mutation):
    """Update return request status"""
    class Arguments:
        """Defines the purpose and behavior of the `Arguments` class."""
        return_request_id = graphene.ID(required=True)
        status = graphene.String(required=True)
    
    return_request = graphene.Field(ReturnRequestType)
    
    @classmethod
    def mutate(cls, root, info, return_request_id, status):
        """Executes mutation business rules and returns the mutation response object."""
        try:
            resolved_id = _decode_graphql_id(return_request_id)
            return_request = ReturnRequest.objects.get(pk=resolved_id)
            return_request.status = status
            return_request.save()
            return UpdateReturnStatusMutation(return_request=return_request)
        except (ReturnRequest.DoesNotExist, ValueError):
            raise Exception('Return request not found')


class Mutation(OrderMutation, graphene.ObjectType):
    """Order Service Mutations"""
    
    # Keep existing mutations for backward compatibility
    create_order_from_cart = CreateOrderFromCartMutation.Field()
    update_order_status = UpdateOrderStatusMutation.Field()
    create_return_request = CreateReturnRequestMutation.Field()
    update_return_status = UpdateReturnStatusMutation.Field()


class MarkOrderSyncedToErpMutation(graphene.Mutation):
    """Groups GraphQL write operations (mutations) for this module."""
    class Arguments:
        """Defines the purpose and behavior of the `Arguments` class."""
        order_id = graphene.ID(required=True)
        erp_reference = graphene.String(required=True)

    order = graphene.Field(OrderType)

    @classmethod
    def mutate(cls, root, info, order_id, erp_reference):
        """Executes mutation business rules and returns the mutation response object."""
        try:
            order = Order.objects.get(pk=int(order_id))
        except (Order.DoesNotExist, ValueError):
            raise Exception('Order not found')

        order.mark_erp_synced(reference=erp_reference)
        return MarkOrderSyncedToErpMutation(order=order)


Mutation.mark_order_synced_to_erp = MarkOrderSyncedToErpMutation.Field()


# Schema definition for Order Service
# NOTE: The gateway composes service Query/Mutation classes directly.
# Avoid eager schema instantiation here to prevent duplicate type
# registrations when all services are imported together.
