"""
Wishlist Service Models - Save for Later functionality
"""

from django.db import models
from django.conf import settings


class Wishlist(models.Model):
    """User's wishlist"""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='wishlist'
    )
    is_public = models.BooleanField(default=False)
    share_token = models.CharField(max_length=100, unique=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'wishlists'
    
    def __str__(self):
        return f"{self.user.username}'s Wishlist"


class WishlistItem(models.Model):
    """Items in user's wishlist"""
    wishlist = models.ForeignKey(
        Wishlist,
        on_delete=models.CASCADE,
        related_name='items'
    )
    product = models.ForeignKey(
        'product_service.Product',
        on_delete=models.CASCADE,
        related_name='in_wishlists'
    )
    
    # Price tracking
    price_when_added = models.DecimalField(max_digits=10, decimal_places=2)
    current_price = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Notification preferences
    notify_on_price_drop = models.BooleanField(default=True)
    notify_on_sale = models.BooleanField(default=True)
    notify_back_in_stock = models.BooleanField(default=True)
    
    notes = models.TextField(blank=True, help_text="User's personal notes")
    
    added_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'wishlist_items'
        indexes = [
            models.Index(fields=['wishlist', 'added_at']),
        ]
        constraints = [
            models.UniqueConstraint(fields=['wishlist', 'product'], name='unique_wishlist_product'),
        ]
    
    def __str__(self):
        return f"{self.product.name} in {self.wishlist.user.username}'s list"


class WishlistNotification(models.Model):
    """Track notifications sent for wishlist items"""
    NOTIFICATION_TYPES = [
        ('price_drop', 'Price Drop'),
        ('on_sale', 'On Sale'),
        ('back_in_stock', 'Back in Stock'),
    ]
    
    item = models.ForeignKey(
        WishlistItem,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    old_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    new_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'wishlist_notifications'
        ordering = ['-sent_at']


class WishlistShare(models.Model):
    """Track wishlist shares"""
    wishlist = models.ForeignKey(
        Wishlist,
        on_delete=models.CASCADE,
        related_name='shares'
    )
    shared_with_email = models.EmailField(null=True, blank=True)
    shared_with_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='shared_wishlists'
    )
    shared_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'wishlist_shares'
