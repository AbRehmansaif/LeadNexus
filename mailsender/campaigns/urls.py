from django.urls import path
from . import views

urlpatterns = [
    path('', views.campaign_list, name='campaign_list'),
    path('create/', views.create_campaign, name='create_campaign'),
    path('<int:pk>/', views.campaign_detail, name='campaign_detail'),
    path('start/<int:pk>/', views.start_campaign, name='start_campaign'),
]
