"""
Vendor Employee Management Models
Allows store owners to manage employees with role-based permissions
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _


class VendorEmployee(models.Model):
    """Employee working for a vendor store"""
    
    class EmployeeRole(models.TextChoices):
        OWNER = 'owner', _('Store Owner')
        MANAGER = 'manager', _('Store Manager')
        INVENTORY_MANAGER = 'inventory_manager', _('Inventory Manager')
        SUPPORT = 'customer_support', _('Customer Support')
        FINANCE = 'finance_officer', _('Finance Officer')
    
    class EmployeeStatus(models.TextChoices):
        ACTIVE = 'active', _('Active')
        INACTIVE = 'inactive', _('Inactive')
        SUSPENDED = 'suspended', _('Suspended')
    
    # Link to vendor (store owner)
    vendor = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='employees_managed'
    )
    
    # Link to employee user
    employee = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='vendor_roles'
    )
    
    role = models.CharField(
        max_length=20,
        choices=EmployeeRole.choices,
        default=EmployeeRole.MANAGER
    )
    
    status = models.CharField(
        max_length=20,
        choices=EmployeeStatus.choices,
        default=EmployeeStatus.ACTIVE
    )
    
    # Permissions
    can_manage_products = models.BooleanField(default=False)
    can_manage_inventory = models.BooleanField(default=False)
    can_manage_orders = models.BooleanField(default=False)
    can_manage_customers = models.BooleanField(default=False)
    can_view_reports = models.BooleanField(default=False)
    can_manage_employees = models.BooleanField(default=False)
    can_withdraw_funds = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'vendor_employees'
        unique_together = ['vendor', 'employee']
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['vendor', 'role']),
            models.Index(fields=['employee', 'vendor']),
        ]
    
    def __str__(self):
        return f"{self.employee.username} - {self.get_role_display()} for {self.vendor.username}"
    
    def save(self, *args, **kwargs):
        """Auto-set permissions based on role"""
        self._set_permissions_by_role()
        super().save(*args, **kwargs)
    
    def _set_permissions_by_role(self):
        """Set permissions based on employee role"""
        # Reset all permissions
        self.can_manage_products = False
        self.can_manage_inventory = False
        self.can_manage_orders = False
        self.can_manage_customers = False
        self.can_view_reports = False
        self.can_manage_employees = False
        self.can_withdraw_funds = False
        
        # Set permissions based on role
        if self.role == self.EmployeeRole.OWNER:
            # Full access
            self.can_manage_products = True
            self.can_manage_inventory = True
            self.can_manage_orders = True
            self.can_manage_customers = True
            self.can_view_reports = True
            self.can_manage_employees = True
            self.can_withdraw_funds = True
        
        elif self.role == self.EmployeeRole.MANAGER:
            # Manage products and orders
            self.can_manage_products = True
            self.can_manage_inventory = True
            self.can_manage_orders = True
            self.can_view_reports = True
        
        elif self.role == self.EmployeeRole.INVENTORY_MANAGER:
            # Only inventory
            self.can_manage_inventory = True
            self.can_view_reports = True
        
        elif self.role == self.EmployeeRole.SUPPORT:
            # Customer support
            self.can_manage_customers = True
            self.can_manage_orders = True
            self.can_view_reports = False
        
        elif self.role == self.EmployeeRole.FINANCE:
            # Finance officer - view reports and handle payouts
            self.can_view_reports = True
            self.can_withdraw_funds = True


class StockAlert(models.Model):
    """Alert when product stock falls below threshold"""
    
    class AlertType(models.TextChoices):
        LOW_STOCK = 'low_stock', _('Low Stock')
        OUT_OF_STOCK = 'out_of_stock', _('Out of Stock')
        BACK_IN_STOCK = 'back_in_stock', _('Back in Stock')
    
    class AlertStatus(models.TextChoices):
        ACTIVE = 'active', _('Active')
        RESOLVED = 'resolved', _('Resolved')
        IGNORED = 'ignored', _('Ignored')
    
    product = models.ForeignKey(
        'product_service.Product',
        on_delete=models.CASCADE,
        related_name='stock_alerts'
    )
    
    alert_type = models.CharField(
        max_length=20,
        choices=AlertType.choices
    )
    
    status = models.CharField(
        max_length=20,
        choices=AlertStatus.choices,
        default=AlertStatus.ACTIVE
    )
    
    current_quantity = models.IntegerField()
    threshold_quantity = models.IntegerField()
    
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'stock_alerts'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['product', 'status']),
            models.Index(fields=['alert_type', 'status']),
        ]
    
    def __str__(self):
        return f"{self.product.name} - {self.get_alert_type_display()}"
