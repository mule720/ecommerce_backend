"""
Product Service GraphQL Schema
GraphQL API for product management
"""
import graphene
from graphene import relay
from graphene_django import DjangoObjectType
from graphene_django.filter import DjangoFilterConnectionField
from django_filters import FilterSet, CharFilter, NumberFilter, BooleanFilter
from django.conf import settings
import json
from decimal import Decimal
from django.core.cache import caches
from .models import (
    Category, Product, ProductImage, ProductVariant,
    ProductReview, Collection, Tag, InventorySyncLog
)
from ecom_backend.query_optimization import (
    get_optimized_products,
    cache_view_result,
    cache_query_result,
)


class CategoryType(DjangoObjectType):
    """GraphQL type for Category model"""
    class Meta:
        """Defines the purpose and behavior of the `Meta` class."""
        model = Category
        fields = "__all__"
        interfaces = (relay.Node,)


class ProductImageType(DjangoObjectType):
    """GraphQL type for ProductImage model"""
    class Meta:
        """Defines the purpose and behavior of the `Meta` class."""
        model = ProductImage
        fields = "__all__"
        interfaces = (relay.Node,)


class ProductVariantType(DjangoObjectType):
    """GraphQL type for ProductVariant model"""
    class Meta:
        """Defines the purpose and behavior of the `Meta` class."""
        model = ProductVariant
        fields = "__all__"
        interfaces = (relay.Node,)


class ProductType(DjangoObjectType):
    """GraphQL type for Product model"""
    class Meta:
        """Defines the purpose and behavior of the `Meta` class."""
        model = Product
        fields = "__all__"
        interfaces = (relay.Node,)
    
    average_rating = graphene.Float()
    
    @cache_view_result(timeout=3600)
    def resolve_average_rating(self, info):
        """Resolver for the GraphQL field `average rating`."""
        reviews = self.reviews.filter(is_approved=True)
        if reviews.exists():
            return sum(r.rating for r in reviews) / reviews.count()
        return 0


class ProductReviewType(DjangoObjectType):
    """GraphQL type for ProductReview model"""
    class Meta:
        """Defines the purpose and behavior of the `Meta` class."""
        model = ProductReview
        fields = "__all__"
        interfaces = (relay.Node,)


class CollectionType(DjangoObjectType):
    """GraphQL type for Collection model"""
    class Meta:
        """Defines the purpose and behavior of the `Meta` class."""
        model = Collection
        fields = "__all__"
        interfaces = (relay.Node,)


class TagType(DjangoObjectType):
    """GraphQL type for Tag model"""
    class Meta:
        """Defines the purpose and behavior of the `Meta` class."""
        model = Tag
        fields = "__all__"
        interfaces = (relay.Node,)


class InventorySyncLogType(DjangoObjectType):
    """GraphQL type that exposes the `InventorySyncLog` model fields to API clients."""
    class Meta:
        """Defines the purpose and behavior of the `Meta` class."""
        model = InventorySyncLog
        fields = "__all__"
        interfaces = (relay.Node,)


# Filters
class ProductFilter(FilterSet):
    """Filter for Product queries"""
    category = CharFilter(field_name='category__slug')
    vendor = NumberFilter(field_name='vendor__id')
    min_price = NumberFilter(field_name='price', lookup_expr='gte')
    max_price = NumberFilter(field_name='price', lookup_expr='lte')
    is_featured = BooleanFilter(field_name='is_featured')
    search = CharFilter(method='search_filter')
    
    class Meta:
        """Defines the purpose and behavior of the `Meta` class."""
        model = Product
        fields = ['status', 'category', 'vendor', 'is_featured']
    
    def search_filter(self, queryset, name, value):
        """Implements `search filter` logic for this module."""
        return queryset.filter(name__icontains=value) | queryset.filter(description__icontains=value)


class CategoryFilter(FilterSet):
    """Filter for Category queries"""
    parent = CharFilter(field_name='parent__slug', exclude=True)
    
    class Meta:
        """Defines the purpose and behavior of the `Meta` class."""
        model = Category
        fields = ['name', 'is_active']


