from django.core.management.base import BaseCommand
from checkout_service.models import ShippingMethod


class Command(BaseCommand):
    help = 'Create default shipping methods'

    def handle(self, *args, **options):
        shipping_methods = [
            {
                'name': 'Standard Delivery',
                'shipping_type': 'standard',
                'base_cost': 5.99,
                'estimated_days': 5,
                'description': 'Delivery in 5-7 business days',
            },
            {
                'name': 'Express Delivery',
                'shipping_type': 'express',
                'base_cost': 12.99,
                'estimated_days': 2,
                'description': 'Delivery in 2-3 business days',
            },
            {
                'name': 'Same Day Delivery',
                'shipping_type': 'same_day',
                'base_cost': 24.99,
                'estimated_days': 0,
                'description': 'Same day delivery (Available for selected areas)',
            },
            {
                'name': 'Customer Pickup',
                'shipping_type': 'pickup',
                'base_cost': 0.00,
                'estimated_days': 0,
                'description': 'Pick up at our store',
            },
        ]

        for method_data in shipping_methods:
            method, created = ShippingMethod.objects.get_or_create(
                shipping_type=method_data['shipping_type'],
                defaults={
                    'name': method_data['name'],
                    'base_cost': method_data['base_cost'],
                    'estimated_days': method_data['estimated_days'],
                    'description': method_data['description'],
                }
            )
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f"Created shipping method: {method.name}")
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f"Shipping method already exists: {method.name}")
                )
        
        self.stdout.write(self.style.SUCCESS("Shipping methods setup complete!"))
