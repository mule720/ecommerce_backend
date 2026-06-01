"""
Gateway Service - Unified GraphQL API
Combines all microservices into a single GraphQL endpoint
"""
import hmac
import hashlib
import graphene
from graphene import ObjectType
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
import json

# Import all service schemas
from user_service.schema import Query as UserQuery, Mutation as UserMutation
from user_service.vendor_management_schema import VendorManagementQuery, VendorManagementMutation
from product_service.schema import Query as ProductQuery, Mutation as ProductMutation
from cart_service.schema import CartQuery, CartMutation
from checkout_service.schema import CheckoutQuery, CheckoutMutation
from order_service.schema import Query as OrderQuery, Mutation as OrderMutation
from payment_service.schema import Query as PaymentQuery, Mutation as PaymentMutation
from shipping_service.schema import Query as ShippingQuery, Mutation as ShippingMutation
from notification_service.schema import Query as NotificationQuery, Mutation as NotificationMutation
from search_service.schema import SearchQuery, SearchMutation
from wishlist_service.schema import WishlistQuery, WishlistMutation
from returns_service.schema import ReturnsQuery, ReturnsMutation
from review_service.schema import ReviewQuery, ReviewMutation
from chat_service.schema import ChatQuery, ChatMutation
from wallet_service.schema import WalletQuery, WalletMutation
from vendor_storefront.schema import StorefrontQuery, StorefrontMutation
from card_vault.schema import CardVaultQuery, CardVaultMutation
from order_service.models import Order
from payment_service.models import Payment, Refund, VendorPayout
from shipping_service.models import Shipment, ShipmentEvent
from product_service.inventory_ops import reserve_inventory_lines, release_inventory_lines
from ecom_backend.event_bus import publish_event


# Combine all Queries
class Query(
    UserQuery,
    VendorManagementQuery,
    ProductQuery,
    CartQuery,
    CheckoutQuery,
    OrderQuery,
    PaymentQuery,
    ShippingQuery,
    NotificationQuery,
    SearchQuery,
    WishlistQuery,
    ReturnsQuery,
    ReviewQuery,
    ChatQuery,
    WalletQuery,
    StorefrontQuery,
    CardVaultQuery,
    ObjectType
):
    """Combined Query type from all services"""
    
    # Service health check
    health_check = graphene.Boolean()
    
    def resolve_health_check(self, info):
        """Resolver for the GraphQL field `health check`."""
        return True
    
    # Gateway info
    gateway_version = graphene.String()
    
    def resolve_gateway_version(self, info):
        """Resolver for the GraphQL field `gateway version`."""
        return "1.0.0"
    
    # Service status
    services_status = graphene.List(graphene.String)
    
    def resolve_services_status(self, info):
        """Resolver for the GraphQL field `services status`."""
        return [
            "user_service: online",
            "product_service: online",
            "order_service: online",
            "payment_service: online",
            "shipping_service: online",
            "notification_service: online",
            "search_service: online",
            "wishlist_service: online",
            "returns_service: online",
            "review_service: online",
            "chat_service: online",
        ]