class CollectionFilter(FilterSet):
    """Filter for Collection queries"""

    class Meta:
        """Defines the purpose and behavior of the `Meta` class."""
        model = Collection
        fields = ['name', 'is_active']


class Query(graphene.ObjectType):
    """Product Service Queries"""
    
    # Category queries
    all_categories = DjangoFilterConnectionField(
        CategoryType,
        filterset_class=CategoryFilter
    )
    category = relay.Node.Field(CategoryType)
    category_by_slug = graphene.Field(
        CategoryType,
        slug=graphene.String(required=True)
    )
    
    # Product queries
    all_products = DjangoFilterConnectionField(
        ProductType,
        filterset_class=ProductFilter
    )
    product = relay.Node.Field(ProductType)
    product_by_slug = graphene.Field(
        ProductType,
        slug=graphene.String(required=True)
    )
    products_by_vendor = graphene.List(
        ProductType,
        vendor_id=graphene.ID(required=True)
    )
    featured_products = graphene.List(ProductType)
    
    # Product Review queries
    product_reviews = graphene.List(
        ProductReviewType,
        product_id=graphene.ID(required=True)
    )
    
    # Collection queries
    all_collections = DjangoFilterConnectionField(
        CollectionType,
        filterset_class=CollectionFilter
    )
    collection = relay.Node.Field(CollectionType)
    collection_by_slug = graphene.Field(
        CollectionType,
        slug=graphene.String(required=True)
    )
    
    # Tag queries
    all_tags = graphene.List(TagType)

    # Sync queries
    inventory_sync_logs = graphene.List(
        InventorySyncLogType,
        product_id=graphene.ID(required=False),
        direction=graphene.String(required=False),
    )
    
    # Resolvers
    def resolve_all_categories(self, info, **kwargs):
        # Return queryset (not list) because this field is a ConnectionField.
        # Returning lists here can break graphene-django filtering/pagination.
        """Resolver for the GraphQL field `all categories`."""
        return Category.objects.filter(is_active=True)
    
    def resolve_category_by_slug(self, info, slug):
        """Resolver for the GraphQL field `category by slug`."""
        cache_backend = caches['categories']
        key = f'category_slug:{slug}'
        category = cache_backend.get(key)
        if category is None:
            try:
                category = Category.objects.get(slug=slug, is_active=True)
                cache_backend.set(key, category, 7200)
            except Category.DoesNotExist:
                return None
        return category
    
    def resolve_all_products(self, info, **kwargs):
        # Return queryset (not list) because this field is a ConnectionField.
        # This also ensures fresh backend data appears in frontend immediately.
        """Resolver for the GraphQL field `all products`."""
        return get_optimized_products(
            Product.objects.filter(status='active'),
            limit=100
        )
    
    def resolve_product_by_slug(self, info, slug):
        """Resolver for the GraphQL field `product by slug`."""
        cache_backend = caches['products']
        key = f'product_slug:{slug}'
        product = cache_backend.get(key)
        if product is None:
            try:
                product = get_optimized_products(
                    Product.objects.filter(slug=slug, status='active')
                ).first()
                if product:
                    cache_backend.set(key, product, 3600)
            except Product.DoesNotExist:
                return None
        return product
    
    def resolve_products_by_vendor(self, info, vendor_id):
        """Resolver for the GraphQL field `products by vendor`."""
        cache_backend = caches['products']
        key = f'vendor_products:{vendor_id}'
        products = cache_backend.get(key)
        if products is None:
            try:
                vendor_id_int = int(vendor_id)
                products = get_optimized_products(
                    Product.objects.filter(vendor_id=vendor_id_int, status='active')
                )
                cache_backend.set(key, products, 3600)
            except (ValueError, TypeError):
                return []
        return products
    
    def resolve_featured_products(self, info):
        """Resolver for the GraphQL field `featured products`."""
        cache_backend = caches['products']
        key = 'featured_products'
        products = cache_backend.get(key)
        if products is None:
            products = get_optimized_products(
                Product.objects.filter(is_featured=True, status='active'),
                limit=20
            )
            cache_backend.set(key, products, 1800)  # 30 minutes
        return products
    
    def resolve_product_reviews(self, info, product_id):
        """Resolver for the GraphQL field `product reviews`."""
        cache_backend = caches['default']
        key = f'product_reviews:{product_id}'
        reviews = cache_backend.get(key)
        if reviews is None:
            try:
                product_id_int = int(product_id)
                reviews = list(ProductReview.objects.filter(
                    product_id=product_id_int,
                    is_approved=True
                ).select_related('user').order_by('-created_at'))
                cache_backend.set(key, reviews, 1800)
            except (ValueError, TypeError):
                return []
        return reviews
    
    def resolve_all_collections(self, info, **kwargs):
        """Resolver for the GraphQL field `all collections`."""
        return Collection.objects.filter(is_active=True)
    
    def resolve_collection_by_slug(self, info, slug):
        """Resolver for the GraphQL field `collection by slug`."""
        try:
            return Collection.objects.get(slug=slug, is_active=True)
        except Collection.DoesNotExist:
            return None
    
    def resolve_all_tags(self, info, **kwargs):
        """Resolver for the GraphQL field `all tags`."""
        return Tag.objects.all()

    def resolve_inventory_sync_logs(self, info, product_id=None, direction=None):
        """Resolver for the GraphQL field `inventory sync logs`."""
        queryset = InventorySyncLog.objects.select_related('product').all()
        if product_id:
            try:
                queryset = queryset.filter(product_id=int(product_id))
            except (TypeError, ValueError):
                return InventorySyncLog.objects.none()
        if direction:
            queryset = queryset.filter(direction=direction)
        return queryset


