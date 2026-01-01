from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Q, Count, Sum
from django.utils import timezone
from django.urls import reverse
from django.conf import settings
from datetime import timedelta
import secrets
import logging

from accounts.decorators import influencer_onboarding_required, influencer_verified_required
from influencers.models import Influencer, PlatformConnection, InfluencerVerificationQueue, PaymentMethod
from campaigns.models import Campaign
from operations.models import Submission, Payout
from .oauth import FacebookOAuth, TikTokOAuth
from .currency_utils import convert_currency
from .forms import PaymentMethodForm
from django.views.decorators.http import require_POST, require_http_methods

logger = logging.getLogger(__name__)


@influencer_onboarding_required
def influencer_dashboard(request):
    """
    Influencer dashboard overview with stats and recent activity.
    """
    influencer = get_object_or_404(Influencer, user=request.user)
    
    # Get verified platform connections with follower counts
    verified_connections = influencer.platform_connections.filter(
        verification_status='verified'
    )
    
    # Build a dict of platform -> follower count (using verified count if available)
    from influencers.models import PlatformSettings
    platform_follower_counts = {}
    eligible_platforms = []
    
    for connection in verified_connections:
        # Use verified count from API if available, otherwise use user-provided count
        follower_count = connection.verified_followers_count if connection.verified_followers_count else connection.followers_count
        platform_follower_counts[connection.platform] = follower_count
        
        # Check if influencer meets minimum follower requirement for this platform
        min_followers = PlatformSettings.get_minimum_followers(connection.platform)
        if follower_count >= min_followers:
            eligible_platforms.append(connection.platform)
    
    # Available jobs (active campaigns matching eligible platforms, no submission yet)
    available_campaigns = Campaign.objects.filter(
        status=Campaign.Status.ACTIVE,
        platform__in=eligible_platforms,
    ).exclude(
        submissions__influencer=influencer
    )
    
    # If influencer has a niche, filter by it
    if influencer.niche:
        available_campaigns = available_campaigns.filter(niche__iexact=influencer.niche)
    
    available_jobs_count = available_campaigns.count()
    
    # In progress jobs (submissions that are new or in_review, due soon)
    week_from_now = timezone.now().date() + timedelta(days=7)
    in_progress_submissions = influencer.submissions.filter(
        status__in=[Submission.Status.NEW, Submission.Status.IN_REVIEW]
    ).select_related('campaign')
    
    in_progress_due_soon = [
        sub for sub in in_progress_submissions
        if sub.campaign.due_date and sub.campaign.due_date <= week_from_now
    ]
    
    # Completed jobs (verified submissions)
    completed_submissions = influencer.submissions.filter(
        status=Submission.Status.VERIFIED
    )
    
    # This month's completed count
    month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    this_month_completed = completed_submissions.filter(
        reviewed_at__gte=month_start
    ).count()
    
    # Wallet stats (matching wallet page logic)
    all_payouts = influencer.payouts.all().select_related('campaign', 'campaign__brand', 'submission')
    
    # Available to withdraw: Payouts from VERIFIED submissions that are still PENDING
    available_payouts = all_payouts.filter(
        status=Payout.Status.PENDING,
        submission__status=Submission.Status.VERIFIED
    )
    available_balance = available_payouts.aggregate(total=Sum('amount'))['total'] or 0
    
    # Pending clearance: Payouts from NEW/IN_REVIEW submissions (job not completed yet)
    pending_clearance_payouts = all_payouts.filter(
        status=Payout.Status.PENDING,
        submission__status__in=[Submission.Status.NEW, Submission.Status.IN_REVIEW]
    )
    pending_clearance_amount = pending_clearance_payouts.aggregate(total=Sum('amount'))['total'] or 0
    
    # Total earned (all sent payouts)
    total_earned = all_payouts.filter(status=Payout.Status.SENT).aggregate(
        total=Sum('amount')
    )['total'] or 0
    
    # Active assignments (submissions in progress)
    active_submissions = influencer.submissions.filter(
        status__in=[Submission.Status.NEW, Submission.Status.IN_REVIEW]
    ).select_related('campaign', 'campaign__brand').order_by('campaign__due_date')[:5]
    
    # Recent activity (completed in last 7 days)
    week_ago = timezone.now() - timedelta(days=7)
    recent_completed = completed_submissions.filter(
        reviewed_at__gte=week_ago
    ).select_related('campaign')[:3]
    
    # Get currency from influencer
    from brands.models import Currency
    influencer_currency = influencer.currency or Currency.get_default()
    currency_symbol = influencer.currency_symbol
    currency_code = influencer.currency_code
    
    # Get verification status info
    verification_status = influencer.verification_status
    is_verified = influencer.is_verified
    
    # Get platform stats
    verified_platforms_count = influencer.platform_connections.filter(
        verification_status='verified'
    ).count()
    total_platforms_count = influencer.platform_connections.count()
    
    # Get total followers across all verified platforms
    total_followers = influencer.total_followers
    
    context = {
        "active_page": "dashboard",
        "influencer": influencer,
        "available_jobs_count": available_jobs_count,
        "in_progress_count": len(in_progress_due_soon),
        "completed_count": completed_submissions.count(),
        "this_month_completed": this_month_completed,
        "available_balance": available_balance,  # Available to withdraw
        "pending_clearance_amount": pending_clearance_amount,  # Pending clearance
        "total_earned": total_earned,  # Lifetime earnings
        "active_submissions": active_submissions,
        "recent_completed": recent_completed,
        "today": timezone.now().date(),
        "currency_symbol": currency_symbol,
        "currency_code": currency_code,
        "verification_status": verification_status,
        "is_verified": is_verified,
        "verified_platforms_count": verified_platforms_count,
        "total_platforms_count": total_platforms_count,
        "total_followers": total_followers,
        "eligible_platforms": eligible_platforms,
    }
    return render(request, "influencers/dashboard.html", context)


