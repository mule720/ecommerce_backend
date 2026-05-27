"""
Product Service Django App Configuration
"""
from django.apps import AppConfig


class ProductServiceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'product_service'
    verbose_name = 'Product Service'
