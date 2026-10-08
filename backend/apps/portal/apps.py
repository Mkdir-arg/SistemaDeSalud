from django.apps import AppConfig


class PortalConfig(AppConfig):
    name = "apps.portal"
    verbose_name = "portal del paciente"

    def ready(self):
        from . import esquema  # noqa: F401  (registra el token del portal en OpenAPI)

        _avisar_si_falta_el_correo()


def _avisar_si_falta_el_correo():
    """En producción sin servidor de correo nadie confirma su cuenta.

    Es un aviso y no un error al arrancar: el resto del sistema anda sin correo,
    y el portal responde igual (R3). Sin el aviso, la falla sólo aparece como
    una línea por cada correo que no salió.
    """
    import logging

    from django.conf import settings

    smtp = settings.EMAIL_BACKEND.endswith("smtp.EmailBackend")
    if settings.ENTORNO == "produccion" and smtp and settings.EMAIL_HOST in ("", "localhost"):
        logging.getLogger("apps.portal").warning(
            "portal: EMAIL_HOST no está configurado; los correos de verificación y recupero no van a salir"
        )
