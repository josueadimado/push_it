from django.shortcuts import render


def home(request):
    """
    Public landing page.

    For now this is a simple placeholder. We will replace the contents of
    templates/landing/home.html with your actual homepage design.
    """
    return render(request, "landing/home.html")

