"""
Card Vault Cryptography
=======================
Two layers of protection:
  1. RSA-OAEP-2048/SHA-256  — card data encrypted in the browser before it
     ever leaves the user's device.  Only this server can decrypt it.
  2. AES-256-GCM             — PAN and expiry are re-encrypted at rest.
     CVV is validated and immediately discarded; it is NEVER stored.

PCI DSS requirements addressed:
  Req 3.4   — PAN stored only in encrypted form (AES-256-GCM)
  Req 3.2.1 — Sensitive authentication data (CVV) not retained after auth
  Req 4.2   — Strong cryptography used to protect PAN in transit
"""
import os
import json
import base64
import logging
import threading

from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_rsa_private_key = None
_rsa_public_pem: str = ''


# ---------------------------------------------------------------------------
# RSA-OAEP key pair — client-side encryption
# ---------------------------------------------------------------------------

def _init_rsa() -> None:
    global _rsa_private_key, _rsa_public_pem
    if _rsa_private_key:
        return
    with _lock:
        if _rsa_private_key:
            return
        pem = getattr(settings, 'CARD_VAULT_RSA_PRIVATE_KEY_PEM', None)
        if pem:
            if isinstance(pem, str):
                pem = pem.encode()
            _rsa_private_key = serialization.load_pem_private_key(pem, password=None)
        else:
            logger.warning(
                '[CardVault] CARD_VAULT_RSA_PRIVATE_KEY_PEM not set — '
                'generating ephemeral RSA key (dev only, NOT suitable for production)'
            )
            _rsa_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        _rsa_public_pem = _rsa_private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()


def get_rsa_public_key_pem() -> str:
    """Return PEM-encoded RSA-2048 public key for browser-side encryption."""
    _init_rsa()
    return _rsa_public_pem


def rsa_decrypt_payload(ciphertext_b64: str) -> dict:
    """
    Decrypt an RSA-OAEP-SHA256 ciphertext (base64) that was produced by the
    browser.  Returns the decoded JSON dict containing card fields.
    Raises on any decryption or JSON parsing error.
    """
    _init_rsa()
    raw = base64.b64decode(ciphertext_b64)
    plaintext = _rsa_private_key.decrypt(
        raw,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )
    return json.loads(plaintext)


# ---------------------------------------------------------------------------
# AES-256-GCM — PAN at rest
# ---------------------------------------------------------------------------

def _get_master_key() -> bytes:
    """
    Load the 32-byte (256-bit) AES master key from settings.
    In production set CARD_VAULT_MASTER_KEY_HEX to a 64-char hex string
    generated from a secure random source (e.g. HSM or AWS KMS data key).
    """
    key_hex = getattr(settings, 'CARD_VAULT_MASTER_KEY_HEX', None)
    if not key_hex or len(key_hex) != 64:
        logger.warning(
            '[CardVault] CARD_VAULT_MASTER_KEY_HEX not configured — '
            'using dev fallback key (NOT safe for production)'
        )
        key_hex = 'c0ffee' * 10 + 'dead'  # 32 bytes, deterministic for dev
    return bytes.fromhex(key_hex)


def aes_encrypt(plaintext: str) -> str:
    """
    Encrypt plaintext with AES-256-GCM.
    Returns base64(12-byte-nonce || ciphertext+tag).
    Each call uses a fresh random nonce.
    """
    key = _get_master_key()
    nonce = os.urandom(12)
    ct = AESGCM(key).encrypt(nonce, plaintext.encode('utf-8'), None)
    return base64.b64encode(nonce + ct).decode('ascii')


def aes_decrypt(encoded: str) -> str:
    """
    Decrypt AES-256-GCM ciphertext produced by aes_encrypt.
    The decoded PAN should be used in memory only and never logged.
    """
    key = _get_master_key()
    raw = base64.b64decode(encoded)
    nonce, ct = raw[:12], raw[12:]
    return AESGCM(key).decrypt(nonce, ct, None).decode('utf-8')
