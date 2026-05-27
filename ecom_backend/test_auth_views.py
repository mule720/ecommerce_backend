"""Test endpoint for debugging authentication"""
import logging
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

logger = logging.getLogger(__name__)


@require_http_methods(["GET", "POST"])
def test_auth(request):
    """Test endpoint to verify JWT authentication is working"""
    user = request.user
    
    response = {
        'authenticated': user.is_authenticated,
        'user': None,
        'token_header': request.headers.get('Authorization', 'NOT_PRESENT')[:30] + '...' if request.headers.get('Authorization') else 'NOT_PRESENT',
    }
    
    if user.is_authenticated:
        response['user'] = {
            'id': str(user.id),
            'email': user.email,
            'role': user.role,
            'has_vendor_profile': hasattr(user, 'vendor_profile') and user.vendor_profile is not None,
        }
        logger.info(f"Test auth: User authenticated - {user.email} ({user.role})")
    else:
        logger.warning("Test auth: User is anonymous/unauthenticated")
    
    return JsonResponse(response)
