"""Returns Service Tests"""
from django.test import TestCase
from django.contrib.auth.models import User
from decimal import Decimal


class ReturnRequestModelTest(TestCase):
    """Test ReturnRequest model"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_return_request_creation(self):
        """Test creating a return request"""
        from .models import ReturnRequest
        
        return_request = ReturnRequest.objects.create(
            customer=self.user,
            reason='defective',
            reason_description='Product stopped working',
            refund_amount=Decimal('99.99')
        )
        
        self.assertEqual(return_request.status, 'requested')
        self.assertEqual(return_request.customer, self.user)
        self.assertFalse(return_request.refund_issued)


class ReturnsQueryTest(TestCase):
    """Test Returns GraphQL queries"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_my_returns_query_unauthenticated(self):
        """Test myReturns query without authentication"""
        from .schema import ReturnsQuery
        
        query = ReturnsQuery()
        result = query.resolve_my_returns(query, None)
        
        self.assertEqual(result, [])
