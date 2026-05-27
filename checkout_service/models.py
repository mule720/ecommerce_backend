"""
Checkout Service Models
Manages checkout sessions and order creation
"""
from django.db import models
from django.conf import settings
from cart_service.models import Cart
from product_service.models import Product
from user_service.auth_models import DeliveryAddress
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from decimal import Decimal, ROUND_HALF_UP


class ShippingMethod(models.Model):
    """Available shipping methods"""
    
    class ShippingType(models.TextChoices):
        PICKUP = 'pickup', _('Customer Pickup')
        STANDARD = 'standard', _('Standard Delivery')
        EXPRESS = 'express', _('Express Delivery')
        SAME_DAY = 'same_day', _('Same Day Delivery')
    
    name = models.CharField(max_length=100)
    shipping_type = models.CharField(
        max_length=20,
        choices=ShippingType.choices,
        unique=True
    )
    base_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    estimated_days = models.IntegerField(default=5)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'checkout_service_shipping_methods'
        ordering = ['base_cost']
    
    def __str__(self):
        return f"{self.name} (${self.base_cost})"


class CheckoutSession(models.Model):
    """Checkout session for order creation"""
    
    class CheckoutStatus(models.TextChoices):
        ACTIVE = 'active', _('Active')
        COMPLETED = 'completed', _('Completed')
        ABANDONED = 'abandoned', _('Abandoned')
        EXPIRED = 'expired', _('Expired')
    
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='checkout_sessions')
    cart = models.ForeignKey(Cart, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=CheckoutStatus.choices,
        default=CheckoutStatus.ACTIVE
    )
    
    # Address info
    delivery_address = models.ForeignKey(
        DeliveryAddress,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    # Shipping info
    shipping_method = models.ForeignKey(
        ShippingMethod,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    # Pricing
    subtotal = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField()
    
    class Meta:
        db_table = 'checkout_sessions'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Checkout {self.id} for {self.customer.username}"
    
    def is_expired(self):
        """Check if checkout session has expired"""
        return timezone.now() > self.expires_at
    
    def calculate_totals(self):
        """Calculate totals for this checkout"""
        if not self.cart:
            return

        subtotal = self.cart.get_total()
        self.subtotal = Decimal(str(subtotal)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        self.shipping_cost = (
            Decimal(str(self.shipping_method.base_cost)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            if self.shipping_method
            else Decimal('0.00')
        )

        # Simple tax calculation: 8.8% of subtotal
        self.tax_amount = (self.subtotal * Decimal('0.088')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        self.total = self.subtotal + self.shipping_cost + self.tax_amount
        self.save()
    
    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'id': self.id,
            'customer': self.customer.username,
            'status': self.status,
            'deliveryAddress': self.delivery_address.to_dict() if self.delivery_address else None,
            'shippingMethod': {
                'id': self.shipping_method.id,
                'name': self.shipping_method.name,
                'type': self.shipping_method.shipping_type,
                'cost': float(self.shipping_method.base_cost),
                'estimatedDays': self.shipping_method.estimated_days,
            } if self.shipping_method else None,
            'subtotal': float(self.subtotal),
            'shippingCost': float(self.shipping_cost),
            'taxAmount': float(self.tax_amount),
            'total': float(self.total),
            'createdAt': self.created_at.isoformat(),
            'expiresAt': self.expires_at.isoformat(),
        }
