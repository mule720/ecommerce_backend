"""
GraphQL Schema Extensions for Multi-Currency Support
Extends existing GraphQL schema with currency conversion and pricing queries
"""

import graphene
from decimal import Decimal
from django.utils import timezone
from ecom_backend.multi_currency import (
    Currency,
    ExchangeRate,
    ProductPricing,
    TaxRate,
    CartPricing
)
from ecom_backend.pricing_utils import (
    PricingCalculator,
    TaxCalculator,
    CurrencyConverter
)


# ============================================================================
# TYPES
# ============================================================================

class CurrencyType(graphene.ObjectType):
    """GraphQL type for Currency"""
    code = graphene.String(required=True)
    name = graphene.String(required=True)
    symbol = graphene.String(required=True)
    country = graphene.String()
    decimal_places = graphene.Int()
    symbol_position = graphene.String()
    is_active = graphene.Boolean()
    is_default = graphene.Boolean()
    
    @staticmethod
    def resolve_is_active(obj, info):
        return obj.is_active if hasattr(obj, 'is_active') else True


class ExchangeRateType(graphene.ObjectType):
    """GraphQL type for Exchange Rate"""
    id = graphene.Int()
    from_currency = graphene.String()
    to_currency = graphene.String()
    rate = graphene.Decimal()
    rate_date = graphene.Date()
    source = graphene.String()


class ProductPricingType(graphene.ObjectType):
    """GraphQL type for Product Pricing"""
    id = graphene.Int()
    product_id = graphene.Int()
    currency = graphene.String()
    price = graphene.Decimal()
    compare_at_price = graphene.Decimal()
    cost = graphene.Decimal()
    discount_percentage = graphene.Decimal()
    is_custom_price = graphene.Boolean()
    is_base_currency = graphene.Boolean()


class PriceData(graphene.ObjectType):
    """Price information in a specific currency"""
    price = graphene.Decimal(required=True)
    compare_at_price = graphene.Decimal()
    cost = graphene.Decimal()
    currency = graphene.String(required=True)
    discount_percentage = graphene.Decimal()
    is_custom_price = graphene.Boolean()
    formatted_price = graphene.String()


class ConversionResult(graphene.ObjectType):
    """Currency conversion result"""
    from_currency = graphene.String(required=True)
    to_currency = graphene.String(required=True)
    original_amount = graphene.Decimal(required=True)
    converted_amount = graphene.Decimal(required=True)
    exchange_rate = graphene.Decimal(required=True)
    rate_date = graphene.Date()
    formatted_converted = graphene.String()


class TaxInformation(graphene.ObjectType):
    """Tax information for a location"""
    country_code = graphene.String()
    state_province = graphene.String()
    tax_type = graphene.String()
    tax_rate = graphene.Decimal()
    currency = graphene.String()


class OrderSummary(graphene.ObjectType):
    """Order pricing summary with currency"""
    subtotal = graphene.Decimal()
    tax_amount = graphene.Decimal()
    shipping_amount = graphene.Decimal()
    discount_amount = graphene.Decimal()
    total = graphene.Decimal()
    currency = graphene.String()
    exchange_rate = graphene.Decimal()
    base_currency = graphene.String()


# ============================================================================
# QUERIES
# ============================================================================

