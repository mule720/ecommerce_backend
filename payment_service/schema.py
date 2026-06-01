"""
Payment Service GraphQL Schema
GraphQL API for payment management
"""
import graphene
from graphene import relay
from graphene_django import DjangoObjectType
from graphene_django.filter import DjangoFilterConnectionField
from django_filters import FilterSet, CharFilter, NumberFilter
from decimal import Decimal
import uuid
from .models import Payment, Refund, SavedPaymentMethod, VendorPayout, PaymentIdempotencyKey

# Alias so existing schema code that references PaymentMethod still works
PaymentMethod = SavedPaymentMethod
from ecom_backend.event_bus import publish_event


class PaymentType(DjangoObjectType):
    """GraphQL type for Payment model"""
    class Meta:
        """Defines the purpose and behavior of the `Meta` class."""
        model = Payment
        fields = "__all__"
        interfaces = (relay.Node,)


class RefundType(DjangoObjectType):
    """GraphQL type for Refund model"""
    class Meta:
        """Defines the purpose and behavior of the `Meta` class."""
        model = Refund
        fields = "__all__"
        interfaces = (relay.Node,)


class CustomerPaymentMethodType(DjangoObjectType):
    """GraphQL type for PaymentMethod model"""
    class Meta:
        """Defines the purpose and behavior of the `Meta` class."""
        model = PaymentMethod
        fields = "__all__"
        interfaces = (relay.Node,)


class VendorPayoutType(DjangoObjectType):
    """GraphQL type for VendorPayout model"""
    class Meta:
        """Defines the purpose and behavior of the `Meta` class."""
        model = VendorPayout
        fields = "__all__"
        interfaces = (relay.Node,)


# Filters
class PaymentFilter(FilterSet):
    """Filter for Payment queries"""
    status = CharFilter(field_name='status')
    method = CharFilter(field_name='method')
    
    class Meta:
        """Defines the purpose and behavior of the `Meta` class."""
        model = Payment
        fields = ['status', 'method']


class RefundFilter(FilterSet):
    """Filter for Refund queries"""
    status = CharFilter(field_name='status')
    min_amount = NumberFilter(field_name='amount', lookup_expr='gte')
    max_amount = NumberFilter(field_name='amount', lookup_expr='lte')

    class Meta:
        """Defines the purpose and behavior of the `Meta` class."""
        model = Refund
        fields = ['status', 'min_amount', 'max_amount']


class Query(graphene.ObjectType):
    """Payment Service Queries"""
    
    # Payment queries
    all_payments = DjangoFilterConnectionField(
        PaymentType,
        filterset_class=PaymentFilter
    )
    payment = relay.Node.Field(PaymentType)
    payment_by_transaction = graphene.Field(
        PaymentType,
        transaction_id=graphene.String(required=True)
    )
    payments_by_order = graphene.List(
        PaymentType,
        order_id=graphene.ID(required=True)
    )
    my_payments = graphene.List(PaymentType)
    
    # Refund queries
    all_refunds = DjangoFilterConnectionField(
        RefundType,
        filterset_class=RefundFilter
    )
    refund = relay.Node.Field(RefundType)
    
    # Payment method queries
    my_payment_methods = graphene.List(CustomerPaymentMethodType)
    
    # Vendor payout queries
    vendor_payouts = graphene.List(VendorPayoutType)
    
    # Resolvers
    def resolve_all_payments(self, info, **kwargs):
        """Resolver for the GraphQL field `all payments`."""
        return Payment.objects.all()
    
    def resolve_payment_by_transaction(self, info, transaction_id):
        """Resolver for the GraphQL field `payment by transaction`."""
        try:
            return Payment.objects.get(transaction_id=transaction_id)
        except Payment.DoesNotExist:
            return None
    
    def resolve_payments_by_order(self, info, order_id):
        """Resolver for the GraphQL field `payments by order`."""
        try:
            return Payment.objects.filter(order_id=int(order_id))
        except ValueError:
            return Payment.objects.none()
    
    def resolve_my_payments(self, info):
        """Resolver for the GraphQL field `my payments`."""
        user = info.context.user
        if user.is_anonymous:
            raise Exception('Not logged in!')
        return Payment.objects.filter(customer=user)
    
    def resolve_all_refunds(self, info, **kwargs):
        """Resolver for the GraphQL field `all refunds`."""
        return Refund.objects.all()
    
    def resolve_my_payment_methods(self, info):
        """Resolver for the GraphQL field `my payment methods`."""
        user = info.context.user
        if user.is_anonymous:
            raise Exception('Not logged in!')
        return PaymentMethod.objects.filter(customer=user)
    
    def resolve_vendor_payouts(self, info):
        """Resolver for the GraphQL field `vendor payouts`."""
        user = info.context.user
        if user.is_anonymous:
            raise Exception('Not logged in!')
        return VendorPayout.objects.filter(vendor=user)


