"""
Vendor Management GraphQL Schema
Mutations and Queries for vendor employee management and stock alerts
"""
import graphene
from graphene_django import DjangoObjectType
from django.contrib.auth.models import User
from .vendor_management_models import VendorEmployee, StockAlert


class VendorEmployeeType(DjangoObjectType):
    """GraphQL type for VendorEmployee"""
    role_display = graphene.String()
    status_display = graphene.String()
    
    class Meta:
        model = VendorEmployee
        fields = [
            'id', 'vendor', 'employee', 'role', 'status',
            'can_manage_products', 'can_manage_inventory', 'can_manage_orders',
            'can_manage_customers', 'can_view_reports', 'can_manage_employees',
            'can_withdraw_funds', 'created_at'
        ]
    
    def resolve_role_display(self, info):
        return self.get_role_display()
    
    def resolve_status_display(self, info):
        return self.get_status_display()


class StockAlertType(DjangoObjectType):
    """GraphQL type for StockAlert"""
    alert_type_display = graphene.String()
    status_display = graphene.String()
    
    class Meta:
        model = StockAlert
        fields = [
            'id', 'product', 'alert_type', 'status',
            'current_quantity', 'threshold_quantity', 'created_at'
        ]
    
    def resolve_alert_type_display(self, info):
        return self.get_alert_type_display()
    
    def resolve_status_display(self, info):
        return self.get_status_display()


# Mutations

class CreateVendorEmployeeMutation(graphene.Mutation):
    """Create a new vendor employee"""
    class Arguments:
        vendor_id = graphene.ID(required=True)
        employee_id = graphene.ID(required=True)
        role = graphene.String(required=True, description="Role: owner, manager, inventory_manager, customer_support, finance_officer")
    
    success = graphene.Boolean()
    message = graphene.String()
    employee = graphene.Field(VendorEmployeeType)
    
    def mutate(self, info, vendor_id, employee_id, role):
        user = info.context.user
        
        if not user.is_authenticated:
            return CreateVendorEmployeeMutation(success=False, message="User must be authenticated")
        
        try:
            vendor = User.objects.get(id=vendor_id)
        except User.DoesNotExist:
            return CreateVendorEmployeeMutation(success=False, message="Vendor not found")
        
        # Only vendor owner can create employees
        if user.id != vendor_id:
            return CreateVendorEmployeeMutation(success=False, message="Only store owner can create employees")
        
        try:
            employee_user = User.objects.get(id=employee_id)
        except User.DoesNotExist:
            return CreateVendorEmployeeMutation(success=False, message="Employee user not found")
        
        # Validate role
        valid_roles = [choice[0] for choice in VendorEmployee.EmployeeRole.choices]
        if role not in valid_roles:
            return CreateVendorEmployeeMutation(success=False, message=f"Invalid role: {role}")
        
        # Check if employee already exists for this vendor
        existing = VendorEmployee.objects.filter(vendor=vendor, employee=employee_user).first()
        if existing:
            return CreateVendorEmployeeMutation(success=False, message="Employee already assigned to this vendor")
        
        # Create employee
        vendor_employee = VendorEmployee.objects.create(
            vendor=vendor,
            employee=employee_user,
            role=role
        )
        
        return CreateVendorEmployeeMutation(
            success=True,
            message=f"Employee {employee_user.username} added as {vendor_employee.get_role_display()}",
            employee=vendor_employee
        )


class UpdateVendorEmployeeMutation(graphene.Mutation):
    """Update vendor employee role or status"""
    class Arguments:
        employee_id = graphene.ID(required=True)
        role = graphene.String(description="New role")
        status = graphene.String(description="New status: active, inactive, suspended")
    
    success = graphene.Boolean()
    message = graphene.String()
    employee = graphene.Field(VendorEmployeeType)
    
    def mutate(self, info, employee_id, role=None, status=None):
        user = info.context.user
        
        if not user.is_authenticated:
            return UpdateVendorEmployeeMutation(success=False, message="User must be authenticated")
        
        try:
            vendor_employee = VendorEmployee.objects.get(id=employee_id)
        except VendorEmployee.DoesNotExist:
            return UpdateVendorEmployeeMutation(success=False, message="Employee not found")
        
        # Only vendor owner can update employees
        if user.id != vendor_employee.vendor_id:
            return UpdateVendorEmployeeMutation(success=False, message="Only store owner can update employees")
        
        # Cannot remove the owner
        if vendor_employee.role == VendorEmployee.EmployeeRole.OWNER and role != VendorEmployee.EmployeeRole.OWNER:
            return UpdateVendorEmployeeMutation(success=False, message="Cannot change owner role")
        
        if role:
            valid_roles = [choice[0] for choice in VendorEmployee.EmployeeRole.choices]
            if role not in valid_roles:
                return UpdateVendorEmployeeMutation(success=False, message=f"Invalid role: {role}")
            vendor_employee.role = role
        
        if status:
            valid_statuses = [choice[0] for choice in VendorEmployee.EmployeeStatus.choices]
            if status not in valid_statuses:
                return UpdateVendorEmployeeMutation(success=False, message=f"Invalid status: {status}")
            vendor_employee.status = status
        
        vendor_employee.save()
        
        return UpdateVendorEmployeeMutation(
            success=True,
            message=f"Employee updated successfully",
            employee=vendor_employee
        )


