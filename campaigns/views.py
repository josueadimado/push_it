from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db import transaction as db_transaction
from decimal import Decimal
import uuid

from accounts.decorators import brand_profile_required
from .models import Campaign
from .forms import CampaignForm
from payments.models import PaymentTransaction


@brand_profile_required
def create_campaign(request):
    """
    Create a new campaign with wallet balance check and deduction.
    """
    brand = request.user.brand_profile
    
    # Check if brand has currency set
    if not brand.currency:
        from brands.models import Currency
        default_currency = Currency.get_default()
        if default_currency:
            brand.currency = default_currency
            brand.save()
    
    if request.method == 'POST':
        form = CampaignForm(request.POST, brand=brand)
        
        if form.is_valid():
            try:
                # Use database transaction to ensure atomicity
                with db_transaction.atomic():
                    # Check wallet balance one more time (in case it changed)
                    budget = form.cleaned_data['budget']
                    
                    if brand.wallet_balance < budget:
                        messages.error(
                            request,
                            f"Insufficient wallet balance. You have {brand.currency_symbol}{brand.wallet_balance:,.2f} "
                            f"but need {brand.currency_symbol}{budget:,.2f}. Please top up your wallet."
                        )
                        return render(request, 'campaigns/create_campaign.html', {
                            'form': form,
                            'brand': brand,
                            'wallet_balance': brand.wallet_balance,
                            'currency_symbol': brand.currency_symbol,
                        })
                    
                    # Create campaign
                    campaign = form.save(commit=False)
                    campaign.brand = brand
                    campaign.status = Campaign.Status.DRAFT  # Start as draft
                    campaign.save()
                    
                    # Deduct budget from wallet
                    brand.wallet_balance -= budget
                    brand.save()
                    
                    # Create payment transaction record
                    payment_transaction = PaymentTransaction.objects.create(
                        user=request.user,
                        brand=brand,
                        amount=budget,
                        currency=brand.currency_code,
                        paystack_reference=f"CAMPAIGN_{uuid.uuid4().hex[:12].upper()}",
                        payment_type=PaymentTransaction.PaymentType.CAMPAIGN_PAYMENT,
                        status=PaymentTransaction.Status.SUCCESS,  # Already deducted, so it's successful
                        description=f"Campaign payment: {campaign.name}",
                        paid_at=timezone.now(),
                        metadata={
                            'campaign_id': campaign.id,
                            'campaign_name': campaign.name,
                            'wallet_deduction': True,
                        }
                    )
                    
                    messages.success(
                        request,
                        f"Campaign '{campaign.name}' created successfully! "
                        f"{brand.currency_symbol}{budget:,.2f} has been deducted from your wallet. "
                        f"Remaining balance: {brand.currency_symbol}{brand.wallet_balance:,.2f}"
                    )
                    
                    return redirect('brands:campaigns')
                    
            except Exception as e:
                messages.error(request, f"An error occurred while creating the campaign: {str(e)}")
        else:
            # Form has errors, show them
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = CampaignForm(brand=brand)
    
    context = {
        'form': form,
        'brand': brand,
        'wallet_balance': brand.wallet_balance,
        'currency_symbol': brand.currency_symbol,
        'currency_code': brand.currency_code,
    }
    
    return render(request, 'campaigns/create_campaign.html', context)


@brand_profile_required
def edit_campaign(request, campaign_id):
    """
    Edit an existing campaign.
    Note: Budget changes are not allowed after creation to prevent wallet issues.
    """
    brand = request.user.brand_profile
    campaign = get_object_or_404(Campaign, id=campaign_id, brand=brand)
    
    # Don't allow editing if campaign is already active/completed
    if campaign.status in [Campaign.Status.ACTIVE, Campaign.Status.COMPLETED]:
        messages.warning(request, "Cannot edit active or completed campaigns.")
        return redirect('brands:campaigns')
    
    if request.method == 'POST':
        form = CampaignForm(request.POST, instance=campaign, brand=brand)
        
        if form.is_valid():
            # Don't allow budget changes
            if 'budget' in form.changed_data:
                messages.error(request, "Budget cannot be changed after campaign creation.")
                return render(request, 'campaigns/edit_campaign.html', {
                    'form': form,
                    'campaign': campaign,
                    'brand': brand,
                })
            
            form.save()
            messages.success(request, f"Campaign '{campaign.name}' updated successfully!")
            return redirect('brands:campaigns')
    else:
        form = CampaignForm(instance=campaign, brand=brand)
    
    context = {
        'form': form,
        'campaign': campaign,
        'brand': brand,
    }
    
    return render(request, 'campaigns/edit_campaign.html', context)


@brand_profile_required
def activate_campaign(request, campaign_id):
    """
    Activate a campaign (change status from DRAFT to ACTIVE).
    Note: Wallet is already deducted when campaign is created, so we just activate it.
    """
    brand = request.user.brand_profile
    campaign = get_object_or_404(Campaign, id=campaign_id, brand=brand)
    
    if campaign.status != Campaign.Status.DRAFT:
        messages.warning(request, "Only draft campaigns can be activated.")
        return redirect('brands:campaigns')
    
    # Check if payment transaction already exists (wallet was already deducted on creation)
    existing_transaction = PaymentTransaction.objects.filter(
        brand=brand,
        payment_type=PaymentTransaction.PaymentType.CAMPAIGN_PAYMENT,
        metadata__campaign_id=campaign.id
    ).first()
    
    if existing_transaction:
        # Wallet was already deducted, just activate the campaign
        campaign.status = Campaign.Status.ACTIVE
        campaign.save()
        messages.success(
            request,
            f"Campaign '{campaign.name}' activated successfully!"
        )
    else:
        # This shouldn't happen if create_campaign worked correctly, but handle it anyway
        # Check wallet balance
        if brand.wallet_balance < campaign.budget:
            messages.error(
                request,
                f"Insufficient wallet balance. You have {brand.currency_symbol}{brand.wallet_balance:,.2f} "
                f"but need {brand.currency_symbol}{campaign.budget:,.2f}. Please top up your wallet."
            )
            return redirect('brands:campaigns')
        
        try:
            with db_transaction.atomic():
                # Deduct budget from wallet (fallback case)
                brand.wallet_balance -= campaign.budget
                brand.save()
                
                # Update campaign status
                campaign.status = Campaign.Status.ACTIVE
                campaign.save()
                
                # Create payment transaction record
                PaymentTransaction.objects.create(
                    user=request.user,
                    brand=brand,
                    amount=campaign.budget,
                    currency=brand.currency_code,
                    paystack_reference=f"CAMPAIGN_{uuid.uuid4().hex[:12].upper()}",
                    payment_type=PaymentTransaction.PaymentType.CAMPAIGN_PAYMENT,
                    status=PaymentTransaction.Status.SUCCESS,
                    description=f"Campaign activation: {campaign.name}",
                    paid_at=timezone.now(),
                    metadata={
                        'campaign_id': campaign.id,
                        'campaign_name': campaign.name,
                        'wallet_deduction': True,
                    }
                )
                
                messages.success(
                    request,
                    f"Campaign '{campaign.name}' activated successfully! "
                    f"{brand.currency_symbol}{campaign.budget:,.2f} has been deducted from your wallet. "
                    f"Remaining balance: {brand.currency_symbol}{brand.wallet_balance:,.2f}"
                )
                
        except Exception as e:
            messages.error(request, f"An error occurred while activating the campaign: {str(e)}")
    
    return redirect('brands:campaigns')
