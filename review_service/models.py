"""
Review Service Models - Detailed review system
"""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.conf import settings


class Review(models.Model):
    """Product reviews with detailed ratings"""
    
    RATING_CHOICES = [
        (1, '1 Star'),
        (2, '2 Stars'),
        (3, '3 Stars'),
        (4, '4 Stars'),
        (5, '5 Stars'),
    ]
    
    STATUS_CHOICES = [
        ('published', 'Published'),
        ('pending', 'Pending Moderation'),
        ('rejected', 'Rejected'),
        ('hidden', 'Hidden'),
    ]
    
    product = models.ForeignKey(
        'product_service.Product',
        on_delete=models.CASCADE,
        related_name='detailed_reviews'
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='detailed_reviews'
    )
    
    # Rating
    rating = models.IntegerField(
        choices=RATING_CHOICES,
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    
    # Detailed ratings (breakdown)
    quality_rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    value_rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    shipping_rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    
    # Review content
    title = models.CharField(max_length=200)
    body = models.TextField()
    
    # Media
    images = models.JSONField(
        default=list,
        help_text="URLs of uploaded images"
    )
    video_url = models.URLField(blank=True, null=True)
    
    # Moderation
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    rejection_reason = models.TextField(blank=True)
    
    # Engagement
    helpful_count = models.IntegerField(default=0)
    unhelpful_count = models.IntegerField(default=0)
    
    # Seller response
    seller_response = models.TextField(blank=True)
    seller_response_at = models.DateTimeField(null=True, blank=True)
    
    # Verification
    is_verified_purchase = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'reviews'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['product', 'status']),
            models.Index(fields=['reviewer']),
            models.Index(fields=['-helpful_count']),
            models.Index(fields=['is_verified_purchase']),
        ]
    
    def __str__(self):
        return f"{self.reviewer.username} - {self.product.name} ({self.rating}★)"
    
    def average_detailed_rating(self):
        """Average of quality, value, and shipping ratings"""
        return (self.quality_rating + self.value_rating + self.shipping_rating) / 3


class ReviewHelpful(models.Model):
    """Track if review was helpful/unhelpful"""
    
    VOTE_CHOICES = [
        ('helpful', 'Helpful'),
        ('unhelpful', 'Unhelpful'),
    ]
    
    review = models.ForeignKey(
        Review,
        on_delete=models.CASCADE,
        related_name='votes'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='review_votes'
    )
    vote_type = models.CharField(max_length=20, choices=VOTE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'review_helpful'
        indexes = [
            models.Index(fields=['review', 'vote_type']),
        ]
        constraints = [
            models.UniqueConstraint(fields=['review', 'user'], name='unique_review_user_vote'),
        ]


class ReviewPolicy(models.Model):
    """Review moderation policies"""
    
    name = models.CharField(max_length=100)
    description = models.TextField()
    
    # Filters
    minimum_rating = models.IntegerField(default=1)
    maximum_rating = models.IntegerField(default=5)
    minimum_title_length = models.IntegerField(default=10)
    minimum_body_length = models.IntegerField(default=20)
    
    # Restrictions
    require_verified_purchase = models.BooleanField(default=False)
    auto_approve_verified = models.BooleanField(default=True)
    require_one_image_for_low_rating = models.BooleanField(default=False)
    
    # Spam detection
    block_keywords = models.JSONField(default=list)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'review_policies'


class ReviewModerationQueue(models.Model):
    """Queue for reviews pending moderation"""
    
    review = models.OneToOneField(
        Review,
        on_delete=models.CASCADE,
        related_name='moderation_queue'
    )
    reason = models.CharField(max_length=200)  # e.g., 'keyword_found', 'low_rating_no_image'
    priority = models.IntegerField(default=0)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='moderation_queue'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'review_moderation_queue'
        ordering = ['-priority', 'created_at']


class ReviewTag(models.Model):
    """Tags for reviews (e.g., 'Fast Shipping', 'Defective')"""
    
    review = models.ForeignKey(
        Review,
        on_delete=models.CASCADE,
        related_name='tags'
    )
    tag = models.CharField(max_length=50)
    
    class Meta:
        db_table = 'review_tags'
        constraints = [
            models.UniqueConstraint(fields=['review', 'tag'], name='unique_review_tag'),
        ]
