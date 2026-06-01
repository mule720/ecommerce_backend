"""
URL configuration for ecom_backend project.

GraphQL API endpoints for all microservices
"""
from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from ecom_backend.graphql_auth import JWTGraphQLView
from ecom_backend.test_auth_views import test_auth
from product_service.video_upload_views import upload_product_video, upload_product_image
from ecom_backend.auth_views import (
    login_user,
    register_customer,
    register_vendor_onboarding,
    select_vendor_subscription,
    trigger_vendor_subscription_payment,
    request_password_reset,
)
from card_vault.crypto import get_rsa_public_key_pem
from django.http import JsonResponse
from payvault.webhook import payvault_webhook


def payment_public_key_view(request):
    """Return RSA public key for client-side card encryption. GET, no auth required."""
    return JsonResponse({'publicKey': get_rsa_public_key_pem()})

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # GraphQL API endpoint with JWT authentication
    path("graphql/", JWTGraphQLView.as_view(graphiql=True), name="graphql"),

    # Test endpoint for debugging auth
    path("api/test-auth/", test_auth, name="test_auth"),

    # Product media upload endpoint (video, with 30-minute limit validation)
    path("api/products/upload-video/", upload_product_video, name="upload_product_video"),
    path("api/products/upload-image/", upload_product_image, name="upload_product_image"),

    # Frontend auth + onboarding endpoints
    path("api/auth/login/", login_user, name="api_login_user"),
    path("api/auth/register/customer/", register_customer, name="api_register_customer"),
    path("api/auth/register/vendor/", register_vendor_onboarding, name="api_register_vendor_onboarding"),
    path("api/auth/reset-password/", request_password_reset, name="api_request_password_reset"),
    path("api/vendor/subscription/select/", select_vendor_subscription, name="api_select_vendor_subscription"),
    path("api/vendor/subscription/payment/trigger/", trigger_vendor_subscription_payment, name="api_trigger_vendor_subscription_payment"),
    
    # Payment public key (for browser-side card encryption)
    path("api/payment/public-key/", payment_public_key_view, name="payment_public_key"),

    # PayVault webhook (payment confirmation callbacks)
    path("api/payvault/webhook/", payvault_webhook, name="payvault_webhook"),

    # Health check endpoint
    path("health/", lambda request: __import__('json'). dumps({"status": "ok"}), name="health"),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
