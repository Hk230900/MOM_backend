from django.apps import AppConfig


class MomApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'mom_api'

    def ready(self):
        import mom_api.signals

