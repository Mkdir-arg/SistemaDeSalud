import time

from django.core.management.base import BaseCommand, CommandError

from apps.geografia.models import Catalogo
from apps.geografia.sincronizacion import corresponde, sincronizar


class Command(BaseCommand):
    help = "Poblar/actualizar el catálogo propio desde Georef. No procesa domicilios de personas."

    def add_arguments(self, parser):
        parser.add_argument("--seco", action="store_true", help="Descarga y valida sin publicar en DB.")
        parser.add_argument("--periodico", action="store_true", help="Proceso independiente: actualización semanal; reintento diario ante fallas.")

    def handle(self, *args, **options):
        if options["seco"] and options["periodico"]:
            raise CommandError("Usá --seco o --periodico, no ambos.")
        while True:
            if not options["periodico"] or corresponde(Catalogo.objects.filter(pk=1).first()):
                try:
                    resultado = sincronizar(seco=options["seco"])
                    self.stdout.write(f"Geografía: {resultado['entidades']} entidades; publicado={resultado['publicado']}.")
                except Exception:
                    if not options["periodico"]:
                        raise CommandError("Falló la sincronización; no se publicó una descarga parcial.") from None
                    self.stderr.write("Falló la sincronización; se conserva el catálogo anterior. Se reintentará más tarde.")
            if not options["periodico"]:
                return
            time.sleep(3600)