# Mutations
class CreateProductMutation(graphene.Mutation):
    """Create a new product"""
    class Arguments:
        """Defines the purpose and behavior of the `Arguments` class."""
        vendor_id = graphene.ID(required=True)
        category_id = graphene.ID()
        name = graphene.String(required=True)
        slug = graphene.String(required=True)
        description = graphene.String(required=True)
        price = graphene.Decimal(required=True)
        compare_at_price = graphene.Decimal()
        quantity = graphene.Int()
        sku = graphene.String()
        weight = graphene.Decimal()
        is_featured = graphene.Boolean()
        is_taxable = graphene.Boolean()
        tax_rate = graphene.Decimal()
        video = graphene.String()
        video_url = graphene.String()
        image_urls = graphene.List(graphene.String)
        variants = graphene.JSONString()
    
    product = graphene.Field(ProductType)
    
    @classmethod
    def mutate(cls, root, info, vendor_id, name, slug, description, price, **kwargs):
        """Executes mutation business rules and returns the mutation response object."""
        from user_service.models import User
        image_urls = kwargs.pop('image_urls', None) or []
        variants_payload = kwargs.pop('variants', None)
        video_path = str(kwargs.pop('video', '') or '').strip()
        video_url = str(kwargs.get('video_url', '') or '').strip()

        if video_path:
            kwargs['video'] = video_path
        if video_url:
            kwargs['video_url'] = video_url

        if len(image_urls) > 10:
            raise Exception('Maximum of 10 product images is allowed')

        try:
            vendor = User.objects.get(pk=int(vendor_id))
        except (User.DoesNotExist, ValueError):
            raise Exception('Vendor not found')

        if isinstance(variants_payload, str) and variants_payload.strip():
            try:
                variants_payload = json.loads(variants_payload)
            except json.JSONDecodeError:
                raise Exception('Invalid variants JSON payload')

        if variants_payload is None:
            variants_payload = []
        if not isinstance(variants_payload, list):
            raise Exception('Variants must be a list')

        # Products created by merchant flow should be visible immediately.
        kwargs.setdefault('status', Product.ProductStatus.ACTIVE)
        
        product = Product.objects.create(
            vendor=vendor,
            name=name,
            slug=slug,
            description=description,
            price=price,
            **kwargs
        )

        for index, image_url in enumerate(image_urls):
            cleaned_url = str(image_url or '').strip()
            if not cleaned_url:
                continue

            image_kwargs = {
                'product': product,
                'is_primary': (index == 0),
                'sort_order': index,
            }

            if cleaned_url.startswith('http://') or cleaned_url.startswith('https://'):
                image_kwargs['external_url'] = cleaned_url
            else:
                normalized_path = cleaned_url.lstrip('/')
                media_prefix = str(settings.MEDIA_URL or '').lstrip('/')
                if media_prefix and normalized_path.startswith(media_prefix):
                    normalized_path = normalized_path[len(media_prefix):].lstrip('/')
                image_kwargs['image'] = normalized_path

            ProductImage.objects.create(**image_kwargs)

        for index, variant in enumerate(variants_payload):
            if not isinstance(variant, dict):
                raise Exception('Each variant must be an object')

            color = str(variant.get('color', '')).strip()
            size = str(variant.get('size', '')).strip()
            variant_sku = str(variant.get('sku', '')).strip()
            try:
                quantity = int(variant.get('quantity', 0) or 0)
            except Exception:
                raise Exception('Variant quantity is invalid')

            variant_price_raw = variant.get('price', price)
            try:
                variant_price = Decimal(str(variant_price_raw))
            except Exception:
                raise Exception('Variant price is invalid')

            compare_price_raw = variant.get('compare_at_price')
            compare_price = None
            if compare_price_raw not in (None, ''):
                try:
                    compare_price = Decimal(str(compare_price_raw))
                except Exception:
                    raise Exception('Variant compare_at_price is invalid')

            variant_name_parts = [part for part in [color, size] if part]
            variant_name = ' / '.join(variant_name_parts) if variant_name_parts else f'Variant {index + 1}'

            ProductVariant.objects.create(
                product=product,
                name=variant_name,
                sku=variant_sku,
                price=variant_price,
                compare_at_price=compare_price,
                color=color,
                size=size,
                quantity=quantity,
                attributes=variant,
            )

        return CreateProductMutation(product=product)


