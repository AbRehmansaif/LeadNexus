from django.urls import path
from . import views

urlpatterns = [
    path('matrix/', views.admin_matrix, name='admin-matrix'),
    path('api/health/', views.get_server_health, name='admin-api-health'),
]
