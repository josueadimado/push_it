from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count, Sum, Q, F
from django.http import JsonResponse
from datetime import timedelta

from campaigns.models import Campaign
from influencers.models import Influencer
from operations.models import Submission, Payout, Notification
from brands.models import Brand


@login_required
def admin_dashboard(request):
    """Admin dashboard view with real data."""
    # Campaign stats
    total_campaigns = Campaign.objects.count()
    active_campaigns = Campaign.objects.filter(status="active").count()
    
    # Submission stats
    videos_in_progress = Submission.objects.filter(status__in=["new", "in_review"]).count()
    videos_completed = Submission.objects.filter(status="verified").count()
    
    # Financial stats
    total_spend = Campaign.objects.aggregate(total=Sum("budget"))["total"] or 0
    
    # Risk stats - campaigns with low delivery rate or due soon
    # Optimized: Use annotations to calculate delivery rates in a single query
    from django.db.models import Case, When, IntegerField, Value
    three_days_from_now = timezone.now().date() + timedelta(days=3)
    
    active_campaigns_annotated = Campaign.objects.filter(status="active").annotate(
        total_assignments=Count('submissions'),
        verified_count=Count('submissions', filter=Q(submissions__status="verified")),
    ).annotate(
        delivery_rate=Case(
            When(total_assignments=0, then=Value(0)),
            default=F('verified_count') * 100.0 / F('total_assignments'),
            output_field=IntegerField()
        ),
        due_soon=Case(
            When(due_date__isnull=False, due_date__lte=three_days_from_now, then=Value(1)),
            default=Value(0),
            output_field=IntegerField()
        )
    )
    
    # Count campaigns at risk (delivery rate < 70 or due soon)
    campaigns_at_risk = active_campaigns_annotated.filter(
        Q(delivery_rate__lt=70) | Q(due_soon=1)
    ).count()
    pending_verifications = Influencer.objects.filter(verification_status="pending").count()
    pending_payouts = Payout.objects.filter(status="pending").count()
    
    # Calculate on-time delivery from actual submissions
    # Optimized: Use select_related to avoid N+1 queries
    all_submissions = Submission.objects.exclude(status="new").select_related('campaign').filter(
        campaign__due_date__isnull=False,
        reviewed_at__isnull=False
    )
    
    # Limit calculation to recent submissions for performance (last 1000)
    recent_submissions = list(all_submissions.order_by('-reviewed_at')[:1000])
    
    if recent_submissions:
        # Count on-time submissions (reviewed before or on due date)
        on_time_count = sum(
            1 for sub in recent_submissions
            if sub.reviewed_at.date() <= sub.campaign.due_date
        )
        total_count = len(recent_submissions)
        on_time_delivery = round((on_time_count / total_count * 100), 1) if total_count > 0 else 0
    else:
        on_time_delivery = 0
    
    # Disputes (flagged submissions)
    disputes_open = Submission.objects.filter(status="flagged").count()
    
    # Recent activity (simplified - can be enhanced with ActivityLog model later)
    recent_submissions = Submission.objects.select_related("influencer", "campaign").order_by("-submitted_at")[:5]
    recent_payouts = Payout.objects.select_related("influencer", "campaign").filter(status="sent").order_by("-sent_at")[:3]
    
    activity = []
    for sub in recent_submissions[:3]:
        activity.append({
            "type": "content_submitted",
            "description": f"Video from {sub.influencer.primary_handle} for '{sub.campaign.name}' submitted.",
            "time": _time_ago(sub.submitted_at),
        })
    for payout in recent_payouts[:2]:
        activity.append({
            "type": "payout_sent",
            "description": f"Payout of ${payout.amount} sent to {payout.influencer.primary_handle}.",
            "time": _time_ago(payout.sent_at) if payout.sent_at else "N/A",
        })
    
    context = {
        "active_page": "overview",
        "stats": {
            "total_campaigns": total_campaigns,
            "active_campaigns": active_campaigns,
            "videos_in_progress": videos_in_progress,
            "videos_completed": videos_completed,
            "total_spend": float(total_spend),
            "on_time_delivery": on_time_delivery,
            "disputes_open": disputes_open,
            "campaigns_at_risk": campaigns_at_risk,
            "pending_verifications": pending_verifications,
            "pending_payouts": pending_payouts,
        },
        "recent_activity": activity,
    }
    return render(request, "operations/admin_dashboard.html", context)


