import csv
import io
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import viewsets, status, decorators, permissions
from rest_framework.response import Response
from .models import SMTPCredential, EmailCampaign, Recipient
from .tasks import start_campaign_async
from rest_framework.serializers import ModelSerializer
from django.core.mail import get_connection

class SMTPCredentialSerializer(ModelSerializer):
    class Meta:
        model = SMTPCredential
        fields = '__all__'

class RecipientSerializer(ModelSerializer):
    class Meta:
        model = Recipient
        fields = '__all__'

class EmailCampaignSerializer(ModelSerializer):
    class Meta:
        model = EmailCampaign
        fields = '__all__'

class SMTPCredentialViewSet(viewsets.ModelViewSet):
    queryset = SMTPCredential.objects.all()
    serializer_class = SMTPCredentialSerializer

    def create(self, request, *args, **kwargs):
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
            
        self.perform_create(serializer)
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
                password=data.get('password'),
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
    queryset = EmailCampaign.objects.all().order_by('-created_at')
    serializer_class = EmailCampaignSerializer

    @decorators.action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        campaign = self.get_object()
        if campaign.status == 'completed':
            return Response({'error': 'Campaign already completed'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Reset counts if starting again from failed/paused
        start_campaign_async(campaign.id)
        return Response({'status': 'Campaign started in background'})

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
        gap_minutes = data.get('gap_minutes', 1)
        
        # 1. Create Campaign
        campaign = EmailCampaign.objects.create(
            name=name or subject,
            subject=subject,
            body=body,
            gap_minutes=gap_minutes
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
                import json
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
        if recipient_list:
            Recipient.objects.bulk_create(recipient_list)
            campaign.total_recipients = len(recipient_list)
            campaign.save()

        return Response(EmailCampaignSerializer(campaign).data, status=status.HTTP_201_CREATED)

class RecipientViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Recipient.objects.all()
    serializer_class = RecipientSerializer
    filterset_fields = ['campaign', 'status']

    def get_queryset(self):
        queryset = super().get_queryset()
        campaign_id = self.request.query_params.get('campaign')
        if campaign_id:
            queryset = queryset.filter(campaign_id=campaign_id)
        return queryset

def track_open(request, recipient_id):
    """
    View to track email opens using a 1x1 pixel.
    """
    try:
        recipient = Recipient.objects.get(id=recipient_id)
        
        if not recipient.is_opened:
            recipient.is_opened = True
            recipient.opened_at = timezone.now()
            
            # Update campaign open count
            campaign = recipient.campaign
            campaign.open_count += 1
            campaign.save(update_fields=['open_count'])
        
        recipient.open_count += 1
        recipient.save(update_fields=['is_opened', 'opened_at', 'open_count'])
        
    except Recipient.DoesNotExist:
        pass
        
    # Always return the GIF, even if recipient not found
    pixel_data = b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff\x21\xf9\x04\x01\x00\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b'
    return HttpResponse(pixel_data, content_type='image/gif')

@decorators.api_view(['GET'])
@decorators.permission_classes([permissions.IsAuthenticated])
def download_campaign_csv(request, pk):
    """
    Export campaign recipients and tracking data as CSV.
    """
    campaign = get_object_or_404(EmailCampaign, pk=pk)
    recipients = campaign.recipients.all().order_by('id')
    
    response = HttpResponse(content_type='text/csv')
    filename = f"campaign_{campaign.id}_{campaign.name.replace(' ', '_')}_report.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    writer = csv.writer(response)
    # Header
    header = ['Email', 'Name', 'Status', 'Sent At', 'Is Opened', 'First Opened At', 'Total Opens', 'Error Message']
    
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
        row = [
            r.email,
            r.name or '',
            r.status.upper(),
            r.sent_at.strftime('%Y-%m-%d %H:%M:%S') if r.sent_at else 'N/A',
            'YES' if r.is_opened else 'NO',
            r.opened_at.strftime('%Y-%m-%d %H:%M:%S') if r.opened_at else 'N/A',
            r.open_count,
            r.error_message or ''
        ]
        
        # Add values for custom keys
        for key in sorted_custom_keys:
            row.append(r.custom_data.get(key, ''))
            
        writer.writerow(row)
        
    return response
