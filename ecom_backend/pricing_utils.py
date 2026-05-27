"""
Price Calculation and Currency Conversion Utilities
"""

from decimal import Decimal
from typing import Dict, Optional, Tuple
from django.core.cache import cache
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class PricingCalculator:
    """Calculates prices with currency conversion and tax"""
    
    @staticmethod
    def get_product_price_in_currency(
        product,
        target_currency: str,
        customer=None
    ) -> Optional[Dict]:
        """Get product price converted to target currency"""
        try:
            from .multi_currency import ProductPricing, CurrencyConverter, Currency
            
            # Try to get pricing for target currency
            pricing = ProductPricing.objects.filter(
                product=product,
                currency__code=target_currency,
                is_active=True
            ).first()
            
            if pricing:
                return {
                    'price': pricing.price,
                    'compare_at_price': pricing.compare_at_price,
                    'cost': pricing.cost,
                    'currency': target_currency,
                    'discount_percentage': pricing.get_discount_percentage(),
                    'is_custom_price': pricing.is_custom_price,
                }
            
            # If not found, convert from base currency
            base_pricing = ProductPricing.objects.filter(
                product=product,
                is_base_currency=True,
                is_active=True
            ).first()
            
            if not base_pricing:
                # Fall back to product.price (if not overridden by ProductPricing)
                default_currency = Currency.objects.filter(is_default=True).first()
                if not default_currency:
                    default_currency = Currency.objects.filter(code='USD').first()
                
                base_currency = default_currency.code if default_currency else 'USD'
            else:
                base_currency = base_pricing.currency.code
            
            if base_currency == target_currency:
                if base_pricing:
                    return {
                        'price': base_pricing.price,
                        'compare_at_price': base_pricing.compare_at_price,
                        'cost': base_pricing.cost,
                        'currency': target_currency,
                        'discount_percentage': base_pricing.get_discount_percentage(),
                        'is_custom_price': base_pricing.is_custom_price,
                    }
                else:
                    return {
                        'price': product.price,
                        'compare_at_price': product.compare_at_price,
                        'cost': product.cost_per_item,
                        'currency': target_currency,
                        'discount_percentage': Decimal('0'),
                        'is_custom_price': False,
                    }
            
            # Convert price
            base_price = base_pricing.price if base_pricing else product.price
            converted_price = CurrencyConverter.convert(
                base_price,
                base_currency,
                target_currency
            )
            
            if not converted_price:
                return None
            
            # Convert compare_at_price
            compare_at = base_pricing.compare_at_price if base_pricing else product.compare_at_price
            converted_compare_at = None
            if compare_at:
                converted_compare_at = CurrencyConverter.convert(
                    compare_at,
                    base_currency,
                    target_currency
                )
            
            # Convert cost
            cost = base_pricing.cost if base_pricing else product.cost_per_item
            converted_cost = None
            if cost:
                converted_cost = CurrencyConverter.convert(
                    cost,
                    base_currency,
                    target_currency
                )
            
            # Calculate discount percentage
            discount_pct = Decimal('0')
            if converted_compare_at and converted_compare_at > converted_price:
                discount_pct = ((converted_compare_at - converted_price) / converted_compare_at) * 100
                discount_pct = discount_pct.quantize(Decimal('0.01'))
            
            return {
                'price': converted_price,
                'compare_at_price': converted_compare_at,
                'cost': converted_cost,
                'currency': target_currency,
                'discount_percentage': discount_pct,
                'is_custom_price': False,
            }
        
        except Exception as e:
            logger.error(f"Error calculating product price: {str(e)}")
            return None
    
    @staticmethod
    def calculate_order_total(
        items: list,
        currency: str,
        tax_rate: Decimal = Decimal('0'),
        shipping_amount: Decimal = Decimal('0'),
        discount_amount: Decimal = Decimal('0')
    ) -> Dict:
        """Calculate order total with all components"""
        
        subtotal = Decimal('0')
        for item in items:
            subtotal += item['price'] * item['quantity']
        
        tax = (subtotal * tax_rate / 100).quantize(Decimal('0.01'))
        total = subtotal + tax + shipping_amount - discount_amount
        
        return {
            'subtotal': subtotal,
            'tax_amount': tax,
            'shipping_amount': shipping_amount,
            'discount_amount': discount_amount,
            'total': total,
            'currency': currency,
        }
    
    @staticmethod
    def get_customer_preferred_currency(customer) -> str:
        """Get customer's preferred currency"""
        try:
            from .multi_currency import Currency
            
            # Check if customer has saved preference
            if hasattr(customer, 'currency_preference'):
                return customer.currency_preference
            
            # Try to detect from customer profile
            if hasattr(customer, 'profile') and hasattr(customer.profile, 'currency'):
                return customer.profile.currency
            
            # Use default currency
            default = Currency.objects.filter(is_default=True, is_active=True).first()
            return default.code if default else 'USD'
        
        except Exception as e:
            logger.error(f"Error getting customer currency: {str(e)}")
            return 'USD'
    
    @staticmethod
    def format_price(
        amount: Decimal,
        currency_code: str
    ) -> str:
        """Format price with currency symbol and locale"""
        try:
            from .multi_currency import Currency
            
            currency = Currency.objects.get(code=currency_code)
            return currency.format_amount(amount)
        
        except Exception as e:
            logger.error(f"Error formatting price: {str(e)}")
            return f"{currency_code} {amount}"


