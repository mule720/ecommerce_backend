"""
Wishlist Service - GraphQL Schema
"""

import graphene
import uuid
from decimal import Decimal

from .models import Wishlist, WishlistItem, WishlistShare, WishlistNotification
from product_service.models import Product


class WishlistItemType(graphene.ObjectType):
    """GraphQL type that exposes the `WishlistItem` model fields to API clients."""
    id = graphene.Int()
    product_id = graphene.Int()
    product_name = graphene.String()
    product_image = graphene.String()
    price_when_added = graphene.Decimal()
    current_price = graphene.Decimal()
    price_saved = graphene.Decimal()
    notify_on_price_drop = graphene.Boolean()
    notify_on_sale = graphene.Boolean()
    notify_back_in_stock = graphene.Boolean()
    notes = graphene.String()
    added_at = graphene.DateTime()
    
    def resolve_price_saved(self, info):
        """Resolver for the GraphQL field `price saved`."""
        return self.price_when_added - self.current_price


class WishlistType(graphene.ObjectType):
    """GraphQL type that exposes the `Wishlist` model fields to API clients."""
    id = graphene.Int()
    item_count = graphene.Int()
    total_value = graphene.Decimal()
    is_public = graphene.Boolean()
    items = graphene.List(WishlistItemType)
    created_at = graphene.DateTime()
    
    def resolve_item_count(self, info):
        """Resolver for the GraphQL field `item count`."""
        return self.items.count()
    
    def resolve_total_value(self, info):
        """Resolver for the GraphQL field `total value`."""
        total = sum(item.current_price for item in self.items.all())
        return Decimal(str(total))
    
    def resolve_items(self, info):
        """Resolver for the GraphQL field `items`."""
        return self.items.all()


class WishlistQuery(graphene.ObjectType):
    """Groups GraphQL read operations (queries) for this module."""
    my_wishlist = graphene.Field(WishlistType)
    wishlist_items = graphene.List(WishlistItemType)
    public_wishlist = graphene.Field(
        WishlistType,
        share_token=graphene.String(required=True)
    )
    
    @staticmethod
    def resolve_my_wishlist(obj, info):
        """Resolver for the GraphQL field `my wishlist`."""
        if not info.context.user.is_authenticated:
            return None
        
        wishlist, _ = Wishlist.objects.get_or_create(user=info.context.user)
        return wishlist
    
    @staticmethod
    def resolve_wishlist_items(obj, info):
        """Resolver for the GraphQL field `wishlist items`."""
        if not info.context.user.is_authenticated:
            return []
        
        wishlist, _ = Wishlist.objects.get_or_create(user=info.context.user)
        items = wishlist.items.select_related('product').all()
        
        return [
            WishlistItemType(
                id=item.id,
                product_id=item.product.id,
                product_name=item.product.name,
                product_image=item.product.images.filter(is_primary=True).first().image.url if item.product.images.exists() else None,
                price_when_added=item.price_when_added,
                current_price=item.current_price,
                notify_on_price_drop=item.notify_on_price_drop,
                notify_on_sale=item.notify_on_sale,
                notify_back_in_stock=item.notify_back_in_stock,
                notes=item.notes,
                added_at=item.added_at,
            )
            for item in items
        ]
    
    @staticmethod
    def resolve_public_wishlist(obj, info, share_token):
        """Resolver for the GraphQL field `public wishlist`."""
        try:
            wishlist = Wishlist.objects.get(share_token=share_token, is_public=True)
            return WishlistType(
                id=wishlist.id,
                is_public=wishlist.is_public,
                items=wishlist.items.select_related('product').all(),
                created_at=wishlist.created_at,
            )
        except Wishlist.DoesNotExist:
            return None


class AddToWishlist(graphene.Mutation):
    """Defines the purpose and behavior of the `AddToWishlist` class."""
    class Arguments:
        """Defines the purpose and behavior of the `Arguments` class."""
        product_id = graphene.Int(required=True)
        notify_price_drop = graphene.Boolean(default_value=True)
        notify_sale = graphene.Boolean(default_value=True)
        notify_back_in_stock = graphene.Boolean(default_value=True)
        notes = graphene.String()
    
    success = graphene.Boolean()
    message = graphene.String()
    item = graphene.Field(WishlistItemType)
    
    @staticmethod
    def mutate(
        root, info,
        product_id,
        notify_price_drop=True,
        notify_sale=True,
        notify_back_in_stock=True,
        notes=''
    ):
        """Executes mutation business rules and returns the mutation response object."""
        if not info.context.user.is_authenticated:
            return AddToWishlist(success=False, message="Not authenticated")
        
        try:
            product = Product.objects.get(id=product_id, status='active')
            wishlist, _ = Wishlist.objects.get_or_create(user=info.context.user)
            
            item, created = WishlistItem.objects.update_or_create(
                wishlist=wishlist,
                product=product,
                defaults={
                    'price_when_added': product.price,
                    'current_price': product.price,
                    'notify_on_price_drop': notify_price_drop,
                    'notify_on_sale': notify_sale,
                    'notify_back_in_stock': notify_back_in_stock,
                    'notes': notes,
                }
            )
            
            message = "Added to wishlist" if created else "Updated in wishlist"
            return AddToWishlist(
                success=True,
                message=message,
                item=WishlistItemType(
                    id=item.id,
                    product_id=product.id,
                    product_name=product.name,
                    price_when_added=item.price_when_added,
                    current_price=item.current_price,
                    notes=item.notes,
                    added_at=item.added_at,
                )
            )
        except Product.DoesNotExist:
            return AddToWishlist(success=False, message="Product not found")


