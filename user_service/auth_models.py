"""
OTP Authentication Service Models
Phone-based OTP verification for user authentication
"""
from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import random
import string
from django.utils.translation import gettext_lazy as _


class OTPVerification(models.Model):
    """OTP verification for phone-based authentication"""
    
    class OTPStatus(models.TextChoices):
        PENDING = 'pending', _('Pending')
        VERIFIED = 'verified', _('Verified')
        EXPIRED = 'expired', _('Expired')
        FAILED = 'failed', _('Failed')
    
    phone_number = models.CharField(max_length=20)
    otp_code = models.CharField(max_length=6)
    status = models.CharField(
        max_length=20,
        choices=OTPStatus.choices,
        default=OTPStatus.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    verified_at = models.DateTimeField(null=True, blank=True)
    attempts = models.IntegerField(default=0)
    max_attempts = models.IntegerField(default=5)
    is_used = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'otp_verifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['phone_number', 'status']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f"OTP for {self.phone_number} ({self.status})"
    
    @classmethod
    def generate_otp(cls):
        """Generate a 6-digit OTP code"""
        return ''.join(random.choices(string.digits, k=6))
    
    @classmethod
    def create_otp(cls, phone_number, expires_in_minutes=10):
        """Create a new OTP verification"""
        otp_code = cls.generate_otp()
        expires_at = timezone.now() + timedelta(minutes=expires_in_minutes)
        
        otp = cls.objects.create(
            phone_number=phone_number,
            otp_code=otp_code,
            expires_at=expires_at
        )
        return otp
    
    def is_expired(self):
        """Check if OTP has expired"""
        return timezone.now() > self.expires_at
    
    def is_valid_attempt(self):
        """Check if OTP can still be attempted"""
        return self.attempts < self.max_attempts and not self.is_expired()
    
    def verify(self, otp_code):
        """Verify OTP code"""
        if self.is_expired():
            self.status = self.OTPStatus.EXPIRED
            self.save()
            return False
        
        if self.attempts >= self.max_attempts:
            self.status = self.OTPStatus.FAILED
            self.save()
            return False
        
        self.attempts += 1
        
        if otp_code != self.otp_code:
            self.save()
            return False
        
        self.status = self.OTPStatus.VERIFIED
        self.verified_at = timezone.now()
        self.is_used = True
        self.save()
        return True


class DeliveryAddress(models.Model):
    """Delivery address for customers"""
    
    class AddressType(models.TextChoices):
        HOME = 'home', _('Home')
        WORK = 'work', _('Work')
        OTHER = 'other', _('Other')
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='user_delivery_addresses')
    full_name = models.CharField(max_length=200)
    phone_number = models.CharField(max_length=20)
    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100)
    address_type = models.CharField(
        max_length=20,
        choices=AddressType.choices,
        default=AddressType.HOME
    )
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'user_service_delivery_addresses'
        ordering = ['-is_default', '-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['user'],
                condition=models.Q(is_default=True),
                name='unique_default_delivery_address_per_user'
            )
        ]
    
    def __str__(self):
        return f"{self.full_name} - {self.address_line1}, {self.city}"
    
    def save(self, *args, **kwargs):
        """
        Ensure only one default address per user
        """
        if self.is_default:
            # Remove default from other addresses
            DeliveryAddress.objects.filter(user=self.user, is_default=True).exclude(
                id=self.id
            ).update(is_default=False)
        super().save(*args, **kwargs)
    
    def get_full_address(self):
        """Get formatted full address"""
        address = f"{self.address_line1}"
        if self.address_line2:
            address += f", {self.address_line2}"
        address += f", {self.city}, {self.state} {self.postal_code}, {self.country}"
        return address
    
    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'id': self.id,
            'fullName': self.full_name,
            'phoneNumber': self.phone_number,
            'line1': self.address_line1,
            'line2': self.address_line2,
            'city': self.city,
            'state': self.state,
            'postalCode': self.postal_code,
            'country': self.country,
            'type': self.address_type,
            'isDefault': self.is_default,
            'fullAddress': self.get_full_address(),
            'createdAt': self.created_at.isoformat(),
        }


class OTPLog(models.Model):
    """Audit log for OTP attempts"""
    
    class OTPAction(models.TextChoices):
        SENT = 'sent', _('OTP Sent')
        VERIFIED = 'verified', _('OTP Verified')
        FAILED = 'failed', _('OTP Failed')
        EXPIRED = 'expired', _('OTP Expired')
    
    phone_number = models.CharField(max_length=20)
    action = models.CharField(max_length=20, choices=OTPAction.choices)
    otp = models.ForeignKey(
        OTPVerification,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'otp_logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['phone_number', 'action']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.phone_number} - {self.action} at {self.created_at}"