# Combine all Mutations
class IntegrationMutation(graphene.ObjectType):
    """GraphQL integration ingress (single endpoint /graphql)."""

    receive_payment_webhook = graphene.Field(
        graphene.JSONString,
        event_type=graphene.String(required=True),
        payload=graphene.JSONString(required=True),
        token=graphene.String(required=False),
        signature=graphene.String(required=False),
    )
    receive_shipping_webhook = graphene.Field(
        graphene.JSONString,
        event_type=graphene.String(required=True),
        payload=graphene.JSONString(required=True),
        token=graphene.String(required=False),
    )
    receive_erp_webhook = graphene.Field(
        graphene.JSONString,
        event_type=graphene.String(required=True),
        payload=graphene.JSONString(required=True),
        token=graphene.String(required=False),
    )
    reserve_inventory = graphene.Field(
        graphene.JSONString,
        source_reference=graphene.String(required=True),
        lines=graphene.JSONString(required=True),
        token=graphene.String(required=False),
    )
    release_inventory = graphene.Field(
        graphene.JSONString,
        source_reference=graphene.String(required=True),
        lines=graphene.JSONString(required=True),
        token=graphene.String(required=False),
    )

    @staticmethod
    def _authorized(token, payload_str=None, signature=None):
        """
        Verify either HMAC-SHA256 signature or shared token.
        HMAC takes priority when PAYMENT_WEBHOOK_HMAC_SECRET is configured.
        """
        hmac_secret = getattr(settings, 'PAYMENT_WEBHOOK_HMAC_SECRET', '')
        if hmac_secret and payload_str and signature:
            expected = hmac.new(
                hmac_secret.encode('utf-8'),
                payload_str.encode('utf-8'),
                hashlib.sha256,
            ).hexdigest()
            return hmac.compare_digest(expected, signature)
        # Fall back to shared token
        expected = getattr(settings, 'INTEGRATION_SHARED_TOKEN', '')
        return (not expected) or (token == expected)

    @staticmethod
    def _obj(value):
        """Internal helper function used by this module."""
        if isinstance(value, dict) or isinstance(value, list):
            return value
        if value in (None, ""):
            return {}
        if isinstance(value, str):
            return json.loads(value)
        return value

    def resolve_receive_payment_webhook(self, info, event_type, payload,
                                         token=None, signature=None):
        """Resolver for the GraphQL field `receive payment webhook`."""
        if not self._authorized(token, payload_str=payload, signature=signature):
            raise Exception("unauthorized")
        payload = self._obj(payload)

        order_id = payload.get("order_id")
        tx = payload.get("transaction_id")

        payment = Payment.objects.filter(transaction_id=tx).first() if tx else None
        if not payment and order_id:
            payment = Payment.objects.filter(order_id=order_id).order_by("-created_at").first()
        order = payment.order if payment else (Order.objects.filter(pk=order_id).first() if order_id else None)

        if event_type == "PaymentCompleted":
            if payment:
                payment.status = "completed"
                payment.gateway_transaction_id = payload.get("gateway_transaction_id", payment.gateway_transaction_id)
                payment.payment_gateway_response = payload
                payment.save(update_fields=["status", "gateway_transaction_id", "payment_gateway_response", "updated_at"])
            if order:
                order.payment_status = Order.PaymentStatus.PAID
                if order.status == Order.OrderStatus.PENDING:
                    order.status = Order.OrderStatus.CONFIRMED
                order.save(update_fields=["payment_status", "status", "updated_at"])

        elif event_type == "PaymentFailed":
            if payment:
                payment.status = "failed"
                payment.payment_gateway_response = payload
                payment.save(update_fields=["status", "payment_gateway_response", "updated_at"])
            if order:
                order.payment_status = Order.PaymentStatus.FAILED
                order.save(update_fields=["payment_status", "updated_at"])

        elif event_type == "RefundProcessed":
            refund = Refund.objects.filter(pk=payload.get("refund_id")).first()
            if refund:
                refund.status = "completed"
                refund.save(update_fields=["status", "updated_at"])
            if payment:
                payment.status = "refunded"
                payment.save(update_fields=["status", "updated_at"])
            if order:
                order.payment_status = Order.PaymentStatus.REFUNDED
                order.status = Order.OrderStatus.REFUNDED
                order.save(update_fields=["payment_status", "status", "updated_at"])

        elif event_type == "VendorPayoutCompleted":
            payout = VendorPayout.objects.filter(pk=payload.get("payout_id")).first()
            if payout:
                payout.status = "paid"
                payout.payment_system_reference = payload.get("bank_reference", payout.payment_system_reference)
                payout.processed_at = timezone.now()
                payout.save(update_fields=["status", "payment_system_reference", "processed_at"])

        elif event_type == "WalletTopUpCompleted":
            # Confirm pending wallet top-up transaction and credit balance
            from wallet_service.models import WalletTransaction, Wallet
            from django.db.models import F
            tx_id = payload.get("transaction_id")
            if tx_id:
                try:
                    from django.db import transaction as db_tx
                    with db_tx.atomic():
                        tx = WalletTransaction.objects.select_for_update().get(
                            pk=int(tx_id),
                            status=WalletTransaction.TransactionStatus.PENDING,
                            type=WalletTransaction.TransactionType.CREDIT,
                        )
                        Wallet.objects.filter(pk=tx.wallet_id).update(
                            balance=F('balance') + tx.amount,
                            updated_at=timezone.now(),
                        )
                        tx.status = WalletTransaction.TransactionStatus.COMPLETED
                        tx.save(update_fields=['status'])
                except WalletTransaction.DoesNotExist:
                    pass

        # Append-only audit log entry for every webhook event
        try:
            from card_vault.models import PaymentAuditLog
            PaymentAuditLog.objects.create(
                action=PaymentAuditLog.Action.PAYMENT_COMPLETED
                       if event_type == "PaymentCompleted"
                       else PaymentAuditLog.Action.PAYMENT_FAILED
                       if event_type == "PaymentFailed"
                       else PaymentAuditLog.Action.REFUND_REQUESTED
                       if event_type == "RefundProcessed"
                       else PaymentAuditLog.Action.PAYOUT_DISPATCHED,
                resource_type='webhook',
                resource_id=str(payload.get("transaction_id", "")),
                metadata={"event_type": event_type, **{k: str(v) for k, v in payload.items()}},
            )
        except Exception:
            pass  # Audit log failure must not block webhook processing

        return {"success": True, "event_type": event_type}

    def resolve_receive_shipping_webhook(self, info, event_type, payload, token=None):
        """Resolver for the GraphQL field `receive shipping webhook`."""
        if not self._authorized(token):
            raise Exception("unauthorized")
        payload = self._obj(payload)

        shipment = Shipment.objects.filter(tracking_number=payload.get("tracking_number", "")).first()
        if not shipment and payload.get("order_id"):
            shipment = Shipment.objects.filter(order_id=payload.get("order_id")).order_by("-created_at").first()

        if event_type in {"ShipmentStatusChanged", "ShipmentDelivered", "ShipmentCreated"} and shipment:
            new_status = payload.get("status")
            if event_type == "ShipmentDelivered":
                new_status = Shipment.ShipmentStatus.DELIVERED
            if new_status:
                shipment.status = new_status
                if new_status == Shipment.ShipmentStatus.DELIVERED:
                    shipment.actual_delivery = timezone.now()
                shipment.save(update_fields=["status", "actual_delivery", "updated_at"])

            ShipmentEvent.objects.create(
                shipment=shipment,
                status=shipment.status,
                location=payload.get("location", ""),
                description=payload.get("description", event_type),
                timestamp=timezone.now(),
            )

            if shipment.order_id and shipment.status == Shipment.ShipmentStatus.DELIVERED:
                order = shipment.order
                order.status = Order.OrderStatus.DELIVERED
                order.save(update_fields=["status", "updated_at"])

        return {"success": True, "event_type": event_type}

    def resolve_receive_erp_webhook(self, info, event_type, payload, token=None):
        """Resolver for the GraphQL field `receive erp webhook`."""
        if not self._authorized(token):
            raise Exception("unauthorized")
        payload = self._obj(payload)

        if event_type == "JournalEntryPosted":
            order = Order.objects.filter(pk=payload.get("order_id")).first()
            if order:
                order.mark_erp_synced(reference=payload.get("journal_entry_id", ""))

        elif event_type == "TaxCalculated":
            order = Order.objects.filter(pk=payload.get("order_id")).first()
            if order and payload.get("tax_amount") is not None:
                order.tax_amount = Decimal(str(payload.get("tax_amount")))
                order.calculate_total()
                order.save(update_fields=["tax_amount", "total", "updated_at"])

        return {"success": True, "event_type": event_type}

    def resolve_reserve_inventory(self, info, source_reference, lines, token=None):
        """Resolver for the GraphQL field `reserve inventory`."""
        if not self._authorized(token):
            raise Exception("unauthorized")
        lines = self._obj(lines)
        reserved = reserve_inventory_lines(
            lines=lines,
            source_reference=source_reference,
            context_message="Inventory reserved by GraphQL integration mutation",
        )
        publish_event("erp.events", "InventoryReserved", {
            "source_reference": source_reference,
            "lines": lines,
        })
        return {"success": True, "reserved": reserved}

    def resolve_release_inventory(self, info, source_reference, lines, token=None):
        """Resolver for the GraphQL field `release inventory`."""
        if not self._authorized(token):
            raise Exception("unauthorized")
        lines = self._obj(lines)
        released = release_inventory_lines(
            lines=lines,
            source_reference=source_reference,
            context_message="Inventory released by GraphQL integration mutation",
        )
        publish_event("erp.events", "InventoryReleased", {
            "source_reference": source_reference,
            "lines": lines,
        })
        return {"success": True, "released": released}


