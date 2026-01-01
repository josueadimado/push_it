from django.contrib import admin
from .models import PaymentTransaction


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    """Admin interface for payment transactions."""
    list_display = [
        'paystack_reference', 'user', 'brand', 'amount', 'currency', 
        'payment_type', 'status', 'created_at', 'paid_at'
    ]
    list_filter = ['status', 'payment_type', 'currency', 'created_at']
    search_fields = [
        'paystack_reference', 'user__email', 'user__username', 
        'brand__company_name', 'description'
    ]
    readonly_fields = [
        'created_at', 'updated_at', 'paid_at', 'paystack_reference',
        'paystack_authorization_code', 'paystack_customer_code'
    ]
    fieldsets = (
        ('Transaction Info', {
            'fields': ('user', 'brand', 'amount', 'currency', 'payment_type', 'status')
        }),
        ('Paystack Details', {
            'fields': (
                'paystack_reference',
                'paystack_authorization_code',
                'paystack_customer_code'
            )
        }),
        ('Additional Info', {
            'fields': ('description', 'metadata')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'paid_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'brand')
