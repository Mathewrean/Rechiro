import os
from pathlib import Path
import importlib.util
try:
    from decouple import config
except Exception:
    def config(name, default=None, cast=str):
        value = os.environ.get(name, default)
        if cast is bool:
            if isinstance(value, bool):
                return value
            return str(value).lower() in {"1", "true", "yes", "on"}
        try:
            return cast(value) if cast and value is not None else value
        except Exception:
            return value

BASE_DIR = Path(__file__).resolve().parent.parent


SECRET_KEY = config('SECRET_KEY', default=os.environ.get('SECRET_KEY', 'django-insecure-change-in-production'))

def _parse_bool(value):
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "y", "on", "debug"}:
        return True
    if normalized in {"0", "false", "no", "n", "off", "release", "prod", "production"}:
        return False
    return False

DEBUG = config('DEBUG', default=False, cast=_parse_bool)

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default="*").split(',')
if "*" not in ALLOWED_HOSTS and not DEBUG:
    ALLOWED_HOSTS.append("*.onrender.com")
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://0.0.0.0:8000",
    "http://127.0.1:8000",
    "https://albert-incult-superfluously.ngrok-free.dev",
    "https://rechiro-production.up.railway.app",
    "https://*.onrender.com",
    "https://rechiro.onrender.com",
]
CORS_ALLOWED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.1:8000",
    "https://sustainablefishing.onrender.com",
    "https://rechiro-production.up.railway.app",
    "https://*.ngrok.io",
    "https://*.ngrok-free.app",
    "https://*.ngrok-free.dev",
    "https://*.ngrok.app",
    "https://albert-incult-superfluously.ngrok-free.dev",
    "https://*.onrender.com",
    "https://rechiro.onrender.com",
]


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "users",
    "fishing",
    # content app removed - e-commerce only platform
]

ALLAUTH_INSTALLED = importlib.util.find_spec("allauth") is not None
if ALLAUTH_INSTALLED:
    INSTALLED_APPS += [
        "allauth",
        "allauth.account",
        "allauth.socialaccount",
        "allauth.socialaccount.providers.google",
    ]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
if importlib.util.find_spec("whitenoise") is not None:
    MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")
if ALLAUTH_INSTALLED:
    MIDDLEWARE.insert(6, "allauth.account.middleware.AccountMiddleware")

ROOT_URLCONF = "rechiro.urls"

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

WSGI_APPLICATION = "rechiro.wsgi.application"


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': str(BASE_DIR / 'db.sqlite3'),
    }
}

# For Render, ensure database directory is writable
try:
    db_path = Path(DATABASES['default']['NAME']).parent
    db_path.mkdir(parents=True, exist_ok=True)
except Exception:
    pass

# Override database configuration if DATABASE_URL is provided (for production)
if 'DATABASE_URL' in os.environ:
    if importlib.util.find_spec("dj_database_url") is not None:
        import dj_database_url
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

STATIC_ROOT = str(BASE_DIR / "staticfiles")
if importlib.util.find_spec("whitenoise") is not None:
    manifest_path = BASE_DIR / "staticfiles" / "staticfiles.json"
    if manifest_path.exists():
        STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
    else:
        STATICFILES_STORAGE = "whitenoise.storage.CompressedStaticFilesStorage"
    WHITENOISE_USE_FINDERS = True

MEDIA_URL = '/media/'
MEDIA_ROOT = str(BASE_DIR / 'media')


DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = 'users.User'
SITE_ID = 1

AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.ModelBackend"]
if ALLAUTH_INSTALLED:
    AUTHENTICATION_BACKENDS.append("allauth.account.auth_backends.AuthenticationBackend")
AUTHENTICATION_BACKENDS = tuple(AUTHENTICATION_BACKENDS)

LOGIN_REDIRECT_URL = "/users/dashboard/"
LOGOUT_REDIRECT_URL = "/users/login/"

ACCOUNT_LOGIN_METHODS = {"username", "email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "username*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "none"
SOCIALACCOUNT_LOGIN_ON_GET = True
GOOGLE_CLIENT_ID = config('GOOGLE_CLIENT_ID', default='')
GOOGLE_CLIENT_SECRET = config('GOOGLE_CLIENT_SECRET', default='')

SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
    }
}
if ALLAUTH_INSTALLED:
    SOCIALACCOUNT_ADAPTER = "users.adapters.RechiroSocialAccountAdapter"
    SOCIALACCOUNT_SIGNUP_FORM_CLASS = "users.adapters.RechiroSocialSignupForm"

CSRF_FAILURE_VIEW = "users.views.csrf_failure_view"

SITE_URL = config('SITE_URL', default='https://rechiro.onrender.com')

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Security hardening (enable for production via environment variables)
# Admin configuration
ADMIN_USERNAME = config("ADMIN_USERNAME", default="")
ADMIN_EMAIL = config("ADMIN_EMAIL", default="")
ADMIN_PASSWORD = config("ADMIN_PASSWORD", default="")

SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=False, cast=_parse_bool)
SESSION_COOKIE_SECURE = config('SESSION_COOKIE_SECURE', default=False, cast=_parse_bool)
CSRF_COOKIE_SECURE = config('CSRF_COOKIE_SECURE', default=False, cast=_parse_bool)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'

# Email configuration - use console backend as fallback when SMTP not configured
EMAIL_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@rechiro.com')

# SMTP settings for production
EMAIL_HOST = config('EMAIL_HOST', default='')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')

# Use SMTP only if credentials are provided
if EMAIL_HOST and EMAIL_HOST_USER and EMAIL_HOST_PASSWORD:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'

# M-Pesa Daraja API Configuration
# Get these from Safaricom Developer Portal
# Consumer Key: FcbgCgnnIxIEY9fFWRl9PFXB15xgPqEUl9AIa3mIbGgPbTOg
# Consumer Secret: e8M2xIKQo7ppCF3rKJdcR4XxYYw04LJa7HlVm8IDXmo8pPxzPoRp4jQcg2WiJxe8
MPESA_CONSUMER_KEY = config('MPESA_CONSUMER_KEY', default='')
MPESA_CONSUMER_SECRET = config('MPESA_CONSUMER_SECRET', default='')
MPESA_BUSINESS_SHORT_CODE = config('MPESA_BUSINESS_SHORT_CODE', default='')
MPESA_PASSKEY = config('MPESA_PASSKEY', default='')
MPESA_CALLBACK_URL = config('MPESA_CALLBACK_URL', default='')
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


# Create logs directory if it doesn't exist (skip during build/static collection)
try:
    os.makedirs(BASE_DIR / 'logs', exist_ok=True)
except (OSError, PermissionError):
    pass

# Create media directory if it doesn't exist
try:
    os.makedirs(BASE_DIR / 'media', exist_ok=True)
except (OSError, PermissionError):
    pass

# Ensure staticfiles directory exists
try:
    os.makedirs(BASE_DIR / 'staticfiles', exist_ok=True)
except (OSError, PermissionError):
    pass

# Security Settings for Production
if not DEBUG:
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    # SECURE_SSL_REDIRECT disabled - Render handles SSL termination
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
else:
    # For development/testing
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
