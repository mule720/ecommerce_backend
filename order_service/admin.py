from django.contrib import admin
from .models import Order, OrderItem, OrderTimeline, VendorOrder, Cart, CartItem


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_number', 'customer', 'status', 'payment_status', 'total', 'created_at')
    list_filter = ('status', 'payment_status', 'escrow_status', 'created_at', 'shipping_country')
    search_fields = ('order_number', 'customer__username', 'customer__email')
    readonly_fields = ('order_number', 'created_at', 'updated_at')
    fieldsets = (
        ('Order Info', {
            'fields': ('order_number', 'customer', 'status', 'payment_status', 'escrow_status')
        }),
        ('Pricing', {
            'fields': ('subtotal', 'tax_amount', 'shipping_amount', 'discount_amount', 'total', 'currency', 'exchange_rate')
        }),
        ('Shipping Address', {
            'fields': ('shipping_first_name', 'shipping_last_name', 'shipping_email', 'shipping_phone', 
                      'shipping_address', 'shipping_city', 'shipping_state', 'shipping_postal_code', 'shipping_country')
        }),
        ('Billing Address', {
            'fields': ('billing_first_name', 'billing_last_name', 'billing_email', 'billing_phone', 
                      'billing_address', 'billing_city', 'billing_state', 'billing_postal_code', 'billing_country')
        }),
        ('Shipping & Payment', {
            'fields': ('shipping_method', 'tracking_number', 'shipping_provider', 'estimated_delivery', 
                      'payment_method', 'platform_commission', 'platform_commission_rate')
        }),
        ('Other', {
            'fields': ('notes', 'created_at', 'updated_at')
        }),
    )


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('product_name', 'order', 'vendor', 'quantity', 'price', 'total', 'status')
    list_filter = ('status', 'created_at', 'vendor')
    search_fields = ('product_name', 'order__order_number', 'vendor__username')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(OrderTimeline)
class OrderTimelineAdmin(admin.ModelAdmin):
    list_display = ('order', 'event_type', 'status', 'actor', 'created_at')
    list_filter = ('event_type', 'status', 'created_at')
    search_fields = ('order__order_number', 'description', 'actor__username')
    readonly_fields = ('created_at',)


@admin.register(VendorOrder)
class VendorOrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'vendor', 'status', 'payout_status', 'subtotal', 'payout_amount')
    list_filter = ('status', 'payout_status', 'created_at')
    search_fields = ('order__order_number', 'vendor__username')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Order & Vendor', {
            'fields': ('order', 'vendor', 'status')
        }),
        ('Financials', {
            'fields': ('subtotal', 'commission_amount', 'payout_amount', 'payout_status')
        }),
        ('Shipping', {
            'fields': ('tracking_number', 'shipping_provider')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'currency', 'item_count', 'total', 'created_at')
    list_filter = ('currency', 'created_at')
    search_fields = ('customer__username', 'customer__email')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'cart', 'product', 'quantity', 'unit_price', 'get_total_price')
    list_filter = ('created_at', 'cart__currency')
    search_fields = ('product__name', 'cart__customer__username')
    readonly_fields = ('created_at', 'updated_at')
