from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from accounts.models import User
from django.utils import timezone
import random
from datetime import timedelta


class Niche(models.Model):
    """Niche/Category model for influencers and campaigns. Managed by admins."""
    
    name = models.CharField(max_length=100, unique=True, help_text="Niche name (e.g., Fashion, Fitness, Tech)")
    description = models.TextField(blank=True, help_text="Optional description of this niche")
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this niche is available for selection"
    )
    icon = models.CharField(
        max_length=50,
        blank=True,
        help_text="Icon name (e.g., 'lucide:shirt' for Fashion)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Niche"
        verbose_name_plural = "Niches"
        ordering = ['name']

    def __str__(self):
        return self.name


class PlatformSettings(models.Model):
    """Platform-specific settings like minimum follower requirements."""
    
    class Platform(models.TextChoices):
        TIKTOK = "tiktok", "TikTok"
        INSTAGRAM = "instagram", "Instagram"
        YOUTUBE = "youtube", "YouTube"
        TWITTER = "twitter", "Twitter/X"
        SNAPCHAT = "snapchat", "Snapchat"
        FACEBOOK = "facebook", "Facebook"
    
    platform = models.CharField(
        max_length=20,
        choices=Platform.choices,
        unique=True,
        help_text="Platform name"
    )
    minimum_followers = models.IntegerField(
        default=1000,
        help_text="Minimum follower count required for this platform"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this platform is available for influencers"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Platform Setting"
        verbose_name_plural = "Platform Settings"
        ordering = ['platform']

    def __str__(self):
        return f"{self.get_platform_display()} (Min: {self.minimum_followers:,} followers)"
    
    @classmethod
    def get_minimum_followers(cls, platform):
        """Get minimum follower requirement for a platform."""
        try:
            setting = cls.objects.get(platform=platform, is_active=True)
            return setting.minimum_followers
        except cls.DoesNotExist:
            # Default to 1000 if not configured
            return 1000


class PlatformConnection(models.Model):
    """Platform connection for influencers (Instagram, TikTok, YouTube, etc.)"""
    
    class Platform(models.TextChoices):
        TIKTOK = "tiktok", "TikTok"
        INSTAGRAM = "instagram", "Instagram"
        YOUTUBE = "youtube", "YouTube"
        TWITTER = "twitter", "Twitter/X"
        SNAPCHAT = "snapchat", "Snapchat"
        FACEBOOK = "facebook", "Facebook"
    
    class VerificationStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        VERIFIED = "verified", "Verified"
        REJECTED = "rejected", "Rejected"
        FAILED = "failed", "Verification Failed"
    
    influencer = models.ForeignKey('Influencer', on_delete=models.CASCADE, related_name="platform_connections")
    platform = models.CharField(max_length=20, choices=Platform.choices)
    handle = models.CharField(max_length=100, help_text="Platform handle (without @)")
    followers_count = models.IntegerField(default=0, help_text="Number of followers/subscribers (user-provided)")
    verified_followers_count = models.IntegerField(
        null=True, 
        blank=True, 
        help_text="Actual follower count verified from platform API"
    )
    follower_verification_date = models.DateTimeField(
        null=True, 
        blank=True, 
        help_text="When follower count was last verified from API"
    )
    
    # Verification
    verification_status = models.CharField(
        max_length=20,
        choices=VerificationStatus.choices,
        default=VerificationStatus.PENDING,
    )
    
    # Automated verification tracking
    verification_confidence = models.FloatField(
        default=0.0,
        help_text="Confidence score from automated verification (0.0 to 1.0)"
    )
    verification_flags = models.JSONField(
        default=list,
        blank=True,
        help_text="List of flags/warnings from automated verification"
    )
    verification_method = models.CharField(
        max_length=20,
        choices=[
            ('auto', 'Automated'),
            ('manual', 'Manual Review'),
            ('api', 'Platform API'),
        ],
        default='auto',
        help_text="Method used for verification"
    )
    
    # Stats (pulled from platform API or manual entry)
    engagement_rate = models.FloatField(default=0.0, help_text="Engagement rate percentage")
    avg_views = models.IntegerField(default=0, help_text="Average views per post")
    sample_post_url = models.URLField(blank=True, null=True, help_text="Sample post for verification")
    
    # OAuth connection (for Facebook/Instagram)
    access_token = models.TextField(blank=True, null=True, help_text="OAuth access token")
    platform_user_id = models.CharField(max_length=100, blank=True, null=True, help_text="Platform user/account ID")
    
    # Facebook/Instagram specific OAuth data
    facebook_page_id = models.CharField(max_length=100, blank=True, null=True, help_text="Facebook Page ID (for Facebook/Instagram OAuth)")
    instagram_business_account_id = models.CharField(max_length=100, blank=True, null=True, help_text="Instagram Business Account ID (from OAuth)")
    
    # TikTok specific OAuth data
    tiktok_open_id = models.CharField(max_length=100, blank=True, null=True, help_text="TikTok Open ID (from OAuth)")
    refresh_token = models.TextField(blank=True, null=True, help_text="OAuth refresh token (for token renewal)")
    
    token_expires_at = models.DateTimeField(blank=True, null=True, help_text="When the OAuth token expires")
    oauth_connected_at = models.DateTimeField(blank=True, null=True, help_text="When OAuth connection was established")
    
    verified_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['influencer', 'platform']
        ordering = ['-followers_count']

    def __str__(self):
        return f"{self.influencer.user.username} - {self.get_platform_display()} ({self.handle})"
    
    @property
    def is_verified(self):
        """Check if platform is verified."""
        return self.verification_status == self.VerificationStatus.VERIFIED


class Influencer(models.Model):
    """Influencer profile extending the User model."""
    
    class VerificationStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        REQUEST_INFO = "request_info", "Request Info"
        PAUSED = "paused", "Paused"  # Admin can pause verified accounts

    class Tier(models.TextChoices):
        TIER_1 = "tier_1", "Tier 1"
        TIER_2 = "tier_2", "Tier 2"
        TIER_3 = "tier_3", "Tier 3"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="influencer_profile")
    verification_status = models.CharField(
        max_length=20,
        choices=VerificationStatus.choices,
        default=VerificationStatus.PENDING,
    )
    tier = models.CharField(
        max_length=20,
        choices=Tier.choices,
        blank=True,
        null=True,
    )
    
    # Legacy platform fields (kept for backward compatibility)
    tiktok_handle = models.CharField(max_length=100, blank=True)
    instagram_handle = models.CharField(max_length=100, blank=True)
    youtube_handle = models.CharField(max_length=100, blank=True)
    
    # Legacy follower counts
    tiktok_followers = models.IntegerField(default=0)
    instagram_followers = models.IntegerField(default=0)
    youtube_subscribers = models.IntegerField(default=0)
    
    # Sample links for verification
    sample_tiktok_link = models.URLField(blank=True, null=True)
    sample_instagram_link = models.URLField(blank=True, null=True)
    sample_youtube_link = models.URLField(blank=True, null=True)
    
    # Primary platform selection
    primary_platform = models.CharField(
        max_length=20,
        choices=PlatformConnection.Platform.choices,
        blank=True,
        null=True,
        help_text="Primary platform the influencer wants to work on"
    )
    
    # Niche/category
    niche = models.ForeignKey(
        'Niche',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='influencers',
        help_text="Primary niche/category"
    )
    # Keep legacy field for backward compatibility during migration
    niche_legacy = models.CharField(max_length=100, blank=True, help_text="Legacy niche field")
    
    # Profile information
    bio = models.TextField(blank=True, help_text="Bio/About me description")
    profile_picture = models.ImageField(
        upload_to='influencers/profile_pictures/',
        blank=True,
        null=True,
        help_text="Profile picture (recommended size: 400x400px)"
    )
    
    # Currency for wallet and payments
    currency = models.ForeignKey(
        'brands.Currency',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='influencers',
        help_text="Currency for wallet and payments"
    )
    
    # Onboarding tracking
    onboarding_completed = models.BooleanField(default=False, help_text="Has completed initial onboarding")
    profile_completed = models.BooleanField(default=False, help_text="Has completed profile setup")
    
    # Admin notes
    admin_notes = models.TextField(blank=True)
    
    # Admin pause tracking
    paused_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="paused_influencers",
        help_text="Admin who paused this account"
    )
    paused_at = models.DateTimeField(null=True, blank=True)
    pause_reason = models.TextField(blank=True, help_text="Reason for pausing the account")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} ({self.get_verification_status_display()})"
    
    def save(self, *args, **kwargs):
        # Set default currency if not set
        if not self.currency_id:
            from brands.models import Currency
            default_currency = Currency.get_default()
            if default_currency:
                self.currency = default_currency
        super().save(*args, **kwargs)
    
    @property
    def currency_symbol(self):
        """Get currency symbol for display."""
        return self.currency.symbol if self.currency else '$'
    
    @property
    def currency_code(self):
        """Get currency code for display."""
        return self.currency.code if self.currency else 'USD'

    @property
    def primary_handle(self):
        """Return the primary handle based on selected primary platform."""
        # If primary platform is set, use that
        if self.primary_platform:
            primary_connection = self.platform_connections.filter(
                platform=self.primary_platform,
                verification_status='verified'
            ).first()
            if primary_connection:
                return f"@{primary_connection.handle}"
        
        # Fallback to first verified platform connection
        primary_connection = self.platform_connections.filter(verification_status='verified').first()
        if primary_connection:
            return f"@{primary_connection.handle}"
        
        # Fallback to legacy fields
        if self.tiktok_handle:
            return f"@{self.tiktok_handle}"
        elif self.instagram_handle:
            return f"@{self.instagram_handle}"
        elif self.youtube_handle:
            return f"@{self.youtube_handle}"
        return self.user.username
    
    @property
    def primary_platform_connection(self):
        """Get the primary platform connection."""
        if self.primary_platform:
            return self.platform_connections.filter(
                platform=self.primary_platform,
                verification_status='verified'
            ).first()
        return self.platform_connections.filter(verification_status='verified').first()
    
    @property
    def total_followers(self):
        """Get total followers across all verified platforms (uses verified count if available)."""
        total = 0
        for conn in self.platform_connections.filter(verification_status='verified'):
            # Use verified count from API if available, otherwise use user-provided count
            count = conn.verified_followers_count if conn.verified_followers_count else conn.followers_count
            total += count
        return total
    
    @property
    def has_minimum_followers(self):
        """Check if influencer meets minimum follower requirements on any platform (uses verified count if available)."""
        for conn in self.platform_connections.filter(verification_status='verified'):
            min_followers = PlatformSettings.get_minimum_followers(conn.platform)
            # Use verified count from API if available, otherwise use user-provided count
            count = conn.verified_followers_count if conn.verified_followers_count else conn.followers_count
            if count >= min_followers:
                return True
        return False
    
    def meets_platform_requirement(self, platform):
        """Check if influencer meets minimum requirement for a specific platform."""
        from .models import PlatformSettings
        
        conn = self.platform_connections.filter(
            platform=platform,
            verification_status='verified'
        ).first()
        
        if not conn:
            return False
        
        min_followers = PlatformSettings.get_minimum_followers(platform)
        # Use verified count from API if available, otherwise use user-provided count
        count = conn.verified_followers_count if conn.verified_followers_count else conn.followers_count
        return count >= min_followers
    
    @property
    def verified_platforms(self):
        """Get list of verified platforms."""
        return self.platform_connections.filter(verification_status='verified')
    
    @property
    def is_verified(self):
        """Check if influencer is fully verified."""
        return (
            self.verification_status == self.VerificationStatus.APPROVED and
            self.has_minimum_followers and
            self.verified_platforms.exists()
        )
    
    @property
    def is_paused(self):
        """Check if influencer account is paused."""
        return self.verification_status == self.VerificationStatus.PAUSED
    
    def pause(self, admin_user, reason=""):
        """Pause the influencer account (admin action)."""
        self.verification_status = self.VerificationStatus.PAUSED
        self.paused_by = admin_user
        self.paused_at = timezone.now()
        self.pause_reason = reason
        self.save()
    
    def unpause(self):
        """Unpause the influencer account."""
        if self.verification_status == self.VerificationStatus.APPROVED:
            # If it was approved before, restore to approved
            self.verification_status = self.VerificationStatus.APPROVED
        else:
            # Otherwise keep as pending
            self.verification_status = self.VerificationStatus.PENDING
        self.paused_by = None
        self.paused_at = None
        self.pause_reason = ""
        self.save()


