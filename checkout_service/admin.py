from django.contrib import admin
from .models import CheckoutSession, ShippingMethod


@admin.register(ShippingMethod)
class ShippingMethodAdmin(admin.ModelAdmin):
    list_display = ('name', 'shipping_type', 'base_cost', 'estimated_days', 'is_active')
    list_filter = ('is_active', 'shipping_type')
    search_fields = ('name', 'description')
    ordering = ('base_cost',)


@admin.register(CheckoutSession)
class CheckoutSessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'status', 'total', 'created_at')
    list_filter = ('status', 'created_at', 'shipping_method')
    search_fields = ('customer__username', 'customer__email')
    readonly_fields = ('created_at', 'updated_at', 'customer', 'cart')
    fieldsets = (
        ('Checkout Info', {
            'fields': ('customer', 'cart', 'status')
        }),
        ('Address & Shipping', {
            'fields': ('delivery_address', 'shipping_method')
        }),
        ('Pricing', {
            'fields': ('subtotal', 'shipping_cost', 'tax_amount', 'total')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'expires_at')
        }),
    )