# Mutations
class ProcessPaymentMutation(graphene.Mutation):
    """
    Process a payment for an order.
    Accepts an optional idempotency_key to prevent double-charges on retries.
    For new purchases use completePurchase (checkout_service) instead — it is
    fully atomic.  This mutation is kept for administrative/retry scenarios.
    """
    class Arguments:
        order_id        = graphene.ID(required=True)
        method          = graphene.String(required=True)
        gateway_name    = graphene.String()
        idempotency_key = graphene.String()

    payment = graphene.Field(PaymentType)

    @classmethod
    def mutate(cls, root, info, order_id, method, gateway_name='internal', idempotency_key=None):
        from order_service.models import Order

        user = info.context.user
        if user.is_anonymous:
            raise Exception('Not logged in!')

        # Idempotency: return existing payment if this key was already processed
        if idempotency_key:
            existing = PaymentIdempotencyKey.objects.filter(
                idempotency_key=idempotency_key, customer=user
            ).select_related('payment').first()
            if existing:
                return ProcessPaymentMutation(payment=existing.payment)

        try:
            order = Order.objects.get(pk=int(order_id))
        except (Order.DoesNotExist, ValueError):
            raise Exception('Order not found')

        transaction_id = f"TXN-{uuid.uuid4().hex[:12].upper()}"

        payment = Payment.objects.create(
            order=order,
            customer=user,
            amount=order.total,
            method=method,
            transaction_id=transaction_id,
            gateway_name=gateway_name,
            status='pending',
        )

        if idempotency_key:
            PaymentIdempotencyKey.objects.create(
                idempotency_key=idempotency_key,
                payment=payment,
                customer=user,
            )

        publish_event('payment.events', 'PaymentRequested', {
            'payment_id':     str(payment.id),
            'transaction_id': payment.transaction_id,
            'order_id':       str(order.id),
            'order_number':   order.order_number,
            'customer_id':    str(user.id),
            'amount':         str(order.total),
            'currency':       order.currency,
            'method':         method,
            'gateway_name':   gateway_name,
        })

        return ProcessPaymentMutation(payment=payment)


class CreateRefundMutation(graphene.Mutation):
    """Create a refund request"""
    class Arguments:
        """Defines the purpose and behavior of the `Arguments` class."""
        payment_id = graphene.ID(required=True)
        amount = graphene.Decimal(required=True)
        reason = graphene.String(required=True)
    
    refund = graphene.Field(RefundType)
    
    @classmethod
    def mutate(cls, root, info, payment_id, amount, reason):
        """Executes mutation business rules and returns the mutation response object."""
        user = info.context.user
        if user.is_anonymous:
            raise Exception('Not logged in!')
        
        try:
            payment = Payment.objects.get(pk=int(payment_id))
        except (Payment.DoesNotExist, ValueError):
            raise Exception('Payment not found')
        
        transaction_id = f"REF-{uuid.uuid4().hex[:12].upper()}"
        
        refund = Refund.objects.create(
            payment=payment,
            order=payment.order,
            amount=amount,
            reason=reason,
            transaction_id=transaction_id,
            status='pending'
        )

        publish_event('payment.events', 'RefundRequested', {
            'refund_id': str(refund.id),
            'payment_id': str(payment.id),
            'transaction_id': payment.transaction_id,
            'order_id': str(payment.order_id),
            'amount': str(amount),
            'reason': reason,
            'customer_id': str(user.id),
        })
        
        return CreateRefundMutation(refund=refund)


