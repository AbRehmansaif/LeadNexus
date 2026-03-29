from .models import GlobalSettings

def global_settings(request):
    """Provides GlobalSettings to all templates."""
    settings = GlobalSettings.objects.first()
    return {'global_settings': settings}
