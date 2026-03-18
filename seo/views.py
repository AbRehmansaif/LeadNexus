from django.shortcuts import render
from django.http import JsonResponse
import re

try:
    import dns.resolver
    DNS_AVAILABLE = True
except ImportError:
    DNS_AVAILABLE = False

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

def dns_config_generator(request):
    """Target keywords: SPF record generator, DKIM generator, DMARC checker, DNS records for email, deliverability setup"""
    return render(request, 'seo/tools/dns-config-generator.html', {'active_page': 'seo'})

def cold_email_roi_calculator(request):
    """Target keywords: cold email ROI calculator, marketing calculator, cold outreach profitability, sales ROI"""
    return render(request, 'seo/tools/cold-email-roi-calculator.html', {'active_page': 'seo'})

def utm_link_builder(request):
    """Target keywords: UTM link builder, campaign URL builder, UTM tracking, cold email tracking, GA4 UTM builder"""
    return render(request, 'seo/tools/utm-link-builder.html', {'active_page': 'seo'})

import random
from datetime import datetime

def campaign_analytics_dashboard(request):
    """Premium SaaS dynamic dashboard with randomized realistic stats"""
    
    # Generate realistic dynamic data
    base_revenue = random.randint(12000, 18000)
    revenue_delta = round(random.uniform(5.0, 15.0), 1)
    conversion_rate = round(random.uniform(3.5, 5.2), 2)
    avg_click_value = round(random.uniform(2.5, 4.5), 2)
    
    # Generate chart data (7 days)
    chart_data = [random.randint(40, 95) for _ in range(7)]
    
    context = {
        'active_page': 'seo',
        'revenue': f"{base_revenue:,.2f}",
        'revenue_delta': revenue_delta,
        'conversion_rate': conversion_rate,
        'avg_click_value': avg_click_value,
        'chart_data': chart_data,
        'refresh_time': datetime.now().strftime("%Y.%m.%d %H:%M:%S")
    }
    
    return render(request, 'seo/tools/campaign-roi-dashboard.html', context)

def check_dns_records(request):
    """AJAX endpoint to check SPF and DMARC records for a domain"""
    domain = request.GET.get('domain', '').strip()
    if not domain:
        return JsonResponse({'error': 'No domain provided'}, status=400)
    
    results = {
        'spf': {'exists': False, 'value': '', 'valid': False},
        'dmarc': {'exists': False, 'value': '', 'valid': False},
    }
    
    try:
        # Check SPF (Look for TXT records starting with v=spf1)
        try:
            txt_records = dns.resolver.resolve(domain, 'TXT')
            for record in txt_records:
                txt_val = record.to_text().strip('"')
                if txt_val.startswith('v=spf1'):
                    results['spf']['exists'] = True
                    results['spf']['value'] = txt_val
                    results['spf']['valid'] = True # Simple exists check
                    break
        except Exception:
            pass

        # Check DMARC (Look for TXT records at _dmarc.domain)
        try:
            dmarc_host = f'_dmarc.{domain}'
            dmarc_records = dns.resolver.resolve(dmarc_host, 'TXT')
            for record in dmarc_records:
                txt_val = record.to_text().strip('"')
                if txt_val.startswith('v=DMARC1'):
                    results['dmarc']['exists'] = True
                    results['dmarc']['value'] = txt_val
                    results['dmarc']['valid'] = True
                    break
        except Exception:
            pass
            
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
        
    return JsonResponse(results)
