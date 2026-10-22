"""Otorga o retira is_staff/is_superuser con registro (#172, decisión D-a).

El Admin ya no edita privilegios: quien opera el servidor lo hace por acá,
declarando un superusuario responsable y un motivo. El responsable es
declarativo —el comando corre con la confianza del host, no autentica a
nadie— y queda registrado en el historial del Admin (LogEntry) y en el log.
Cambiar privilegios no toca contraseña ni sesiones: el JWT vigente refleja el
nuevo estado en la próxima solicitud porque los permisos se leen del usuario.
"""
import logging

from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import Usuario
from apps.simulacion.perfiles import es_cuenta_referencia

log = logging.getLogger(__name__)
VALORES = {"si": True, "no": False}


class Command(BaseCommand):
    help = "Otorga o retira is_staff/is_superuser dejando registro del responsable y el motivo."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True, help="Cuenta a modificar.")
        parser.add_argument("--responsable", required=True, help="Email de un superusuario activo que asume el cambio.")
        parser.add_argument("--motivo", required=True)
        parser.add_argument("--staff", choices=VALORES)
        parser.add_argument("--superusuario", choices=VALORES)

    def handle(self, *args, email, responsable, motivo, staff, superusuario, **opciones):
        motivo = motivo.strip()
        if not motivo:
            raise CommandError("Indicá el motivo del cambio.")
        if staff is None and superusuario is None:
            raise CommandError("Indicá --staff y/o --superusuario.")
        cambios = {}
        if staff is not None:
            cambios["is_staff"] = VALORES[staff]
        if superusuario is not None:
            cambios["is_superuser"] = VALORES[superusuario]
            # Un superusuario sin acceso al Admin no tiene sentido operativo.
            if cambios["is_superuser"]:
                cambios.setdefault("is_staff", True)

        with transaction.atomic():
            objetivo = Usuario.objects.select_for_update().filter(email__iexact=email).first()
            autor = Usuario.objects.filter(email__iexact=responsable, is_active=True, is_superuser=True).first()
            if objetivo is None:
                raise CommandError("No existe esa cuenta.")
            if autor is None:
                raise CommandError("El responsable debe ser un superusuario activo.")
            if es_cuenta_referencia(objetivo):
                raise CommandError("Las cuentas de referencia no reciben privilegios.")
            if autor.pk == objetivo.pk and cambios.get("is_superuser") is False:
                raise CommandError("Un responsable no retira su propio superusuario.")
            anteriores = {campo: getattr(objetivo, campo) for campo in cambios}
            if anteriores == cambios:
                self.stdout.write("Sin cambios.")
                return
            for campo, valor in cambios.items():
                setattr(objetivo, campo, valor)
            objetivo.save(update_fields=list(cambios))
            detalle = ", ".join(f"{c}: {anteriores[c]}→{v}" for c, v in cambios.items())
            LogEntry.objects.create(
                user=autor,
                content_type=ContentType.objects.get_for_model(Usuario),
                object_id=str(objetivo.pk),
                object_repr=str(objetivo)[:200],
                action_flag=CHANGE,
                change_message=f"asignar_privilegios: {detalle}. Motivo: {motivo}",
            )
        log.warning("privilegios de cuenta %s modificados por %s: %s", objetivo.pk, autor.pk, detalle)
        self.stdout.write(self.style.SUCCESS(f"Privilegios actualizados: {detalle}."))