class RemoveFromWishlist(graphene.Mutation):
    """Defines the purpose and behavior of the `RemoveFromWishlist` class."""
    class Arguments:
        """Defines the purpose and behavior of the `Arguments` class."""
        item_id = graphene.Int(required=True)
    
    success = graphene.Boolean()
    message = graphene.String()
    
    @staticmethod
    def mutate(root, info, item_id):
        """Executes mutation business rules and returns the mutation response object."""
        if not info.context.user.is_authenticated:
            return RemoveFromWishlist(success=False, message="Not authenticated")
        
        try:
            item = WishlistItem.objects.get(id=item_id, wishlist__user=info.context.user)
            item.delete()
            return RemoveFromWishlist(success=True, message="Removed from wishlist")
        except WishlistItem.DoesNotExist:
            return RemoveFromWishlist(success=False, message="Item not found")


class UpdateWishlistItem(graphene.Mutation):
    """Defines the purpose and behavior of the `UpdateWishlistItem` class."""
    class Arguments:
        """Defines the purpose and behavior of the `Arguments` class."""
        item_id = graphene.Int(required=True)
        notes = graphene.String()
        notify_price_drop = graphene.Boolean()
        notify_sale = graphene.Boolean()
        notify_back_in_stock = graphene.Boolean()
    
    success = graphene.Boolean()
    item = graphene.Field(WishlistItemType)
    
    @staticmethod
    def mutate(
        root, info, item_id,
        notes=None,
        notify_price_drop=None,
        notify_sale=None,
        notify_back_in_stock=None
    ):
        """Executes mutation business rules and returns the mutation response object."""
        if not info.context.user.is_authenticated:
            return UpdateWishlistItem(success=False)
        
        try:
            item = WishlistItem.objects.get(id=item_id, wishlist__user=info.context.user)
            
            if notes is not None:
                item.notes = notes
            if notify_price_drop is not None:
                item.notify_on_price_drop = notify_price_drop
            if notify_sale is not None:
                item.notify_on_sale = notify_sale
            if notify_back_in_stock is not None:
                item.notify_back_in_stock = notify_back_in_stock
            
            item.save()
            return UpdateWishlistItem(success=True, item=item)
        except WishlistItem.DoesNotExist:
            return UpdateWishlistItem(success=False)


class ShareWishlist(graphene.Mutation):
    """Defines the purpose and behavior of the `ShareWishlist` class."""
    class Arguments:
        """Defines the purpose and behavior of the `Arguments` class."""
        make_public = graphene.Boolean(default_value=True)
        share_email = graphene.String()
    
    success = graphene.Boolean()
    share_token = graphene.String()
    share_url = graphene.String()
    
    @staticmethod
    def mutate(root, info, make_public=True, share_email=None):
        """Executes mutation business rules and returns the mutation response object."""
        if not info.context.user.is_authenticated:
            return ShareWishlist(success=False)
        
        wishlist, _ = Wishlist.objects.get_or_create(user=info.context.user)
        
        if make_public and not wishlist.share_token:
            wishlist.share_token = str(uuid.uuid4())
            wishlist.is_public = True
            wishlist.save()
        
        if share_email:
            WishlistShare.objects.create(
                wishlist=wishlist,
                shared_with_email=share_email
            )
        
        return ShareWishlist(
            success=True,
            share_token=wishlist.share_token,
            share_url=f"/wishlist/{wishlist.share_token}"
        )


class WishlistMutation(graphene.ObjectType):
    """Groups GraphQL write operations (mutations) for this module."""
    add_to_wishlist = AddToWishlist.Field()
    remove_from_wishlist = RemoveFromWishlist.Field()
    update_wishlist_item = UpdateWishlistItem.Field()
    share_wishlist = ShareWishlist.Field()
