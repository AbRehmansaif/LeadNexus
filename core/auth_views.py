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
from .forms import ProfessionalRegisterForm, EmailAuthenticationForm
from .models import PasswordResetCode, EmailVerificationCode
from admintask.models import GlobalSettings
from threading import Thread

class LoginView(auth_views.LoginView):
    authentication_form = EmailAuthenticationForm
    template_name = 'registration/login.html'
    redirect_authenticated_user = False
    
    def form_valid(self, form):
        from django.contrib.auth import login as auth_login
        auth_login(self.request, form.get_user())
        
        remember_me = self.request.POST.get('remember_me')
        if not remember_me:
            # If NOT checked, session expires when the browser is closed
            self.request.session.set_expiry(0)
        else:
            # If CHECKED, session stays for 30 days
            self.request.session.set_expiry(2592000)
            
        messages.success(self.request, f"Welcome back, {self.request.user.username}!")
        return redirect(self.get_success_url())

class RegisterView(CreateView):
    form_class = ProfessionalRegisterForm
    template_name = 'registration/register.html'
    success_url = reverse_lazy('login')

    def form_valid(self, form):
        user = form.save(commit=False)
        user.is_active = False # Deactivate until email is verified
        user.save()
        
        # ── Generate Professional Verification Code ──
        verification_code = ''.join(random.choices(string.digits, k=6))
        EmailVerificationCode.objects.create(user=user, code=verification_code)
        
        # ── Send Professional Verification Email (Async) ──
        def send_professional_verification(u_email, u_username, u_code):
            try:
                subject = f"{u_code} is your LeadNexus Verification Code"
                
                html_message = f"""
                <html>
                <body style="font-family: 'Segoe UI', Arial, sans-serif; background-color: #0d1117; color: #ffffff; padding: 40px; margin: 0;">
                    <div style="max-width: 600px; margin: 0 auto; background: #161b22; border: 1px solid #30363d; border-radius: 16px; overflow: hidden; box-shadow: 0 10px 30px rgba(0,0,0,0.5);">
                        <div style="background: #8b5cf6; padding: 30px; text-align: center;">
                            <h1 style="color: #ffffff; margin: 0; font-size: 28px; letter-spacing: 1px;">VERIFICATION REQUIRED</h1>
                        </div>
                        
                        <div style="padding: 40px; text-align: center;">
                            <h2 style="color: #ffffff; font-size: 22px;">Hi {u_username},</h2>
                            <p style="line-height: 1.6; color: #8b949e; font-size: 16px;">Welcome to LeadNexus! To initialize your autonomous growth protocols, we need to verify your email identity.</p>
                            
                            <div style="margin: 30px auto; background: rgba(139, 92, 246, 0.05); border: 1px dashed #8b5cf6; padding: 30px; border-radius: 12px; display: inline-block;">
                                <span style="font-family: 'Courier New', monospace; font-size: 42px; font-weight: 800; color: #8b5cf6; letter-spacing: 8px;">{u_code}</span>
                            </div>
                            
                            <p style="line-height: 1.6; color: #8b949e; font-size: 14px;">This security code will expire in 24 hours. Enter it in the registration portal to activate your operator account.</p>

                            <div style="text-align: center; margin: 30px 0;">
                                <a href="https://getleadnexus.com/verify-email/" 
                                   style="background-color: #8b5cf6; color: #ffffff; padding: 14px 30px; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block;">
                                    Verify Email Identity
                                </a>
                            </div>
 
                            <p style="color: #8b949e; font-size: 14px; border-top: 1px solid #30363d; padding-top: 25px;">
                                If you did not create a LeadNexus account, please disregard this transmission.
                            </p>
                        </div>
                        
                        <div style="background: #21262d; padding: 25px; text-align: center; font-size: 12px; color: #8b949e; border-top: 1px solid #30363d;">
                            &copy; 2026 LeadNexus. All rights reserved.
                        </div>
                    </div>
                </body>
                </html>
                """
                
                plain_message = (
                    f"Hi {u_username},\n\n"
                    f"Welcome to LeadNexus! Your verification code is: {u_code}\n\n"
                    "Enter this code in the portal to activate your account.\n\n"
                    "The LeadNexus Team"
                )

                send_mail(subject, plain_message, settings.DEFAULT_FROM_EMAIL, [u_email], html_message=html_message, fail_silently=True)
            except Exception: pass

        Thread(target=send_professional_verification, args=(user.email, user.username, verification_code)).start()
        
        # ── Affiliate Referral Tracking ──
        ref_code = self.request.session.get('affiliate_ref')
        if ref_code:
            try:
                from core.models import UserProfile
                profile, _ = UserProfile.objects.get_or_create(user=user)
                profile.referred_by = ref_code
                profile.save(update_fields=['referred_by'])
                
                from affiliatemarketing.models import Affiliate
                try:
                    affiliate = Affiliate.objects.get(referral_code=ref_code, status='active')
                    affiliate.total_signups += 1
                    affiliate.save(update_fields=['total_signups'])
                except Affiliate.DoesNotExist:
                    pass
            except Exception:
                pass

        self.request.session['verify_email'] = user.email
        messages.info(self.request, "Deployment Initialized: A 6-digit verification code has been dispatched to your email.")
        return redirect('verify-email')

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

