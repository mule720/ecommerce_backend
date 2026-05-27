"""
Shipping Service Django App Configuration
"""
from django.apps import AppConfig


class ShippingServiceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'shipping_service'
    verbose_name = 'Shipping Service'
