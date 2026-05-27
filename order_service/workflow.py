"""
Order Workflow Management
Handles order status transitions, validations, and state management
"""
from django.utils import timezone
from decimal import Decimal
from .models import Order, OrderItem, VendorOrder, OrderTimeline


class OrderWorkflow:
    """Manages order status transitions and business logic"""
    
    # Valid status transitions
    VALID_TRANSITIONS = {
        Order.OrderStatus.PENDING: [
            Order.OrderStatus.CONFIRMED,
            Order.OrderStatus.CANCELLED,
        ],
        Order.OrderStatus.CONFIRMED: [
            Order.OrderStatus.PROCESSING,
            Order.OrderStatus.CANCELLED,
        ],
        Order.OrderStatus.PROCESSING: [
            Order.OrderStatus.SHIPPED,
            Order.OrderStatus.CANCELLED,
        ],
        Order.OrderStatus.SHIPPED: [
            Order.OrderStatus.OUT_FOR_DELIVERY,
            Order.OrderStatus.CANCELLED,
        ],
        Order.OrderStatus.OUT_FOR_DELIVERY: [
            Order.OrderStatus.DELIVERED,
            Order.OrderStatus.CANCELLED,
        ],
        Order.OrderStatus.DELIVERED: [
            Order.OrderStatus.REFUNDED,
        ],
        Order.OrderStatus.CANCELLED: [],
        Order.OrderStatus.REFUNDED: [],
    }
    
    @staticmethod
    def can_transition(current_status, new_status):
        """Check if status transition is valid"""
        if current_status not in OrderWorkflow.VALID_TRANSITIONS:
            return False
        return new_status in OrderWorkflow.VALID_TRANSITIONS[current_status]
    
    @staticmethod
    def transition(order, new_status, actor, description=None):
        """
        Perform a status transition with validation
        Returns: (success, message)
        """
        if not OrderWorkflow.can_transition(order.status, new_status):
            return False, f"Cannot transition from {order.status} to {new_status}"
        
        old_status = order.status
        order.status = new_status
        order.save()
        
        # Create timeline entry
        event_type = OrderWorkflow._get_event_type(new_status)
        timeline_description = description or f"Order status changed to {new_status}"
        
        OrderTimeline.objects.create(
            order=order,
            event_type=event_type,
            status=new_status,
            description=timeline_description,
            actor=actor
        )
        
        return True, f"Order transitioned from {old_status} to {new_status}"
    
    @staticmethod
    def _get_event_type(status):
        """Map order status to timeline event type"""
        status_to_event = {
            Order.OrderStatus.PENDING: OrderTimeline.EventType.PAYMENT_PENDING,
            Order.OrderStatus.CONFIRMED: OrderTimeline.EventType.CONFIRMED,
            Order.OrderStatus.PROCESSING: OrderTimeline.EventType.PROCESSING,
            Order.OrderStatus.SHIPPED: OrderTimeline.EventType.SHIPPED,
            Order.OrderStatus.OUT_FOR_DELIVERY: OrderTimeline.EventType.OUT_FOR_DELIVERY,
            Order.OrderStatus.DELIVERED: OrderTimeline.EventType.DELIVERED,
            Order.OrderStatus.CANCELLED: OrderTimeline.EventType.CANCELLED,
            Order.OrderStatus.REFUNDED: OrderTimeline.EventType.REFUNDED,
        }
        return status_to_event.get(status, OrderTimeline.EventType.ORDER_CREATED)


