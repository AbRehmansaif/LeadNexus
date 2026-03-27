from django import forms
from django.contrib.auth.models import User

class AffiliateUnifiedRegistrationForm(forms.ModelForm):
    # User fields
    username = forms.CharField(max_length=150, help_text="Unique operator identifier")
    email = forms.EmailField(help_text="Primary contact/identity email")
    password = forms.CharField(widget=forms.PasswordInput, help_text="Security Key (min 8 characters)")
    
    class Meta:
        from .models import Affiliate
        model = Affiliate
        fields = ['payout_method', 'payout_email', 'payout_details']

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("This email is already registered. Please login instead.")
        return email

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("This username is taken. Choose another.")
        return username