class VerifyEmailView(View):
    template_name = 'registration/verify_email.html'
    
    def get(self, request):
        if not request.session.get('verify_email'):
            return redirect('register')
        return render(request, self.template_name)
        
    def post(self, request):
        code = request.POST.get('code')
        email = request.session.get('verify_email')
        
        if not email:
            return redirect('register')
            
        try:
            user = User.objects.get(email=email)
            verify_code = EmailVerificationCode.objects.filter(user=user, code=code).last()
            
            if verify_code and verify_code.is_valid():
                verify_code.is_used = True
                verify_code.save()
                
                user.is_active = True
                user.save()
                
                # Check for profile and mark as verified
                from core.models import UserProfile
                profile, _ = UserProfile.objects.get_or_create(user=user)
                profile.is_verified = True
                profile.save()

                # Automated Login
                from django.contrib.auth import login as auth_login
                auth_login(self.request, user, backend='core.backends.EmailOrUsernameBackend')
                
                # Handle Affiliate increment now that they are verified users
                ref_code = self.request.session.pop('affiliate_ref', None)
                if ref_code:
                    from affiliatemarketing.models import Affiliate
                    Affiliate.objects.filter(referral_code=ref_code, status='active').update(total_signups=models.F('total_signups') + 1)

                del request.session['verify_email']
                messages.success(self.request, "Account Identity Verified! Welcome to the LeadNexus network.")
                return redirect('subscription')
            else:
                messages.error(request, "Invalid or expired verification code.")
        except User.DoesNotExist:
            return redirect('register')
            
        return render(request, self.template_name)

class ResendVerificationCodeView(View):
    def get(self, request):
        email = request.session.get('verify_email')
        if not email:
            return redirect('register')
            
        try:
            user = User.objects.get(email=email)
            if user.is_active:
                messages.error(request, "This account is already active. Please login.")
                return redirect('login')
                
            # ── Generate Professional Verification Code ──
            verification_code = ''.join(random.choices(string.digits, k=6))
            EmailVerificationCode.objects.create(user=user, code=verification_code)
            
            # ── Send Professional Verification Email (Async) ──
            def send_professional_verification(u_email, u_username, u_code):
                try:
                    subject = f"{u_code} is your LeadNexus Verification Code"
                    
                    html_message = f"""
                    <html>
                    <body style="font-family: 'Segoe UI', Arial, sans-serif; background-color: #0d1117; color: #ffffff; padding: 40px; margin: 0;">
                        <div style="max-width: 600px; margin: 0 auto; background: #161b22; border: 1px solid #30363d; border-radius: 16px; overflow: hidden; box-shadow: 0 10px 30px rgba(0,0,0,0.5);">
                            <div style="background: #8b5cf6; padding: 30px; text-align: center;">
                                <h1 style="color: #ffffff; margin: 0; font-size: 28px; letter-spacing: 1px;">VERIFICATION REQUIRED</h1>
                            </div>
                            
                            <div style="padding: 40px; text-align: center;">
                                <h2 style="color: #ffffff; font-size: 22px;">Hi {u_username},</h2>
                                <p style="line-height: 1.6; color: #8b949e; font-size: 16px;">We received a request to resend your LeadNexus access code. Enter it below to activate your account.</p>
                                
                                <div style="margin: 30px auto; background: rgba(139, 92, 246, 0.05); border: 1px dashed #8b5cf6; padding: 30px; border-radius: 12px; display: inline-block;">
                                    <span style="font-family: 'Courier New', monospace; font-size: 42px; font-weight: 800; color: #8b5cf6; letter-spacing: 8px;">{u_code}</span>
                                </div>
                                
                                <p style="line-height: 1.6; color: #8b949e; font-size: 14px;">This security code will expire in 24 hours. Enter it in the registration portal to activate your operator account.</p>

                                <div style="text-align: center; margin: 30px 0;">
                                    <a href="https://getleadnexus.com/verify-email/" 
                                       style="background-color: #8b5cf6; color: #ffffff; padding: 14px 30px; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block;">
                                        Verify Email Identity
                                    </a>
                                </div>
    
                                <p style="color: #8b949e; font-size: 14px; border-top: 1px solid #30363d; padding-top: 25px;">
                                    If you did not create a LeadNexus account, please disregard this transmission.
                                </p>
                            </div>
                            
                            <div style="background: #21262d; padding: 25px; text-align: center; font-size: 12px; color: #8b949e; border-top: 1px solid #30363d;">
                                &copy; 2026 LeadNexus. All rights reserved.
                            </div>
                        </div>
                    </body>
                    </html>
                    """
                    
                    plain_message = (
                        f"Hi {u_username},\n\n"
                        f"Your LeadNexus verification code is: {u_code}\n\n"
                        "Enter this code in the portal to activate your account.\n\n"
                        "The LeadNexus Team"
                    )

                    send_mail(subject, plain_message, settings.DEFAULT_FROM_EMAIL, [u_email], html_message=html_message, fail_silently=True)
                except Exception: pass

            Thread(target=send_professional_verification, args=(user.email, user.username, verification_code)).start()
            messages.success(request, "Code Redispatched: A fresh 6-digit code has been queued for your email.")
            return redirect('verify-email')
            
        except User.DoesNotExist:
            return redirect('register')

