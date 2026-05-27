"""Returns Service App Configuration"""
from django.apps import AppConfig


class ReturnsServiceConfig(AppConfig):
    """Returns Service configuration"""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'returns_service'
    verbose_name = 'Returns Service'
