"""REST auth and vendor onboarding endpoints for frontend integration."""
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from ecom_backend.event_bus import publish_event
from user_service.models import CustomerProfile, VendorProfile, VendorSubscription

logger = logging.getLogger(__name__)
User = get_user_model()


def _json_body(request):
    """Parse JSON body safely and return a dict."""
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode('utf-8'))
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def _error(message, status=400):
    """Build a consistent JSON error response."""
    return JsonResponse({'error': message}, status=status)


def _normalize_email(email):
    """Normalize incoming email for uniqueness checks."""
    return str(email or '').strip().lower()


def _build_unique_username(email):
    """Derive a unique username from email prefix."""
    base = _normalize_email(email).split('@')[0] or 'user'
    base = ''.join(ch for ch in base if ch.isalnum() or ch in {'-', '_', '.'}) or 'user'
    candidate = base[:140]
    index = 1
    while User.objects.filter(username=candidate).exists():
        suffix = f"-{index}"
        candidate = f"{base[:140 - len(suffix)]}{suffix}"
        index += 1
    return candidate


def _issue_token(user):
    """Issue a signed JWT access token for frontend session storage."""
    now = datetime.now(timezone.utc)
    payload = {
        'sub': str(user.id),
        'email': user.email,
        'role': user.role,
        'iat': int(now.timestamp()),
        'exp': int((now + timedelta(hours=24)).timestamp()),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')


def _serialize_user(user):
    """Serialize user data for frontend auth state."""
    data = {
        'id': str(user.id),
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'role': user.role,
        'phone': user.phone,
        'is_verified': user.is_verified,
        'created_at': user.created_at.isoformat() if user.created_at else '',
    }
    if user.role == User.UserRole.VENDOR and hasattr(user, 'vendor_profile'):
        data['vendor_profile'] = {
            'id': str(user.vendor_profile.id),
            'business_name': user.vendor_profile.business_name,
            'tax_id': user.vendor_profile.tax_id,
            'pacra_registration_number': user.vendor_profile.business_license,
            'status': user.vendor_profile.status,
        }
    return data


def _serialize_subscription(subscription):
    """Serialize vendor subscription payload for frontend steps."""
    return {
        'id': str(subscription.id),
        'plan_code': subscription.plan_code,
        'plan_name': subscription.plan_name,
        'billing_cycle': subscription.billing_cycle,
        'amount': str(subscription.amount),
        'currency': subscription.currency,
        'status': subscription.status,
        'payment_reference': subscription.payment_reference,
        'created_at': subscription.created_at.isoformat() if subscription.created_at else '',
    }


def _extract_token(request, payload):
    """Read JWT from Authorization header or request body fallback."""
    header = request.headers.get('Authorization', '')
    if header.lower().startswith('bearer '):
        return header.split(' ', 1)[1].strip()
    return str((payload or {}).get('token') or '').strip()


def _authenticate_request(request, payload):
    """Resolve authenticated user from incoming JWT token."""
    token = _extract_token(request, payload)
    if not token:
        return None, _error('Authentication token is required.', status=401)

    try:
        decoded = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        return None, _error('Session expired. Please sign in again.', status=401)
    except jwt.InvalidTokenError:
        return None, _error('Invalid authentication token.', status=401)

    user_id = decoded.get('sub')
    if not user_id:
        return None, _error('Invalid authentication token payload.', status=401)

    try:
        user = User.objects.get(pk=int(user_id), is_active=True)
    except (User.DoesNotExist, ValueError, TypeError):
        return None, _error('Authenticated user not found.', status=401)

    return user, None


@csrf_exempt
@require_POST
def login_user(request):
    """Authenticate an existing user and return JWT + profile data."""
    payload = _json_body(request)
    if payload is None:
        return _error('Invalid JSON payload.')

    email = _normalize_email(payload.get('email'))
    password = str(payload.get('password') or '')

    if not email or not password:
        return _error('Email and password are required.')

    user = User.objects.filter(email__iexact=email).first()
    if not user or not user.check_password(password):
        return _error('Invalid email or password.', status=401)
    if not user.is_active:
        return _error('Account is disabled. Please contact support.', status=403)

    token = _issue_token(user)
    return JsonResponse({'token': token, 'user': _serialize_user(user)})


@csrf_exempt
@require_POST
def register_customer(request):
    """Create customer account directly from login page sign-up flow."""
    payload = _json_body(request)
    if payload is None:
        return _error('Invalid JSON payload.')

    first_name = str(payload.get('first_name') or '').strip()
    last_name = str(payload.get('last_name') or '').strip()
    email = _normalize_email(payload.get('email'))
    password = str(payload.get('password') or '')
    phone = str(payload.get('phone') or '').strip()

    if not first_name or not last_name:
        return _error('First name and last name are required.')
    if not email:
        return _error('Email is required.')
    if len(password) < 6:
        return _error('Password must be at least 6 characters long.')
    if User.objects.filter(email__iexact=email).exists():
        return _error('An account with this email already exists.', status=409)

    with transaction.atomic():
        user = User.objects.create_user(
            username=_build_unique_username(email),
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            role=User.UserRole.CUSTOMER,
            phone=phone,
        )
        CustomerProfile.objects.get_or_create(user=user)

    token = _issue_token(user)
    return JsonResponse({'token': token, 'user': _serialize_user(user)}, status=201)


@csrf_exempt
@require_POST
def register_vendor_onboarding(request):
    """Create vendor account from Start Selling flow with business details."""
    payload = _json_body(request)
    if payload is None:
        return _error('Invalid JSON payload.')

    first_name = str(payload.get('first_name') or '').strip()
    last_name = str(payload.get('last_name') or '').strip()
    email = _normalize_email(payload.get('email'))
    password = str(payload.get('password') or '')
    phone = str(payload.get('phone') or '').strip()
    company_name = str(payload.get('company_name') or '').strip()
    tpin = str(payload.get('tpin') or '').strip()
    pacra_registration_number = str(payload.get('pacra_registration_number') or '').strip()
    business_description = str(payload.get('business_description') or '').strip()
    address = str(payload.get('address') or '').strip()
    city = str(payload.get('city') or '').strip()
    country = str(payload.get('country') or '').strip()
    postal_code = str(payload.get('postal_code') or '').strip()
    bank_account = str(payload.get('bank_account') or '').strip()
    payout_method = str(payload.get('payout_method') or '').strip()

    if not first_name or not last_name:
        return _error('Owner first name and last name are required.')
    if not email:
        return _error('Email is required.')
    if len(password) < 6:
        return _error('Password must be at least 6 characters long.')
    if not company_name:
        return _error('Company name is required.')
    if not tpin:
        return _error('TPIN is required.')
    if not pacra_registration_number:
        return _error('PACRA registration number is required.')
    if User.objects.filter(email__iexact=email).exists():
        return _error('An account with this email already exists.', status=409)

    with transaction.atomic():
        user = User.objects.create_user(
            username=_build_unique_username(email),
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            role=User.UserRole.VENDOR,
            phone=phone,
            address=address,
            city=city,
            country=country,
            postal_code=postal_code,
        )

        vendor_profile = VendorProfile.objects.create(
            user=user,
            business_name=company_name,
            business_description=business_description,
            business_license=pacra_registration_number,
            tax_id=tpin,
            bank_account=bank_account,
            payout_method=payout_method,
            status=VendorProfile.VendorStatus.PENDING,
        )

    token = _issue_token(user)
    return JsonResponse(
        {
            'token': token,
            'user': _serialize_user(user),
            'vendor_profile': {
                'id': str(vendor_profile.id),
                'business_name': vendor_profile.business_name,
                'tax_id': vendor_profile.tax_id,
                'pacra_registration_number': vendor_profile.business_license,
                'status': vendor_profile.status,
            },
        },
        status=201,
    )


@csrf_exempt
@require_POST
def select_vendor_subscription(request):
    """Persist selected vendor subscription and prepare payment step."""
    payload = _json_body(request)
    if payload is None:
        return _error('Invalid JSON payload.')

    user, auth_error = _authenticate_request(request, payload)
    if auth_error:
        return auth_error
    if user.role != User.UserRole.VENDOR:
        return _error('Only vendor accounts can select subscriptions.', status=403)

    plan_code = str(payload.get('plan_code') or '').strip()
    plan_name = str(payload.get('plan_name') or '').strip()
    billing_cycle = str(payload.get('billing_cycle') or VendorSubscription.BillingCycle.MONTHLY).strip().lower()
    currency = str(payload.get('currency') or 'ZMW').strip().upper()
    amount_raw = payload.get('amount')
    features = payload.get('features') or []

    if not plan_code or not plan_name:
        return _error('Subscription plan code and name are required.')
    valid_cycles = {choice[0] for choice in VendorSubscription.BillingCycle.choices}
    if billing_cycle not in valid_cycles:
        return _error('Invalid billing cycle selected.')
    try:
        amount = Decimal(str(amount_raw))
    except (InvalidOperation, TypeError, ValueError):
        return _error('Subscription amount must be a valid number.')
    if amount <= 0:
        return _error('Subscription amount must be greater than 0.')

    try:
        vendor_profile = user.vendor_profile
    except VendorProfile.DoesNotExist:
        return _error('Vendor profile not found for this user.', status=404)

    subscription = VendorSubscription.objects.create(
        vendor_profile=vendor_profile,
        plan_code=plan_code,
        plan_name=plan_name,
        billing_cycle=billing_cycle,
        amount=amount,
        currency=currency,
        status=VendorSubscription.SubscriptionStatus.PAYMENT_PENDING,
        payment_reference=f"VSUB-{uuid.uuid4().hex[:12].upper()}",
        metadata={'features': features},
    )

    return JsonResponse(
        {
            'subscription': _serialize_subscription(subscription),
            'next_step': 'payment',
        },
        status=201,
    )


@csrf_exempt
@require_POST
def trigger_vendor_subscription_payment(request):
    """Trigger payment integration event for vendor subscription checkout."""
    payload = _json_body(request)
    if payload is None:
        return _error('Invalid JSON payload.')

    user, auth_error = _authenticate_request(request, payload)
    if auth_error:
        return auth_error
    if user.role != User.UserRole.VENDOR:
        return _error('Only vendor accounts can trigger subscription payments.', status=403)

    subscription_id = payload.get('subscription_id')
    if not subscription_id:
        return _error('subscription_id is required.')

    try:
        subscription = VendorSubscription.objects.get(
            pk=int(subscription_id),
            vendor_profile__user=user,
        )
    except (VendorSubscription.DoesNotExist, ValueError, TypeError):
        return _error('Subscription not found for this vendor.', status=404)

    if subscription.status == VendorSubscription.SubscriptionStatus.CANCELLED:
        return _error('Cancelled subscriptions cannot be paid.', status=400)

    subscription.status = VendorSubscription.SubscriptionStatus.PAYMENT_PENDING
    subscription.save(update_fields=['status', 'updated_at'])

    event_payload = {
        'subscription_id': str(subscription.id),
        'vendor_id': str(user.id),
        'email': user.email,
        'plan_code': subscription.plan_code,
        'plan_name': subscription.plan_name,
        'billing_cycle': subscription.billing_cycle,
        'amount': str(subscription.amount),
        'currency': subscription.currency,
        'payment_reference': subscription.payment_reference,
        'requested_at': datetime.now(timezone.utc).isoformat(),
    }

    event_queued = True
    try:
        publish_event('payment.events', 'VendorSubscriptionPaymentRequested', event_payload)
    except Exception:
        logger.exception('Failed to publish vendor subscription payment event')
        event_queued = False

    return JsonResponse(
        {
            'subscription': _serialize_subscription(subscription),
            'payment': {
                'provider': 'payment_system',
                'status': 'triggered',
                'reference': subscription.payment_reference,
                'amount': str(subscription.amount),
                'currency': subscription.currency,
                'event_queued': event_queued,
                'message': 'Payment module triggered. Complete gateway callback integration later.',
            },
        }
    )


@csrf_exempt
@require_POST
def request_password_reset(request):
    """Acknowledge reset password requests (email delivery integrated later)."""
    payload = _json_body(request)
    if payload is None:
        return _error('Invalid JSON payload.')

    email = _normalize_email(payload.get('email'))
    if not email:
        return _error('Email is required.')

    # Intentionally return the same response regardless of account existence.
    user = User.objects.filter(email__iexact=email).only('id', 'email').first()
    if user:
        try:
            publish_event(
                'ecommerce.events',
                'PasswordResetRequested',
                {
                    'user_id': str(user.id),
                    'email': user.email,
                    'requested_at': datetime.now(timezone.utc).isoformat(),
                },
            )
        except Exception:
            logger.exception('Failed to publish password reset event')

    return JsonResponse(
        {
            'message': 'If an account exists for this email, reset instructions will be sent.'
        }
    )
