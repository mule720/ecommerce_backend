from django.contrib import admin
from chat_service.models import (
    ChatRoom, ChatMessage, ChatTemplate, ChatQueue, ChatRating, ChatBan
)


@admin.register(ChatRoom)
class ChatRoomAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'assigned_agent', 'status', 'priority', 'message_count', 'created_at')
    list_filter = ('status', 'priority', 'created_at')
    search_fields = ('subject', 'customer__username', 'assigned_agent__username')
    readonly_fields = ('message_count', 'created_at', 'updated_at', 'closed_at')


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'room', 'sender', 'message_type', 'is_read', 'created_at')
    list_filter = ('message_type', 'is_read', 'created_at')
    search_fields = ('content', 'room__subject', 'sender__username')
    readonly_fields = ('created_at', 'updated_at', 'read_at')


@admin.register(ChatTemplate)
class ChatTemplateAdmin(admin.ModelAdmin):
    list_display = ('id', 'category', 'title', 'is_active', 'usage_count', 'created_at')
    list_filter = ('is_active', 'category', 'created_at')
    search_fields = ('title', 'content', 'category')


@admin.register(ChatQueue)
class ChatQueueAdmin(admin.ModelAdmin):
    list_display = ('id', 'room', 'queue_type', 'position', 'estimated_wait_time', 'created_at')
    list_filter = ('queue_type', 'created_at')
    search_fields = ('room__subject',)


@admin.register(ChatRating)
class ChatRatingAdmin(admin.ModelAdmin):
    list_display = ('id', 'room', 'rating', 'resolved', 'helpful', 'created_at')
    list_filter = ('rating', 'resolved', 'helpful', 'created_at')
    search_fields = ('room__subject',)


@admin.register(ChatBan)
class ChatBanAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'reason', 'banned_until', 'created_by', 'created_at')
    list_filter = ('banned_until', 'created_at')
    search_fields = ('user__username', 'reason')
