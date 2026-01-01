from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect
from django.db.models import Count, Sum, Q
from django.utils import timezone
from datetime import timedelta

from accounts.decorators import brand_profile_required, brand_verified_required
from campaigns.models import Campaign
from operations.models import Submission


@brand_profile_required
def brand_dashboard(request):
    """
    Brand dashboard view with real campaign data.
    """
    # Get the brand profile for the current user
    brand = request.user.brand_profile
    
    # Ensure brand has a currency
    if not brand.currency:
        from brands.models import Currency
        default_currency = Currency.get_default()
        if default_currency:
            brand.currency = default_currency
            brand.save()
    
    # Get campaigns for this brand
    campaigns = Campaign.objects.filter(brand=brand).select_related('brand')
    
    # Calculate stats
    total_campaigns = campaigns.count()
    active_campaigns = campaigns.filter(status='active').count()
    draft_campaigns = campaigns.filter(status='draft').count()
    completed_campaigns = campaigns.filter(status='completed').count()
    
    # Get submissions for this brand's campaigns
    brand_submissions = Submission.objects.filter(campaign__brand=brand).select_related('campaign', 'influencer')
    
    videos_in_progress = brand_submissions.filter(status__in=['new', 'in_review']).count()
    videos_completed = brand_submissions.filter(status='verified').count()
    videos_pending = brand_submissions.filter(status='new').count()
    
    # Total spend (sum of all campaign budgets that have been paid)
    from payments.models import PaymentTransaction
    total_spend = PaymentTransaction.objects.filter(
        brand=brand,
        payment_type=PaymentTransaction.PaymentType.CAMPAIGN_PAYMENT,
        status=PaymentTransaction.Status.SUCCESS
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # Also calculate from campaign budgets (for display purposes)
    total_budget = campaigns.aggregate(total=Sum('budget'))['total'] or 0
    
    # Recent campaigns (last 5)
    recent_campaigns = campaigns.order_by('-created_at')[:5]
    
    # Calculate delivery progress for each campaign
    campaign_data = []
    for campaign in recent_campaigns:
        delivered = campaign.videos_delivered  # Use the property from Campaign model
        progress = campaign.delivery_progress  # Use the property from Campaign model
        
        campaign_data.append({
            'campaign': campaign,
            'delivered': delivered,
            'progress': progress,
        })
    
    # Calculate new campaigns this week
    week_ago = timezone.now() - timedelta(days=7)
    new_this_week = campaigns.filter(created_at__gte=week_ago).count()
    
    # Calculate completed videos this month
    month_ago = timezone.now() - timedelta(days=30)
    completed_this_month = brand_submissions.filter(status='verified', reviewed_at__gte=month_ago).count()
    
    # Wallet balance
    wallet_balance = brand.wallet_balance
    
    context = {
        'active_page': 'dashboard',
        'brand': brand,
        'stats': {
            'total_campaigns': total_campaigns,
            'active_campaigns': active_campaigns,
            'draft_campaigns': draft_campaigns,
            'completed_campaigns': completed_campaigns,
            'videos_in_progress': videos_in_progress,
            'videos_pending': videos_pending,
            'videos_completed': videos_completed,
            'total_spend': float(total_spend),
            'total_budget': float(total_budget),
            'new_this_week': new_this_week,
            'completed_this_month': completed_this_month,
            'wallet_balance': float(wallet_balance),
        },
        'campaign_data': campaign_data,
    }
    return render(request, "brands/dashboard.html", context)


@brand_profile_required
def brand_wallet(request):
    """
    Brand wallet view for top-up and balance management with Paystack integration.
    """
    from decimal import Decimal
    from django.contrib import messages
    from .models import Currency
    from payments.paystack_service import PaystackService
    from payments.models import PaymentTransaction
    import uuid
    
    brand = request.user.brand_profile
    
    # Ensure brand has a currency (set default if not)
    if not brand.currency:
        default_currency = Currency.get_default()
        if default_currency:
            brand.currency = default_currency
            brand.save()
    
    if request.method == "POST":
        if 'top_up' in request.POST:
            # Initialize Paystack payment
            amount_str = request.POST.get('amount', '0')
            try:
                amount = Decimal(amount_str)
                if amount <= 0:
                    messages.error(request, "Please enter a valid amount greater than zero.")
                else:
                    # Generate unique reference
                    reference = f"WALLET_{uuid.uuid4().hex[:12].upper()}"
                    
                    # Create pending transaction
                    transaction = PaymentTransaction.objects.create(
                        user=request.user,
                        brand=brand,
                        amount=amount,
                        currency=brand.currency_code,
                        paystack_reference=reference,
                        payment_type=PaymentTransaction.PaymentType.WALLET_TOPUP,
                        status=PaymentTransaction.Status.PENDING,
                        description=f"Wallet top-up of {brand.currency_symbol}{amount:,.2f}",
                        metadata={
                            "wallet_topup": True,
                            "brand_id": brand.id,
                        }
                    )
                    
                    # Build callback URL for payment redirect
                    from django.urls import reverse
                    # Use request to build absolute URL
                    callback_url = request.build_absolute_uri(reverse('payments:callback'))
                    
                    # Initialize Paystack transaction
                    paystack_response = PaystackService.initialize_transaction(
                        email=request.user.email,
                        amount=float(amount),
                        currency=brand.currency_code,
                        reference=reference,
                        callback_url=callback_url,
                        metadata={
                            "transaction_id": transaction.id,
                            "brand_id": brand.id,
                            "custom_fields": [
                                {
                                    "display_name": "Payment Type",
                                    "variable_name": "payment_type",
                                    "value": "Wallet Top-up"
                                }
                            ]
                        }
                    )
                    
                    if paystack_response.get('status') and paystack_response.get('data'):
                        # Redirect to Paystack payment page
                        authorization_url = paystack_response['data']['authorization_url']
                        return redirect(authorization_url)
                    else:
                        transaction.status = PaymentTransaction.Status.FAILED
                        transaction.save()
                        error_message = paystack_response.get('message', 'Failed to initialize payment. Please try again.')
                        messages.error(request, f"Payment initialization failed: {error_message}")
            except (ValueError, TypeError) as e:
                messages.error(request, "Please enter a valid amount.")
            except Exception as e:
                messages.error(request, f"An error occurred: {str(e)}")
    
    # Get all active currencies for selection
    currencies = Currency.objects.filter(is_active=True).order_by('is_default', 'name')
    
    # Get recent transactions
    recent_transactions = PaymentTransaction.objects.filter(
        user=request.user,
        brand=brand
    ).order_by('-created_at')[:5]
    
    context = {
        'active_page': 'wallet',
        'brand': brand,
        'wallet_balance': brand.wallet_balance,
        'currency': brand.currency,
        'currency_symbol': brand.currency_symbol,
        'currency_code': brand.currency_code,
        'currencies': currencies,
        'recent_transactions': recent_transactions,
        'paystack_public_key': PaystackService.get_public_key(),
    }
    return render(request, "brands/wallet.html", context)


@brand_profile_required
def brand_campaigns(request):
    """
    Brand campaigns list view with filters and search.
    """
    from decimal import Decimal
    
    # Get the brand profile for the current user
    brand = None
    try:
        brand = request.user.brand_profile
    except:
        pass
    
    # Check wallet balance and show message if low
    if brand and brand.wallet_balance <= 0:
        messages.warning(request, "Your wallet balance is low. Please top up to create new campaigns.")
    
    # Get campaigns for this brand
    if brand:
        campaigns = Campaign.objects.filter(brand=brand).select_related('brand').order_by('-created_at')
    else:
        campaigns = Campaign.objects.none()
    
    # Get filter parameters
    status_filter = request.GET.get('status', '')
    platform_filter = request.GET.get('platform', '')
    search_query = request.GET.get('search', '')
    
    # Apply filters
    if status_filter:
        campaigns = campaigns.filter(status=status_filter)
    
    if platform_filter:
        campaigns = campaigns.filter(platform=platform_filter)
    
    if search_query:
        campaigns = campaigns.filter(name__icontains=search_query)
    
    # Calculate delivery progress for each campaign
    campaign_data = []
    for campaign in campaigns:
        submissions = Submission.objects.filter(campaign=campaign, status='verified')
        delivered = submissions.count()
        progress = int((delivered / campaign.package_videos * 100)) if campaign.package_videos > 0 else 0
        
        # Determine status badge
        if campaign.status == 'active':
            if delivered == campaign.package_videos:
                status_badge = 'review'  # All videos delivered, awaiting review
            else:
                status_badge = 'active'
        elif campaign.status == 'completed':
            status_badge = 'completed'
        elif campaign.status == 'draft':
            status_badge = 'draft'
        else:
            status_badge = campaign.status
        
        campaign_data.append({
            'campaign': campaign,
            'delivered': delivered,
            'progress': progress,
            'status_badge': status_badge,
        })
    
    context = {
        'active_page': 'campaigns',
        'brand': brand,
        'campaign_data': campaign_data,
        'total_campaigns': campaigns.count(),
        'current_filters': {
            'status': status_filter,
            'platform': platform_filter,
            'search': search_query,
        },
    }
    return render(request, "brands/campaigns.html", context)


@brand_profile_required
def brand_billing(request):
    """
    Brand billing and payments view.
    Shows payment methods, spending summary, and invoice history.
    """
    # Get the brand profile for the current user
    brand = None
    try:
        brand = request.user.brand_profile
    except:
        pass
    
    # Get campaigns for this brand
    if brand:
        campaigns = Campaign.objects.filter(brand=brand).select_related('brand')
    else:
        campaigns = Campaign.objects.none()
    
    # Get payment transactions for wallet top-ups
    from payments.models import PaymentTransaction
    
    # Calculate spending (campaigns + wallet top-ups)
    total_campaign_spend = campaigns.aggregate(total=Sum('budget'))['total'] or 0
    total_topups = PaymentTransaction.objects.filter(
        brand=brand,
        payment_type=PaymentTransaction.PaymentType.WALLET_TOPUP,
        status=PaymentTransaction.Status.SUCCESS
    ).aggregate(total=Sum('amount'))['total'] or 0
    total_spend = total_campaign_spend + total_topups
    
    # Calculate this month's spending
    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    this_month_campaigns = campaigns.filter(created_at__gte=month_start)
    this_month_campaign_spend = this_month_campaigns.aggregate(total=Sum('budget'))['total'] or 0
    this_month_topups = PaymentTransaction.objects.filter(
        brand=brand,
        payment_type=PaymentTransaction.PaymentType.WALLET_TOPUP,
        status=PaymentTransaction.Status.SUCCESS,
        created_at__gte=month_start
    ).aggregate(total=Sum('amount'))['total'] or 0
    this_month_spend = this_month_campaign_spend + this_month_topups
    
    # Generate invoice history from campaigns and wallet top-ups (sorted by date, most recent first)
    invoices = []
    
    # Add wallet top-ups
    topup_transactions = PaymentTransaction.objects.filter(
        brand=brand,
        payment_type=PaymentTransaction.PaymentType.WALLET_TOPUP,
        status=PaymentTransaction.Status.SUCCESS
    ).order_by('-created_at')[:20]
    
    for transaction in topup_transactions:
        invoices.append({
            'date': transaction.created_at,
            'description': f"Wallet Top-up - {transaction.description}",
            'amount': float(transaction.amount),
            'status': 'paid',
            'type': 'topup',
            'transaction_id': transaction.id,
        })
    
    # Add campaigns
    for campaign in campaigns.order_by('-created_at')[:20]:
        invoices.append({
            'date': campaign.created_at,
            'description': f"{campaign.name} - Campaign #{campaign.id}",
            'amount': float(campaign.budget),
            'status': 'paid',
            'type': 'campaign',
            'campaign_id': campaign.id,
        })
    
    # Sort all invoices by date (most recent first) and limit to 20
    invoices.sort(key=lambda x: x['date'], reverse=True)
    invoices = invoices[:20]
    
    # Get payment methods from successful Paystack transactions with authorization codes
    payment_methods = []
    # Fetch saved payment methods from Paystack using stored authorization codes
    # This would require additional API calls to Paystack's customer/authorization endpoints
    # For now, we'll show cards that have been used successfully
    successful_transactions = PaymentTransaction.objects.filter(
        brand=brand,
        status=PaymentTransaction.Status.SUCCESS,
        paystack_authorization_code__isnull=False
    ).exclude(paystack_authorization_code='').order_by('-created_at')
    
    seen_cards = set()
    for transaction in successful_transactions:
        auth_code = transaction.paystack_authorization_code
        if auth_code and auth_code not in seen_cards:
            # In a real implementation, you'd fetch card details from Paystack API
            # For now, we'll just show that a card was used
            # You can enhance this by calling Paystack's authorization endpoint
            seen_cards.add(auth_code)
            # Note: To get actual card details, you'd need to call:
            # GET https://api.paystack.co/transaction/verify/{reference}
            # or use the authorization code to get card details
    
    context = {
        'active_page': 'billing',
        'brand': brand,
        'payment_methods': payment_methods,
        'currency_symbol': brand.currency_symbol if brand else '₵',
        'currency_code': brand.currency_code if brand else 'GHS',
        'spending': {
            'this_month': float(this_month_spend),
            'lifetime': float(total_spend),
        },
        'invoices': invoices,
    }
    return render(request, "brands/billing.html", context)


@brand_profile_required
def brand_profile(request):
    """
    Brand company profile view.
    Shows company details, contact information, and verification status.
    Allows editing of profile information.
    """
    from accounts.forms import BrandProfileForm
    from brands.models import Brand
    
    # Get the brand profile for the current user
    brand = None
    try:
        brand = request.user.brand_profile
    except:
        pass
    
    # Handle form submission
    if request.method == 'POST':
        form = BrandProfileForm(request.POST, request.FILES, instance=brand)
        if form.is_valid():
            form.save()
            # Update profile completion status
            brand.profile_completed = brand.is_profile_complete
            brand.save()
            messages.success(request, "Profile updated successfully!")
            return redirect('brands:profile')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = BrandProfileForm(instance=brand)
    
    # Determine verification status - use actual brand status
    if brand:
        verification_status = brand.verification_status
        email_verified = request.user.is_email_verified
        business_verified = (brand.verification_status == Brand.VerificationStatus.VERIFIED)
        
        # Get verification queue info to show when verification was scheduled
        verification_scheduled_at = None
        verification_processed = False
        try:
            queue_entry = brand.verification_queue
            verification_scheduled_at = queue_entry.scheduled_at
            verification_processed = queue_entry.processed
        except:
            pass
        
        # Check if payment method exists (has saved authorization code)
        from payments.models import PaymentTransaction
        payment_method_added = PaymentTransaction.objects.filter(
            brand=brand,
            status=PaymentTransaction.Status.SUCCESS,
            paystack_authorization_code__isnull=False
        ).exclude(paystack_authorization_code='').exists()
    else:
        verification_status = 'pending'
        email_verified = False
        business_verified = False
        payment_method_added = False
        verification_scheduled_at = None
        verification_processed = False
    
    context = {
        'active_page': 'profile',
        'brand': brand,
        'form': form,
        'verification': {
            'status': verification_status,
            'email_verified': email_verified,
            'business_verified': business_verified,
            'payment_method_added': payment_method_added,
            'scheduled_at': verification_scheduled_at,
            'processed': verification_processed,
        },
    }
    return render(request, "brands/profile.html", context)


@brand_profile_required
def add_payment_method(request):
    """
    Add a new payment method using Paystack inline form.
    This allows users to enter card details directly on the page.
    """
    from payments.paystack_service import PaystackService
    from django.urls import reverse
    import uuid
    
    brand = request.user.brand_profile
    
    # Ensure brand has a currency
    if not brand.currency:
        from brands.models import Currency
        default_currency = Currency.get_default()
        if default_currency:
            brand.currency = default_currency
            brand.save()
    
    # Get Paystack public key for inline form
    paystack_public_key = PaystackService.get_public_key()
    
    # Generate a unique reference for this card addition
    reference = f"CARD_{uuid.uuid4().hex[:12].upper()}"
    
    context = {
        'brand': brand,
        'currency_symbol': brand.currency_symbol,
        'currency_code': brand.currency_code,
        'paystack_public_key': paystack_public_key,
        'reference': reference,
        'user_email': request.user.email,
    }
    return render(request, "brands/add_payment_method.html", context)


@brand_profile_required
def save_payment_method(request):
    """
    Save payment method after Paystack inline form submission.
    This endpoint receives the authorization code from the frontend.
    """
    from payments.models import PaymentTransaction
    from payments.paystack_service import PaystackService
    from django.http import JsonResponse
    import json
    
    if request.method != "POST":
        return JsonResponse({'status': False, 'message': 'Invalid request method'}, status=405)
    
    try:
        data = json.loads(request.body)
        authorization_code = data.get('authorization_code')
        reference = data.get('reference')
        
        if not authorization_code:
            return JsonResponse({'status': False, 'message': 'Authorization code is required'}, status=400)
        
        brand = request.user.brand_profile
        
        # Verify the transaction to get card details
        if reference:
            verify_response = PaystackService.verify_transaction(reference)
            if verify_response.get('status') and verify_response.get('data'):
                transaction_data = verify_response['data']
                authorization = transaction_data.get('authorization', {})
                
                # Create a record of the saved payment method
                # Note: We're not creating a PaymentTransaction here since no money was charged
                # Instead, we'll store the authorization code for future use
                # In a real implementation, you might want a PaymentMethod model
                
                # For now, we'll create a minimal transaction record to track saved cards
                PaymentTransaction.objects.create(
                    user=request.user,
                    brand=brand,
                    amount=0,  # No charge for saving card
                    currency=brand.currency_code,
                    paystack_reference=reference,
                    paystack_authorization_code=authorization_code,
                    paystack_customer_code=transaction_data.get('customer', {}).get('customer_code', ''),
                    payment_type=PaymentTransaction.PaymentType.WALLET_TOPUP,  # Using as placeholder
                    status=PaymentTransaction.Status.SUCCESS,
                    description="Payment method saved",
                    metadata={
                        "add_payment_method": True,
                        "brand_id": brand.id,
                        "card_type": authorization.get('brand', ''),
                        "last4": authorization.get('last4', ''),
                        "exp_month": authorization.get('exp_month', ''),
                        "exp_year": authorization.get('exp_year', ''),
                    }
                )
                
                return JsonResponse({
                    'status': True,
                    'message': 'Payment method saved successfully'
                })
        
        return JsonResponse({'status': False, 'message': 'Failed to verify transaction'}, status=400)
        
    except json.JSONDecodeError:
        return JsonResponse({'status': False, 'message': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'status': False, 'message': str(e)}, status=500)


@brand_profile_required
def brand_settings(request):
    """
    Brand settings view.
    Shows team members, notifications, security, and account deletion options.
    """
    # Get the brand profile for the current user
    brand = None
    try:
        brand = request.user.brand_profile
    except:
        pass
    
    # Team members (for now, just show the current user)
    # In a real app, this would come from a TeamMember model
    team_members = [
        {
            'name': request.user.get_full_name() or request.user.username,
            'email': request.user.email,
            'role': 'Admin',
            'avatar': None,
        },
    ]
    
    # Notification preferences (demo data - can be replaced with UserPreferences model)
    notification_prefs = {
        'campaign_updates': True,
        'billing_alerts': True,
        'marketing_tips': False,
    }
    
    # Security settings
    two_factor_enabled = False  # Would check actual 2FA status
    
    context = {
        'active_page': 'settings',
        'brand': brand,
        'team_members': team_members,
        'notification_prefs': notification_prefs,
        'two_factor_enabled': two_factor_enabled,
    }
    return render(request, "brands/settings.html", context)
