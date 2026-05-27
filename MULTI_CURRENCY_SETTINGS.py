"""
Multi-Currency Configuration Settings
Add these settings to your Django settings.py file
"""

# ============================================================================
# MULTI-CURRENCY CONFIGURATION
# ============================================================================

# Enable/disable multi-currency support
CURRENCIES_ENABLED = True

# Default currency for the system
DEFAULT_CURRENCY = 'USD'

# List of supported currencies (ISO 4217 codes)
SUPPORTED_CURRENCIES = [
    'USD',  # United States Dollar
    'EUR',  # Euro
    'GBP',  # British Pound
    'JPY',  # Japanese Yen
    'ZMW',  # Zambian Kwacha
    'ZAR',  # South African Rand
    'CAD',  # Canadian Dollar
    'AUD',  # Australian Dollar
    'INR',  # Indian Rupee
    'NGN',  # Nigerian Naira
]

# Currency API Configuration
# Supported providers: 'openexchangerates', 'fixer', 'manual'
CURRENCY_API_PROVIDER = 'openexchangerates'

# API keys for currency providers (store securely in environment variables)
CURRENCY_API_KEY = ''  # Set via environment variable: CURRENCY_API_KEY

# Cache exchange rates for this duration (in seconds)
CURRENCY_CACHE_TIMEOUT = 86400  # 24 hours

# Cache key prefix for currency operations
CURRENCY_CACHE_PREFIX = 'currency_'

# ============================================================================
# CURRENCY FORMATTING CONFIGURATION
# ============================================================================

# Currency symbol positions
# Options: 'before' (e.g., $100) or 'after' (e.g., 100 $)
CURRENCY_SYMBOL_POSITIONS = {
    'USD': 'before',   # $100.00
    'EUR': 'after',    # 100,00 €
    'GBP': 'before',   # £100.00
    'JPY': 'before',   # ¥100
    'ZMW': 'after',    # 100 ZK
    'ZAR': 'before',   # R100.00
    'CAD': 'before',   # CA$100.00
    'AUD': 'before',   # A$100.00
    'INR': 'before',   # ₹100.00
    'NGN': 'before',   # ₦100.00
}

# Decimal places per currency
CURRENCY_DECIMAL_PLACES = {
    'USD': 2,
    'EUR': 2,
    'GBP': 2,
    'JPY': 0,  # Japanese Yen doesn't use decimal places
    'ZMW': 2,
    'ZAR': 2,
    'CAD': 2,
    'AUD': 2,
    'INR': 2,
    'NGN': 2,
}

# Thousand separators per locale
CURRENCY_THOUSAND_SEPARATORS = {
    'USD': ',',
    'EUR': '.',  # European style
    'GBP': ',',
    'JPY': ',',
    'ZMW': ',',
    'ZAR': ',',
    'CAD': ',',
    'AUD': ',',
    'INR': ',',
    'NGN': ',',
}

# Decimal separators per locale
CURRENCY_DECIMAL_SEPARATORS = {
    'USD': '.',
    'EUR': ',',  # European style
    'GBP': '.',
    'JPY': '.',
    'ZMW': '.',
    'ZAR': '.',
    'CAD': '.',
    'AUD': '.',
    'INR': '.',
    'NGN': '.',
}

# ============================================================================
# TAX CONFIGURATION
# ============================================================================

# Enable tax calculations
TAX_ENABLED = True

# Default tax rate (fallback when no specific rate is found)
DEFAULT_TAX_RATE = 0.0

# Include shipping in taxable amount
TAX_INCLUDES_SHIPPING = True

# Tax-free shipping threshold (amount above which shipping is not taxed)
TAX_FREE_SHIPPING_THRESHOLD = None  # Set to Decimal('100.00') to disable tax on shipping over $100

# VAT/GST settings for different regions
VAT_RATES = {
    'GB': 20.0,    # UK VAT
    'DE': 19.0,    # German VAT
    'FR': 20.0,    # French VAT
    'IT': 22.0,    # Italian VAT
    'ES': 21.0,    # Spanish VAT
    'NL': 21.0,    # Dutch VAT
    'PL': 23.0,    # Polish VAT
    'SE': 25.0,    # Swedish VAT
    'DK': 25.0,    # Danish VAT
    'NO': 25.0,    # Norwegian VAT
}

