"""
Cart Service Admin
"""
from django.contrib import admin
from .models import Cart, CartItem


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('customer', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('customer__username', 'customer__email')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ('product', 'quantity', 'cart', 'added_at')
    list_filter = ('added_at', 'updated_at')
    search_fields = ('product__name', 'cart__customer__username')
    readonly_fields = ('added_at', 'updated_at')
