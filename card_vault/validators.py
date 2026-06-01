"""Card data validators: Luhn algorithm and card brand detection."""
import re
from datetime import datetime


def luhn_check(pan: str) -> bool:
    """Return True if the PAN passes the Luhn checksum."""
    digits = [int(d) for d in pan if d.isdigit()]
    if not (13 <= len(digits) <= 19):
        return False
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


_BRANDS = [
    ('visa',       r'^4\d{12}(?:\d{3})?(?:\d{3})?$'),
    ('mastercard', r'^5[1-5]\d{14}$|^2(?:2[2-9][1-9]|[3-6]\d{2}|7[01]\d|720)\d{12}$'),
    ('amex',       r'^3[47]\d{13}$'),
    ('discover',   r'^6(?:011|5\d{2})\d{12}$'),
    ('unionpay',   r'^62\d{14,17}$'),
    ('diners',     r'^3(?:0[0-5]|[68]\d)\d{11}$'),
    ('jcb',        r'^(?:2131|1800|35\d{3})\d{11}$'),
]


def detect_card_brand(pan: str) -> str:
    """Return the card brand name or 'unknown'."""
    clean = re.sub(r'[\s\-]', '', pan)
    for brand, pattern in _BRANDS:
        if re.match(pattern, clean):
            return brand
    return 'unknown'


def validate_expiry(month: int, year: int) -> bool:
    """Return True if the card expiry is in the future."""
    if not (1 <= month <= 12):
        return False
    now = datetime.now()
    return (year, month) >= (now.year, now.month)
