"""
Payment Service — Django Admin
================================
Admin interfaces for VendorPaymentTerms and VendorPayout.

Admin controls:
  - Set payout period, fee %, and currency per vendor (VendorPaymentTerms)
  - View and manage all payout records
  - Manually trigger a retry for failed payouts
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import VendorPaymentTerms, VendorPayout, Payment, Refund


@admin.register(VendorPaymentTerms)
class VendorPaymentTermsAdmin(admin.ModelAdmin):
    list_display  = (
        'vendor_name', 'payout_period', 'payout_day_display',
        'platform_fee_percentage', 'currency', 'min_payout_amount', 'is_active',
    )
    list_filter   = ('payout_period', 'currency', 'is_active')
    search_fields = ('vendor__email', 'vendor__first_name', 'vendor__last_name')
    list_editable = ('payout_period', 'platform_fee_percentage', 'currency', 'is_active')

    fieldsets = (
        ('Vendor', {
            'fields': ('vendor',),
        }),
        ('Payout Schedule', {
            'fields': ('payout_period', 'payout_day'),
            'description': (
                'For Weekly: payout_day = 0 (Monday) through 6 (Sunday). '
                'For Monthly: payout_day = 1 through 28 (day of the month).'
            ),
        }),
        ('Fees & Limits', {
            'fields': ('platform_fee_percentage', 'currency', 'min_payout_amount'),
        }),
        ('Status', {
            'fields': ('is_active',),
        }),
    )

    @admin.display(description='Vendor')
    def vendor_name(self, obj):
        return obj.vendor.get_full_name() or obj.vendor.email

    @admin.display(description='Payout Day')
    def payout_day_display(self, obj):
        if obj.payout_period == 'weekly' and obj.payout_day is not None:
            days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
            return days[obj.payout_day] if 0 <= obj.payout_day <= 6 else obj.payout_day
        if obj.payout_period == 'monthly' and obj.payout_day is not None:
            return f"Day {obj.payout_day}"
        return '—'


@admin.register(VendorPayout)
class VendorPayoutAdmin(admin.ModelAdmin):
    list_display  = (
        'source_reference', 'vendor_name', 'vendor_phone',
        'gross_amount', 'platform_fee_percentage', 'currency',
        'status_badge', 'created_at', 'processed_at',
    )
    list_filter   = ('status', 'currency', 'created_at')
    search_fields = ('vendor__email', 'vendor_phone', 'source_reference', 'payment_system_reference')
    readonly_fields = (
        'payment_system_reference', 'event_trace_id',
        'queued_at', 'processed_at', 'failure_reason',
    )
    actions = ['retry_failed_payouts']

    fieldsets = (
        ('Payout Details', {
            'fields': (
                'vendor', 'payment_terms', 'source_reference', 'order_items',
                'vendor_phone',
            ),
        }),
        ('Amounts', {
            'fields': ('gross_amount', 'platform_fee_percentage', 'currency'),
        }),
        ('Status & Tracking', {
            'fields': (
                'status', 'payment_system_reference', 'event_trace_id',
                'failure_reason', 'queued_at', 'processed_at',
            ),
        }),
    )

    @admin.display(description='Vendor')
    def vendor_name(self, obj):
        return obj.vendor.get_full_name() or obj.vendor.email

    @admin.display(description='Status')
    def status_badge(self, obj):
        colours = {
            'pending': '#f59e0b',
            'queued':  '#3b82f6',
            'paid':    '#22c55e',
            'failed':  '#ef4444',
        }
        colour = colours.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:4px;">{}</span>',
            colour, obj.get_status_display(),
        )

    @admin.action(description='Retry selected failed payouts')
    def retry_failed_payouts(self, request, queryset):
        from .services import _dispatch_payout
        retried = 0
        for payout in queryset.filter(status='failed'):
            payout.status         = VendorPayout.PayoutStatus.PENDING
            payout.failure_reason = ''
            payout.save(update_fields=['status', 'failure_reason'])
            _dispatch_payout(payout)
            retried += 1
        self.message_user(request, f"{retried} payout(s) re-queued.")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display  = ('transaction_id', 'order', 'customer', 'amount', 'currency', 'method', 'status', 'created_at')
    list_filter   = ('status', 'method', 'currency')
    search_fields = ('transaction_id', 'gateway_transaction_id', 'customer__email')
    readonly_fields = ('payment_gateway_response', 'payment_system_reference')


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display  = ('transaction_id', 'payment', 'order', 'amount', 'status', 'created_at')
    list_filter   = ('status',)
    search_fields = ('transaction_id',)