class UpdateProductMutation(graphene.Mutation):
    """Update a product"""
    class Arguments:
        """Defines the purpose and behavior of the `Arguments` class."""
        id = graphene.ID(required=True)
        name = graphene.String()
        description = graphene.String()
        price = graphene.Decimal()
        compare_at_price = graphene.Decimal()
        quantity = graphene.Int()
        sku = graphene.String()
        status = graphene.String()
        is_featured = graphene.Boolean()
    
    product = graphene.Field(ProductType)
    
    @classmethod
    def mutate(cls, root, info, id, **kwargs):
        """Executes mutation business rules and returns the mutation response object."""
        try:
            product = Product.objects.get(pk=int(id))
        except (Product.DoesNotExist, ValueError):
            raise Exception('Product not found')
        
        for key, value in kwargs.items():
            if value is not None:
                setattr(product, key, value)
        
        product.save()
        return UpdateProductMutation(product=product)


class DeleteProductMutation(graphene.Mutation):
    """Delete a product (soft delete)"""
    class Arguments:
        """Defines the purpose and behavior of the `Arguments` class."""
        id = graphene.ID(required=True)
    
    success = graphene.Boolean()
    
    @classmethod
    def mutate(cls, root, info, id):
        """Executes mutation business rules and returns the mutation response object."""
        try:
            product = Product.objects.get(pk=int(id))
            product.status = 'deleted'
            product.save()
            return DeleteProductMutation(success=True)
        except (Product.DoesNotExist, ValueError):
            return DeleteProductMutation(success=False)


class CreateProductReviewMutation(graphene.Mutation):
    """Create a product review"""
    class Arguments:
        """Defines the purpose and behavior of the `Arguments` class."""
        product_id = graphene.ID(required=True)
        user_id = graphene.ID(required=True)
        rating = graphene.Int(required=True)
        title = graphene.String(required=True)
        comment = graphene.String(required=True)
    
    review = graphene.Field(ProductReviewType)
    
    @classmethod
    def mutate(cls, root, info, product_id, user_id, rating, title, comment):
        """Executes mutation business rules and returns the mutation response object."""
        from user_service.models import User
        
        try:
            product = Product.objects.get(pk=int(product_id))
            user = User.objects.get(pk=int(user_id))
        except (Product.DoesNotExist, User.DoesNotExist, ValueError):
            raise Exception('Product or User not found')
        
        review, created = ProductReview.objects.update_or_create(
            product=product,
            user=user,
            defaults={
                'rating': rating,
                'title': title,
                'comment': comment
            }
        )
        return CreateProductReviewMutation(review=review)


