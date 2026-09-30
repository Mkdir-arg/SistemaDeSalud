from django.apps import AppConfig


class SimulacionConfig(AppConfig):
    name = "apps.simulacion"
    verbose_name = "simulación de perfiles"

    def ready(self):
        # La autoría se corrige al guardar, en cualquier modelo: ver `contexto.py`.
        from django.db.models.signals import pre_save

        from . import esquema  # noqa: F401  (registra el encabezado en OpenAPI)
        from .contexto import atribuir_autoria

        pre_save.connect(atribuir_autoria, dispatch_uid="simulacion.atribuir_autoria")
