"""Returns Service Django Admin Configuration"""
from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import ReturnShipment, ReturnHistory


# Note: ReturnRequest admin is registered in order_service
# This admin only handles returns_service-specific functionality


@admin.register(ReturnShipment)
class ReturnShipmentAdmin(admin.ModelAdmin):
    """Admin interface for ReturnShipment"""
    
    list_display = ['id', 'tracking_number', 'carrier', 'sent_at', 'received_at']
    list_filter = ['carrier', 'sent_at', 'received_at']
    search_fields = ['tracking_number', 'return_request__id']
    readonly_fields = ['sent_at']
    
    fieldsets = (
        (_('Shipment Info'), {
            'fields': ('return_request', 'tracking_number', 'carrier')
        }),
        (_('Timeline'), {
            'fields': ('sent_at', 'received_at')
        }),
    )


@admin.register(ReturnHistory)
class ReturnHistoryAdmin(admin.ModelAdmin):
    """Admin interface for ReturnHistory"""
    
    list_display = ['id', 'return_request', 'status_from', 'status_to', 'changed_by', 'changed_at']
    list_filter = ['status_from', 'status_to', 'changed_at']
    search_fields = ['return_request__id', 'changed_by__email']
    readonly_fields = ['changed_at']
    
    fieldsets = (
        (_('Status Change'), {
            'fields': ('return_request', 'status_from', 'status_to')
        }),
        (_('Details'), {
            'fields': ('changed_by', 'reason')
        }),
        (_('Timestamp'), {
            'fields': ('changed_at',),
            'classes': ('collapse',)
        }),
    )
