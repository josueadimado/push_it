from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Load environment variables from .env file if it exists
# Install python-decouple: pip install python-decouple
USE_DECOUPLE = False
try:
    from decouple import config
    USE_DECOUPLE = True
except (ImportError, Exception):
    # If decouple is not installed or fails for any reason (permissions, etc.), 
    # fallback to os.getenv
    USE_DECOUPLE = False
    def config(key, default=None):
        return os.getenv(key, default)

SECRET_KEY = config(
    "DJANGO_SECRET_KEY",
    default="dev-secret-key-change-in-production",
)

DEBUG = False

ALLOWED_HOSTS: list[str] = []

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",  # For human-readable time formatting
    # Project apps
    "core",
    "accounts",
    "brands",
    "influencers",
    "campaigns",
    "payments",
    "operations",
    "api",
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

ROOT_URLCONF = "pushit.urls"

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
            ],
        },
    },
]

WSGI_APPLICATION = "pushit.wsgi.application"
ASGI_APPLICATION = "pushit.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

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
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Use our custom user model with role support
AUTH_USER_MODEL = "accounts.User"

# Email Configuration
# For development, emails are printed to console
# For production, configure SMTP settings
EMAIL_BACKEND = config(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend"  # Console backend for development
)
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="noreply@pushit.com")
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# SMTP Settings (for production)
EMAIL_HOST = config("EMAIL_HOST", default="")
EMAIL_PORT = int(config("EMAIL_PORT", default="587"))
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default="True").lower() == "true"
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")

# Platform API Keys for Follower Verification
YOUTUBE_API_KEY = config("YOUTUBE_API_KEY", default="")

# Instagram & Facebook API Configuration (Instagram Graph API)
# These use the Facebook Graph API since Instagram is owned by Facebook
INSTAGRAM_ACCESS_TOKEN = config("INSTAGRAM_ACCESS_TOKEN", default="")
FACEBOOK_APP_ID = config("FACEBOOK_APP_ID", default="")
FACEBOOK_APP_SECRET = config("FACEBOOK_APP_SECRET", default="")
FACEBOOK_ACCESS_TOKEN = config("FACEBOOK_ACCESS_TOKEN", default="")
FACEBOOK_PAGE_ID = config("FACEBOOK_PAGE_ID", default="")  # Optional: Facebook Page ID if using Instagram

# TikTok OAuth Configuration (TikTok Login Kit)
# Get your keys from: https://developers.tiktok.com/
# Create an app and get Client Key and Client Secret
TIKTOK_CLIENT_KEY = config("TIKTOK_CLIENT_KEY", default="")
TIKTOK_CLIENT_SECRET = config("TIKTOK_CLIENT_SECRET", default="")

# TikTok Business API (optional - for admin-level access)
# TIKTOK_API_KEY = config("TIKTOK_API_KEY", default="")

# RapidAPI Configuration (for Instagram/Facebook scraping)
# Get your key from: https://rapidapi.com/
# Subscribe to: Instagram Scraper API2 or Facebook Profile Scraper
RAPIDAPI_KEY = config("RAPIDAPI_KEY", default="")

# OAuth Redirect URLs (for Facebook/Instagram OAuth)
# These are automatically built from request, but you can override if needed
OAUTH_REDIRECT_BASE_URL = config("OAUTH_REDIRECT_BASE_URL", default="")

# Paystack Payment Gateway Configuration
PAYSTACK_SECRET_KEY = config("PAYSTACK_SECRET_KEY", default="")
PAYSTACK_PUBLIC_KEY = config("PAYSTACK_PUBLIC_KEY", default="")
PAYSTACK_WEBHOOK_SECRET = config("PAYSTACK_WEBHOOK_SECRET", default="")  # Optional: for additional webhook security



