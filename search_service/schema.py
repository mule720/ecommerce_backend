"""
Search Service - GraphQL Schema
"""

import graphene
from django.db.models import Q, F
from decimal import Decimal
from django.core.cache import caches

from .models import (
    SearchFilter, SearchLog, ProductSearchIndex, PopularSearch,
    ProductView, ProductInteraction, BrowsingHistory, UserEngagementMetric
)
from product_service.models import Product, Category
from ecom_backend.query_optimization import cache_query_result


class SearchFilterType(graphene.ObjectType):
    """GraphQL type that exposes the `SearchFilter` model fields to API clients."""
    id = graphene.Int()
    name = graphene.String()
    filters = graphene.JSONString()
    created_at = graphene.DateTime()


class ProductSearchResultType(graphene.ObjectType):
    """GraphQL type that exposes the `ProductSearchResult` model fields to API clients."""
    id = graphene.Int()
    name = graphene.String()
    price = graphene.Decimal()
    rating = graphene.Decimal()
    review_count = graphene.Int()
    image = graphene.String()
    category = graphene.String()
    vendor = graphene.String()
    discount_percentage = graphene.Decimal()


class PopularSearchType(graphene.ObjectType):
    """GraphQL type that exposes the `PopularSearch` model fields to API clients."""
    query = graphene.String()
    count = graphene.Int()


class ProductViewType(graphene.ObjectType):
    """GraphQL type for ProductView"""
    id = graphene.Int()
    product_id = graphene.Int()
    product_name = graphene.String()
    view_duration = graphene.Int()
    source = graphene.String()
    device_type = graphene.String()
    viewed_at = graphene.DateTime()


class ProductInteractionType(graphene.ObjectType):
    """GraphQL type for ProductInteraction"""
    id = graphene.Int()
    product_id = graphene.Int()
    product_name = graphene.String()
    interaction_type = graphene.String()
    interaction_value = graphene.String()
    page = graphene.String()
    device_type = graphene.String()
    created_at = graphene.DateTime()


class BrowsingHistoryType(graphene.ObjectType):
    """GraphQL type for BrowsingHistory"""
    id = graphene.Int()
    product_id = graphene.Int()
    product_name = graphene.String()
    view_count = graphene.Int()
    last_viewed_at = graphene.DateTime()
    added_at = graphene.DateTime()


class UserEngagementMetricType(graphene.ObjectType):
    """GraphQL type for UserEngagementMetric"""
    engagement_score = graphene.Float()
    total_searches = graphene.Int()
    total_views = graphene.Int()
    total_adds_to_cart = graphene.Int()
    total_wishlist_adds = graphene.Int()
    total_purchases = graphene.Int()
    total_reviews = graphene.Int()
    avg_session_duration = graphene.Int()
    last_activity_at = graphene.DateTime()


