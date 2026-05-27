"""
User Service Django Admin
"""
from django.contrib import admin
from .models import User, CustomerProfile, VendorProfile, DriverProfile, VendorSubscription
from .auth_models import OTPVerification, DeliveryAddress, OTPLog


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'phone', 'role', 'is_verified', 'created_at')
    list_filter = ('role', 'is_verified', 'created_at')
    search_fields = ('username', 'email', 'phone', 'first_name', 'last_name')
    fieldsets = (
        ('Authentication', {'fields': ('username', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'email')}),
        ('Contact', {'fields': ('phone', 'address', 'city', 'country', 'postal_code')}),
        ('Role & Status', {'fields': ('role', 'is_verified', 'is_active')}),
        ('Permissions', {'fields': ('is_staff', 'is_superuser', 'groups')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )
    readonly_fields = ('created_at', 'updated_at')


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'loyalty_points', 'gender')
    list_filter = ('gender',)
    search_fields = ('user__username', 'user__email')


@admin.register(VendorProfile)
class VendorProfileAdmin(admin.ModelAdmin):
    list_display = ('business_name', 'user', 'status', 'rating', 'total_sales')
    list_filter = ('status',)
    search_fields = ('business_name', 'user__username', 'user__email')
    readonly_fields = ('total_sales', 'rating')


@admin.register(DriverProfile)
class DriverProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'vehicle_type', 'status', 'total_deliveries', 'rating')
    list_filter = ('status', 'vehicle_type', 'rating')
    search_fields = ('user__username', 'vehicle_number', 'license_number')
    readonly_fields = ('total_deliveries', 'rating')


@admin.register(VendorSubscription)
class VendorSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('vendor_profile', 'plan_name', 'billing_cycle', 'status', 'amount', 'created_at')
    list_filter = ('status', 'billing_cycle', 'created_at')
    search_fields = ('vendor_profile__business_name', 'plan_name')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(OTPVerification)
class OTPVerificationAdmin(admin.ModelAdmin):
    list_display = ('phone_number', 'status', 'attempts', 'created_at', 'expires_at')
    list_filter = ('status', 'created_at')
    search_fields = ('phone_number',)
    readonly_fields = ('otp_code', 'created_at', 'verified_at')


@admin.register(DeliveryAddress)
class DeliveryAddressAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'user', 'city', 'country', 'is_default', 'address_type')
    list_filter = ('address_type', 'is_default', 'country', 'city')
    search_fields = ('full_name', 'user__username', 'user__email', 'address_line1', 'city')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(OTPLog)
class OTPLogAdmin(admin.ModelAdmin):
    list_display = ('phone_number', 'action', 'created_at')
    list_filter = ('action', 'created_at')
    search_fields = ('phone_number', 'ip_address')
    readonly_fields = ('created_at',)
