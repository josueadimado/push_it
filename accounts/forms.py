from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm

from .models import User
from brands.models import Brand
from influencers.models import Influencer, PlatformConnection, PlatformSettings, Niche


class BaseSignupForm(UserCreationForm):
    """
    Shared signup logic.
    We only ask for name, email, and password for now.
    """

    first_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={
            'placeholder': 'Enter your first name',
            'required': True,
            'autocomplete': 'given-name'
        })
    )
    last_name = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Enter your last name',
            'autocomplete': 'family-name'
        })
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'placeholder': 'name@example.com',
            'required': True,
            'type': 'email',
            'autocomplete': 'email'
        })
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("first_name", "last_name", "email", "password1", "password2")
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add HTML5 validation attributes to password fields
        self.fields['password1'].widget.attrs.update({
            'required': True,
            'autocomplete': 'new-password',
            'minlength': '8'
        })
        self.fields['password2'].widget.attrs.update({
            'required': True,
            'autocomplete': 'new-password',
            'minlength': '8'
        })

    def clean_email(self):
        """
        Validate that the email is not already used by another account.
        This prevents the same email from being used for both brand and influencer accounts.
        """
        email = self.cleaned_data.get('email')
        if email:
            # Normalize email (lowercase) for comparison
            email = email.lower().strip()
            
            # Check if email already exists (either as email or username)
            # Since we set username = email, we need to check both fields
            if User.objects.filter(email=email).exists() or User.objects.filter(username=email).exists():
                raise forms.ValidationError(
                    "This email address is already registered. Please use a different email or try logging in instead."
                )
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        # Normalize email to lowercase before saving
        email = self.cleaned_data["email"].lower().strip()
        user.username = email  # keep username == email
        user.email = email
        if commit:
            user.save()
        return user


class BrandSignupForm(BaseSignupForm):
    """Signup form for brand / company accounts."""

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Roles.BRAND
        if commit:
            user.save()
            # Create brand profile
            Brand.objects.create(user=user)
        return user


class InfluencerSignupForm(BaseSignupForm):
    """Signup form for creator / influencer accounts."""

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Roles.INFLUENCER
        if commit:
            user.save()
            # Create influencer profile
            Influencer.objects.create(user=user)
        return user


class LoginForm(AuthenticationForm):
    """Login form that accepts both email and username."""

    username = forms.CharField(
        label="Email or Username",
        required=True,
        widget=forms.TextInput(attrs={
            "autocomplete": "username",
            "placeholder": "Enter your email or username",
            "required": True
        })
    )
    password = forms.CharField(
        required=True,
        widget=forms.PasswordInput(attrs={
            "autocomplete": "current-password",
            "placeholder": "Enter your password",
            "required": True
        })
    )


class BrandOnboardingForm(forms.ModelForm):
    """Form for brand profile completion - simplified to essential fields only."""
    
    class Meta:
        model = Brand
        fields = ['company_name', 'industry', 'currency']
        widgets = {
            'company_name': forms.TextInput(attrs={'placeholder': 'Enter your company name', 'required': True}),
            'industry': forms.Select(attrs={'class': 'form-select'}),
            'currency': forms.Select(attrs={'class': 'form-select'}),
        }
    
    def __init__(self, *args, **kwargs):
        from brands.models import Industry, Currency
        super().__init__(*args, **kwargs)
        self.fields['company_name'].required = True
        # Only show active industries
        self.fields['industry'].queryset = Industry.objects.filter(is_active=True).order_by('name')
        self.fields['industry'].empty_label = 'Select your industry...'
        self.fields['industry'].required = True
        # Currency selection - show active currencies
        self.fields['currency'].queryset = Currency.objects.filter(is_active=True).order_by('is_default', 'name')
        self.fields['currency'].empty_label = 'Select currency...'
        self.fields['currency'].required = True
        # Set default currency if not set
        if not self.instance.currency_id:
            default_currency = Currency.get_default()
            if default_currency:
                self.fields['currency'].initial = default_currency


class BrandProfileForm(forms.ModelForm):
    """Form for editing brand profile with all fields."""
    
    class Meta:
        model = Brand
        fields = ['company_name', 'website', 'industry', 'description', 'contact_email', 'phone_number', 'address', 'currency', 'logo']
        widgets = {
            'company_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Enter your company name'}),
            'website': forms.URLInput(attrs={'class': 'form-input', 'placeholder': 'https://yourcompany.com'}),
            'industry': forms.Select(attrs={'class': 'form-input'}),
            'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 5, 'placeholder': 'Tell us about your company, products, and services', 'style': 'resize: vertical; min-height: 120px;'}),
            'contact_email': forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'contact@yourcompany.com'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-input', 'placeholder': '+1234567890', 'id': 'phone-number-input'}),
            'address': forms.Textarea(attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Company address', 'style': 'resize: vertical; min-height: 80px;'}),
            'currency': forms.Select(attrs={'class': 'form-input'}),
            'logo': forms.FileInput(attrs={'class': 'form-input', 'accept': 'image/*', 'style': 'display: none;'}),
        }
    
    def __init__(self, *args, **kwargs):
        from brands.models import Industry, Currency
        super().__init__(*args, **kwargs)
        self.fields['company_name'].required = True
        # Only show active industries
        self.fields['industry'].queryset = Industry.objects.filter(is_active=True).order_by('name')
        self.fields['industry'].empty_label = 'Select your industry...'
        self.fields['industry'].required = True
        # Currency selection
        self.fields['currency'].queryset = Currency.objects.filter(is_active=True).order_by('is_default', 'name')
        self.fields['currency'].empty_label = 'Select currency...'
        self.fields['currency'].required = True
        # Logo field
        self.fields['logo'].required = False
        # All other fields are optional
        self.fields['website'].required = False
        self.fields['description'].required = False
        self.fields['contact_email'].required = False
        self.fields['phone_number'].required = False
        self.fields['address'].required = False


