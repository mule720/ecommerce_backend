"""
Shipping Service GraphQL Schema
GraphQL API for shipping management
"""
import graphene
from graphene import relay
from graphene_django import DjangoObjectType
from graphene_django.filter import DjangoFilterConnectionField
from django_filters import FilterSet, CharFilter
from datetime import datetime, timedelta
from .models import ShippingZone, ShippingMethod, Shipment, ShipmentEvent, DeliveryAddress


class ShippingZoneType(DjangoObjectType):
    """GraphQL type for ShippingZone model"""
    class Meta:
        """Defines the purpose and behavior of the `Meta` class."""
        model = ShippingZone
        fields = "__all__"
        interfaces = (relay.Node,)


class ShippingMethodType(DjangoObjectType):
    """GraphQL type for ShippingMethod model"""
    class Meta:
        """Defines the purpose and behavior of the `Meta` class."""
        model = ShippingMethod
        fields = "__all__"
        interfaces = (relay.Node,)
        # Avoid GraphQL type-name collision with auto-generated
        # enum for ShippingMethod.type choices (ShippingMethodType).
        convert_choices_to_enum = False


class ShipmentEventType(DjangoObjectType):
    """GraphQL type for ShipmentEvent model"""
    class Meta:
        """Defines the purpose and behavior of the `Meta` class."""
        model = ShipmentEvent
        fields = "__all__"


class ShipmentType(DjangoObjectType):
    """GraphQL type for Shipment model"""
    class Meta:
        """Defines the purpose and behavior of the `Meta` class."""
        model = Shipment
        fields = "__all__"
        interfaces = (relay.Node,)
    
    events = graphene.List(ShipmentEventType)
    
    def resolve_events(self, info):
        """Resolver for the GraphQL field `events`."""
        return self.events.all()


class ShippingDeliveryAddressType(DjangoObjectType):
    """GraphQL type for DeliveryAddress model (shipping-specific)"""
    class Meta:
        """Defines the purpose and behavior of the `Meta` class."""
        model = DeliveryAddress
        fields = "__all__"
        interfaces = (relay.Node,)


# Filters
class ShipmentFilter(FilterSet):
    """Filter for Shipment queries"""
    status = CharFilter(field_name='status')
    
    class Meta:
        """Defines the purpose and behavior of the `Meta` class."""
        model = Shipment
        fields = ['status']


class Query(graphene.ObjectType):
    """Shipping Service Queries"""
    
    # Shipping Zone queries
    all_shipping_zones = graphene.List(ShippingZoneType)
    shipping_zone = graphene.Field(
        ShippingZoneType,
        id=graphene.ID(required=True)
    )
    
    # Shipping Method queries
    shipping_methods = graphene.List(
        ShippingMethodType,
        zone_id=graphene.ID(required=True)
    )
    
    # Shipment queries
    all_shipments = DjangoFilterConnectionField(
        ShipmentType,
        filterset_class=ShipmentFilter
    )
    shipment = relay.Node.Field(ShipmentType)
    shipment_by_tracking = graphene.Field(
        ShipmentType,
        tracking_number=graphene.String(required=True)
    )
    shipments_by_order = graphene.List(
        ShipmentType,
        order_id=graphene.ID(required=True)
    )
    my_shipments = graphene.List(ShipmentType)
    
    # Delivery Address queries
    my_delivery_addresses = graphene.List(ShippingDeliveryAddressType)
    
    # Resolvers
    def resolve_all_shipping_zones(self, info, **kwargs):
        """Resolver for the GraphQL field `all shipping zones`."""
        return ShippingZone.objects.filter(is_active=True)
    
    def resolve_shipping_zone(self, info, id):
        """Resolver for the GraphQL field `shipping zone`."""
        try:
            return ShippingZone.objects.get(pk=int(id))
        except (ShippingZone.DoesNotExist, ValueError):
            return None
    
    def resolve_shipping_methods(self, info, zone_id):
        """Resolver for the GraphQL field `shipping methods`."""
        try:
            return ShippingMethod.objects.filter(zone_id=int(zone_id), is_active=True)
        except ValueError:
            return []
    
    def resolve_all_shipments(self, info, **kwargs):
        """Resolver for the GraphQL field `all shipments`."""
        return Shipment.objects.all()
    
    def resolve_shipment_by_tracking(self, info, tracking_number):
        """Resolver for the GraphQL field `shipment by tracking`."""
        try:
            return Shipment.objects.get(tracking_number=tracking_number)
        except Shipment.DoesNotExist:
            return None
    
    def resolve_shipments_by_order(self, info, order_id):
        """Resolver for the GraphQL field `shipments by order`."""
        try:
            return Shipment.objects.filter(order_id=int(order_id))
        except ValueError:
            return []
    
    def resolve_my_shipments(self, info):
        """Resolver for the GraphQL field `my shipments`."""
        user = info.context.user
        if user.is_anonymous:
            raise Exception('Not logged in!')
        return Shipment.objects.filter(order__customer=user)
    
    def resolve_my_delivery_addresses(self, info):
        """Resolver for the GraphQL field `my delivery addresses`."""
        user = info.context.user
        if user.is_anonymous:
            raise Exception('Not logged in!')
        return DeliveryAddress.objects.filter(customer=user)


