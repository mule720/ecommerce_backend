from django.contrib import admin
from .models import CardVaultEntry, PaymentAuditLog


@admin.register(CardVaultEntry)
class CardVaultEntryAdmin(admin.ModelAdmin):
    list_display = ('customer', 'card_brand', 'pan_last_four', 'is_default', 'is_active', 'created_at')
    list_filter  = ('card_brand', 'is_active', 'is_default')
    search_fields = ('customer__email', 'pan_last_four', 'pan_bin')
    readonly_fields = ('token', 'encrypted_pan', 'encrypted_expiry',
                       'encrypted_cardholder_name', 'key_version', 'created_at', 'updated_at')

    def has_add_permission(self, request):
        return False  # Cards are only created via the tokenize mutation


@admin.register(PaymentAuditLog)
class PaymentAuditLogAdmin(admin.ModelAdmin):
    list_display  = ('created_at', 'action', 'actor', 'resource_type', 'resource_id', 'ip_address')
    list_filter   = ('action',)
    search_fields = ('actor__email', 'resource_id', 'ip_address')
    readonly_fields = ('action', 'actor', 'resource_type', 'resource_id',
                       'ip_address', 'metadata', 'created_at')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
