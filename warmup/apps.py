from django.apps import AppConfig


class WarmupConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'warmup'
    verbose_name = 'Email Warmup'
