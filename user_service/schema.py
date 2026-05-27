"""
User Service GraphQL Schema
GraphQL API for user management
"""
import graphene
from graphene import relay
from graphene_django import DjangoObjectType
from graphene_django.filter import DjangoFilterConnectionField
from django.db.models import Q
import django_filters
from .models import User, CustomerProfile, VendorProfile, DriverProfile
from .auth_schema import AuthQuery, AuthMutation


class UserType(DjangoObjectType):
    """GraphQL type for User model"""
    class Meta:
        """Defines the purpose and behavior of the `Meta` class."""
        model = User
        fields = "__all__"
        interfaces = (relay.Node,)


class CustomerProfileType(DjangoObjectType):
    """GraphQL type for CustomerProfile model"""
    class Meta:
        """Defines the purpose and behavior of the `Meta` class."""
        model = CustomerProfile
        fields = "__all__"


class VendorProfileType(DjangoObjectType):
    """GraphQL type for VendorProfile model"""
    class Meta:
        """Defines the purpose and behavior of the `Meta` class."""
        model = VendorProfile
        fields = "__all__"
        interfaces = (relay.Node,)
        filter_fields = []


class DriverProfileType(DjangoObjectType):
    """GraphQL type for DriverProfile model"""
    class Meta:
        """Defines the purpose and behavior of the `Meta` class."""
        model = DriverProfile
        fields = "__all__"
        interfaces = (relay.Node,)
        filter_fields = []


class UserFilter(django_filters.FilterSet):
    """Django filterset for User queries"""

    role = django_filters.CharFilter(field_name='role', lookup_expr='iexact')
    is_verified = django_filters.BooleanFilter(field_name='is_verified')
    search = django_filters.CharFilter(method='filter_search')

    class Meta:
        """Defines the purpose and behavior of the `Meta` class."""
        model = User
        fields = ['role', 'is_verified']

    def filter_search(self, queryset, name, value):
        """Applies custom queryset filtering for user-supplied filter values."""
        return queryset.filter(
            Q(username__icontains=value)
            | Q(email__icontains=value)
            | Q(first_name__icontains=value)
            | Q(last_name__icontains=value)
        )


class Query(AuthQuery, graphene.ObjectType):
    """User Service Queries"""
    
    # Get all users with filtering and pagination
    all_users = DjangoFilterConnectionField(
        UserType,
        filterset_class=UserFilter
    )
    
    # Get single user by ID
    user = relay.Node.Field(UserType)
    
    # Get current authenticated user
    me = graphene.Field(UserType)
    
    # Get users by role
    users_by_role = graphene.List(
        UserType,
        role=graphene.String(required=True)
    )
    
    # Get customer profile
    customer_profile = graphene.Field(CustomerProfileType)
    
    # Get vendor profile by ID
    vendor_profile = graphene.Field(
        VendorProfileType,
        id=graphene.ID(required=True)
    )
    
    # Get all vendors
    all_vendors = DjangoFilterConnectionField(VendorProfileType)
    
    # Get driver profile by ID
    driver_profile = graphene.Field(
        DriverProfileType,
        id=graphene.ID(required=True)
    )
    
    # Get all drivers
    all_drivers = DjangoFilterConnectionField(DriverProfileType)
    
    def resolve_all_users(self, info, **kwargs):
        """Resolver for the GraphQL field `all users`."""
        return User.objects.all()
    
    def resolve_me(self, info):
        """Resolver for the GraphQL field `me`."""
        user = info.context.user
        if user.is_anonymous:
            raise Exception('Not logged in!')
        return user
    
    def resolve_users_by_role(self, info, role):
        """Resolver for the GraphQL field `users by role`."""
        return User.objects.filter(role=role)
    
    def resolve_customer_profile(self, info):
        """Resolver for the GraphQL field `customer profile`."""
        user = info.context.user
        if user.is_anonymous:
            raise Exception('Not logged in!')
        try:
            return user.customer_profile
        except CustomerProfile.DoesNotExist:
            return None
    
    def resolve_vendor_profile(self, info, id):
        """Resolver for the GraphQL field `vendor profile`."""
        try:
            vendor_id = int(id)
            return VendorProfile.objects.get(pk=vendor_id)
        except (VendorProfile.DoesNotExist, ValueError):
            return None
    
    def resolve_all_vendors(self, info, **kwargs):
        """Resolver for the GraphQL field `all vendors`."""
        return VendorProfile.objects.all()
    
    def resolve_driver_profile(self, info, id):
        """Resolver for the GraphQL field `driver profile`."""
        try:
            driver_id = int(id)
            return DriverProfile.objects.get(pk=driver_id)
        except (DriverProfile.DoesNotExist, ValueError):
            return None
    
    def resolve_all_drivers(self, info, **kwargs):
        """Resolver for the GraphQL field `all drivers`."""
        return DriverProfile.objects.all()


class CreateUserMutation(graphene.Mutation):
    """Create a new user"""
    class Arguments:
        """Defines the purpose and behavior of the `Arguments` class."""
        username = graphene.String(required=True)
        email = graphene.String(required=True)
        password = graphene.String(required=True)
        role = graphene.String(default_value='customer')
        first_name = graphene.String()
        last_name = graphene.String()
        phone = graphene.String()
    
    user = graphene.Field(UserType)
    
    @classmethod
    def mutate(cls, root, info, username, email, password, role, **kwargs):
        """Executes mutation business rules and returns the mutation response object."""
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            role=role,
            **kwargs
        )
        
        # Create profile based on role
        if role == 'customer':
            CustomerProfile.objects.create(user=user)
        elif role == 'vendor':
            VendorProfile.objects.create(
                user=user,
                business_name=username
            )
        elif role == 'driver':
            DriverProfile.objects.create(user=user)
        
        return CreateUserMutation(user=user)


