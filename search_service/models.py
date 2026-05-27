"""
Search Service - Advanced product search and filtering
"""

from django.db import models
from django.conf import settings


class SearchFilter(models.Model):
    """Store user's saved search filters"""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='saved_filters'
    )
    name = models.CharField(max_length=100)
    filters = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'search_filters'


class SearchLog(models.Model):
    """Log all search queries for analytics"""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    query = models.CharField(max_length=255)
    filters = models.JSONField(default=dict)
    results_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'search_logs'
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['user', 'created_at']),
        ]


class ProductSearchIndex(models.Model):
    """Denormalized search index for fast full-text search"""
    product = models.OneToOneField(
        'product_service.Product',
        on_delete=models.CASCADE,
        related_name='search_index'
    )
    search_text = models.TextField(blank=True)
    name = models.CharField(max_length=200, db_index=True)
    category_name = models.CharField(max_length=100, blank=True)
    vendor_name = models.CharField(max_length=100, blank=True)
    
    price_min = models.DecimalField(max_digits=10, decimal_places=2)
    price_max = models.DecimalField(max_digits=10, decimal_places=2)
    
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    review_count = models.IntegerField(default=0)
    
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'product_search_index'
        indexes = [
            models.Index(fields=['is_active']),
            models.Index(fields=['rating', 'review_count']),
            models.Index(fields=['price_min', 'price_max']),
        ]


class PopularSearch(models.Model):
    """Track trending search terms"""
    query = models.CharField(max_length=255, unique=True)
    count = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'popular_searches'
        ordering = ['-count']


class ProductView(models.Model):
    """Track product page views for analytics"""
    product = models.ForeignKey(
        'product_service.Product',
        on_delete=models.CASCADE,
        related_name='views'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='product_views'
    )
    session_id = models.CharField(max_length=100, blank=True)
    
    # Engagement data
    view_duration = models.IntegerField(default=0, help_text="Time spent viewing product in seconds")
    source = models.CharField(
        max_length=50,
        choices=[
            ('search', 'Search Results'),
            ('category', 'Category Browse'),
            ('featured', 'Featured Section'),
            ('recommendation', 'Recommendation'),
            ('direct', 'Direct Link'),
            ('other', 'Other'),
        ],
        default='direct'
    )
    
    # Device info
    device_type = models.CharField(
        max_length=20,
        choices=[
            ('mobile', 'Mobile'),
            ('tablet', 'Tablet'),
            ('desktop', 'Desktop'),
        ],
        default='desktop'
    )
    
    viewed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'product_views'
        indexes = [
            models.Index(fields=['product', 'viewed_at']),
            models.Index(fields=['user', 'viewed_at']),
            models.Index(fields=['viewed_at']),
        ]
    
    def __str__(self):
        return f"View of {self.product.name} at {self.viewed_at}"


class ProductInteraction(models.Model):
    """Track user interactions with products (clicks, adds to cart, etc.)"""
    INTERACTION_TYPES = [
        ('view', 'Product View'),
        ('click', 'Click'),
        ('add_to_cart', 'Add to Cart'),
        ('add_to_wishlist', 'Add to Wishlist'),
        ('remove_from_wishlist', 'Remove from Wishlist'),
        ('share', 'Share'),
        ('review', 'Review/Rate'),
        ('report', 'Report'),
        ('purchase', 'Purchase'),
        ('compare', 'Compare'),
        ('zoom_image', 'Zoom Image'),
        ('read_review', 'Read Review'),
    ]
    
    product = models.ForeignKey(
        'product_service.Product',
        on_delete=models.CASCADE,
        related_name='interactions'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='product_interactions'
    )
    
    interaction_type = models.CharField(max_length=20, choices=INTERACTION_TYPES)
    interaction_value = models.CharField(
        max_length=255,
        blank=True,
        help_text="Additional data about the interaction"
    )
    
    # Context
    page = models.CharField(max_length=100, blank=True, help_text="Page where interaction occurred")
    referrer = models.CharField(max_length=255, blank=True)
    
    # Device info
    device_type = models.CharField(
        max_length=20,
        choices=[
            ('mobile', 'Mobile'),
            ('tablet', 'Tablet'),
            ('desktop', 'Desktop'),
        ],
        default='desktop'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'product_interactions'
        indexes = [
            models.Index(fields=['product', 'interaction_type', 'created_at']),
            models.Index(fields=['user', 'interaction_type', 'created_at']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.user or 'Anonymous'} - {self.get_interaction_type_display()} - {self.product.name}"


class BrowsingHistory(models.Model):
    """Track user's browsing history"""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='browsing_history'
    )
    product = models.ForeignKey(
        'product_service.Product',
        on_delete=models.CASCADE,
        related_name='browsed_by'
    )
    
    # Tracking
    view_count = models.IntegerField(default=1)
    last_viewed_at = models.DateTimeField(auto_now=True)
    added_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'browsing_history'
        unique_together = ['user', 'product']
        indexes = [
            models.Index(fields=['user', 'last_viewed_at']),
        ]
    
    def __str__(self):
        return f"{self.user.username} viewed {self.product.name}"


class UserEngagementMetric(models.Model):
    """Aggregate user engagement metrics"""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='engagement_metric'
    )
    
    # Activity counts
    total_searches = models.IntegerField(default=0)
    total_views = models.IntegerField(default=0)
    total_adds_to_cart = models.IntegerField(default=0)
    total_wishlist_adds = models.IntegerField(default=0)
    total_purchases = models.IntegerField(default=0)
    total_reviews = models.IntegerField(default=0)
    
    # Aggregate scores
    engagement_score = models.FloatField(default=0.0, help_text="0-100 scale")
    avg_session_duration = models.IntegerField(default=0, help_text="seconds")
    last_activity_at = models.DateTimeField(null=True, blank=True)
    
    calculated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'user_engagement_metrics'
    
    def __str__(self):
        return f"Engagement: {self.user.username} (Score: {self.engagement_score})"