@login_required
def admin_campaigns(request):
    """Admin campaigns management page."""
    campaigns = Campaign.objects.select_related("brand", "brand__user").all().order_by("-created_at")
    context = {
        "active_page": "campaigns",
        "campaigns": campaigns,
    }
    return render(request, "operations/campaigns.html", context)


@login_required
def admin_campaign_detail(request, campaign_id: int):
    """Admin single campaign detail page."""
    campaign = get_object_or_404(
        Campaign.objects.select_related("brand", "brand__user"),
        id=campaign_id
    )
    
    # Get submissions for this campaign with influencer info
    submissions = Submission.objects.filter(campaign=campaign).select_related("influencer", "influencer__user")
    
    # Group by influencer to show assigned creators
    creators_data = {}
    for sub in submissions:
        inf = sub.influencer
        if inf.id not in creators_data:
            creators_data[inf.id] = {
                "id": inf.id,
                "name": inf.user.get_full_name() or inf.user.username,
                "handle": inf.primary_handle,
                "initials": _get_initials(inf.user.get_full_name() or inf.user.username),
                "platform": campaign.platform,
                "platform_icon": _get_platform_icon(campaign.platform),
                "platform_color": _get_platform_color(campaign.platform),
                "status": _get_creator_status(sub.status),
                "last_activity": _time_ago(sub.submitted_at),
            }
    
    creators = list(creators_data.values())
    
    context = {
        "active_page": "campaigns",
        "campaign": campaign,
        "creators": creators,
        "assigned_creators": len(creators),
    }
    return render(request, "operations/campaign_detail.html", context)


@login_required
def admin_influencers(request):
    """Admin influencers management page."""
    influencers = Influencer.objects.select_related("user").all().order_by("-created_at")
    context = {
        "active_page": "influencers",
        "influencers": influencers,
    }
    return render(request, "operations/influencers.html", context)


@login_required
def admin_verification(request):
    """Admin verification queue page."""
    # Get pending verifications
    pending_influencers = Influencer.objects.filter(
        verification_status="pending"
    ).select_related("user").order_by("-created_at")
    
    pending_brands = Brand.objects.filter(
        verification_status="pending"
    ).select_related("user").order_by("-created_at")
    
    # Calculate stats
    total_pending = pending_influencers.count() + pending_brands.count()
    
    # Calculate average wait time (time since oldest pending request)
    # Optimized: Use database aggregation instead of Python loops
    from django.db.models import Min
    
    oldest_influencer = pending_influencers.aggregate(oldest=Min('created_at'))['oldest']
    oldest_brand = pending_brands.aggregate(oldest=Min('created_at'))['oldest']
    
    all_oldest = [d for d in [oldest_influencer, oldest_brand] if d is not None]
    
    if all_oldest:
        oldest_pending = min(all_oldest)
        wait_delta = timezone.now() - oldest_pending
        hours = wait_delta.total_seconds() / 3600
        avg_wait_hours = int(hours)
        avg_wait_minutes = int((hours - avg_wait_hours) * 60)
        avg_wait_time = f"{avg_wait_hours}h {avg_wait_minutes}m"
    else:
        avg_wait_time = "0h 0m"
    
    # Today's stats
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    approved_today = Influencer.objects.filter(
        verification_status="approved",
        updated_at__gte=today_start
    ).count() + Brand.objects.filter(
        verification_status="verified",
        updated_at__gte=today_start
    ).count()
    
    rejected_today = Influencer.objects.filter(
        verification_status="rejected",
        updated_at__gte=today_start
    ).count() + Brand.objects.filter(
        verification_status="rejected",
        updated_at__gte=today_start
    ).count()
    
    rejection_rate = round((rejected_today / (approved_today + rejected_today) * 100), 1) if (approved_today + rejected_today) > 0 else 0
    
    # Combine all pending for display
    verification_items = []
    for inf in pending_influencers:
        full_name = inf.user.get_full_name() or inf.user.username
        verification_items.append({
            "id": inf.id,
            "type": "influencer",
            "user": inf.user,
            "name": full_name,
            "initials": _get_initials(full_name),
            "role": "Influencer",
            "created_at": inf.created_at,
            "time_ago": _time_ago(inf.created_at),
            "verification_type": "Platform & Profile",
            "risk_level": _calculate_risk_level(inf),
        })
    
    for brand in pending_brands:
        brand_name = brand.company_name or brand.user.username
        verification_items.append({
            "id": brand.id,
            "type": "brand",
            "user": brand.user,
            "name": brand_name,
            "initials": _get_initials(brand_name),
            "role": "Brand Account",
            "created_at": brand.created_at,
            "time_ago": _time_ago(brand.created_at),
            "verification_type": "Business Registration",
            "risk_level": _calculate_brand_risk_level(brand),
        })
    
    # Sort by created_at (newest first)
    verification_items.sort(key=lambda x: x["created_at"], reverse=True)
    
    context = {
        "active_page": "verification",
        "pending_influencers": pending_influencers,
        "pending_brands": pending_brands,
        "verification_items": verification_items[:50],  # Limit to 50 for performance
        "stats": {
            "total_pending": total_pending,
            "avg_wait_time": avg_wait_time,
            "approved_today": approved_today,
            "rejected_today": rejected_today,
            "rejection_rate": rejection_rate,
        },
    }
    return render(request, "operations/verification.html", context)


