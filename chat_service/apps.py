from django.apps import AppConfig


class ChatServiceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'chat_service'
    label = 'chat_service'
    verbose_name = 'Chat Service'
