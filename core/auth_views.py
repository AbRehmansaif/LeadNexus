from django.contrib.auth import views as auth_views
from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import CreateView
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import redirect

class LoginView(auth_views.LoginView):
    template_name = 'registration/login.html'
    
    def get_success_url(self):
        messages.success(self.request, f"Welcome back, {self.request.user.username}!")
        return super().get_success_url()

class RegisterView(CreateView):
    form_class = UserCreationForm
    template_name = 'registration/register.html'
    success_url = reverse_lazy('login')

    def form_valid(self, form):
        messages.success(self.request, "Account created successfully! You can now log in.")
        return super().form_valid(form)

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('dashboard')
        return super().dispatch(request, *args, **kwargs)
