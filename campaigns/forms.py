from django import forms
from .models import Campaign
from influencers.models import Niche


class CampaignForm(forms.ModelForm):
    """Form for creating and editing campaigns."""
    
    class Meta:
        model = Campaign
        fields = [
            'name',
            'description',
            'platform',
            'niche',
            'package_videos',
            'budget',
            'start_date',
            'due_date',
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Enter campaign name',
                'required': True,
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-input',
                'rows': 5,
                'placeholder': 'Describe your campaign goals and requirements...',
                'style': 'resize: vertical; min-height: 120px;',
            }),
            'platform': forms.Select(attrs={
                'class': 'form-input',
                'required': True,
            }),
            'niche': forms.Select(attrs={
                'class': 'form-input',
                'required': True,
            }),
            'package_videos': forms.NumberInput(attrs={
                'class': 'form-input',
                'placeholder': 'Number of videos',
                'min': 1,
                'required': True,
            }),
            'budget': forms.NumberInput(attrs={
                'class': 'form-input',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0.01',
                'required': True,
            }),
            'start_date': forms.DateInput(attrs={
                'class': 'form-input',
                'type': 'date',
            }),
            'due_date': forms.DateInput(attrs={
                'class': 'form-input',
                'type': 'date',
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.brand = kwargs.pop('brand', None)
        super().__init__(*args, **kwargs)
        
        # Set required fields
        self.fields['name'].required = True
        self.fields['platform'].required = True
        self.fields['niche'].required = True
        self.fields['package_videos'].required = True
        self.fields['budget'].required = True
        self.fields['description'].required = False
        self.fields['start_date'].required = False
        self.fields['due_date'].required = False
        
        # Load active niches for the dropdown
        # Since Campaign.niche is a CharField, we'll use the niche name as the value
        active_niches = Niche.objects.filter(is_active=True).order_by('name')
        niche_choices = [('', 'Select a niche/category...')]
        niche_choices.extend([(niche.name, niche.name) for niche in active_niches])
        self.fields['niche'].widget = forms.Select(
            attrs={
                'class': 'form-input',
                'required': True,
            },
            choices=niche_choices
        )
    
    def clean_budget(self):
        """Validate budget is positive."""
        budget = self.cleaned_data.get('budget')
        if budget and budget <= 0:
            raise forms.ValidationError("Budget must be greater than zero.")
        return budget
    
    def clean_package_videos(self):
        """Validate package_videos is positive."""
        videos = self.cleaned_data.get('package_videos')
        if videos and videos <= 0:
            raise forms.ValidationError("Number of videos must be greater than zero.")
        return videos
    
    def clean(self):
        """Validate wallet balance if brand is provided."""
        cleaned_data = super().clean()
        budget = cleaned_data.get('budget')
        
        if self.brand and budget:
            if self.brand.wallet_balance < budget:
                raise forms.ValidationError(
                    f"Insufficient wallet balance. You have {self.brand.currency_symbol}{self.brand.wallet_balance:,.2f} "
                    f"but need {self.brand.currency_symbol}{budget:,.2f}. Please top up your wallet."
                )
        
        return cleaned_data

