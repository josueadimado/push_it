from django import forms
from .models import PaymentMethod


class PaymentMethodForm(forms.ModelForm):
    """Form for adding/editing payment methods."""
    
    class Meta:
        model = PaymentMethod
        fields = [
            'method_type',
            'is_default',
            # Bank Transfer fields
            'bank_name',
            'account_number',
            'account_name',
            'swift_code',
            'bank_country',
            # Mobile Money fields
            'mobile_money_network',
            'mobile_money_number',
            'mobile_money_name',
        ]
        widgets = {
            'method_type': forms.Select(attrs={
                'class': 'input',
                'id': 'id_method_type',
            }),
            'is_default': forms.CheckboxInput(attrs={
                'class': 'checkbox',
            }),
            'bank_name': forms.TextInput(attrs={
                'class': 'input',
                'placeholder': 'e.g., GCB Bank, Ecobank',
            }),
            'account_number': forms.TextInput(attrs={
                'class': 'input',
                'placeholder': 'Account number',
            }),
            'account_name': forms.TextInput(attrs={
                'class': 'input',
                'placeholder': 'Account holder name',
            }),
            'swift_code': forms.TextInput(attrs={
                'class': 'input',
                'placeholder': 'SWIFT/BIC code (optional)',
            }),
            'bank_country': forms.TextInput(attrs={
                'class': 'input',
                'placeholder': 'Country',
                'value': 'Ghana',
            }),
            'mobile_money_network': forms.Select(attrs={
                'class': 'input',
            }),
            'mobile_money_number': forms.TextInput(attrs={
                'class': 'input',
                'placeholder': 'e.g., 0244123456',
            }),
            'mobile_money_name': forms.TextInput(attrs={
                'class': 'input',
                'placeholder': 'Name on Mobile Money account',
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.influencer = kwargs.pop('influencer', None)
        super().__init__(*args, **kwargs)
        
        # Make fields conditional based on method_type
        if self.instance and self.instance.pk:
            method_type = self.instance.method_type
        else:
            method_type = self.data.get('method_type') if self.data else None
        
        # Show/hide fields based on method type
        if method_type == PaymentMethod.MethodType.BANK_TRANSFER:
            self.fields['bank_name'].required = True
            self.fields['account_number'].required = True
            self.fields['account_name'].required = True
            self.fields['swift_code'].required = False
            self.fields['bank_country'].required = True
            
            # Hide mobile money fields
            self.fields['mobile_money_network'].required = False
            self.fields['mobile_money_number'].required = False
            self.fields['mobile_money_name'].required = False
        elif method_type == PaymentMethod.MethodType.MOBILE_MONEY:
            self.fields['mobile_money_network'].required = True
            self.fields['mobile_money_number'].required = True
            self.fields['mobile_money_name'].required = True
            
            # Hide bank fields
            self.fields['bank_name'].required = False
            self.fields['account_number'].required = False
            self.fields['account_name'].required = False
            self.fields['swift_code'].required = False
            self.fields['bank_country'].required = False
    
    def clean(self):
        cleaned_data = super().clean()
        method_type = cleaned_data.get('method_type')
        
        if method_type == PaymentMethod.MethodType.BANK_TRANSFER:
            # Validate bank transfer fields
            if not cleaned_data.get('bank_name'):
                raise forms.ValidationError("Bank name is required for bank transfer.")
            if not cleaned_data.get('account_number'):
                raise forms.ValidationError("Account number is required for bank transfer.")
            if not cleaned_data.get('account_name'):
                raise forms.ValidationError("Account name is required for bank transfer.")
        elif method_type == PaymentMethod.MethodType.MOBILE_MONEY:
            # Validate mobile money fields
            if not cleaned_data.get('mobile_money_network'):
                raise forms.ValidationError("Mobile Money network is required.")
            if not cleaned_data.get('mobile_money_number'):
                raise forms.ValidationError("Mobile Money number is required.")
            if not cleaned_data.get('mobile_money_name'):
                raise forms.ValidationError("Mobile Money account name is required.")
            
            # Validate mobile money number format (Ghana: 10 digits starting with 0)
            mobile_number = cleaned_data.get('mobile_money_number', '').strip()
            if mobile_number and not (mobile_number.startswith('0') and len(mobile_number) == 10 and mobile_number[1:].isdigit()):
                raise forms.ValidationError("Mobile Money number must be 10 digits starting with 0 (e.g., 0244123456).")
        
        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.influencer:
            instance.influencer = self.influencer
        
        if commit:
            instance.save()
        return instance

