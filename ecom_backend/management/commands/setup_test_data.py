"""
Management command to populate database with 100+ vendors and products for testing
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils.text import slugify
from decimal import Decimal
from product_service.models import Product, Category
from user_service.models import VendorProfile
from django.db import transaction
import random

User = get_user_model()


class Command(BaseCommand):
    help = 'Populate database with 100+ vendors and products for testing backend-frontend connection'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n🚀 Starting database population...'))
        
        with transaction.atomic():
            # Create categories
            categories = self.create_categories()
            self.stdout.write(self.style.SUCCESS(f'✓ Created {len(categories)} categories'))
            
            # Create 100+ vendors
            vendors = self.create_vendors(count=100)
            self.stdout.write(self.style.SUCCESS(f'✓ Created {len(vendors)} vendors'))
            
            # Create 2-5 products per vendor
            total_products = self.create_products(vendors, categories)
            self.stdout.write(self.style.SUCCESS(f'✓ Created {total_products} products'))
        
        self.stdout.write(self.style.SUCCESS('\n✨ Database population completed!'))
        self.print_login_info()

    def create_categories(self):
        """Create product categories"""
        categories_data = [
            {'name': 'Electronics', 'description': 'Electronic devices and gadgets'},
            {'name': 'Clothing & Fashion', 'description': 'Apparel and fashion items'},
            {'name': 'Home & Garden', 'description': 'Home and garden products'},
            {'name': 'Sports & Outdoors', 'description': 'Sports and fitness equipment'},
            {'name': 'Books & Media', 'description': 'Books and educational materials'},
            {'name': 'Toys & Games', 'description': 'Toys and games for all ages'},
            {'name': 'Health & Beauty', 'description': 'Health and beauty products'},
            {'name': 'Automotive', 'description': 'Automotive parts and accessories'},
        ]
        
        categories = {}
        for cat_data in categories_data:
            category, created = Category.objects.get_or_create(
                slug=slugify(cat_data['name']),
                defaults={
                    'name': cat_data['name'],
                    'description': cat_data['description'],
                    'is_active': True
                }
            )
            categories[cat_data['name']] = category
        
        return categories

    def create_vendors(self, count=100):
        """Create 100+ vendors"""
        vendor_names = [
            'TechHub', 'StyleMax', 'HomeComfort', 'SportZone', 'BookWorld',
            'ElectroStore', 'FashionHub', 'GardenGear', 'PlayHub', 'BeautyBay',
            'SnapElectronics', 'VogueStyle', 'NestHome', 'FitPro', 'PageTurner',
            'GadgetGalaxy', 'TrendZone', 'CozyLiving', 'ActiveLife', 'ReadMore',
            'TechWave', 'ChicEdge', 'ModernHome', 'FitnessFirst', 'StoryHub',
            'DigitalPoint', 'StyleSense', 'LivingPlus', 'WellnessHub', 'LibraryPlus',
        ]
        
        vendors = []
        created_count = 0
        
        for i in range(count):
            # Cycle through vendor names and add number
            base_name = vendor_names[i % len(vendor_names)]
            vendor_num = (i // len(vendor_names)) + 1
            
            username = f'vendor_{base_name.lower()}_{i+1}'.replace(' ', '_')
            email = f'vendor{i+1}@store.com'
            business_name = f'{base_name} Store #{i+1}'
            
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': email,
                    'first_name': base_name,
                    'last_name': f'Vendor {i+1}',
                    'role': User.UserRole.VENDOR,
                    'is_verified': True,
                }
            )
            
            if created:
                user.set_password('VendorPass123!')
                user.save()
                created_count += 1
            
            # Create or update vendor profile
            vendor_profile, _ = VendorProfile.objects.get_or_create(
                user=user,
                defaults={
                    'business_name': business_name,
                    'business_description': f'Premium products from {business_name}',
                    'tax_id': f'TAX{i+100000}',
                    'status': VendorProfile.VendorStatus.APPROVED,
                    'rating': Decimal(str(round(random.uniform(3.5, 5.0), 1))),
                }
            )
            
            vendors.append(user)
        
        self.stdout.write(f'  → {created_count} new vendors created, {count - created_count} already existed')
        return vendors

    def create_products(self, vendors, categories):
        """Create 2-5 products per vendor"""
        
        product_templates = [
            {
                'name': 'Premium {category} Product',
                'description': 'High-quality {category} product with excellent features and durability',
                'price_range': (19.99, 199.99),
            },
            {
                'name': 'Professional {category} Item',
                'description': 'Professional-grade {category} item designed for serious users',
                'price_range': (29.99, 299.99),
            },
            {
                'name': '{category} Bundle Pack',
                'description': 'Complete bundle of {category} products at special price',
                'price_range': (49.99, 499.99),
            },
            {
                'name': 'Deluxe {category} Set',
                'description': 'Deluxe collection featuring top-quality {category} items',
                'price_range': (59.99, 599.99),
            },
            {
                'name': '{category} Essential Collection',
                'description': 'Essential {category} products for everyday use',
                'price_range': (24.99, 249.99),
            },
        ]
        
        categories_list = list(categories.values())
        total_products_created = 0
        
        for vendor_idx, vendor in enumerate(vendors):
            products_count = random.randint(2, 5)
            
            for p in range(products_count):
                category = random.choice(categories_list)
                template = random.choice(product_templates)
                
                # Generate unique SKU
                sku = f'SKU{vendor_idx+1:04d}{p+1:02d}'
                
                # Generate price
                min_price, max_price = template['price_range']
                price = Decimal(str(round(random.uniform(min_price, max_price), 2)))
                compare_at_price = price + Decimal(str(round(random.uniform(10, 50), 2)))
                cost = price * Decimal('0.4')
                
                product_name = template['name'].replace('{category}', category.name)
                
                product, created = Product.objects.get_or_create(
                    sku=sku,
                    defaults={
                        'vendor': vendor,
                        'category': category,
                        'name': product_name,
                        'slug': slugify(f'{product_name}-{sku}'),
                        'description': template['description'].replace('{category}', category.name),
                        'price': price,
                        'compare_at_price': compare_at_price,
                        'cost_per_item': cost,
                        'quantity': random.randint(10, 200),
                        'weight': Decimal(str(round(random.uniform(0.1, 5.0), 2))),
                        'status': Product.ProductStatus.ACTIVE,
                        'is_featured': random.choice([True, False]),
                        'is_taxable': True,
                        'tax_rate': Decimal('10.00'),
                    }
                )
                
                if created:
                    total_products_created += 1
            
            if (vendor_idx + 1) % 20 == 0:
                self.stdout.write(f'  → Processed {vendor_idx + 1} vendors...')
        
        return total_products_created

    def print_login_info(self):
        """Print login information for testing"""
        self.stdout.write(self.style.SUCCESS('\n' + '='*60))
        self.stdout.write(self.style.WARNING('🔐 TEST ACCOUNT CREDENTIALS'))
        self.stdout.write('='*60)
        self.stdout.write('\nAll vendor accounts use the same password:')
        self.stdout.write(self.style.SUCCESS('  Password: VendorPass123!'))
        self.stdout.write('\nVendor usernames format:')
        self.stdout.write('  vendor_<storename>_<number>')
        self.stdout.write('  Example: vendor_techwav_1, vendor_techwav_2, etc.')
        self.stdout.write('\n' + '='*60)
