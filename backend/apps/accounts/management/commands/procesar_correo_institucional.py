"""Worker explícito de outbox; ejecutar bajo supervisión, nunca al importar."""
import json
import time

from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.accounts.correo_outbox import estado_outbox, politica, procesar_siguiente, purgar_payloads
from apps.accounts.credenciales import exigir_configuracion_correo
from apps.auditoria.latidos import latir

SERVICIO = "correo_institucional"


class Command(BaseCommand):
    help = "Procesa la outbox institucional durable; estados agregados y purga manual sin datos personales."

    def add_arguments(self, parser):
        parser.add_argument("--una-pasada", action="store_true")
        parser.add_argument("--max-trabajos", type=int, default=100)
        parser.add_argument("--estado", action="store_true")
        parser.add_argument("--purgar-antes", help="Fecha ISO con zona; limpia payloads terminales, no filas ni backups.")

    def handle(self, *args, **options):
        if options["max_trabajos"] <= 0:
            raise CommandError("--max-trabajos debe ser positivo.")
        if sum(bool(options[clave]) for clave in ("estado", "purgar_antes", "una_pasada")) > 1:
            raise CommandError("Elegí una sola operación.")
        try:
            politica()
            if options["purgar_antes"]:
                fecha = parse_datetime(options["purgar_antes"])
                if fecha is None or timezone.is_naive(fecha):
                    raise CommandError("La purga requiere una fecha ISO con zona horaria.")
                cantidad = purgar_payloads(fecha, limite=options["max_trabajos"])
                self.stdout.write(json.dumps({"payloads_purgados": cantidad}))
                return
            if options["estado"]:
                self.stdout.write(json.dumps(estado_outbox()))
                return
            exigir_configuracion_correo()
        except CommandError:
            raise
        except Exception:
            raise CommandError("Correo institucional sin configuración válida o base no disponible.") from None

        try:
            while True:
                close_old_connections()
                cantidad = 0
                while cantidad < options["max_trabajos"] and procesar_siguiente():
                    cantidad += 1
                    latir(SERVICIO)
                latir(SERVICIO)
                if options["una_pasada"]:
                    estado = estado_outbox()
                    self.stdout.write(json.dumps(estado))
                    if estado["error"] or estado["plazos_vencidos"] or estado["reservas_vencidas"]:
                        raise CommandError("Hay correos con error definitivo o plazo/reserva vencidos; revisar el estado agregado.")
                    return
                time.sleep(politica()["espera_segundos"])
        except KeyboardInterrupt:
            return
        except CommandError:
            raise
        except Exception:
            # No dejar que el runner imprima parámetros SQL/payload/proveedor.
            raise CommandError("El worker de correo se detuvo por un fallo operativo; revisar su estado agregado.") from None
