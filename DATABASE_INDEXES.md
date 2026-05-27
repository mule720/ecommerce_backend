"""
Database indexes for performance optimization
Add these to product_service, search_service, and order_service models
"""

# product_service/models.py additions:
"""
Add these indexes to Product model Meta class:

class Meta:
    indexes = [
        models.Index(fields=['status', 'is_featured']),
        models.Index(fields=['vendor', 'status']),
        models.Index(fields=['category', 'status']),
        models.Index(fields=['slug']),
        models.Index(fields=['created_at', 'status']),
    ]
"""

# search_service/models.py additions:
"""
Add these indexes to ProductSearchIndex model Meta class:

class Meta:
    indexes = [
        models.Index(fields=['name']),
        models.Index(fields=['search_text']),
        models.Index(fields=['product', 'is_active']),
        models.Index(fields=['rating', '-review_count']),
        models.Index(fields=['price_min', 'price_max']),
        models.Index(fields=['category_name']),
    ]
"""

# order_service/models.py additions:
"""
Add these indexes to Order model Meta class:

class Meta:
    indexes = [
        models.Index(fields=['customer', 'created_at']),
        models.Index(fields=['status']),
        models.Index(fields=['order_number']),
        models.Index(fields=['payment_status']),
    ]
    
Add these indexes to Cart model Meta class:

class Meta:
    indexes = [
        models.Index(fields=['customer']),
    ]
"""