@login_required
def admin_submissions(request):
    """Admin submissions review page."""
    submissions = Submission.objects.select_related(
        "influencer", "influencer__user", "campaign", "campaign__brand"
    ).order_by("-submitted_at")
    
    # Stats
    stats = {
        "new_submissions": submissions.filter(status="new").count(),
        "in_review": submissions.filter(status="in_review").count(),
        "verified": submissions.filter(status="verified").count(),
        "needs_reupload": submissions.filter(status="needs_reupload").count(),
    }
    
    context = {
        "active_page": "submissions",
        "stats": stats,
        "submissions": submissions[:50],  # Limit for now
    }
    return render(request, "operations/submissions.html", context)


@login_required
def admin_payments(request):
    """Admin payments page."""
    payouts = Payout.objects.select_related(
        "influencer", "influencer__user", "campaign", "campaign__brand"
    ).order_by("-due_date")
    
    # Calculate stats
    now = timezone.now().date()
    week_from_now = now + timedelta(days=7)
    
    this_week_payouts = payouts.filter(
        status="pending",
        due_date__gte=now,
        due_date__lte=week_from_now,
    )
    overdue_payouts = payouts.filter(status="pending", due_date__lt=now)
    pending_payouts = payouts.filter(status="pending")
    
    this_week_total = this_week_payouts.aggregate(total=Sum("amount"))["total"] or 0
    overdue_total = overdue_payouts.aggregate(total=Sum("amount"))["total"] or 0
    total_owed = pending_payouts.aggregate(total=Sum("amount"))["total"] or 0
    
    # Total volume (all payouts)
    total_volume = Payout.objects.aggregate(total=Sum("amount"))["total"] or 0
    
    context = {
        "active_page": "payments",
        "stats": {
            "this_week_due": f"{this_week_total:,.2f}".replace(".00", ""),
            "this_week_count": this_week_payouts.count(),
            "overdue": f"{overdue_total:,.2f}".replace(".00", ""),
            "overdue_count": overdue_payouts.count(),
            "total_owed": f"{total_owed:,.2f}".replace(".00", ""),
            "total_volume": f"{total_volume:,.2f}".replace(".00", ""),
            "total_payouts": payouts.count(),
        },
        "payouts": payouts[:50],  # Limit for now
    }
    return render(request, "operations/payments.html", context)


@login_required
def admin_reports(request):
    """Admin reports page."""
    context = {
        "active_page": "reports",
    }
    return render(request, "operations/reports.html", context)


# Backend Actions

@login_required
def approve_submission(request, submission_id: int):
    """Approve a submission (mark as verified)."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    
    submission = get_object_or_404(Submission, id=submission_id)
    submission.status = Submission.Status.VERIFIED
    submission.reviewed_at = timezone.now()
    submission.reviewed_by = request.user
    submission.save()
    
    messages.success(request, f"Submission from {submission.influencer.primary_handle} approved.")
    
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"success": True, "status": "verified"})
    
    return redirect("operations:submissions")


@login_required
def reject_submission(request, submission_id: int):
    """Reject a submission (mark as needs_reupload)."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    
    submission = get_object_or_404(Submission, id=submission_id)
    submission.status = Submission.Status.NEEDS_REUPLOAD
    submission.reviewed_at = timezone.now()
    submission.reviewed_by = request.user
    submission.save()
    
    messages.warning(request, f"Submission from {submission.influencer.primary_handle} marked as needs re-upload.")
    
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"success": True, "status": "needs_reupload"})
    
    return redirect("operations:submissions")