class CurrencyQuery(graphene.ObjectType):
    """Currency-related queries"""
    
    all_currencies = graphene.List(CurrencyType)
    currency = graphene.Field(CurrencyType, code=graphene.String(required=True))
    
    exchange_rate = graphene.Field(
        ExchangeRateType,
        from_currency=graphene.String(required=True),
        to_currency=graphene.String(required=True),
        rate_date=graphene.Date()
    )
    
    convert_currency = graphene.Field(
        ConversionResult,
        amount=graphene.Decimal(required=True),
        from_currency=graphene.String(required=True),
        to_currency=graphene.String(required=True),
        rate_date=graphene.Date()
    )
    
    product_price_in_currency = graphene.Field(
        PriceData,
        product_id=graphene.Int(required=True),
        currency=graphene.String(required=True)
    )
    
    product_available_currencies = graphene.List(
        graphene.String,
        product_id=graphene.Int(required=True)
    )
    
    tax_rate = graphene.Field(
        TaxInformation,
        country_code=graphene.String(required=True),
        state_province=graphene.String(),
        currency=graphene.String(required=True)
    )
    
    calculate_order_tax = graphene.Field(
        graphene.Decimal,
        subtotal=graphene.Decimal(required=True),
        country_code=graphene.String(required=True),
        state_province=graphene.String(),
        currency=graphene.String(required=True)
    )
    
    @staticmethod
    def resolve_all_currencies(obj, info):
        """Get all active currencies"""
        currencies = Currency.objects.filter(is_active=True).order_by('code')
        return [
            CurrencyType(
                code=c.code,
                name=c.name,
                symbol=c.symbol,
                country=c.country,
                decimal_places=c.decimal_places,
                symbol_position=c.symbol_position,
                is_active=c.is_active,
                is_default=c.is_default
            )
            for c in currencies
        ]
    
    @staticmethod
    def resolve_currency(obj, info, code):
        """Get specific currency"""
        try:
            currency = Currency.objects.get(code=code, is_active=True)
            return CurrencyType(
                code=currency.code,
                name=currency.name,
                symbol=currency.symbol,
                country=currency.country,
                decimal_places=currency.decimal_places,
                symbol_position=currency.symbol_position,
                is_active=currency.is_active,
                is_default=currency.is_default
            )
        except Currency.DoesNotExist:
            return None
    
    @staticmethod
    def resolve_exchange_rate(obj, info, from_currency, to_currency, rate_date=None):
        """Get exchange rate between two currencies"""
        if rate_date is None:
            rate_date = timezone.now().date()
        
        try:
            rate = ExchangeRate.objects.get(
                from_currency__code=from_currency,
                to_currency__code=to_currency,
                rate_date=rate_date
            )
            return ExchangeRateType(
                id=rate.id,
                from_currency=rate.from_currency.code,
                to_currency=rate.to_currency.code,
                rate=rate.rate,
                rate_date=rate.rate_date,
                source=rate.source
            )
        except ExchangeRate.DoesNotExist:
            return None
    
    @staticmethod
    def resolve_convert_currency(obj, info, amount, from_currency, to_currency, rate_date=None):
        """Convert amount from one currency to another"""
        if rate_date is None:
            rate_date = timezone.now().date()
        
        converted = CurrencyConverter.convert(
            Decimal(str(amount)),
            from_currency,
            to_currency,
            rate_date
        )
        
        if converted is None:
            return None
        
        try:
            rate = ExchangeRate.objects.get(
                from_currency__code=from_currency,
                to_currency__code=to_currency,
                rate_date=rate_date
            )
            exchange_rate = rate.rate
        except:
            exchange_rate = Decimal('1.0')
        
        return ConversionResult(
            from_currency=from_currency,
            to_currency=to_currency,
            original_amount=Decimal(str(amount)),
            converted_amount=converted,
            exchange_rate=exchange_rate,
            rate_date=rate_date,
            formatted_converted=f"{to_currency} {converted}"
        )
    
    @staticmethod
    def resolve_product_price_in_currency(obj, info, product_id, currency):
        """Get product price in specific currency"""
        from product_service.models import Product
        
        try:
            product = Product.objects.get(id=product_id)
            pricing = product.get_price_for_currency(currency)
            
            if not pricing:
                return None
            
            return PriceData(
                price=pricing['price'],
                compare_at_price=pricing.get('compare_at_price'),
                cost=pricing.get('cost'),
                currency=currency,
                discount_percentage=pricing.get('discount_percentage', Decimal('0')),
                is_custom_price=pricing.get('is_custom_price', False),
                formatted_price=PricingCalculator.format_price(pricing['price'], currency)
            )
        except Exception:
            return None
    
    @staticmethod
    def resolve_product_available_currencies(obj, info, product_id):
        """Get all currencies this product is priced in"""
        from product_service.models import Product
        
        try:
            product = Product.objects.get(id=product_id)
            return list(product.get_available_currencies())
        except:
            return []
    
    @staticmethod
    def resolve_tax_rate(obj, info, country_code, state_province='', currency='USD'):
        """Get tax rate for location"""
        try:
            tax_rate = TaxRate.objects.get(
                country_code=country_code,
                state_province=state_province,
                currency__code=currency,
                is_active=True
            )
            return TaxInformation(
                country_code=tax_rate.country_code,
                state_province=tax_rate.state_province,
                tax_type=tax_rate.tax_type,
                tax_rate=tax_rate.rate,
                currency=tax_rate.currency.code
            )
        except TaxRate.DoesNotExist:
            return None
    
    @staticmethod
    def resolve_calculate_order_tax(obj, info, subtotal, country_code, currency, state_province=''):
        """Calculate tax for order"""
        return TaxCalculator.calculate_tax(
            Decimal(str(subtotal)),
            country_code,
            state_province,
            currency
        )


