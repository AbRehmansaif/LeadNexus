from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Campaign, Lead
from .utils import run_campaign
from django.contrib import messages

@login_required
def campaign_list(request):
    campaigns = Campaign.objects.filter(user=request.user)
    return render(request, 'campaigns/list.html', {'campaigns': campaigns})

@login_required
def create_campaign(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        subject = request.POST.get('subject')
        body = request.POST.get('body')
        leads_raw = request.POST.get('leads') # Expecting comma separated or new line
        
        campaign = Campaign.objects.create(
            user=request.user,
            name=name,
            subject=subject,
            body=body
        )
        
        # Process leads
        for line in leads_raw.split('\n'):
            parts = line.strip().split(',')
            if len(parts) >= 1:
                email = parts[0].strip()
                first_name = parts[1].strip() if len(parts) > 1 else ""
                if email:
                    Lead.objects.create(campaign=campaign, email=email, first_name=first_name)
        
        messages.success(request, "Campaign created successfully!")
        return redirect('campaign_list')
        
    return render(request, 'campaigns/create.html')

@login_required
def campaign_detail(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk, user=request.user)
    return render(request, 'campaigns/detail.html', {'campaign': campaign})

@login_required
def start_campaign(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk, user=request.user)
    result = run_campaign(campaign.id)
    messages.info(request, result)
    return redirect('campaign_list')