class VerifyRequestView(View):
    template_name = 'registration/verify_request.html'
    
    def get(self, request):
        return render(request, self.template_name)
        
    def post(self, request):
        email = request.POST.get('email')
        try:
            user = User.objects.get(email=email)
            if user.is_active:
                messages.info(request, "This account is already active. Please login.")
                return redirect('login')
                
            # ── Generate Professional Verification Code ──
            verification_code = ''.join(random.choices(string.digits, k=6))
            EmailVerificationCode.objects.create(user=user, code=verification_code)
            
            # ── Send Professional Verification Email (Async) ──
            def send_professional_verification(u_email, u_username, u_code):
                try:
                    subject = f"{u_code} is your LeadNexus Verification Code"
                    
                    html_message = f"""
                    <html>
                    <body style="font-family: 'Segoe UI', Arial, sans-serif; background-color: #0d1117; color: #ffffff; padding: 40px; margin: 0;">
                        <div style="max-width: 600px; margin: 0 auto; background: #161b22; border: 1px solid #30363d; border-radius: 16px; overflow: hidden; box-shadow: 0 10px 30px rgba(0,0,0,0.5);">
                            <div style="background: #8b5cf6; padding: 30px; text-align: center;">
                                <h1 style="color: #ffffff; margin: 0; font-size: 28px; letter-spacing: 1px;">VERIFICATION REQUIRED</h1>
                            </div>
                            
                            <div style="padding: 40px; text-align: center;">
                                <h2 style="color: #ffffff; font-size: 22px;">Hi {u_username},</h2>
                                <p style="line-height: 1.6; color: #8b949e; font-size: 16px;">We received a request to initialize your LeadNexus access. Enter the code below to activate your account.</p>
                                
                                <div style="margin: 30px auto; background: rgba(139, 92, 246, 0.05); border: 1px dashed #8b5cf6; padding: 30px; border-radius: 12px; display: inline-block;">
                                    <span style="font-family: 'Courier New', monospace; font-size: 42px; font-weight: 800; color: #8b5cf6; letter-spacing: 8px;">{u_code}</span>
                                </div>
                                
                                <p style="line-height: 1.6; color: #8b949e; font-size: 14px;">This security code will expire in 24 hours. Enter it in the registration portal to activate your operator account.</p>

                                <div style="text-align: center; margin: 30px 0;">
                                    <a href="https://getleadnexus.com/verify-email/" 
                                       style="background-color: #8b5cf6; color: #ffffff; padding: 14px 30px; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block;">
                                        Verify Email Identity
                                    </a>
                                </div>
    
                                <p style="color: #8b949e; font-size: 14px; border-top: 1px solid #30363d; padding-top: 25px;">
                                    If you did not create a LeadNexus account, please disregard this transmission.
                                </p>
                            </div>
                            
                            <div style="background: #21262d; padding: 25px; text-align: center; font-size: 12px; color: #8b949e; border-top: 1px solid #30363d;">
                                &copy; 2026 LeadNexus. All rights reserved.
                            </div>
                        </div>
                    </body>
                    </html>
                    """
                    
                    plain_message = (
                        f"Hi {u_username},\n\n"
                        f"Your LeadNexus verification code is: {u_code}\n\n"
                        "Enter this code in the portal to activate your account.\n\n"
                        "The LeadNexus Team"
                    )

                    send_mail(subject, plain_message, settings.DEFAULT_FROM_EMAIL, [u_email], html_message=html_message, fail_silently=True)
                except Exception: pass

            Thread(target=send_professional_verification, args=(user.email, user.username, verification_code)).start()
            request.session['verify_email'] = email
            messages.success(request, "A verification code has been dispatched to your email address.")
            return redirect('verify-email')
            
        except User.DoesNotExist:
            # Still show info to avoid enumeration but direct to register if you're sure
             messages.info(request, "If an unverified account exists for this email, a code has been dispatched.")
             return redirect('login')

