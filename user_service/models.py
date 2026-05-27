"""
User Service Models
Multi-vendor e-commerce user management
"""
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _


class User(AbstractUser):
    """Extended User model with roles for multi-vendor e-commerce"""
    
    class UserRole(models.TextChoices):
        ADMIN = 'admin', _('Admin')
        CUSTOMER = 'customer', _('Customer')
        VENDOR = 'vendor', _('Vendor')
        DRIVER = 'driver', _('Driver')
    
    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.CUSTOMER
    )
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'users'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.username} ({self.role})"


class CustomerProfile(models.Model):
    """Additional profile information for customers"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='customer_profile')
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, blank=True)
    loyalty_points = models.IntegerField(default=0)
    wishlist = models.JSONField(default=list)
    
    class Meta:
        db_table = 'customer_profiles'


class VendorProfile(models.Model):
    """Additional profile information for vendors"""
    
    class VendorStatus(models.TextChoices):
        PENDING = 'pending', _('Pending Approval')
        APPROVED = 'approved', _('Approved')
        SUSPENDED = 'suspended', _('Suspended')
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='vendor_profile')
    business_name = models.CharField(max_length=200)
    business_description = models.TextField(blank=True)
    business_license = models.CharField(max_length=100, blank=True)
    tax_id = models.CharField(max_length=50, blank=True)
    status = models.CharField(max_length=20, choices=VendorStatus.choices, default=VendorStatus.PENDING)
    bank_account = models.CharField(max_length=200, blank=True)
    payout_method = models.CharField(max_length=50, blank=True)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    total_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    class Meta:
        db_table = 'vendor_profiles'
    
    def __str__(self):
        return self.business_name


class DriverProfile(models.Model):
    """Additional profile information for delivery drivers"""
    
    class DriverStatus(models.TextChoices):
        AVAILABLE = 'available', _('Available')
        BUSY = 'busy', _('Busy')
        OFFLINE = 'offline', _('Offline')
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='driver_profile')
    vehicle_type = models.CharField(max_length=50, blank=True)
    vehicle_number = models.CharField(max_length=50, blank=True)
    license_number = models.CharField(max_length=50, blank=True)
    status = models.CharField(max_length=20, choices=DriverStatus.choices, default=DriverStatus.OFFLINE)
    current_location_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    current_location_lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    total_deliveries = models.IntegerField(default=0)
    
    class Meta:
        db_table = 'driver_profiles'


class VendorSubscription(models.Model):
    """Subscription plan selected by a vendor during onboarding."""

    class BillingCycle(models.TextChoices):
        MONTHLY = 'monthly', _('Monthly')
        YEARLY = 'yearly', _('Yearly')

    class SubscriptionStatus(models.TextChoices):
        PENDING = 'pending', _('Pending')
        PAYMENT_PENDING = 'payment_pending', _('Payment Pending')
        ACTIVE = 'active', _('Active')
        CANCELLED = 'cancelled', _('Cancelled')
        PAYMENT_FAILED = 'payment_failed', _('Payment Failed')

    vendor_profile = models.ForeignKey(
        VendorProfile,
        on_delete=models.CASCADE,
        related_name='subscriptions',
    )
    plan_code = models.CharField(max_length=50)
    plan_name = models.CharField(max_length=100)
    billing_cycle = models.CharField(
        max_length=20,
        choices=BillingCycle.choices,
        default=BillingCycle.MONTHLY,
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    currency = models.CharField(max_length=10, default='ZMW')
    status = models.CharField(
        max_length=30,
        choices=SubscriptionStatus.choices,
        default=SubscriptionStatus.PENDING,
    )
    payment_reference = models.CharField(max_length=120, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'vendor_subscriptions'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.vendor_profile.business_name} - {self.plan_name} ({self.status})"
