import os
from pathlib import Path
import dj_database_url
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent


SECRET_KEY = config('SECRET_KEY', default="django-insecure-ki)+%eng&-v5u$z%5_7^=o#gm3i(muw2$_8t)_)$uht=$i8nmp")

DEBUG = config('DEBUG', default=True, cast=bool)

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default="*").split(',')
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.1:8000",
    "https://sustainablefishing.onrender.com",
    "https://*.ngrok.io",
    "https://*.ngrok-free.app",
    "https://*.ngrok.app",
]
CORS_ALLOWED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.1:8000",
    "https://sustainablefishing.onrender.com",
    "https://*.ngrok.io",
    "https://*.ngrok-free.app",
    "https://*.ngrok.app",
]


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "users",
    "fishing",
    # content app removed - e-commerce only platform
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "sustainable_fishing.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "users.admin_utils.admin_statistics_context",
                "users.admin_utils.cart_context",
            ],
        },
    },
]

WSGI_APPLICATION = "sustainable_fishing.wsgi.application"


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Override database configuration if DATABASE_URL is provided (for production)
if 'DATABASE_URL' in os.environ:
    DATABASES['default'] = dj_database_url.parse(os.environ.get('DATABASE_URL'))
    DATABASES['default']['CONN_MAX_AGE'] = 600
    DATABASES['default']['CONN_HEALTH_CHECKS'] = True


AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Nairobi"
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')


DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = 'users.User'

 
# M-Pesa Daraja API Configuration
# Get these from Safaricom Developer Portal
# Consumer Key: FcbgCgnnIxIEY9fFWRl9PFXB15xgPqEUl9AIa3mIbGgPbTOg
# Consumer Secret: e8M2xIKQo7ppCF3rKJdcR4XxYYw04LJa7HlVm8IDXmo8pPxzPoRp4jQcg2WiJxe8
MPESA_CONSUMER_KEY = config('MPESA_CONSUMER_KEY', default='FcbgCgnnIxIEY9fFWRl9PFXB15xgPqEUl9AIa3mIbGgPbTOg')
MPESA_CONSUMER_SECRET = config('MPESA_CONSUMER_SECRET', default='e8M2xIKQo7ppCF3rKJdcR4XxYYw04LJa7HlVm8IDXmo8pPxzPoRp4jQcg2WiJxe8')
MPESA_BUSINESS_SHORT_CODE = config('MPESA_BUSINESS_SHORT_CODE', default='8501360')
MPESA_PASSKEY = config('MPESA_PASSKEY', default='bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919')
MPESA_CALLBACK_URL = config('MPESA_CALLBACK_URL', default='https://05fc-41-90-11-251.ngrok-free.app/api/mpesa/callback/')
MPESA_BASE_URL = config('MPESA_BASE_URL', default='https://sandbox.safaricom.co.ke')

# For B2C payments (refunds)
MPESA_INITIATOR_NAME = config('MPESA_INITIATOR_NAME', default='')
MPESA_SECURITY_CREDENTIAL = config('MPESA_SECURITY_CREDENTIAL', default='')


# Logging Configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs/mpesa.log',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'fishing': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True,
        },
        'mpesa': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}


# Create logs directory if it doesn't exist
os.makedirs(BASE_DIR / 'logs', exist_ok=True)

