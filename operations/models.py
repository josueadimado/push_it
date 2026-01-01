from django.db import models
from campaigns.models import Campaign
from influencers.models import Influencer


class Submission(models.Model):
    """Submission model for influencer video proofs."""
    
    class Status(models.TextChoices):
        NEW = "new", "New"
        IN_REVIEW = "in_review", "In Review"
        VERIFIED = "verified", "Verified"
        FLAGGED = "flagged", "Flagged"
        NEEDS_REUPLOAD = "needs_reupload", "Needs Re-upload"

    influencer = models.ForeignKey(Influencer, on_delete=models.CASCADE, related_name="submissions")
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="submissions")
    
    # Proof details
    proof_link = models.URLField(help_text="Link to the posted video")
    proof_type = models.CharField(
        max_length=20,
        choices=[("link", "Link"), ("file", "File")],
        default="link",
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.NEW,
    )
    
    # Admin notes
    admin_notes = models.TextField(blank=True)
    
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(blank=True, null=True)
    reviewed_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="reviewed_submissions",
    )

    class Meta:
        ordering = ["-submitted_at"]

    def __str__(self):
        return f"{self.influencer.primary_handle} - {self.campaign.name} ({self.get_status_display()})"


class Payout(models.Model):
    """Payout model for influencer payments."""
    
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    influencer = models.ForeignKey(Influencer, on_delete=models.CASCADE, related_name="payouts")
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="payouts")
    submission = models.OneToOneField(
        Submission,
        on_delete=models.CASCADE,
        related_name="payout",
        blank=True,
        null=True,
    )
    
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    due_date = models.DateField()
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    
    # Payment details
    reference = models.CharField(max_length=100, blank=True, help_text="Payment reference/transaction ID")
    notes = models.TextField(blank=True)
    
    sent_at = models.DateTimeField(blank=True, null=True)
    sent_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="sent_payouts",
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-due_date", "-created_at"]

    def __str__(self):
        return f"${self.amount} - {self.influencer.primary_handle} ({self.get_status_display()})"

    @property
    def is_overdue(self):
        """Check if payout is overdue."""
        from django.utils import timezone
        return self.status == self.Status.PENDING and self.due_date < timezone.now().date()


class Notification(models.Model):
    """Notification model for user notifications."""
    
    class Type(models.TextChoices):
        SUBMISSION_VERIFIED = "submission_verified", "Submission Verified"
        SUBMISSION_FLAGGED = "submission_flagged", "Submission Flagged"
        PAYOUT_SENT = "payout_sent", "Payout Sent"
        PAYOUT_AVAILABLE = "payout_available", "Payout Available"
        CAMPAIGN_ASSIGNED = "campaign_assigned", "Campaign Assigned"
        CAMPAIGN_DUE_SOON = "campaign_due_soon", "Campaign Due Soon"
        WITHDRAWAL_PROCESSED = "withdrawal_processed", "Withdrawal Processed"
        ACCOUNT_VERIFIED = "account_verified", "Account Verified"
        PLATFORM_VERIFIED = "platform_verified", "Platform Verified"
        GENERAL = "general", "General"
    
    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="notifications"
    )
    notification_type = models.CharField(
        max_length=50,
        choices=Type.choices,
        default=Type.GENERAL
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    link = models.URLField(blank=True, null=True, help_text="Optional link to related page")
    
    # Related objects (optional)
    submission = models.ForeignKey(
        Submission,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="notifications"
    )
    payout = models.ForeignKey(
        Payout,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="notifications"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_read", "created_at"]),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.title}"
    
    def mark_as_read(self):
        """Mark notification as read."""
        from django.utils import timezone
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=["is_read", "read_at"])
