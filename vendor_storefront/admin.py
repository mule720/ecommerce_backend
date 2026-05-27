from django.contrib import admin
from .models import VendorStorefront, StorefrontSection, StorefrontReview


@admin.register(VendorStorefront)
class VendorStorefrontAdmin(admin.ModelAdmin):
    list_display  = ['slug', 'vendor', 'template', 'is_published', 'is_featured', 'created_at']
    list_filter   = ['is_published', 'is_featured', 'template']
    search_fields = ['slug', 'vendor__username', 'vendor__vendor_profile__business_name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(StorefrontSection)
class StorefrontSectionAdmin(admin.ModelAdmin):
    list_display = ['storefront', 'section_type', 'title', 'sort_order', 'is_active']


@admin.register(StorefrontReview)
class StorefrontReviewAdmin(admin.ModelAdmin):
    list_display  = ['storefront', 'reviewer', 'rating', 'is_approved', 'created_at']
    list_filter   = ['is_approved', 'rating']
    actions       = ['approve_reviews']

    def approve_reviews(self, request, queryset):
        queryset.update(is_approved=True)
    approve_reviews.short_description = 'Approve selected reviews'
