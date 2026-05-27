"""
Cart Service GraphQL Schema
GraphQL API for shopping cart management
"""
import graphene
from graphene import relay
from graphene_django import DjangoObjectType
from django.contrib.auth.models import User
from product_service.models import Product
from .models import Cart, CartItem


class CartItemType(DjangoObjectType):
    """GraphQL type for CartItem"""
    product_info = graphene.JSONString()
    subtotal = graphene.Float()

    class Meta:
        model = CartItem
        fields = ['id', 'product', 'quantity', 'added_at']
        interfaces = (relay.Node,)

    def resolve_product_info(self, info):
        return self.get_product_info()

    def resolve_subtotal(self, info):
        return self.get_subtotal()


class CartType(DjangoObjectType):
    """GraphQL type for Cart"""
    items = graphene.List(CartItemType)
    total = graphene.Float()
    items_count = graphene.Int()
    grouped_by_vendor = graphene.JSONString()

    class Meta:
        model = Cart
        fields = ['id', 'customer', 'created_at', 'updated_at']
        interfaces = (relay.Node,)

    def resolve_items(self, info):
        return self.items.all()

    def resolve_total(self, info):
        return self.get_total()

    def resolve_items_count(self, info):
        return self.get_items_count()

    def resolve_grouped_by_vendor(self, info):
        grouped = self.get_grouped_by_vendor()
        result = {}
        for vendor_id, vendor_data in grouped.items():
            result[str(vendor_id)] = {
                'vendor': {
                    'id': vendor_data['vendor'].id,
                    'businessName': vendor_data['vendor'].vendor_profile.business_name 
                        if hasattr(vendor_data['vendor'], 'vendor_profile') else 'Store'
                },
                'items': [
                    {
                        'id': item.id,
                        'quantity': item.quantity,
                        'product': item.get_product_info(),
                        'subtotal': item.get_subtotal()
                    }
                    for item in vendor_data['items']
                ],
                'vendor_total': sum(item.get_subtotal() for item in vendor_data['items'])
            }
        return result


class AddToCartMutation(graphene.Mutation):
    """Add product to cart"""
    cart_item = graphene.Field(CartItemType)
    cart = graphene.Field(CartType)
    success = graphene.Boolean()
    message = graphene.String()

    class Arguments:
        product_id = graphene.Int(required=True)
        quantity = graphene.Int(required=True, default_value=1)

    def mutate(self, info, product_id, quantity):
        try:
            user = info.context.user
            if not user.is_authenticated:
                return AddToCartMutation(success=False, message="User not authenticated")

            # Get or create cart
            cart, _ = Cart.objects.get_or_create(customer=user)

            # Get product
            try:
                product = Product.objects.get(id=product_id)
            except Product.DoesNotExist:
                return AddToCartMutation(success=False, message="Product not found")

            # Check stock
            if product.quantity < quantity:
                return AddToCartMutation(success=False, message="Insufficient stock")

            # Add or update cart item
            cart_item, created = CartItem.objects.update_or_create(
                cart=cart,
                product=product,
                defaults={'quantity': quantity}
            )

            return AddToCartMutation(
                cart_item=cart_item,
                cart=cart,
                success=True,
                message="Product added to cart" if created else "Cart updated"
            )
        except Exception as e:
            return AddToCartMutation(success=False, message=str(e))


class RemoveFromCartMutation(graphene.Mutation):
    """Remove product from cart"""
    success = graphene.Boolean()
    message = graphene.String()
    cart = graphene.Field(CartType)

    class Arguments:
        cart_item_id = graphene.Int(required=True)

    def mutate(self, info, cart_item_id):
        try:
            user = info.context.user
            if not user.is_authenticated:
                return RemoveFromCartMutation(success=False, message="User not authenticated")

            cart_item = CartItem.objects.get(id=cart_item_id, cart__customer=user)
            cart = cart_item.cart
            cart_item.delete()

            return RemoveFromCartMutation(
                success=True,
                message="Item removed from cart",
                cart=cart
            )
        except CartItem.DoesNotExist:
            return RemoveFromCartMutation(success=False, message="Cart item not found")
        except Exception as e:
            return RemoveFromCartMutation(success=False, message=str(e))


class UpdateCartItemMutation(graphene.Mutation):
    """Update quantity of cart item"""
    cart_item = graphene.Field(CartItemType)
    cart = graphene.Field(CartType)
    success = graphene.Boolean()
    message = graphene.String()

    class Arguments:
        cart_item_id = graphene.Int(required=True)
        quantity = graphene.Int(required=True)

    def mutate(self, info, cart_item_id, quantity):
        try:
            user = info.context.user
            if not user.is_authenticated:
                return UpdateCartItemMutation(success=False, message="User not authenticated")

            cart_item = CartItem.objects.get(id=cart_item_id, cart__customer=user)

            if quantity <= 0:
                cart_item.delete()
                return UpdateCartItemMutation(
                    success=True,
                    message="Item removed from cart",
                    cart=cart_item.cart
                )

            # Check stock
            if cart_item.product.quantity < quantity:
                return UpdateCartItemMutation(
                    success=False,
                    message=f"Only {cart_item.product.quantity} items available"
                )

            cart_item.quantity = quantity
            cart_item.save()

            return UpdateCartItemMutation(
                cart_item=cart_item,
                cart=cart_item.cart,
                success=True,
                message="Cart updated"
            )
        except CartItem.DoesNotExist:
            return UpdateCartItemMutation(success=False, message="Cart item not found")
        except Exception as e:
            return UpdateCartItemMutation(success=False, message=str(e))


class ClearCartMutation(graphene.Mutation):
    """Clear entire cart"""
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info):
        try:
            user = info.context.user
            if not user.is_authenticated:
                return ClearCartMutation(success=False, message="User not authenticated")

            try:
                cart = Cart.objects.get(customer=user)
                # Delete full cart record so backend matches frontend expectation
                # of "no cart" after clear action.
                cart.delete()
                return ClearCartMutation(success=True, message="Cart cleared")
            except Cart.DoesNotExist:
                return ClearCartMutation(success=False, message="Cart not found")

        except Exception as e:
            return ClearCartMutation(success=False, message=str(e))


class CartQuery(graphene.ObjectType):
    """Cart queries"""
    get_cart = graphene.Field(CartType)
    cart_total = graphene.Float()
    cart_items_count = graphene.Int()

    def resolve_get_cart(self, info):
        user = info.context.user
        if not user.is_authenticated:
            return None
        try:
            return Cart.objects.get(customer=user)
        except Cart.DoesNotExist:
            # Do not auto-create an empty cart. This keeps DB clean and ensures
            # "clear cart" removes both items and cart row until user adds again.
            return None

    def resolve_cart_total(self, info):
        user = info.context.user
        if not user.is_authenticated:
            return 0
        try:
            cart = Cart.objects.get(customer=user)
            return cart.get_total()
        except Cart.DoesNotExist:
            return 0

    def resolve_cart_items_count(self, info):
        user = info.context.user
        if not user.is_authenticated:
            return 0
        try:
            cart = Cart.objects.get(customer=user)
            return cart.get_items_count()
        except Cart.DoesNotExist:
            return 0


class CartMutation(graphene.ObjectType):
    """Cart mutations"""
    add_to_cart = AddToCartMutation.Field()
    remove_from_cart = RemoveFromCartMutation.Field()
    update_cart_item = UpdateCartItemMutation.Field()
    clear_cart = ClearCartMutation.Field()