@influencer_verified_required
def job_feed(request):
    """
    Job feed showing available campaigns matched to the influencer.
    Allows influencers to accept campaigns.
    """
    influencer = get_object_or_404(Influencer, user=request.user)
    
    # Handle campaign acceptance
    if request.method == "POST" and 'accept_campaign' in request.POST:
        campaign_id = request.POST.get('campaign_id')
        try:
            campaign = Campaign.objects.get(id=campaign_id, status=Campaign.Status.ACTIVE)
            
            # Check if already accepted
            if Submission.objects.filter(influencer=influencer, campaign=campaign).exists():
                messages.warning(request, "You have already accepted this campaign.")
            else:
                # Create submission (without proof_link yet - they'll submit later)
                Submission.objects.create(
                    influencer=influencer,
                    campaign=campaign,
                    status=Submission.Status.NEW,
                )
                messages.success(request, f"You've accepted '{campaign.name}'. Submit your proof when ready!")
                return redirect("influencers:my_jobs")
        except Campaign.DoesNotExist:
            messages.error(request, "Campaign not found or no longer available.")
    
    # Get verified platform connections with follower counts
    verified_connections = influencer.platform_connections.filter(
        verification_status='verified'
    )
    
    if not verified_connections.exists():
        messages.warning(request, "You need to verify at least one platform to see available jobs.")
        return redirect("influencers:profile")
    
    # Build a dict of platform -> follower count (using verified count if available)
    from influencers.models import PlatformSettings
    platform_follower_counts = {}
    eligible_platforms = []
    
    for connection in verified_connections:
        # Use verified count from API if available, otherwise use user-provided count
        follower_count = connection.verified_followers_count if connection.verified_followers_count else connection.followers_count
        platform_follower_counts[connection.platform] = follower_count
        
        # Check if influencer meets minimum follower requirement for this platform
        min_followers = PlatformSettings.get_minimum_followers(connection.platform)
        if follower_count >= min_followers:
            eligible_platforms.append(connection.platform)
    
    if not eligible_platforms:
        messages.warning(
            request, 
            f"You don't meet the minimum follower requirements for any platform. "
            f"Please verify your accounts and ensure you have enough followers."
        )
        return redirect("influencers:profile")
    
    # Get available campaigns (active, matching eligible platforms, not already accepted)
    campaigns = Campaign.objects.filter(
        status=Campaign.Status.ACTIVE,
        platform__in=eligible_platforms,
    ).exclude(
        submissions__influencer=influencer
    ).select_related('brand').order_by('-created_at')
    
    # Filter by niche if set
    if influencer.niche:
        campaigns = campaigns.filter(niche__iexact=influencer.niche)
    
    # Apply filters
    platform_filter = request.GET.get('platform')
    if platform_filter:
        campaigns = campaigns.filter(platform=platform_filter)
    
    niche_filter = request.GET.get('niche')
    if niche_filter:
        campaigns = campaigns.filter(niche__icontains=niche_filter)
    
    # Calculate estimated payout per campaign (budget / package_videos)
    # Also add eligibility info for each campaign
    for campaign in campaigns:
        if campaign.package_videos > 0:
            campaign.estimated_payout = campaign.budget / campaign.package_videos
        else:
            campaign.estimated_payout = campaign.budget
        
        # Add follower count info for this campaign's platform
        campaign.influencer_followers = platform_follower_counts.get(campaign.platform, 0)
        campaign.min_required_followers = PlatformSettings.get_minimum_followers(campaign.platform)
        campaign.meets_requirement = campaign.influencer_followers >= campaign.min_required_followers
    
    # Get unique niches and platforms for filters (only from eligible campaigns)
    eligible_campaigns = Campaign.objects.filter(
        status=Campaign.Status.ACTIVE,
        platform__in=eligible_platforms
    )
    available_niches = eligible_campaigns.values_list('niche', flat=True).distinct()
    available_platforms = eligible_campaigns.values_list('platform', flat=True).distinct()
    
    # Get currency for display
    from brands.models import Currency
    influencer_currency = influencer.currency or Currency.get_default()
    currency_symbol = influencer.currency_symbol
    currency_code = influencer.currency_code
    
    context = {
        "active_page": "job_feed",
        "influencer": influencer,
        "campaigns": campaigns,
        "available_niches": available_niches,
        "available_platforms": available_platforms,
        "verified_platforms": eligible_platforms,  # Only show eligible platforms
        "platform_filter": platform_filter,
        "niche_filter": niche_filter,
        "platform_follower_counts": platform_follower_counts,
        "currency_symbol": currency_symbol,
        "currency_code": currency_code,
    }
    return render(request, "influencers/job_feed.html", context)


@influencer_verified_required
def campaign_detail(request, campaign_id):
    """
    View campaign details before accepting.
    """
    influencer = get_object_or_404(Influencer, user=request.user)
    campaign = get_object_or_404(
        Campaign.objects.select_related('brand'),
        id=campaign_id,
        status=Campaign.Status.ACTIVE
    )
    
    # Check if already accepted
    already_accepted = Submission.objects.filter(
        influencer=influencer,
        campaign=campaign
    ).exists()
    
    # Check if campaign matches influencer's platforms and follower requirements
    from influencers.models import PlatformSettings
    
    verified_connection = influencer.platform_connections.filter(
        verification_status='verified',
        platform=campaign.platform
    ).first()
    
    can_accept = False
    if verified_connection and not already_accepted:
        # Check follower count requirement
        follower_count = verified_connection.verified_followers_count if verified_connection.verified_followers_count else verified_connection.followers_count
        min_followers = PlatformSettings.get_minimum_followers(campaign.platform)
        can_accept = follower_count >= min_followers
    
    # Calculate estimated payout
    if campaign.package_videos > 0:
        estimated_payout = campaign.budget / campaign.package_videos
    else:
        estimated_payout = campaign.budget
    
    # Handle acceptance
    if request.method == "POST" and 'accept_campaign' in request.POST and can_accept:
        # Calculate payout amount in campaign currency (budget divided by number of videos in package)
        if campaign.package_videos > 0:
            payout_amount_campaign_currency = campaign.budget / campaign.package_videos
        else:
            payout_amount_campaign_currency = campaign.budget
        
        # Convert to influencer's currency
        from brands.models import Currency
        influencer_currency = influencer.currency or Currency.get_default()
        campaign_currency = campaign.brand.currency or Currency.get_default()
        
        payout_amount = convert_currency(
            payout_amount_campaign_currency,
            campaign_currency,
            influencer_currency
        )
        
        # Create submission and payout in a transaction
        from django.db import transaction
        with transaction.atomic():
            submission = Submission.objects.create(
                influencer=influencer,
                campaign=campaign,
                status=Submission.Status.NEW,
            )
            
            # Create payout with PENDING status (will be available for withdrawal after verification)
            # Store amount in influencer's currency
            Payout.objects.create(
                influencer=influencer,
                campaign=campaign,
                submission=submission,
                amount=payout_amount,
                due_date=campaign.due_date or timezone.now().date() + timedelta(days=30),
                status=Payout.Status.PENDING,
            )
        
        currency_symbol = influencer.currency_symbol
        currency_symbol = influencer.currency_symbol
        messages.success(
            request, 
            f"You've accepted '{campaign.name}'. "
            f"{currency_symbol}{payout_amount:.2f} has been added to your wallet (converted from {campaign.brand.currency_symbol}{payout_amount_campaign_currency:.2f}) "
            f"and will be available for withdrawal after job completion. "
            f"Submit your proof when ready!"
        )
        return redirect("influencers:my_jobs")
    
    # Get currency for display
    from brands.models import Currency
    influencer_currency = influencer.currency or Currency.get_default()
    currency_symbol = influencer.currency_symbol
    currency_code = influencer.currency_code
    
    # Get follower info if connection exists
    follower_info = None
    if verified_connection:
        follower_count = verified_connection.verified_followers_count if verified_connection.verified_followers_count else verified_connection.followers_count
        min_followers = PlatformSettings.get_minimum_followers(campaign.platform)
        follower_info = {
            'count': follower_count,
            'min_required': min_followers,
            'meets_requirement': follower_count >= min_followers,
        }
    
    context = {
        "active_page": "job_feed",
        "campaign": campaign,
        "influencer": influencer,
        "already_accepted": already_accepted,
        "can_accept": can_accept,
        "estimated_payout": estimated_payout,
        "currency_symbol": currency_symbol,
        "currency_code": currency_code,
        "follower_info": follower_info,
    }
    return render(request, "influencers/campaign_detail.html", context)