class SearchQuery(graphene.ObjectType):
    """Groups GraphQL read operations (queries) for this module."""
    search_products = graphene.List(
        ProductSearchResultType,
        query=graphene.String(required=True),
        category_id=graphene.Int(),
        min_price=graphene.Decimal(),
        max_price=graphene.Decimal(),
        min_rating=graphene.Decimal(),
        sort_by=graphene.String(),
        limit=graphene.Int(),
        offset=graphene.Int(),
    )
    
    saved_filters = graphene.List(SearchFilterType)
    
    popular_searches = graphene.List(
        PopularSearchType,
        limit=graphene.Int(default_value=10)
    )
    
    filter_options = graphene.JSONString(
        category_id=graphene.Int()
    )
    
    # New interaction tracking queries
    my_browsing_history = graphene.List(BrowsingHistoryType, limit=graphene.Int(default_value=50))
    my_product_views = graphene.List(ProductViewType, limit=graphene.Int(default_value=50))
    my_engagement_metric = graphene.Field(UserEngagementMetricType)
    product_views = graphene.List(
        ProductViewType,
        product_id=graphene.Int(required=True),
        limit=graphene.Int(default_value=100)
    )
    product_interactions = graphene.List(
        ProductInteractionType,
        product_id=graphene.Int(required=True),
        interaction_type=graphene.String(),
        limit=graphene.Int(default_value=100)
    )
    
    @staticmethod
    def resolve_search_products(
        obj, info,
        query,
        category_id=None,
        min_price=None,
        max_price=None,
        min_rating=None,
        sort_by='relevance',
        limit=20,
        offset=0
    ):
        # Create cache key from search parameters
        """Resolver for the GraphQL field `search products`."""
        cache_key = f"search:{query}:{category_id}:{min_price}:{max_price}:{min_rating}:{sort_by}:{limit}:{offset}"
        cache_backend = caches['default']
        
        # Check cache first
        cached_results = cache_backend.get(cache_key)
        if cached_results is not None:
            return cached_results
        
        # Full-text search with filters - use index for speed
        queryset = ProductSearchIndex.objects.filter(
            Q(name__icontains=query) | Q(search_text__icontains=query),
            is_active=True
        ).select_related('product')
        
        # Apply filters
        if category_id:
            queryset = queryset.filter(product__category_id=category_id)
        
        if min_price:
            queryset = queryset.filter(price_min__gte=min_price)
        
        if max_price:
            queryset = queryset.filter(price_max__lte=max_price)
        
        if min_rating:
            queryset = queryset.filter(rating__gte=min_rating)
        
        # Sorting - only most relevant fields to reduce query complexity
        if sort_by == 'price_low':
            queryset = queryset.order_by('price_min')
        elif sort_by == 'price_high':
            queryset = queryset.order_by('-price_min')
        elif sort_by == 'rating':
            queryset = queryset.order_by('-rating')
        elif sort_by == 'newest':
            queryset = queryset.order_by('-updated_at')
        else:  # relevance - optimized
            queryset = queryset.order_by('-review_count', '-rating')
        
        # Pagination with limit to query size
        total = queryset.count()
        items = list(queryset[offset:min(offset+limit, 100)])
        
        results = []
        for item in items:
            product = item.product
            primary_image = product.images.filter(is_primary=True).first()
            results.append(ProductSearchResultType(
                id=product.id,
                name=product.name,
                price=product.price,
                rating=item.rating,
                review_count=item.review_count,
                image=primary_image.image.url if primary_image else None,
                category=item.category_name,
                vendor=item.vendor_name,
                discount_percentage=((product.compare_at_price - product.price) / product.compare_at_price * 100) if product.compare_at_price else Decimal('0')
            ))
        
        # Cache results for 5 minutes
        cache_backend.set(cache_key, results, 300)
        
        # Log search (async in production)
        user = info.context.user if info.context.user.is_authenticated else None
        SearchLog.objects.create(
            user=user,
            query=query,
            filters={
                'category_id': category_id,
                'min_price': str(min_price) if min_price else None,
                'max_price': str(max_price) if max_price else None,
                'min_rating': str(min_rating) if min_rating else None,
            },
            results_count=len(results)
        )
        
        # Update popular searches (batch in production)
        from django.db import models
        PopularSearch.objects.filter(query=query).update(
            count=models.F('count') + 1
        ) or PopularSearch.objects.create(query=query, count=1)
        
        return results
    
    @staticmethod
    def resolve_saved_filters(obj, info):
        """Resolver for the GraphQL field `saved filters`."""
        if not info.context.user.is_authenticated:
            return []
        
        filters = SearchFilter.objects.filter(user=info.context.user)
        return [
            SearchFilterType(
                id=f.id,
                name=f.name,
                filters=f.filters,
                created_at=f.created_at
            )
            for f in filters
        ]
    
    @staticmethod
    def resolve_popular_searches(obj, info, limit=10):
        """Resolver for the GraphQL field `popular searches`."""
        searches = PopularSearch.objects.all()[:limit]
        return [
            PopularSearchType(query=s.query, count=s.count)
            for s in searches
        ]
    
    @staticmethod
    def resolve_filter_options(obj, info, category_id=None):
        """Resolver for the GraphQL field `filter options`."""
        products = Product.objects.filter(status='active')
        
        if category_id:
            products = products.filter(category_id=category_id)
        
        # Get distinct values
        prices = products.values_list('price', flat=True).distinct()
        categories = Category.objects.filter(is_active=True).values('id', 'name')
        
        return {
            'price_range': {
                'min': min(prices) if prices else 0,
                'max': max(prices) if prices else 0,
            },
            'categories': list(categories),
            'ratings': [
                {'value': 5, 'label': '5 stars'},
                {'value': 4, 'label': '4+ stars'},
                {'value': 3, 'label': '3+ stars'},
                {'value': 2, 'label': '2+ stars'},
                {'value': 1, 'label': '1+ stars'},
            ]
        }
    
    @staticmethod
    def resolve_my_browsing_history(obj, info, limit=50):
        """Get user's browsing history"""
        if not info.context.user.is_authenticated:
            return []
        
        history = BrowsingHistory.objects.filter(
            user=info.context.user
        ).select_related('product').order_by('-last_viewed_at')[:limit]
        
        return [
            BrowsingHistoryType(
                id=h.id,
                product_id=h.product_id,
                product_name=h.product.name,
                view_count=h.view_count,
                last_viewed_at=h.last_viewed_at,
                added_at=h.added_at,
            )
            for h in history
        ]
    
    @staticmethod
    def resolve_my_product_views(obj, info, limit=50):
        """Get user's recent product views"""
        if not info.context.user.is_authenticated:
            return []
        
        views = ProductView.objects.filter(
            user=info.context.user
        ).select_related('product').order_by('-viewed_at')[:limit]
        
        return [
            ProductViewType(
                id=v.id,
                product_id=v.product_id,
                product_name=v.product.name,
                view_duration=v.view_duration,
                source=v.source,
                device_type=v.device_type,
                viewed_at=v.viewed_at,
            )
            for v in views
        ]
    
    @staticmethod
    def resolve_my_engagement_metric(obj, info):
        """Get user's engagement metric"""
        if not info.context.user.is_authenticated:
            return None
        
        try:
            metric = UserEngagementMetric.objects.get(user=info.context.user)
            return UserEngagementMetricType(
                engagement_score=metric.engagement_score,
                total_searches=metric.total_searches,
                total_views=metric.total_views,
                total_adds_to_cart=metric.total_adds_to_cart,
                total_wishlist_adds=metric.total_wishlist_adds,
                total_purchases=metric.total_purchases,
                total_reviews=metric.total_reviews,
                avg_session_duration=metric.avg_session_duration,
                last_activity_at=metric.last_activity_at,
            )
        except UserEngagementMetric.DoesNotExist:
            return None
    
    @staticmethod
    def resolve_product_views(obj, info, product_id, limit=100):
        """Get views for a specific product (staff only)"""
        if not info.context.user.is_staff:
            return []
        
        views = ProductView.objects.filter(
            product_id=product_id
        ).order_by('-viewed_at')[:limit]
        
        return [
            ProductViewType(
                id=v.id,
                product_id=v.product_id,
                product_name=v.product.name,
                view_duration=v.view_duration,
                source=v.source,
                device_type=v.device_type,
                viewed_at=v.viewed_at,
            )
            for v in views
        ]
    
    @staticmethod
    def resolve_product_interactions(obj, info, product_id, interaction_type=None, limit=100):
        """Get interactions for a specific product (staff only)"""
        if not info.context.user.is_staff:
            return []
        
        queryset = ProductInteraction.objects.filter(
            product_id=product_id
        )
        
        if interaction_type:
            queryset = queryset.filter(interaction_type=interaction_type)
        
        interactions = queryset.order_by('-created_at')[:limit]
        
        return [
            ProductInteractionType(
                id=i.id,
                product_id=i.product_id,
                product_name=i.product.name,
                interaction_type=i.interaction_type,
                interaction_value=i.interaction_value,
                page=i.page,
                device_type=i.device_type,
                created_at=i.created_at,
            )
            for i in interactions
        ]


