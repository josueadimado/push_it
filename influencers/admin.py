from django.contrib import admin
from .models import Niche, PlatformSettings, PlatformConnection, Influencer


@admin.register(Niche)
class NicheAdmin(admin.ModelAdmin):
    """Admin interface for niches."""
    list_display = ['name', 'is_active', 'created_at']
    list_editable = ['is_active']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    fields = ['name', 'description', 'icon', 'is_active']


@admin.register(PlatformSettings)
class PlatformSettingsAdmin(admin.ModelAdmin):
    """Admin interface for platform settings."""
    list_display = ['platform', 'minimum_followers', 'is_active', 'updated_at']
    list_editable = ['minimum_followers', 'is_active']
    list_filter = ['is_active', 'platform']
    search_fields = ['platform']


@admin.register(PlatformConnection)
class PlatformConnectionAdmin(admin.ModelAdmin):
    """Admin interface for platform connections."""
    list_display = [
        'influencer', 'platform', 'handle', 'followers_count', 
        'verification_status', 'verification_confidence', 'verification_method', 'created_at'
    ]
    list_filter = ['platform', 'verification_status', 'verification_method', 'created_at']
    search_fields = ['influencer__user__username', 'influencer__user__email', 'handle']
    readonly_fields = ['created_at', 'updated_at', 'verified_at', 'verification_confidence', 'verification_flags']
    
    fieldsets = (
        ('Connection Info', {
            'fields': ('influencer', 'platform', 'handle', 'followers_count')
        }),
        ('Verification', {
            'fields': (
                'verification_status', 
                'verification_method',
                'verification_confidence',
                'verification_flags',
                'verified_at'
            )
        }),
        ('Stats', {
            'fields': ('engagement_rate', 'avg_views', 'sample_post_url')
        }),
        ('API Integration', {
            'fields': ('access_token', 'platform_user_id'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['verify_selected', 'reject_selected', 'flag_for_review']
    
    def verify_selected(self, request, queryset):
        """Manually verify selected connections."""
        count = queryset.update(
            verification_status=PlatformConnection.VerificationStatus.VERIFIED,
            verification_method='manual'
        )
        self.message_user(request, f'{count} connection(s) verified.')
    verify_selected.short_description = "Verify selected connections"
    
    def reject_selected(self, request, queryset):
        """Reject selected connections."""
        count = queryset.update(
            verification_status=PlatformConnection.VerificationStatus.REJECTED,
            verification_method='manual'
        )
        self.message_user(request, f'{count} connection(s) rejected.')
    reject_selected.short_description = "Reject selected connections"
    
    def flag_for_review(self, request, queryset):
        """Flag selected connections for manual review."""
        count = queryset.update(
            verification_status=PlatformConnection.VerificationStatus.PENDING,
            verification_method='manual'
        )
        self.message_user(request, f'{count} connection(s) flagged for review.')
    flag_for_review.short_description = "Flag for manual review"


@admin.register(Influencer)
class InfluencerAdmin(admin.ModelAdmin):
    """Admin interface for influencers."""
    list_display = ['user', 'primary_platform', 'niche', 'verification_status', 'onboarding_completed', 'created_at']
    list_filter = ['verification_status', 'primary_platform', 'onboarding_completed', 'created_at']
    search_fields = ['user__username', 'user__email', 'niche']
    readonly_fields = ['created_at', 'updated_at']
    filter_horizontal = []
