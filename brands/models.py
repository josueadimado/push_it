from django.db import models
from accounts.models import User
import random
from datetime import timedelta
from django.utils import timezone


class Currency(models.Model):
    """Currency model for supporting multiple currencies. Managed by admins."""
    
    code = models.CharField(max_length=3, unique=True, help_text="ISO 4217 currency code (e.g., NGN, USD, EUR)")
    name = models.CharField(max_length=50, help_text="Currency name (e.g., Nigerian Naira, US Dollar)")
    symbol = models.CharField(max_length=10, help_text="Currency symbol (e.g., ₦, $, €)")
    is_default = models.BooleanField(
        default=False,
        help_text="Whether this is the default currency for new brands"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this currency is available for selection"
    )
    exchange_rate = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=1.0000,
        help_text="Exchange rate to default currency (for conversion purposes)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Currency"
        verbose_name_plural = "Currencies"
        ordering = ['is_default', 'name']

    def __str__(self):
        return f"{self.code} - {self.name} ({self.symbol})"
    
    def save(self, *args, **kwargs):
        # Ensure only one default currency
        if self.is_default:
            Currency.objects.filter(is_default=True).update(is_default=False)
        super().save(*args, **kwargs)
    
    @classmethod
    def get_default(cls):
        """Get the default currency (Ghanaian Cedi for Ghana-based accounts)."""
        return cls.objects.filter(is_default=True).first() or cls.objects.filter(code='GHS').first()


class Industry(models.Model):
    """Industry model for brands. Managed by admins."""
    
    name = models.CharField(max_length=100, unique=True, help_text="Industry name (e.g., Fashion, Technology, Food & Beverage)")
    description = models.TextField(blank=True, help_text="Optional description of this industry")
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this industry is available for selection"
    )
    icon = models.CharField(
        max_length=50,
        blank=True,
        help_text="Icon name (e.g., 'lucide:shirt' for Fashion)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Industry"
        verbose_name_plural = "Industries"
        ordering = ['name']

    def __str__(self):
        return self.name


class Brand(models.Model):
    """Brand profile extending the User model."""
    
    class VerificationStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        VERIFIED = "verified", "Verified"
        REJECTED = "rejected", "Rejected"
        REQUEST_INFO = "request_info", "Request Info"
        PAUSED = "paused", "Paused"  # Admin can pause verified accounts
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="brand_profile")
    company_name = models.CharField(max_length=200, blank=True)
    website = models.URLField(blank=True, null=True)
    industry = models.ForeignKey(
        'Industry',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='brands',
        help_text="Primary industry/category"
    )
    # Keep legacy field for backward compatibility during migration
    industry_legacy = models.CharField(max_length=100, blank=True, help_text="Legacy industry field")
    description = models.TextField(blank=True, help_text="Company description")
    
    # Company logo
    logo = models.ImageField(
        upload_to='brands/logos/',
        blank=True,
        null=True,
        help_text="Company logo (recommended size: 400x400px)"
    )
    
    # Contact information
    contact_email = models.EmailField(blank=True, null=True)
    phone_number = models.CharField(max_length=30, blank=True, help_text="International format: +1 (555) 123-4567")
    address = models.TextField(blank=True)
    
    # Verification
    verification_status = models.CharField(
        max_length=20,
        choices=VerificationStatus.choices,
        default=VerificationStatus.PENDING,
    )
    
    # Profile completion tracking
    profile_completed = models.BooleanField(default=False)
    
    # Wallet balance for campaign payments
    wallet_balance = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text="Available balance for creating campaigns"
    )
    
    # Currency for wallet and payments
    currency = models.ForeignKey(
        'Currency',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='brands',
        help_text="Currency for wallet and payments"
    )
    
    # Admin review tracking
    paused_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="paused_brands",
        help_text="Admin who paused this account"
    )
    paused_at = models.DateTimeField(null=True, blank=True)
    pause_reason = models.TextField(blank=True, help_text="Reason for pausing the account")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.company_name or self.user.username
    
    def save(self, *args, **kwargs):
        # Set default currency (Naira) if not set
        if not self.currency_id:
            default_currency = Currency.get_default()
            if default_currency:
                self.currency = default_currency
        super().save(*args, **kwargs)
    
    @property
    def currency_symbol(self):
        """Get currency symbol for display."""
        return self.currency.symbol if self.currency else '₦'
    
    @property
    def currency_code(self):
        """Get currency code for display."""
        return self.currency.code if self.currency else 'NGN'
    
    @property
    def is_verified(self):
        """Check if brand is verified."""
        return self.verification_status == self.VerificationStatus.VERIFIED
    
    @property
    def is_paused(self):
        """Check if brand account is paused."""
        return self.verification_status == self.VerificationStatus.PAUSED
    
    @property
    def is_profile_complete(self):
        """Check if required profile fields are filled."""
        # Simplified: only company name and industry are required
        return bool(
            self.company_name and
            (self.industry or self.industry_legacy)
        )
    
    def pause(self, admin_user, reason=""):
        """Pause the brand account (admin action)."""
        self.verification_status = self.VerificationStatus.PAUSED
        self.paused_by = admin_user
        self.paused_at = timezone.now()
        self.pause_reason = reason
        self.save()
    
    def unpause(self):
        """Unpause the brand account."""
        if self.is_verified:
            # If it was verified before, restore to verified
            self.verification_status = self.VerificationStatus.VERIFIED
        else:
            # Otherwise keep as pending
            self.verification_status = self.VerificationStatus.PENDING
        self.paused_by = None
        self.paused_at = None
        self.pause_reason = ""
        self.save()


class BrandVerificationQueue(models.Model):
    """Queue for delayed brand verification."""
    
    brand = models.OneToOneField(Brand, on_delete=models.CASCADE, related_name="verification_queue")
    scheduled_at = models.DateTimeField(help_text="When to process this verification")
    processed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['scheduled_at']
    
    @classmethod
    def schedule_verification(cls, brand):
        """Schedule verification for a brand with random 5-10 minute delay."""
        # Random delay between 5 and 10 minutes
        delay_minutes = random.randint(5, 10)
        scheduled_at = timezone.now() + timedelta(minutes=delay_minutes)
        
        # Create or update queue entry
        queue_entry, created = cls.objects.get_or_create(
            brand=brand,
            defaults={'scheduled_at': scheduled_at}
        )
        if not created:
            queue_entry.scheduled_at = scheduled_at
            queue_entry.processed = False
            queue_entry.save()
        
        return queue_entry
    
    def __str__(self):
        return f"Verification for {self.brand} scheduled at {self.scheduled_at}"
