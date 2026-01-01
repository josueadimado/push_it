from .base import *

DEBUG = True

ALLOWED_HOSTS = [
    'localhost',
    '127.0.0.1',
    'noninterpolating-rosemary-techily.ngrok-free.dev',
    '.ngrok-free.dev',  # Allow any ngrok free domain
    '.ngrok.io',  # Allow any ngrok domain
]

# CSRF trusted origins for ngrok and localhost
# Note: Django doesn't support wildcards in CSRF_TRUSTED_ORIGINS
# If your ngrok URL changes, update this list
CSRF_TRUSTED_ORIGINS = [
    'https://noninterpolating-rosemary-techily.ngrok-free.dev',
    'http://localhost:8000',
    'http://127.0.0.1:8000',
]

# Trust proxy headers from ngrok (for HTTPS detection)
# This tells Django to trust the X-Forwarded-Proto header from ngrok
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_TLS = True  # Force HTTPS when behind proxy


