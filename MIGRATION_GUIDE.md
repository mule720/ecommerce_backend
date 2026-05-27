# Multi-Currency Implementation Migration Guide

## Step-by-Step Implementation

### Phase 1: Code Integration (1-2 hours)

#### 1.1 Add Files to Your Project

Copy these files to your e-commerce backend:

```
ecom_backend/
├── multi_currency.py (NEW - 800+ lines)
├── pricing_utils.py (NEW - 400+ lines)
├── graphql_currency_schema.py (NEW - 500+ lines)
├── management/
│   ├── __init__.py (NEW)
│   └── commands/
│       ├── __init__.py (NEW)
│       ├── init_currencies.py (NEW - 300+ lines)
│       └── update_exchange_rates.py (NEW - 50 lines)
├── MULTI_CURRENCY_GUIDE.md (Documentation)
├── MULTI_CURRENCY_SETTINGS.py (Configuration template)
└── API_DOCUMENTATION_MULTICURRENCY.md (API docs)

product_service/
└── models.py (MODIFIED - add base_currency field and methods)

order_service/
└── models.py (MODIFIED - add exchange_rate fields and methods)
```

#### 1.2 Update Django Settings

Add to your `settings.py`:

```python
# Import multi-currency configuration
import os
from pathlib import Path

# Multi-Currency Settings
CURRENCIES_ENABLED = True
DEFAULT_CURRENCY = 'USD'
CURRENCY_API_PROVIDER = os.getenv('CURRENCY_API_PROVIDER', 'manual')
CURRENCY_API_KEY = os.getenv('CURRENCY_API_KEY', '')

SUPPORTED_CURRENCIES = [
    'USD', 'EUR', 'GBP', 'JPY', 'ZMW', 'ZAR',
    'CAD', 'AUD', 'INR', 'NGN'
]

# Currency caching
CURRENCY_CACHE_TIMEOUT = 86400  # 24 hours

# Tax configuration
TAX_ENABLED = True
DEFAULT_TAX_RATE = 0.0
TAX_INCLUDES_SHIPPING = True

# Logging for currency operations
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'currency_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/currency.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'ecom_backend.multi_currency': {
            'handlers': ['currency_file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
```

### Phase 2: Database Migrations (1-2 hours)

#### 2.1 Create Migrations

Run these commands in your Django project:

```bash
# Create migrations for the new multi_currency models
python manage.py makemigrations

# Check what migrations will be created
python manage.py showmigrations

# Simulate the migration (optional, to verify)
python manage.py migrate --plan
```

#### 2.2 Apply Migrations

```bash
# Apply all pending migrations
python manage.py migrate

# Check migration status
python manage.py showmigrations
```

#### 2.3 Initialize Currencies

```bash
# Initialize 10 major currencies and sample exchange rates
python manage.py init_currencies
```

This command creates:
- 10 currencies (USD, EUR, GBP, JPY, ZMW, ZAR, CAD, AUD, INR, NGN)
- Sample exchange rates for all pairs
- Sample tax rates for major countries

#### 2.4 Verify Database

Check that tables were created:

```bash
python manage.py dbshell

# In PostgreSQL:
\dt currencies
\dt exchange_rates
\dt product_pricing
\dt tax_rates
\dt car_pricing
\dt currency_conversion_logs

# In SQLite:
.tables

# Check sample data
SELECT * FROM currencies LIMIT 5;
SELECT COUNT(*) FROM exchange_rates;
```

### Phase 3: Update Existing Data (2-3 hours)

#### 3.1 Create Base Currency Entries for Existing Products

Create a migration file:

```python
# ecom_backend/migrations/0001_create_product_pricing.py

from django.db import migrations
from decimal import Decimal

def create_product_pricing(apps, schema_editor):
    Product = apps.get_model('product_service', 'Product')
    ProductPricing = apps.get_model('ecom_backend', 'ProductPricing')
    Currency = apps.get_model('ecom_backend', 'Currency')
    
    usd = Currency.objects.get(code='USD')
    
    for product in Product.objects.all():
        ProductPricing.objects.get_or_create(
            product=product,
            currency=usd,
            defaults={
                'price': product.price,
                'compare_at_price': product.compare_at_price,
                'cost': product.cost_per_item,
                'is_base_currency': True,
            }
        )

def reverse_product_pricing(apps, schema_editor):
    ProductPricing = apps.get_model('ecom_backend', 'ProductPricing')
    ProductPricing.objects.all().delete()

class Migration(migrations.Migration):
    dependencies = [
        ('ecom_backend', '0001_initial_models'),
    ]

    operations = [
        migrations.RunPython(create_product_pricing, reverse_product_pricing),
    ]
```

Run the migration:

```bash
python manage.py migrate
```

#### 3.2 Create Currency Field for Existing Carts

