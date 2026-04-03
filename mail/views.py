import csv
import io
import json
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.core.cache import cache
from django.db.models import F
from rest_framework import viewsets, status, decorators, permissions, serializers, pagination
from rest_framework.response import Response
from .models import SMTPCredential, EmailCampaign, Recipient, CampaignStep, SentEmailLog
from .tasks import trigger_followup_task, check_for_replies, _mark_failed
from django.core.mail import get_connection
from django.views.decorators.clickjacking import xframe_options_exempt
from core.encryption import decrypt_password

class SMTPCredentialSerializer(serializers.ModelSerializer):
    class Meta:
        model = SMTPCredential
        fields = '__all__'

class CampaignStepSerializer(serializers.ModelSerializer):
    class Meta:
        model = CampaignStep
        fields = '__all__'

class RecipientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recipient
        fields = '__all__'

class EmailCampaignSerializer(serializers.ModelSerializer):
    steps = CampaignStepSerializer(many=True, read_only=True)
    stats = serializers.SerializerMethodField()

    class Meta:
        model = EmailCampaign
        fields = '__all__'
    
    def get_stats(self, obj):
        """Use the high-performance stats property from the model."""
        return obj.stats

class SMTPCredentialViewSet(viewsets.ModelViewSet):
    serializer_class = SMTPCredentialSerializer
    
    def get_queryset(self):
        return SMTPCredential.objects.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        # Check Quota
        if not request.user.profile.can_add_smtp():
            return Response(
                {'detail': f'SMTP slot limit reached ({request.user.profile.smtp_limit}). Upgrade your plan for more slots.'},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Test connection before saving
        data = serializer.validated_data
        success, error_msg = self.test_smtp_connection(data)
        
        if not success:
            return Response(
                {'detail': error_msg},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        serializer.save(user=request.user)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        
        # Test connection before saving
        data = serializer.validated_data
        # For partial updates, we need to merge with existing data for the test
        test_data = {
            'host': data.get('host', instance.host),
            'port': data.get('port', instance.port),
            'username': data.get('username', instance.username),
            'password': data.get('password', instance.password),
            'use_tls': data.get('use_tls', instance.use_tls),
            'use_ssl': data.get('use_ssl', instance.use_ssl),
        }
        
        success, error_msg = self.test_smtp_connection(test_data)
        
        if not success:
            return Response(
                {'detail': error_msg},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        self.perform_update(serializer)
        return Response(serializer.data)

    def test_smtp_connection(self, data):
        """Helper to test SMTP connection and return human-friendly errors."""
        try:
            connection = get_connection(
                host=data.get('host'),
                port=data.get('port'),
                username=data.get('username'),
                password=decrypt_password(data.get('password')),
                use_tls=data.get('use_tls'),
                use_ssl=data.get('use_ssl'),
                timeout=10
            )
            connection.open()
            connection.close()
            return True, None
        except Exception as e:
            error_str = str(e)
            
            # Professional cleanup for common SMTP errors
            if "Username and Password not accepted" in error_str:
                error_str = "Authentication failed. Please verify your email and password. (Note: Gmail/Outlook require an App Password)"
            elif "Connection refused" in error_str:
                error_str = "Could not connect to the SMTP server. Please check the Host and Port."
            elif "timeout" in error_str.lower():
                error_str = "Connection timed out. The server might be blocking the port."
            else:
                # Fallback: remove the raw tuple/byte formatting if present
                if "(" in error_str and "b'" in error_str:
                    try:
                        # Attempt to extract the text between single quotes
                        parts = error_str.split("'")
                        if len(parts) > 1:
                            error_str = parts[1]
                    except:
                        pass
            
            return False, error_str

class EmailCampaignViewSet(viewsets.ModelViewSet):
    serializer_class = EmailCampaignSerializer
    pagination_class = pagination.PageNumberPagination
    
    def get_queryset(self):
        return EmailCampaign.objects.filter(user=self.request.user, steps__isnull=False).distinct().order_by('-created_at')

    @decorators.action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        campaign = self.get_object()
        if campaign.status == 'completed':
            return Response({'error': 'Campaign already completed'}, status=status.HTTP_400_BAD_REQUEST)
        # Resume paused campaigns or restart pending ones
        trigger_followup_task(campaign.id, 1)
        return Response({'status': 'Campaign started (Step 1) in background'})

    @decorators.action(detail=True, methods=['post'])
    def trigger_step(self, request, pk=None):
        """Manually trigger a specific step for the campaign."""
        campaign = self.get_object()
        step_number = request.data.get('step_number')
        if not step_number:
            return Response({'error': 'step_number is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        trigger_followup_task(campaign.id, int(step_number))
        return Response({'status': f'Step {step_number} triggered in background'})

    @decorators.action(detail=False, methods=['post'])
    def check_replies(self, request):
        """Manually trigger the IMAP reply checker using Celery."""
        check_for_replies.delay()
        return Response({'status': 'Reply detection task initiated'})

    @decorators.action(detail=True, methods=['post'])
    def pause(self, request, pk=None):
        campaign = self.get_object()
        campaign.status = 'paused'
        campaign.save()
        return Response({'status': 'Campaign paused'})

    @decorators.action(detail=False, methods=['post'])
    def create_with_recipients(self, request):
        data = request.data
        name = data.get('name', '')
        subject = data.get('subject', '')
        body = data.get('body', '')
        gap_seconds = data.get('gap_seconds', 2)
        scheduled_at = data.get('scheduled_at')
        status_val = data.get('status', 'running') # Default to running if not scheduled
        if scheduled_at:
            status_val = 'scheduled'

        # 1. Validation & Create Campaign
        profile = request.user.profile
        if not profile.default_work_days or not profile.default_send_window_start or not profile.default_send_window_end:
            return Response(
                {'error': 'Mission critical: You must configure your Outreach Schedule in Profile Settings before deploying a campaign.'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        work_days_str = ','.join(map(str, profile.default_work_days))

        # Always create in 'pending' first — status is updated after recipients are confirmed
        # to avoid a race where the Celery task fires before bulk_create completes.
        campaign = EmailCampaign.objects.create(
            user=request.user,
            name=name or subject,
            subject=subject,
            body=body,
            gap_seconds=gap_seconds,
            scheduled_at=scheduled_at,
            status='pending',  # will be updated below once recipients are validated
            send_window_start=profile.default_send_window_start,
            send_window_end=profile.default_send_window_end,
            work_days=work_days_str
        )

        # 2. Setup Steps if provided
        steps_data = data.get('steps', [])
        if isinstance(steps_data, str):
            steps_data = json.loads(steps_data)
        
        if steps_data:
            for s in steps_data:
                CampaignStep.objects.create(
                    campaign=campaign,
                    step_number=s.get('step_number'),
                    wait_days=s.get('wait_days', 3),
                    subject=s.get('subject'),
                    body=s.get('body'),
                    subject_b=s.get('subject_b'),
                    body_b=s.get('body_b')
                )
        else:
            # Fallback: Create Step 1 from basic campaign info
            CampaignStep.objects.create(
                campaign=campaign,
                step_number=1,
                wait_days=0,
                subject=subject,
                body=body
            )

        recipient_list = []

        # 2. Process Recipients from CSV file
        if 'csv_file' in request.FILES:
            csv_file = request.FILES['csv_file']
            
            # Simple extension check
            if not csv_file.name.endswith('.csv'):
                campaign.delete() # Cleanup
                return Response({'error': 'Invalid file format. Please upload a .csv file.'}, status=status.HTTP_400_BAD_REQUEST)

            try:
                # Try UTF-8 first (standard)
                decoded_file = csv_file.read().decode('utf-8')
            except UnicodeDecodeError:
                # Fallback to latin-1 if UTF-8 fails (common for Excel CSVs)
                csv_file.seek(0)
                decoded_file = csv_file.read().decode('latin-1')
            
            try:
                io_string = io.StringIO(decoded_file)
                reader = csv.DictReader(io_string)
                for row in reader:
                    email = row.get('email') or row.get('Email')
                    if email:
                        recipient_list.append(Recipient(
                            campaign=campaign,
                            email=email,
                            name=row.get('name') or row.get('Name') or '',
                            custom_data={k.lower(): v for k, v in row.items() if k.lower() not in ['email', 'name']}
                        ))
            except Exception:
                campaign.delete()
                return Response({'error': 'Failed to parse CSV. The file may be corrupt or not a valid CSV.'}, status=status.HTTP_400_BAD_REQUEST)

        # 3. Process Recipients from manual input (can be list or JSON string)
        manual_recipients = data.get('recipients', [])
        if isinstance(manual_recipients, str):
            try:
                manual_recipients = json.loads(manual_recipients)
            except json.JSONDecodeError:
                manual_recipients = []

        if isinstance(manual_recipients, list):
            for r in manual_recipients:
                email = r.get('email')
                if email:
                    recipient_list.append(Recipient(
                        campaign=campaign,
                        email=email,
                        name=r.get('name', ''),
                        custom_data=r.get('custom_data', {})
                    ))

        # Bulk create recipients
        if not recipient_list:
            campaign.delete()
            return Response(
                {'error': 'No valid recipients found. Ensure your CSV has an "email" column or enter leads manually.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        Recipient.objects.bulk_create(recipient_list)
        campaign.total_recipients = len(recipient_list)
        # Now that recipients are confirmed, set the final status
        campaign.status = status_val
        campaign.save(update_fields=['total_recipients', 'status'])

        return Response(EmailCampaignSerializer(campaign).data, status=status.HTTP_201_CREATED)

class RecipientViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Recipient.objects.all()
    serializer_class = RecipientSerializer
    pagination_class = pagination.PageNumberPagination
    filterset_fields = ['campaign', 'status']

    def get_queryset(self):
        queryset = super().get_queryset()
        campaign_id = self.request.query_params.get('campaign')
        if campaign_id:
            queryset = queryset.filter(campaign_id=campaign_id)
        return queryset

def track_open(request, recipient_id):
    """
    Enhanced view to track email opens using a 1x1 pixel.
    Includes filtering for bots, scanners, and the sender's own session 
    to significantly reduce false positives.
    """
    # 1. Ignore HEAD requests (common for scanners/pre-fetchers)
    if request.method == "HEAD":
        return HttpResponse(status=204)

    # 2. Extract metadata
    ua = request.META.get('HTTP_USER_AGENT', '').lower()
    ip = request.META.get('REMOTE_ADDR', '')
    purpose = request.META.get('HTTP_X_PURPOSE', '').lower()
    moz_purpose = request.META.get('HTTP_X_MOZ', '').lower()
    
    # 3. Known Bot/Scanner/Pre-fetch Filtering
    # Common strings used by security scanners, link pre-fetchers, and bots
    bot_keywords = [
        'bot', 'spider', 'crawl', 'scanner', 'security', 'preview', 
        'transcoder', 'headless', 'inspect', 'discovery', 'validator',
        'office', 'microsoft', 'google-http-client', 'bing', 'yahoo', 
        'facebookexternalhit', 'slackbot', 'discordbot', 'whatsapp',
        'apple-pubsub', 'embedly', 'bitlybot'
    ]
    
    is_bot = any(keyword in ua for keyword in bot_keywords)
    
    # Pre-fetch detection
    if purpose == 'preview' or moz_purpose == 'prefetch' or 'prefetch' in ua:
        is_bot = True
    
    # Note: We do NOT skip 'google' entirely because Gmail uses a proxy
    # for real human opens. but we can skip specific Google crawlers.
    if "googlebot" in ua or "adsbot-google" in ua:
        is_bot = True

    try:
        recipient = Recipient.objects.select_related('campaign').get(id=recipient_id)
        
        # 4. Skip tracking if:
        # - It's a known bot
        # - The request comes from the sender themselves (if logged in to the platform)
        is_sender = False
        if request.user.is_authenticated and request.user.id == recipient.campaign.user_id:
            is_sender = True
            
        if not is_bot and not is_sender:
            if not recipient.is_opened:
                recipient.is_opened = True
                recipient.opened_at = timezone.now()
                
                # ATOMIC UPDATES
                campaign = recipient.campaign
                EmailCampaign.objects.filter(id=campaign.id).update(
                    open_count=F('open_count') + 1
                )
                
                # Invalidate cache for this campaign
                cache.delete(f"campaign_stats_{campaign.id}")
            
            # Record every single open increment (even if already marked is_opened)
            # but only if it's not a bot/sender
            recipient.open_count = (recipient.open_count or 0) + 1
            recipient.save(update_fields=['is_opened', 'opened_at', 'open_count'])
        
    except Recipient.DoesNotExist:
        pass
        
    # Always return the GIF, even if recipient not found or hit was filtered
    pixel_data = b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff\x21\xf9\x04\x01\x00\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b'
    response = HttpResponse(pixel_data, content_type='image/gif')
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response

@xframe_options_exempt
def unsubscribe(request, recipient_id):
    """
    View to handle formal unsubscribe requests via link.
    Now includes a confirmation step to prevent automated link scanners/bots 
    from accidentally unsubscribing recipients.
    """
    recipient = get_object_or_404(Recipient, id=recipient_id)
    
    # Handle the actual unsubscription via POST (manual user click)
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Re-fetch with lock for atomic update
                r = Recipient.objects.select_for_update().get(id=recipient_id)
                if not r.is_unsubscribed:
                    r.is_unsubscribed = True
                    r.unsubscribed_at = timezone.now()
                    r.status = 'unsubscribed'
                    r.save(update_fields=['is_unsubscribed', 'unsubscribed_at', 'status'])
                    
                    # Invalidate cache
                    cache.delete(f"campaign_stats_{r.campaign_id}")
                    
            # Get the 'From Name' for the success page
            last_log = recipient.delivery_logs.order_by('-sent_at').first()
            from_name = last_log.smtp_used.from_name if (last_log and last_log.smtp_used and last_log.smtp_used.from_name) else "the sender"

            success_html = f"""
            <html>
            <head>
                <title>Unsubscribed from emails</title>
                <style>
                    body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #0d1117; color: #ffffff; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }}
                    .card {{ background: #161b22; border: 1px solid #30363d; padding: 40px; border-radius: 12px; text-align: center; max-width: 400px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }}
                    h1 {{ color: #10b981; margin-top: 0; }}
                    p {{ color: #8b949e; line-height: 1.6; }}
                    .icon {{ font-size: 48px; margin-bottom: 20px; color: #10b981; }}
                </style>
            </head>
            <body>
                <div class="card">
                    <div class="icon">✓</div>
                    <h1>Unsubscribed</h1>
                    <p>You have been successfully removed from this campaign. You will no longer receive automated follow-ups from <b>{from_name}</b>.</p>
                </div>
            </body>
            </html>
            """
            return HttpResponse(success_html)
        except Exception as e:
            return HttpResponse(f"An error occurred: {str(e)}", status=500)

    # GET Request: Show confirmation page (Stops bots/scanners)
    last_log = recipient.delivery_logs.order_by('-sent_at').first()
    from_email = last_log.smtp_used.from_email if (last_log and last_log.smtp_used) else "the sender"
    
    confirm_html = f"""
    <html>
    <head>
        <title>Confirm Unsubscribe</title>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #0d1117; color: #ffffff; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }}
            .card {{ background: #161b22; border: 1px solid #30363d; padding: 40px; border-radius: 12px; text-align: center; max-width: 450px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }}
            h1 {{ color: #8b5cf6; margin-top: 0; font-size: 24px; }}
            p {{ color: #8b949e; line-height: 1.6; margin-bottom: 30px; }}
            .btn {{ background: #ef4444; color: white; border: none; padding: 12px 30px; border-radius: 8px; cursor: pointer; font-weight: bold; font-size: 16px; transition: background 0.2s; text-decoration: none; display: inline-block; }}
            .btn:hover {{ background: #dc2626; }}
            .cancel {{ color: #8b949e; text-decoration: none; display: block; margin-top: 20px; font-size: 14px; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>Stop Receiving Emails?</h1>
            <p>Are you sure you want to unsubscribe from communications sent via <b>{from_email}</b>?</p>
            <form method="POST">
                <input type="hidden" name="recipient_id" value="{recipient_id}">
                <button type="submit" class="btn">Confirm Unsubscribe</button>
            </form>
            <p class="cancel">If you didn't mean to click this, you can simply close this window.</p>
        </div>
    </body>
    </html>
    """
    return HttpResponse(confirm_html)

@decorators.api_view(['GET'])
@decorators.permission_classes([permissions.IsAuthenticated])
def download_campaign_csv(request, pk):
    """
    Export campaign recipients and tracking data as CSV.
    Only the campaign owner can download their campaign data.
    """
    # Ownership check — prevents any authenticated user from accessing another's data
    campaign = get_object_or_404(EmailCampaign, pk=pk, user=request.user)
    recipients = campaign.recipients.prefetch_related(
        'delivery_logs__smtp_used'
    ).order_by('id')

    response = HttpResponse(content_type='text/csv')
    filename = f"campaign_{campaign.id}_{campaign.name.replace(' ', '_')}_report.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    header = ['Email', 'Name', 'Status', 'Last Sent At', 'Step', 'Sent Via (Email)', 'Opened', 'Opened At', 'Replied', 'Replied At', 'Error']

    # Add custom data keys to header if they exist
    custom_keys = set()
    for r in recipients:
        if r.custom_data:
            custom_keys.update(r.custom_data.keys())

    sorted_custom_keys = sorted(list(custom_keys))
    header.extend(sorted_custom_keys)
    writer.writerow(header)

    # Rows
    for r in recipients:
        # Use r.smtp_email (stored on recipient at send time) as primary source.
        # Fallback to the delivery log's smtp credential from_email if available.
        if r.smtp_email:
            sent_via = r.smtp_email
        else:
            last_log = r.delivery_logs.last()
            sent_via = last_log.smtp_used.from_email if (last_log and last_log.smtp_used) else 'N/A'

        row = [
            r.email,
            r.name or '',
            r.get_status_display(),
            r.last_sent_at.strftime('%Y-%m-%d %H:%M:%S') if r.last_sent_at else 'N/A',
            r.current_step_index,
            sent_via,
            'YES' if r.is_opened else 'NO',
            r.opened_at.strftime('%m-%d %H:%M') if r.opened_at else '-',
            'YES' if r.is_replied else 'NO',
            r.replied_at.strftime('%m-%d %H:%M') if r.replied_at else '-',
            r.error_message or ''
        ]

        for key in sorted_custom_keys:
            row.append(r.custom_data.get(key, ''))

        writer.writerow(row)

    return response


@login_required
def email_dedup_tool_page(request):
    """Renders the Email Deduplication Tool page."""
    return render(request, 'mail/email_dedup_tool.html', {'active_page': 'campaigns'})


@login_required
def email_dedup_tool_process(request):
    """
    Processes an uploaded CSV file entirely in-memory.
    Cross-references each email against all previously sent Recipient records
    for the current user's campaigns.

    Security layers:
      1. Login required (decorator)
      2. CSRF token (Django middleware)
      3. POST-only method enforcement
      4. File size hard cap (5 MB)
      5. MIME type validation
      6. File extension check (with path traversal protection)
      7. Filename length and character sanitization
      8. Per-user rate limiting (10 requests / minute)
      9. Max column count cap (50 columns)
     10. Max row count cap (100,000 rows)
     11. Per-cell email field length cap (320 chars, RFC 5321 max)

    Nothing is stored to disk or database.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method.'}, status=405)

    # ── Layer 1: Rate Limiting ────────────────────────────────────────────────
    # Allow max 10 upload-process requests per user per 60 seconds.
    rate_key = f'dedup_rate_{request.user.id}'
    request_count = cache.get(rate_key, 0)
    if request_count >= 10:
        return JsonResponse(
            {'error': 'Too many requests. Please wait a moment before uploading again.'},
            status=429
        )
    cache.set(rate_key, request_count + 1, timeout=60)

    # ── Layer 2: File Presence ────────────────────────────────────────────────
    csv_file = request.FILES.get('csv_file')
    if not csv_file:
        return JsonResponse({'error': 'No file was uploaded.'}, status=400)

    # ── Layer 3: File Size Cap (5 MB) ─────────────────────────────────────────
    MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
    if csv_file.size > MAX_FILE_SIZE:
        return JsonResponse(
            {'error': f'File is too large ({csv_file.size // (1024*1024)} MB). Maximum allowed size is 5 MB.'},
            status=400
        )

    # ── Layer 4: Filename Sanitization ────────────────────────────────────────
    # Prevent path traversal attacks (e.g. ../../etc/passwd)
    import os, re
    raw_name = os.path.basename(csv_file.name or '')
    if len(raw_name) > 255:
        return JsonResponse({'error': 'Filename is too long.'}, status=400)
    if not re.match(r'^[\w\s\-\.]+$', raw_name):
        return JsonResponse({'error': 'Filename contains invalid characters.'}, status=400)

    # ── Layer 5: File Extension Check ─────────────────────────────────────────
    if not raw_name.lower().endswith('.csv'):
        return JsonResponse({'error': 'Only .csv files are accepted.'}, status=400)

    # ── Layer 6: MIME Type Validation ─────────────────────────────────────────
    ALLOWED_MIME_TYPES = {
        'text/csv',
        'text/plain',
        'application/csv',
        'application/vnd.ms-excel',  # some older Excel exports
    }
    if csv_file.content_type and csv_file.content_type.split(';')[0].strip() not in ALLOWED_MIME_TYPES:
        return JsonResponse(
            {'error': 'Invalid file type. Please upload a plain CSV file.'},
            status=400
        )

    # ── Layer 7: Read & Decode ────────────────────────────────────────────────
    try:
        try:
            content = csv_file.read().decode('utf-8')
        except UnicodeDecodeError:
            csv_file.seek(0)
            content = csv_file.read().decode('latin-1')
    except Exception:
        return JsonResponse({'error': 'Could not read the file. Please ensure it is a valid CSV.'}, status=400)

    # ── Layer 8: Parse CSV Structure ─────────────────────────────────────────
    try:
        reader = csv.DictReader(io.StringIO(content))
        rows = list(reader)
        fieldnames = reader.fieldnames or []
    except Exception:
        return JsonResponse({'error': 'Failed to read the file structure. Please check your CSV format.'}, status=400)

    if not rows:
        return JsonResponse({'error': 'The uploaded file appears to be empty.'}, status=400)

    # ── Layer 9: Column Count Cap (prevents memory bombs via wide CSVs) ───────
    MAX_COLUMNS = 50
    if len(fieldnames) > MAX_COLUMNS:
        return JsonResponse(
            {'error': f'Your file has too many columns ({len(fieldnames)}). Maximum allowed is {MAX_COLUMNS}.'},
            status=400
        )

    # ── Layer 10: Row Count Cap ───────────────────────────────────────────────
    MAX_ROWS = 100_000
    if len(rows) > MAX_ROWS:
        return JsonResponse(
            {'error': f'Your file has too many rows ({len(rows):,}). Maximum allowed is {MAX_ROWS:,} per upload.'},
            status=400
        )

    # ── Detect Email Column (case-insensitive) ────────────────────────────────
    email_col = None
    for col in fieldnames:
        if col.strip().lower() == 'email':
            email_col = col
            break

    if not email_col:
        return JsonResponse(
            {'error': 'No "email" column found. Please ensure your CSV has a column named "email".'},
            status=400
        )


    # Build a lookup map: email (lowercased) → list of campaign names sent to
    # Only look at the current user's campaigns
    sent_records = (
        Recipient.objects
        .filter(
            campaign__user=request.user,
            status__in=['active', 'replied', 'completed', 'unsubscribed', 'failed']
        )
        .exclude(current_step_index=0)
        .select_related('campaign')
        .values('email', 'campaign__name')
    )

    sent_map = {}  # {lowercase_email: [campaign_name, ...]}
    for record in sent_records:
        key = record['email'].strip().lower()
        camp_name = record['campaign__name'] or 'Unknown Campaign'
        if key not in sent_map:
            sent_map[key] = []
        if camp_name not in sent_map[key]:
            sent_map[key].append(camp_name)

    # Annotate every row
    already_sent = []   # summary list for the table
    clean_rows = []     # rows NOT previously contacted
    annotated_rows = [] # ALL rows with annotation

    seen_in_file = set()  # deduplicate within the uploaded file itself
    valid_email_count = 0  # count only rows that had a real email address

    for row in rows:
        raw_email = row.get(email_col, '').strip()
        if not raw_email:
            continue

        # ── Layer 11: Email Field Length Cap (RFC 5321 max = 320 chars) ───────
        if len(raw_email) > 320:
            continue  # silently skip malformed oversized cells

        valid_email_count += 1

        lower_email = raw_email.lower()
        campaigns_used = sent_map.get(lower_email, [])
        was_sent = bool(campaigns_used)
        campaign_names_str = ', '.join(campaigns_used) if campaigns_used else ''

        annotated_row = dict(row)
        annotated_row['_previously_sent'] = 'YES' if was_sent else 'NO'
        annotated_row['_campaign_names'] = campaign_names_str
        annotated_rows.append(annotated_row)

        if was_sent:
            if lower_email not in seen_in_file:
                already_sent.append({
                    'email': raw_email,
                    'campaigns': campaign_names_str,
                })
        else:
            clean_rows.append(row)

        seen_in_file.add(lower_email)

    return JsonResponse({
        'success': True,
        'total_uploaded': valid_email_count,
        'already_sent_count': len(already_sent),
        'clean_count': len(clean_rows),
        'already_sent': already_sent,
        'clean_fieldnames': fieldnames,
        'clean_rows': clean_rows,
        'all_fieldnames': fieldnames,
        'all_rows': annotated_rows,
    })


@login_required
def email_dedup_download(request):
    """
    Streams a filtered clean CSV (no previously contacted leads) back to the browser.
    All data is constructed in-memory from POST JSON — nothing stored.
    """
    if request.method != 'POST':
        return HttpResponse(status=405)

    try:
        payload = json.loads(request.body)
        fieldnames = payload.get('fieldnames', [])
        rows = payload.get('rows', [])
    except (json.JSONDecodeError, Exception):
        return HttpResponse('Invalid payload', status=400)

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore')
    writer.writeheader()
    for row in rows:
        writer.writerow(row)

    response = HttpResponse(output.getvalue(), content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="clean_leads.csv"'
    return response
