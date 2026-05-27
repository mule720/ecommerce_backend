"""
Stock Management Utilities
Handles inventory deduction, alerts, and notifications
"""
from django.utils import timezone
from decimal import Decimal
from product_service.models import Product
from .vendor_management_models import StockAlert


class StockManager:
    """Manages stock operations including deduction and alerts"""
    
    # Low stock threshold (as percentage of typical quantity)
    LOW_STOCK_THRESHOLD_PERCENT = 20  # 20% of normal stock
    
    @staticmethod
    def deduct_stock_on_payment(order):
        """
        Deduct stock for all items when order payment is received.
        Called from PaymentWorkflow.mark_payment_received()
        """
        from order_service.models import OrderItem
        
        stock_updates = []
        
        # Get all order items
        order_items = order.items.select_related('product')
        
        for order_item in order_items:
            product = order_item.product
            old_quantity = product.quantity
            new_quantity = old_quantity - order_item.quantity
            
            # Update product stock
            product.quantity = max(0, new_quantity)
            product.save(update_fields=['quantity', 'updated_at'])
            
            stock_updates.append({
                'product_id': product.id,
                'product': product,
                'old_quantity': old_quantity,
                'deducted': order_item.quantity,
                'new_quantity': product.quantity,
                'order_id': order.id,
            })
            
            # Check if we need to create stock alerts
            StockManager.check_and_create_alerts(product)
        
        return stock_updates
    
    @staticmethod
    def check_and_create_alerts(product):
        """Create stock alerts if conditions are met"""
        if product.quantity <= 0:
            # Out of stock alert
            existing_alert = StockAlert.objects.filter(
                product=product,
                alert_type=StockAlert.AlertType.OUT_OF_STOCK,
                status=StockAlert.AlertStatus.ACTIVE
            ).first()
            
            if not existing_alert:
                StockAlert.objects.create(
                    product=product,
                    alert_type=StockAlert.AlertType.OUT_OF_STOCK,
                    current_quantity=product.quantity,
                    threshold_quantity=0
                )
        else:
            # Check if low stock
            # Calculate low stock threshold (20% of recent average or fixed minimum)
            low_stock_threshold = max(10, int(product.quantity * 1.25))  # If we have 10 items, low stock is when we hit 8
            
            if product.quantity < low_stock_threshold:
                # Check if alert already exists
                existing_alert = StockAlert.objects.filter(
                    product=product,
                    alert_type=StockAlert.AlertType.LOW_STOCK,
                    status=StockAlert.AlertStatus.ACTIVE
                ).first()
                
                if not existing_alert:
                    StockAlert.objects.create(
                        product=product,
                        alert_type=StockAlert.AlertType.LOW_STOCK,
                        current_quantity=product.quantity,
                        threshold_quantity=low_stock_threshold
                    )
            else:
                # Clear low stock alerts if stock is back to normal
                StockAlert.objects.filter(
                    product=product,
                    alert_type=StockAlert.AlertType.LOW_STOCK,
                    status=StockAlert.AlertStatus.ACTIVE
                ).update(
                    status=StockAlert.AlertStatus.RESOLVED,
                    resolved_at=timezone.now()
                )
                
                # Check for back in stock
                out_of_stock_alert = StockAlert.objects.filter(
                    product=product,
                    alert_type=StockAlert.AlertType.OUT_OF_STOCK,
                    status=StockAlert.AlertStatus.ACTIVE
                ).first()
                
                if out_of_stock_alert:
                    out_of_stock_alert.status = StockAlert.AlertStatus.RESOLVED
                    out_of_stock_alert.resolved_at = timezone.now()
                    out_of_stock_alert.save()
                    
                    # Create back in stock alert
                    StockAlert.objects.create(
                        product=product,
                        alert_type=StockAlert.AlertType.BACK_IN_STOCK,
                        current_quantity=product.quantity,
                        threshold_quantity=1
                    )
    
    @staticmethod
    def adjust_inventory(product, quantity_delta, reason="Manual adjustment"):
        """
        Adjust inventory for a product (used for manual corrections, returns, etc.)
        quantity_delta: positive for adding stock, negative for removing
        """
        old_quantity = product.quantity
        product.quantity = max(0, product.quantity + quantity_delta)
        product.save(update_fields=['quantity', 'updated_at'])
        
        # Check alerts
        StockManager.check_and_create_alerts(product)
        
        return {
            'product_id': product.id,
            'old_quantity': old_quantity,
            'delta': quantity_delta,
            'new_quantity': product.quantity,
            'reason': reason,
        }
    
    @staticmethod
    def restore_stock_on_refund(order_item):
        """Restore stock when order item is refunded"""
        product = order_item.product
        old_quantity = product.quantity
        product.quantity += order_item.quantity
        product.save(update_fields=['quantity', 'updated_at'])
        
        # Check alerts
        StockManager.check_and_create_alerts(product)
        
        return {
            'product_id': product.id,
            'old_quantity': old_quantity,
            'restored': order_item.quantity,
            'new_quantity': product.quantity,
        }
    
    @staticmethod
    def get_stock_summary_for_vendor(vendor):
        """Get stock summary for vendor dashboard"""
        from django.db.models import Count, Q, Sum
        
        products = Product.objects.filter(vendor=vendor)
        
        summary = {
            'total_products': products.count(),
            'in_stock_products': products.filter(quantity__gt=0).count(),
            'out_of_stock_products': products.filter(quantity=0).count(),
            'low_stock_products': StockAlert.objects.filter(
                product__vendor=vendor,
                alert_type=StockAlert.AlertType.LOW_STOCK,
                status=StockAlert.AlertStatus.ACTIVE
            ).values('product').distinct().count(),
            'total_inventory_value': products.aggregate(
                total=Sum('quantity')
            )['total'] or 0,
            'active_alerts': StockAlert.objects.filter(
                product__vendor=vendor,
                status=StockAlert.AlertStatus.ACTIVE
            ).count(),
        }
        
        return summary
    
    @staticmethod
    def bulk_update_inventory(vendor, inventory_updates):
        """
        Bulk update inventory for multiple products
        inventory_updates: List of {'sku': 'ABC123', 'quantity': 50} dicts
        """
        results = []
        
        for update in inventory_updates:
            sku = update.get('sku')
            quantity = update.get('quantity')
            
            if not sku or quantity is None:
                results.append({
                    'sku': sku,
                    'success': False,
                    'message': 'Missing SKU or quantity'
                })
                continue
            
            try:
                product = Product.objects.get(vendor=vendor, sku=sku)
                old_quantity = product.quantity
                product.quantity = int(quantity)
                product.save(update_fields=['quantity', 'updated_at'])
                
                # Check alerts
                StockManager.check_and_create_alerts(product)
                
                results.append({
                    'sku': sku,
                    'success': True,
                    'old_quantity': old_quantity,
                    'new_quantity': product.quantity,
                })
            except Product.DoesNotExist:
                results.append({
                    'sku': sku,
                    'success': False,
                    'message': f'Product with SKU {sku} not found'
                })
        
        return results
