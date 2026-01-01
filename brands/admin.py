from django.contrib import admin
from .models import Currency, Industry, Brand, BrandVerificationQueue


@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    """Admin interface for currencies."""
    list_display = ['code', 'name', 'symbol', 'is_default', 'is_active', 'exchange_rate', 'created_at']
    list_editable = ['is_active', 'exchange_rate']
    list_filter = ['is_default', 'is_active', 'created_at']
    search_fields = ['code', 'name', 'symbol']
    fields = ['code', 'name', 'symbol', 'is_default', 'is_active', 'exchange_rate']
    
    def save_model(self, request, obj, form, change):
        # Ensure only one default currency
        if obj.is_default:
            Currency.objects.filter(is_default=True).exclude(pk=obj.pk).update(is_default=False)
        super().save_model(request, obj, form, change)


@admin.register(Industry)
class IndustryAdmin(admin.ModelAdmin):
    """Admin interface for industries."""
    list_display = ['name', 'is_active', 'created_at']
    list_editable = ['is_active']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    fields = ['name', 'description', 'icon', 'is_active']


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    """Admin interface for brands."""
    list_display = ['company_name', 'user', 'industry', 'currency', 'wallet_balance', 'verification_status', 'profile_completed', 'created_at']
    list_filter = ['verification_status', 'industry', 'currency', 'profile_completed', 'created_at']
    search_fields = ['company_name', 'user__username', 'user__email', 'industry__name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(BrandVerificationQueue)
class BrandVerificationQueueAdmin(admin.ModelAdmin):
    """Admin interface for brand verification queue."""
    list_display = ['brand', 'scheduled_at', 'processed', 'created_at']
    list_filter = ['processed', 'scheduled_at', 'created_at']
    search_fields = ['brand__company_name', 'brand__user__email']
    readonly_fields = ['created_at']
