"""
Checkout Service GraphQL Schema
"""
import graphene
from graphene_django import DjangoObjectType
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.models import User
from .models import CheckoutSession, ShippingMethod
from cart_service.models import Cart
from user_service.auth_models import DeliveryAddress


class CheckoutShippingMethodType(DjangoObjectType):
    """GraphQL type for ShippingMethod (checkout-specific)"""
    class Meta:
        model = ShippingMethod
        fields = ['id', 'name', 'shipping_type', 'base_cost', 'estimated_days', 'description']


class CheckoutSessionType(DjangoObjectType):
    """GraphQL type for CheckoutSession"""
    
    shipping_method = graphene.Field(CheckoutShippingMethodType)
    delivery_address = graphene.String()
    is_expired = graphene.Boolean()
    
    class Meta:
        model = CheckoutSession
        fields = [
            'id', 'status', 'subtotal', 'shipping_cost', 
            'tax_amount', 'total', 'created_at', 'updated_at', 'expires_at'
        ]
    
    def resolve_delivery_address(self, info):
        """Return formatted delivery address"""
        if self.delivery_address:
            return self.delivery_address.get_full_address()
        return None
    
    def resolve_is_expired(self, info):
        """Check if session is expired"""
        return self.is_expired()


class InitializeCheckoutMutation(graphene.Mutation):
    """Initialize checkout session from cart"""
    
    class Arguments:
        shipping_address_id = graphene.Int(required=True)
    
    checkout_session = graphene.Field(CheckoutSessionType)
    message = graphene.String()
    success = graphene.Boolean()
    
    def mutate(self, info, shipping_address_id):
        user = info.context.user
        
        # Require authentication
        if not user.is_authenticated:
            return InitializeCheckoutMutation(
                success=False,
                message="User must be authenticated"
            )
        
        # Get user's cart
        try:
            cart = Cart.objects.get(customer=user)
            if cart.items.count() == 0:
                return InitializeCheckoutMutation(
                    success=False,
                    message="Cart is empty"
                )
        except Cart.DoesNotExist:
            return InitializeCheckoutMutation(
                success=False,
                message="Cart not found"
            )
        
        # Get delivery address
        try:
            delivery_address = DeliveryAddress.objects.get(
                id=shipping_address_id,
                user=user
            )
        except DeliveryAddress.DoesNotExist:
            return InitializeCheckoutMutation(
                success=False,
                message="Delivery address not found"
            )
        
        # Create checkout session
        # Expire after 30 minutes
        expires_at = timezone.now() + timedelta(minutes=30)
        
        checkout = CheckoutSession.objects.create(
            customer=user,
            cart=cart,
            delivery_address=delivery_address,
            expires_at=expires_at,
        )
        
        # Calculate initial totals with no shipping method
        checkout.calculate_totals()
        
        return InitializeCheckoutMutation(
            success=True,
            checkout_session=checkout,
            message="Checkout session initialized"
        )


class SelectShippingMethodMutation(graphene.Mutation):
    """Select shipping method for checkout"""
    
    class Arguments:
        checkout_session_id = graphene.Int(required=True)
        shipping_method_id = graphene.Int(required=True)
    
    checkout_session = graphene.Field(CheckoutSessionType)
    message = graphene.String()
    success = graphene.Boolean()
    
    def mutate(self, info, checkout_session_id, shipping_method_id):
        user = info.context.user
        
        if not user.is_authenticated:
            return SelectShippingMethodMutation(
                success=False,
                message="User must be authenticated"
            )
        
        try:
            checkout = CheckoutSession.objects.get(
                id=checkout_session_id,
                customer=user,
                status='active'
            )
        except CheckoutSession.DoesNotExist:
            return SelectShippingMethodMutation(
                success=False,
                message="Checkout session not found"
            )
        
        if checkout.is_expired():
            checkout.status = 'expired'
            checkout.save()
            return SelectShippingMethodMutation(
                success=False,
                message="Checkout session has expired"
            )
        
        try:
            shipping_method = ShippingMethod.objects.get(id=shipping_method_id, is_active=True)
        except ShippingMethod.DoesNotExist:
            return SelectShippingMethodMutation(
                success=False,
                message="Shipping method not found"
            )
        
        checkout.shipping_method = shipping_method
        checkout.calculate_totals()
        
        return SelectShippingMethodMutation(
            success=True,
            checkout_session=checkout,
            message="Shipping method selected"
        )


class UpdateShippingAddressMutation(graphene.Mutation):
    """Update shipping address in checkout"""
    
    class Arguments:
        checkout_session_id = graphene.Int(required=True)
        shipping_address_id = graphene.Int(required=True)
    
    checkout_session = graphene.Field(CheckoutSessionType)
    message = graphene.String()
    success = graphene.Boolean()
    
    def mutate(self, info, checkout_session_id, shipping_address_id):
        user = info.context.user
        
        if not user.is_authenticated:
            return UpdateShippingAddressMutation(
                success=False,
                message="User must be authenticated"
            )
        
        try:
            checkout = CheckoutSession.objects.get(
                id=checkout_session_id,
                customer=user,
                status='active'
            )
        except CheckoutSession.DoesNotExist:
            return UpdateShippingAddressMutation(
                success=False,
                message="Checkout session not found"
            )
        
        if checkout.is_expired():
            checkout.status = 'expired'
            checkout.save()
            return UpdateShippingAddressMutation(
                success=False,
                message="Checkout session has expired"
            )
        
        try:
            delivery_address = DeliveryAddress.objects.get(
                id=shipping_address_id,
                user=user
            )
        except DeliveryAddress.DoesNotExist:
            return UpdateShippingAddressMutation(
                success=False,
                message="Delivery address not found"
            )
        
        checkout.delivery_address = delivery_address
        checkout.save()
        
        return UpdateShippingAddressMutation(
            success=True,
            checkout_session=checkout,
            message="Shipping address updated"
        )


class CheckoutMutation(graphene.ObjectType):
    """Checkout mutations"""
    initialize_checkout = InitializeCheckoutMutation.Field()
    select_shipping_method = SelectShippingMethodMutation.Field()
    update_shipping_address = UpdateShippingAddressMutation.Field()


class CheckoutQuery(graphene.ObjectType):
    """Checkout queries"""
    
    get_checkout_session = graphene.Field(CheckoutSessionType, checkout_id=graphene.Int(required=True))
    available_shipping_methods = graphene.List(CheckoutShippingMethodType)
    my_checkout_sessions = graphene.List(CheckoutSessionType)
    
    def resolve_get_checkout_session(self, info, checkout_id):
        """Get checkout session details"""
        user = info.context.user
        
        if not user.is_authenticated:
            return None
        
        try:
            return CheckoutSession.objects.get(id=checkout_id, customer=user)
        except CheckoutSession.DoesNotExist:
            return None
    
    def resolve_available_shipping_methods(self, info):
        """Get all active shipping methods"""
        return ShippingMethod.objects.filter(is_active=True)
    
    def resolve_my_checkout_sessions(self, info):
        """Get user's active checkout sessions"""
        user = info.context.user
        
        if not user.is_authenticated:
            return CheckoutSession.objects.none()
        
        return CheckoutSession.objects.filter(
            customer=user,
            status='active'
        )
