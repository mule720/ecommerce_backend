"""
Notification Service Django App Configuration
"""
from django.apps import AppConfig


class NotificationServiceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'notification_service'
    verbose_name = 'Notification Service'
