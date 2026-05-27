from django.contrib import admin
from search_service.models import (
    SearchFilter, SearchLog, ProductSearchIndex, PopularSearch,
    ProductView, ProductInteraction, BrowsingHistory, UserEngagementMetric
)


@admin.register(SearchFilter)
class SearchFilterAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'name', 'created_at')
    list_filter = ('created_at', 'user')
    search_fields = ('name', 'user__username')


@admin.register(SearchLog)
class SearchLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'query', 'results_count', 'created_at')
    list_filter = ('created_at', 'user')
    search_fields = ('query',)
    readonly_fields = ('created_at',)


@admin.register(ProductSearchIndex)
class ProductSearchIndexAdmin(admin.ModelAdmin):
    list_display = ('id', 'product', 'name', 'is_active', 'rating')
    list_filter = ('is_active', 'rating')
    search_fields = ('name', 'search_text')
    readonly_fields = ('updated_at',)


@admin.register(PopularSearch)
class PopularSearchAdmin(admin.ModelAdmin):
    list_display = ('id', 'query', 'count', 'updated_at')
    list_filter = ('updated_at',)
    search_fields = ('query',)
    ordering = ('-count',)


@admin.register(ProductView)
class ProductViewAdmin(admin.ModelAdmin):
    list_display = ('id', 'product', 'user', 'view_duration', 'source', 'device_type', 'viewed_at')
    list_filter = ('source', 'device_type', 'viewed_at')
    search_fields = ('product__name', 'user__username')
    readonly_fields = ('viewed_at',)
    
    fieldsets = (
        ('Product & User', {
            'fields': ('product', 'user', 'session_id')
        }),
        ('Engagement', {
            'fields': ('view_duration', 'source')
        }),
        ('Device Info', {
            'fields': ('device_type',)
        }),
        ('Timestamp', {
            'fields': ('viewed_at',),
            'classes': ('collapse',)
        }),
    )


@admin.register(ProductInteraction)
class ProductInteractionAdmin(admin.ModelAdmin):
    list_display = ('id', 'product', 'user', 'interaction_type', 'device_type', 'created_at')
    list_filter = ('interaction_type', 'device_type', 'created_at')
    search_fields = ('product__name', 'user__username', 'page')
    readonly_fields = ('created_at',)
    
    fieldsets = (
        ('Product & User', {
            'fields': ('product', 'user')
        }),
        ('Interaction Details', {
            'fields': ('interaction_type', 'interaction_value')
        }),
        ('Context', {
            'fields': ('page', 'referrer', 'device_type')
        }),
        ('Timestamp', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )


@admin.register(BrowsingHistory)
class BrowsingHistoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'product', 'view_count', 'last_viewed_at', 'added_at')
    list_filter = ('last_viewed_at', 'added_at')
    search_fields = ('user__username', 'product__name')
    readonly_fields = ('added_at', 'last_viewed_at')


@admin.register(UserEngagementMetric)
class UserEngagementMetricAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'engagement_score', 'total_searches', 'total_views', 'total_purchases', 'calculated_at')
    list_filter = ('calculated_at', 'engagement_score')
    search_fields = ('user__username',)
    readonly_fields = ('calculated_at',)
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Activity Counts', {
            'fields': ('total_searches', 'total_views', 'total_adds_to_cart', 'total_wishlist_adds', 'total_purchases', 'total_reviews')
        }),
        ('Engagement Metrics', {
            'fields': ('engagement_score', 'avg_session_duration', 'last_activity_at')
        }),
        ('Last Calculated', {
            'fields': ('calculated_at',),
            'classes': ('collapse',)
        }),
    )
