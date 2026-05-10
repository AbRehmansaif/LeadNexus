import json
import logging

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from mail.models import SMTPCredential
from .models import WarmupAccount, WarmupEmail, WarmupDailyScore, WarmupPool
from core.encryption import encrypt_password

logger = logging.getLogger(__name__)


from django.core.paginator import Paginator

# ── Dashboard ─────────────────────────────────────────────────────────────────

@login_required
def dashboard(request):
    accounts_qs = WarmupAccount.objects.filter(user=request.user).select_related('smtp_credential').order_by('-started_at')
    
    # Pagination
    paginator = Paginator(accounts_qs, 10)
    page_number = request.GET.get('page')
    accounts = paginator.get_page(page_number)

    # Accounts without a warmup profile yet
    warmed_cred_ids = accounts_qs.values_list('smtp_credential_id', flat=True)
    available_creds = SMTPCredential.objects.filter(user=request.user).exclude(id__in=warmed_cred_ids)
    pool = WarmupPool.objects.filter(user=request.user)

    # ── Ramp-up schedule visualization ──
    from .tasks import calculate_daily_volume
    ramp_schedule = []
    for d in range(1, 31):
        vol = calculate_daily_volume(d, 50)
        cls = 'future'
        # Simple visualization logic: if any account is on this day, mark it
        # (Usually better to show progress per account, but this is a global guide)
        ramp_schedule.append({'day': d, 'vol': vol, 'cls': cls})

    context = {
        'accounts': accounts,
        'available_creds': available_creds,
        'pool': pool,
        'ramp_schedule': ramp_schedule,
        'active_nav': 'warmup',
    }
    return render(request, 'warmup/dashboard.html', context)


# ── Account detail ────────────────────────────────────────────────────────────

@login_required
def account_detail(request, pk):
    account = get_object_or_404(WarmupAccount, pk=pk, user=request.user)
    logs = account.warmup_emails.all()[:50]
    daily_scores = list(
        account.daily_scores.order_by('date').values('date', 'score', 'inbox_rate', 'spam_rate', 'emails_sent')
    )
    # Chart data as JSON for the frontend
    chart_labels = [str(d['date']) for d in daily_scores]
    chart_scores = [d['score'] for d in daily_scores]
    chart_inbox  = [round(d['inbox_rate'], 1) for d in daily_scores]
    chart_spam   = [round(d['spam_rate'], 1) for d in daily_scores]

    context = {
        'account': account,
        'logs': logs,
        'chart_labels': json.dumps(chart_labels),
        'chart_scores': json.dumps(chart_scores),
        'chart_inbox': json.dumps(chart_inbox),
        'chart_spam': json.dumps(chart_spam),
        'active_nav': 'warmup',
    }
    return render(request, 'warmup/account_detail.html', context)


# ── CRUD / Controls ───────────────────────────────────────────────────────────

@login_required
@require_POST
def start_warmup(request):
    """Enroll one or more existing SMTP credentials into the warmup programme."""
    cred_ids = request.POST.getlist('cred_id')
    max_daily = int(request.POST.get('max_daily_volume', 50))
    target_days = int(request.POST.get('target_days', 30))

    if not cred_ids:
        messages.error(request, "No email accounts selected.")
        return redirect('warmup:dashboard')

    count_started = 0
    count_resumed = 0

    for cid in cred_ids:
        cred = get_object_or_404(SMTPCredential, pk=cid, user=request.user)

        account, created = WarmupAccount.objects.get_or_create(
            user=request.user,
            smtp_credential=cred,
            defaults={
                'status': 'warming',
                'max_daily_volume': max_daily,
                'target_days': target_days,
                'started_at': timezone.now(),
            },
        )
        if not created:
            account.status = 'warming'
            account.max_daily_volume = max_daily
            account.target_days = target_days
            if not account.started_at:
                account.started_at = timezone.now()
            account.save()
            count_resumed += 1
        else:
            count_started += 1

    if count_started > 0 and count_resumed > 0:
        messages.success(request, f"Started warmup for {count_started} accounts and resumed for {count_resumed} accounts.")
    elif count_started > 0:
        messages.success(request, f"Started warmup for {count_started} account(s). First cycle runs at 9 AM.")
    elif count_resumed > 0:
        messages.success(request, f"Warmup resumed for {count_resumed} account(s).")

    return redirect('warmup:dashboard')