@login_required
def flag_submission(request, submission_id: int):
    """Flag a submission (mark as flagged/disputed)."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    
    submission = get_object_or_404(Submission, id=submission_id)
    submission.status = Submission.Status.FLAGGED
    submission.reviewed_at = timezone.now()
    submission.reviewed_by = request.user
    submission.save()
    
    messages.warning(request, f"Submission from {submission.influencer.primary_handle} flagged for review.")
    
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"success": True, "status": "flagged"})
    
    return redirect("operations:submissions")


@login_required
def mark_payout_sent(request, payout_id: int):
    """Mark a payout as sent."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    
    payout = get_object_or_404(Payout, id=payout_id)
    payout.status = Payout.Status.SENT
    payout.sent_at = timezone.now()
    payout.sent_by = request.user
    payout.save()
    
    messages.success(request, f"Payout of ${payout.amount} marked as sent to {payout.influencer.primary_handle}.")
    
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"success": True, "status": "sent"})
    
    return redirect("operations:payments")


@login_required
def review_influencer(request, influencer_id: int):
    """Review page for influencer verification - shows all details."""
    influencer = get_object_or_404(Influencer, id=influencer_id)
    
    # Get all platform connections
    platform_connections = influencer.platform_connections.all().order_by('-followers_count')
    
    # Calculate risk level
    risk_level = _calculate_risk_level(influencer)
    
    # Get verification queue info if exists
    verification_queue = None
    if hasattr(influencer, 'verification_queue'):
        verification_queue = influencer.verification_queue
    
    context = {
        "active_page": "verification",
        "influencer": influencer,
        "platform_connections": platform_connections,
        "risk_level": risk_level,
        "verification_queue": verification_queue,
    }
    
    return render(request, "operations/review_influencer.html", context)


@login_required
def review_brand(request, brand_id: int):
    """Review page for brand verification - shows all details."""
    brand = get_object_or_404(Brand, id=brand_id)
    
    # Calculate risk level
    risk_level = _calculate_brand_risk_level(brand)
    
    # Get verification queue info if exists
    verification_queue = None
    if hasattr(brand, 'verification_queue'):
        verification_queue = brand.verification_queue
    
    context = {
        "active_page": "verification",
        "brand": brand,
        "risk_level": risk_level,
        "verification_queue": verification_queue,
    }
    
    return render(request, "operations/review_brand.html", context)


@login_required
def approve_influencer(request, influencer_id: int):
    """Approve an influencer verification."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    
    influencer = get_object_or_404(Influencer, id=influencer_id)
    influencer.verification_status = Influencer.VerificationStatus.APPROVED
    influencer.save()
    
    messages.success(request, f"Influencer {influencer.primary_handle} approved.")
    
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"success": True, "status": "approved"})
    
    return redirect("operations:verification")


@login_required
def reject_influencer(request, influencer_id: int):
    """Reject an influencer verification."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    
    influencer = get_object_or_404(Influencer, id=influencer_id)
    influencer.verification_status = Influencer.VerificationStatus.REJECTED
    influencer.save()
    
    messages.warning(request, f"Influencer {influencer.primary_handle} rejected.")
    
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"success": True, "status": "rejected"})
    
    return redirect("operations:verification")


@login_required
def pause_influencer(request, influencer_id: int):
    """Pause an influencer account (admin action)."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    
    influencer = get_object_or_404(Influencer, id=influencer_id)
    reason = request.POST.get("reason", "")
    
    influencer.pause(request.user, reason)
    
    messages.warning(request, f"Influencer {influencer.primary_handle} paused.")
    
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"success": True, "status": "paused"})
    
    return redirect("operations:influencers")


@login_required
def unpause_influencer(request, influencer_id: int):
    """Unpause an influencer account (admin action)."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    
    influencer = get_object_or_404(Influencer, id=influencer_id)
    influencer.unpause()
    
    messages.success(request, f"Influencer {influencer.primary_handle} unpaused.")
    
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"success": True, "status": "unpaused"})
    
    return redirect("operations:influencers")


@login_required
def pause_brand(request, brand_id: int):
    """Pause a brand account (admin action)."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    
    brand = get_object_or_404(Brand, id=brand_id)
    reason = request.POST.get("reason", "")
    
    brand.pause(request.user, reason)
    
    messages.warning(request, f"Brand {brand.company_name} paused.")
    
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"success": True, "status": "paused"})
    
    return redirect("operations:verification")


@login_required
def unpause_brand(request, brand_id: int):
    """Unpause a brand account (admin action)."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    
    brand = get_object_or_404(Brand, id=brand_id)
    brand.unpause()
    
    messages.success(request, f"Brand {brand.company_name} unpaused.")
    
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"success": True, "status": "unpaused"})
    
    return redirect("operations:verification")