class CreateCategoryMutation(graphene.Mutation):
    """Create a new category"""
    class Arguments:
        """Defines the purpose and behavior of the `Arguments` class."""
        name = graphene.String(required=True)
        slug = graphene.String(required=True)
        description = graphene.String()
        parent_id = graphene.ID()
    
    category = graphene.Field(CategoryType)
    
    @classmethod
    def mutate(cls, root, info, name, slug, **kwargs):
        """Executes mutation business rules and returns the mutation response object."""
        parent_id = kwargs.get('parent_id')
        parent = None
        if parent_id:
            try:
                parent = Category.objects.get(pk=int(parent_id))
            except (Category.DoesNotExist, ValueError):
                pass
        
        category = Category.objects.create(
            name=name,
            slug=slug,
            parent=parent,
            description=kwargs.get('description', '')
        )
        return CreateCategoryMutation(category=category)


class CreateCollectionMutation(graphene.Mutation):
    """Create a new collection"""
    class Arguments:
        """Defines the purpose and behavior of the `Arguments` class."""
        name = graphene.String(required=True)
        slug = graphene.String(required=True)
        description = graphene.String()
        product_ids = graphene.List(graphene.ID)
    
    collection = graphene.Field(CollectionType)
    
    @classmethod
    def mutate(cls, root, info, name, slug, **kwargs):
        """Executes mutation business rules and returns the mutation response object."""
        product_ids = kwargs.get('product_ids', [])
        products = Product.objects.filter(pk__in=[int(pid) for pid in product_ids])
        
        collection = Collection.objects.create(
            name=name,
            slug=slug,
            description=kwargs.get('description', '')
        )
        collection.products.set(products)
        
        return CreateCollectionMutation(collection=collection)


class AddProductToCollectionMutation(graphene.Mutation):
    """Add a product to a collection"""
    class Arguments:
        """Defines the purpose and behavior of the `Arguments` class."""
        collection_id = graphene.ID(required=True)
        product_id = graphene.ID(required=True)
    
    collection = graphene.Field(CollectionType)
    
    @classmethod
    def mutate(cls, root, info, collection_id, product_id):
        """Executes mutation business rules and returns the mutation response object."""
        try:
            collection = Collection.objects.get(pk=int(collection_id))
            product = Product.objects.get(pk=int(product_id))
            collection.products.add(product)
            collection.save()
            return AddProductToCollectionMutation(collection=collection)
        except (Collection.DoesNotExist, Product.DoesNotExist, ValueError):
            raise Exception('Collection or Product not found')


class Mutation(graphene.ObjectType):
    """Product Service Mutations"""
    
    create_product = CreateProductMutation.Field()
    update_product = UpdateProductMutation.Field()
    delete_product = DeleteProductMutation.Field()
    create_product_review = CreateProductReviewMutation.Field()
    create_category = CreateCategoryMutation.Field()
    create_collection = CreateCollectionMutation.Field()
    add_product_to_collection = AddProductToCollectionMutation.Field()


class RegisterProductErpMappingMutation(graphene.Mutation):
    """Groups GraphQL write operations (mutations) for this module."""
    class Arguments:
        """Defines the purpose and behavior of the `Arguments` class."""
        product_id = graphene.ID(required=True)
        erp_product_id = graphene.String(required=True)
        erp_tenant_id = graphene.String(required=False)
        erp_vendor_id = graphene.String(required=False)

    product = graphene.Field(ProductType)

    @classmethod
    def mutate(cls, root, info, product_id, erp_product_id, erp_tenant_id="", erp_vendor_id=""):
        """Executes mutation business rules and returns the mutation response object."""
        try:
            product = Product.objects.get(pk=int(product_id))
        except (Product.DoesNotExist, ValueError):
            raise Exception('Product not found')

        product.erp_product_id = erp_product_id
        product.erp_tenant_id = erp_tenant_id or product.erp_tenant_id
        product.erp_vendor_id = erp_vendor_id or product.erp_vendor_id
        product.mark_inventory_synced()
        product.save(update_fields=['erp_product_id', 'erp_tenant_id', 'erp_vendor_id', 'last_inventory_sync_at', 'updated_at'])
        return RegisterProductErpMappingMutation(product=product)


