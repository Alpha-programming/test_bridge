from django.apps import AppConfig



class IeltsConfig(AppConfig):
    name = 'ielts'

    def ready(self):
        import ielts.signals