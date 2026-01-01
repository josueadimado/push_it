from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_str
from django.contrib.auth.tokens import default_token_generator

from .forms import (
    BrandSignupForm, InfluencerSignupForm, LoginForm,
    BrandOnboardingForm, InfluencerOnboardingForm, InfluencerPlatformForm
)
from .models import User
from .utils import send_verification_email
from brands.models import Brand
from influencers.models import Influencer, PlatformConnection, PlatformSettings


def signup_brand(request):
    """Signup page for brand/company accounts."""
    if request.user.is_authenticated:
        return redirect("core:home")
    
    if request.method == "POST":
        form = BrandSignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Send verification email
            try:
                send_verification_email(user, request)
            except Exception as e:
                # Log error but don't block signup
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to send verification email: {e}")
                messages.warning(request, "Account created, but verification email could not be sent. Please contact support.")
            
            auth_login(request, user)
            return redirect("accounts:email_verification_sent")
    else:
        form = BrandSignupForm()
    return render(request, "accounts/signup_brand.html", {"form": form})


def signup_influencer(request):
    """Signup page for influencer/creator accounts."""
    if request.user.is_authenticated:
        return redirect("core:home")
    
    if request.method == "POST":
        form = InfluencerSignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Send verification email
            try:
                send_verification_email(user, request)
            except Exception as e:
                # Log error but don't block signup
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to send verification email: {e}")
                messages.warning(request, "Account created, but verification email could not be sent. Please contact support.")
            
            auth_login(request, user)
            return redirect("accounts:email_verification_sent")
    else:
        form = InfluencerSignupForm()
    return render(request, "accounts/signup_influencer.html", {"form": form})


def login_view(request):
    """Shared login for brands & influencers."""
    if request.user.is_authenticated:
        return redirect("core:home")

    if request.method == "POST":
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            auth_login(request, user)
            
            # Refresh user from database to get latest email verification status
            user.refresh_from_db()
            
            # Check email verification (warn but don't block)
            if not user.is_email_verified:
                messages.warning(request, "Please verify your email address to access all features. Check your inbox for the verification link.")
            
            # Route by role - check superuser/staff first for admin access
            if user.is_superuser or user.is_staff or user.role == User.Roles.ADMIN:
                return redirect("operations:admin_dashboard")
            if user.role == User.Roles.BRAND:
                # Check if profile is complete
                try:
                    brand = user.brand_profile
                    if not brand.is_profile_complete:
                        return redirect("accounts:brand_onboarding")
                except Brand.DoesNotExist:
                    return redirect("accounts:brand_onboarding")
                return redirect("brands:dashboard")
            if user.role == User.Roles.INFLUENCER:
                # Check if onboarding is complete
                try:
                    influencer = user.influencer_profile
                    if not influencer.onboarding_completed:
                        return redirect("accounts:influencer_onboarding")
                except Influencer.DoesNotExist:
                    return redirect("accounts:influencer_onboarding")
                return redirect("influencers:dashboard")
            return redirect("core:home")
        else:
            # Try to authenticate with username if email fails
            username_or_email = form.data.get('username', '')
            password = form.data.get('password', '')
            
            # Try authenticating with username first (for admin users)
            from django.contrib.auth import authenticate
            user = authenticate(request, username=username_or_email, password=password)
            
            if user is None:
                # If that fails, try with email (for regular users)
                try:
                    user_obj = User.objects.get(email=username_or_email)
                    user = authenticate(request, username=user_obj.username, password=password)
                except User.DoesNotExist:
                    pass
            
            if user is not None:
                auth_login(request, user)
                # Refresh user from database to get latest email verification status
                user.refresh_from_db()
                
                # Route by role - check superuser/staff first for admin access
                if user.is_superuser or user.is_staff or user.role == User.Roles.ADMIN:
                    return redirect("operations:admin_dashboard")
                if user.role == User.Roles.BRAND:
                    # Check if profile is complete
                    try:
                        brand = user.brand_profile
                        if not brand.is_profile_complete:
                            return redirect("accounts:brand_onboarding")
                    except Brand.DoesNotExist:
                        return redirect("accounts:brand_onboarding")
                    return redirect("brands:dashboard")
                if user.role == User.Roles.INFLUENCER:
                    # Check if onboarding is complete
                    try:
                        influencer = user.influencer_profile
                        if not influencer.onboarding_completed:
                            return redirect("accounts:influencer_onboarding")
                    except Influencer.DoesNotExist:
                        return redirect("accounts:influencer_onboarding")
                    return redirect("influencers:dashboard")
                return redirect("core:home")
            else:
                # Add error to form if both attempts fail
                form.add_error(None, "Invalid email/username or password.")
    else:
        form = LoginForm(request)
    return render(request, "accounts/login.html", {"form": form})


@login_required
def logout_view(request):
    """Logout the user and redirect to home page."""
    auth_logout(request)
    from django.shortcuts import redirect
    return redirect('core:home')
    return redirect("core:home")


