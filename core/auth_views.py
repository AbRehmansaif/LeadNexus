from django.contrib.auth import views as auth_views
from django.contrib import messages
from django.urls import reverse_lazy

class LoginView(auth_views.LoginView):
    template_name = 'registration/login.html'
    
    def get_success_url(self):
        messages.success(self.request, f"Welcome back, {self.request.user.username}!")
        return super().get_success_url()