class SaveSearchFilter(graphene.Mutation):
    """Reusable filter configuration used to narrow list query results."""
    class Arguments:
        """Defines the purpose and behavior of the `Arguments` class."""
        name = graphene.String(required=True)
        filters = graphene.JSONString(required=True)
    
    success = graphene.Boolean()
    filter_id = graphene.Int()
    
    @staticmethod
    def mutate(root, info, name, filters):
        """Executes mutation business rules and returns the mutation response object."""
        if not info.context.user.is_authenticated:
            return SaveSearchFilter(success=False)
        
        search_filter = SearchFilter.objects.create(
            user=info.context.user,
            name=name,
            filters=filters
        )
        return SaveSearchFilter(success=True, filter_id=search_filter.id)


class DeleteSearchFilter(graphene.Mutation):
    """Reusable filter configuration used to narrow list query results."""
    class Arguments:
        """Defines the purpose and behavior of the `Arguments` class."""
        filter_id = graphene.Int(required=True)
    
    success = graphene.Boolean()
    
    @staticmethod
    def mutate(root, info, filter_id):
        """Executes mutation business rules and returns the mutation response object."""
        if not info.context.user.is_authenticated:
            return DeleteSearchFilter(success=False)
        
        try:
            SearchFilter.objects.get(id=filter_id, user=info.context.user).delete()
            return DeleteSearchFilter(success=True)
        except SearchFilter.DoesNotExist:
            return DeleteSearchFilter(success=False)


