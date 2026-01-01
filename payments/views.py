from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect
import json

from .models import PaymentTransaction
from .paystack_service import PaystackService
from brands.models import Brand


@login_required
def payment_callback(request):
    """
    Handle Paystack payment callback after user completes payment.
    """
    reference = request.GET.get('reference')
    
    if not reference:
        messages.error(request, "Invalid payment reference.")
        return redirect("brands:wallet")
    
    try:
        transaction = PaymentTransaction.objects.get(paystack_reference=reference)
        
        # Verify transaction with Paystack
        paystack_response = PaystackService.verify_transaction(reference)
        
        if paystack_response.get('status') and paystack_response.get('data'):
            data = paystack_response['data']
            
            if data.get('status') == 'success':
                # Payment successful
                transaction.status = PaymentTransaction.Status.SUCCESS
                transaction.paystack_authorization_code = data.get('authorization', {}).get('authorization_code', '')
                transaction.paystack_customer_code = data.get('customer', {}).get('customer_code', '')
                transaction.paid_at = timezone.now()
                transaction.save()
                
                # Check if this is for adding a payment method
                is_adding_payment_method = transaction.metadata.get('add_payment_method', False)
                
                if is_adding_payment_method:
                    # Payment method added successfully - don't add to wallet
                    currency_symbol = transaction.brand.currency_symbol if transaction.brand else '₵'
                    messages.success(
                        request,
                        f"Payment method added successfully! The verification charge of {currency_symbol}{transaction.amount:,.2f} will be refunded."
                    )
                    # In a real implementation, you might want to refund this amount immediately
                    # or mark it for refund. For now, we'll just redirect to billing.
                    return redirect("brands:billing")
                elif transaction.brand and transaction.payment_type == PaymentTransaction.PaymentType.WALLET_TOPUP:
                    # Add amount to wallet (only for actual top-ups, not payment method additions)
                    transaction.brand.wallet_balance += transaction.amount
                    transaction.brand.save()
                    currency_symbol = transaction.brand.currency_symbol
                    messages.success(
                        request, 
                        f"Payment successful! {currency_symbol}{transaction.amount:,.2f} has been added to your wallet."
                    )
                    return redirect("brands:wallet")
                else:
                    messages.success(request, "Payment successful!")
                    return redirect("brands:billing")
            else:
                # Payment failed
                transaction.status = PaymentTransaction.Status.FAILED
                transaction.save()
                messages.error(request, "Payment was not successful. Please try again.")
                return redirect("brands:wallet")
        else:
            messages.error(request, "Could not verify payment. Please contact support.")
            return redirect("brands:wallet")
            
    except PaymentTransaction.DoesNotExist:
        messages.error(request, "Transaction not found.")
        return redirect("brands:wallet")
    except Exception as e:
        messages.error(request, f"An error occurred: {str(e)}")
        return redirect("brands:wallet")


@csrf_exempt
@require_POST
def paystack_webhook(request):
    """
    Handle Paystack webhook for payment events.
    This endpoint is called by Paystack when payment status changes.
    """
    from django.conf import settings
    
    # Get webhook signature
    signature = request.headers.get('X-Paystack-Signature', '')
    
    # Get request body
    payload = request.body.decode('utf-8')
    
    # Verify signature (skip in DEBUG mode for easier local testing)
    if not settings.DEBUG:
        if not PaystackService.verify_webhook_signature(payload, signature):
            return JsonResponse({'status': 'error', 'message': 'Invalid signature'}, status=400)
    elif not signature:
        # In DEBUG mode, log if signature is missing but don't fail
        import logging
        logger = logging.getLogger(__name__)
        logger.warning("Webhook called without signature in DEBUG mode")
    
    try:
        event_data = json.loads(payload)
        event_type = event_data.get('event')
        data = event_data.get('data', {})
        
        if event_type == 'charge.success':
            # Payment successful
            reference = data.get('reference')
            
            try:
                transaction = PaymentTransaction.objects.get(paystack_reference=reference)
                
                if transaction.status == PaymentTransaction.Status.PENDING:
                    transaction.status = PaymentTransaction.Status.SUCCESS
                    transaction.paystack_authorization_code = data.get('authorization', {}).get('authorization_code', '')
                    transaction.paystack_customer_code = data.get('customer', {}).get('customer_code', '')
                    transaction.paid_at = timezone.now()
                    transaction.save()
                    
                    # Add amount to wallet
                    if transaction.brand and transaction.payment_type == PaymentTransaction.PaymentType.WALLET_TOPUP:
                        transaction.brand.wallet_balance += transaction.amount
                        transaction.brand.save()
            
            except PaymentTransaction.DoesNotExist:
                pass  # Transaction not found, ignore
        
        elif event_type == 'charge.failed':
            # Payment failed
            reference = data.get('reference')
            
            try:
                transaction = PaymentTransaction.objects.get(paystack_reference=reference)
                if transaction.status == PaymentTransaction.Status.PENDING:
                    transaction.status = PaymentTransaction.Status.FAILED
                    transaction.save()
            except PaymentTransaction.DoesNotExist:
                pass
        
        return JsonResponse({'status': 'success'})
    
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
