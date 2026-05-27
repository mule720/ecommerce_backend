from django.contrib import admin
from review_service.models import (
    Review, ReviewHelpful, ReviewPolicy, ReviewModerationQueue, ReviewTag
)


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('id', 'product', 'reviewer', 'rating', 'status', 'is_verified_purchase', 'created_at')
    list_filter = ('status', 'rating', 'is_verified_purchase', 'created_at')
    search_fields = ('product__name', 'reviewer__username', 'title', 'body')
    readonly_fields = ('helpful_count', 'unhelpful_count', 'created_at', 'updated_at')


@admin.register(ReviewHelpful)
class ReviewHelpfulAdmin(admin.ModelAdmin):
    list_display = ('id', 'review', 'user', 'vote_type', 'created_at')
    list_filter = ('vote_type', 'created_at')
    search_fields = ('review__title', 'user__username')


@admin.register(ReviewPolicy)
class ReviewPolicyAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'is_active', 'minimum_rating', 'maximum_rating')
    list_filter = ('is_active',)
    search_fields = ('name',)


@admin.register(ReviewModerationQueue)
class ReviewModerationQueueAdmin(admin.ModelAdmin):
    list_display = ('id', 'review', 'reason', 'priority', 'assigned_to', 'created_at')
    list_filter = ('reason', 'priority', 'created_at')
    search_fields = ('review__title', 'assigned_to__username')


@admin.register(ReviewTag)
class ReviewTagAdmin(admin.ModelAdmin):
    list_display = ('id', 'review', 'tag')
    list_filter = ('tag',)
    search_fields = ('tag', 'review__product__name')
