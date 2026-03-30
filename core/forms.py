from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from django.contrib.auth import authenticate # Added this import for authenticate function

class ProfessionalRegisterForm(UserCreationForm):
    email = forms.EmailField(required=True, help_text="Used for account identity verification.")

    class Meta(UserCreationForm.Meta):
        fields = ("username", "email")

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("This email identity is already registered in the Nexus.")
        return email

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise ValidationError("This OPERATOR ID is already taken. Choose another.")
        return username

    def clean_password1(self):
        password = self.cleaned_data.get('password1')
        if len(password) < 8:
            raise ValidationError("Security Key must be at least 8 characters long.")
        # Additional complexity can be added here
        return password
from django.contrib.auth.forms import AuthenticationForm
class EmailAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(label="Email Address", widget=forms.EmailInput(attrs={'class': 'auth-input', 'placeholder': 'operator@leadnexus.pro', 'autofocus': True}))

    def clean(self):
        email = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')

        if email and password:
            self.user_cache = authenticate(self.request, username=email, password=password)
            if self.user_cache is None:
                # Try to find user by email since username might be different
                user = User.objects.filter(email=email).first()
                if user:
                    self.user_cache = authenticate(self.request, username=user.username, password=password)
                
                if self.user_cache is None:
                    raise self.get_invalid_login_error()
            else:
                self.confirm_login_allowed(self.user_cache)

        return self.cleaned_data

    def confirm_login_allowed(self, user):
        if not user.is_active:
            raise ValidationError(
                "This operator account is currently in 'Inactive' status. Please verify your email identity to gain access.",
                code='inactive',
            )
