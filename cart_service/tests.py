""
Cart Service Tests
"""
from django.test import TestCase
from django.contrib.auth.models import User
from product_service.models import Product, Category
from .models import Cart, CartItem


class CartTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.category = Category.objects.create(name='Test', slug='test')
        self.product = Product.objects.create(
            vendor=self.user,
            name='Test Product',
            price=10.00,
            quantity=10,
            category=self.category
        )

    def test_cart_creation(self):
        cart = Cart.objects.create(customer=self.user)
        self.assertEqual(cart.customer, self.user)

    def test_add_to_cart(self):
        cart = Cart.objects.create(customer=self.user)
        CartItem.objects.create(cart=cart, product=self.product, quantity=2)
        self.assertEqual(cart.items.count(), 1)

    def test_cart_total(self):
        cart = Cart.objects.create(customer=self.user)
        CartItem.objects.create(cart=cart, product=self.product, quantity=2)
        self.assertEqual(cart.get_total(), 20.0)
