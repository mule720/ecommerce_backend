"""
Management command to initialize currencies and exchange rates
"""

from django.core.management.base import BaseCommand
from decimal import Decimal
from datetime import date
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Initialize currencies and exchange rates for multi-currency support'

    def handle(self, *args, **options):
        from ecom_backend.multi_currency import Currency, ExchangeRate, TaxRate
        
        # Define currencies to create
        currencies_data = [
            {
                'code': 'USD',
                'name': 'United States Dollar',
                'symbol': '$',
                'country': 'United States',
                'is_default': True,
                'symbol_position': 'before',
                'thousands_separator': ',',
                'decimal_separator': '.',
            },
            {
                'code': 'EUR',
                'name': 'Euro',
                'symbol': '€',
                'country': 'European Union',
                'is_default': False,
                'symbol_position': 'after',
                'thousands_separator': '.',
                'decimal_separator': ',',
            },
            {
                'code': 'GBP',
                'name': 'British Pound',
                'symbol': '£',
                'country': 'United Kingdom',
                'is_default': False,
                'symbol_position': 'before',
                'thousands_separator': ',',
                'decimal_separator': '.',
            },
            {
                'code': 'JPY',
                'name': 'Japanese Yen',
                'symbol': '¥',
                'country': 'Japan',
                'is_default': False,
                'decimal_places': 0,
                'symbol_position': 'before',
                'thousands_separator': ',',
                'decimal_separator': '.',
            },
            {
                'code': 'ZMW',
                'name': 'Zambian Kwacha',
                'symbol': 'ZK',
                'country': 'Zambia',
                'is_default': False,
                'symbol_position': 'after',
                'thousands_separator': ',',
                'decimal_separator': '.',
            },
            {
                'code': 'ZAR',
                'name': 'South African Rand',
                'symbol': 'R',
                'country': 'South Africa',
                'is_default': False,
                'symbol_position': 'before',
                'thousands_separator': ',',
                'decimal_separator': '.',
            },
            {
                'code': 'CAD',
                'name': 'Canadian Dollar',
                'symbol': 'CA$',
                'country': 'Canada',
                'is_default': False,
                'symbol_position': 'before',
                'thousands_separator': ',',
                'decimal_separator': '.',
            },
            {
                'code': 'AUD',
                'name': 'Australian Dollar',
                'symbol': 'A$',
                'country': 'Australia',
                'is_default': False,
                'symbol_position': 'before',
                'thousands_separator': ',',
                'decimal_separator': '.',
            },
            {
                'code': 'INR',
                'name': 'Indian Rupee',
                'symbol': '₹',
                'country': 'India',
                'is_default': False,
                'symbol_position': 'before',
                'thousands_separator': ',',
                'decimal_separator': '.',
            },
            {
                'code': 'NGN',
                'name': 'Nigerian Naira',
                'symbol': '₦',
                'country': 'Nigeria',
                'is_default': False,
                'symbol_position': 'before',
                'thousands_separator': ',',
                'decimal_separator': '.',
            },
        ]
        
        created_count = 0
        for curr_data in currencies_data:
            currency, created = Currency.objects.get_or_create(
                code=curr_data['code'],
                defaults=curr_data
            )
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Created currency: {currency.code} - {currency.name}')
                )
            else:
                self.stdout.write(f'Currency already exists: {currency.code}')
        
        self.stdout.write(
            self.style.SUCCESS(f'\nSuccessfully created {created_count} currencies')
        )
        
        # Create sample exchange rates
        self._create_exchange_rates()
        
        # Create sample tax rates
        self._create_tax_rates()
    
    def _create_exchange_rates(self):
        """Create sample exchange rates"""
        from ecom_backend.multi_currency import Currency, ExchangeRate
        
        today = date.today()
        
        # Sample rates (as of today)
        rates_data = [
            ('USD', 'EUR', '0.92'),
            ('USD', 'GBP', '0.79'),
            ('USD', 'JPY', '110.50'),
            ('USD', 'ZMW', '20.85'),
            ('USD', 'ZAR', '16.45'),
            ('USD', 'CAD', '1.36'),
            ('USD', 'AUD', '1.48'),
            ('USD', 'INR', '75.20'),
            ('USD', 'NGN', '411.50'),
        ]
        
        created_count = 0
        for from_code, to_code, rate in rates_data:
            try:
                from_curr = Currency.objects.get(code=from_code)
                to_curr = Currency.objects.get(code=to_code)
                
                exchange_rate, created = ExchangeRate.objects.get_or_create(
                    from_currency=from_curr,
                    to_currency=to_curr,
                    rate_date=today,
                    defaults={
                        'rate': Decimal(rate),
                        'source': 'manual'
                    }
                )
                if created:
                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'Created exchange rate: {from_code} → {to_code} = {rate}')
                    )
            except Currency.DoesNotExist:
                self.stdout.write(self.style.WARNING(f'Currency not found: {from_code} or {to_code}'))
        
        self.stdout.write(
            self.style.SUCCESS(f'\nSuccessfully created {created_count} exchange rates')
        )
    
    def _create_tax_rates(self):
        """Create sample tax rates"""
        from ecom_backend.multi_currency import Currency, TaxRate
        
        tax_data = [
            {'country': 'US', 'state': 'CA', 'rate': 8.25, 'tax_type': 'sales_tax'},
            {'country': 'US', 'state': 'TX', 'rate': 8.25, 'tax_type': 'sales_tax'},
            {'country': 'US', 'state': 'NY', 'rate': 8.875, 'tax_type': 'sales_tax'},
            {'country': 'UK', 'state': '', 'rate': 20.0, 'tax_type': 'vat'},
            {'country': 'DE', 'state': '', 'rate': 19.0, 'tax_type': 'vat'},
            {'country': 'FR', 'state': '', 'rate': 20.0, 'tax_type': 'vat'},
            {'country': 'JP', 'state': '', 'rate': 10.0, 'tax_type': 'vat'},
            {'country': 'ZA', 'state': '', 'rate': 15.0, 'tax_type': 'vat'},
            {'country': 'IN', 'state': '', 'rate': 18.0, 'tax_type': 'gst'},
        ]
        
        try:
            usd = Currency.objects.get(code='USD')
            created_count = 0
            
            for tax in tax_data:
                tax_rate, created = TaxRate.objects.get_or_create(
                    country_code=tax['country'],
                    state_province=tax['state'],
                    tax_type=tax['tax_type'],
                    currency=usd,
                    defaults={'rate': Decimal(str(tax['rate']))}
                )
                if created:
                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'Created tax rate: {tax["country"]} {tax["tax_type"]} = {tax["rate"]}%')
                    )
            
            self.stdout.write(
                self.style.SUCCESS(f'\nSuccessfully created {created_count} tax rates')
            )
        
        except Currency.DoesNotExist:
            self.stdout.write(self.style.ERROR('USD currency not found'))
