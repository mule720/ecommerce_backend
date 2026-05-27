"""
Management command to create sample orders for testing
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from order_service.models import Order, OrderItem
from product_service.models import Product
from datetime import timedelta
from django.utils import timezone
import random


class Command(BaseCommand):
    help = 'Create sample orders for testing order functionality'

    def handle(self, *args, **options):
        # Get or create test customer
        customer, created = User.objects.get_or_create(
            email='customer@test.com',
            defaults={
                'username': 'testcustomer',
                'first_name': 'John',
                'last_name': 'Doe',
                'is_active': True
            }
        )
        if created:
            customer.set_password('CustomerPass123!')
            customer.save()
            self.stdout.write(f'✓ Created customer: {customer.email}')
        else:
            self.stdout.write(f'✓ Using existing customer: {customer.email}')

        # Get available products
        products = Product.objects.filter(status='ACTIVE')[:20]

        if not products.exists():
            self.stdout.write('✗ No active products found. Run setup_test_data.py first.')
            return

        self.stdout.write(f'Creating sample orders for {customer.email}...\n')

        # Create 5 sample orders with different statuses
        statuses = ['pending', 'confirmed', 'processing', 'shipped', 'delivered']
        
        for i in range(5):
            status = statuses[i]
            
            # Create order
            order = Order.objects.create(
                customer=customer,
                status=status,
                payment_status='completed' if status != 'pending' else 'pending',
                subtotal=100.00,
                shipping_amount=10.00,
                tax_amount=8.80,
                total=118.80,
                shipping_first_name='John',
                shipping_last_name='Doe',
                shipping_email='customer@test.com',
                shipping_phone='+1 555-0123',
                shipping_address='123 Main Street',
                shipping_city='New York',
                shipping_state='NY',
                shipping_postal_code='10001',
                shipping_country='United States',
                created_at=timezone.now() - timedelta(days=i*7)
            )

            # Add random products to order
            num_items = random.randint(1, 3)
            selected_products = random.sample(list(products), min(num_items, len(products)))

            total = 0
            for product in selected_products:
                quantity = random.randint(1, 3)
                unit_price = float(product.price)
                item_total = unit_price * quantity
                total += item_total

                OrderItem.objects.create(
                    order=order,
                    product=product,
                    quantity=quantity,
                    unit_price=unit_price,
                    total=item_total
                )

            # Update order total
            order.subtotal = total
            order.tax_amount = round(total * 0.088, 2)
            order.total = total + order.shipping_amount + order.tax_amount
            order.save()

            self.stdout.write(
                f'✓ Order {order.order_number} ({status}): '
                f'{len(selected_products)} items, ${order.total:.2f}'
            )

        self.stdout.write(
            self.style.SUCCESS(f'\n✓ Successfully created 5 sample orders!\n')
            f'Test login:\n'
            f'  Email: {customer.email}\n'
            f'  Password: CustomerPass123!'
        )