class Mutation(
    UserMutation,
    VendorManagementMutation,
    ProductMutation,
    CartMutation,
    CheckoutMutation,
    OrderMutation,
    PaymentMutation,
    ShippingMutation,
    NotificationMutation,
    SearchMutation,
    WishlistMutation,
    ReturnsMutation,
    ReviewMutation,
    ChatMutation,
    WalletMutation,
    StorefrontMutation,
    CardVaultMutation,
    IntegrationMutation,
    ObjectType
):
    """Combined Mutation type from all services"""
    pass


# Create the unified schema
gateway_schema = graphene.Schema(query=Query, mutation=Mutation)


# GraphQL Type Definitions for the Gateway
gateway_types = """
type GatewayInfo {
    version: String!
    services: [String!]!
    healthCheck: Boolean!
}

type Query {
    # Gateway
    gatewayInfo: GatewayInfo!
    
    # User Service
    allUsers: UserConnection
    user(id: ID!): User
    me: User
    usersByRole(role: String!): [User!]!
    customerProfile: CustomerProfile
    vendorProfile(id: ID!): VendorProfile
    allVendors: [VendorProfile!]!
    driverProfile(id: ID!): DriverProfile
    allDrivers: [DriverProfile!]!
    
    # Product Service
    allCategories: [Category!]!
    category(slug: String!): Category
    allProducts: ProductConnection
    product(slug: String!): Product
    productsByVendor(vendorId: ID!): [Product!]!
    featuredProducts: [Product!]!
    productReviews(productId: ID!): [ProductReview!]!
    allCollections: [Collection!]!
    collection(slug: String!): Collection
    allTags: [Tag!]!
    
    # Order Service
    allOrders: OrderConnection
    order(id: ID!): Order
    orderByNumber(orderNumber: String!): Order
    myOrders: [Order!]!
    ordersByVendor(vendorId: ID!): [Order!]!
    myCart: Cart
    returnRequests(orderItemId: ID!): [ReturnRequest!]!
    
    # Payment Service
    allPayments: PaymentConnection
    payment(transactionId: String!): Payment
    paymentsByOrder(orderId: ID!): [Payment!]!
    myPayments: [Payment!]!
    allRefunds: [Refund!]!
    myPaymentMethods: [CustomerPaymentMethod!]!
    vendorPayouts: [VendorPayout!]!
    
    # Shipping Service
    allShippingZones: [ShippingZone!]!
    shippingZone(id: ID!): ShippingZone
    shippingMethods(zoneId: ID!): [ShippingMethod!]!
    allShipments: ShipmentConnection
    shipment(trackingNumber: String!): Shipment
    shipmentsByOrder(orderId: ID!): [Shipment!]!
    myShipments: [Shipment!]!
    myDeliveryAddresses: [DeliveryAddress!]!
    
    # Notification Service
    myNotifications: [Notification!]!
    unreadNotificationCount: Int!
    allEmailTemplates: [EmailTemplate!]!
    emailTemplate(id: ID!): EmailTemplate
    emailQueue: [EmailQueue!]!
    myPushNotifications: [PushNotification!]!
}

type Mutation {
    # User Service
    createUser(username: String!, email: String!, password: String!, role: String, firstName: String, lastName: String, phone: String): User
    updateUser(id: ID!, firstName: String, lastName: String, phone: String, address: String, city: String, country: String, postalCode: String): User
    updateCustomerProfile(dateOfBirth: Date, gender: String): CustomerProfile
    updateVendorProfile(id: ID!, businessName: String, businessDescription: String, businessLicense: String, taxId: String, bankAccount: String, payoutMethod: String): VendorProfile
    updateDriverStatus(id: ID!, status: String!, currentLocationLat: Float, currentLocationLng: Float): DriverProfile
    approveVendor(id: ID!): VendorProfile
    
    # Product Service
    createProduct(vendorId: ID!, categoryId: ID, name: String!, slug: String!, description: String!, price: Float!, compareAtPrice: Float, quantity: Int, sku: String, weight: Float, isFeatured: Boolean, isTaxable: Boolean, taxRate: Float): Product
    updateProduct(id: ID!, name: String, description: String, price: Float, compareAtPrice: Float, quantity: Int, sku: String, status: String, isFeatured: Boolean): Product
    deleteProduct(id: ID!): Boolean
    createProductReview(productId: ID!, userId: ID!, rating: Int!, title: String!, comment: String!): ProductReview
    createCategory(name: String!, slug: String!, description: String, parentId: ID): Category
    createCollection(name: String!, slug: String!, description: String, productIds: [ID]): Collection
    addProductToCollection(collectionId: ID!, productId: ID!): Collection
    
    # Order Service
    createOrderFromCart(shippingFirstName: String!, shippingLastName: String!, shippingEmail: String!, shippingPhone: String!, shippingAddress: String!, shippingCity: String!, shippingState: String!, shippingCountry: String!, shippingPostalCode: String!, notes: String): Order
    updateOrderStatus(orderId: ID!, status: String!): Order
    addToCart(productId: ID!, quantity: Int): Cart
    updateCartItemQuantity(cartItemId: ID!, quantity: Int!): Cart
    removeFromCart(cartItemId: ID!): Cart
    clearCart: Boolean
    createReturnRequest(orderItemId: ID!, reason: String!, refundAmount: Float!): ReturnRequest
    updateReturnStatus(returnRequestId: ID!, status: String!): ReturnRequest
    
    # Payment Service
    processPayment(orderId: ID!, method: String!, gatewayName: String): Payment
    createRefund(paymentId: ID!, amount: Float!, reason: String!): Refund
    savePaymentMethod(type: String!, lastFour: String!, brand: String, expiryMonth: Int!, expiryYear: Int!, gatewayToken: String!, isDefault: Boolean): CustomerPaymentMethod
    deletePaymentMethod(paymentMethodId: ID!): Boolean
    createVendorPayout(vendorId: ID!, amount: Float!, orderItemIds: [ID]): VendorPayout
    
    # Shipping Service
    createShipment(orderId: ID!, orderItemId: ID, vendorId: ID!, shippingMethodId: ID!, carrier: String!): Shipment
    updateShipmentStatus(shipmentId: ID!, status: String!, location: String, description: String): Shipment
    assignDriver(shipmentId: ID!, driverId: ID!): Shipment
    saveDeliveryAddress(label: String, firstName: String!, lastName: String!, phone: String!, address: String!, city: String!, state: String!, country: String!, postalCode: String!, latitude: Float, longitude: Float, isDefault: Boolean): DeliveryAddress
    deleteDeliveryAddress(addressId: ID!): Boolean
    
    # Notification Service
    createNotification(userId: ID!, type: String!, title: String!, message: String!, priority: String, link: String, data: String): Notification
    markNotificationRead(notificationId: ID!): Notification
    markAllNotificationsRead: Boolean
    deleteNotification(notificationId: ID!): Boolean
    createEmailTemplate(name: String!, subject: String!, body: String!, type: String!): EmailTemplate
    queueEmail(toEmail: String!, subject: String!, body: String!): EmailQueue
    sendPushNotification(userId: ID!, title: String!, message: String!, data: String): PushNotification
}
"""