# Regional tax configurations (country -> list of tax rates)
REGIONAL_TAX_RATES = {
    'US': [
        {'state': 'CA', 'rate': 8.25},
        {'state': 'TX', 'rate': 8.25},
        {'state': 'NY', 'rate': 8.875},
        {'state': 'FL', 'rate': 6.0},
    ],
    'GB': [
        {'state': '', 'rate': 20.0},  # Standard VAT
    ],
    'DE': [
        {'state': '', 'rate': 19.0},  # Standard VAT
    ],
}

# ============================================================================
# SHIPPING COST CONFIGURATION
# ============================================================================

# Base shipping costs by currency
BASE_SHIPPING_COSTS = {
    'USD': 10.00,
    'EUR': 9.20,
    'GBP': 7.90,
    'JPY': 1100.00,
    'ZMW': 208.50,
}

# Free shipping threshold (amount above which shipping is free)
FREE_SHIPPING_THRESHOLD = {
    'USD': 100.00,
    'EUR': 92.00,
    'GBP': 79.00,
    'JPY': 11000.00,
}

# Weight-based shipping multiplier
SHIPPING_WEIGHT_MULTIPLIER = {
    'USD': 1.00,  # $1 per kg
    'EUR': 0.92,  # €0.92 per kg
    'GBP': 0.79,  # £0.79 per kg
}

# ============================================================================
# PAYMENT PROCESSING CONFIGURATION
# ============================================================================

# Currencies supported by payment gateway
PAYMENT_GATEWAY_CURRENCIES = {
    'stripe': ['USD', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD'],
    'paypal': ['USD', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD', 'INR'],
    'razorpay': ['INR'],
    'payu': ['ZAR', 'NGN'],
}

# Currency conversion fees (percentage)
CURRENCY_CONVERSION_FEE = 0.5  # 0.5% fee for automatic conversions

# ============================================================================
# EXCHANGE RATE CONFIGURATION
# ============================================================================

# Exchange rate update schedule (cron format)
EXCHANGE_RATE_UPDATE_SCHEDULE = {
    'hour': 0,      # Midnight
    'minute': 0,
    'timezone': 'UTC'
}

# Minimum exchange rate age before warning (in days)
EXCHANGE_RATE_MAX_AGE_WARNING = 1

# Maximum exchange rate age before blocking (in days)
EXCHANGE_RATE_MAX_AGE_BLOCKING = 7

# Automatically create missing exchange rates by reversing known rates
AUTO_CREATE_REVERSE_RATES = True

# Fallback strategy when exchange rate is not available
# Options: 'error', 'use_last_known', 'use_default', 'manual'
EXCHANGE_RATE_FALLBACK_STRATEGY = 'use_last_known'

# ============================================================================
# CUSTOMER PREFERENCES CONFIGURATION
# ============================================================================

# Auto-detect customer currency from IP geolocation
AUTO_DETECT_CURRENCY = True

# Store customer currency preference in profile
SAVE_CUSTOMER_CURRENCY_PREFERENCE = True

# Default currency for new customers
NEW_CUSTOMER_DEFAULT_CURRENCY = 'USD'

# ============================================================================
# INVENTORY AND PRICING CONFIGURATION
# ============================================================================

# Update all currency prices when base price changes
AUTO_UPDATE_CURRENCY_PRICES = False  # Manual is recommended

# Allow vendors to set custom prices per currency
ALLOW_CUSTOM_CURRENCY_PRICING = True

# Require approval for custom currency prices
REQUIRE_APPROVAL_FOR_CUSTOM_PRICING = False

# Automatically convert prices on currency creation
AUTO_CONVERT_ON_CURRENCY_CREATION = True

# ============================================================================
# AUDIT AND LOGGING CONFIGURATION
# ============================================================================

# Log all currency conversions
LOG_CURRENCY_CONVERSIONS = True

# Log all exchange rate updates
LOG_EXCHANGE_RATE_UPDATES = True

# Log all tax calculations
LOG_TAX_CALCULATIONS = True

# Log level for currency operations
CURRENCY_LOG_LEVEL = 'INFO'  # DEBUG, INFO, WARNING, ERROR

# ============================================================================
# INTEGRATION WITH INSTALLED APPS
# ============================================================================

# Add these apps to INSTALLED_APPS in settings.py
# (Assuming ecom_backend is in PYTHONPATH)
INSTALLED_APPS = [
    # ... other apps ...
    'ecom_backend',  # For multi_currency models
    'product_service',
    'order_service',
    'payment_service',
    'shipping_service',
    'notification_service',
    'user_service',
    'gateway_service',
]

# ============================================================================
# DATABASE CONFIGURATION
# ============================================================================

# For PostgreSQL (recommended for production):
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'ecommerce_db',
        'USER': 'postgres',
        'PASSWORD': 'password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

# For SQLite (development):
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.sqlite3',
#         'NAME': BASE_DIR / 'db.sqlite3',
#     }
# }

# ============================================================================
# CACHING CONFIGURATION
# ============================================================================

# Redis cache (recommended)
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 50,
                'retry_on_timeout': True,
            }
        },
        'KEY_PREFIX': 'ecommerce',
        'TIMEOUT': 300,  # Default timeout
    }
}