class RemoveVendorEmployeeMutation(graphene.Mutation):
    """Remove vendor employee"""
    class Arguments:
        employee_id = graphene.ID(required=True)
    
    success = graphene.Boolean()
    message = graphene.String()
    
    def mutate(self, info, employee_id):
        user = info.context.user
        
        if not user.is_authenticated:
            return RemoveVendorEmployeeMutation(success=False, message="User must be authenticated")
        
        try:
            vendor_employee = VendorEmployee.objects.get(id=employee_id)
        except VendorEmployee.DoesNotExist:
            return RemoveVendorEmployeeMutation(success=False, message="Employee not found")
        
        # Only vendor owner can remove employees
        if user.id != vendor_employee.vendor_id:
            return RemoveVendorEmployeeMutation(success=False, message="Only store owner can remove employees")
        
        # Cannot remove the owner
        if vendor_employee.role == VendorEmployee.EmployeeRole.OWNER:
            return RemoveVendorEmployeeMutation(success=False, message="Cannot remove owner")
        
        employee_name = vendor_employee.employee.username
        vendor_employee.delete()
        
        return RemoveVendorEmployeeMutation(
            success=True,
            message=f"Employee {employee_name} removed successfully"
        )


class ResolveStockAlertMutation(graphene.Mutation):
    """Mark stock alert as resolved"""
    class Arguments:
        alert_id = graphene.ID(required=True)
    
    success = graphene.Boolean()
    message = graphene.String()
    alert = graphene.Field(StockAlertType)
    
    def mutate(self, info, alert_id):
        user = info.context.user
        
        if not user.is_authenticated:
            return ResolveStockAlertMutation(success=False, message="User must be authenticated")
        
        try:
            alert = StockAlert.objects.select_related('product').get(id=alert_id)
        except StockAlert.DoesNotExist:
            return ResolveStockAlertMutation(success=False, message="Alert not found")
        
        # Only vendor or admin can resolve alerts
        if user.id != alert.product.vendor_id and not user.is_staff:
            return ResolveStockAlertMutation(success=False, message="Permission denied")
        
        from django.utils import timezone
        alert.status = StockAlert.AlertStatus.RESOLVED
        alert.resolved_at = timezone.now()
        alert.save()
        
        return ResolveStockAlertMutation(
            success=True,
            message="Stock alert resolved",
            alert=alert
        )


# Queries

class VendorManagementQuery(graphene.ObjectType):
    """Vendor management queries"""
    
    vendor_employees = graphene.List(
        VendorEmployeeType,
        vendor_id=graphene.ID(required=True)
    )
    
    vendor_employee_detail = graphene.Field(
        VendorEmployeeType,
        employee_id=graphene.ID(required=True)
    )
    
    my_vendor_roles = graphene.List(VendorEmployeeType)
    
    stock_alerts = graphene.List(
        StockAlertType,
        vendor_id=graphene.ID(required=True),
        status=graphene.String()
    )
    
    def resolve_vendor_employees(self, info, vendor_id):
        """Get all employees for a vendor"""
        user = info.context.user
        
        if not user.is_authenticated:
            return []
        
        # Only vendor owner can view their employees
        if str(user.id) != vendor_id and not user.is_staff:
            return []
        
        return VendorEmployee.objects.filter(vendor_id=vendor_id).select_related('employee')
    
    def resolve_vendor_employee_detail(self, info, employee_id):
        """Get vendor employee details"""
        user = info.context.user
        
        if not user.is_authenticated:
            return None
        
        try:
            vendor_employee = VendorEmployee.objects.select_related('vendor', 'employee').get(id=employee_id)
            
            # Only vendor owner or the employee can view
            if user.id != vendor_employee.vendor_id and user.id != vendor_employee.employee_id and not user.is_staff:
                return None
            
            return vendor_employee
        except VendorEmployee.DoesNotExist:
            return None
    
    def resolve_my_vendor_roles(self, info):
        """Get all vendor roles for current user"""
        user = info.context.user
        
        if not user.is_authenticated:
            return []
        
        return VendorEmployee.objects.filter(employee=user).select_related('vendor')
    
    def resolve_stock_alerts(self, info, vendor_id, status=None):
        """Get stock alerts for a vendor"""
        user = info.context.user
        
        if not user.is_authenticated:
            return []
        
        # Only vendor owner can view alerts
        if str(user.id) != vendor_id and not user.is_staff:
            return []
        
        queryset = StockAlert.objects.filter(
            product__vendor_id=vendor_id
        ).select_related('product')
        
        if status:
            queryset = queryset.filter(status=status)
        
        return queryset.order_by('-created_at')


# Combine Mutations
class VendorManagementMutation(graphene.ObjectType):
    """Vendor management mutations"""
    create_vendor_employee = CreateVendorEmployeeMutation.Field()
    update_vendor_employee = UpdateVendorEmployeeMutation.Field()
    remove_vendor_employee = RemoveVendorEmployeeMutation.Field()
    resolve_stock_alert = ResolveStockAlertMutation.Field()