# ============================================================================
# MUTATIONS
# ============================================================================

class SetOrderCurrency(graphene.Mutation):
    """Set currency for an order"""
    
    class Arguments:
        order_id = graphene.Int(required=True)
        currency = graphene.String(required=True)
    
    success = graphene.Boolean()
    message = graphene.String()
    order = graphene.Field(lambda: graphene.ObjectType)
    
    @staticmethod
    def mutate(root, info, order_id, currency):
        from order_service.models import Order
        
        try:
            order = Order.objects.get(id=order_id)
            order.set_currency(currency)
            order.save()
            
            return SetOrderCurrency(
                success=True,
                message=f"Order currency changed to {currency}",
                order=order
            )
        except Order.DoesNotExist:
            return SetOrderCurrency(
                success=False,
                message="Order not found"
            )
        except ValueError as e:
            return SetOrderCurrency(
                success=False,
                message=str(e)
            )


class SetCartCurrency(graphene.Mutation):
    """Set currency for shopping cart"""
    
    class Arguments:
        cart_id = graphene.Int(required=True)
        currency = graphene.String(required=True)
    
    success = graphene.Boolean()
    message = graphene.String()
    
    @staticmethod
    def mutate(root, info, cart_id, currency):
        from order_service.models import Cart
        
        try:
            cart = Cart.objects.get(id=cart_id)
            cart.set_currency(currency)
            
            return SetCartCurrency(
                success=True,
                message=f"Cart currency changed to {currency}"
            )
        except Cart.DoesNotExist:
            return SetCartCurrency(
                success=False,
                message="Cart not found"
            )
        except ValueError as e:
            return SetCartCurrency(
                success=False,
                message=str(e)
            )


class CalculateOrderTotal(graphene.Mutation):
    """Calculate complete order total with tax and shipping"""
    
    class Arguments:
        order_id = graphene.Int(required=True)
    
    success = graphene.Boolean()
    message = graphene.String()
    summary = graphene.Field(OrderSummary)
    
    @staticmethod
    def mutate(root, info, order_id):
        from order_service.models import Order
        
        try:
            order = Order.objects.get(id=order_id)
            order.apply_tax()
            order.calculate_total()
            order.save()
            
            summary = OrderSummary(
                subtotal=order.subtotal,
                tax_amount=order.tax_amount,
                shipping_amount=order.shipping_amount,
                discount_amount=order.discount_amount,
                total=order.total,
                currency=order.currency,
                exchange_rate=order.exchange_rate,
                base_currency=order.base_currency
            )
            
            return CalculateOrderTotal(
                success=True,
                message="Order total calculated successfully",
                summary=summary
            )
        except Order.DoesNotExist:
            return CalculateOrderTotal(
                success=False,
                message="Order not found"
            )


class CurrencyMutation(graphene.ObjectType):
    """All currency-related mutations"""
    set_order_currency = SetOrderCurrency.Field()
    set_cart_currency = SetCartCurrency.Field()
    calculate_order_total = CalculateOrderTotal.Field()
