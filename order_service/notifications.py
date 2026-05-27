"""
Order Notification Service
Handles sending notifications to customers, vendors, and shipping companies
"""
from django.utils import timezone
from .models import Order, OrderTimeline, VendorOrder


class OrderNotificationService:
    """Manages order-related notifications"""
    
    # Notification types
    ORDER_CREATED = 'order_created'
    ORDER_CONFIRMED = 'order_confirmed'
    ORDER_PROCESSING = 'order_processing'
    ORDER_SHIPPED = 'order_shipped'
    ORDER_OUT_FOR_DELIVERY = 'order_out_for_delivery'
    ORDER_DELIVERED = 'order_delivered'
    ORDER_CANCELLED = 'order_cancelled'
    PAYMENT_RECEIVED = 'payment_received'
    SHIPMENT_READY = 'shipment_ready'
    
    @staticmethod
    def notify_customer_order_created(order):
        """Notify customer that order was created"""
        notification_data = {
            'order_id': order.id,
            'order_number': order.order_number,
            'total': str(order.total),
            'currency': order.currency,
        }
        
        return {
            'recipient_type': 'customer',
            'recipient_id': order.customer.id,
            'notification_type': OrderNotificationService.ORDER_CREATED,
            'title': f'Order {order.order_number} Created',
            'message': f'Your order of {order.currency} {order.total} has been placed',
            'data': notification_data,
            'action_url': f'/orders/{order.id}',
        }
    
    @staticmethod
    def notify_vendor_order_received(order, vendor):
        """Notify vendor they have a new order"""
        vendor_order = order.vendor_orders.filter(vendor=vendor).first()
        if not vendor_order:
            return None
        
        items_count = order.items.filter(vendor=vendor).count()
        
        notification_data = {
            'order_id': order.id,
            'vendor_order_id': vendor_order.id,
            'order_number': order.order_number,
            'items_count': items_count,
            'amount': str(vendor_order.subtotal),
        }
        
        return {
            'recipient_type': 'vendor',
            'recipient_id': vendor.id,
            'notification_type': OrderNotificationService.ORDER_CREATED,
            'title': f'New Order: {order.order_number}',
            'message': f'You have a new order with {items_count} item(s)',
            'data': notification_data,
            'action_url': f'/merchant-orders/{order.id}',
        }
    
    @staticmethod
    def notify_customer_order_confirmed(order):
        """Notify customer order is confirmed"""
        return {
            'recipient_type': 'customer',
            'recipient_id': order.customer.id,
            'notification_type': OrderNotificationService.ORDER_CONFIRMED,
            'title': f'Order {order.order_number} Confirmed',
            'message': 'Your order has been confirmed and vendors are preparing it',
            'data': {'order_id': order.id},
            'action_url': f'/orders/{order.id}',
        }
    
    @staticmethod
    def notify_customer_payment_received(order):
        """Notify customer payment was received"""
        return {
            'recipient_type': 'customer',
            'recipient_id': order.customer.id,
            'notification_type': OrderNotificationService.PAYMENT_RECEIVED,
            'title': 'Payment Received',
            'message': f'We received your payment of {order.currency} {order.total}',
            'data': {'order_id': order.id},
            'action_url': f'/orders/{order.id}',
        }
    
    @staticmethod
    def notify_customer_order_shipped(order):
        """Notify customer order is shipped"""
        tracking_info = {
            'tracking_number': order.tracking_number,
            'shipping_provider': order.shipping_provider,
            'estimated_delivery': order.estimated_delivery.isoformat() if order.estimated_delivery else None,
        }
        
        return {
            'recipient_type': 'customer',
            'recipient_id': order.customer.id,
            'notification_type': OrderNotificationService.ORDER_SHIPPED,
            'title': f'Order {order.order_number} Shipped',
            'message': f'Your order is on its way! Tracking: {order.tracking_number}',
            'data': {
                'order_id': order.id,
                **tracking_info
            },
            'action_url': f'/orders/{order.id}/tracking',
        }
    
    @staticmethod
    def notify_customer_order_delivered(order):
        """Notify customer order was delivered"""
        return {
            'recipient_type': 'customer',
            'recipient_id': order.customer.id,
            'notification_type': OrderNotificationService.ORDER_DELIVERED,
            'title': f'Order {order.order_number} Delivered',
            'message': 'Your order has been delivered. Please confirm receipt.',
            'data': {'order_id': order.id},
            'action_url': f'/orders/{order.id}',
        }
    
    @staticmethod
    def notify_customer_order_cancelled(order, reason=''):
        """Notify customer order was cancelled"""
        return {
            'recipient_type': 'customer',
            'recipient_id': order.customer.id,
            'notification_type': OrderNotificationService.ORDER_CANCELLED,
            'title': f'Order {order.order_number} Cancelled',
            'message': f'Your order has been cancelled. {reason}' if reason else 'Your order has been cancelled.',
            'data': {'order_id': order.id, 'reason': reason},
            'action_url': f'/orders/{order.id}',
        }
    
    @staticmethod
    def notify_customer_ready_for_pickup(order):
        """Notify customer order is ready for pickup (if using pickup method)"""
        return {
            'recipient_type': 'customer',
            'recipient_id': order.customer.id,
            'notification_type': OrderNotificationService.SHIPMENT_READY,
            'title': f'Order {order.order_number} Ready for Pickup',
            'message': 'Your order is ready for pickup at the store',
            'data': {'order_id': order.id},
            'action_url': f'/orders/{order.id}',
        }


