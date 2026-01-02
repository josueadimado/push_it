"""
URL configuration for pushit project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls")),
    # Custom admin/operations dashboard (separate from Django admin)
    path("ops/", include("operations.urls")),
    # Brand & influencer dashboards
    path("brand/", include("brands.urls")),
    path("influencer/", include("influencers.urls")),
    # Auth: signup/login for brands & influencers
    path("accounts/", include("accounts.urls")),
    # Payment callbacks and webhooks
    path("payments/", include("payments.urls")),
]

# Serve static and media files
if settings.DEBUG:
    # Development: Use Django's static file serving
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
else:
    # Production: Fallback to serve static files if web server isn't configured
    # Note: Ideally, configure your web server (nginx/Apache) to serve static files for better performance
    # This is a temporary solution if web server configuration isn't available
    import os
    
    # Only add static file serving if directories exist
    if os.path.exists(settings.STATIC_ROOT) and os.path.isdir(settings.STATIC_ROOT):
        urlpatterns += [
            re_path(r'^static/(?P<path>.*)$', serve, {'document_root': settings.STATIC_ROOT, 'show_indexes': False}),
        ]
    if os.path.exists(settings.MEDIA_ROOT) and os.path.isdir(settings.MEDIA_ROOT):
        urlpatterns += [
            re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT, 'show_indexes': False}),
        ]
