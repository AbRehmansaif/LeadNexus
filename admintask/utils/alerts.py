import requests
import logging
from admintask.models import AdminTaskSettings, ErrorNotification

logger = logging.getLogger(__name__)

def send_admin_alert(alert_type, message, context=None):
    """
    Saves an alert to the database and sends it to Telegram if configured.
    alert_type: 'campaign_fail', 'server_error', 'security_breach', 'quota_exhausted'
    """
    # 1. Save to DB for Admin Matrix
    notification = ErrorNotification.objects.create(
        type=alert_type,
        message=message,
        context_data=context or {}
    )

    # 2. Try Telegram
    settings = AdminTaskSettings.objects.first()
    if settings and settings.enable_error_alerts and settings.telegram_bot_token and settings.admin_chat_id:
        try:
            url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
            payload = {
                "chat_id": settings.admin_chat_id,
                "text": f"🚨 *Neural Alert: {alert_type.upper()}*\n\n{message}",
                "parse_mode": "Markdown"
            }
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                notification.sent_to_telegram = True
                notification.save()
            else:
                logger.error(f"Telegram alert failed: {response.text}")
        except Exception as e:
            logger.error(f"Error sending telegram alert: {e}")

    return notification
