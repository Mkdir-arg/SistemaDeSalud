"""Historial de accesos a datos clínicos, para que la auditoría tenga qué revisar.

Qué carga
---------
El registro de accesos se escribe cuando alguien consulta datos clínicos por la
API. Los `seed_*` recorren el motor sin pasar por ahí, así que después de una
carga el registro está vacío, y es la única pantalla del auditor estatal.

Este comando reconstruye lo que esa operación habría dejado en los últimos
`--dias` días:

- **Consultas de la historia** por quienes trabajaron cada caso, en el momento en
  que lo trabajaron. Salen de la trazabilidad de los casos, no del azar.
- **Búsquedas en el padrón** de admisión.
- **Exportaciones** del padrón por la administración.
- **Consultas de un financiador** sobre sus autorizaciones.
- **Dos accesos que merecen una pregunta:** un profesional de otra área que abre
  la historia de un paciente de guardia de madrugada, y una exportación grande
  fuera de horario. Son lo que el registro existe para poder mostrar.

Requisitos
----------
- `ENTORNO` distinto de `produccion`.
- Casos ya cargados (`seed_volumen`, `seed_los_aromos`, `seed_financiadores`).

Agrega sobre lo que haya: correrlo dos veces duplica el historial.
"""
import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Membresia, Usuario
from apps.auditoria.models import AccesoClinico
from apps.casos.models import EventoCaso
from apps.demo.entorno import exigir_entorno_de_prueba
from apps.instituciones.models import Institucion
from apps.registros.models import Ciudadano

# De cada evento con autor en la ventana, cuántos terminan en una consulta de la
# historia. Uno de cada tres alcanza para que cada caso tenga lectores sin que el
# registro sea una copia de la trazabilidad.
PROPORCION_DE_LECTURA = 3


