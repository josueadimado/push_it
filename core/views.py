from django.shortcuts import render
from django.utils import timezone


def home(request):
    """
    Public landing page.

    For now this is a simple placeholder. We will replace the contents of
    templates/landing/home.html with your actual homepage design.
    """
    return render(request, "landing/home.html")


def terms_of_service(request):
    """Terms of Service page."""
    context = {
        'effective_date': timezone.now().strftime('%B %d, %Y'),
    }
    return render(request, "core/terms_of_service.html", context)


def privacy_policy(request):
    """Privacy Policy page."""
    context = {
        'effective_date': timezone.now().strftime('%B %d, %Y'),
    }
    return render(request, "core/privacy_policy.html", context)

