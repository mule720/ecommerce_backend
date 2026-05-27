from django.contrib import admin
from .models import Wallet, WalletTransaction


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ('customer', 'balance', 'pending_balance', 'currency', 'created_at')
    search_fields = ('customer__username', 'customer__email')
    list_filter = ('currency', 'created_at')


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'wallet', 'type', 'amount', 'status', 'reference', 'created_at')
    search_fields = ('wallet__customer__username', 'reference', 'description')
    list_filter = ('type', 'status', 'created_at')
