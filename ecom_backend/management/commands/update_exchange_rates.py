"""
Management command to update exchange rates from API
"""

from django.core.management.base import BaseCommand
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Update exchange rates from external API'

    def add_arguments(self, parser):
        parser.add_argument(
            '--provider',
            type=str,
            default='manual',
            help='Currency API provider (openexchangerates, fixer, manual)'
        )

    def handle(self, *args, **options):
        from ecom_backend.multi_currency import CurrencyConverter
        
        provider = options.get('provider')
        
        if provider == 'manual':
            self.stdout.write(
                self.style.WARNING('Manual provider selected. Please use another provider for live rates.')
            )
            return
        
        try:
            self.stdout.write(f'Updating exchange rates from {provider}...')
            CurrencyConverter.update_exchange_rates_from_api()
            self.stdout.write(
                self.style.SUCCESS('Exchange rates updated successfully')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error updating exchange rates: {str(e)}')
            )