class LogProductViewMutation(graphene.Mutation):
    """Log a product view"""
    class Arguments:
        product_id = graphene.Int(required=True)
        view_duration = graphene.Int(default_value=0)
        source = graphene.String(default_value='direct')
        device_type = graphene.String(default_value='desktop')
    
    success = graphene.Boolean()
    message = graphene.String()
    
    @staticmethod
    def mutate(root, info, product_id, view_duration=0, source='direct', device_type='desktop'):
        """Log a product view"""
        try:
            from product_service.models import Product
            
            product = Product.objects.get(id=product_id)
            user = info.context.user if info.context.user.is_authenticated else None
            
            ProductView.objects.create(
                product=product,
                user=user,
                view_duration=view_duration,
                source=source,
                device_type=device_type
            )
            
            # Update browsing history
            if user:
                history, created = BrowsingHistory.objects.get_or_create(
                    user=user,
                    product=product
                )
                if not created:
                    history.view_count += 1
                    history.save(update_fields=['view_count', 'last_viewed_at'])
            
            return LogProductViewMutation(success=True, message='View logged')
        except Exception as e:
            return LogProductViewMutation(success=False, message=str(e))


class LogProductInteractionMutation(graphene.Mutation):
    """Log a product interaction"""
    class Arguments:
        product_id = graphene.Int(required=True)
        interaction_type = graphene.String(required=True)
        interaction_value = graphene.String()
        page = graphene.String()
        device_type = graphene.String(default_value='desktop')
    
    success = graphene.Boolean()
    message = graphene.String()
    
    @staticmethod
    def mutate(root, info, product_id, interaction_type, interaction_value='', page='', device_type='desktop'):
        """Log a product interaction"""
        try:
            from product_service.models import Product
            
            product = Product.objects.get(id=product_id)
            user = info.context.user if info.context.user.is_authenticated else None
            
            ProductInteraction.objects.create(
                product=product,
                user=user,
                interaction_type=interaction_type,
                interaction_value=interaction_value,
                page=page,
                device_type=device_type
            )
            
            # Update engagement metric
            if user:
                metric, created = UserEngagementMetric.objects.get_or_create(user=user)
                
                # Increment relevant counter
                if interaction_type == 'add_to_cart':
                    metric.total_adds_to_cart += 1
                elif interaction_type == 'add_to_wishlist':
                    metric.total_wishlist_adds += 1
                elif interaction_type == 'purchase':
                    metric.total_purchases += 1
                elif interaction_type == 'review':
                    metric.total_reviews += 1
                elif interaction_type == 'view':
                    metric.total_views += 1
                
                from django.utils import timezone
                metric.last_activity_at = timezone.now()
                metric.save()
            
            return LogProductInteractionMutation(success=True, message='Interaction logged')
        except Exception as e:
            return LogProductInteractionMutation(success=False, message=str(e))


class SearchMutation(graphene.ObjectType):
    """Groups GraphQL write operations (mutations) for this module."""
    save_search_filter = SaveSearchFilter.Field()
    delete_search_filter = DeleteSearchFilter.Field()
    log_product_view = LogProductViewMutation.Field()
    log_product_interaction = LogProductInteractionMutation.Field()
