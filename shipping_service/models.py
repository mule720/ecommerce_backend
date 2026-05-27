"""
Shipping Service Models
Multi-vendor e-commerce shipping management
"""
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from decimal import Decimal


class ShippingZone(models.Model):
    """Shipping zones for different regions"""
    name = models.CharField(max_length=100)
    countries = models.JSONField(default=list)
    regions = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'shipping_zones'
    
    def __str__(self):
        return self.name


class ShippingMethod(models.Model):
    """Shipping methods within zones"""
    
    class MethodType(models.TextChoices):
        STANDARD = 'standard', _('Standard Shipping')
        EXPRESS = 'express', _('Express Shipping')
        OVERNIGHT = 'overnight', _('Overnight Shipping')
        PICKUP = 'pickup', _('Store Pickup')
        FREE = 'free', _('Free Shipping')
    
    zone = models.ForeignKey(
        ShippingZone,
        on_delete=models.CASCADE,
        related_name='methods'
    )
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=20, choices=MethodType.choices)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    free_shipping_threshold = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    estimated_days = models.IntegerField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'shipping_methods'
    
    def __str__(self):
        return f"{self.name} - {self.price}"


class Shipment(models.Model):
    """Shipment tracking for orders"""
    
    class ShipmentStatus(models.TextChoices):
        PENDING = 'pending', _('Pending')
        PICKED_UP = 'picked_up', _('Picked Up')
        IN_TRANSIT = 'in_transit', _('In Transit')
        OUT_FOR_DELIVERY = 'out_for_delivery', _('Out for Delivery')
        DELIVERED = 'delivered', _('Delivered')
        FAILED = 'failed', _('Failed')
        RETURNED = 'returned', _('Returned')
    
    order = models.ForeignKey(
        'order_service.Order',
        on_delete=models.CASCADE,
        related_name='shipments'
    )
    order_item = models.ForeignKey(
        'order_service.OrderItem',
        on_delete=models.CASCADE,
        related_name='shipments',
        null=True,
        blank=True
    )
    vendor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='shipments'
    )
    driver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='deliveries'
    )
    shipping_method = models.ForeignKey(
        ShippingMethod,
        on_delete=models.CASCADE,
        related_name='shipments'
    )
    status = models.CharField(
        max_length=20,
        choices=ShipmentStatus.choices,
        default=ShipmentStatus.PENDING
    )
    tracking_number = models.CharField(max_length=100, unique=True)
    carrier = models.CharField(max_length=100)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2)
    estimated_delivery = models.DateField(null=True, blank=True)
    actual_delivery = models.DateTimeField(null=True, blank=True)
    shipping_label_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'shipments'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Shipment {self.tracking_number}"


class ShipmentEvent(models.Model):
    """Tracking events for shipments"""
    shipment = models.ForeignKey(
        Shipment,
        on_delete=models.CASCADE,
        related_name='events'
    )
    status = models.CharField(max_length=50)
    location = models.CharField(max_length=200)
    description = models.TextField()
    timestamp = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'shipment_events'
        ordering = ['-timestamp']


class DeliveryAddress(models.Model):
    """Saved delivery addresses for customers"""
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='delivery_addresses'
    )
    label = models.CharField(max_length=50, default='Home')
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    address = models.TextField()
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'shipping_service_delivery_addresses'
    
    def __str__(self):
        return f"{self.label} - {self.city}"