@influencer_verified_required
def my_jobs(request):
    """
    List of jobs the influencer has accepted or completed.
    Allows submitting proof for accepted campaigns.
    """
    influencer = get_object_or_404(Influencer, user=request.user)
    
    # Handle proof submission
    if request.method == "POST" and 'submit_proof' in request.POST:
        submission_id = request.POST.get('submission_id')
        proof_link = request.POST.get('proof_link', '').strip()
        
        if proof_link:
            try:
                submission = Submission.objects.get(
                    id=submission_id,
                    influencer=influencer,
                    status__in=[Submission.Status.NEW, Submission.Status.NEEDS_REUPLOAD]
                )
                submission.proof_link = proof_link
                submission.status = Submission.Status.IN_REVIEW
                submission.save()
                messages.success(request, "Proof submitted! It's now under review.")
                return redirect("influencers:my_jobs")
            except Submission.DoesNotExist:
                messages.error(request, "Submission not found or cannot be updated.")
        else:
            messages.error(request, "Please provide a proof link.")
    
    # Get all submissions with related data
    submissions = influencer.submissions.all().select_related(
        'campaign', 'campaign__brand'
    ).order_by('-submitted_at', '-campaign__due_date')
    
    # Filter by status
    status_filter = request.GET.get('status', 'all')
    if status_filter != 'all':
        submissions = submissions.filter(status=status_filter)
    
    # Group submissions by status for stats
    status_counts = {
        'new': submissions.filter(status=Submission.Status.NEW).count(),
        'in_review': submissions.filter(status=Submission.Status.IN_REVIEW).count(),
        'verified': submissions.filter(status=Submission.Status.VERIFIED).count(),
        'flagged': submissions.filter(status=Submission.Status.FLAGGED).count(),
        'needs_reupload': submissions.filter(status=Submission.Status.NEEDS_REUPLOAD).count(),
    }
    
    # Calculate total earnings (from verified submissions with payouts)
    total_earned = Payout.objects.filter(
        influencer=influencer,
        status=Payout.Status.SENT
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # Get currency from influencer
    from brands.models import Currency
    influencer_currency = influencer.currency or Currency.get_default()
    currency_symbol = influencer.currency_symbol
    currency_code = influencer.currency_code
    
    context = {
        "active_page": "my_jobs",
        "influencer": influencer,
        "submissions": submissions,
        "status_counts": status_counts,
        "status_filter": status_filter,
        "total_earned": total_earned,
        "currency_symbol": currency_symbol,
        "currency_code": currency_code,
    }
    return render(request, "influencers/my_jobs.html", context)


@influencer_verified_required
def wallet(request):
    """
    Wallet dashboard showing earnings, withdrawals, and payment history.
    
    Wallet logic:
    - When assigned to a job: Payout is created with PENDING status (added to wallet)
    - When job is verified: Payout becomes available for withdrawal
    - Available to withdraw: Sum of payouts from VERIFIED submissions with PENDING status
    - Pending clearance: Sum of payouts from NEW/IN_REVIEW submissions with PENDING status
    """
    influencer = get_object_or_404(Influencer, user=request.user)
    
    # Get all payouts
    all_payouts = influencer.payouts.all().select_related('campaign', 'campaign__brand', 'submission').order_by('-due_date', '-created_at')
    
    # Available to withdraw: Payouts from VERIFIED submissions that are still PENDING
    verified_submissions = influencer.submissions.filter(status=Submission.Status.VERIFIED)
    available_payouts = all_payouts.filter(
        status=Payout.Status.PENDING,
        submission__status=Submission.Status.VERIFIED
    )
    available_balance = available_payouts.aggregate(total=Sum('amount'))['total'] or 0
    
    # Pending clearance: Payouts from NEW/IN_REVIEW submissions (job not completed yet)
    pending_submissions = influencer.submissions.filter(
        status__in=[Submission.Status.NEW, Submission.Status.IN_REVIEW]
    )
    pending_clearance_payouts = all_payouts.filter(
        status=Payout.Status.PENDING,
        submission__status__in=[Submission.Status.NEW, Submission.Status.IN_REVIEW]
    )
    pending_clearance_amount = pending_clearance_payouts.aggregate(total=Sum('amount'))['total'] or 0
    
    # Total earned (all sent payouts)
    total_earned = all_payouts.filter(status=Payout.Status.SENT).aggregate(
        total=Sum('amount')
    )['total'] or 0
    
    # All pending payouts (for display)
    all_pending_payouts = all_payouts.filter(status=Payout.Status.PENDING)
    overdue_payouts = [p for p in all_pending_payouts if p.is_overdue]
    overdue_amount = sum(p.amount for p in overdue_payouts)
    
    # Filter by status
    status_filter = request.GET.get('status', 'all')
    if status_filter == 'pending':
        payouts = all_pending_payouts
    elif status_filter == 'sent':
        payouts = all_payouts.filter(status=Payout.Status.SENT)
    elif status_filter == 'available':
        payouts = available_payouts
    elif status_filter == 'overdue':
        payouts = overdue_payouts
    else:
        payouts = all_payouts
    
    # Get recent payouts (last 10)
    recent_payouts = all_payouts[:10]
    
    # Get currency from influencer
    from brands.models import Currency
    influencer_currency = influencer.currency or Currency.get_default()
    currency_symbol = influencer.currency_symbol
    currency_code = influencer.currency_code
    
    # Get payment methods
    payment_methods = influencer.payment_methods.all()
    default_payment_method = payment_methods.filter(is_default=True).first()
    
    context = {
        "active_page": "wallet",
        "influencer": influencer,
        "available_balance": available_balance,  # Available to withdraw
        "pending_clearance_amount": pending_clearance_amount,  # Pending clearance
        "total_earned": total_earned,  # Lifetime earnings (sent payouts)
        "overdue_amount": overdue_amount,
        "payouts": payouts,
        "recent_payouts": recent_payouts,
        "status_filter": status_filter,
        "pending_count": all_pending_payouts.count(),
        "sent_count": all_payouts.filter(status=Payout.Status.SENT).count(),
        "available_count": available_payouts.count(),
        "currency_symbol": currency_symbol,
        "currency_code": currency_code,
        "payment_methods": payment_methods,
        "default_payment_method": default_payment_method,
    }
    return render(request, "influencers/wallet.html", context)


@influencer_verified_required
@login_required
def request_withdrawal(request):
    """
    Handle withdrawal request from influencer.
    Creates a withdrawal request for all available payouts (from verified submissions).
    """
    if request.method != "POST":
        messages.error(request, "Invalid request method.")
        return redirect("influencers:wallet")
    
    influencer = get_object_or_404(Influencer, user=request.user)
    
    # Get available payouts (from verified submissions, still pending)
    available_payouts = influencer.payouts.filter(
        status=Payout.Status.PENDING,
        submission__status=Submission.Status.VERIFIED
    )
    
    if not available_payouts.exists():
        messages.warning(request, "You don't have any available balance to withdraw.")
        return redirect("influencers:wallet")
    
    total_amount = available_payouts.aggregate(total=Sum('amount'))['total'] or 0
    
    # Get influencer currency
    from brands.models import Currency
    influencer_currency = influencer.currency or Currency.get_default()
    currency_symbol = influencer.currency_symbol
    min_withdrawal = convert_currency(50, Currency.get_default() or Currency.objects.filter(code='USD').first(), influencer_currency)
    
    if total_amount < min_withdrawal:
        messages.warning(
            request, 
            f"Minimum withdrawal amount is {currency_symbol}{min_withdrawal:.2f}. You have {currency_symbol}{total_amount:.2f} available."
        )
        return redirect("influencers:wallet")
    
    # Check if influencer has a payment method set up
    default_payment_method = influencer.payment_methods.filter(is_default=True).first()
    if not default_payment_method:
        messages.warning(
            request,
            "Please add a payment method before requesting withdrawal. "
            "Go to Payment Methods section and add your bank account or Mobile Money details."
        )
        return redirect("influencers:wallet")
    
    # For now, we'll just show a message that withdrawal request has been submitted
    # In a full implementation, you would create a WithdrawalRequest model
    # and notify admins to process it
    
    payment_method_display = default_payment_method.get_display_name()
    messages.success(
        request,
        f"Withdrawal request submitted for {currency_symbol}{total_amount:.2f}. "
        f"Payment will be sent to: {payment_method_display}. "
        f"Our team will process your withdrawal within 1-3 business days. "
        f"You will receive a notification once it's processed."
    )
    
    # Log the withdrawal request (in production, create a WithdrawalRequest model)
    logger.info(
        f"Withdrawal request from {influencer.user.username}: "
        f"${total_amount:.2f} from {available_payouts.count()} payout(s)"
    )
    
    return redirect("influencers:wallet")


@influencer_verified_required
@login_required
@require_http_methods(["GET", "POST"])
def add_payment_method(request):
    """Add a new payment method."""
    influencer = get_object_or_404(Influencer, user=request.user)
    
    if request.method == "POST":
        form = PaymentMethodForm(request.POST, influencer=influencer)
        if form.is_valid():
            payment_method = form.save(commit=False)
            payment_method.influencer = influencer
            payment_method.save()
            messages.success(request, f"Payment method added successfully: {payment_method.get_display_name()}")
            return redirect("influencers:wallet")
    else:
        form = PaymentMethodForm(influencer=influencer)
    
    context = {
        "active_page": "wallet",
        "influencer": influencer,
        "form": form,
        "action": "Add",
    }
    return render(request, "influencers/payment_method_form.html", context)


@influencer_verified_required
@login_required
@require_http_methods(["GET", "POST"])
def edit_payment_method(request, method_id):
    """Edit an existing payment method."""
    influencer = get_object_or_404(Influencer, user=request.user)
    payment_method = get_object_or_404(PaymentMethod, id=method_id, influencer=influencer)
    
    if request.method == "POST":
        form = PaymentMethodForm(request.POST, instance=payment_method, influencer=influencer)
        if form.is_valid():
            form.save()
            messages.success(request, f"Payment method updated: {payment_method.get_display_name()}")
            return redirect("influencers:wallet")
    else:
        form = PaymentMethodForm(instance=payment_method, influencer=influencer)
    
    context = {
        "active_page": "wallet",
        "influencer": influencer,
        "form": form,
        "payment_method": payment_method,
        "action": "Edit",
    }
    return render(request, "influencers/payment_method_form.html", context)


@influencer_verified_required
@login_required
@require_POST
def delete_payment_method(request, method_id):
    """Delete a payment method."""
    influencer = get_object_or_404(Influencer, user=request.user)
    payment_method = get_object_or_404(PaymentMethod, id=method_id, influencer=influencer)
    
    display_name = payment_method.get_display_name()
    payment_method.delete()
    
    messages.success(request, f"Payment method deleted: {display_name}")
    return redirect("influencers:wallet")


@influencer_verified_required
@login_required
@require_POST
def set_default_payment_method(request, method_id):
    """Set a payment method as default."""
    influencer = get_object_or_404(Influencer, user=request.user)
    payment_method = get_object_or_404(PaymentMethod, id=method_id, influencer=influencer)
    
    payment_method.is_default = True
    payment_method.save()  # This will automatically unset other defaults via the model's save() method
    
    messages.success(request, f"Default payment method set to: {payment_method.get_display_name()}")
    return redirect("influencers:wallet")


@influencer_onboarding_required
def profile(request):
    """
    Profile and verification page for influencers.
    Shows profile details, platform connections, and allows adding new platforms.
    """
    influencer = get_object_or_404(Influencer, user=request.user)
    
    # Get all platform connections
    platform_connections = influencer.platform_connections.all().order_by('-followers_count')
    
    # Get verified platforms
    verified_platforms = platform_connections.filter(verification_status='verified')
    pending_platforms = platform_connections.filter(verification_status='pending')
    rejected_platforms = platform_connections.filter(verification_status='rejected')
    
    # Get platform settings for minimum requirements
    from influencers.models import PlatformSettings
    platform_settings = PlatformSettings.objects.filter(is_active=True)
    platform_requirements = {
        setting.platform: setting.minimum_followers 
        for setting in platform_settings
    }
    
    # Handle profile picture update (if form submitted)
    if request.method == "POST" and 'update_profile_picture' in request.POST:
        if 'profile_picture' in request.FILES:
            influencer.profile_picture = request.FILES['profile_picture']
            influencer.save()
            messages.success(request, "Profile picture updated successfully!")
            return redirect("influencers:profile")
        else:
            messages.error(request, "Please select a picture to upload.")
    
    # Handle currency update (if form submitted)
    if request.method == "POST" and 'update_currency' in request.POST:
        from brands.models import Currency
        currency_id = request.POST.get('currency')
        if currency_id:
            try:
                currency = Currency.objects.get(id=currency_id, is_active=True)
                influencer.currency = currency
                influencer.save()
                messages.success(request, f"Currency updated to {currency.code} ({currency.symbol}).")
                return redirect("influencers:profile")
            except Currency.DoesNotExist:
                messages.error(request, "Invalid currency selected.")
        else:
            messages.error(request, "Please select a currency.")
    
    # Create a simple form just for the picture field
    from django import forms
    class ProfilePictureForm(forms.Form):
        profile_picture = forms.ImageField(required=False)
    profile_form = ProfilePictureForm()
    
    # Handle adding new platform (if form submitted)
    if request.method == "POST" and 'add_platform' in request.POST:
        from accounts.forms import InfluencerPlatformForm
        platform_form = InfluencerPlatformForm(request.POST, influencer=influencer)
        if platform_form.is_valid():
            platform_conn = platform_form.save()
            messages.success(request, f"{platform_conn.get_platform_display()} account added! Pending verification.")
            return redirect("influencers:profile")
    else:
        from accounts.forms import InfluencerPlatformForm
        platform_form = InfluencerPlatformForm(influencer=influencer)
    
    # Calculate profile completeness
    completeness_score = 0
    if influencer.niche:
        completeness_score += 20
    if influencer.primary_platform:
        completeness_score += 20
    if verified_platforms.exists():
        completeness_score += 30
    if influencer.user.first_name and influencer.user.last_name:
        completeness_score += 15
    if influencer.user.email:
        completeness_score += 15
    
    # Check OAuth configuration status
    oauth_config = {
        'facebook_configured': bool(
            getattr(settings, 'FACEBOOK_APP_ID', None) and 
            getattr(settings, 'FACEBOOK_APP_SECRET', None)
        ),
        'tiktok_configured': bool(
            getattr(settings, 'TIKTOK_CLIENT_KEY', None) and 
            getattr(settings, 'TIKTOK_CLIENT_SECRET', None)
        ),
    }
    
    # Check if account should be auto-approved (in case it wasn't triggered before)
    if influencer.verification_status == Influencer.VerificationStatus.PENDING:
        has_verified_platforms = verified_platforms.exists()
        has_minimum_followers = influencer.has_minimum_followers
        has_niche = influencer.niche is not None
        has_primary_platform = influencer.primary_platform is not None
        
        if has_verified_platforms and has_minimum_followers and has_niche and has_primary_platform:
            # Auto-approve influencer account
            influencer.verification_status = Influencer.VerificationStatus.APPROVED
            influencer.save()
            logger.info(f"Auto-approved influencer {influencer.user.username} on profile page load - all requirements met")
            messages.success(request, "🎉 Your account has been fully verified and approved! You can now start accepting jobs.")
            # Refresh to get updated status
            influencer.refresh_from_db()
            verified_platforms = influencer.verified_platforms
    
    # Get available currencies for selection
    from brands.models import Currency
    available_currencies = Currency.objects.filter(is_active=True).order_by('is_default', 'name')
    
    context = {
        "active_page": "profile",
        "influencer": influencer,
        "profile_form": profile_form,
        "platform_connections": platform_connections,
        "verified_platforms": verified_platforms,
        "pending_platforms": pending_platforms,
        "rejected_platforms": rejected_platforms,
        "platform_form": platform_form,
        "platform_requirements": platform_requirements,
        "completeness_score": completeness_score,
        "oauth_config": oauth_config,  # Add OAuth config status
        "available_currencies": available_currencies,
    }
    return render(request, "influencers/profile.html", context)


@influencer_onboarding_required
@login_required
def reverify_platform(request, connection_id):
    """
    Manually re-verify a platform connection.
    Only accepts POST requests.
    """
    if request.method != 'POST':
        messages.error(request, "Invalid request method.")
        return redirect("influencers:profile")
    
    influencer = get_object_or_404(Influencer, user=request.user)
    
    try:
        connection = PlatformConnection.objects.get(
            id=connection_id,
            influencer=influencer
        )
    except PlatformConnection.DoesNotExist:
        messages.error(request, "Platform connection not found.")
        return redirect("influencers:profile")
    
    # Run verification
    from .verification import VerificationService
    try:
        logger.info(f"Starting re-verification for connection {connection.id} (platform: {connection.platform}, handle: {connection.handle})")
        result = VerificationService.verify_connection(connection, auto_approve=True)
        
        # Refresh connection to get updated status
        connection.refresh_from_db()
        
        logger.info(f"Verification result: passed={result.passed}, confidence={result.confidence}, status={connection.verification_status}")
        
        # Auto-approve influencer account if all requirements are met
        if result.passed and connection.verification_status == PlatformConnection.VerificationStatus.VERIFIED:
            try:
                # Refresh influencer to get latest data
                influencer.refresh_from_db()
                
                # Check if influencer account should be auto-approved
                if influencer.verification_status == Influencer.VerificationStatus.PENDING:
                    # Check all requirements
                    has_verified_platforms = influencer.verified_platforms.exists()
                    has_minimum_followers = influencer.has_minimum_followers
                    has_niche = influencer.niche is not None
                    has_primary_platform = influencer.primary_platform is not None
                    
                    logger.info(f"Auto-approval check for {influencer.user.username}: verified_platforms={has_verified_platforms}, min_followers={has_minimum_followers}, niche={has_niche}, primary_platform={has_primary_platform}")
                    
                    if has_verified_platforms and has_minimum_followers and has_niche and has_primary_platform:
                        # Auto-approve influencer account
                        influencer.verification_status = Influencer.VerificationStatus.APPROVED
                        influencer.save()
                        logger.info(f"Auto-approved influencer {influencer.user.username} - all requirements met")
                        messages.success(request, "🎉 Your account has been fully verified and approved! You can now start accepting jobs.")
                    else:
                        # Log what's missing for debugging
                        missing = []
                        if not has_verified_platforms:
                            missing.append("verified platforms")
                        if not has_minimum_followers:
                            missing.append("minimum followers")
                        if not has_niche:
                            missing.append("niche")
                        if not has_primary_platform:
                            missing.append("primary platform")
                        logger.info(f"Auto-approval skipped for {influencer.user.username} - missing: {', '.join(missing)}")
            except Exception as e:
                logger.error(f"Failed to auto-approve influencer after platform verification: {e}", exc_info=True)
        
        if result.passed:
            messages.success(
                request, 
                f"✓ {connection.get_platform_display()} account verified successfully! "
                f"({connection.verified_followers_count or connection.followers_count:,} followers)"
            )
        else:
            # Show specific error messages (only show unique ones)
            error_messages = []
            info_messages = []
            seen_flags = set()
            
            for flag in result.flags:
                # Avoid duplicates
                if flag in seen_flags:
                    continue
                seen_flags.add(flag)
                
                if 'you need at least' in flag.lower() or 'below minimum' in flag.lower():
                    error_messages.append(flag)
                elif 'Follower count corrected' in flag:
                    # This is informational, not an error
                    info_messages.append(flag)
            
            # Show info messages (follower count corrected) only once
            for info_msg in info_messages:
                messages.info(request, info_msg)
            
            # Show error messages
            if error_messages:
                messages.error(request, " ".join(error_messages))
            else:
                messages.warning(
                    request, 
                    f"Verification did not pass. Status: {connection.get_verification_status_display()}. "
                    "An admin will review your account."
                )
    except Exception as e:
        logger.error(f"Re-verification error for connection {connection.id}: {e}", exc_info=True)
        messages.error(request, f"Verification failed: {str(e)}")
    
    return redirect(reverse("influencers:profile") + "#platforms")


@influencer_onboarding_required
@login_required
def connect_facebook(request):
    """Initiate Facebook OAuth flow."""
    # Temporarily disabled - OAuth configuration in progress
    messages.info(
        request,
        "Facebook auto-connect is temporarily unavailable while we configure OAuth permissions. "
        "Please use the manual form below to add your Facebook account for now."
    )
    return redirect(reverse("influencers:profile") + "#platforms")
    
    influencer = get_object_or_404(Influencer, user=request.user)
    
    # Check if Facebook OAuth is configured
    # Note: OAuth 2.0 requires App ID and App Secret to work
    facebook_app_id = getattr(settings, 'FACEBOOK_APP_ID', None)
    facebook_app_secret = getattr(settings, 'FACEBOOK_APP_SECRET', None)
    
    if not facebook_app_id or not facebook_app_secret:
        messages.info(
            request, 
            "Facebook OAuth is not configured. You can still add Facebook manually using the 'Add New Platform' form below."
        )
        logger.info("Facebook OAuth attempted but FACEBOOK_APP_ID or FACEBOOK_APP_SECRET is not set - user can use manual entry")
        return redirect(reverse("influencers:profile") + "#platforms")
    
    # Generate state for security
    state = secrets.token_urlsafe(32)
    request.session['oauth_state'] = state
    request.session['oauth_platform'] = 'facebook'
    
    # Build redirect URI - ensure HTTPS when using ngrok
    redirect_uri = request.build_absolute_uri(reverse('influencers:oauth_callback'))
    
    # Force HTTPS if using ngrok domain
    if 'ngrok' in redirect_uri and redirect_uri.startswith('http://'):
        redirect_uri = redirect_uri.replace('http://', 'https://')
        logger.info(f"Forced HTTPS for redirect URI: {redirect_uri}")
    
    try:
        auth_url = FacebookOAuth.get_authorization_url(redirect_uri, state=state)
        logger.info(f"Initiating Facebook OAuth for user {request.user.id} with redirect: {redirect_uri}")
        return redirect(auth_url)
    except ValueError as e:
        messages.error(request, f"Configuration error: {str(e)}")
        logger.error(f"Facebook OAuth configuration error: {e}")
        return redirect("influencers:profile")
    except Exception as e:
        messages.error(request, f"Failed to initiate Facebook connection: {str(e)}")
        logger.error(f"Facebook OAuth initiation error: {e}", exc_info=True)
        return redirect("influencers:profile")


@influencer_onboarding_required
@login_required
def connect_instagram(request):
    """
    Initiate Instagram OAuth flow (via Facebook).
    Instagram Business accounts must be connected to a Facebook Page.
    This flow will:
    1. Prompt user to log in to Facebook
    2. Request permissions to access their Pages
    3. Find Instagram Business accounts connected to those Pages
    4. Automatically retrieve follower count and account details
    """
    # Temporarily disabled - OAuth configuration in progress
    messages.info(
        request,
        "Instagram auto-connect is temporarily unavailable while we configure OAuth permissions. "
        "Please use the manual form below to add your Instagram account for now."
    )
    return redirect(reverse("influencers:profile") + "#platforms")
    
    influencer = get_object_or_404(Influencer, user=request.user)
    
    # Check if Facebook OAuth is configured (Instagram uses Facebook OAuth)
    # Note: OAuth 2.0 requires App ID and App Secret to work
    facebook_app_id = getattr(settings, 'FACEBOOK_APP_ID', None)
    facebook_app_secret = getattr(settings, 'FACEBOOK_APP_SECRET', None)
    
    if not facebook_app_id or not facebook_app_secret:
        messages.info(
            request, 
            "Instagram OAuth is not configured. You can still add Instagram manually using the 'Add New Platform' form below."
        )
        logger.info("Instagram OAuth attempted but FACEBOOK_APP_ID or FACEBOOK_APP_SECRET is not set - user can use manual entry")
        return redirect(reverse("influencers:profile") + "#platforms")
    
    # Store a flag to show helpful message after redirect
    request.session['instagram_connect_initiated'] = True
    
    # Generate state for security
    state = secrets.token_urlsafe(32)
    request.session['oauth_state'] = state
    request.session['oauth_platform'] = 'instagram'
    
    # Build redirect URI - ensure HTTPS when using ngrok
    redirect_uri = request.build_absolute_uri(reverse('influencers:oauth_callback'))
    
    # Force HTTPS if using ngrok domain
    if 'ngrok' in redirect_uri and redirect_uri.startswith('http://'):
        redirect_uri = redirect_uri.replace('http://', 'https://')
        logger.info(f"Forced HTTPS for redirect URI: {redirect_uri}")
    
    try:
        auth_url = FacebookOAuth.get_authorization_url(redirect_uri, state=state)
        logger.info(f"Initiating Instagram OAuth for user {request.user.id} with redirect: {redirect_uri}")
        # Redirect to Facebook OAuth - user will be prompted to log in and grant permissions
        return redirect(auth_url)
    except ValueError as e:
        messages.error(request, f"Configuration error: {str(e)}")
        logger.error(f"Instagram OAuth configuration error: {e}")
        return redirect("influencers:profile")
    except Exception as e:
        messages.error(request, f"Failed to initiate Instagram connection: {str(e)}")
        logger.error(f"Instagram OAuth initiation error: {e}", exc_info=True)
        return redirect("influencers:profile")


@influencer_onboarding_required
@login_required
def oauth_callback(request):
    """Handle OAuth callback from Facebook/Instagram."""
    influencer = get_object_or_404(Influencer, user=request.user)
    
    # Verify state
    state = request.GET.get('state')
    stored_state = request.session.get('oauth_state')
    platform = request.session.get('oauth_platform', 'facebook')
    
    if not state or state != stored_state:
        messages.error(request, "Invalid OAuth state. Please try again.")
        return redirect("influencers:profile")
    
    # Clear state from session
    request.session.pop('oauth_state', None)
    request.session.pop('oauth_platform', None)
    
    code = request.GET.get('code')
    if not code:
        error = request.GET.get('error')
        error_reason = request.GET.get('error_reason', request.GET.get('error_description', 'Unknown error'))
        messages.error(request, f"OAuth authorization failed: {error_reason}")
        return redirect("influencers:profile")
    
    try:
        redirect_uri = request.build_absolute_uri(reverse('influencers:oauth_callback'))
        
        # Handle TikTok OAuth
        if platform == 'tiktok':
            access_token, expires_in, refresh_token = TikTokOAuth.exchange_code_for_token(code, redirect_uri)
            
            # Get user info - TikTok API v2 requires open_id in request body
            # First, try to get user info without open_id (some endpoints support this)
            user_info = TikTokOAuth.get_user_info(access_token)
            
            if not user_info:
                messages.error(request, "Failed to get TikTok account information. Please try again.")
                logger.error(f"TikTok user info failed for user {request.user.id}")
                return redirect("influencers:profile")
            
            # Extract data
            open_id = user_info.get('open_id')
            display_name = user_info.get('display_name', '')
            username = display_name.replace('@', '') if display_name else ''
            followers_count = user_info.get('follower_count', 0)
            
            # If we still don't have open_id, try to get it from a different endpoint
            if not open_id:
                # Try to decode from token or use a fallback
                logger.warning(f"TikTok open_id not found in user_info for user {request.user.id}")
                # We'll create a temporary open_id based on the username or use a placeholder
                # In production, you might want to handle this differently
                if username:
                    open_id = f"tiktok_{username}"
                else:
                    messages.error(request, "Failed to get TikTok account ID. Please try connecting again.")
                    return redirect("influencers:profile")
            
            # Create or update platform connection
            platform_conn, created = PlatformConnection.objects.update_or_create(
                influencer=influencer,
                platform=PlatformConnection.Platform.TIKTOK,
                defaults={
                    'handle': username or f"tiktok_{open_id[:8]}" if open_id else 'tiktok_user',
                    'followers_count': followers_count,
                    'verified_followers_count': followers_count,
                    'access_token': access_token,
                    'platform_user_id': open_id,
                    'tiktok_open_id': open_id,
                    'refresh_token': refresh_token,
                    'token_expires_at': timezone.now() + timedelta(seconds=expires_in) if expires_in else None,
                    'oauth_connected_at': timezone.now(),
                    'follower_verification_date': timezone.now(),
                    'verification_status': PlatformConnection.VerificationStatus.VERIFIED,
                    'verification_method': 'api',
                }
            )
            
            # Trigger auto-verification if needed (though it should already be verified via OAuth)
            if created or platform_conn.verification_status != PlatformConnection.VerificationStatus.VERIFIED:
                from .verification import VerificationService
                try:
                    VerificationService.verify_connection(platform_conn, auto_approve=True)
                except Exception as e:
                    logger.warning(f"Auto-verification failed for TikTok: {e}")
            
            messages.success(
                request, 
                f"✓ TikTok account @{platform_conn.handle} connected successfully! "
                f"({followers_count:,} followers)"
            )
            return redirect(reverse("influencers:profile") + "#platforms")
        
        # Handle Facebook/Instagram OAuth
        access_token, expires_in = FacebookOAuth.exchange_code_for_token(code, redirect_uri)
        
        # Exchange for long-lived token (60 days)
        try:
            long_lived_token, long_expires_in = FacebookOAuth.exchange_for_long_lived_token(access_token)
            access_token = long_lived_token
            expires_in = long_expires_in
        except Exception as e:
            logger.warning(f"Failed to exchange for long-lived token: {e}")
            # Continue with short-lived token
        
        # Calculate expiration time
        expires_at = timezone.now() + timedelta(seconds=expires_in) if expires_in else None
        
        # Get user's pages
        pages = FacebookOAuth.get_user_pages(access_token)
        
        if not pages:
            messages.warning(request, "No Facebook Pages found. Please create a Facebook Page and try again.")
            return redirect("influencers:profile")
        
        # For Instagram, we need a page with connected Instagram account
        if platform == 'instagram':
            # Find page with Instagram account
            instagram_page = None
            for page in pages:
                if page.get('instagram_business_account'):
                    instagram_page = page
                    break
            
            if not instagram_page:
                messages.warning(
                    request, 
                    "No Instagram Business Account found. "
                    "Please connect your Instagram account to a Facebook Page and try again. "
                    "See instructions below on how to connect Instagram to a Facebook Page."
                )
                return redirect("influencers:profile")
            
            # IMPORTANT: For Instagram Business accounts, we need to use the PAGE access token,
            # not the user access token. The page access token is in the page data.
            page_access_token = instagram_page.get('access_token')
            if not page_access_token:
                # Fallback: try to get page access token from page info
                page_info = FacebookOAuth.get_page_info(instagram_page['id'], access_token)
                if page_info:
                    # Try to get page token from /me/accounts with page token
                    # Actually, we already have it in instagram_page from get_user_pages
                    page_access_token = access_token  # Fallback to user token
            
            # Get Instagram account info using PAGE access token
            instagram_account_id = instagram_page['instagram_business_account']['id']
            # Use page access token if available, otherwise use user token
            token_to_use = page_access_token or access_token
            instagram_info = FacebookOAuth.get_instagram_account_info(instagram_account_id, token_to_use)
            
            if not instagram_info:
                messages.error(
                    request, 
                    "Failed to get Instagram account information. "
                    "Make sure your Instagram account is connected to a Facebook Page and the app has the required permissions."
                )
                logger.error(f"Failed to get Instagram info for account {instagram_account_id} with token type: {'page' if page_access_token else 'user'}")
                return redirect("influencers:profile")
            
            # Create or update platform connection
            username = instagram_info.get('username', '')
            followers_count = instagram_info.get('followers_count', 0)
            
            platform_conn, created = PlatformConnection.objects.update_or_create(
                influencer=influencer,
                platform=PlatformConnection.Platform.INSTAGRAM,
                defaults={
                    'handle': username,
                    'followers_count': followers_count,
                    'verified_followers_count': followers_count,
                    'access_token': access_token,
                    'platform_user_id': instagram_account_id,
                    'facebook_page_id': instagram_page['id'],
                    'instagram_business_account_id': instagram_account_id,
                    'token_expires_at': expires_at,
                    'oauth_connected_at': timezone.now(),
                    'follower_verification_date': timezone.now(),
                    'verification_status': PlatformConnection.VerificationStatus.VERIFIED,
                    'verification_method': 'api',
                }
            )
            
            # Trigger auto-verification if needed
            if created or platform_conn.verification_status != PlatformConnection.VerificationStatus.VERIFIED:
                from .verification import VerificationService
                try:
                    VerificationService.verify_connection(platform_conn, auto_approve=True)
                except Exception as e:
                    logger.warning(f"Auto-verification failed for Instagram: {e}")
            
            messages.success(
                request, 
                f"✓ Instagram account @{username} connected successfully! "
                f"({followers_count:,} followers). "
                "Your account has been automatically verified."
            )
        
        else:  # Facebook
            # Let user choose which page to connect (for now, use first page)
            # In future, you can add a page selection UI
            page = pages[0]
            page_info = FacebookOAuth.get_page_info(page['id'], access_token)
            
            if not page_info:
                messages.error(request, "Failed to get Facebook Page information.")
                return redirect("influencers:profile")
            
            username = page_info.get('username', page_info.get('name', ''))
            followers_count = page_info.get('followers_count', 0)
            
            # Create or update platform connection
            platform_conn, created = PlatformConnection.objects.update_or_create(
                influencer=influencer,
                platform=PlatformConnection.Platform.FACEBOOK,
                defaults={
                    'handle': username,
                    'followers_count': followers_count,
                    'verified_followers_count': followers_count,
                    'access_token': access_token,
                    'platform_user_id': page_info['id'],
                    'facebook_page_id': page_info['id'],
                    'token_expires_at': expires_at,
                    'oauth_connected_at': timezone.now(),
                    'follower_verification_date': timezone.now(),
                    'verification_status': PlatformConnection.VerificationStatus.VERIFIED,
                    'verification_method': 'api',
                }
            )
            
            # Trigger auto-verification if needed
            if created or platform_conn.verification_status != PlatformConnection.VerificationStatus.VERIFIED:
                from .verification import VerificationService
                try:
                    VerificationService.verify_connection(platform_conn, auto_approve=True)
                except Exception as e:
                    logger.warning(f"Auto-verification failed for Facebook: {e}")
            
            messages.success(
                request, 
                f"✓ Facebook Page '{page_info.get('name', username)}' connected successfully! "
                f"({followers_count:,} followers)"
            )
        
        return redirect("influencers:profile")
        
    except Exception as e:
        logger.error(f"OAuth callback error: {e}")
        messages.error(request, f"Failed to connect account: {str(e)}")
        return redirect("influencers:profile")


@influencer_onboarding_required
@login_required
def connect_tiktok(request):
    """Initiate TikTok OAuth flow."""
    # Temporarily disabled - OAuth configuration in progress
    messages.info(
        request,
        "TikTok auto-connect is temporarily unavailable while we configure OAuth permissions. "
        "Please use the manual form below to add your TikTok account for now."
    )
    return redirect(reverse("influencers:profile") + "#platforms")
    
    influencer = get_object_or_404(Influencer, user=request.user)
    
    # Check if TikTok OAuth is configured
    # Note: OAuth 2.0 requires Client Key and Client Secret to work
    if not getattr(settings, 'TIKTOK_CLIENT_KEY', None):
        messages.info(
            request, 
            "TikTok OAuth is not configured. You can still add TikTok manually using the 'Add New Platform' form below."
        )
        logger.info("TikTok OAuth attempted but TIKTOK_CLIENT_KEY is not set - user can use manual entry")
        return redirect(reverse("influencers:profile") + "#platforms")
    
    # Generate state for security
    state = secrets.token_urlsafe(32)
    request.session['oauth_state'] = state
    request.session['oauth_platform'] = 'tiktok'
    
    # Build redirect URI - ensure HTTPS when using ngrok
    redirect_uri = request.build_absolute_uri(reverse('influencers:oauth_callback'))
    
    # Force HTTPS if using ngrok domain
    if 'ngrok' in redirect_uri and redirect_uri.startswith('http://'):
        redirect_uri = redirect_uri.replace('http://', 'https://')
        logger.info(f"Forced HTTPS for redirect URI: {redirect_uri}")
    
    try:
        auth_url, state_returned = TikTokOAuth.get_authorization_url(redirect_uri, state=state)
        # Update state in session with the one returned by TikTok
        request.session['oauth_state'] = state_returned
        logger.info(f"Initiating TikTok OAuth for user {request.user.id} with redirect: {redirect_uri}")
        return redirect(auth_url)
    except ValueError as e:
        messages.error(request, f"Configuration error: {str(e)}")
        logger.error(f"TikTok OAuth configuration error: {e}")
        return redirect("influencers:profile")
    except Exception as e:
        messages.error(request, f"Failed to initiate TikTok connection: {str(e)}")
        logger.error(f"TikTok OAuth initiation error: {e}", exc_info=True)
        return redirect("influencers:profile")
