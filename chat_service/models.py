"""
Chat Service Models - Live chat support system
"""

from django.db import models
from django.conf import settings


class ChatRoom(models.Model):
    """Chat room between customer and support/vendor"""
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('on_hold', 'On Hold'),
        ('closed', 'Closed'),
        ('waiting', 'Waiting Customer'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='chat_rooms_as_customer'
    )
    assigned_agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='chat_rooms_assigned'
    )
    
    # For product-specific chats
    product = models.ForeignKey(
        'product_service.Product',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='chat_rooms'
    )
    order = models.ForeignKey(
        'order_service.Order',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='chat_rooms'
    )
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    
    subject = models.CharField(max_length=200)
    
    # Metrics
    message_count = models.IntegerField(default=0)
    first_response_time = models.DurationField(null=True, blank=True)
    resolution_time = models.DurationField(null=True, blank=True)
    
    # Ratings
    satisfaction_rating = models.IntegerField(
        null=True,
        blank=True,
        choices=[(i, f'{i} Stars') for i in range(1, 6)]
    )
    feedback = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'chat_rooms'
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['customer', 'status']),
            models.Index(fields=['assigned_agent', 'status']),
            models.Index(fields=['priority']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"Chat #{self.id} - {self.subject}"


class ChatMessage(models.Model):
    """Individual chat messages"""
    
    MESSAGE_TYPES = [
        ('text', 'Text'),
        ('image', 'Image'),
        ('file', 'File'),
        ('system', 'System'),
    ]
    
    room = models.ForeignKey(
        ChatRoom,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='sent_messages'
    )
    
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES, default='text')
    content = models.TextField()
    
    # File attachments
    file_url = models.URLField(blank=True)
    file_name = models.CharField(max_length=255, blank=True)
    file_size = models.IntegerField(null=True, blank=True)
    
    # Read status
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'chat_messages'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['room', 'created_at']),
            models.Index(fields=['sender']),
            models.Index(fields=['is_read']),
        ]


class ChatTemplate(models.Model):
    """Pre-written responses for common questions"""
    
    category = models.CharField(max_length=100)
    title = models.CharField(max_length=200)
    content = models.TextField()
    shortcuts = models.JSONField(default=list)  # /shortcut1, /shortcut2
    
    usage_count = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='chat_templates'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'chat_templates'
        ordering = ['category', 'title']


class ChatQueue(models.Model):
    """Queue for routing chats to agents"""
    
    QUEUE_TYPES = [
        ('general', 'General Support'),
        ('sales', 'Sales'),
        ('technical', 'Technical Support'),
        ('returns', 'Returns & Refunds'),
        ('billing', 'Billing'),
    ]
    
    room = models.OneToOneField(
        ChatRoom,
        on_delete=models.CASCADE,
        related_name='queue'
    )
    queue_type = models.CharField(max_length=20, choices=QUEUE_TYPES, default='general')
    position = models.IntegerField(default=0)
    
    estimated_wait_time = models.IntegerField(null=True, blank=True)  # in seconds
    
    created_at = models.DateTimeField(auto_now_add=True)
    assigned_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'chat_queue'
        ordering = ['position', 'created_at']


class ChatRating(models.Model):
    """Customer satisfaction ratings"""
    
    room = models.OneToOneField(
        ChatRoom,
        on_delete=models.CASCADE,
        related_name='rating'
    )
    rating = models.IntegerField(choices=[(i, str(i)) for i in range(1, 6)])
    comment = models.TextField(blank=True)
    
    resolved = models.BooleanField(default=False)
    helpful = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'chat_ratings'


class ChatBan(models.Model):
    """Block abusive users from chat"""
    
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='chat_ban'
    )
    reason = models.TextField()
    banned_until = models.DateTimeField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='issued_bans'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'chat_bans'