```python
# ecom_backend/migrations/0002_cart_currency.py

from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ('order_service', 'previous_migration'),
    ]

    operations = [
        migrations.RunSQL(
            "UPDATE carts SET currency = 'USD' WHERE currency IS NULL;",
            migrations.RunSQL.noop
        ),
    ]
```

#### 3.3 Create Exchange Rate Entries for Existing Orders

Create a management command:

```python
# ecom_backend/management/commands/backfill_order_exchange_rates.py

from django.core.management.base import BaseCommand
from order_service.models import Order
from ecom_backend.multi_currency import ExchangeRate
from django.utils import timezone

class Command(BaseCommand):
    help = 'Backfill exchange rates for existing orders'

    def handle(self, *args, **options):
        today = timezone.now().date()
        orders_updated = 0
        
        for order in Order.objects.filter(exchange_rate_date__isnull=True):
            try:
                rate = ExchangeRate.objects.get(
                    from_currency__code=order.base_currency,
                    to_currency__code=order.currency,
                    rate_date=today
                )
                order.exchange_rate = rate.rate
                order.exchange_rate_date = today
                order.save()
                orders_updated += 1
            except ExchangeRate.DoesNotExist:
                # Use default 1:1 if not found
                order.exchange_rate = 1.0
                order.exchange_rate_date = today
                order.save()
                orders_updated += 1
        
        self.stdout.write(f'Updated {orders_updated} orders')
```

Run it:

```bash
python manage.py backfill_order_exchange_rates
```

### Phase 4: Testing (2-3 hours)

#### 4.1 Unit Tests

Create test file: `ecom_backend/tests/test_multi_currency.py`

```python
from django.test import TestCase
from decimal import Decimal
from ecom_backend.multi_currency import (
    Currency, ExchangeRate, ProductPricing, 
    CurrencyConverter
)
from ecom_backend.pricing_utils import PricingCalculator
from product_service.models import Product

class MultiCurrencyTests(TestCase):
    
    @classmethod
    def setUpTestData(cls):
        # Create test currencies
        cls.usd = Currency.objects.create(
            code='USD',
            name='US Dollar',
            symbol='$',
            is_default=True
        )
        cls.eur = Currency.objects.create(
            code='EUR',
            name='Euro',
            symbol='€'
        )
        
        # Create exchange rate
        ExchangeRate.objects.create(
            from_currency=cls.usd,
            to_currency=cls.eur,
            rate=Decimal('0.92'),
            rate_date='2024-01-15'
        )
    
    def test_currency_conversion(self):
        """Test currency conversion"""
        result = CurrencyConverter.convert(
            Decimal('100.00'),
            'USD',
            'EUR',
            '2024-01-15'
        )
        self.assertEqual(result, Decimal('92.00'))
    
    def test_product_pricing(self):
        """Test product pricing in different currencies"""
        # Create test product
        product = Product.objects.create(
            name='Test Product',
            price=Decimal('100.00'),
            base_currency='USD',
            vendor_id=1
        )
        
        # Get price in EUR
        pricing = product.get_price_for_currency('EUR')
        self.assertIsNotNone(pricing)
        self.assertEqual(pricing['currency'], 'EUR')

# Run tests
# python manage.py test ecom_backend.tests.test_multi_currency
```

#### 4.2 Integration Tests

```bash
# Test API endpoints
python manage.py test

# Test specific functionality
python manage.py test ecom_backend.tests.test_multi_currency.MultiCurrencyTests

# Run with verbose output
python manage.py test --verbosity=2
```

#### 4.3 Manual Testing

Test in Django shell:

```bash
python manage.py shell

# Test currency operations
from ecom_backend.multi_currency import Currency, CurrencyConverter
from decimal import Decimal

# Get all currencies
currencies = Currency.objects.all()
print(f"Found {currencies.count()} currencies")

# Test conversion
result = CurrencyConverter.convert(Decimal('100'), 'USD', 'EUR')
print(f"100 USD = {result} EUR")

# Test product pricing
from product_service.models import Product
product = Product.objects.first()
pricing = product.get_price_for_currency('EUR')
print(f"Product price: {pricing}")
```

### Phase 5: Configuration & Deployment (1-2 hours)

#### 5.1 Environment Variables

Create `.env` file:

```
# Multi-Currency
CURRENCY_API_PROVIDER=openexchangerates
CURRENCY_API_KEY=your_api_key_here
DEFAULT_CURRENCY=USD

# Database
DATABASE_URL=postgresql://user:password@localhost/ecommerce_db

# Redis
REDIS_URL=redis://localhost:6379/0

# API Settings
DEBUG=False
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=localhost,127.0.0.1,yourdomain.com
```

#### 5.2 Celery Tasks (for scheduled updates)

Add to `celery.py`:

```python
from celery import shared_task
from ecom_backend.multi_currency import CurrencyConverter
import logging

logger = logging.getLogger(__name__)

@shared_task
def update_exchange_rates():
    """Update exchange rates daily"""
    try:
        CurrencyConverter.update_exchange_rates_from_api()
        logger.info("Exchange rates updated successfully")
    except Exception as e:
        logger.error(f"Error updating exchange rates: {str(e)}")

@shared_task
def cleanup_old_conversion_logs():
    """Clean up conversion logs older than 90 days"""
    from ecom_backend.multi_currency import CurrencyConversionLog
    from datetime import timedelta
    from django.utils import timezone
    
    cutoff = timezone.now() - timedelta(days=90)
    deleted = CurrencyConversionLog.objects.filter(created_at__lt=cutoff).delete()
    logger.info(f"Deleted {deleted[0]} old conversion logs")
```

Add to `celery_beat_schedule`:

```python
CELERY_BEAT_SCHEDULE = {
    'update-exchange-rates': {
        'task': 'ecom_backend.tasks.update_exchange_rates',
        'schedule': crontab(hour=0, minute=0),  # Daily at midnight UTC
    },
    'cleanup-conversion-logs': {
        'task': 'ecom_backend.tasks.cleanup_old_conversion_logs',
        'schedule': crontab(0, 0, day_of_month=1),  # First day of month
    },
}
```

#### 5.3 Update GraphQL Schema

If using GraphQL, add to your main schema:

```python
# gateway_service/schema.py

import graphene
from ecom_backend.graphql_currency_schema import (
    CurrencyQuery,
    CurrencyMutation
)

class Query(CurrencyQuery, graphene.ObjectType):
    pass

class Mutation(CurrencyMutation, graphene.ObjectType):
    pass

schema = graphene.Schema(query=Query, mutation=Mutation)
```

#### 5.4 API Views (REST)

Create `ecom_backend/views.py`:

```python
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from decimal import Decimal

from .multi_currency import Currency, ExchangeRate, ProductPricing
from .serializers import (
    CurrencySerializer,
    ExchangeRateSerializer,
    ProductPricingSerializer
)

class CurrencyViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Currency.objects.filter(is_active=True)
    serializer_class = CurrencySerializer
    pagination_class = None
    
    @action(detail=False, methods=['post'])
    def update_rates(self, request):
        permission_classes = [IsAdminUser]
        from .multi_currency import CurrencyConverter
        
        try:
            CurrencyConverter.update_exchange_rates_from_api()
            return Response({'status': 'Exchange rates updated'})
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

class ExchangeRateViewSet(viewsets.ModelViewSet):
    queryset = ExchangeRate.objects.all()
    serializer_class = ExchangeRateSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        from_curr = self.request.query_params.get('from_currency')
        to_curr = self.request.query_params.get('to_currency')
        
        qs = super().get_queryset()
        if from_curr:
            qs = qs.filter(from_currency__code=from_curr)
        if to_curr:
            qs = qs.filter(to_currency__code=to_curr)
        return qs

class ProductPricingViewSet(viewsets.ModelViewSet):
    queryset = ProductPricing.objects.select_related('product', 'currency')
    serializer_class = ProductPricingSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        product_id = self.request.query_params.get('product')
        if product_id:
            return self.queryset.filter(product_id=product_id)
        return self.queryset
```

Create `ecom_backend/serializers.py`:

```python
from rest_framework import serializers
from .multi_currency import Currency, ExchangeRate, ProductPricing

class CurrencySerializer(serializers.ModelSerializer):
    class Meta:
        model = Currency
        fields = [
            'code', 'name', 'symbol', 'country',
            'decimal_places', 'symbol_position', 'is_default'
        ]

class ExchangeRateSerializer(serializers.ModelSerializer):
    from_currency = serializers.CharField(source='from_currency.code')
    to_currency = serializers.CharField(source='to_currency.code')
    
    class Meta:
        model = ExchangeRate
        fields = ['id', 'from_currency', 'to_currency', 'rate', 'rate_date', 'source']

class ProductPricingSerializer(serializers.ModelSerializer):
    currency = serializers.CharField(source='currency.code')
    discount_percentage = serializers.SerializerMethodField()
    
    class Meta:
        model = ProductPricing
        fields = [
            'id', 'product', 'currency', 'price',
            'compare_at_price', 'cost', 'discount_percentage',
            'is_custom_price', 'is_base_currency'
        ]
    
    def get_discount_percentage(self, obj):
        return obj.get_discount_percentage()
```

Register in `urls.py`:

```python
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CurrencyViewSet, ExchangeRateViewSet, ProductPricingViewSet

router = DefaultRouter()
router.register('currencies', CurrencyViewSet, basename='currency')
router.register('exchange-rates', ExchangeRateViewSet, basename='exchange-rate')
router.register('product-pricing', ProductPricingViewSet, basename='product-pricing')

urlpatterns = [
    path('api/v1/', include(router.urls)),
]
```

