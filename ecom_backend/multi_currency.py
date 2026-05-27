"""
Currency Management Models & Utilities
Handles multi-currency support for the e-commerce platform
"""

from django.db import models
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from decimal import Decimal
import requests
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class Currency(models.Model):
    """Supported currencies in the system"""
    
    code = models.CharField(
        max_length=3,
        unique=True,
        primary_key=True,
        help_text="ISO 4217 currency code (e.g., USD, ZMW, GBP)"
    )
    name = models.CharField(max_length=100)
    symbol = models.CharField(max_length=10)
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    
    # Regional configuration
    country = models.CharField(max_length=100, blank=True)
    decimal_places = models.IntegerField(default=2)
    
    # Formatting
    symbol_position = models.CharField(
        max_length=10,
        choices=[('before', 'Before Amount'), ('after', 'After Amount')],
        default='before'
    )
    thousands_separator = models.CharField(max_length=1, default=',')
    decimal_separator = models.CharField(max_length=1, default='.')
    
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'currencies'
        verbose_name_plural = 'currencies'
        ordering = ['code']
    
    def __str__(self):
        return f"{self.code} - {self.name}"
    
    def format_amount(self, amount: Decimal) -> str:
        """Format amount according to currency settings"""
        formatted = f"{amount:,.{self.decimal_places}f}"
        formatted = formatted.replace(',', '|').replace(self.thousands_separator if self.thousands_separator != ',' else '|', self.thousands_separator)
        formatted = formatted.replace('|', 'TEMP').replace(self.decimal_separator if self.decimal_separator != '.' else '.', self.decimal_separator).replace('TEMP', self.thousands_separator)
        
        if self.symbol_position == 'before':
            return f"{self.symbol}{formatted}"
        else:
            return f"{formatted} {self.symbol}"


class ExchangeRate(models.Model):
    """Daily exchange rates between currencies"""
    
    from_currency = models.ForeignKey(
        Currency,
        on_delete=models.CASCADE,
        related_name='outgoing_rates'
    )
    to_currency = models.ForeignKey(
        Currency,
        on_delete=models.CASCADE,
        related_name='incoming_rates'
    )
    rate = models.DecimalField(max_digits=20, decimal_places=8)
    rate_date = models.DateField()
    source = models.CharField(
        max_length=50,
        choices=[
            ('fixer', 'Fixer.io'),
            ('openexchangerates', 'Open Exchange Rates'),
            ('exchangerateapi', 'Exchange Rate API'),
            ('manual', 'Manual Entry'),
            ('ecb', 'European Central Bank'),
        ],
        default='manual'
    )
    
    class Meta:
        db_table = 'exchange_rates'
        unique_together = [['from_currency', 'to_currency', 'rate_date']]
        indexes = [
            models.Index(fields=['from_currency', 'to_currency', 'rate_date']),
        ]
    
    def __str__(self):
        return f"{self.from_currency} to {self.to_currency} = {self.rate}"
    
    @classmethod
    def get_rate(cls, from_currency: str, to_currency: str, date: Optional[str] = None):
        """Get exchange rate for currency pair"""
        if from_currency == to_currency:
            return Decimal('1.0')
        
        if date is None:
            date = timezone.now().date()
        
        # Try cache first
        cache_key = f"exchange_rate_{from_currency}_{to_currency}_{date}"
        cached_rate = cache.get(cache_key)
        if cached_rate:
            return Decimal(str(cached_rate))
        
        # Get from database
        try:
            exchange_rate = cls.objects.get(
                from_currency=from_currency,
                to_currency=to_currency,
                rate_date=date
            )
            # Cache for 24 hours
            cache.set(cache_key, float(exchange_rate.rate), 86400)
            return exchange_rate.rate
        except cls.DoesNotExist:
            logger.warning(f"Exchange rate not found: {from_currency} to {to_currency} on {date}")
            return None


class ProductPricing(models.Model):
    """Price of a product in different currencies"""
    
    product = models.ForeignKey(
        'product_service.Product',
        on_delete=models.CASCADE,
        related_name='currency_prices'
    )
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    compare_at_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Original price before discount"
    )
    cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Cost price in this currency"
    )
    is_base_currency = models.BooleanField(
        default=False,
        help_text="Mark if this is the base currency for the product"
    )
    is_active = models.BooleanField(default=True)
    
    # Manual override flag
    is_custom_price = models.BooleanField(
        default=False,
        help_text="If True, price is manually set and won't be auto-converted"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'product_pricing'
        unique_together = [['product', 'currency']]
        indexes = [
            models.Index(fields=['product', 'currency']),
            models.Index(fields=['product', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.product.name} - {self.currency.code}: {self.price}"
    
    def get_discount_percentage(self) -> Decimal:
        """Get discount percentage if compare_at_price is set"""
        if self.compare_at_price and self.compare_at_price > self.price:
            discount = ((self.compare_at_price - self.price) / self.compare_at_price) * 100
            return Decimal(str(discount)).quantize(Decimal('0.01'))
        return Decimal('0')


class TaxRate(models.Model):
    """Tax rates per country and currency"""
    
    country_code = models.CharField(max_length=2)
    state_province = models.CharField(max_length=100, blank=True)
    tax_type = models.CharField(
        max_length=20,
        choices=[
            ('vat', 'VAT'),
            ('gst', 'GST'),
            ('sales_tax', 'Sales Tax'),
            ('other', 'Other'),
        ]
    )
    rate = models.DecimalField(max_digits=5, decimal_places=2)
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT)
    is_active = models.BooleanField(default=True)
    applies_to_shipping = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'tax_rates'
        unique_together = [['country_code', 'state_province', 'tax_type', 'currency']]
    
    def __str__(self):
        return f"{self.country_code} {self.tax_type}: {self.rate}%"


class CartPricing(models.Model):
    """Cart with multi-currency support"""
    
    cart_id = models.CharField(max_length=100, unique=True)
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='carts'
    )
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT)
    
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    shipping_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    coupon_code = models.CharField(max_length=50, blank=True)
    notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField()
    
    class Meta:
        db_table = 'cart_pricing'
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"Cart {self.cart_id} ({self.currency.code})"
    
    def recalculate_totals(self):
        """Recalculate cart totals"""
        items = self.items.select_related('product__vendor')
        
        self.subtotal = sum(item.get_total_price() for item in items)
        self.tax_amount = self._calculate_tax()
        self.total = self.subtotal + self.tax_amount + self.shipping_amount - self.discount_amount
        self.save()
    
    def _calculate_tax(self) -> Decimal:
        """Calculate tax based on currency and customer location"""
        # This will be implemented based on your tax requirements
        return Decimal('0.00')


