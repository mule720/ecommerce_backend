"""
Product Service Models
Multi-vendor e-commerce product management
"""
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.utils import timezone


class Category(models.Model):
    """Product categories for organizing products"""
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children'
    )
    image = models.ImageField(upload_to='categories/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'categories'
        verbose_name_plural = 'categories'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class Product(models.Model):
    """Product model for multi-vendor e-commerce"""
    
    class ProductStatus(models.TextChoices):
        DRAFT = 'draft', _('Draft')
        ACTIVE = 'active', _('Active')
        INACTIVE = 'inactive', _('Inactive')
        DELETED = 'deleted', _('Deleted')
    
    vendor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='products'
    )
    erp_tenant_id = models.CharField(max_length=100, blank=True)
    erp_vendor_id = models.CharField(max_length=100, blank=True)
    erp_product_id = models.CharField(max_length=100, blank=True)
    last_inventory_sync_at = models.DateTimeField(null=True, blank=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        related_name='products'
    )
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220)
    description = models.TextField()
    # Optional short product demo/marketing video (one video per product).
    video = models.FileField(upload_to='products/videos/', blank=True, null=True)
    # Optional external video link (for CDN/YouTube/Vimeo-hosted videos).
    video_url = models.URLField(blank=True)
    
    # Base currency for pricing
    base_currency = models.CharField(
        max_length=3,
        default='USD',
        help_text="Base currency for this product. Prices in other currencies are converted from this."
    )
    
    # Legacy price fields (kept for backward compatibility, but use ProductPricing for multi-currency)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    compare_at_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True
    )
    cost_per_item = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Vendor's cost for the item"
    )
    quantity = models.IntegerField(default=0)
    sku = models.CharField(max_length=100, unique=True, blank=True)
    barcode = models.CharField(max_length=100, blank=True)
    weight = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    weight_unit = models.CharField(max_length=10, default='kg')
    status = models.CharField(
        max_length=20,
        choices=ProductStatus.choices,
        default=ProductStatus.DRAFT
    )
    is_featured = models.BooleanField(default=False)
    is_taxable = models.BooleanField(default=True)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    meta_title = models.CharField(max_length=200, blank=True)
    meta_description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'products'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['vendor', 'status']),
            models.Index(fields=['category', 'status']),
            models.Index(fields=['slug']),
        ]
    
    def __str__(self):
        return self.name

    def mark_inventory_synced(self):
        self.last_inventory_sync_at = timezone.now()
        self.save(update_fields=['last_inventory_sync_at', 'updated_at'])
    
    def get_price_for_currency(self, currency_code: str):
        """
        Get product price in specified currency
        Returns price from ProductPricing model with automatic conversion if needed
        """
        from ecom_backend.pricing_utils import PricingCalculator
        return PricingCalculator.get_product_price_in_currency(self, currency_code)
    
    def get_available_currencies(self):
        """Get all currencies this product is priced in"""
        from ecom_backend.multi_currency import ProductPricing
        return ProductPricing.objects.filter(
            product=self,
            is_active=True
        ).values_list('currency__code', flat=True)
    
    def create_currency_pricing(self, currency_code: str, price, compare_at_price=None, cost=None):
        """Create pricing for a specific currency"""
        from ecom_backend.multi_currency import ProductPricing, Currency
        
        try:
            currency = Currency.objects.get(code=currency_code)
            pricing, created = ProductPricing.objects.update_or_create(
                product=self,
                currency=currency,
                defaults={
                    'price': price,
                    'compare_at_price': compare_at_price,
                    'cost': cost,
                    'is_base_currency': (currency_code == self.base_currency),
                }
            )
            return pricing, created
        except Currency.DoesNotExist:
            raise ValueError(f"Currency {currency_code} not found")


class ProductImage(models.Model):
    """Product images"""
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='images'
    )
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    external_url = models.URLField(blank=True)
    alt_text = models.CharField(max_length=200, blank=True)
    is_primary = models.BooleanField(default=False)
    sort_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'product_images'
        ordering = ['sort_order']


class ProductVariant(models.Model):
    """Product variants (size, color, etc.)"""
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='variants'
    )
    name = models.CharField(max_length=100)
    sku = models.CharField(max_length=100, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    compare_at_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True
    )
    color = models.CharField(max_length=50, blank=True)
    size = models.CharField(max_length=50, blank=True)
    quantity = models.IntegerField(default=0)
    weight = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    attributes = models.JSONField(default=dict)
    
    class Meta:
        db_table = 'product_variants'


class ProductReview(models.Model):
    """Product reviews from customers"""
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='reviews'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='product_reviews'
    )
    rating = models.IntegerField(
        choices=[(i, i) for i in range(1, 6)],
        help_text="Rating from 1-5"
    )
    title = models.CharField(max_length=200)
    comment = models.TextField()
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'product_reviews'
        ordering = ['-created_at']
        unique_together = ['product', 'user']


class Collection(models.Model):
    """Product collections for grouping products"""
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    products = models.ManyToManyField(Product, related_name='collections')
    image = models.ImageField(upload_to='collections/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'collections'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class Tag(models.Model):
    """Tags for products"""
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(unique=True)
    products = models.ManyToManyField(Product, related_name='tags')
    
    class Meta:
        db_table = 'tags'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class InventorySyncLog(models.Model):
    """Audit trail for ERP <-> E-commerce inventory synchronization."""
    DIRECTION_CHOICES = [
        ('ecom_to_erp', 'E-commerce to ERP'),
        ('erp_to_ecom', 'ERP to E-commerce'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
    ]

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='inventory_sync_logs')
    direction = models.CharField(max_length=20, choices=DIRECTION_CHOICES)
    quantity_delta = models.IntegerField(default=0)
    source_reference = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    message = models.TextField(blank=True)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'inventory_sync_logs'
        ordering = ['-created_at']