# Mutations
class CreateShipmentMutation(graphene.Mutation):
    """Create a shipment for an order"""
    class Arguments:
        """Defines the purpose and behavior of the `Arguments` class."""
        order_id = graphene.ID(required=True)
        order_item_id = graphene.ID()
        vendor_id = graphene.ID(required=True)
        shipping_method_id = graphene.ID(required=True)
        carrier = graphene.String(required=True)
    
    shipment = graphene.Field(ShipmentType)
    
    @classmethod
    def mutate(cls, root, info, order_id, vendor_id, shipping_method_id, carrier):
        """Executes mutation business rules and returns the mutation response object."""
        from order_service.models import Order, OrderItem
        
        try:
            order = Order.objects.get(pk=int(order_id))
            shipping_method = ShippingMethod.objects.get(pk=int(shipping_method_id))
            
            order_item = None
            if 'order_item_id' in info.variable_values:
                try:
                    order_item = OrderItem.objects.get(pk=int(info.variable_values['order_item_id']))
                except (OrderItem.DoesNotExist, ValueError):
                    pass
            
            # Generate tracking number
            tracking_number = f"TRK-{datetime.now().strftime('%Y%m%d')}-{Shipment.objects.count() + 1:06d}"
            
            shipment = Shipment.objects.create(
                order=order,
                order_item=order_item,
                vendor_id=int(vendor_id),
                shipping_method=shipping_method,
                tracking_number=tracking_number,
                carrier=carrier,
                shipping_cost=shipping_method.price,
                estimated_delivery=datetime.now().date() + timedelta(days=shipping_method.estimated_days)
            )
            
            return CreateShipmentMutation(shipment=shipment)
        except (Order.DoesNotExist, ShippingMethod.DoesNotExist, ValueError) as e:
            raise Exception(str(e))


class UpdateShipmentStatusMutation(graphene.Mutation):
    """Update shipment status"""
    class Arguments:
        """Defines the purpose and behavior of the `Arguments` class."""
        shipment_id = graphene.ID(required=True)
        status = graphene.String(required=True)
        location = graphene.String()
        description = graphene.String()
    
    shipment = graphene.Field(ShipmentType)
    
    @classmethod
    def mutate(cls, root, info, shipment_id, status, **kwargs):
        """Executes mutation business rules and returns the mutation response object."""
        try:
            shipment = Shipment.objects.get(pk=int(shipment_id))
            shipment.status = status
            
            if status == 'delivered':
                shipment.actual_delivery = datetime.now()
            
            shipment.save()
            
            # Create tracking event
            ShipmentEvent.objects.create(
                shipment=shipment,
                status=status,
                location=kwargs.get('location', ''),
                description=kwargs.get('description', ''),
                timestamp=datetime.now()
            )
            
            return UpdateShipmentStatusMutation(shipment=shipment)
        except (Shipment.DoesNotExist, ValueError):
            raise Exception('Shipment not found')


