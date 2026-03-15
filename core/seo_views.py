from django.shortcuts import render

def email_automation_tool(request):
    return render(request, 'seo/email-automation-tool.html', {'active_page': 'seo'})

def cold_email_automation(request):
    return render(request, 'seo/cold-email-automation.html', {'active_page': 'seo'})

def email_automation_for_sales(request):
    return render(request, 'seo/email-automation-for-sales.html', {'active_page': 'seo'})

def email_automation_for_marketing(request):
    return render(request, 'seo/email-automation-for-marketing.html', {'active_page': 'seo'})

def email_automation_for_seo(request):
    return render(request, 'seo/email-automation-for-seo.html', {'active_page': 'seo'})

def email_automation_for_agencies(request):
    return render(request, 'seo/email-automation-for-agencies.html', {'active_page': 'seo'})

def email_automation_for_recruiters(request):
    return render(request, 'seo/email-automation-for-recruiters.html', {'active_page': 'seo'})

def email_automation_for_saas(request):
    return render(request, 'seo/email-automation-for-saas.html', {'active_page': 'seo'})

def email_automation_for_startups(request):
    return render(request, 'seo/email-automation-for-startups.html', {'active_page': 'seo'})

def lead_generation_email_tool(request):
    return render(request, 'seo/lead-generation-email-tool.html', {'active_page': 'seo'})

def outreach_automation(request):
    return render(request, 'seo/outreach-automation.html', {'active_page': 'seo'})
