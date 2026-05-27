# Multi-Currency Support Implementation Guide

## Overview

This implementation adds comprehensive multi-currency support to the e-commerce system, allowing customers in different regions to view prices in their preferred currencies with automatic conversion and proper tax calculations.

## Architecture

### Key Components

1. **Currency Models** (`ecom_backend/multi_currency.py`)
   - `Currency`: Defines supported currencies with formatting rules
   - `ExchangeRate`: Stores daily exchange rates between currency pairs
   - `ProductPricing`: Stores price of products in multiple currencies
   - `TaxRate`: Stores tax rates per country/region and currency
   - `CartPricing`: Shopping cart with currency-aware pricing
   - `CurrencyConversionLog`: Audit trail for all conversions

2. **Pricing Utilities** (`ecom_backend/pricing_utils.py`)
   - `PricingCalculator`: Converts product prices between currencies
   - `TaxCalculator`: Calculates taxes based on location and currency
   - `ShippingPricingCalculator`: Handles shipping costs in different currencies
   - `DiscountCalculator`: Applies discounts in specified currency

3. **Updated Models**
   - `Product`: Now has `base_currency` field for multi-currency pricing
   - `Order`: Enhanced with `exchange_rate` tracking for historical accuracy
   - `Cart`: Now accepts currency selection
   - `CartItem`: Supports cached pricing in cart's currency

## Setup Instructions

### 1. Create and Apply Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### 2. Initialize Currencies and Exchange Rates

```bash
python manage.py init_currencies
```

This command:
- Creates 10 major world currencies (USD, EUR, GBP, JPY, ZMW, ZAR, CAD, AUD, INR, NGN)
- Sets up sample exchange rates
- Creates sample tax rates for various countries

### 3. Configure Currency Settings

Add to `settings.py`:

```python
# Multi-Currency Configuration
CURRENCIES_ENABLED = True
DEFAULT_CURRENCY = 'USD'
CURRENCY_API_PROVIDER = 'openexchangerates'  # or 'fixer'
CURRENCY_API_KEY = 'your-api-key-here'

# Cache exchange rates for 24 hours
CURRENCY_CACHE_TIMEOUT = 86400

# Supported currencies
SUPPORTED_CURRENCIES = [
    'USD', 'EUR', 'GBP', 'JPY', 'ZMW', 'ZAR',
    'CAD', 'AUD', 'INR', 'NGN'
]
```

## Usage Examples

### Getting Product Price in Different Currency

```python
from product_service.models import Product
from ecom_backend.pricing_utils import PricingCalculator

product = Product.objects.get(id=1)

# Get price in EUR (auto-converts from base currency)
price_data = product.get_price_for_currency('EUR')
print(f"EUR {price_data['price']}")  # EUR 92.00
```

### Creating Multi-Currency Pricing

```python
from product_service.models import Product

product = Product.objects.get(id=1)

# Create pricing for specific currency
pricing, created = product.create_currency_pricing(
    currency_code='GBP',
    price=Decimal('79.99'),
    compare_at_price=Decimal('99.99'),
    cost=Decimal('40.00')
)
```

### Creating an Order with Currency Conversion

```python
from order_service.models import Order
from ecom_backend.pricing_utils import PricingCalculator, TaxCalculator

order = Order.objects.create(
    order_number='ORD-001',
    customer=customer,
    subtotal=Decimal('100.00'),
    shipping_amount=Decimal('10.00'),
    currency='EUR',
    base_currency='USD'
)

# Set currency with automatic exchange rate lookup
order.set_currency('EUR')

# Calculate and apply tax
tax_amount = TaxCalculator.calculate_tax(
    order.subtotal,
    country_code='DE',
    currency='EUR'
)
order.tax_amount = tax_amount

# Calculate total
order.calculate_total()
order.save()
```

### Shopping Cart with Currency Selection

```python
from order_service.models import Cart, CartItem

# Create cart for customer in EUR
cart = Cart.objects.create(
    customer=customer,
    currency='EUR'
)

# Add product to cart
cart_item = CartItem.objects.create(
    cart=cart,
    product=product,
    quantity=2
)

# Update prices for cart currency
cart_item.update_price_for_currency()

# Get total in EUR
print(f"Cart total: {cart.total} EUR")
```

### Currency Conversion

```python
from ecom_backend.multi_currency import CurrencyConverter
from decimal import Decimal

# Convert amount
amount = Decimal('100.00')
converted = CurrencyConverter.convert(amount, 'USD', 'EUR')
print(f"{amount} USD = {converted} EUR")
```

### Tax Calculation

```python
from ecom_backend.pricing_utils import TaxCalculator
from decimal import Decimal

# Get tax rate for location
tax_rate = TaxCalculator.get_tax_rate('US', 'CA', 'USD')
print(f"California sales tax: {tax_rate}%")

# Calculate tax amount
subtotal = Decimal('100.00')
tax = TaxCalculator.calculate_tax(subtotal, 'US', 'CA', 'USD')
print(f"Tax: {tax}")
```

