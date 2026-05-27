"""
Order Service Models
Multi-vendor e-commerce order management
"""
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from decimal import Decimal


class Order(models.Model):
    """Order model for multi-vendor e-commerce"""
    
    class OrderStatus(models.TextChoices):
        PENDING = 'pending', _('Pending')
        CONFIRMED = 'confirmed', _('Confirmed')
        PROCESSING = 'processing', _('Processing')
        SHIPPED = 'shipped', _('Shipped')
        OUT_FOR_DELIVERY = 'out_for_delivery', _('Out for Delivery')
        DELIVERED = 'delivered', _('Delivered')
        CANCELLED = 'cancelled', _('Cancelled')
        REFUNDED = 'refunded', _('Refunded')
    
    class PaymentStatus(models.TextChoices):
        PENDING = 'pending', _('Pending')
        PAID = 'paid', _('Paid')
        FAILED = 'failed', _('Failed')
        REFUNDED = 'refunded', _('Refunded')
    
    order_number = models.CharField(max_length=50, unique=True)
    erp_sync_status = models.CharField(max_length=20, default='pending')
    erp_sync_reference = models.CharField(max_length=120, blank=True)
    last_synced_with_erp_at = models.DateTimeField(null=True, blank=True)
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='orders'
    )
    status = models.CharField(
        max_length=30,
        choices=OrderStatus.choices,
        default=OrderStatus.PENDING
    )
    payment_status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING
    )
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    shipping_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Multi-currency support
    currency = models.CharField(max_length=3, default='USD')
    base_currency = models.CharField(
        max_length=3,
        default='USD',
        help_text="Currency in which product prices are stored"
    )
    exchange_rate = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        default=Decimal('1.0'),
        help_text="Exchange rate from base_currency to currency at time of order"
    )
    exchange_rate_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date of the exchange rate used"
    )
    
    # Shipping information
    shipping_first_name = models.CharField(max_length=100)
    shipping_last_name = models.CharField(max_length=100)
    shipping_email = models.EmailField()
    shipping_phone = models.CharField(max_length=20)
    shipping_address = models.TextField()
    shipping_city = models.CharField(max_length=100)
    shipping_state = models.CharField(max_length=100)
    shipping_country = models.CharField(max_length=100, help_text="Used for tax calculations")
    shipping_postal_code = models.CharField(max_length=20)
    
    # New shipping method fields
    shipping_method = models.CharField(max_length=50, blank=True)
    tracking_number = models.CharField(max_length=100, blank=True)
    shipping_provider = models.CharField(max_length=100, blank=True)
    estimated_delivery = models.DateTimeField(null=True, blank=True)
    
    # Billing information
    billing_first_name = models.CharField(max_length=100)
    billing_last_name = models.CharField(max_length=100)
    billing_email = models.EmailField()
    billing_phone = models.CharField(max_length=20)
    billing_address = models.TextField()
    billing_city = models.CharField(max_length=100)
    billing_state = models.CharField(max_length=100)
    billing_country = models.CharField(max_length=100)
    billing_postal_code = models.CharField(max_length=20)
    
    # Payment method and escrow
    payment_method = models.CharField(
        max_length=50,
        default='wallet',
        choices=[
            ('wallet', 'Wallet'),
            ('card', 'Credit/Debit Card'),
            ('mobile_money', 'Mobile Money'),
            ('bank_transfer', 'Bank Transfer'),
        ]
    )
    
    class EscrowStatus(models.TextChoices):
        PENDING = 'pending', _('Pending')
        HELD = 'held', _('Held')
        RELEASED = 'released', _('Released')
        REFUNDED = 'refunded', _('Refunded')
    
    escrow_status = models.CharField(
        max_length=20,
        choices=EscrowStatus.choices,
        default=EscrowStatus.PENDING
    )
    platform_commission = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Platform commission on this order"
    )
    platform_commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('5.00'),
        help_text="Commission rate as percentage"
    )
    
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'orders'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['customer', 'status']),
            models.Index(fields=['order_number']),
        ]
    
    def __str__(self):
        return f"Order {self.order_number}"
    
    def calculate_total(self):
        """Calculate order total with currency conversion applied"""
        self.total = (self.subtotal + self.tax_amount + self.shipping_amount - self.discount_amount)
        return self.total
    
    def set_currency(self, currency_code: str, exchange_rate: Decimal = None):
        """Set order currency and exchange rate"""
        from ecom_backend.multi_currency import ExchangeRate, Currency
        from django.utils import timezone
        
        try:
            # Verify currency exists
            currency = Currency.objects.get(code=currency_code, is_active=True)
            self.currency = currency_code
            
            # Get exchange rate if not provided
            if exchange_rate is None and self.base_currency != currency_code:
                exchange_rate = ExchangeRate.get_rate(
                    self.base_currency,
                    currency_code,
                    timezone.now().date()
                )
            
            if exchange_rate:
                self.exchange_rate = exchange_rate
                self.exchange_rate_date = timezone.now().date()
        
        except Currency.DoesNotExist:
            raise ValueError(f"Currency {currency_code} not found or inactive")
    
    def get_tax_amount(self) -> Decimal:
        """Calculate tax based on shipping country and currency"""
        from ecom_backend.pricing_utils import TaxCalculator
        
        return TaxCalculator.calculate_tax(
            self.subtotal,
            self.shipping_country,
            self.shipping_state,
            self.currency
        )
    
    def apply_tax(self):
        """Calculate and apply tax to this order"""
        self.tax_amount = self.get_tax_amount()
        self.save()

    def mark_erp_synced(self, reference: str = ''):
        self.erp_sync_status = 'synced'
        if reference:
            self.erp_sync_reference = reference
        self.last_synced_with_erp_at = timezone.now()
        self.save(update_fields=['erp_sync_status', 'erp_sync_reference', 'last_synced_with_erp_at', 'updated_at'])