class TaxCalculator:
    """Calculates taxes based on location and currency"""
    
    @staticmethod
    def get_tax_rate(
        country_code: str,
        state: str = '',
        currency: str = 'USD'
    ) -> Optional[Decimal]:
        """Get tax rate for location"""
        try:
            from .multi_currency import TaxRate
            
            # Try state-specific first
            if state:
                tax_rate = TaxRate.objects.filter(
                    country_code=country_code,
                    state_province=state,
                    currency__code=currency,
                    is_active=True
                ).first()
                
                if tax_rate:
                    return tax_rate.rate
            
            # Fall back to country level
            tax_rate = TaxRate.objects.filter(
                country_code=country_code,
                state_province='',
                currency__code=currency,
                is_active=True
            ).first()
            
            if tax_rate:
                return tax_rate.rate
            
            return Decimal('0')
        
        except Exception as e:
            logger.error(f"Error getting tax rate: {str(e)}")
            return Decimal('0')
    
    @staticmethod
    def calculate_tax(
        subtotal: Decimal,
        country_code: str,
        state: str = '',
        currency: str = 'USD',
        include_shipping: bool = False,
        shipping_amount: Decimal = Decimal('0')
    ) -> Decimal:
        """Calculate tax amount"""
        
        tax_rate = TaxCalculator.get_tax_rate(country_code, state, currency)
        
        taxable_amount = subtotal
        if include_shipping:
            taxable_amount += shipping_amount
        
        tax_amount = (taxable_amount * tax_rate / 100).quantize(Decimal('0.01'))
        return tax_amount


class ShippingPricingCalculator:
    """Calculates shipping costs with currency conversion"""
    
    @staticmethod
    def get_shipping_cost(
        origin_country: str,
        destination_country: str,
        weight: Decimal,
        currency: str = 'USD'
    ) -> Optional[Dict]:
        """Get shipping cost for route and weight"""
        try:
            from .multi_currency import CurrencyConverter
            
            # This would typically query a shipping provider API
            # For now, return a placeholder structure
            
            base_cost = Decimal('10.00')  # Example base cost
            
            # Convert if needed
            if currency != 'USD':
                converted_cost = CurrencyConverter.convert(
                    base_cost,
                    'USD',
                    currency
                )
            else:
                converted_cost = base_cost
            
            return {
                'cost': converted_cost,
                'currency': currency,
                'estimated_days': 3,
                'method': 'STANDARD',
            }
        
        except Exception as e:
            logger.error(f"Error calculating shipping: {str(e)}")
            return None


class DiscountCalculator:
    """Handles discount calculations in multiple currencies"""
    
    @staticmethod
    def apply_coupon(
        subtotal: Decimal,
        coupon_code: str,
        currency: str = 'USD'
    ) -> Tuple[Decimal, str]:
        """Apply coupon to subtotal"""
        try:
            # This would query CouponCode model
            # For now, return no discount
            
            return subtotal, ''
        
        except Exception as e:
            logger.error(f"Error applying coupon: {str(e)}")
            return subtotal, ''
    
    @staticmethod
    def get_volume_discount(
        quantity: int,
        unit_price: Decimal,
        currency: str = 'USD'
    ) -> Decimal:
        """Get discount based on quantity"""
        
        if quantity >= 100:
            return (unit_price * Decimal('0.20')).quantize(Decimal('0.01'))  # 20% discount
        elif quantity >= 50:
            return (unit_price * Decimal('0.15')).quantize(Decimal('0.01'))  # 15% discount
        elif quantity >= 10:
            return (unit_price * Decimal('0.10')).quantize(Decimal('0.01'))  # 10% discount
        
        return Decimal('0')