class RequestPasswordResetView(auth_views.PasswordResetView):
    template_name = 'registration/password_reset_form.html'
    
    def form_valid(self, form):
        email = form.cleaned_data.get('email')
        try:
            user = User.objects.get(email=email)
            # Generate 6-digit code
            code = ''.join(random.choices(string.digits, k=6))
            PasswordResetCode.objects.create(user=user, code=code)
            
            # Send Email (Async for SaaS performance)
            def send_recovery_email(u_email, u_username, u_code):
                try:
                    subject = "LeadNexus Password Reset"
                    
                    html_message = f"""
                    <html>
                    <body style="font-family: 'Segoe UI', Arial, sans-serif; background-color: #0d1117; color: #ffffff; padding: 40px; margin: 0;">
                        <div style="max-width: 600px; margin: 0 auto; background: #161b22; border: 1px solid #30363d; border-radius: 16px; overflow: hidden; box-shadow: 0 10px 30px rgba(0,0,0,0.5);">
                            <div style="background: #8b5cf6; padding: 30px; text-align: center;">
                                <h1 style="color: #ffffff; margin: 0; font-size: 24px; letter-spacing: 1px;">IDENTITY RECOVERY</h1>
                            </div>
                            
                            <div style="padding: 40px; text-align: center;">
                                <h2 style="color: #ffffff; font-size: 20px;">Hello {u_username},</h2>
                                <p style="line-height: 1.6; color: #8b949e;">We received a request to access your LeadNexus operator dashboard. Use the code below to authorize your identity restoration.</p>
                                
                                <div style="margin: 30px auto; background: rgba(255, 255, 255, 0.03); border: 1px solid #30363d; padding: 30px; border-radius: 12px; display: inline-block;">
                                    <span style="font-family: 'Courier New', monospace; font-size: 42px; font-weight: 800; color: #8b5cf6; letter-spacing: 8px;">{u_code}</span>
                                </div>

                                <p style="color: #8b949e; font-size: 14px; margin-top: 20px;">
                                    Use this code within <b style="color: #f87171;">15 minutes</b> to reset your security key.<br>
                                    If you did not request this code, please ignore this email or contact our security team.
                                </p>
                            </div>
                            
                            <div style="background: #21262d; padding: 25px; text-align: center; font-size: 12px; color: #8b949e; border-top: 1px solid #30363d;">
                                &copy; 2026 LeadNexus. All rights reserved.
                            </div>
                        </div>
                    </body>
                    </html>
                    """

                    plain_message = (
                        f"Hello {u_username},\n\n"
                        f"Your identity recovery code is: {u_code}\n\n"
                        "Use this code within 15 minutes to reset your security key in the LeadNexus portal.\n\n"
                        "If you did not request this code, please ignore this email or contact our security team immediately.\n\n"
                        "LeadNexus"
                    )
                    send_mail(subject, plain_message, settings.DEFAULT_FROM_EMAIL, [u_email], html_message=html_message, fail_silently=True)
                except Exception:
                    pass

            Thread(target=send_recovery_email, args=(user.email, user.username, code)).start()
            
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
            user.set_password(password) # Using set_password is better practice than make_password manually
            user.save()
            
            # ── Async Email Notification (SaaS Level Performance) ──
            from django.utils import timezone as d_timezone
            from admintask.models import GlobalSettings
            now_str = d_timezone.now().strftime('%Y-%m-%d %H:%M:%S %Z')
            gs = GlobalSettings.objects.first()
            contact_email = gs.contact_email if gs else "security@leadnexus.ai" 

            # Capture IP and Device
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip = x_forwarded_for.split(',')[0]
            else:
                ip = request.META.get('REMOTE_ADDR')
            user_agent = request.META.get('HTTP_USER_AGENT', 'Unknown Device')

            def send_confirmation_email(user_email, username, time_str, support_email, client_ip, client_device):
                try:
                    subject = "Password Change Successfully - LeadNexus"
                    
                    html_message = f"""
                    <html>
                    <body style="font-family: 'Segoe UI', Arial, sans-serif; background-color: #0d1117; color: #ffffff; padding: 40px; margin: 0;">
                        <div style="max-width: 600px; margin: 0 auto; background: #161b22; border: 1px solid #30363d; border-radius: 16px; overflow: hidden; box-shadow: 0 10px 30px rgba(0,0,0,0.5);">
                            <div style="background: #10b981; padding: 30px; text-align: center;">
                                <h1 style="color: #ffffff; margin: 0; font-size: 24px; letter-spacing: 1px;">SECURITY ALERT</h1>
                            </div>
                            
                            <div style="padding: 40px;">
                                <h2 style="color: #ffffff; font-size: 20px;">Hello {username},</h2>
                                <p style="line-height: 1.6; color: #8b949e;">Your LeadNexus security key (password) was successfully updated on <b>{time_str}</b>.</p>
                                
                                <div style="margin: 30px 0; background: rgba(255, 255, 255, 0.02); border: 1px solid #30363d; padding: 20px; border-radius: 10px;">
                                    <h3 style="color: #8b949e; margin-top: 0; font-size: 14px; text-transform: uppercase;">Security Parameters:</h3>
                                    <ul style="list-style: none; padding: 0; color: #8b949e; font-size: 13px;">
                                        <li style="margin-bottom: 8px;">🌐 <b>IP Address:</b> <span style="color: #ffffff;">{client_ip}</span></li>
                                        <li>📱 <b>Device:</b> <span style="color: #ffffff;">{client_device}</span></li>
                                    </ul>
                                </div>

                                <div style="text-align: center; margin: 35px 0;">
                                    <a href="https://getleadnexus.com/login/" 
                                       style="background-color: #10b981; color: #ffffff; padding: 12px 30px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">
                                        Login to Dashboard
                                    </a>
                                </div>

                                <p style="color: #8b949e; font-size: 13px; border-top: 1px solid #30363d; padding-top: 20px; line-height: 1.6;">
                                    If you did not perform this update, please contact our security team immediately: <b style="color: #ffffff;">{support_email}</b><br>
                                    and immediately reset your password here: <a href="https://getleadnexus.com/password_reset/" style="color: #10b981; text-decoration: none;">LeadNexus Security Portal</a>
                                </p>
                            </div>
                            
                            <div style="background: #21262d; padding: 25px; text-align: center; font-size: 12px; color: #8b949e; border-top: 1px solid #30363d;">
                                &copy; 2026 LeadNexus. All rights reserved.
                            </div>
                        </div>
                    </body>
                    </html>
                    """

                    plain_message = (
                        f"Hello {username},\n\n"
                        f"Your security key (password) was successfully updated on {time_str}.\n\n"
                        "Security Parameters:\n"
                        f"- IP Address: {client_ip}\n"
                        f"- Device: {client_device}\n\n"
                        "You can now login using your new credentials.\n\n"
                        "Login here: https://getleadnexus.com/login/\n\n"
                        f"If you did not perform this update, please contact our security team immediately: {support_email}\n"
                        "And immediately reset your password here: https://getleadnexus.com/password_reset/\n\n"
                        "LeadNexus Security Team"
                    )
                    send_mail(
                        subject,
                        plain_message,
                        settings.DEFAULT_FROM_EMAIL,
                        [user_email],
                        html_message=html_message,
                        fail_silently=True,
                    )
                except Exception:
                    pass

            Thread(target=send_confirmation_email, args=(user.email, user.username, now_str, contact_email, ip, user_agent)).start()

            # Clear session
            if 'reset_email' in request.session: del request.session['reset_email']
            if 'code_verified' in request.session: del request.session['code_verified']
            
            messages.success(request, "Identity restored. You can now login with your new security key.")
            return redirect('login')
        except User.DoesNotExist:
            return redirect('password_reset')