class SyncInventoryFromErpMutation(graphene.Mutation):
    """Groups GraphQL write operations (mutations) for this module."""
    class Arguments:
        """Defines the purpose and behavior of the `Arguments` class."""
        erp_product_id = graphene.String(required=True)
        quantity_delta = graphene.Int(required=True)
        source_reference = graphene.String(required=True)
        erp_tenant_id = graphene.String(required=False)
        erp_vendor_id = graphene.String(required=False)
        payload = graphene.String(required=False)

    product = graphene.Field(ProductType)
    sync_log = graphene.Field(InventorySyncLogType)

    @classmethod
    def mutate(
        cls,
        root,
        info,
        erp_product_id,
        quantity_delta,
        source_reference,
        erp_tenant_id="",
        erp_vendor_id="",
        payload="{}",
    ):
        """Executes mutation business rules and returns the mutation response object."""
        product = Product.objects.filter(erp_product_id=erp_product_id).first()
        if not product:
            raise Exception('No e-commerce product mapping for ERP product')

        product.quantity = max(0, product.quantity - int(quantity_delta))
        if erp_tenant_id:
            product.erp_tenant_id = erp_tenant_id
        if erp_vendor_id:
            product.erp_vendor_id = erp_vendor_id
        product.mark_inventory_synced()
        product.save(update_fields=['quantity', 'erp_tenant_id', 'erp_vendor_id', 'last_inventory_sync_at', 'updated_at'])

        parsed_payload = {}
        if payload:
            try:
                parsed_payload = json.loads(payload)
            except Exception:
                parsed_payload = {'raw_payload': payload}

        sync_log = InventorySyncLog.objects.create(
            product=product,
            direction='erp_to_ecom',
            quantity_delta=int(quantity_delta),
            source_reference=source_reference,
            status='success',
            message='ERP POS sale synced to e-commerce inventory',
            payload=parsed_payload,
        )
        return SyncInventoryFromErpMutation(product=product, sync_log=sync_log)


class MarkInventorySentToErpMutation(graphene.Mutation):
    """Groups GraphQL write operations (mutations) for this module."""
    class Arguments:
        """Defines the purpose and behavior of the `Arguments` class."""
        product_id = graphene.ID(required=True)
        quantity_delta = graphene.Int(required=True)
        source_reference = graphene.String(required=True)
        payload = graphene.String(required=False)

    sync_log = graphene.Field(InventorySyncLogType)

    @classmethod
    def mutate(cls, root, info, product_id, quantity_delta, source_reference, payload="{}"):
        """Executes mutation business rules and returns the mutation response object."""
        try:
            product = Product.objects.get(pk=int(product_id))
        except (Product.DoesNotExist, ValueError):
            raise Exception('Product not found')

        parsed_payload = {}
        if payload:
            try:
                parsed_payload = json.loads(payload)
            except Exception:
                parsed_payload = {'raw_payload': payload}

        log = InventorySyncLog.objects.create(
            product=product,
            direction='ecom_to_erp',
            quantity_delta=int(quantity_delta),
            source_reference=source_reference,
            status='success',
            message='Inventory delta posted from e-commerce side for ERP consumption',
            payload=parsed_payload,
        )
        product.mark_inventory_synced()
        return MarkInventorySentToErpMutation(sync_log=log)


Mutation.register_product_erp_mapping = RegisterProductErpMappingMutation.Field()
Mutation.sync_inventory_from_erp = SyncInventoryFromErpMutation.Field()
Mutation.mark_inventory_sent_to_erp = MarkInventorySentToErpMutation.Field()


# Schema definition for Product Service
# NOTE: The gateway composes service Query/Mutation classes directly.
# Avoid eager schema instantiation here to prevent duplicate type
# registrations when all services are imported together.
