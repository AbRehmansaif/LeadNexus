from django.urls import path
from . import views

app_name = 'seo'

urlpatterns = [
    path('email-automation-tool/',           views.email_automation_tool,           name='seo-email-automation-tool'),
    path('cold-email-automation/',           views.cold_email_automation,           name='seo-cold-email-automation'),
    path('email-automation-for-sales/',       views.email_automation_for_sales,       name='seo-email-automation-for-sales'),
    path('email-automation-for-marketing/',   views.email_automation_for_marketing,   name='seo-email-automation-for-marketing'),
    path('email-automation-for-seo/',         views.email_automation_for_seo,         name='seo-email-automation-for-seo'),
    path('email-automation-for-agencies/',    views.email_automation_for_agencies,    name='seo-email-automation-for-agencies'),
    path('email-automation-for-recruiters/',  views.email_automation_for_recruiters,  name='seo-email-automation-for-recruiters'),
    path('email-automation-for-saas/',        views.email_automation_for_saas,        name='seo-email-automation-for-saas'),
    path('email-automation-for-startups/',    views.email_automation_for_startups,    name='seo-email-automation-for-startups'),
    path('lead-generation-email-tool/',       views.lead_generation_email_tool,       name='seo-lead-generation-email-tool'),
    path('outreach-automation/',             views.outreach_automation,             name='seo-outreach-automation'),
]