# ============ EMAIL VERIFICATION ============

def verify_email(request, uidb64, token):
    """Verify user's email address. Works when clicking or copying the link."""
    import logging
    logger = logging.getLogger(__name__)
    
    # First, try to decode and get the user
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError) as e:
        logger.warning(f"Email verification failed - invalid uidb64 format: {e}")
        messages.error(request, "Invalid verification link. Please request a new one.")
        return redirect("accounts:resend_verification")
    except User.DoesNotExist:
        logger.warning(f"Email verification failed - user not found (uidb64: {uidb64})")
        messages.error(request, "User not found. Please request a new verification link.")
        return redirect("accounts:resend_verification")
    
    # Check if user is already verified
    if user.is_email_verified:
        messages.info(request, "Your email is already verified!")
        # Auto-login if not already logged in, or refresh session if already logged in
        if not request.user.is_authenticated:
            auth_login(request, user)
        elif request.user.id == user.id:
            # User is already logged in - refresh session to ensure latest user data
            auth_login(request, user)
        
        # Redirect based on role
        if user.role == User.Roles.BRAND:
            try:
                brand = user.brand_profile
                if brand.is_profile_complete:
                    return redirect("brands:dashboard")
                else:
                    return redirect("accounts:brand_onboarding")
            except Brand.DoesNotExist:
                return redirect("accounts:brand_onboarding")
        elif user.role == User.Roles.INFLUENCER:
            try:
                influencer = user.influencer_profile
                if influencer.onboarding_completed:
                    return redirect("influencers:dashboard")
                else:
                    return redirect("accounts:influencer_onboarding")
            except Influencer.DoesNotExist:
                return redirect("accounts:influencer_onboarding")
        else:
            return redirect("core:home")
    
    # Verify the token - this is the critical check
    if default_token_generator.check_token(user, token):
        # Token is valid - verify the email
        user.is_email_verified = True
        user.save(update_fields=['is_email_verified'])
        
        logger.info(f"Email verified successfully for user {user.email}")
        
        # Refresh user object from database to ensure we have latest data
        user.refresh_from_db()
        
        # Clear any old messages and show only verification success
        storage = messages.get_messages(request)
        storage.used = True  # Mark all messages as used
        
        messages.success(request, "Email verified successfully!")
        
        # Auto-login if not already logged in, or update session if already logged in
        if not request.user.is_authenticated:
            auth_login(request, user)
        elif request.user.id == user.id:
            # User is already logged in - refresh their session with updated user data
            # This ensures request.user.is_email_verified is updated
            from django.contrib.auth import update_session_auth_hash
            # Refresh the user in the session
            auth_login(request, user)
        
        # Redirect based on role
        if user.role == User.Roles.BRAND:
            try:
                brand = user.brand_profile
                if brand.is_profile_complete:
                    return redirect("brands:dashboard")
                else:
                    return redirect("accounts:brand_onboarding")
            except Brand.DoesNotExist:
                return redirect("accounts:brand_onboarding")
        elif user.role == User.Roles.INFLUENCER:
            try:
                influencer = user.influencer_profile
                if influencer.onboarding_completed:
                    return redirect("influencers:dashboard")
                else:
                    return redirect("accounts:influencer_onboarding")
            except Influencer.DoesNotExist:
                return redirect("accounts:influencer_onboarding")
        else:
            return redirect("core:home")
    else:
        # Token is invalid or expired
        logger.warning(f"Email verification failed for user {user.email} - token mismatch or expired (token: {token[:20]}...)")
        messages.error(request, "Invalid verification link. It may have expired. Please request a new one.")
        return redirect("accounts:resend_verification")


@login_required
def email_verification_sent(request):
    """Page shown after sending verification email."""
    return render(request, "accounts/email_verification_sent.html")


@login_required
def resend_verification(request):
    """Resend verification email."""
    if request.method == "POST":
        if not request.user.is_email_verified:
            try:
                send_verification_email(request.user, request)
                # Clear old messages
                storage = messages.get_messages(request)
                storage.used = True
                messages.success(request, "Verification email sent! Please check your inbox.")
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to resend verification email: {e}")
                messages.error(request, f"Failed to send verification email: {str(e)}. Please check your email settings.")
        else:
            messages.info(request, "Your email is already verified.")
        return redirect("accounts:email_verification_sent")
    
    return render(request, "accounts/resend_verification.html")


# ============ BRAND ONBOARDING ============

