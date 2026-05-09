import json
import datetime
from django.shortcuts import render, redirect
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from google_auth_oauthlib.flow import Flow
from .models import GmailAccount
from .utils import encrypt_value, decrypt_value
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# Allow insecure transport for local development
import os
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

def get_flow(request):
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [settings.GOOGLE_REDIRECT_URI],
            }
        },
        scopes=['https://www.googleapis.com/auth/gmail.send', 'https://www.googleapis.com/auth/userinfo.email', 'openid'],
        redirect_uri=settings.GOOGLE_REDIRECT_URI
    )
    return flow

@login_required
def google_login(request):
    flow = get_flow(request)
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'
    )
    request.session['google_oauth_state'] = state
    # Store the code verifier so it's available in the callback
    request.session['google_oauth_verifier'] = flow.code_verifier
    return redirect(authorization_url)

# Remove @login_required here to prevent redirect loops during the callback
def google_callback(request):
    if not request.user.is_authenticated:
        return redirect('login')

    state = request.session.get('google_oauth_state')
    verifier = request.session.get('google_oauth_verifier')
    
    flow = get_flow(request)
    flow.code_verifier = verifier
    
    try:
        flow.fetch_token(authorization_response=request.build_absolute_uri())
    except Exception as e:
        messages.error(request, f"Failed to get token: {str(e)}")
        return redirect('dashboard')

    credentials = flow.credentials
    
    # Try to get email from id_token first (more reliable)
    email = None
    if hasattr(credentials, 'id_token') and credentials.id_token:
        from google.oauth2 import id_token
        from google.auth.transport import requests
        try:
            # We don't verify the signature here because we just got it from Google over HTTPS
            id_info = id_token.verify_oauth2_token(
                credentials.id_token, 
                requests.Request(), 
                credentials.client_id,
                clock_skew_in_seconds=10
            )
            email = id_info.get('email')
        except Exception:
            pass
    
    # Fallback to UserInfo API if id_token doesn't have it
    if not email:
        try:
            service = build('oauth2', 'v2', credentials=credentials)
            user_info = service.userinfo().get().execute()
            email = user_info.get('email')
        except Exception as e:
            messages.error(request, f"Failed to get user email: {str(e)}")
            return redirect('dashboard')

    if not email:
        messages.error(request, "Could not retrieve email from Google.")
        return redirect('dashboard')

    # Save or update the GmailAccount
    account, created = GmailAccount.objects.update_or_create(
        user=request.user,
        email=email,
        defaults={
            'access_token': encrypt_value(credentials.token),
            'refresh_token': encrypt_value(credentials.refresh_token) if credentials.refresh_token else None,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': json.dumps(credentials.scopes),
            'expiry': credentials.expiry,
        }
    )
    
    messages.success(request, f"Successfully connected {email}!")
    return redirect('dashboard')

@login_required
def dashboard(request):
    accounts = GmailAccount.objects.filter(user=request.user)
    return render(request, 'accounts/dashboard.html', {'accounts': accounts})
