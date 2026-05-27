"""
Database query optimization utilities
- Automatic select_related and prefetch_related
- Query countlimit
- Caching decorators
"""
from django.views.decorators.cache import cache_page
from django.core.cache import cache
from functools import wraps
import hashlib
import json


def get_optimized_products(queryset=None, limit=None):
    """
    Get products with all related data in minimal queries
    Uses select_related and prefetch_related to avoid N+1 queries
    """
    from product_service.models import Product
    
    if queryset is None:
        queryset = Product.objects.all()
    
    # Use select_related for ForeignKey relationships
    queryset = queryset.select_related(
        'vendor',
        'category',
    )
    
    # Use prefetch_related for reverse ForeignKey and M2M
    queryset = queryset.prefetch_related(
        'images',
        'variants',
        'reviews',
    )
    
    if limit:
        queryset = queryset[:limit]
    
    return queryset


def get_optimized_orders(queryset=None, limit=None):
    """
    Get orders with all related data in minimal queries
    """
    from order_service.models import Order
    
    if queryset is None:
        queryset = Order.objects.all()
    
    queryset = queryset.select_related(
        'user',
    )
    
    queryset = queryset.prefetch_related(
        'items',
        'items__product',
    )
    
    if limit:
        queryset = queryset[:limit]
    
    return queryset


class CacheQuerySet:
    """Cache queryset results by cache key"""
    
    @staticmethod
    def cache_key(prefix, **kwargs):
        """Generate cache key from parameters"""
        key_data = json.dumps(kwargs, sort_keys=True, default=str)
        hash_suffix = hashlib.md5(key_data.encode()).hexdigest()[:8]
        return f"{prefix}:{hash_suffix}"
    
    @staticmethod
    def get_or_set(prefix, func, timeout=300, **kwargs):
        """Get from cache or call func and cache result"""
        key = CacheQuerySet.cache_key(prefix, **kwargs)
        result = cache.get(key)
        
        if result is None:
            result = func(**kwargs)
            cache.set(key, result, timeout)
        
        return result


def cache_query_result(prefix, timeout=300):
    """
    Decorator to cache function results based on arguments
    
    Usage:
        @cache_query_result('products', timeout=3600)
        def get_products(category_id=None):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Create cache key from function name and arguments
            key_data = {
                'func': func.__name__,
                'args': args,
                'kwargs': kwargs
            }
            key = CacheQuerySet.cache_key(prefix, **key_data)
            
            result = cache.get(key)
            if result is None:
                result = func(*args, **kwargs)
                cache.set(key, result, timeout)
            
            return result
        
        return wrapper
    return decorator


def cache_view_result(timeout=300):
    """
    Decorator to cache view/field resolution results
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Create cache key from function name, self, and kwargs
            key_parts = [func.__name__]
            
            if args and hasattr(args[0], 'pk'):
                key_parts.append(str(args[0].pk))
            
            key = ':'.join(key_parts)
            
            result = cache.get(key)
            if result is None:
                result = func(*args, **kwargs)
                cache.set(key, result, timeout)
            
            return result
        
        return wrapper
    return decorator


def invalidate_cache(pattern_prefix):
    """
    Invalidate cache keys matching pattern
    Note: This is approximate and requires KEYS command
    """
    from django.core.cache import caches
    cache_instance = caches['default']
    
    try:
        # This works with redis-py
        if hasattr(cache_instance, '_cache'):
            client = cache_instance._cache
            if hasattr(client, 'delete_many'):
                # Get all keys matching pattern
                cursor = 0
                while True:
                    cursor, keys = client.scan(cursor, match=f"ecom:{pattern_prefix}:*")
                    if keys:
                        client.delete(*keys)
                    if cursor == 0:
                        break
    except Exception as e:
        print(f"Cache invalidation failed: {e}")
