from django.contrib import admin
from .models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    """Admin interface for User model."""
    list_display = ['username', 'email', 'role', 'is_email_verified', 'is_staff', 'date_joined']
    list_filter = ['role', 'is_email_verified', 'is_staff', 'is_active', 'date_joined']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    readonly_fields = ['date_joined', 'last_login']
    
    fieldsets = (
        ('Authentication', {
            'fields': ('username', 'email', 'password')
        }),
        ('Personal Info', {
            'fields': ('first_name', 'last_name')
        }),
        ('Account Type', {
            'fields': ('role',)
        }),
        ('Status', {
            'fields': ('is_email_verified', 'is_active', 'is_staff', 'is_superuser')
        }),
        ('Important Dates', {
            'fields': ('date_joined', 'last_login'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['verify_emails', 'unverify_emails']
    
    def verify_emails(self, request, queryset):
        """Bulk action to verify selected users' emails."""
        count = queryset.update(is_email_verified=True)
        self.message_user(request, f'{count} user(s) email(s) verified successfully.')
    verify_emails.short_description = "Verify selected users' emails"
    
    def unverify_emails(self, request, queryset):
        """Bulk action to unverify selected users' emails."""
        count = queryset.update(is_email_verified=False)
        self.message_user(request, f'{count} user(s) email(s) unverified.')
    unverify_emails.short_description = "Unverify selected users' emails"
