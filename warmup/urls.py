from django.urls import path
from . import views

app_name = 'warmup'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('account/<int:pk>/', views.account_detail, name='detail'),

    # Controls
    path('start/', views.start_warmup, name='start'),
    path('account/<int:pk>/pause/', views.pause_warmup, name='pause'),
    path('account/<int:pk>/resume/', views.resume_warmup, name='resume'),
    path('account/<int:pk>/delete/', views.delete_warmup, name='delete'),
    path('account/<int:pk>/run-now/', views.run_now, name='run_now'),

    # Pool
    path('pool/add/', views.add_pool_email, name='add_pool'),
    path('pool/<int:pk>/delete/', views.delete_pool_email, name='delete_pool'),

    # API
    path('api/account/<int:pk>/stats/', views.api_account_stats, name='api_stats'),
]