class AssignDriverMutation(graphene.Mutation):
    """Assign a driver to a shipment"""
    class Arguments:
        """Defines the purpose and behavior of the `Arguments` class."""
        shipment_id = graphene.ID(required=True)
        driver_id = graphene.ID(required=True)
    
    shipment = graphene.Field(ShipmentType)
    
    @classmethod
    def mutate(cls, root, info, shipment_id, driver_id):
        """Executes mutation business rules and returns the mutation response object."""
        try:
            shipment = Shipment.objects.get(pk=int(shipment_id))
            shipment.driver_id = int(driver_id)
            shipment.save()
            return AssignDriverMutation(shipment=shipment)
        except (Shipment.DoesNotExist, ValueError):
            raise Exception('Shipment not found')


class SaveDeliveryAddressMutation(graphene.Mutation):
    """Save a delivery address"""
    class Arguments:
        """Defines the purpose and behavior of the `Arguments` class."""
        label = graphene.String()
        first_name = graphene.String(required=True)
        last_name = graphene.String(required=True)
        phone = graphene.String(required=True)
        address = graphene.String(required=True)
        city = graphene.String(required=True)
        state = graphene.String(required=True)
        country = graphene.String(required=True)
        postal_code = graphene.String(required=True)
        latitude = graphene.Float()
        longitude = graphene.Float()
        is_default = graphene.Boolean()
    
    delivery_address = graphene.Field(ShippingDeliveryAddressType)
    
    @classmethod
    def mutate(cls, root, info, **kwargs):
        """Executes mutation business rules and returns the mutation response object."""
        user = info.context.user
        if user.is_anonymous:
            raise Exception('Not logged in!')
        
        is_default = kwargs.get('is_default', False)
        
        # If setting as default, unset other defaults
        if is_default:
            DeliveryAddress.objects.filter(customer=user, is_default=True).update(is_default=False)
        
        delivery_address = DeliveryAddress.objects.create(
            customer=user,
            label=kwargs.get('label', 'Home'),
            first_name=kwargs['first_name'],
            last_name=kwargs['last_name'],
            phone=kwargs['phone'],
            address=kwargs['address'],
            city=kwargs['city'],
            state=kwargs['state'],
            country=kwargs['country'],
            postal_code=kwargs['postal_code'],
            latitude=kwargs.get('latitude'),
            longitude=kwargs.get('longitude'),
            is_default=is_default
        )
        
        return SaveDeliveryAddressMutation(delivery_address=delivery_address)


class DeleteDeliveryAddressMutation(graphene.Mutation):
    """Delete a delivery address"""
    class Arguments:
        """Defines the purpose and behavior of the `Arguments` class."""
        address_id = graphene.ID(required=True)
    
    success = graphene.Boolean()
    
    @classmethod
    def mutate(cls, root, info, address_id):
        """Executes mutation business rules and returns the mutation response object."""
        user = info.context.user
        if user.is_anonymous:
            raise Exception('Not logged in!')
        
        try:
            address = DeliveryAddress.objects.get(pk=int(address_id), customer=user)
            address.delete()
            return DeleteDeliveryAddressMutation(success=True)
        except (DeliveryAddress.DoesNotExist, ValueError):
            return DeleteDeliveryAddressMutation(success=False)


class Mutation(graphene.ObjectType):
    """Shipping Service Mutations"""
    
    create_shipment = CreateShipmentMutation.Field()
    update_shipment_status = UpdateShipmentStatusMutation.Field()
    assign_driver = AssignDriverMutation.Field()
    save_delivery_address = SaveDeliveryAddressMutation.Field()
    delete_delivery_address = DeleteDeliveryAddressMutation.Field()


# Schema definition for Shipping Service
# NOTE:
# This service schema is intentionally not instantiated at import-time.
# The gateway composes Query/Mutation classes directly, and eager schema
# instantiation can trigger duplicate GraphQL type registration errors.