### Phase 6: Frontend Integration (2-3 hours)

#### 6.1 Currency Selector Component

```javascript
// React component
import React, { useState, useEffect } from 'react';

function CurrencySelector({ onCurrencyChange }) {
  const [currencies, setCurrencies] = useState([]);
  const [selected, setSelected] = useState('USD');

  useEffect(() => {
    fetch('/api/v1/currencies/')
      .then(res => res.json())
      .then(data => setCurrencies(data))
      .catch(err => console.error('Error fetching currencies:', err));
  }, []);

  const handleChange = (e) => {
    setSelected(e.target.value);
    onCurrencyChange(e.target.value);
  };

  return (
    <select value={selected} onChange={handleChange} className="currency-selector">
      {currencies.map(curr => (
        <option key={curr.code} value={curr.code}>
          {curr.code} - {curr.symbol}
        </option>
      ))}
    </select>
  );
}

export default CurrencySelector;
```

#### 6.2 Price Display Component

```javascript
// React component for displaying converted prices
function ProductPrice({ productId, currency }) {
  const [pricing, setPricing] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetch(`/api/v1/products/${productId}/price/?currency=${currency}`)
      .then(res => res.json())
      .then(data => setPricing(data))
      .catch(err => console.error('Price fetch error:', err))
      .finally(() => setLoading(false));
  }, [productId, currency]);

  if (loading) return <span>Loading...</span>;
  if (!pricing) return <span>N/A</span>;

  return (
    <div className="product-price">
      {pricing.compare_at_price && (
        <span className="original-price" style={{ textDecoration: 'line-through' }}>
          {pricing.currency} {pricing.compare_at_price}
        </span>
      )}
      <span className="sale-price">
        {pricing.currency} {pricing.price}
      </span>
      {pricing.discount_percentage > 0 && (
        <span className="discount-badge">
          Save {pricing.discount_percentage}%
        </span>
      )}
    </div>
  );
}

export default ProductPrice;
```

### Phase 7: Monitoring & Maintenance (Ongoing)

#### 7.1 Check Exchange Rates

```bash
# Check if today's rates exist
python manage.py shell
from ecom_backend.multi_currency import ExchangeRate
from django.utils import timezone
today = timezone.now().date()
rates = ExchangeRate.objects.filter(rate_date=today)
print(f"Rates for {today}: {rates.count()}")
```

#### 7.2 Monitor Errors

Check logs:

```bash
tail -f logs/currency.log
```

#### 7.3 Performance Monitoring

```python
from django.db import connection
from django.test.utils import override_settings

# Check query count
from django.conf import settings
if settings.DEBUG:
    print(f"Total queries: {len(connection.queries)}")
    for query in connection.queries[:5]:
        print(query)
```

## Troubleshooting

### Migration Errors

**Error:** `Migrate: Table 'currencies' doesn't exist`

**Solution:**
```bash
python manage.py migrate --app ecom_backend
```

### API Key Issues

**Error:** `CURRENCY_API_KEY` not found

**Solution:**
```bash
export CURRENCY_API_KEY='your_api_key'
python manage.py runserver
```

### Exchange Rate Not Found

**Error:** `ExchangeRate matching query does not exist`

**Solution:**
```bash
python manage.py init_currencies
python manage.py update_exchange_rates --provider=openexchangerates
```

### QuerySet Error

**Error:** `AttributeError: 'QuerySet' object has no attribute 'get_price'`

**Solution:**
```python
# Make sure select_related is used
from product_service.models import Product
product = Product.objects.select_related('vendor').get(id=1)
```

## Checklist

- [ ] Copy all Python files to project
- [ ] Update `settings.py` with multi-currency configuration
- [ ] Create migrations: `python manage.py makemigrations`
- [ ] Apply migrations: `python manage.py migrate`
- [ ] Initialize currencies: `python manage.py init_currencies`
- [ ] Create backfill migrations for existing data
- [ ] Run unit tests: `python manage.py test`
- [ ] Configure Celery tasks for scheduled updates
- [ ] Update API routes (if using REST)
- [ ] Update GraphQL schema (if using GraphQL)
- [ ] Create frontend components
- [ ] Test in staging environment
- [ ] Deploy to production
- [ ] Monitor exchange rate updates
- [ ] Set up alerts for API failures

## Expected Outcome

After completing all phases:

✅ Multi-currency system fully integrated
✅ Products priced in multiple currencies
✅ Automatic currency conversion
✅ Tax calculations by region
✅ Customer currency preferences
✅ Order history with exchange rates
✅ GraphQL & REST API support
✅ Scheduled exchange rate updates
✅ Comprehensive logging & monitoring
✅ Ready for international expansion
