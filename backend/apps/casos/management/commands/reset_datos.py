"""
Borra TODOS los datos de dominio (instituciones, áreas, grupos, flujos,
formularios, casos, ciudadanos, historias y usuarios de demo), conservando solo
los super admin de plataforma. Sirve para dejar la base limpia y configurar un
escenario real desde cero. Funciona igual en SQLite o Postgres.

    python manage.py reset_datos          # pide confirmación
    python manage.py reset_datos --si      # sin confirmación (CI / Docker)
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import LegajoProfesional, Membresia, Usuario
from apps.casos.models import Caso
from apps.flujos.models import Conexion, Flujo, Nodo, VersionFlujo
from apps.formularios.models import Campo, Formulario
from apps.instituciones.models import Area, Grupo, Institucion, Subarea
from apps.registros.models import Ciudadano, EntradaHistoria, Estudio, HistoriaClinica, Receta


class Command(BaseCommand):
    help = "Borra todos los datos de dominio, conservando los super admin."

    def add_arguments(self, parser):
        parser.add_argument("--si", action="store_true", help="No pedir confirmación.")

    @transaction.atomic
    def handle(self, *args, **options):
        if not options["si"]:
            resp = input("Esto borra TODOS los datos (salvo super admins). ¿Seguro? [escribí 'si']: ")
            if resp.strip().lower() != "si":
                self.stdout.write(self.style.WARNING("Cancelado."))
                return

        # Orden seguro respecto de las FK (los casos protegen la versión).
        Caso.objects.all().delete()            # cascada: valores, fila, eventos
        EntradaHistoria.objects.all().delete()
        Estudio.objects.all().delete()
        Receta.objects.all().delete()
        HistoriaClinica.objects.all().delete()
        Ciudadano.objects.all().delete()
        Conexion.objects.all().delete()
        Nodo.objects.all().delete()
        VersionFlujo.objects.all().delete()
        Flujo.objects.all().delete()
        Campo.objects.all().delete()
        Formulario.objects.all().delete()
        Grupo.objects.all().delete()
        Subarea.objects.all().delete()
        Area.objects.all().delete()
        Membresia.objects.all().delete()
        LegajoProfesional.objects.filter(usuario__is_superuser=False).delete()
        borrados = Usuario.objects.filter(is_superuser=False).delete()[0]
        Institucion.objects.all().delete()

        quedan = list(Usuario.objects.values_list("email", flat=True))
        self.stdout.write(self.style.SUCCESS(
            f"Datos borrados. Usuarios no-admin eliminados: {borrados}. "
            f"Super admins conservados: {quedan or '(ninguno)'}"
        ))
