from django.contrib import admin
from wishlist_service.models import Wishlist, WishlistItem, WishlistNotification, WishlistShare


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'is_public', 'created_at', 'updated_at')
    list_filter = ('is_public', 'created_at')
    search_fields = ('user__username', 'share_token')


@admin.register(WishlistItem)
class WishlistItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'wishlist', 'product', 'price_when_added', 'current_price', 'added_at')
    list_filter = ('added_at', 'notify_on_price_drop', 'notify_on_sale', 'notify_back_in_stock')
    search_fields = ('product__name', 'wishlist__user__username')


@admin.register(WishlistNotification)
class WishlistNotificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'item', 'notification_type', 'old_value', 'new_value', 'sent_at')
    list_filter = ('notification_type', 'sent_at')
    search_fields = ('item__product__name',)


@admin.register(WishlistShare)
class WishlistShareAdmin(admin.ModelAdmin):
    list_display = ('id', 'wishlist', 'shared_with_email', 'shared_with_user', 'shared_at')
    list_filter = ('shared_at',)
    search_fields = ('wishlist__user__username', 'shared_with_email')