## Exchange Rate Management

### Manual Exchange Rate Entry

```python
from decimal import Decimal
from ecom_backend.multi_currency import ExchangeRate, Currency

usd = Currency.objects.get(code='USD')
eur = Currency.objects.get(code='EUR')

rate = ExchangeRate.objects.create(
    from_currency=usd,
    to_currency=eur,
    rate=Decimal('0.92'),
    rate_date='2024-01-15',
    source='manual'
)
```

### Auto-Update from API

```bash
# Update from Open Exchange Rates API
python manage.py update_exchange_rates --provider=openexchangerates

# Update from Fixer.io API
python manage.py update_exchange_rates --provider=fixer
```

## Database Schema

### Key Tables

```
currencies
├── code (PK)
├── name
├── symbol
├── country
├── decimal_places
└── formatting options

exchange_rates
├── id (PK)
├── from_currency (FK)
├── to_currency (FK)
├── rate
├── rate_date
└── source

product_pricing
├── id (PK)
├── product (FK)
├── currency (FK)
├── price
├── compare_at_price
├── cost
└── is_base_currency

tax_rates
├── id (PK)
├── country_code
├── state_province
├── tax_type
├── rate
└── currency (FK)

orders (modified)
├── id
├── currency (NEW)
├── base_currency (NEW)
├── exchange_rate (NEW)
├── exchange_rate_date (NEW)
└── ... other fields

carts (modified)
├── id
├── currency (NEW)
└── ... other fields
```

## API Integration

### Supported Exchange Rate Providers

1. **Open Exchange Rates** (recommended)
   - Website: https://openexchangerates.org/
   - Free tier: 1,000 requests/month
   - Setup: Add `CURRENCY_API_KEY` to settings

2. **Fixer.io**
   - Website: https://fixer.io/
   - Free tier: 100 requests/month
   - Setup: Add `CURRENCY_API_KEY` to settings

### Example: Scheduled Exchange Rate Updates

Add to `celery.py`:

```python
from celery import shared_task
from ecom_backend.multi_currency import CurrencyConverter

@shared_task
def update_exchange_rates():
    """Update exchange rates daily"""
    CurrencyConverter.update_exchange_rates_from_api()
```

Add to beat schedule:

```python
CELERY_BEAT_SCHEDULE = {
    'update-exchange-rates': {
        'task': 'ecom_backend.tasks.update_exchange_rates',
        'schedule': crontab(hour=0, minute=0),  # Daily at midnight
    },
}
```

## Frontend Integration

### Currency Selector Component

```javascript
// React example
function CurrencySelector({ onSelect }) {
  const [currencies, setCurrencies] = useState([]);

  useEffect(() => {
    fetch('/api/currencies/')
      .then(res => res.json())
      .then(data => setCurrencies(data));
  }, []);

  return (
    <select onChange={(e) => onSelect(e.target.value)}>
      <option value="">Select Currency</option>
      {currencies.map(curr => (
        <option key={curr.code} value={curr.code}>
          {curr.code} - {curr.symbol}
        </option>
      ))}
    </select>
  );
}
```

### Price Display Component

```javascript
// Display product price with converter
function ProductPrice({ product, currency }) {
  const [price, setPrice] = useState(null);

  useEffect(() => {
    fetch(`/api/products/${product.id}/price/?currency=${currency}`)
      .then(res => res.json())
      .then(data => setPrice(data));
  }, [product, currency]);

  if (!price) return <span>Loading...</span>;

  return (
    <div>
      <span className="discount" style={{ textDecoration: 'line-through' }}>
        {currency} {price.compare_at_price}
      </span>
      <span className="price">
        {currency} {price.price}
      </span>
      {price.discount_percentage > 0 && (
        <span className="discount-badge">
          Save {price.discount_percentage}%
        </span>
      )}
    </div>
  );
}
```

## Caching Strategy

All exchange rates are cached for 24 hours:

```python
from django.core.cache import cache

# Cache key format: exchange_rate_FROM_TO_DATE
cache_key = f"exchange_rate_USD_EUR_2024-01-15"
cached_rate = cache.get(cache_key)
```

Clear cache when needed:

```python
from django.core.cache import cache

cache.delete_many(cache.keys('exchange_rate_*'))
```

## Error Handling

```python
from ecom_backend.multi_currency import CurrencyConverter

try:
    converted_price = CurrencyConverter.convert(
        Decimal('100.00'),
        'USD',
        'EUR'
    )
    
    if converted_price is None:
        # Exchange rate not available
        raise ValueError("Exchange rate not found")
        
except Exception as e:
    logger.error(f"Currency conversion failed: {str(e)}")
    # Fall back to default currency
    return None
```

