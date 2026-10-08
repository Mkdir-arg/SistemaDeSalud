"""
La cuenta del portal del paciente para la demo (#122): Andrea Paniagua.

Ya validada y sin RENAPER. Es la misma persona que el guion comercial muestra
del lado del hospital (caso abierto de radiografía en Hospital Central) y del
financiador (Mutual del Valle, Plan Integral, MV00011). Corre como último paso
de `seed_entorno_demo`; también suelto, sobre una carga ya hecha.

    python manage.py seed_portal_demo
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.demo.claves import clave_demo
from apps.demo.entorno import exigir_entorno_de_prueba
from apps.flujos.models import Flujo
from apps.registros.models import Ciudadano

from ...demo import preparar_paciente

INSTITUCION = "Hospital Central"
# El documento sale del orden de la persona en `seed_financiadores.PERSONAS`:
# no cambia entre cargas, el id sí.
DOCUMENTO = "FIC100011"
NOMBRE, APELLIDO = "Andrea", "Paniagua"
EMAIL = "andrea.paniagua@paciente.test"
# La sala de espera donde queda: la de Cardiología de `seed_guardia`, que es la
# especialidad de su turno. La llama Laura Méndez desde un box de esa área.
SALA = "Atención cardiológica"
AUTOR_ESTUDIOS = "Laboratorio central"


class Command(BaseCommand):
    help = "Crea la cuenta validada del portal del paciente de la demo (Andrea Paniagua) y sus datos de muestra."

    def handle(self, *args, **options):
        exigir_entorno_de_prueba("seed_portal_demo")
        ciudadano = Ciudadano.objects.filter(
            institucion__nombre=INSTITUCION, documento=DOCUMENTO, nombre=NOMBRE, apellido=APELLIDO,
        ).select_related("institucion").first()
        if ciudadano is None:
            raise CommandError(
                f"No está {NOMBRE} {APELLIDO} ({DOCUMENTO}) en {INSTITUCION}. Corré antes seed_financiadores "
                "(o seed_entorno_demo, que carga todo)."
            )
        sala = Flujo.objects.filter(institucion=ciudadano.institucion, titulo=SALA).first()
        if sala is None:
            # No frena la carga: el resto del portal se puede mostrar igual.
            self.stderr.write(f"Sin el flujo «{SALA}» (seed_guardia): {NOMBRE} no queda en ninguna sala de espera.")
        with transaction.atomic():
            paciente = preparar_paciente(ciudadano, email=EMAIL, password=clave_demo(), sala=sala, autor=AUTOR_ESTUDIOS)
        turno = paciente.turno
        espera = f", y esperando en la sala de {sala.area.nombre}" if paciente.caso else ""
        self.stdout.write(self.style.SUCCESS(
            f"Portal del paciente: {EMAIL} ({NOMBRE} {APELLIDO}). Turno reservado el "
            f"{timezone.localtime(turno.inicio):%d/%m %H:%M} en «{turno.agenda.nombre}», un estudio con archivo y uno pendiente{espera}."
        ))
