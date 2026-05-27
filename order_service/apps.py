"""
Order Service Django App Configuration
"""
from django.apps import AppConfig


class OrderServiceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'order_service'
    verbose_name = 'Order Service'
