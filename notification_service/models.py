"""
Notification Service Models
Multi-vendor e-commerce notification management
"""
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _


class Notification(models.Model):
    """User notifications"""
    
    class NotificationType(models.TextChoices):
        ORDER_PLACED = 'order_placed', _('Order Placed')
        ORDER_CONFIRMED = 'order_confirmed', _('Order Confirmed')
        ORDER_SHIPPED = 'order_shipped', _('Order Shipped')
        ORDER_DELIVERED = 'order_delivered', _('Order Delivered')
        PAYMENT_RECEIVED = 'payment_received', _('Payment Received')
        PAYMENT_FAILED = 'payment_failed', _('Payment Failed')
        REFUND_PROCESSED = 'refund_processed', _('Refund Processed')
        VENDOR_APPROVED = 'vendor_approved', _('Vendor Approved')
        VENDOR_SUSPENDED = 'vendor_suspended', _('Vendor Suspended')
        RETURN_REQUEST = 'return_request', _('Return Request')
        REVIEW_RECEIVED = 'review_received', _('Review Received')
        PROMOTION = 'promotion', _('Promotion')
        GENERAL = 'general', _('General')
    
    class Priority(models.TextChoices):
        LOW = 'low', _('Low')
        NORMAL = 'normal', _('Normal')
        HIGH = 'high', _('High')
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    type = models.CharField(max_length=30, choices=NotificationType.choices)
    title = models.CharField(max_length=200)
    message = models.TextField()
    priority = models.CharField(
        max_length=10,
        choices=Priority.choices,
        default=Priority.NORMAL
    )
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    link = models.CharField(max_length=500, blank=True)
    data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} - {self.user.username}"


class EmailTemplate(models.Model):
    """Email templates for notifications"""
    name = models.CharField(max_length=100)
    subject = models.CharField(max_length=200)
    body = models.TextField()
    type = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'email_templates'
    
    def __str__(self):
        return self.name


class EmailQueue(models.Model):
    """Queued emails for sending"""
    
    class EmailStatus(models.TextChoices):
        PENDING = 'pending', _('Pending')
        SENT = 'sent', _('Sent')
        FAILED = 'failed', _('Failed')
    
    to_email = models.EmailField()
    subject = models.CharField(max_length=200)
    body = models.TextField()
    status = models.CharField(
        max_length=10,
        choices=EmailStatus.choices,
        default=EmailStatus.PENDING
    )
    attempts = models.IntegerField(default=0)
    sent_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'email_queue'
        ordering = ['-created_at']


class PushNotification(models.Model):
    """Push notifications for mobile app"""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='push_notifications'
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    data = models.JSONField(default=dict, blank=True)
    is_sent = models.BooleanField(default=False)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'push_notifications'
        ordering = ['-created_at']