class VendorPaymentNotificationService:
    """Manages vendor payment notifications"""
    
    PAYOUT_RELEASED = 'payout_released'
    PAYOUT_PENDING = 'payout_pending'
    
    @staticmethod
    def notify_vendor_payout_released(vendor, vendor_order):
        """Notify vendor their payout was released"""
        return {
            'recipient_type': 'vendor',
            'recipient_id': vendor.id,
            'notification_type': VendorPaymentNotificationService.PAYOUT_RELEASED,
            'title': 'Payment Released',
            'message': f'We released {vendor_order.payout_amount} to your account for order {vendor_order.order.order_number}',
            'data': {
                'vendor_order_id': vendor_order.id,
                'amount': str(vendor_order.payout_amount),
            },
            'action_url': '/merchant-earnings',
        }
    
    @staticmethod
    def notify_vendor_pending_payout(vendor, total_pending):
        """Notify vendor they have pending payouts"""
        return {
            'recipient_type': 'vendor',
            'recipient_id': vendor.id,
            'notification_type': VendorPaymentNotificationService.PAYOUT_PENDING,
            'title': 'Pending Payments',
            'message': f'You have pending payments totaling {total_pending} awaiting release',
            'data': {'total_amount': total_pending},
            'action_url': '/merchant-earnings',
        }


class ShippingNotificationService:
    """Manages shipping company notifications"""
    
    SHIPMENT_READY = 'shipment_ready'
    PICK_UP_REQUEST = 'pick_up_request'
    
    @staticmethod
    def notify_shipping_company_pickup(order):
        """Notify shipping company to pick up order"""
        shipping_info = {
            'order_number': order.order_number,
            'recipient_name': f"{order.shipping_first_name} {order.shipping_last_name}",
            'recipient_phone': order.shipping_phone,
            'pickup_address': order.shipping_address,
            'city': order.shipping_city,
            'postal_code': order.shipping_postal_code,
            'weight': 'TBD',  # Would be calculated from items
        }
        
        return {
            'recipient_type': 'shipping_company',
            'shipping_provider': order.shipping_provider,
            'notification_type': ShippingNotificationService.PICK_UP_REQUEST,
            'title': f'Pickup Request: {order.order_number}',
            'message': f'Order {order.order_number} is ready for pickup',
            'data': shipping_info,
        }
    
    @staticmethod
    def update_tracking_info(order, tracking_number, status=''):
        """Update order with tracking info from shipping company"""
        order.tracking_number = tracking_number
        if status:
            # Map external provider status to our status
            pass
        order.save()
        
        return {
            'order_id': order.id,
            'tracking_number': tracking_number,
            'updated_at': timezone.now().isoformat(),
        }
