import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Scrapper.settings')
django.setup()

from core.templatetags.admin_metrics import get_nexus_metrics
try:
    metrics = get_nexus_metrics()
    print(metrics)
except Exception as e:
    print("FAILED", e)
