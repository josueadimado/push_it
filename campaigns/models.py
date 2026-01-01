from django.db import models
from brands.models import Brand


class Campaign(models.Model):
    """Campaign model for brand video promotion campaigns."""
    
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    class Platform(models.TextChoices):
        TIKTOK = "tiktok", "TikTok"
        INSTAGRAM = "instagram", "Instagram"
        YOUTUBE = "youtube", "YouTube"

    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name="campaigns")
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Package details
    package_videos = models.IntegerField(help_text="Number of videos ordered")
    platform = models.CharField(max_length=20, choices=Platform.choices)
    niche = models.CharField(max_length=100, help_text="Campaign niche/category")
    
    # Budget
    budget = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Dates
    start_date = models.DateField(blank=True, null=True)
    due_date = models.DateField(blank=True, null=True)
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    
    # Internal notes
    internal_notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.brand.company_name})"

    @property
    def videos_delivered(self):
        """Count of verified submissions for this campaign."""
        return self.submissions.filter(status="verified").count()

    @property
    def delivery_progress(self):
        """Calculate delivery progress percentage."""
        if self.package_videos == 0:
            return 0
        return int((self.videos_delivered / self.package_videos) * 100)

    @property
    def is_at_risk(self):
        """Check if campaign is at risk (low delivery or due soon)."""
        from django.utils import timezone
        progress = self.delivery_progress
        days_until_due = (self.due_date - timezone.now().date()).days if self.due_date else None
        return progress < 70 or (days_until_due is not None and days_until_due <= 7)
