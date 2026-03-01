import csv
import io
from rest_framework import viewsets, status, decorators
from rest_framework.response import Response
from .models import SMTPCredential, EmailCampaign, Recipient
from .tasks import start_campaign_async
from rest_framework.serializers import ModelSerializer

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
            decoded_file = csv_file.read().decode('utf-8')
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