class CartItem(models.Model):
    """Items in a cart"""
    
    cart = models.ForeignKey(CartPricing, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('product_service.Product', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    total_price = models.DecimalField(max_digits=12, decimal_places=2)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'cart_items'
        unique_together = [['cart', 'product']]
    
    def get_total_price(self) -> Decimal:
        """Calculate total price for this item"""
        return self.unit_price * self.quantity


class CurrencyConversionLog(models.Model):
    """Log all currency conversions for audit trail"""
    
    from_currency = models.CharField(max_length=3)
    to_currency = models.CharField(max_length=3)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    converted_amount = models.DecimalField(max_digits=12, decimal_places=2)
    exchange_rate = models.DecimalField(max_digits=20, decimal_places=8)
    
    reference_type = models.CharField(max_length=50)  # 'order', 'cart', 'payment'
    reference_id = models.CharField(max_length=100)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'currency_conversion_logs'
        indexes = [
            models.Index(fields=['reference_type', 'reference_id']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.amount} {self.from_currency} = {self.converted_amount} {self.to_currency}"


# ============================================================================
# UTILITY FUNCTIONS FOR CURRENCY CONVERSION
# ============================================================================

class CurrencyConverter:
    """Handles currency conversion with exchange rates"""
    
    @staticmethod
    def convert(
        amount: Decimal,
        from_currency: str,
        to_currency: str,
        use_date=None
    ) -> Optional[Decimal]:
        """Convert amount from one currency to another"""
        
        if from_currency == to_currency:
            return amount
        
        exchange_rate = ExchangeRate.get_rate(from_currency, to_currency, use_date)
        
        if exchange_rate is None:
            return None
        
        converted = amount * exchange_rate
        return converted.quantize(Decimal('0.01'))
    
    @staticmethod
    def get_available_currencies() -> list:
        """Get all active currencies"""
        return Currency.objects.filter(is_active=True).order_by('code')
    
    @staticmethod
    def get_default_currency() -> Optional[Currency]:
        """Get the default currency"""
        return Currency.objects.filter(is_default=True, is_active=True).first()
    
    @staticmethod
    def update_exchange_rates_from_api():
        """Fetch and update exchange rates from external API"""
        try:
            from django.conf import settings
            
            api_provider = getattr(settings, 'CURRENCY_API_PROVIDER', 'openexchangerates')
            api_key = getattr(settings, 'CURRENCY_API_KEY', '')
            
            if api_provider == 'openexchangerates':
                CurrencyConverter._update_from_open_exchange_rates(api_key)
            elif api_provider == 'fixer':
                CurrencyConverter._update_from_fixer(api_key)
            else:
                logger.warning(f"Unknown currency API provider: {api_provider}")
        
        except Exception as e:
            logger.error(f"Error updating exchange rates: {str(e)}")
    
    @staticmethod
    def _update_from_open_exchange_rates(api_key: str):
        """Update rates from Open Exchange Rates API"""
        url = f"https://openexchangerates.org/api/latest.json?app_id={api_key}"
        
        try:
            response = requests.get(url, timeout=10)
            data = response.json()
            
            base_currency = data['base']
            timestamp = data['timestamp']
            
            for currency_code, rate in data['rates'].items():
                ExchangeRate.objects.update_or_create(
                    from_currency=base_currency,
                    to_currency=currency_code,
                    rate_date=timezone.now().date(),
                    defaults={
                        'rate': Decimal(str(rate)),
                        'source': 'openexchangerates'
                    }
                )
            
            logger.info("Exchange rates updated successfully from Open Exchange Rates")
        
        except Exception as e:
            logger.error(f"Error fetching rates from Open Exchange Rates: {str(e)}")
    
    @staticmethod
    def _update_from_fixer(api_key: str):
        """Update rates from Fixer API"""
        url = f"https://api.fixer.io/latest?access_key={api_key}"
        
        try:
            response = requests.get(url, timeout=10)
            data = response.json()
            
            if not data.get('success', False):
                logger.error(f"Fixer API error: {data.get('error', {}).get('info')}")
                return
            
            base_currency = data['base']
            
            for currency_code, rate in data['rates'].items():
                ExchangeRate.objects.update_or_create(
                    from_currency=base_currency,
                    to_currency=currency_code,
                    rate_date=timezone.now().date(),
                    defaults={
                        'rate': Decimal(str(rate)),
                        'source': 'fixer'
                    }
                )
            
            logger.info("Exchange rates updated successfully from Fixer")
        
        except Exception as e:
            logger.error(f"Error fetching rates from Fixer: {str(e)}")
