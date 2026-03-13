from django.contrib.auth import views as auth_views
from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import CreateView, View
from django.shortcuts import redirect, render
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
import random
import string
from .forms import ProfessionalRegisterForm
from .models import PasswordResetCode, GlobalSettings

class LoginView(auth_views.LoginView):
    template_name = 'registration/login.html'
    redirect_authenticated_user = False
    
    def get_success_url(self):
        messages.success(self.request, f"Welcome back, {self.request.user.username}!")
        return super().get_success_url()

class RegisterView(CreateView):
    form_class = ProfessionalRegisterForm
    template_name = 'registration/register.html'
    success_url = reverse_lazy('login')

    def form_valid(self, form):
        response = super().form_valid(form)
        user = self.object
        
        # Send Welcome Email
        try:
            subject = "Neural Identity Verified — Welcome to LeadNexus"
            message = f"Hello {user.username},\n\nYour operator identity has been successfully registered in the LeadNexus network.\n\nOperator ID: {user.username}\nRegistered Email: {user.email}\n\nYou can now access your dashboard and initiate lead discovery protocols.\n\nWelcome back, Operator.\n— The LeadNexus Team"
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=True,
            )
        except:
            pass
            
        messages.success(self.request, "Account created successfully! You can now log in.")
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        settings = GlobalSettings.objects.first()
        context['registrations_enabled'] = settings.registrations_enabled if settings else True
        return context

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('dashboard')
            
        # Check if registrations are specifically disabled
        settings = GlobalSettings.objects.first()
        if settings and not settings.registrations_enabled:
            # If user tries to POST to a disabled registration, block it
            if request.method == 'POST':
                messages.error(request, "Registration sequence is currently disabled by system administrators.")
                return redirect('register')
                
        return super().dispatch(request, *args, **kwargs)

class RequestPasswordResetView(auth_views.PasswordResetView):
    template_name = 'registration/password_reset_form.html'
    
    def form_valid(self, form):
        email = form.cleaned_data.get('email')
        try:
            user = User.objects.get(email=email)
            # Generate 6-digit code
            code = ''.join(random.choices(string.digits, k=6))
            PasswordResetCode.objects.create(user=user, code=code)
            
            # Send Email
            subject = "Nexus Security: Identity Recovery Code"
            message = f"Your identity recovery code is: {code}\n\nUse this code in the LeadNexus portal to reset your security key. This code will expire in 15 minutes.\n\nLeadNexus Intelligence Unit"
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=True)
            
            self.request.session['reset_email'] = email
            return redirect('password-verify-code')
        except User.DoesNotExist:
            # Still show success to prevent email enumeration
            messages.info(self.request, "If an account exists with this email, a recovery code has been dispatched.")
            return redirect('password_reset_done')

class VerifyResetCodeView(View):
    template_name = 'registration/password_reset_verify.html'
    
    def get(self, request):
        return render(request, self.template_name)
        
    def post(self, request):
        code = request.POST.get('code')
        email = request.session.get('reset_email')
        
        if not email:
            return redirect('password_reset')
            
        try:
            user = User.objects.get(email=email)
            reset_code = PasswordResetCode.objects.filter(user=user, code=code).last()
            
            if reset_code and reset_code.is_valid():
                reset_code.is_used = True
                reset_code.save()
                request.session['code_verified'] = True
                return redirect('password-reset-confirm')
            else:
                messages.error(request, "Invalid or expired recovery code.")
        except User.DoesNotExist:
            pass
            
        return render(request, self.template_name)

class CustomPasswordResetConfirmView(View):
    template_name = 'registration/password_reset_new.html'
    
    def get(self, request):
        if not request.session.get('code_verified'):
            return redirect('password_reset')
        return render(request, self.template_name)
        
    def post(self, request):
        if not request.session.get('code_verified'):
            return redirect('password_reset')
            
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        email = request.session.get('reset_email')
        
        if password != confirm_password:
            messages.error(request, "Security keys do not match.")
            return render(request, self.template_name)
            
        if len(password) < 8:
            messages.error(request, "Security key must be at least 8 characters.")
            return render(request, self.template_name)
            
        try:
            user = User.objects.get(email=email)
            user.password = make_password(password)
            user.save()
            
            # Clear session
            if 'reset_email' in request.session: del request.session['reset_email']
            if 'code_verified' in request.session: del request.session['code_verified']
            
            messages.success(request, "Identity restored. You can now login with your new security key.")
            return redirect('login')
        except User.DoesNotExist:
            return redirect('password_reset')
