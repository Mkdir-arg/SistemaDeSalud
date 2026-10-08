"""
Escenario mínimo del e2e de la app del paciente (#122), sobre `seed_guardia`.

No reemplaza a `seed_portal_demo`: usa la misma `preparar_paciente`, pero sobre
una persona propia y no sobre los doce meses de `seed_entorno_demo`, que tarda
minutos y exige PostgreSQL. Corre en SQLite.

Además de la cuenta, el turno a más de 24 horas y los estudios, deja:
- un turno dentro de las próximas 24 horas, que no se puede cancelar;
- una afiliación vinculada a la persona (cobertura «confirmada»);
- un caso de cardiología en la fila de espera, para llamarlo desde un box.

Escribe en `--salida` (JSON) lo que el e2e necesita para operar del lado del
hospital: ids del caso, del box y del turno, y el email de quien llama.

    python manage.py seed_guardia
    python manage.py seed_portal_e2e --salida /tmp/portal-e2e.json
"""
import json
from datetime import date, time, timedelta
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Usuario
from apps.agenda import motor as agenda_motor
from apps.agenda.models import Agenda, Disponibilidad, Turno
from apps.demo.claves import clave_demo
from apps.demo.entorno import exigir_entorno_de_prueba
from apps.financiadores.models import Afiliado, Financiador, Plan, VinculoCiudadano
from apps.flujos.models import Flujo
from apps.instituciones.models import Box, Institucion
from apps.registros.models import Ciudadano

from ...demo import preparar_paciente
from .seed_portal_demo import APELLIDO, AUTOR_ESTUDIOS, INSTITUCION, NOMBRE, SALA

# Otro documento y otro email que los de `seed_portal_demo`, a propósito: con el
# mismo documento validado en dos cuentas, R2 rechaza la segunda carga.
DOCUMENTO = "FIC199001"
EMAIL = "paciente.e2e@paciente.test"
LLAMA = "cardio.med@hospital.gob.ar"


class Command(BaseCommand):
    help = "Escenario mínimo del e2e del portal del paciente (requiere seed_guardia)."

    def add_arguments(self, parser):
        parser.add_argument("--salida", help="Archivo JSON con los ids que usa el e2e.")

    def handle(self, *args, **options):
        exigir_entorno_de_prueba("seed_portal_e2e")
        # Se controla acá y no con `required`: la guarda de producción va primero.
        if not options["salida"]:
            raise CommandError("Falta --salida: el archivo JSON donde el e2e lee los ids.")
        inst = Institucion.objects.filter(nombre=INSTITUCION).first()
        flujo = Flujo.objects.filter(institucion=inst, titulo=SALA).first() if inst else None
        if flujo is None:
            raise CommandError("Falta la carga de guardia: corré antes seed_guardia.")
        with transaction.atomic():
            datos = self._cargar(inst, flujo)
        Path(options["salida"]).write_text(json.dumps(datos, indent=2), encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"Escenario del portal listo: {EMAIL}"))

    def _cargar(self, inst, flujo):
        admin = Usuario.objects.get(email="admin@salud.local")
        ciudadano, _ = Ciudadano.objects.update_or_create(
            institucion=inst, documento=DOCUMENTO,
            defaults={"nombre": NOMBRE, "apellido": APELLIDO, "codigo": "E2E-0001",
                      "fecha_nacimiento": date(1983, 11, 12)},
        )

        financiador, _ = Financiador.objects.get_or_create(nombre="Mutual del Valle", defaults={"tipo": "mutual"})
        plan, _ = Plan.objects.get_or_create(financiador=financiador, codigo="MV-INT", defaults={"nombre": "Plan Integral"})
        afiliado, _ = Afiliado.objects.get_or_create(
            financiador=financiador, documento=ciudadano.documento,
            defaults={"numero": "MV00011", "nombre": f"{NOMBRE} {APELLIDO}", "plan": plan,
                      "desde": timezone.localdate() - timedelta(days=200)},
        )
        VinculoCiudadano.objects.get_or_create(afiliado=afiliado, ciudadano=ciudadano, defaults={"verificado_por": admin})

        cardio = Agenda.objects.get(institucion=inst, nombre="Dra. Méndez · Cardiología")
        paciente = preparar_paciente(ciudadano, email=EMAIL, password=clave_demo(), agendas=[cardio], sala=flujo, autor=AUTOR_ESTUDIOS)

        return {
            "email": EMAIL,
            "turno_cancelable": paciente.turno.pk,
            "turno_cercano": self._turno_cercano(inst, ciudadano, cardio).pk,
            "estudio": paciente.estudio.pk,
            "llama": LLAMA,
            "caso": paciente.caso.pk,
            "box": Box.objects.filter(area=flujo.area, nombre="Box 1").values_list("pk", flat=True).get(),
            "institucion": inst.pk,
        }

    def _turno_cercano(self, inst, ciudadano, cardio):
        """Un turno en las próximas horas: R3 no deja cancelarlo desde el portal.

        Va en una agenda que atiende todo el día, todos los días: la del seed
        de guardia puede no tener lugar en las próximas 24 horas.
        """
        agenda, creada = Agenda.objects.get_or_create(
            institucion=inst, nombre="E2E · Clínica de día",
            defaults={"area": cardio.area, "profesional": cardio.profesional, "duracion_min": 30},
        )
        if creada:
            Disponibilidad.objects.bulk_create(
                Disponibilidad(agenda=agenda, dia_semana=d, desde=time(0, 0), hasta=time(23, 30)) for d in range(7)
            )
        existente = Turno.objects.filter(
            agenda=agenda, ciudadano=ciudadano, estado=Turno.Estado.RESERVADO,
            inicio__gt=timezone.now(), inicio__lt=timezone.now() + timedelta(hours=20),
        ).first()
        if existente:
            return existente
        # El de una corrida anterior que ya pasó ocupa el día («ya tiene un turno
        # ese día en esta agenda»). La agenda es sólo del e2e: se cancela.
        for viejo in Turno.objects.filter(agenda=agenda, ciudadano=ciudadano, estado=Turno.Estado.RESERVADO, inicio__lte=timezone.now()):
            agenda_motor.cancelar(viejo, motivo="Escenario del e2e rehecho")
        libre = agenda_motor.proximos_libres(agenda, desde=timezone.now() + timedelta(hours=2), dias=2, cuantos=1)[0]
        return agenda_motor.reservar(agenda, ciudadano, libre["inicio"], origen=Turno.Origen.MOSTRADOR)