class OrderItem(models.Model):
    """Individual items in an order"""
    
    class ItemStatus(models.TextChoices):
        PENDING = 'pending', _('Pending')
        CONFIRMED = 'confirmed', _('Confirmed')
        SHIPPED = 'shipped', _('Shipped')
        DELIVERED = 'delivered', _('Delivered')
        CANCELLED = 'cancelled', _('Cancelled')
        RETURNED = 'returned', _('Returned')
    
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items'
    )
    vendor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='order_items'
    )
    product_name = models.CharField(max_length=200)
    product_image = models.CharField(max_length=500, blank=True)
    sku = models.CharField(max_length=100, blank=True)
    quantity = models.IntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(
        max_length=20,
        choices=ItemStatus.choices,
        default=ItemStatus.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'order_items'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.product_name} x {self.quantity}"
    
    def save(self, *args, **kwargs):
        self.total = (self.price * self.quantity) + self.tax_amount - self.discount_amount
        super().save(*args, **kwargs)


class Cart(models.Model):
    """Shopping cart with multi-currency support"""
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='order_cart'
    )
    currency = models.CharField(
        max_length=3,
        default='USD',
        help_text="Currency for pricing in this cart"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'order_service_carts'
    
    def __str__(self):
        return f"Cart for {self.customer.username} ({self.currency})"
    
    @property
    def total(self):
        items = self.items.all()
        return sum(item.get_total_price() for item in items)
    
    @property
    def item_count(self):
        return self.items.count()
    
    def set_currency(self, currency_code: str):
        """Change cart currency and recalculate prices"""
        from ecom_backend.multi_currency import Currency
        
        try:
            currency = Currency.objects.get(code=currency_code, is_active=True)
            self.currency = currency_code
            self.save()
        except Currency.DoesNotExist:
            raise ValueError(f"Currency {currency_code} not found or inactive")


class CartItem(models.Model):
    """Items in shopping cart with currency-aware pricing"""
    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name='items'
    )
    product = models.ForeignKey(
        'product_service.Product',
        on_delete=models.CASCADE,
        related_name='cart_items'
    )
    quantity = models.IntegerField(default=1)
    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Cached unit price in cart's currency at time of adding"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'order_service_cart_items'
        unique_together = ['cart', 'product']
    
    def __str__(self):
        return f"{self.product.name} x {self.quantity}"
    
    def get_unit_price(self):
        """Get product price in cart's currency"""
        if self.unit_price:
            return self.unit_price
        
        # Get price for cart's currency
        pricing = self.product.get_price_for_currency(self.cart.currency)
        if pricing:
            return pricing['price']
        
        return self.product.price
    
    def get_total_price(self) -> Decimal:
        """Calculate total price for this item in cart currency"""
        return self.get_unit_price() * self.quantity
    
    def update_price_for_currency(self):
        """Update cached unit price for current cart currency"""
        pricing = self.product.get_price_for_currency(self.cart.currency)
        if pricing:
            self.unit_price = pricing['price']
            self.save()


