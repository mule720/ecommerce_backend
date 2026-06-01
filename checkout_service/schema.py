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


class CompletePurchaseMutation(graphene.Mutation):
    """
    Atomic, idempotent mutation that finalises checkout:
      1. Validates checkout session (not expired, not already completed)
      2. Creates an Order from the cart
      3. Processes payment — wallet (instant) or card/mobile-money (async via event)
      4. Marks checkout session as completed and clears the cart
      5. Returns order number + payment status

    The client MUST supply a UUID idempotency_key it generated.  Duplicate
    submissions with the same key return the original result without
    creating a second charge.
    """

    class Arguments:
        checkout_session_id = graphene.Int(required=True)
        payment_method      = graphene.String(required=True)   # 'wallet' | 'card' | 'mobile_money'
        idempotency_key     = graphene.String(required=True)
        vault_token         = graphene.String()                # required for payment_method='card'
        mobile_phone        = graphene.String()                # required for payment_method='mobile_money'

    order_number    = graphene.String()
    payment_status  = graphene.String()
    payment_id      = graphene.ID()
    order_id        = graphene.ID()
    total           = graphene.Float()
    checkout_url    = graphene.String()   # PayVault redirect URL for card/mobile_money
    success         = graphene.Boolean()
    error           = graphene.String()

    @classmethod
    def mutate(cls, root, info, checkout_session_id, payment_method,
               idempotency_key, vault_token=None, mobile_phone=None):
        import uuid
        from decimal import Decimal
        from django.db import transaction as db_transaction
        from django.db.models import F
        from django.utils import timezone
        from django.utils.text import slugify

        from order_service.models import Order, OrderItem
        from payment_service.models import Payment, PaymentIdempotencyKey
        from wallet_service.models import Wallet, WalletTransaction
        from card_vault.models import CardVaultEntry, PaymentAuditLog
        from ecom_backend.event_bus import publish_event

        user = info.context.user
        if user.is_anonymous:
            return cls(success=False, error='Not authenticated')

        # ── Idempotency check ──────────────────────────────────────────────
        existing_key = PaymentIdempotencyKey.objects.filter(
            idempotency_key=idempotency_key, customer=user
        ).select_related('payment__order').first()
        if existing_key:
            p = existing_key.payment
            o = p.order
            return cls(
                order_number=o.order_number, payment_status=p.status,
                payment_id=str(p.id), order_id=str(o.id),
                total=float(p.amount), success=True,
            )

        # ── Validate checkout session ──────────────────────────────────────
        try:
            checkout = CheckoutSession.objects.get(
                id=checkout_session_id, customer=user, status='active'
            )
        except CheckoutSession.DoesNotExist:
            return cls(success=False, error='Checkout session not found or already completed')

        if checkout.is_expired():
            checkout.status = CheckoutSession.CheckoutStatus.EXPIRED
            checkout.save(update_fields=['status'])
            return cls(success=False, error='Checkout session has expired')

        if not checkout.shipping_method:
            return cls(success=False, error='No shipping method selected')

        cart = checkout.cart
        if not cart or not cart.items.exists():
            return cls(success=False, error='Cart is empty')

        addr = checkout.delivery_address
        if not addr:
            return cls(success=False, error='No delivery address selected')

        # ── Validate payment method ────────────────────────────────────────
        VALID_METHODS = ('wallet', 'card', 'mobile_money', 'cash_on_delivery')
        if payment_method not in VALID_METHODS:
            return cls(success=False, error=f'Invalid payment method: {payment_method}')

        vault_entry = None
        if payment_method == 'card':
            if not vault_token:
                return cls(success=False, error='vault_token required for card payment')
            try:
                vault_entry = CardVaultEntry.objects.get(
                    token=vault_token, customer=user, is_active=True
                )
            except CardVaultEntry.DoesNotExist:
                return cls(success=False, error='Invalid or expired vault token')

        if payment_method == 'mobile_money' and not mobile_phone:
            return cls(success=False, error='mobile_phone required for mobile money payment')

        # ── Atomic order + payment creation ───────────────────────────────
        try:
            with db_transaction.atomic():
                # Generate unique order number
                date_part = timezone.now().strftime('%Y%m%d')
                rand_part = uuid.uuid4().hex[:8].upper()
                order_number = f'ORD-{date_part}-{rand_part}'

                # Build shipping address string
                addr_line = f'{addr.address_line1}'
                if getattr(addr, 'address_line2', ''):
                    addr_line += f', {addr.address_line2}'

                first_name = getattr(addr, 'first_name', '') or getattr(user, 'first_name', '')
                last_name  = getattr(addr, 'last_name', '')  or getattr(user, 'last_name', '')
                phone      = getattr(addr, 'phone_number', '') or getattr(user, 'phone_number', '')
                email      = getattr(user, 'email', '')

                order = Order.objects.create(
                    order_number=order_number,
                    customer=user,
                    status=Order.OrderStatus.PENDING,
                    payment_status=Order.PaymentStatus.PENDING,
                    subtotal=checkout.subtotal,
                    tax_amount=checkout.tax_amount,
                    shipping_amount=checkout.shipping_cost,
                    total=checkout.total,
                    currency='ZMW',
                    payment_method=payment_method,
                    shipping_method=checkout.shipping_method.shipping_type,
                    shipping_first_name=first_name,
                    shipping_last_name=last_name,
                    shipping_email=email,
                    shipping_phone=phone,
                    shipping_address=addr_line,
                    shipping_city=getattr(addr, 'city', ''),
                    shipping_state=getattr(addr, 'state', ''),
                    shipping_country=getattr(addr, 'country', ''),
                    shipping_postal_code=getattr(addr, 'postal_code', ''),
                    billing_first_name=first_name,
                    billing_last_name=last_name,
                    billing_email=email,
                    billing_phone=phone,
                    billing_address=addr_line,
                    billing_city=getattr(addr, 'city', ''),
                    billing_state=getattr(addr, 'state', ''),
                    billing_country=getattr(addr, 'country', ''),
                    billing_postal_code=getattr(addr, 'postal_code', ''),
                )

                # Create order items from cart
                for cart_item in cart.items.select_related('product__vendor').all():
                    OrderItem.objects.create(
                        order=order,
                        product=cart_item.product,
                        vendor=cart_item.product.vendor if hasattr(cart_item.product, 'vendor') else None,
                        product_name=cart_item.product.name,
                        quantity=cart_item.quantity,
                        unit_price=cart_item.product.price,
                        subtotal=cart_item.subtotal,
                    )

                txn_id = f'TXN-{uuid.uuid4().hex[:12].upper()}'
                payvault_checkout_url = None

                if payment_method == 'wallet':
                    # Atomic wallet debit — prevents double-spend
                    wallet = Wallet.objects.select_for_update().get_or_create(customer=user)[0]
                    if wallet.balance < checkout.total:
                        raise ValueError('Insufficient wallet balance')

                    Wallet.objects.filter(pk=wallet.pk).update(
                        balance=F('balance') - checkout.total,
                        updated_at=timezone.now(),
                    )
                    WalletTransaction.objects.create(
                        wallet=wallet,
                        type=WalletTransaction.TransactionType.DEBIT,
                        amount=checkout.total,
                        status=WalletTransaction.TransactionStatus.COMPLETED,
                        description=f'Payment for order {order_number}',
                        reference=txn_id,
                    )
                    payment = Payment.objects.create(
                        order=order, customer=user, amount=checkout.total,
                        currency='ZMW', method='wallet', status='completed',
                        transaction_id=txn_id,
                    )
                    order.payment_status = Order.PaymentStatus.PAID
                    order.status = Order.OrderStatus.CONFIRMED
                    order.save(update_fields=['payment_status', 'status', 'updated_at'])

                    PaymentAuditLog.objects.create(
                        action=PaymentAuditLog.Action.WALLET_DEBITED,
                        actor=user,
                        resource_type='payment',
                        resource_id=str(payment.id),
                        ip_address=info.context.META.get('REMOTE_ADDR'),
                        metadata={'amount': str(checkout.total), 'order': order_number},
                    )

                else:
                    # Card / mobile money — route through PayVault and return checkout URL.
                    method_map = {
                        'card': 'credit_card',
                        'mobile_money': 'mobile_money',
                        'cash_on_delivery': 'cash_on_delivery',
                    }

                    payvault_checkout_url = None
                    PAYVAULT_METHODS = {'card', 'mobile_money'}
                    if payment_method in PAYVAULT_METHODS:
                        try:
                            from payvault.client import create_payment_session
                            pv_session = create_payment_session(
                                amount=str(checkout.total),
                                description=f'E-commerce order {order_number}',
                                merchant_reference=order_number,
                                idempotency_key=idempotency_key,
                            )
                            txn_id = pv_session['sessionReference']
                            payvault_checkout_url = pv_session['paymentUrl']
                        except Exception:
                            pass  # PayVault unavailable — fall through to event-based flow

                    payment = Payment.objects.create(
                        order=order, customer=user, amount=checkout.total,
                        currency='ZMW', method=method_map.get(payment_method, payment_method),
                        status='processing', transaction_id=txn_id,
                    )

                    if not payvault_checkout_url:
                        # Fallback: publish event for async handler
                        event_payload = {
                            'payment_id':     str(payment.id),
                            'transaction_id': txn_id,
                            'order_id':       str(order.id),
                            'order_number':   order_number,
                            'customer_id':    str(user.id),
                            'amount':         str(checkout.total),
                            'currency':       'ZMW',
                            'method':         payment_method,
                        }
                        if payment_method == 'card' and vault_entry:
                            event_payload['vault_token'] = vault_token
                            event_payload['card_brand']  = vault_entry.card_brand
                            event_payload['last_four']   = vault_entry.pan_last_four
                        if payment_method == 'mobile_money':
                            event_payload['mobile_phone'] = mobile_phone
                        publish_event('payment.events', 'PaymentRequested', event_payload)

                    PaymentAuditLog.objects.create(
                        action=PaymentAuditLog.Action.PAYMENT_INITIATED,
                        actor=user,
                        resource_type='payment',
                        resource_id=str(payment.id),
                        ip_address=info.context.META.get('REMOTE_ADDR'),
                        metadata={'method': payment_method, 'amount': str(checkout.total), 'order': order_number},
                    )

                # Store idempotency key inside the same transaction
                PaymentIdempotencyKey.objects.create(
                    idempotency_key=idempotency_key,
                    payment=payment,
                    customer=user,
                )

                # Finalise checkout session
                checkout.status = CheckoutSession.CheckoutStatus.COMPLETED
                checkout.save(update_fields=['status'])

                # Clear cart
                cart.items.all().delete()

        except ValueError as exc:
            return cls(success=False, error=str(exc))
        except Exception as exc:
            return cls(success=False, error=f'Payment processing error: {exc}')

        return cls(
            order_number=order_number,
            payment_status=payment.status,
            payment_id=str(payment.id),
            order_id=str(order.id),
            total=float(checkout.total),
            checkout_url=payvault_checkout_url if payment_method in ('card', 'mobile_money') else None,
            success=True,
        )


class CheckoutMutation(graphene.ObjectType):
    """Checkout mutations"""
    initialize_checkout    = InitializeCheckoutMutation.Field()
    select_shipping_method = SelectShippingMethodMutation.Field()
    update_shipping_address = UpdateShippingAddressMutation.Field()
    complete_purchase      = CompletePurchaseMutation.Field()


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
