from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = 'apps.accounts'

    def ready(self):
        from . import esquema  # noqa: F401  (registra JWT institucional en OpenAPI)
