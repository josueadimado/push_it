from django.db import models
from accounts.models import User
from brands.models import Brand


class PaymentTransaction(models.Model):
    """Payment transaction model for tracking Paystack payments."""
    
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"
    
    class PaymentType(models.TextChoices):
        WALLET_TOPUP = "wallet_topup", "Wallet Top-up"
        CAMPAIGN_PAYMENT = "campaign_payment", "Campaign Payment"
    
    # User and brand
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="payment_transactions")
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name="payment_transactions", null=True, blank=True)
    
    # Payment details
    amount = models.DecimalField(max_digits=10, decimal_places=2, help_text="Amount in brand's currency")
    currency = models.CharField(max_length=3, default="NGN", help_text="Currency code")
    
    # Paystack details
    paystack_reference = models.CharField(max_length=100, unique=True, help_text="Paystack transaction reference")
    paystack_authorization_code = models.CharField(max_length=100, blank=True, help_text="Paystack authorization code for future charges")
    paystack_customer_code = models.CharField(max_length=100, blank=True, help_text="Paystack customer code")
    
    # Transaction details
    payment_type = models.CharField(max_length=20, choices=PaymentType.choices, default=PaymentType.WALLET_TOPUP)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True, help_text="Additional payment metadata")
    description = models.TextField(blank=True, help_text="Payment description")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['paystack_reference']),
            models.Index(fields=['status', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.payment_type} - {self.amount} {self.currency} ({self.get_status_display()})"
    
    @property
    def is_successful(self):
        """Check if payment was successful."""
        return self.status == self.Status.SUCCESS
    
    @property
    def is_pending(self):
        """Check if payment is pending."""
        return self.status == self.Status.PENDING
