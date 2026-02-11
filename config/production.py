# Create novaedge/settings/production.py

import os
import environ
from pathlib import Path
from datetime import timedelta

env = environ.Env(
    DEBUG=(bool, False)
)

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Read .env file
env_file = os.path.join(BASE_DIR, '.env')
if os.path.exists(env_file):
    env.read_env(env_file)

# =============================================================================
# PRODUCTION SECURITY SETTINGS
# =============================================================================

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

# Hosts
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['api.novaedgefinance.com'])

# Database
DATABASES = {
    'default': env.db('DATABASE_URL')
}

# =============================================================================
# SECURITY MIDDLEWARE
# =============================================================================

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# =============================================================================
# HTTPS/SSL SETTINGS
# =============================================================================

SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'

# =============================================================================
# CORS SETTINGS
# =============================================================================

CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS', default=[
    'https://novaedgefinance.com',
    'https://www.novaedgefinance.com',
    'https://admin.novaedgefinance.com'
])

CORS_ALLOW_CREDENTIALS = True
CORS_EXPOSE_HEADERS = ['Content-Type', 'X-Content-Type-Options']

# =============================================================================
# CSRF SETTINGS
# =============================================================================

CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS', default=[
    'https://novaedgefinance.com',
    'https://www.novaedgefinance.com'
])

# =============================================================================
# JWT SETTINGS
# =============================================================================

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# =============================================================================
# NOWPAYMENTS CONFIGURATION
# =============================================================================

NOWPAYMENTS_API_KEY = env('NOWPAYMENTS_API_KEY')
NOWPAYMENTS_IPN_SECRET = env('NOWPAYMENTS_IPN_SECRET')
NOWPAYMENTS_BASE_URL = env('NOWPAYMENTS_BASE_URL', default='https://api.nowpayments.io/v1')

# =============================================================================
# EMAIL CONFIGURATION
# =============================================================================

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = env('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = env.int('EMAIL_PORT', default=587)
EMAIL_USE_TLS = env.bool('EMAIL_USE_TLS', default=True)
EMAIL_HOST_USER = env('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='noreply@novaedgefinance.com')
SERVER_EMAIL = env('SERVER_EMAIL', default='alerts@novaedgefinance.com')

# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {asctime} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'novaedge.log'),
            'maxBytes': 10485760,  # 10MB
            'backupCount': 10,
            'formatter': 'verbose',
        },
        'error_file': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'error.log'),
            'maxBytes': 10485760,
            'backupCount': 10,
            'formatter': 'verbose',
        },
        'payments_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'payments.log'),
            'maxBytes': 10485760,
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'error_file'],
            'level': 'INFO',
            'propagate': True,
        },
        'wallet': {
            'handlers': ['file', 'payments_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'investments': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': False,
        },
        'reporting': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# =============================================================================
# STATIC & MEDIA FILES (for Render)
# =============================================================================

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# =============================================================================
# CELERY CONFIGURATION (for async tasks)
# =============================================================================

CELERY_BROKER_URL = env('REDIS_URL', default='redis://localhost:6379')
CELERY_RESULT_BACKEND = env('REDIS_URL', default='redis://localhost:6379')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'

# =============================================================================
# SITE URLS
# =============================================================================

SITE_URL = env('SITE_URL', default='https://api.novaedgefinance.com')
FRONTEND_URL = env('FRONTEND_URL', default='https://novaedgefinance.com')

# =============================================================================
# APP SPECIFIC SETTINGS
# =============================================================================

# Referral settings
REFERRAL_BONUS_AMOUNT = env.decimal('REFERRAL_BONUS_AMOUNT', default=5.00)
REFERRAL_MIN_DEPOSIT = env.decimal('REFERRAL_MIN_DEPOSIT', default=10.00)

# Investment settings
INVESTMENT_DAILY_LIMIT = env.decimal('INVESTMENT_DAILY_LIMIT', default=10000.00)
INVESTMENT_AUTO_COMPOUND = env.bool('INVESTMENT_AUTO_COMPOUND', default=True)

# Security settings
MAX_FAILED_LOGIN_ATTEMPTS = env.int('MAX_FAILED_LOGIN_ATTEMPTS', default=5)
ACCOUNT_LOCKOUT_MINUTES = env.int('ACCOUNT_LOCKOUT_MINUTES', default=15)

# =============================================================================
# SENTRY CONFIGURATION (Error tracking)
# =============================================================================

SENTRY_DSN = env('SENTRY_DSN', default=None)
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.celery import CeleryIntegration
    
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration(), CeleryIntegration()],
        traces_sample_rate=0.1,
        send_default_pii=False,
        environment="production",
    )
