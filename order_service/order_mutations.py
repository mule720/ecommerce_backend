"""
Enhanced Order Mutations for checkout integration
"""
import graphene
from graphene_django import DjangoObjectType
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
import uuid
from typing import TYPE_CHECKING
from .models import Order, OrderItem, OrderTimeline, VendorOrder
from cart_service.models import Cart, CartItem
from checkout_service.models import CheckoutSession
from product_service.models import Product
from user_service.auth_models import DeliveryAddress

if TYPE_CHECKING:
    from .schema import OrderType


class OrderTimelineType(DjangoObjectType):
    """GraphQL type for OrderTimeline"""
    class Meta:
        model = OrderTimeline
        fields = ['id', 'event_type', 'status', 'description', 'actor', 'created_at']


class VendorOrderType(DjangoObjectType):
    """GraphQL type for VendorOrder"""
    vendor_name = graphene.String()
    
    class Meta:
        model = VendorOrder
        fields = ['id', 'vendor', 'status', 'subtotal', 'commission_amount', 'payout_amount', 'payout_status', 'created_at']
    
    def resolve_vendor_name(self, info):
        return self.vendor.username if self.vendor else None


class CreateOrderFromCheckoutMutation(graphene.Mutation):
    """Create order from checkout session with payment handling"""
    
    class Arguments:
        checkout_session_id = graphene.Int(required=True)
    
    order_id = graphene.Int()
    order_number = graphene.String()
    message = graphene.String()
    success = graphene.Boolean()
    
    def mutate(self, info, checkout_session_id):
        user = info.context.user
        
        if not user.is_authenticated:
            return CreateOrderFromCheckoutMutation(
                success=False,
                message="User must be authenticated"
            )
        
        # Get checkout session
        try:
            checkout = CheckoutSession.objects.get(
                id=checkout_session_id,
                customer=user,
                status='active'
            )
        except CheckoutSession.DoesNotExist:
            return CreateOrderFromCheckoutMutation(
                success=False,
                message="Checkout session not found"
            )
        
        if checkout.is_expired():
            checkout.status = 'expired'
            checkout.save()
            return CreateOrderFromCheckoutMutation(
                success=False,
                message="Checkout session has expired"
            )
        
        # Get cart
        if not checkout.cart:
            return CreateOrderFromCheckoutMutation(
                success=False,
                message="No cart associated with checkout"
            )
        
        cart = checkout.cart
        if cart.cartitem_set.count() == 0:
            return CreateOrderFromCheckoutMutation(
                success=False,
                message="Cart is empty"
            )
        
        # Get delivery address
        if not checkout.delivery_address:
            return CreateOrderFromCheckoutMutation(
                success=False,
                message="Delivery address not selected"
            )
        
        # Get shipping method
        if not checkout.shipping_method:
            return CreateOrderFromCheckoutMutation(
                success=False,
                message="Shipping method not selected"
            )
        
        # Generate order number
        order_number = f"ORD-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
        
        # Create order
        order = Order.objects.create(
            order_number=order_number,
            customer=user,
            subtotal=checkout.subtotal,
            tax_amount=checkout.tax_amount,
            shipping_amount=checkout.shipping_cost,
            total=checkout.total,
            
            # Shipping info from delivery address
            shipping_first_name=checkout.delivery_address.full_name.split()[0] if checkout.delivery_address.full_name else '',
            shipping_last_name=checkout.delivery_address.full_name.split()[-1] if checkout.delivery_address.full_name else '',
            shipping_email=user.email,
            shipping_phone=checkout.delivery_address.phone_number,
            shipping_address=checkout.delivery_address.address_line1,
            shipping_city=checkout.delivery_address.city,
            shipping_state=checkout.delivery_address.state,
            shipping_country=checkout.delivery_address.country,
            shipping_postal_code=checkout.delivery_address.postal_code,
            
            # Billing same as shipping
            billing_first_name=checkout.delivery_address.full_name.split()[0] if checkout.delivery_address.full_name else '',
            billing_last_name=checkout.delivery_address.full_name.split()[-1] if checkout.delivery_address.full_name else '',
            billing_email=user.email,
            billing_phone=checkout.delivery_address.phone_number,
            billing_address=checkout.delivery_address.address_line1,
            billing_city=checkout.delivery_address.city,
            billing_state=checkout.delivery_address.state,
            billing_country=checkout.delivery_address.country,
            billing_postal_code=checkout.delivery_address.postal_code,
            
            # Shipping method
            shipping_method=checkout.shipping_method.shipping_type,
            estimated_delivery=timezone.now() + timezone.timedelta(days=checkout.shipping_method.estimated_days),
            
            # Payment
            payment_method='wallet',
            status=Order.OrderStatus.PENDING,
            payment_status=Order.PaymentStatus.PENDING,
        )
        
        # Create OrderTimeline entry
        OrderTimeline.objects.create(
            order=order,
            event_type=OrderTimeline.EventType.ORDER_CREATED,
            status=Order.OrderStatus.PENDING,
            description=f"Order created from checkout session {checkout_session_id}",
            actor=user
        )
        
        # Create order items and vendor groupings grouping by vendor
        vendor_items = {}
        for cart_item in cart.cartitem_set.all():
            product = cart_item.product
            vendor_id = product.vendor_id
            
            if vendor_id not in vendor_items:
                vendor_items[vendor_id] = {
                    'vendor': product.vendor,
                    'items': [],
                    'subtotal': Decimal('0.00')
                }
            
            # Create OrderItem
            item_subtotal = product.price * cart_item.quantity
            vendor_items[vendor_id]['subtotal'] += item_subtotal
            
            order_item = OrderItem.objects.create(
                order=order,
                vendor=product.vendor,
                product_name=product.name,
                product_image=str(product.image) if product.image else '',
                sku=product.sku or '',
                quantity=cart_item.quantity,
                price=product.price,
                total=item_subtotal,
                status=OrderItem.ItemStatus.PENDING
            )
            
            vendor_items[vendor_id]['items'].append(order_item)
        
        # Create VendorOrder records and calculate commissions
        platform_commission_rate = Decimal('5.00')
        
        for vendor_id, vendor_data in vendor_items.items():
            commission = (vendor_data['subtotal'] * platform_commission_rate) / Decimal('100.00')
            
            vendor_order = VendorOrder.objects.create(
                order=order,
                vendor=vendor_data['vendor'],
                subtotal=vendor_data['subtotal'],
                commission_amount=commission,
                payout_amount=vendor_data['subtotal'] - commission,
                status=VendorOrder.VendorOrderStatus.PENDING,
                payout_status='pending'
            )
        
        # Mark checkout as completed
        checkout.status = 'completed'
        checkout.save()
        
        # Clear cart
        cart.cartitem_set.all().delete()
        
        return CreateOrderFromCheckoutMutation(
            success=True,
            order_id=order.id,
            order_number=order.order_number,
            message="Order created successfully"
        )