class OrderTimeline(models.Model):
    """Track order status changes and events"""
    
    class EventType(models.TextChoices):
        ORDER_CREATED = 'order_created', _('Order Created')
        PAYMENT_PENDING = 'payment_pending', _('Payment Pending')
        PAYMENT_RECEIVED = 'payment_received', _('Payment Received')
        CONFIRMED = 'confirmed', _('Confirmed')
        PROCESSING = 'processing', _('Processing')
        PACKED = 'packed', _('Packed')
        SHIPPED = 'shipped', _('Shipped')
        IN_TRANSIT = 'in_transit', _('In Transit')
        OUT_FOR_DELIVERY = 'out_for_delivery', _('Out for Delivery')
        DELIVERED = 'delivered', _('Delivered')
        CANCELLED = 'cancelled', _('Cancelled')
        RETURNED = 'returned', _('Returned')
        REFUNDED = 'refunded', _('Refunded')
    
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='timeline'
    )
    event_type = models.CharField(
        max_length=50,
        choices=EventType.choices
    )
    status = models.CharField(
        max_length=30,
        choices=Order.OrderStatus.choices
    )
    description = models.TextField(blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='order_timeline_events'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'order_timeline'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['order', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.order.order_number} - {self.event_type}"


class VendorOrder(models.Model):
    """Vendor-specific order grouping (one order can have items from multiple vendors)"""
    
    class VendorOrderStatus(models.TextChoices):
        PENDING = 'pending', _('Pending')
        CONFIRMED = 'confirmed', _('Confirmed')
        PROCESSING = 'processing', _('Processing')
        SHIPPED = 'shipped', _('Shipped')
        DELIVERED = 'delivered', _('Delivered')
        CANCELLED = 'cancelled', _('Cancelled')
        REFUNDED = 'refunded', _('Refunded')
    
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='vendor_orders'
    )
    vendor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='vendor_orders'
    )
    status = models.CharField(
        max_length=20,
        choices=VendorOrderStatus.choices,
        default=VendorOrderStatus.PENDING
    )
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    commission_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    payout_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    payout_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('processing', 'Processing'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
        ],
        default='pending'
    )
    tracking_number = models.CharField(max_length=100, blank=True)
    shipping_provider = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'vendor_orders'
        unique_together = ['order', 'vendor']
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['vendor', 'status']),
            models.Index(fields=['order']),
        ]
    
    def __str__(self):
        return f"Vendor Order {self.id} - {self.vendor.username}"
    
    def calculate_payout(self):
        """Calculate vendor payout (subtotal - commission)"""
        self.payout_amount = self.subtotal - self.commission_amount
        return self.payout_amount


class ReturnRequest(models.Model):
    """Product return requests"""
    
    class ReturnStatus(models.TextChoices):
        PENDING = 'pending', _('Pending')
        APPROVED = 'approved', _('Approved')
        REJECTED = 'rejected', _('Rejected')
        COMPLETED = 'completed', _('Completed')
    
    order_item = models.ForeignKey(
        OrderItem,
        on_delete=models.CASCADE,
        related_name='return_requests'
    )
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='return_requests'
    )
    reason = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=ReturnStatus.choices,
        default=ReturnStatus.PENDING
    )
    refund_amount = models.DecimalField(max_digits=10, decimal_places=2)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'return_requests'
        ordering = ['-created_at']