class InfluencerPlatformForm(forms.ModelForm):
    """Form for adding a platform connection."""
    
    class Meta:
        model = PlatformConnection
        fields = ['platform', 'handle', 'followers_count', 'sample_post_url']
        widgets = {
            'platform': forms.Select(attrs={'class': 'form-select'}),
            'handle': forms.TextInput(attrs={'placeholder': 'yourhandle (without @)'}),
            'followers_count': forms.NumberInput(attrs={'placeholder': 'Enter follower count'}),
            'sample_post_url': forms.URLInput(attrs={'placeholder': 'https://...'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.influencer = kwargs.pop('influencer', None)
        super().__init__(*args, **kwargs)
        self.fields['handle'].required = True
        self.fields['followers_count'].required = True
        
        # Filter to only show active platforms
        active_platforms = PlatformSettings.objects.filter(is_active=True).values_list('platform', flat=True)
        if active_platforms:
            self.fields['platform'].queryset = self.fields['platform'].queryset.filter(
                value__in=active_platforms
            ) if hasattr(self.fields['platform'], 'queryset') else None
            # For choice fields, filter the choices
            if hasattr(self.fields['platform'], 'choices'):
                self.fields['platform'].choices = [
                    choice for choice in self.fields['platform'].choices
                    if choice[0] in active_platforms
                ]
        
        # Exclude already connected platforms
        if self.influencer:
            connected_platforms = self.influencer.platform_connections.values_list('platform', flat=True)
            if hasattr(self.fields['platform'], 'choices'):
                self.fields['platform'].choices = [
                    choice for choice in self.fields['platform'].choices
                    if choice[0] not in connected_platforms
                ]
    
    def clean_followers_count(self):
        followers = self.cleaned_data.get('followers_count', 0)
        platform = self.cleaned_data.get('platform')
        
        if platform:
            min_followers = PlatformSettings.get_minimum_followers(platform)
            if followers < min_followers:
                platform_display = dict(PlatformConnection.Platform.choices).get(platform, platform)
                raise forms.ValidationError(
                    f"You need at least {min_followers:,} followers on {platform_display} to join as an influencer."
                )
        else:
            # Default minimum if platform not selected
            if followers < 1000:
                raise forms.ValidationError("You need at least 1,000 followers to join as an influencer.")
        
        return followers
    
    def save(self, commit=True):
        platform_conn = super().save(commit=False)
        if self.influencer:
            platform_conn.influencer = self.influencer
        if commit:
            platform_conn.save()
        return platform_conn


class InfluencerOnboardingForm(forms.ModelForm):
    """Form for influencer profile completion."""
    
    class Meta:
        model = Influencer
        fields = ['primary_platform', 'niche']
        widgets = {
            'primary_platform': forms.Select(attrs={'class': 'form-select'}),
            'niche': forms.Select(attrs={'class': 'form-select'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Only show active niches
        self.fields['niche'].queryset = Niche.objects.filter(is_active=True).order_by('name')
        self.fields['niche'].empty_label = 'Select your niche...'
        self.fields['niche'].required = True
        
        # Only show platforms that have connections (regardless of verification status)
        # During onboarding, platforms may be pending verification
        instance = kwargs.get('instance')
        if instance:
            connected_platforms = instance.platform_connections.values_list('platform', flat=True)
            
            if hasattr(self.fields['primary_platform'], 'choices'):
                # Convert choices to list (it might be an iterator)
                all_choices = list(self.fields['primary_platform'].choices)
                
                # Filter choices to only show connected platforms
                filtered_choices = [
                    choice for choice in all_choices
                    if choice[0] in connected_platforms
                ]
                
                # If there are connected platforms, show them
                if filtered_choices:
                    # Create new list with empty choice at the beginning
                    self.fields['primary_platform'].choices = [('', 'Select primary platform...')] + filtered_choices
                    self.fields['primary_platform'].required = True
                else:
                    # No platforms connected yet - show all available platforms with message
                    # This allows user to see what platforms they can connect
                    self.fields['primary_platform'].choices = [('', 'Connect a platform first...')] + all_choices
                    self.fields['primary_platform'].required = False
