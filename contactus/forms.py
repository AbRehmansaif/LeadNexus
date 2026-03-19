import re
from django import forms

from django.core.validators import RegexValidator

class ContactForm(forms.Form):
    name = forms.CharField(
        max_length=100,
        validators=[RegexValidator(r'^[a-zA-Z0-9\s]+$', "Invalid name")]
    )
    email = forms.EmailField(max_length=254)
    industry = forms.CharField(max_length=100, required=False)
    phone = forms.CharField(max_length=20, required=False)
    message = forms.CharField(
        max_length=2000,
        widget=forms.Textarea
    )

    def clean_message(self):
        msg = self.cleaned_data['message']

        blocked = ['<script', 'http://', 'https://', 'href=', 'SELECT ', 'DROP ']

        for b in blocked:
            if b.lower() in msg.lower():
                raise forms.ValidationError("Invalid content")

        return msg
