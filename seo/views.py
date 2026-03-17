from django.shortcuts import render

# ── SEO Marketing Pages ──────────────────────────────

def email_automation_tool(request):
    """Target keyword: email automation tool"""
    return render(request, 'seo/email-automation-tool.html', {'active_page': 'seo'})

def cold_email_automation(request):
    """Target keyword: cold email automation"""
    return render(request, 'seo/cold-email-automation.html', {'active_page': 'seo'})

def email_automation_for_sales(request):
    """Target keyword: email automation for sales"""
    return render(request, 'seo/email-automation-for-sales.html', {'active_page': 'seo'})

def email_automation_for_marketing(request):
    """Target keyword: email automation for marketing"""
    return render(request, 'seo/email-automation-for-marketing.html', {'active_page': 'seo'})

def email_automation_for_seo(request):
    """Target keyword: email automation for seo"""
    return render(request, 'seo/email-automation-for-seo.html', {'active_page': 'seo'})

def email_automation_for_agencies(request):
    """Target keyword: email automation for agencies"""
    return render(request, 'seo/email-automation-for-agencies.html', {'active_page': 'seo'})

def email_automation_for_recruiters(request):
    """Target keyword: email automation for recruiters"""
    return render(request, 'seo/email-automation-for-recruiters.html', {'active_page': 'seo'})

def email_automation_for_saas(request):
    """Target keyword: email automation for saas"""
    return render(request, 'seo/email-automation-for-saas.html', {'active_page': 'seo'})

def email_automation_for_startups(request):
    """Target keyword: email automation for startups"""
    return render(request, 'seo/email-automation-for-startups.html', {'active_page': 'seo'})

def lead_generation_email_tool(request):
    """Target keyword: lead generation email tool"""
    return render(request, 'seo/lead-generation-email-tool.html', {'active_page': 'seo'})

def outreach_automation(request):
    """Target keyword: outreach automation"""
    return render(request, 'seo/outreach-automation.html', {'active_page': 'seo'})

# ── Free Tool Pages ───────────────────────────────────

def markdown_to_html_converter(request):
    """Target keywords: markdown to html converter, html to markdown, free markdown converter"""
    return render(request, 'seo/tools/markdown-to-html-converter.html', {'active_page': 'seo'})

def excel_to_csv_converter(request):
    """Target keywords: excel to csv converter, xlsx to csv, xls to csv, free csv converter"""
    return render(request, 'seo/tools/excel-to-csv-converter.html', {'active_page': 'seo'})

def email_spam_word_checker(request):
    """Target keywords: email spam word checker, cold email spam checker, check email for spam words, cold email deliverability tool"""
    return render(request, 'seo/tools/email-spam-checker.html', {'active_page': 'seo'})

def email_warmup_calculator(request):
    """Target keywords: email warmup schedule, cold email warmup calculator, domain warmup"""
    return render(request, 'seo/tools/email-warmup-calculator.html', {'active_page': 'seo'})