class UpdateUserMutation(graphene.Mutation):
    """Update user information"""
    class Arguments:
        """Defines the purpose and behavior of the `Arguments` class."""
        id = graphene.ID(required=True)
        first_name = graphene.String()
        last_name = graphene.String()
        phone = graphene.String()
        address = graphene.String()
        city = graphene.String()
        country = graphene.String()
        postal_code = graphene.String()
    
    user = graphene.Field(UserType)
    
    @classmethod
    def mutate(cls, root, info, id, **kwargs):
        """Executes mutation business rules and returns the mutation response object."""
        try:
            user_id = int(id)
            user = User.objects.get(pk=user_id)
        except (User.DoesNotExist, ValueError):
            raise Exception('User not found')
        
        for key, value in kwargs.items():
            if value is not None:
                setattr(user, key, value)
        
        user.save()
        return UpdateUserMutation(user=user)


class UpdateCustomerProfileMutation(graphene.Mutation):
    """Update customer profile"""
    class Arguments:
        """Defines the purpose and behavior of the `Arguments` class."""
        date_of_birth = graphene.Date()
        gender = graphene.String()
    
    customer_profile = graphene.Field(CustomerProfileType)
    
    @classmethod
    def mutate(cls, root, info, **kwargs):
        """Executes mutation business rules and returns the mutation response object."""
        user = info.context.user
        if user.is_anonymous:
            raise Exception('Not logged in!')
        
        profile, _ = CustomerProfile.objects.get_or_create(user=user)
        
        for key, value in kwargs.items():
            if value is not None:
                setattr(profile, key, value)
        
        profile.save()
        return UpdateCustomerProfileMutation(customer_profile=profile)


class UpdateVendorProfileMutation(graphene.Mutation):
    """Update vendor profile"""
    class Arguments:
        """Defines the purpose and behavior of the `Arguments` class."""
        id = graphene.ID(required=True)
        business_name = graphene.String()
        business_description = graphene.String()
        business_license = graphene.String()
        tax_id = graphene.String()
        bank_account = graphene.String()
        payout_method = graphene.String()
    
    vendor_profile = graphene.Field(VendorProfileType)
    
    @classmethod
    def mutate(cls, root, info, id, **kwargs):
        """Executes mutation business rules and returns the mutation response object."""
        try:
            vendor_id = int(id)
            profile = VendorProfile.objects.get(pk=vendor_id)
        except (VendorProfile.DoesNotExist, ValueError):
            raise Exception('Vendor profile not found')
        
        for key, value in kwargs.items():
            if value is not None:
                setattr(profile, key, value)
        
        profile.save()
        return UpdateVendorProfileMutation(vendor_profile=profile)


class UpdateDriverStatusMutation(graphene.Mutation):
    """Update driver availability status"""
    class Arguments:
        """Defines the purpose and behavior of the `Arguments` class."""
        id = graphene.ID(required=True)
        status = graphene.String(required=True)
        current_location_lat = graphene.Float()
        current_location_lng = graphene.Float()
    
    driver_profile = graphene.Field(DriverProfileType)
    
    @classmethod
    def mutate(cls, root, info, id, status, **kwargs):
        """Executes mutation business rules and returns the mutation response object."""
        try:
            driver_id = int(id)
            profile = DriverProfile.objects.get(pk=driver_id)
        except (DriverProfile.DoesNotExist, ValueError):
            raise Exception('Driver profile not found')
        
        profile.status = status
        if 'current_location_lat' in kwargs:
            profile.current_location_lat = kwargs['current_location_lat']
        if 'current_location_lng' in kwargs:
            profile.current_location_lng = kwargs['current_location_lng']
        
        profile.save()
        return UpdateDriverStatusMutation(driver_profile=profile)


class ApproveVendorMutation(graphene.Mutation):
    """Approve a vendor (admin only)"""
    class Arguments:
        """Defines the purpose and behavior of the `Arguments` class."""
        id = graphene.ID(required=True)
    
    vendor_profile = graphene.Field(VendorProfileType)
    
    @classmethod
    def mutate(cls, root, info, id):
        """Executes mutation business rules and returns the mutation response object."""
        try:
            vendor_id = int(id)
            profile = VendorProfile.objects.get(pk=vendor_id)
        except (VendorProfile.DoesNotExist, ValueError):
            raise Exception('Vendor profile not found')
        
        profile.status = 'approved'
        profile.save()
        return ApproveVendorMutation(vendor_profile=profile)


class Mutation(AuthMutation, graphene.ObjectType):
    """User Service Mutations"""
    
    create_user = CreateUserMutation.Field()
    update_user = UpdateUserMutation.Field()
    update_customer_profile = UpdateCustomerProfileMutation.Field()
    update_vendor_profile = UpdateVendorProfileMutation.Field()
    update_driver_status = UpdateDriverStatusMutation.Field()
    approve_vendor = ApproveVendorMutation.Field()


# Schema definition for User Service
# NOTE: The gateway composes service Query/Mutation classes directly.
# Avoid eager schema instantiation here to prevent duplicate type
# registrations when all services are imported together.