## Best Practices

1. **Always Use Decimal for Money**
   ```python
   from decimal import Decimal
   price = Decimal('99.99')  # Good
   price = 99.99  # Bad - floating point precision issues
   ```

2. **Lock Exchange Rates in Orders**
   - Never recalculate order amounts using current rates
   - Store the exchange rate used at order time
   - This ensures historical accuracy and tax calculations

3. **Cache Exchange Rates**
   - Use 24-hour caching for exchange rates
   - Refresh daily at off-peak hours
   - Implement fallback to last known rate if API fails

4. **Tax Compliance**
   - Calculate tax based on shipping address
   - Include shipping in taxable amount if applicable
   - Store tax calculation method for audit trail

5. **Regional Pricing**
   - Use ProductPricing model for region-specific pricing
   - Mark is_custom_price=True for manually set prices
   - Implement vendor approval workflow for regional prices

## Monitoring and Debugging

### Check Currency Configuration

```python
from ecom_backend.multi_currency import Currency

# List all active currencies
currencies = Currency.objects.filter(is_active=True)
for curr in currencies:
    print(f"{curr.code}: {curr.name}")
```

### Verify Exchange Rates

```python
from ecom_backend.multi_currency import ExchangeRate
from django.utils import timezone

today = timezone.now().date()
rates = ExchangeRate.objects.filter(rate_date=today)
print(f"Found {rates.count()} exchange rates for {today}")
```

### Debug Price Conversion

```python
from ecom_backend.pricing_utils import PricingCalculator

pricing = PricingCalculator.get_product_price_in_currency(product, 'EUR')
print(f"Debug: {pricing}")
# {
#   'price': Decimal('92.00'),
#   'consider_at_price': Decimal('120.00'),
#   'currency': 'EUR',
#   'discount_percentage': Decimal('23.33'),
#   'is_custom_price': False
# }
```

## Troubleshooting

### Exchange Rate Not Found

**Error:** `ExchangeRate matching query does not exist`

**Solution:**
```bash
# Initialize rates
python manage.py init_currencies

# Or manually create rate
python manage.py shell
>>> from ecom_backend.multi_currency import Currency, ExchangeRate
>>> from decimal import Decimal
>>> usd = Currency.objects.get(code='USD')
>>> eur = Currency.objects.get(code='EUR')
>>> ExchangeRate.objects.create(
...     from_currency=usd,
...     to_currency=eur,
...     rate=Decimal('0.92'),
...     rate_date=date.today()
... )
```

### Currency Not Found

**Error:** `Currency matching query does not exist`

**Solution:**
```bash
python manage.py init_currencies
```

### Conversion Returns None

**Solution:**
- Check if exchange rate exists for the date
- Verify both currencies are active
- Check cache for stale data

## Performance Considerations

1. **Index on Frequently Queried Fields**
   ```python
   # Indexes created on:
   - exchange_rates: (from_currency, to_currency, rate_date)
   - product_pricing: (product, currency), (product, is_active)
   - tax_rates: (country_code, state_province, currency)
   ```

2. **Query Optimization**
   ```python
   # Use select_related for foreign keys
   orders = Order.objects.select_related('customer').filter(status='pending')
   
   # Use prefetch_related for reverse relations
   products = Product.objects.prefetch_related('currency_prices')
   ```

3. **Cache Strategy**
   - Exchange rates: 24 hours
   - Currency list: 1 hour
   - Tax rates: 24 hours
   - Conversion results: 1 hour

## Testing

```python
from django.test import TestCase
from decimal import Decimal
from ecom_backend.multi_currency import Currency, ExchangeRate, CurrencyConverter

class MultiCurrencyTests(TestCase):
    def setUp(self):
        self.usd = Currency.objects.create(code='USD', name='US Dollar', symbol='$')
        self.eur = Currency.objects.create(code='EUR', name='Euro', symbol='€')
        
        ExchangeRate.objects.create(
            from_currency=self.usd,
            to_currency=self.eur,
            rate=Decimal('0.92'),
            rate_date='2024-01-15'
        )
    
    def test_currency_conversion(self):
        result = CurrencyConverter.convert(
            Decimal('100.00'),
            'USD',
            'EUR',
            '2024-01-15'
        )
        self.assertEqual(result, Decimal('92.00'))
```

## Support and Maintenance

- Monitor exchange rate updates for failures
- Review currency conversion logs quarterly
- Update tax rates when regulations change
- Regular backup of multi_currency tables
- Monitor exchange rate API service status

## Related Documentation

- [Product Service Documentation](../product_service/README.md)
- [Order Service Documentation](../order_service/README.md)
- [Payment Service Documentation](../payment_service/README.md)
- [Django Multi-language Support](https://docs.djangoproject.com/en/stable/topics/i18n/)