@login_required
def brand_onboarding(request):
    """Brand profile completion page."""
    if request.user.role != User.Roles.BRAND:
        return redirect("core:home")
    
    # Get or create brand profile (in case it wasn't created during signup)
    try:
        brand = request.user.brand_profile
    except Brand.DoesNotExist:
        # Create brand profile if it doesn't exist
        brand = Brand.objects.create(user=request.user)
    
    if request.method == "POST":
        form = BrandOnboardingForm(request.POST, instance=brand)
        if form.is_valid():
            brand = form.save()
            # Mark profile as completed
            brand.profile_completed = brand.is_profile_complete
            brand.save()
            
            # Schedule automated verification (delayed 5-10 minutes)
            if brand.is_profile_complete:
                try:
                    from brands.models import BrandVerificationQueue
                    BrandVerificationQueue.schedule_verification(brand)
                    messages.success(request, "Profile completed! Top up your wallet to start posting campaigns.")
                    return redirect("brands:wallet")
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Failed to schedule verification: {e}")
                    messages.info(request, "Profile completed! Top up your wallet to start posting campaigns.")
                    return redirect("brands:wallet")
            else:
                messages.success(request, "Profile updated! Please complete all required fields.")
                return redirect("accounts:brand_onboarding")
    else:
        form = BrandOnboardingForm(instance=brand)
    
    return render(request, "accounts/brand_onboarding.html", {
        "form": form,
        "brand": brand,
    })


@login_required
def brand_verification_pending(request):
    """Page shown while brand verification is pending."""
    if request.user.role != User.Roles.BRAND:
        return redirect("core:home")
    
    try:
        brand = request.user.brand_profile
    except Brand.DoesNotExist:
        return redirect("accounts:brand_onboarding")
    
    if brand.is_verified:
        return redirect("brands:dashboard")
    
    return render(request, "accounts/brand_verification_pending.html", {
        "brand": brand,
    })


# ============ INFLUENCER ONBOARDING ============

@login_required
def influencer_onboarding(request):
    """Influencer onboarding page - connect platforms and complete profile."""
    if request.user.role != User.Roles.INFLUENCER:
        return redirect("core:home")
    
    influencer = get_object_or_404(Influencer, user=request.user)
    platform_connections = influencer.platform_connections.all()
    
    # Handle platform form submission
    if request.method == "POST":
        if 'add_platform' in request.POST:
            platform_form = InfluencerPlatformForm(request.POST, influencer=influencer)
            if platform_form.is_valid():
                platform_conn = platform_form.save()
                messages.success(request, f"{platform_conn.get_platform_display()} account added! Pending verification.")
                return redirect("accounts:influencer_onboarding")
        elif 'complete_onboarding' in request.POST:
            profile_form = InfluencerOnboardingForm(request.POST, instance=influencer)
            if profile_form.is_valid():
                influencer = profile_form.save()
                
                # Check if they have at least one platform connected
                if not influencer.platform_connections.exists():
                    messages.error(request, "Please connect at least one platform before continuing.")
                    return redirect("accounts:influencer_onboarding")
                
                # Allow completion if they have platform, niche, and primary platform
                # Minimum followers will be checked during verification
                influencer.onboarding_completed = True
                influencer.profile_completed = True
                influencer.save()
                
                # Schedule automated verification (delayed 5-10 minutes)
                try:
                    from influencers.models import InfluencerVerificationQueue
                    InfluencerVerificationQueue.schedule_verification(influencer)
                    messages.success(request, "Onboarding completed! Your account is being reviewed and you'll be notified shortly.")
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Failed to schedule verification: {e}")
                    messages.success(request, "Onboarding completed! Your account is pending verification.")
                # Redirect to dashboard - they can access it but tools require verification
                return redirect("influencers:dashboard")
    else:
        platform_form = InfluencerPlatformForm(influencer=influencer)
        profile_form = InfluencerOnboardingForm(instance=influencer)
    
    # Check if onboarding can be completed
    # Allow continuing if at least one platform is connected
    has_platform = platform_connections.exists()
    can_complete = (
        influencer.niche and
        influencer.primary_platform and
        has_platform
    )
    
    # Check if they meet minimum followers (for display purposes)
    meets_requirements = influencer.has_minimum_followers
    
    # Get platform settings for display
    platform_settings = PlatformSettings.objects.filter(is_active=True)
    platform_requirements = {
        setting.platform: setting.minimum_followers 
        for setting in platform_settings
    }
    
    return render(request, "accounts/influencer_onboarding.html", {
        "influencer": influencer,
        "platform_form": platform_form,
        "profile_form": profile_form,
        "platform_connections": platform_connections,
        "can_complete": can_complete,
        "meets_requirements": meets_requirements,
        "has_platform": has_platform,
        "platform_requirements": platform_requirements,
    })


@login_required
def influencer_verification_pending(request):
    """Page shown while influencer verification is pending."""
    if request.user.role != User.Roles.INFLUENCER:
        return redirect("core:home")
    
    try:
        influencer = request.user.influencer_profile
    except Influencer.DoesNotExist:
        return redirect("accounts:influencer_onboarding")
    
    if influencer.is_verified:
        return redirect("influencers:dashboard")
    
    return render(request, "accounts/influencer_verification_pending.html", {
        "influencer": influencer,
    })