class PaymentWorkflow:
    """Manages payment processing and escrow"""
    
    @staticmethod
    def mark_payment_received(order, transaction_id, actor):
        """
        Mark order as paid and transition to confirmed.
        Deducts stock from inventory when payment is received.
        """
        if order.payment_status == Order.PaymentStatus.PAID:
            return False, "Order already paid"
        
        order.payment_status = Order.PaymentStatus.PAID
        order.save()
        
        # Hold funds in escrow
        order.escrow_status = Order.EscrowStatus.HELD
        order.save()
        
        # Deduct stock for all items
        from product_service.stock_manager import StockManager
        stock_updates = StockManager.deduct_stock_on_payment(order)
        
        # Create timeline entry
        OrderTimeline.objects.create(
            order=order,
            event_type=OrderTimeline.EventType.PAYMENT_RECEIVED,
            status=order.status,
            description=f"Payment received (Transaction: {transaction_id}). Stock deducted for {len(stock_updates)} items.",
            actor=actor
        )
        
        # Auto-confirm order after payment
        success, msg = OrderWorkflow.transition(
            order,
            Order.OrderStatus.CONFIRMED,
            actor,
            "Auto-confirmed after payment received"
        )
        
        return success, "Payment received and order confirmed"
    
    @staticmethod
    def release_escrow_to_vendor(order, vendor_order):
        """
        Release escrowed funds to vendor
        (In real implementation, this would trigger external wallet/payment system)
        """
        if vendor_order.payout_status == 'completed':
            return False, "Payout already completed for this vendor order"
        
        if order.escrow_status != Order.EscrowStatus.HELD:
            return False, "Order funds not in escrow"
        
        # Mark as released (external system would update wallet)
        vendor_order.payout_status = 'completed'
        vendor_order.released_at = timezone.now()
        vendor_order.save()
        
        # Check if all vendors have been paid
        unpaid_orders = order.vendor_orders.filter(payout_status='pending')
        if not unpaid_orders.exists():
            order.escrow_status = Order.EscrowStatus.RELEASED
            order.save()
        
        return True, f"Released {vendor_order.payout_amount} to vendor"
    
    @staticmethod
    def process_refund(order, reason, actor):
        """
        Process full or partial refund.
        Restores stock for all items when refund is processed.
        """
        if order.status != Order.OrderStatus.DELIVERED:
            return False, "Can only refund delivered orders"
        
        order.payment_status = Order.PaymentStatus.REFUNDED
        order.status = Order.OrderStatus.REFUNDED
        order.escrow_status = Order.EscrowStatus.REFUNDED
        order.save()
        
        # Restore stock for all items
        from product_service.stock_manager import StockManager
        stock_updates = []
        for order_item in order.items.all():
            update = StockManager.restore_stock_on_refund(order_item)
            stock_updates.append(update)
        
        # Update vendor orders
        for vendor_order in order.vendor_orders.all():
            vendor_order.payout_status = 'refunded'
            vendor_order.save()
        
        OrderTimeline.objects.create(
            order=order,
            event_type=OrderTimeline.EventType.REFUNDED,
            status=Order.OrderStatus.REFUNDED,
            description=f"Refund processed: {reason}. Stock restored for {len(stock_updates)} items.",
            actor=actor
        )
        
        return True, "Refund processed successfully"


class OrderValidation:
    """Validates order operations"""
    
    @staticmethod
    def can_cancel_order(order):
        """Check if order can be cancelled"""
        cancellable_statuses = [
            Order.OrderStatus.PENDING,
            Order.OrderStatus.CONFIRMED,
            Order.OrderStatus.PROCESSING,
        ]
        return order.status in cancellable_statuses
    
    @staticmethod
    def can_request_return(order):
        """Check if return can be requested"""
        return order.status == Order.OrderStatus.DELIVERED
    
    @staticmethod
    def validate_inventory(cart_items):
        """Validate inventory before checkout"""
        from product_service.models import Product
        
        issues = []
        for cart_item in cart_items:
            product = cart_item.product
            if not product.in_stock:
                issues.append(f"{product.name} is out of stock")
            elif product.stock_quantity < cart_item.quantity:
                issues.append(
                    f"{product.name} only has {product.stock_quantity} units available"
                )
        
        return len(issues) == 0, issues
    
    @staticmethod
    def validate_delivery_address(address):
        """Validate delivery address"""
        if not address:
            return False, "Delivery address required"
        
        required_fields = [
            'full_name', 'phone_number', 'address_line1',
            'city', 'state', 'country', 'postal_code'
        ]
        
        for field in required_fields:
            if not getattr(address, field, None):
                return False, f"Missing required field: {field}"
        
        return True, "Address valid"


class VendorPaymentCalculator:
    """Calculates vendor earnings and commissions"""
    
    PLATFORM_COMMISSION_RATE = Decimal('5.00')  # 5% commission
    
    @staticmethod
    def calculate_vendor_payout(order, vendor):
        """
        Calculate vendor payout from order
        Returns: {
            gross_amount,
            platform_commission,
            payout_amount,
        }
        """
        vendor_order = order.vendor_orders.filter(vendor=vendor).first()
        if not vendor_order:
            return None
        
        return {
            'gross_amount': vendor_order.subtotal,
            'platform_commission': vendor_order.commission_amount,
            'payout_amount': vendor_order.payout_amount,
        }
    
    @staticmethod
    def calculate_order_commission(order_total):
        """Calculate platform commission from order total"""
        return (order_total * VendorPaymentCalculator.PLATFORM_COMMISSION_RATE) / Decimal('100')
    
    @staticmethod
    def generate_vendor_payout_report(vendor, start_date=None, end_date=None):
        """Generate payout summary for a vendor"""
        from django.db.models import Sum
        
        orders = VendorOrder.objects.filter(
            vendor=vendor,
            payout_status='completed'
        )
        
        if start_date:
            orders = orders.filter(created_at__gte=start_date)
        if end_date:
            orders = orders.filter(created_at__lte=end_date)
        
        total = orders.aggregate(
            gross=Sum('subtotal'),
            commission=Sum('commission_amount'),
            payout=Sum('payout_amount')
        )
        
        return {
            'vendor': vendor,
            'total_gross': total['gross'] or Decimal('0'),
            'total_commission': total['commission'] or Decimal('0'),
            'total_payout': total['payout'] or Decimal('0'),
            'order_count': orders.count(),
            'period': {
                'start_date': start_date,
                'end_date': end_date,
            }
        }
