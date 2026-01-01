"""
Paystack payment integration service.
Handles payment initialization and verification.
"""
import requests
import hashlib
import hmac
from decimal import Decimal
from django.conf import settings
from django.utils import timezone


class PaystackService:
    """Service for interacting with Paystack API."""
    
    BASE_URL = "https://api.paystack.co"
    
    @classmethod
    def get_secret_key(cls):
        """Get Paystack secret key from settings."""
        return getattr(settings, 'PAYSTACK_SECRET_KEY', '')
    
    @classmethod
    def get_public_key(cls):
        """Get Paystack public key from settings."""
        return getattr(settings, 'PAYSTACK_PUBLIC_KEY', '')
    
    @classmethod
    def initialize_transaction(cls, email, amount, currency="NGN", reference=None, metadata=None, callback_url=None):
        """
        Initialize a Paystack transaction.
        
        Args:
            email: Customer email
            amount: Amount in kobo (for NGN) or smallest currency unit
            currency: Currency code (default: NGN)
            reference: Custom reference (optional)
            metadata: Additional metadata (optional)
            callback_url: Callback URL for payment redirect (optional)
        
        Returns:
            dict: Response from Paystack API
        """
        secret_key = cls.get_secret_key()
        
        # Validate secret key
        if not secret_key:
            return {
                "status": False,
                "message": "Paystack secret key is not configured. Please add PAYSTACK_SECRET_KEY to your .env file.",
                "data": None
            }
        
        if not secret_key.startswith(('sk_test_', 'sk_live_')):
            return {
                "status": False,
                "message": f"Invalid Paystack secret key format. Key should start with 'sk_test_' or 'sk_live_'. Got: {secret_key[:10]}...",
                "data": None
            }
        
        url = f"{cls.BASE_URL}/transaction/initialize"
        headers = {
            "Authorization": f"Bearer {secret_key}",
            "Content-Type": "application/json"
        }
        
        # Convert amount to smallest currency unit
        # For NGN: 1 Naira = 100 Kobo
        # For GHS: 1 Cedi = 100 Pesewas
        # For USD/EUR/GBP: amount is in cents
        if currency in ["NGN", "GHS"]:
            # Naira and Cedi use 100 as the smallest unit
            amount_in_kobo = int(amount * 100)
        else:
            # For other currencies (USD, EUR, GBP), use smallest unit (cents)
            amount_in_kobo = int(amount * 100)
        
        payload = {
            "email": email,
            "amount": amount_in_kobo,
            "currency": currency,
            "metadata": metadata or {},
            # Force new card entry by disabling saved cards
            "channels": ["card"]  # Only allow card payments, don't show saved cards
        }
        
        if reference:
            payload["reference"] = reference
        
        if callback_url:
            payload["callback_url"] = callback_url
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            
            # Better error handling
            if response.status_code == 403:
                error_data = response.json() if response.content else {}
                error_message = error_data.get('message', 'Forbidden - Check your Paystack secret key')
                
                # Check if it's a currency issue
                if 'currency' in error_message.lower() or 'not supported' in error_message.lower():
                    return {
                        "status": False,
                        "message": f"Currency Error: {error_message}. Please enable {currency} (Nigerian Naira) in your Paystack account settings at https://dashboard.paystack.com/#/settings/business",
                        "data": None
                    }
                
                return {
                    "status": False,
                    "message": f"Paystack API Error (403): {error_message}. Please verify your PAYSTACK_SECRET_KEY in .env file.",
                    "data": None
                }
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            error_data = {}
            try:
                error_data = e.response.json() if e.response.content else {}
            except:
                pass
            
            error_message = error_data.get('message', str(e))
            return {
                "status": False,
                "message": f"Paystack API Error ({e.response.status_code}): {error_message}",
                "data": None
            }
        except requests.exceptions.RequestException as e:
            return {
                "status": False,
                "message": f"Network error: {str(e)}",
                "data": None
            }
    
    @classmethod
    def verify_transaction(cls, reference):
        """
        Verify a Paystack transaction.
        
        Args:
            reference: Paystack transaction reference
        
        Returns:
            dict: Response from Paystack API
        """
        url = f"{cls.BASE_URL}/transaction/verify/{reference}"
        headers = {
            "Authorization": f"Bearer {cls.get_secret_key()}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {
                "status": False,
                "message": str(e),
                "data": None
            }
    
    @classmethod
    def verify_webhook_signature(cls, payload, signature):
        """
        Verify Paystack webhook signature.
        
        Args:
            payload: Raw request body
            signature: X-Paystack-Signature header value
        
        Returns:
            bool: True if signature is valid
        """
        secret_key = cls.get_secret_key()
        computed_signature = hmac.new(
            secret_key.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha512
        ).hexdigest()
        
        return hmac.compare_digest(computed_signature, signature)
    
    @classmethod
    def format_amount_for_display(cls, amount, currency="NGN"):
        """
        Format amount for display based on currency.
        
        Args:
            amount: Amount in smallest currency unit (kobo for NGN)
            currency: Currency code
        
        Returns:
            Decimal: Amount in main currency unit
        """
        if currency == "NGN":
            return Decimal(amount) / 100  # Convert kobo to Naira
        else:
            return Decimal(amount) / 100  # Convert cents to main unit

