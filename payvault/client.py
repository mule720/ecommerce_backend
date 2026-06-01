"""
PayVault client for e-commerce — zero extra dependencies.
Configure via Django settings:

    PAYVAULT_BASE_URL   = 'http://localhost:8001'
    PAYVAULT_API_KEY_ID = '...'
    PAYVAULT_API_SECRET = '...'
"""
import json
import urllib.request
import urllib.error
from django.conf import settings


class PayVaultError(Exception):
    pass


def _get_settings():
    base_url   = getattr(settings, 'PAYVAULT_BASE_URL', '')
    key_id     = getattr(settings, 'PAYVAULT_API_KEY_ID', '')
    api_secret = getattr(settings, 'PAYVAULT_API_SECRET', '')
    if not (base_url and key_id and api_secret):
        raise PayVaultError('PayVault settings not configured.')
    return base_url.rstrip('/') + '/graphql/', key_id, api_secret


_MUTATION = """
mutation CreatePaymentSession(
    $apiKeyId: String!
    $apiSecret: String!
    $amount: Decimal!
    $currency: String
    $description: String
    $merchantReference: String
    $idempotencyKey: String
) {
    createPaymentSession(
        apiKeyId: $apiKeyId
        apiSecret: $apiSecret
        amount: $amount
        currency: $currency
        description: $description
        merchantReference: $merchantReference
        idempotencyKey: $idempotencyKey
    ) {
        session {
            sessionReference
            status
            expiresAt
        }
        paymentUrl
    }
}
"""


def create_payment_session(
    amount: str,
    description: str = '',
    merchant_reference: str = '',
    idempotency_key: str = '',
    currency: str = 'ZMW',
) -> dict:
    """
    Returns dict with sessionReference, paymentUrl, status.
    Raises PayVaultError on failure.
    """
    import secrets
    graphql_url, key_id, api_secret = _get_settings()

    payload = json.dumps({'query': _MUTATION, 'variables': {
        'apiKeyId':          key_id,
        'apiSecret':         api_secret,
        'amount':            str(amount),
        'currency':          currency,
        'description':       description,
        'merchantReference': merchant_reference,
        'idempotencyKey':    idempotency_key or secrets.token_hex(16),
    }}).encode()

    req = urllib.request.Request(
        graphql_url,
        data=payload,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        raise PayVaultError(f'PayVault HTTP {exc.code}')
    except Exception as exc:
        raise PayVaultError(str(exc))

    if body.get('errors'):
        raise PayVaultError(body['errors'][0].get('message', 'GraphQL error'))

    result = body.get('data', {}).get('createPaymentSession', {})
    session = result.get('session')
    if not session:
        raise PayVaultError('Empty response from PayVault.')

    return {
        'sessionReference': session['sessionReference'],
        'status':           session['status'],
        'paymentUrl':       result.get('paymentUrl', ''),
    }