class Command(BaseCommand):
    help = "Reconstruye el historial de accesos a datos clínicos de los últimos días."

    def add_arguments(self, parser):
        parser.add_argument("--dias", type=int, default=45, help="Ventana hacia atrás (por defecto 45).")
        parser.add_argument("--semilla", type=int, default=2026)

    @transaction.atomic
    def handle(self, *args, **opciones):
        exigir_entorno_de_prueba("seed_accesos")
        self.az = random.Random(opciones["semilla"])
        self.ahora = timezone.now()
        desde = self.ahora - timedelta(days=opciones["dias"])
        self.creados = {tipo: 0 for tipo in AccesoClinico.Tipo.values}

        self._lecturas_de_historia(desde)
        for inst in Institucion.objects.filter(ciudadanos__isnull=False).distinct().order_by("pk"):
            self._busquedas_y_exportaciones(inst, desde)
        self._consultas_de_financiadores(desde)
        self._accesos_para_preguntar()

        self.stdout.write(self.style.SUCCESS(
            "Accesos clínicos: " + " · ".join(f"{cantidad} {tipo}" for tipo, cantidad in self.creados.items())
        ))

    def _anotar(self, momento, usuario, tipo, recurso, ciudadano=None, institucion=None,
                objeto_id="", detalle="", resultados=0):
        # `momento` es auto_now_add: se refecha después, porque al crear Django
        # siempre escribe la hora real.
        acceso = AccesoClinico.objects.create(
            usuario=usuario, ciudadano=ciudadano,
            institucion=institucion or (ciudadano.institucion if ciudadano else None),
            tipo=tipo, recurso=recurso, objeto_id=str(objeto_id)[:40], detalle=detalle[:300],
            resultados=resultados, ip=f"10.20.{self.az.randint(1, 30)}.{self.az.randint(2, 250)}",
        )
        AccesoClinico.objects.filter(pk=acceso.pk).update(momento=min(momento, self.ahora))
        self.creados[tipo] += 1

    def _lecturas_de_historia(self, desde):
        eventos = (EventoCaso.objects
                   .filter(fecha__gte=desde, autor__isnull=False, caso__ciudadano__isnull=False)
                   .select_related("caso__ciudadano__institucion", "autor")
                   .order_by("pk"))
        for indice, evento in enumerate(eventos.iterator()):
            if indice % PROPORCION_DE_LECTURA:
                continue
            ciudadano = evento.caso.ciudadano
            self._anotar(
                evento.fecha - timedelta(minutes=self.az.randint(1, 6)), evento.autor,
                AccesoClinico.Tipo.DETALLE, "historiaclinica", ciudadano=ciudadano,
                objeto_id=ciudadano.pk,
            )

    def _busquedas_y_exportaciones(self, inst, desde):
        admision = list(Usuario.objects.filter(
            membresias__institucion=inst, membresias__rol=Membresia.Rol.ADMINISTRATIVO, is_active=True,
        ).distinct().order_by("pk"))
        admin = Usuario.objects.filter(
            membresias__institucion=inst, membresias__rol=Membresia.Rol.ADMIN_INSTITUCION,
        ).order_by("pk").first()
        padron = list(Ciudadano.objects.filter(institucion=inst).order_by("pk"))
        if not padron:
            return
        dias = (self.ahora - desde).days
        for _ in range(min(len(padron), 4 * dias) if admision else 0):
            persona = self.az.choice(padron)
            # Horario de mostrador, de 7 a 19. Se fija la hora del día: sumar horas
            # a `desde` las corría según la hora de la carga y llenaba la madrugada,
            # que es justo donde tiene que destacar el acceso de `_accesos_para_preguntar`.
            dia = timezone.localtime(desde + timedelta(days=self.az.randint(0, dias - 1)))
            momento = dia.replace(hour=self.az.randint(7, 19), minute=self.az.randint(0, 59))
            criterio = self.az.choice([f"search={persona.apellido}", f"documento={persona.documento}"])
            self._anotar(momento, self.az.choice(admision), AccesoClinico.Tipo.LISTADO, "ciudadano",
                         institucion=inst, detalle=criterio, resultados=self.az.randint(1, 3))
        if admin:
            for semanas in (1, 4):
                momento = self.ahora - timedelta(weeks=semanas, hours=self.az.randint(1, 5))
                self._anotar(momento, admin, AccesoClinico.Tipo.EXPORTACION, "ciudadano",
                             institucion=inst, detalle="formato=csv", resultados=len(padron))

    def _consultas_de_financiadores(self, desde):
        from apps.financiadores.models import MembresiaFinanciador, SolicitudAutorizacion

        for solicitud in (SolicitudAutorizacion.objects.filter(creado__gte=desde)
                          .select_related("ciudadano", "institucion").order_by("pk")):
            lector = (MembresiaFinanciador.objects
                      .filter(financiador_id=solicitud.financiador_id, activo=True)
                      .order_by("pk").values_list("usuario", flat=True).first())
            if not lector:
                continue
            self._anotar(
                solicitud.creado + timedelta(minutes=self.az.randint(5, 40)), Usuario.objects.get(pk=lector),
                AccesoClinico.Tipo.FINANCIADOR, "solicitudautorizacion", ciudadano=solicitud.ciudadano,
                institucion=solicitud.institucion, objeto_id=solicitud.pk,
                detalle=f"solicitud={solicitud.pk}", resultados=1,
            )

    def _accesos_para_preguntar(self):
        # Salud mental abriendo la historia de un paciente de guardia a las 3 de
        # la madrugada: puede tener una explicación, pero es la que hay que pedir.
        curioso = Usuario.objects.filter(email="sm.med@hospital.gob.ar").first()
        guardia = (EventoCaso.objects.filter(caso__area_actual__nombre="Guardia", caso__ciudadano__isnull=False)
                   .select_related("caso__ciudadano__institucion").order_by("-fecha").first())
        if curioso and guardia:
            madrugada = timezone.localtime(self.ahora - timedelta(days=2)).replace(hour=3, minute=12)
            self._anotar(madrugada, curioso, AccesoClinico.Tipo.DETALLE, "historiaclinica",
                         ciudadano=guardia.caso.ciudadano, objeto_id=guardia.caso.ciudadano.pk)
        admin = Usuario.objects.filter(email="admin.central@hospital.gob.ar").first()
        central = Institucion.objects.filter(nombre="Hospital Central").first()
        if admin and central:
            domingo = timezone.localtime(self.ahora - timedelta(days=(timezone.localtime(self.ahora).weekday() + 1) % 7 or 7))
            self._anotar(domingo.replace(hour=23, minute=48), admin, AccesoClinico.Tipo.EXPORTACION,
                         "historiaclinica", institucion=central, detalle="formato=csv",
                         resultados=Ciudadano.objects.filter(institucion=central).count())
