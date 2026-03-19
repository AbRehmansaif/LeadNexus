from django.shortcuts import render
from django.http import JsonResponse
from django.core.mail import send_mail
from django.conf import settings
from .models import ContactMessage
import json

def contact_us_view(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            name = data.get('name')
            email = data.get('email')
            industry = data.get('industry', '')
            phone = data.get('phone', '')
            message = data.get('message')

            if not all([name, email, message]):
                return JsonResponse({'status': 'error', 'message': 'Missing required fields.'}, status=400)

            # 1. Save to Database
            contact_msg = ContactMessage.objects.create(
                name=name,
                email=email,
                subject=f"Contact from {industry}" if industry else "New Contact Message",
                message=f"Industry: {industry}\nPhone: {phone}\n\nMessage:\n{message}"
            )

            # 2. Get Contact Settings for Notification
            from .models import ContactSettings
            cs = ContactSettings.objects.first()
            
            dest_email = cs.notification_email if cs else settings.EMAIL_HOST_USER
            subject = f"New Contact Message: {contact_msg.subject}"
            email_body = f"""
            New message received from LeadNexus Landing Page:
            
            Name: {name}
            Email: {email}
            Industry: {industry}
            Phone: {phone}
            
            Message:
            {message}
            
            View in Admin: {settings.SITE_URL}/admin/contactus/contactmessage/{contact_msg.id}/change/
            """
            
            try:
                if cs and cs.notification_smtp:
                    # Use Custom SMTP Credential
                    from django.core.mail import get_connection, EmailMessage
                    cred = cs.notification_smtp
                    connection = get_connection(
                        host=cred.host, 
                        port=cred.port, 
                        username=cred.username, 
                        password=cred.password,
                        use_tls=cred.use_tls, 
                        use_ssl=cred.use_ssl
                    )
                    from_email = f"{cred.from_name} <{cred.from_email}>" if cred.from_name else cred.from_email
                    mail = EmailMessage(
                        subject, email_body, from_email, [dest_email],
                        connection=connection
                    )
                    mail.send()
                else:
                    # Use Default Django SMTP
                    send_mail(
                        subject,
                        email_body,
                        settings.DEFAULT_FROM_EMAIL,
                        [dest_email],
                        fail_silently=False,
                    )
            except Exception as e:
                print(f"Notification email failed: {e}")

            return JsonResponse({'status': 'success', 'message': 'Message sent successfully!'})

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)
