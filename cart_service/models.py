"""
Cart Service Models
Shopping cart management for multi-vendor purchases
"""
from django.db import models
from django.conf import settings
from product_service.models import Product
from django.utils.translation import gettext_lazy as _
from decimal import Decimal


class Cart(models.Model):
    """Shopping cart for a customer"""
    customer = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='cart'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'cart_service_carts'
        ordering = ['-updated_at']

    def __str__(self):
        return f"Cart for {self.customer.username}"

    def get_total(self):
        """Calculate total price of all items in cart"""
        items = self.items.all()
        return sum((item.get_subtotal() for item in items), Decimal('0.00'))

    def get_items_count(self):
        """Get total number of items in cart"""
        return self.items.aggregate(total=models.Sum('quantity'))['total'] or 0

    def get_grouped_by_vendor(self):
        """Group cart items by vendor"""
        items = self.items.select_related('product', 'product__vendor')
        grouped = {}
        for item in items:
            vendor_id = item.product.vendor.id
            if vendor_id not in grouped:
                grouped[vendor_id] = {
                    'vendor': item.product.vendor,
                    'items': []
                }
            grouped[vendor_id]['items'].append(item)
        return grouped


class CartItem(models.Model):
    """Individual item in a shopping cart"""
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'cart_service_cart_items'
        unique_together = ['cart', 'product']
        ordering = ['-added_at']

    def __str__(self):
        return f"{self.product.name} x{self.quantity} in {self.cart.customer.username}'s cart"

    def get_subtotal(self):
        """Calculate subtotal for this cart item"""
        return Decimal(str(self.product.price)) * Decimal(str(self.quantity))

    def get_product_info(self):
        """Get product info for serialization"""
        return {
            'id': self.product.id,
            'name': self.product.name,
            'price': float(self.product.price),
            'compareAtPrice': float(self.product.compare_at_price) if self.product.compare_at_price else None,
            'image': self.product.get_primary_image(),
            'vendor': {
                'id': self.product.vendor.id,
                'businessName': self.product.vendor.vendor_profile.business_name if hasattr(self.product.vendor, 'vendor_profile') else 'Store'
            }
        }
