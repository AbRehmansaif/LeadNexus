from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
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