class SavePaymentMethodMutation(graphene.Mutation):
    """Save a payment method for customer"""
    class Arguments:
        """Defines the purpose and behavior of the `Arguments` class."""
        type = graphene.String(required=True)
        last_four = graphene.String(required=True)
        brand = graphene.String()
        expiry_month = graphene.Int(required=True)
        expiry_year = graphene.Int(required=True)
        gateway_token = graphene.String(required=True)
        is_default = graphene.Boolean()
    
    payment_method = graphene.Field(CustomerPaymentMethodType)
    
    @classmethod
    def mutate(cls, root, info, **kwargs):
        """Executes mutation business rules and returns the mutation response object."""
        user = info.context.user
        if user.is_anonymous:
            raise Exception('Not logged in!')
        
        is_default = kwargs.get('is_default', False)
        
        # If setting as default, unset other defaults
        if is_default:
            PaymentMethod.objects.filter(customer=user, is_default=True).update(is_default=False)
        
        payment_method = PaymentMethod.objects.create(
            customer=user,
            type=kwargs['type'],
            last_four=kwargs['last_four'],
            brand=kwargs.get('brand', ''),
            expiry_month=kwargs['expiry_month'],
            expiry_year=kwargs['expiry_year'],
            gateway_token=kwargs['gateway_token'],
            is_default=is_default
        )
        
        return SavePaymentMethodMutation(payment_method=payment_method)


class DeletePaymentMethodMutation(graphene.Mutation):
    """Delete a saved payment method"""
    class Arguments:
        """Defines the purpose and behavior of the `Arguments` class."""
        payment_method_id = graphene.ID(required=True)
    
    success = graphene.Boolean()
    
    @classmethod
    def mutate(cls, root, info, payment_method_id):
        """Executes mutation business rules and returns the mutation response object."""
        user = info.context.user
        if user.is_anonymous:
            raise Exception('Not logged in!')
        
        try:
            payment_method = PaymentMethod.objects.get(
                pk=int(payment_method_id),
                customer=user
            )
            payment_method.delete()
            return DeletePaymentMethodMutation(success=True)
        except (PaymentMethod.DoesNotExist, ValueError):
            return DeletePaymentMethodMutation(success=False)


class CreateVendorPayoutMutation(graphene.Mutation):
    """Create a vendor payout"""
    class Arguments:
        """Defines the purpose and behavior of the `Arguments` class."""
        vendor_id = graphene.ID(required=True)
        amount = graphene.Decimal(required=True)
        order_item_ids = graphene.List(graphene.ID)
    
    payout = graphene.Field(VendorPayoutType)
    
    @classmethod
    def mutate(cls, root, info, vendor_id, amount, order_item_ids=None):
        """Executes mutation business rules and returns the mutation response object."""
        from order_service.models import OrderItem
        
        try:
            transaction_id = f"PAYOUT-{uuid.uuid4().hex[:12].upper()}"
            
            payout = VendorPayout.objects.create(
                vendor_id=int(vendor_id),
                amount=amount,
                transaction_id=transaction_id,
                status='pending'
            )
            
            if order_item_ids:
                order_items = OrderItem.objects.filter(pk__in=[int(oid) for oid in order_item_ids])
                payout.order_items.set(order_items)

            publish_event('payment.events', 'VendorPayoutRequested', {
                'payout_id': str(payout.id),
                'transaction_id': payout.transaction_id,
                'vendor_id': str(vendor_id),
                'amount': str(amount),
                'order_item_ids': [str(oid) for oid in (order_item_ids or [])],
            })
            
            return CreateVendorPayoutMutation(payout=payout)
        except ValueError:
            raise Exception('Invalid vendor or order item')


class Mutation(graphene.ObjectType):
    """Payment Service Mutations"""
    
    process_payment = ProcessPaymentMutation.Field()
    create_refund = CreateRefundMutation.Field()
    save_payment_method = SavePaymentMethodMutation.Field()
    delete_payment_method = DeletePaymentMethodMutation.Field()
    create_vendor_payout = CreateVendorPayoutMutation.Field()


# Schema definition for Payment Service
# NOTE: The gateway composes service Query/Mutation classes directly.
# Avoid eager schema instantiation here to prevent duplicate type
# registrations when all services are imported together.
