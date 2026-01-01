from functools import wraps
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from brands.models import Brand
from influencers.models import Influencer


def brand_profile_required(view_func):
    """Decorator to ensure brand has completed profile."""
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if request.user.role != request.user.Roles.BRAND:
            return redirect('core:home')
        
        try:
            brand = request.user.brand_profile
        except Brand.DoesNotExist:
            return redirect('accounts:brand_onboarding')
        
        if not brand.is_profile_complete:
            return redirect('accounts:brand_onboarding')
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def brand_verified_required(view_func):
    """Decorator to ensure brand is verified before accessing wallet/campaigns."""
    @wraps(view_func)
    @brand_profile_required
    def _wrapped_view(request, *args, **kwargs):
        brand = request.user.brand_profile
        
        if not brand.is_verified:
            return redirect('accounts:brand_verification_pending')
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def influencer_onboarding_required(view_func):
    """Decorator to ensure influencer has completed onboarding."""
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if request.user.role != request.user.Roles.INFLUENCER:
            return redirect('core:home')
        
        try:
            influencer = request.user.influencer_profile
        except Influencer.DoesNotExist:
            return redirect('accounts:influencer_onboarding')
        
        if not influencer.onboarding_completed:
            return redirect('accounts:influencer_onboarding')
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def influencer_verified_required(view_func):
    """Decorator to ensure influencer is verified before accessing jobs."""
    @wraps(view_func)
    @influencer_onboarding_required
    def _wrapped_view(request, *args, **kwargs):
        influencer = request.user.influencer_profile
        
        if not influencer.is_verified:
            return redirect('accounts:influencer_verification_pending')
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view

