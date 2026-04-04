from django.urls import path
from . import views

app_name = 'csvtools'

urlpatterns = [
    path('tools/csv-cleaner/', views.cleaner_page, name='cleaner'),
    path('tools/csv-cleaner/process/', views.cleaner_process, name='cleaner-process'),
    path('tools/csv-cleaner/preview/', views.cleaner_preview, name='cleaner-preview'),
]