# Local memory cache (for development)
# CACHES = {
#     'default': {
#         'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
#         'LOCATION': 'unique-snowflake',
#     }
# }

# ============================================================================
# CELERY CONFIGURATION (for async tasks like exchange rate updates)
# ============================================================================

# Celery broker configuration
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'

# Celery beat schedule (for periodic tasks)
CELERY_BEAT_SCHEDULE = {
    'update-exchange-rates': {
        'task': 'ecom_backend.tasks.update_exchange_rates',
        'schedule': {'hour': 0, 'minute': 0},  # Daily at midnight
    },
}

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/currency.log',
            'maxBytes': 1024 * 1024 * 10,  # 10MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'ecom_backend.multi_currency': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True,
        },
        'ecom_backend.pricing_utils': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}

# ============================================================================
# SECURITY CONFIGURATION
# ============================================================================

# Protect currency conversion endpoints with authentication
CURRENCY_ENDPOINTS_REQUIRE_AUTH = True

# Rate limiting for exchange rate API calls (requests per hour)
CURRENCY_API_RATE_LIMIT = 1000

# ============================================================================
# PERFORMANCE TUNING
# ============================================================================

# Batch size for bulk exchange rate updates
EXCHANGE_RATE_BATCH_SIZE = 100

# Query optimization: use select_related and prefetch_related
USE_QUERY_OPTIMIZATION = True

# Number of items to fetch per page in list views
DEFAULT_PAGINATION_SIZE = 20

# ============================================================================
# EXAMPLE USAGE IN SETTINGS.PY
# ============================================================================

# At the top of your settings.py:
# from pathlib import Path
# from .multi_currency_settings import *

# Or import specific settings:
# CURRENCIES_ENABLED = True
# DEFAULT_CURRENCY = 'USD'
# SUPPORTED_CURRENCIES = ['USD', 'EUR', 'GBP']
# etc.

# ============================================================================
# ENVIRONMENT VARIABLES
# ============================================================================

# Set these in your .env file or system environment:
# CURRENCY_API_KEY=your_api_key_here
# CURRENCY_API_PROVIDER=openexchangerates
# DATABASE_URL=postgresql://user:password@localhost/dbname
# REDIS_URL=redis://localhost:6379/0

# Example .env file:
# CURRENCY_API_PROVIDER=openexchangerates
# CURRENCY_API_KEY=your_open_exchange_rates_api_key
# DEFAULT_CURRENCY=USD
# ALLOWED_HOSTS=localhost,127.0.0.1,example.com
# DEBUG=False
# SECRET_KEY=your-secret-key
# DATABASE_URL=postgresql://postgres:password@localhost/ecommerce_db
# REDIS_URL=redis://localhost:6379/0