# Signal to auto-verify platform connections when created
@receiver(post_save, sender=PlatformConnection)
def auto_verify_platform_connection(sender, instance, created, **kwargs):
    """
    Automatically verify platform connections when they are created.
    Only runs if verification_status is PENDING.
    """
    if created and instance.verification_status == PlatformConnection.VerificationStatus.PENDING:
        try:
            from .verification import VerificationService
            
            # Run automated verification (this will auto-approve if passed)
            result = VerificationService.verify_connection(instance, auto_approve=True)
            
            # Refresh instance to get the latest status (verify_connection may have updated it)
            instance.refresh_from_db()
            
            # Store verification metadata
            # Only update status if it's still PENDING (verify_connection already set it to VERIFIED if passed)
            if instance.verification_status == PlatformConnection.VerificationStatus.PENDING:
                if result.confidence >= 0.5:
                    # Medium confidence - keep pending for manual review
                    new_status = PlatformConnection.VerificationStatus.PENDING
                else:
                    # Low confidence - reject
                    new_status = PlatformConnection.VerificationStatus.REJECTED
            else:
                # Status was already set to VERIFIED by verify_connection
                new_status = instance.verification_status
            
            # Save without triggering signal again
            PlatformConnection.objects.filter(pk=instance.pk).update(
                verification_confidence=result.confidence,
                verification_flags=result.flags,
                verification_method='auto',
                verification_status=new_status,
            )
            
            # Auto-approve influencer account if all requirements are met
            if new_status == PlatformConnection.VerificationStatus.VERIFIED:
                try:
                    influencer = instance.influencer
                    # Check if influencer account should be auto-approved
                    if influencer.verification_status == Influencer.VerificationStatus.PENDING:
                        # Check all requirements
                        has_verified_platforms = influencer.verified_platforms.exists()
                        has_minimum_followers = influencer.has_minimum_followers
                        has_niche = influencer.niche is not None
                        has_primary_platform = influencer.primary_platform is not None
                        
                        if has_verified_platforms and has_minimum_followers and has_niche and has_primary_platform:
                            # Auto-approve influencer account
                            influencer.verification_status = Influencer.VerificationStatus.APPROVED
                            influencer.save()
                            logger.info(f"Auto-approved influencer {influencer.user.username} - all requirements met")
                except Exception as e:
                    logger.warning(f"Failed to auto-approve influencer after platform verification: {e}")
        except Exception as e:
            # If verification fails, keep as pending for manual review
            # Log error but don't break the save
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Auto-verification failed for {instance}: {e}", exc_info=True)


