from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings


def generate_verification_token(user):
    """Generate a verification token for a user."""
    return default_token_generator.make_token(user)


def send_verification_email(user, request=None):
    """
    Send email verification email to user.
    
    Args:
        user: User instance to send verification to
        request: HttpRequest object (optional, for building absolute URLs)
    """
    token = generate_verification_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    
    # Build verification URL
    if request:
        verification_url = request.build_absolute_uri(
            f'/accounts/verify-email/{uid}/{token}/'
        )
        # Build logo URL
        logo_url = request.build_absolute_uri('/static/images/logo/Pushit.svg')
    else:
        # Fallback if no request object
        from django.contrib.sites.models import Site
        try:
            current_site = Site.objects.get_current()
            domain = current_site.domain
            protocol = 'https' if getattr(settings, 'USE_HTTPS', False) else 'http'
        except:
            domain = 'localhost:8000'
            protocol = 'http'
        verification_url = f'{protocol}://{domain}/accounts/verify-email/{uid}/{token}/'
        logo_url = f'{protocol}://{domain}/static/images/logo/Pushit.svg'
    
    # Email subject
    subject = 'Verify your PushIt account email'
    
    # Render email template
    context = {
        'user': user,
        'verification_url': verification_url,
        'logo_url': logo_url,
        'site_name': 'PushIt',
    }
    
    # Plain text email
    message = render_to_string('accounts/emails/verification_email.txt', context)
    
    # HTML email
    html_message = render_to_string('accounts/emails/verification_email.html', context)
    
    # Send email
    send_mail(
        subject=subject,
        message=message,
        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@pushit.com'),
        recipient_list=[user.email],
        html_message=html_message,
        fail_silently=False,
    )

