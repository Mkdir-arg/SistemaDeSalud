import json

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.financiadores.preparacion import verificar_preparacion


class Command(BaseCommand):
    help = "Verifica configuración y responsables del piloto sin cambiar datos ni activar el circuito."
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument("--institucion", type=int, required=True)
        parser.add_argument("--financiador", type=int, action="append", dest="financiadores",
                            help="ID de financiador previsto; repetible. Predeterminado: convenios activos/propuestos.")
        parser.add_argument("--usuario", type=int, action="append", dest="usuarios",
                            help="ID de responsable hospitalario; repetible. Limita las concesiones a revisar.")
        parser.add_argument("--exigir-completa", action="store_true",
                            help="Termina con error si faltan configuraciones o responsables obligatorios.")

    def handle(self, *args, **options):
        try:
            resultado = verificar_preparacion(
                institucion_id=options["institucion"], financiadores=options.get("financiadores"),
                usuarios=options.get("usuarios"),
            )
        except ValidationError as error:
            raise CommandError(" ".join(error.messages)) from None
        self.stdout.write(json.dumps(resultado, ensure_ascii=False, indent=2))
        if options["exigir_completa"] and not resultado["configuracion_completa"]:
            raise CommandError("La preparación tiene faltantes. Consultá los códigos del reporte; no se modificaron datos.")
