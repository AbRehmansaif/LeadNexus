from django.urls import path
from .views import contact_us_view

app_name = 'contactus'

urlpatterns = [
    path('submit/', contact_us_view, name='contact_submit'),
]
