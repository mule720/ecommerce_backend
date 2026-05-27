"""
Custom GraphQL view with JWT authentication support
Intercepts requests to extract and validate JWT tokens from Authorization header
"""
import jwt
import json
import logging
from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from graphene_django.views import GraphQLView as DjangoGraphQLView

logger = logging.getLogger(__name__)
User = get_user_model()


@method_decorator(csrf_exempt, name='dispatch')
class JWTGraphQLView(DjangoGraphQLView):
    """GraphQL view with JWT token authentication support"""

    def get_context(self, request):
        """Extract JWT from Authorization header and attach user to context"""
        context = super().get_context(request)
        
        # Try to extract JWT token from Authorization header
        auth_header = request.headers.get('Authorization', '')
        logger.debug(f"GraphQL request - Auth header present: {bool(auth_header)}")
        
        if auth_header.lower().startswith('bearer '):
            token = auth_header.split(' ', 1)[1].strip()
            logger.debug(f"Attempting to decode JWT token")
            try:
                decoded = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
                user_id = decoded.get('sub')
                email = decoded.get('email')
                logger.debug(f"JWT decoded successfully - user_id: {user_id}, email: {email}")
                
                if user_id:
                    try:
                        user = User.objects.get(pk=int(user_id), is_active=True)
                        context.user = user
                        request.user = user
                        logger.info(f"GraphQL user authenticated: {user.email} (ID: {user.id}, Role: {user.role})")
                    except (User.DoesNotExist, ValueError, TypeError) as e:
                        logger.warning(f"User not found with ID {user_id}: {e}")
            except jwt.ExpiredSignatureError as e:
                logger.warning(f"JWT token expired: {e}")
            except jwt.InvalidTokenError as e:
                logger.warning(f"Invalid JWT token: {e}")
        else:
            logger.debug("No Bearer token found in Authorization header")
        
        return context
