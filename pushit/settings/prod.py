from .base import *

DEBUG = False

# Set ALLOWED_HOSTS - include pushit.now and any additional hosts from environment
ALLOWED_HOSTS = ["pushit.now"]
if os.getenv("DJANGO_ALLOWED_HOSTS"):
    additional_hosts = [host.strip() for host in os.getenv("DJANGO_ALLOWED_HOSTS").split(",") if host.strip()]
    ALLOWED_HOSTS.extend(additional_hosts)

# Static files configuration for production
STATIC_URL = "/static/"
MEDIA_URL = "/media/"