@login_required
@require_POST
def pause_warmup(request, pk):
    account = get_object_or_404(WarmupAccount, pk=pk, user=request.user)
    account.status = 'paused'
    account.save(update_fields=['status'])
    messages.warning(request, f"Warmup paused for {account.smtp_credential.from_email}.")
    return redirect('warmup:dashboard')


@login_required
@require_POST
def resume_warmup(request, pk):
    account = get_object_or_404(WarmupAccount, pk=pk, user=request.user)
    account.status = 'warming'
    account.save(update_fields=['status'])
    messages.success(request, f"Warmup resumed for {account.smtp_credential.from_email}.")
    return redirect('warmup:dashboard')


@login_required
@require_POST
def delete_warmup(request, pk):
    account = get_object_or_404(WarmupAccount, pk=pk, user=request.user)
    email_addr = account.smtp_credential.from_email
    account.delete()
    messages.info(request, f"Warmup account {email_addr} removed.")
    return redirect('warmup:dashboard')


@login_required
@require_POST
def run_now(request, pk):
    """Manually trigger one warmup cycle immediately (useful for testing)."""
    account = get_object_or_404(WarmupAccount, pk=pk, user=request.user)
    from .tasks import run_single_account_warmup
    run_single_account_warmup.delay(account.id)
    messages.success(request, f"Warmup cycle queued for {account.smtp_credential.from_email}.")
    return redirect('warmup:detail', pk=pk)


# ── Pool management ───────────────────────────────────────────────────────────

@login_required
@require_POST
def add_pool_email(request):
    email_addr    = request.POST.get('email', '').strip()
    smtp_host     = request.POST.get('smtp_host', '').strip()
    smtp_port     = int(request.POST.get('smtp_port', 587))
    imap_host     = request.POST.get('imap_host', '').strip()
    username      = request.POST.get('username', '').strip()
    raw_password  = request.POST.get('password', '').strip()
    use_tls       = request.POST.get('use_tls') == 'on'

    if not email_addr or not smtp_host or not username or not raw_password:
        messages.error(request, "All fields are required to add a pool email.")
        return redirect('warmup:dashboard')

    encrypted = encrypt_password(raw_password)
    WarmupPool.objects.update_or_create(
        user=request.user,
        email=email_addr,
        defaults={
            'smtp_host': smtp_host,
            'smtp_port': smtp_port,
            'imap_host': imap_host,
            'username': username,
            'password': encrypted,
            'use_tls': use_tls,
            'is_active': True,
        },
    )
    messages.success(request, f"{email_addr} added to warmup pool.")
    return redirect('warmup:dashboard')


@login_required
@require_POST
def delete_pool_email(request, pk):
    pool_entry = get_object_or_404(WarmupPool, pk=pk, user=request.user)
    pool_entry.delete()
    messages.info(request, "Pool email removed.")
    return redirect('warmup:dashboard')


# ── API endpoint (score + stats for AJAX polling) ─────────────────────────────

@login_required
def api_account_stats(request, pk):
    account = get_object_or_404(WarmupAccount, pk=pk, user=request.user)
    label, _ = account.score_label
    return JsonResponse({
        'score': account.warmup_score,
        'score_label': label,
        'inbox_rate': account.inbox_rate,
        'spam_rate': account.spam_rate,
        'reply_rate': account.reply_rate,
        'day_number': account.day_number,
        'target_days': account.target_days,
        'progress': account.progress_percentage,
        'total_sent': account.total_sent,
        'status': account.status,
    })
