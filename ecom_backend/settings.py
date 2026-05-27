"""
Django settings for ecom_backend project.

Multi-vendor e-commerce backend with microservices architecture
"""
import os
from pathlib import Path
from datetime import timedelta

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-4q0yzei=7pb#6t!!ci347omfcz^au!63yrgcod-eo1!it0y7*='

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['*']

# CSRF trusted origins - required for cross-origin requests from frontend
CSRF_TRUSTED_ORIGINS = [
    'http://localhost:3000',
    'http://localhost:5173', 
    'http://localhost:8080',
    'http://127.0.0.1:3000',
    'http://127.0.0.1:5173',
    'http://127.0.0.1:8080',
]


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third party apps
    'graphene_django',
    'django_filters',
    'corsheaders',
    
    # Services (as Django apps)
    'user_service',
    'product_service',
    'cart_service',
    'checkout_service',
    'order_service',
    'payment_service',
    'shipping_service',
    'notification_service',
    'search_service',
    'wishlist_service',
    'returns_service',
    'review_service',
    'chat_service',
    'wallet_service',
    'gateway_service',
    'vendor_storefront',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # Performance optimizations
    'ecom_backend.graphql_middleware.QueryDepthMiddleware',
]

ROOT_URLCONF = 'ecom_backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'ecom_backend.wsgi.application'


# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/

STATIC_URL = 'static/'

# Media files
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
# https://docs.djangoproject.com/en/6.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom user model
AUTH_USER_MODEL = 'user_service.User'

# GraphQL Settings
GRAPHENE = {
    'SCHEMA': 'gateway_service.gateway_schema.gateway_schema',
    'MIDDLEWARE': [
        'graphene_django.debug.DjangoDebugMiddleware',
    ],
    'CAMELCASE_ERRORS': True,
    'RELAY_ENABLED': True,
    'ATOMIC_MUTATIONS': False,
}

# JWT Settings
GRAPHQL_JWT = {
    'JWT_VERIFY_EXPIRATION': True,
    'JWT_EXPIRATION_DELTA': timedelta(hours=24),
    'JWT_ALGORITHM': 'HS256',
}

# CORS Settings
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True

# CORS_ALLOWED_ORIGINS = [
#     'http://localhost:3000',
#     'http://localhost:5173',
#     'http://127.0.0.1:3000',
#     'http://127.0.0.1:5173',
# ]

# Service URLs (for inter-service communication)
SERVICE_URLS = {
    'user_service': 'http://localhost:8001',
    'product_service': 'http://localhost:8002',
    'order_service': 'http://localhost:8003',
    'payment_service': 'http://localhost:8004',
    'shipping_service': 'http://localhost:8005',
    'notification_service': 'http://localhost:8006',
}

# External system integration endpoints/tokens
PAYMENT_SYSTEM_WEBHOOK_URL = os.environ.get('PAYMENT_SYSTEM_WEBHOOK_URL', 'http://localhost:8010')
SHIPPING_SYSTEM_WEBHOOK_URL = os.environ.get('SHIPPING_SYSTEM_WEBHOOK_URL', 'http://localhost:8020')
ERP_SYSTEM_WEBHOOK_URL = os.environ.get('ERP_SYSTEM_WEBHOOK_URL', 'http://localhost:8030')
INTEGRATION_SHARED_TOKEN = os.environ.get('INTEGRATION_SHARED_TOKEN', '')

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'DEBUG' if DEBUG else 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'ecom_backend': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}

# File upload settings
FILE_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10MB

# Cache settings - Redis for performance
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/1'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'CONNECTION_POOL_KWARGS': {'max_connections': 50},
            'SOCKET_CONNECT_TIMEOUT': 5,
            'SOCKET_TIMEOUT': 5,
            'COMPRESSOR': 'django_redis.compressors.zlib.ZlibCompressor',
            'IGNORE_EXCEPTIONS': True,
        },
        'KEY_PREFIX': 'ecom',
        'TIMEOUT': 300,  # 5 minutes default TTL
    },
    'products': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/1'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
        'KEY_PREFIX': 'products',
        'TIMEOUT': 3600,  # 1 hour for products
    },
    'categories': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/1'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
        'KEY_PREFIX': 'categories',
        'TIMEOUT': 7200,  # 2 hours for categories
    },
}

# If Redis cache backend/options are incompatible in local/dev environments,
# gracefully fall back to in-memory cache so GraphQL queries still work.
if os.environ.get('DISABLE_REDIS_CACHE', '0') == '1':
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'ecom-default',
        },
        'products': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'ecom-products',
        },
        'categories': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'ecom-categories',
        },
    }

# Session settings
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_AGE = 86400  # 24 hours
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG

# ===================
# Event Bus / Celery
# ===================
SYSTEM_NAME = os.environ.get('SYSTEM_NAME', 'ecommerce')

CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'amqp://guest:guest@localhost:5672//')
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'rpc://')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'

# Queue this system listens on
EVENT_BUS_QUEUE = os.environ.get('EVENT_BUS_QUEUE', 'ecommerce.events')

# Target queues this system can publish to (shared RabbitMQ cluster)
EVENT_BUS_TARGET_QUEUES = [
    'ecommerce.events',
    'payment.events',
    'shipping.events',
    'erp.events',
]

CELERY_TASK_ROUTES = {
    'event_bus.consume_event': {'queue': EVENT_BUS_QUEUE},
}

# ─────────────────────────────────────────────
# Celery Beat — Automated Vendor Payout Schedule
# ─────────────────────────────────────────────
from celery.schedules import crontab  # noqa: E402

CELERY_BEAT_SCHEDULE = {
    # Daily vendor payouts — 23:55 Africa/Lusaka every day
    'ecommerce-daily-payouts': {
        'task': 'payment_service.dispatch_daily_payouts',
        'schedule': crontab(hour=23, minute=55),
    },
    # Weekly vendor payouts — every Monday 23:55
    'ecommerce-weekly-payouts': {
        'task': 'payment_service.dispatch_weekly_payouts',
        'schedule': crontab(hour=23, minute=55, day_of_week=1),
    },
    # Monthly vendor payouts — 1st of each month 23:55
    'ecommerce-monthly-payouts': {
        'task': 'payment_service.dispatch_monthly_payouts',
        'schedule': crontab(hour=23, minute=55, day_of_month=1),
    },
}

CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'