class UpdateOrderStatusMutation(graphene.Mutation):
    """Update order status by vendor or admin"""
    
    class Arguments:
        order_id = graphene.Int(required=True)
        new_status = graphene.String(required=True)
        description = graphene.String()
    
    order_id = graphene.Int()
    order_number = graphene.String()
    new_status = graphene.String()
    message = graphene.String()
    success = graphene.Boolean()
    
    def mutate(self, info, order_id, new_status, description=''):
        user = info.context.user
        
        if not user.is_authenticated:
            return UpdateOrderStatusMutation(
                success=False,
                message="User must be authenticated"
            )
        
        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            return UpdateOrderStatusMutation(
                success=False,
                message="Order not found"
            )
        
        # Check permissions
        is_vendor = order.items.filter(vendor=user).exists()
        is_admin = user.is_staff
        
        if not (is_vendor or is_admin or order.customer == user):
            return UpdateOrderStatusMutation(
                success=False,
                message="You don't have permission to update this order"
            )
        
        # Validate status
        valid_statuses = [choice[0] for choice in Order.OrderStatus.choices]
        if new_status not in valid_statuses:
            return UpdateOrderStatusMutation(
                success=False,
                message=f"Invalid status: {new_status}"
            )
        
        old_status = order.status
        order.status = new_status
        order.save()
        
        # Create timeline entry
        OrderTimeline.objects.create(
            order=order,
            event_type=self._get_event_type(new_status),
            status=new_status,
            description=description or f"Status changed from {old_status} to {new_status}",
            actor=user
        )
        
        return UpdateOrderStatusMutation(
            success=True,
            order_id=order.id,
            order_number=order.order_number,
            new_status=order.status,
            message="Order status updated"
        )
    
    @staticmethod
    def _get_event_type(status):
        """Map order status to timeline event type"""
        status_to_event = {
            'pending': OrderTimeline.EventType.PAYMENT_PENDING,
            'confirmed': OrderTimeline.EventType.CONFIRMED,
            'processing': OrderTimeline.EventType.PROCESSING,
            'shipped': OrderTimeline.EventType.SHIPPED,
            'out_for_delivery': OrderTimeline.EventType.OUT_FOR_DELIVERY,
            'delivered': OrderTimeline.EventType.DELIVERED,
            'cancelled': OrderTimeline.EventType.CANCELLED,
            'refunded': OrderTimeline.EventType.REFUNDED,
        }
        return status_to_event.get(status, status)