class InfluencerVerificationQueue(models.Model):
    """Queue for delayed influencer verification."""
    
    influencer = models.OneToOneField(Influencer, on_delete=models.CASCADE, related_name="verification_queue")
    scheduled_at = models.DateTimeField(help_text="When to process this verification")
    processed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['scheduled_at']
    
    @classmethod
    def schedule_verification(cls, influencer):
        """Schedule verification for an influencer with random 5-10 minute delay."""
        # Random delay between 5 and 10 minutes
        delay_minutes = random.randint(5, 10)
        scheduled_at = timezone.now() + timedelta(minutes=delay_minutes)
        
        # Create or update queue entry
        queue_entry, created = cls.objects.get_or_create(
            influencer=influencer,
            defaults={'scheduled_at': scheduled_at}
        )
        if not created:
            queue_entry.scheduled_at = scheduled_at
            queue_entry.processed = False
            queue_entry.save()
        
        return queue_entry
    
    def __str__(self):
        return f"Verification for {self.influencer} scheduled at {self.scheduled_at}"


class PaymentMethod(models.Model):
    """Payment methods for influencer withdrawals (Bank Transfer, Mobile Money)."""
    
    class MethodType(models.TextChoices):
        BANK_TRANSFER = "bank", "Bank Transfer"
        MOBILE_MONEY = "momo", "Mobile Money"
    
    class MobileMoneyNetwork(models.TextChoices):
        MTN = "mtn", "MTN Mobile Money"
        VODAFONE = "vodafone", "Vodafone Cash"
        AIRTELTIGO = "airteltigo", "AirtelTigo Money"
        OTHER = "other", "Other"
    
    influencer = models.ForeignKey(
        'Influencer',
        on_delete=models.CASCADE,
        related_name='payment_methods',
        help_text="Influencer who owns this payment method"
    )
    method_type = models.CharField(
        max_length=20,
        choices=MethodType.choices,
        help_text="Type of payment method"
    )
    is_default = models.BooleanField(
        default=False,
        help_text="Default payment method for withdrawals"
    )
    
    # Bank Transfer fields
    bank_name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Bank name (for bank transfer)"
    )
    account_number = models.CharField(
        max_length=50,
        blank=True,
        help_text="Account number (for bank transfer)"
    )
    account_name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Account holder name (for bank transfer)"
    )
    swift_code = models.CharField(
        max_length=20,
        blank=True,
        help_text="SWIFT/BIC code (optional, for international transfers)"
    )
    bank_country = models.CharField(
        max_length=100,
        blank=True,
        default="Ghana",
        help_text="Country where bank is located"
    )
    
    # Mobile Money fields (Ghana)
    mobile_money_network = models.CharField(
        max_length=20,
        choices=MobileMoneyNetwork.choices,
        blank=True,
        help_text="Mobile Money network (for Ghana)"
    )
    mobile_money_number = models.CharField(
        max_length=20,
        blank=True,
        help_text="Mobile Money phone number (e.g., 0244123456)"
    )
    mobile_money_name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Name registered with Mobile Money account"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Payment Method"
        verbose_name_plural = "Payment Methods"
        ordering = ['-is_default', '-created_at']
    
    def __str__(self):
        if self.method_type == self.MethodType.BANK_TRANSFER:
            return f"Bank Transfer - {self.bank_name} ({self.account_number[-4:] if len(self.account_number) > 4 else self.account_number})"
        elif self.method_type == self.MethodType.MOBILE_MONEY:
            return f"{self.get_mobile_money_network_display()} - {self.mobile_money_number}"
        return f"{self.get_method_type_display()}"
    
    def save(self, *args, **kwargs):
        # If this is set as default, unset other default methods for this influencer
        if self.is_default:
            PaymentMethod.objects.filter(
                influencer=self.influencer,
                is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)
    
    def get_display_name(self):
        """Get a user-friendly display name for this payment method."""
        if self.method_type == self.MethodType.BANK_TRANSFER:
            if self.bank_name:
                account_display = f"****{self.account_number[-4:]}" if len(self.account_number) > 4 else self.account_number
                return f"{self.bank_name} ({account_display})"
            return f"Bank Account (****{self.account_number[-4:]})" if len(self.account_number) > 4 else f"Bank Account ({self.account_number})"
        elif self.method_type == self.MethodType.MOBILE_MONEY:
            return f"{self.get_mobile_money_network_display()} - {self.mobile_money_number}"
        return self.get_method_type_display()
    
    def get_details_summary(self):
        """Get a summary of payment details for display."""
        if self.method_type == self.MethodType.BANK_TRANSFER:
            return f"{self.account_name} - {self.bank_name}"
        elif self.method_type == self.MethodType.MOBILE_MONEY:
            return f"{self.mobile_money_name} - {self.mobile_money_number}"
        return ""
