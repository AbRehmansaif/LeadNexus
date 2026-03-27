from django.urls import path
from . import views

urlpatterns = [
    path('', views.affiliate_landing, name='affiliate-landing'),
    path('apply/', views.affiliate_register, name='affiliate-apply'),
    path('register/', views.affiliate_register, name='affiliate-register'),
    path('dashboard/', views.affiliate_dashboard, name='affiliate-dashboard'),
    path('payout-request/', views.affiliate_payout_request, name='affiliate-payout-request'),
    path('update-payout/', views.affiliate_update_payout, name='affiliate-update-payout'),
    path('delete-payout/', views.affiliate_delete_payout, name='affiliate-delete-payout'),
    path('update-settings/', views.affiliate_update_settings, name='affiliate-update-settings'),
]