class ConfirmOrderDeliveryMutation(graphene.Mutation):
    """Customer confirms order delivery"""
    
    class Arguments:
        order_id = graphene.Int(required=True)
    
    order_id = graphene.Int()
    order_number = graphene.String()
    message = graphene.String()
    success = graphene.Boolean()
    
    def mutate(self, info, order_id):
        user = info.context.user
        
        if not user.is_authenticated:
            return ConfirmOrderDeliveryMutation(
                success=False,
                message="User must be authenticated"
            )
        
        try:
            order = Order.objects.get(id=order_id, customer=user)
        except Order.DoesNotExist:
            return ConfirmOrderDeliveryMutation(
                success=False,
                message="Order not found"
            )
        
        order.status = Order.OrderStatus.DELIVERED
        order.save()
        
        # Create timeline entry
        OrderTimeline.objects.create(
            order=order,
            event_type=OrderTimeline.EventType.DELIVERED,
            status=Order.OrderStatus.DELIVERED,
            description="Customer confirmed delivery",
            actor=user
        )
        
        return ConfirmOrderDeliveryMutation(
            success=True,
            order_id=order.id,
            order_number=order.order_number,
            message="Delivery confirmed"
        )


class ReleaseVendorPayoutMutation(graphene.Mutation):
    """Release vendor payout from escrow (Admin only)"""
    
    class Arguments:
        vendor_order_id = graphene.Int(required=True)
    
    vendor_order = graphene.Field(VendorOrderType)
    message = graphene.String()
    success = graphene.Boolean()
    
    def mutate(self, info, vendor_order_id):
        user = info.context.user
        
        if not user.is_authenticated or not user.is_staff:
            return ReleaseVendorPayoutMutation(
                success=False,
                message="Admin permission required"
            )
        
        try:
            vendor_order = VendorOrder.objects.get(id=vendor_order_id)
        except VendorOrder.DoesNotExist:
            return ReleaseVendorPayoutMutation(
                success=False,
                message="Vendor order not found"
            )
        
        vendor_order.payout_status = 'completed'
        vendor_order.save()
        
        # Update parent order escrow status if all vendor payouts are completed
        order = vendor_order.order
        if not order.vendor_orders.filter(payout_status__in=['pending', 'processing']).exists():
            order.escrow_status = Order.EscrowStatus.RELEASED
            order.save()
        
        return ReleaseVendorPayoutMutation(
            success=True,
            vendor_order=vendor_order,
            message="Payout released"
        )


class OrderMutation(graphene.ObjectType):
    """Order mutations"""
    create_order_from_checkout = CreateOrderFromCheckoutMutation.Field()
    update_order_status = UpdateOrderStatusMutation.Field()
    confirm_order_delivery = ConfirmOrderDeliveryMutation.Field()
    release_vendor_payout = ReleaseVendorPayoutMutation.Field()