@login_required
def approve_brand(request, brand_id: int):
    """Approve a brand verification."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    
    brand = get_object_or_404(Brand, id=brand_id)
    brand.verification_status = Brand.VerificationStatus.VERIFIED
    brand.save()
    
    messages.success(request, f"Brand {brand.company_name} approved.")
    
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"success": True, "status": "verified"})
    
    return redirect("operations:verification")


@login_required
def reject_brand(request, brand_id: int):
    """Reject a brand verification."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    
    brand = get_object_or_404(Brand, id=brand_id)
    brand.verification_status = Brand.VerificationStatus.REJECTED
    brand.save()
    
    messages.warning(request, f"Brand {brand.company_name} rejected.")
    
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"success": True, "status": "rejected"})
    
    return redirect("operations:verification")


# Helper functions

def _time_ago(dt):
    """Return a human-readable time ago string."""
    if not dt:
        return "N/A"
    
    delta = timezone.now() - dt
    if delta.days > 0:
        return f"{delta.days}d ago"
    elif delta.seconds >= 3600:
        hours = delta.seconds // 3600
        return f"{hours}h ago"
    elif delta.seconds >= 60:
        minutes = delta.seconds // 60
        return f"{minutes}m ago"
    else:
        return "Just now"


def _get_initials(name):
    """Get initials from a name."""
    parts = name.split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    return name[:2].upper() if len(name) >= 2 else name.upper()


def _get_platform_icon(platform):
    """Get icon name for platform."""
    icons = {
        "tiktok": "lucide:music-2",
        "instagram": "lucide:instagram",
        "youtube": "lucide:youtube",
    }
    return icons.get(platform.lower(), "lucide:video")


def _get_platform_color(platform):
    """Get color for platform."""
    colors = {
        "tiktok": "#000000",
        "instagram": "#E4405F",
        "youtube": "#FF0000",
    }
    return colors.get(platform.lower(), "#666666")


def _get_creator_status(submission_status):
    """Map submission status to creator status."""
    status_map = {
        "new": "New",
        "in_review": "In Review",
        "verified": "Approved",
        "flagged": "Disputed",
        "needs_reupload": "Needs Re-upload",
    }
    return status_map.get(submission_status, "Unknown")


def _calculate_risk_level(influencer):
    """Calculate risk level for an influencer verification."""
    # Check if they have verified platforms
    verified_platforms = influencer.platform_connections.filter(verification_status="verified")
    if not verified_platforms.exists():
        return "high"
    
    # Check if they meet minimum followers
    if not influencer.has_minimum_followers:
        return "medium"
    
    # Check for flags in platform connections
    for conn in influencer.platform_connections.all():
        if conn.verification_flags and len(conn.verification_flags) > 2:
            return "medium"
        # Check for follower count discrepancies
        if conn.verified_followers_count and conn.followers_count:
            discrepancy = abs(conn.verified_followers_count - conn.followers_count)
            if discrepancy > conn.followers_count * 0.1:  # More than 10% difference
                return "medium"
    
    return "low"


def _calculate_brand_risk_level(brand):
    """Calculate risk level for a brand verification."""
    # Check if profile is complete
    if not brand.is_profile_complete:
        return "medium"
    
    # Check if website is provided and valid
    if not brand.website:
        return "low"  # Website is optional
    
    # Additional checks can be added here (e.g., domain age, business registration)
    return "low"


# Notification views

@login_required
def get_notifications(request):
    """Get notifications for the current user (JSON API)."""
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:10]
    
    unread_count = Notification.objects.filter(user=request.user, is_read=False).count()
    
    notifications_data = []
    for notif in notifications:
        notifications_data.append({
            'id': notif.id,
            'title': notif.title,
            'message': notif.message,
            'type': notif.notification_type,
            'is_read': notif.is_read,
            'link': notif.link or '',
            'created_at': notif.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'time_ago': _time_ago(notif.created_at),
        })
    
    return JsonResponse({
        'notifications': notifications_data,
        'unread_count': unread_count,
    })


@login_required
def mark_notification_read(request, notification_id):
    """Mark a notification as read."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.mark_as_read()
    
    return JsonResponse({"success": True})
