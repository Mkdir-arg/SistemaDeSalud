"""Más efectores en la red, para que el tablero de plataforma muestre una red.

Qué carga
---------
El tablero de instituciones es lo primero que ve la autoridad de plataforma. Con
los dos hospitales de `seed_guardia` y `seed_red` mostraba una fila con datos,
otra en cero y ninguna alerta. Este comando suma a la Región Sanitaria VI:

- **Hospital Zonal Sur:** lleno. Sus camas superan el 90 % y el tablero lo
  marca en «Requiere atención».
- **Clínica San Martín:** mediana, con ocupación normal.
- **Centro de Salud Barrio Norte:** atención primaria, sin camas.
- **Hospital Regional Lomas del Este:** en puesta en marcha hace 45 días, con
  áreas y su administrador, pero sin flujos ni agendas. Es la otra alerta del
  tablero: más de 30 días en alta.

Y le da a Villa Real lo que le faltaba para no verse en cero: una fila de
demanda espontánea y pacientes internados.

Cada efector activo tiene 30 días de atenciones de fila, pacientes esperando
ahora e internados en este momento. Todo se recorre con el motor real, como en
`seed_volumen`, con el reloj puesto en el momento de cada paso: las esperas, los
tiempos de atención y las historias clínicas salen de la operación y no de
números escritos a mano.

Requisitos
----------
- `ENTORNO` distinto de `produccion`.
- `seed_red` ya cargado: la región y Villa Real.

No es idempotente: se carga una vez por `seed_entorno_demo`, que vacía la base.

    python manage.py seed_efectores
"""
import random
from datetime import timedelta
from unittest.mock import patch

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import LegajoProfesional, Membresia, Usuario
from apps.casos import motor
from apps.casos.management.commands.seed_volumen import APELLIDOS, DIAGNOSTICOS, MOTIVOS, NOMBRES_F, NOMBRES_M
from apps.casos.models import Caso, Notificacion
from apps.demo.claves import clave_demo
from apps.demo.entorno import exigir_entorno_de_prueba
from apps.flujos.models import Conexion, Flujo, Nodo, VersionFlujo
from apps.instituciones.models import Area, Box, Cama, Grupo, Institucion, Subarea
from apps.red.models import Red
from apps.registros.models import Ciudadano, HistoriaClinica

R = Membresia.Rol
NOMBRE_RED = "Región Sanitaria VI"
VILLA_REAL = "Hospital Municipal de Villa Real"
DIAS = 30
# Los que cada efector ya atendió hoy, como mínimo.
ATENDIDOS_HOY = 3

# Cada efector activo: cuánta gente atiende por día, cuántos boxes tiene, sus
# camas y cuántas están ocupadas ahora, y los que esperan en la sala.
EFECTORES = [
    {
        "nombre": "Hospital Zonal Sur", "tipo": "Hospital general de agudos", "prefijo": "zonal",
        "lat": -34.8105, "lon": -58.3902, "boxes": 4, "por_dia": (16, 24), "esperando": 7,
        "camas": 24, "internados": 23,
        "personal": [("Graciela", "Ibarra", R.MEDICO), ("Hernán", "Toledo", R.ADMINISTRATIVO),
                     ("Patricia", "Luque", R.JEFE_AREA)],
    },
    {
        "nombre": "Clínica San Martín", "tipo": "Clínica", "prefijo": "sanmartin",
        "lat": -34.7231, "lon": -58.2614, "boxes": 3, "por_dia": (8, 13), "esperando": 4,
        "camas": 12, "internados": 7,
        "personal": [("Ramiro", "Ocampo", R.MEDICO), ("Liliana", "Sáez", R.ADMINISTRATIVO)],
    },
    {
        "nombre": "Centro de Salud Barrio Norte", "tipo": "Centro de atención primaria", "prefijo": "norte",
        "lat": -34.7402, "lon": -58.4123, "boxes": 2, "por_dia": (9, 15), "esperando": 5,
        "camas": 0, "internados": 0,
        "personal": [("Mónica", "Arce", R.MEDICO), ("Julián", "Paz", R.ADMINISTRATIVO)],
    },
]
EN_ALTA = {
    "nombre": "Hospital Regional Lomas del Este", "tipo": "Hospital general", "prefijo": "lomas",
    "lat": -34.8350, "lon": -58.2210, "dias_en_alta": 45,
    "areas": ["Guardia", "Internación", "Consultorios externos"],
    "admin": ("Norberto", "Achával"),
}
# Villa Real ya existe (`seed_red`): sólo se le suma operación.
VILLA = {"prefijo": "villa", "boxes": 1, "por_dia": (5, 9), "esperando": 3, "internados": 4}


class Reloj:
    """El reloj del motor mientras se recorre un caso: marca la hora de cada paso.

    Avanza un milisegundo por lectura para que dos registros del mismo paso no
    empaten. Puede volver atrás entre un caso y otro: los recorridos se hacen
    en orden de ingreso y dos pacientes se superponen en la sala.
    """

    def __init__(self):
        self.t = timezone.now()

    def __call__(self):
        self.t += timedelta(milliseconds=1)
        return self.t


class Command(BaseCommand):
    help = "Suma efectores a la red, con operación de los últimos 30 días, para el tablero de plataforma."

    def add_arguments(self, parser):
        parser.add_argument("--semilla", type=int, default=2026)

    @transaction.atomic
    def handle(self, *args, **opciones):
        exigir_entorno_de_prueba("seed_efectores")
        self.azar = random.Random(opciones["semilla"])
        red = Red.objects.filter(nombre=NOMBRE_RED).first()
        villa = Institucion.objects.filter(nombre=VILLA_REAL).first()
        if red is None or villa is None:
            raise CommandError("Falta la red de Villa Real. Corré `seed_red` primero.")

        # Hora local: los turnos de la guardia se cuentan de 7 a 23 en Argentina.
        self.ahora = timezone.localtime()
        self.reloj = Reloj()
        resumen = []
        for datos in EFECTORES:
            inst = Institucion.objects.create(
                nombre=datos["nombre"], tipo=datos["tipo"], latitud=datos["lat"], longitud=datos["lon"],
            )
            red.instituciones.add(inst)
            resumen.append(self._operar(inst, datos, self._estructura(inst, datos)))
        resumen.append(self._operar(villa, VILLA, self._estructura_villa(villa)))
        resumen.append(self._en_alta(red))

        self.stdout.write(self.style.SUCCESS(f"\nEfectores de «{NOMBRE_RED}»:"))
        for linea in resumen:
            self.stdout.write(f"  {linea}")

    # ----------------------------------------------------------------- #
    # Estructura
    # ----------------------------------------------------------------- #
    def _persona(self, inst, prefijo, nombre, apellido, rol, areas):
        sufijo = {R.MEDICO: "med", R.ADMINISTRATIVO: "adm", R.JEFE_AREA: "jefe", R.ADMIN_INSTITUCION: "admin"}[rol]
        usuario = Usuario.objects.create_user(f"{prefijo}.{sufijo}@hospital.gob.ar", clave_demo(),
                                              nombre=nombre, apellido=apellido)
        membresia = Membresia.objects.create(usuario=usuario, institucion=inst, rol=rol)
        membresia.areas.set(areas)
        if rol == R.MEDICO:
            # La atención se firma con matrícula: sin legajo, el motor no deja firmar.
            LegajoProfesional.objects.create(usuario=usuario, especialidad="Clínica médica",
                                             matricula=f"MP {self.azar.randint(10000, 99999)}")
        return usuario

    def _estructura(self, inst, datos):
        guardia = Area.objects.create(institucion=inst, nombre="Guardia" if datos["camas"] else "Demanda espontánea")
        areas = [guardia]
        internacion = None
        if datos["camas"]:
            internacion = Area.objects.create(institucion=inst, nombre="Internación")
            areas.append(internacion)
        personal = {rol: self._persona(inst, datos["prefijo"], nombre, apellido, rol, areas)
                    for nombre, apellido, rol in datos["personal"]}
        boxes = [Box.objects.create(area=guardia, nombre=f"Consultorio {i}") for i in range(1, datos["boxes"] + 1)]
        grupo = Grupo.objects.create(area=guardia, nombre=f"Equipo de {guardia.nombre.lower()}")
        grupo.miembros.set(personal.values())
        fila = self._flujo_de_fila(inst, guardia, grupo)
        cama = None
        if internacion:
            sala = Subarea.objects.create(area=internacion, nombre="Clínica médica")
            for i in range(1, datos["camas"] + 1):
                Cama.objects.create(area=internacion, subarea=sala, nombre=f"{100 + i}")
            g_int = Grupo.objects.create(area=internacion, nombre="Equipo de internación")
            g_int.miembros.set(personal.values())
            cama = self._flujo_de_internacion(inst, internacion, sala, g_int)
        return {"fila": fila, "cama": cama, "boxes": boxes, "medico": personal[R.MEDICO],
                "internacion": internacion}

    def _estructura_villa(self, villa):
        guardia = Area.objects.get(institucion=villa, nombre="Guardia")
        internacion = Area.objects.get(institucion=villa, nombre="Internación")
        grupo = Grupo.objects.get(area=guardia, nombre="Guardia de Villa Real")
        medico = Usuario.objects.get(email="villa.med@hospital.gob.ar")
        # El flujo de guardia de `seed_red` no tiene fila: sirve para derivar.
        # La consulta de demanda espontánea es la que pasa por la sala.
        fila = self._flujo_de_fila(villa, guardia, grupo, titulo="Demanda espontánea")
        if not hasattr(medico, "legajo"):
            LegajoProfesional.objects.create(usuario=medico, especialidad="Medicina general", matricula="MP 40718")
        Membresia.objects.get(usuario=medico, institucion=villa, rol=R.MEDICO).areas.add(internacion)
        g_int, _ = Grupo.objects.get_or_create(area=internacion, nombre="Internación de Villa Real")
        g_int.miembros.set([medico, Usuario.objects.get(email="villa.jefe@hospital.gob.ar")])
        sala = Subarea.objects.get(area=internacion, nombre="Sala general")
        cama = self._flujo_de_internacion(villa, internacion, sala, g_int)
        return {"fila": fila, "cama": cama, "boxes": list(Box.objects.filter(area=guardia)),
                "medico": medico, "internacion": internacion}

    def _publicar(self, flujo, nodos, conexiones, **version):
        v = VersionFlujo.objects.create(flujo=flujo, numero=1, **version)
        creados = [Nodo.objects.create(version=v, tipo=tipo, titulo=titulo, x=80 + 240 * i, y=180, config=config or {})
                   for i, (tipo, titulo, config) in enumerate(nodos)]
        for origen, destino in conexiones:
            Conexion.objects.create(version=v, origen=creados[origen], destino=creados[destino])
        if not motor.puede_publicar(v):
            raise CommandError(f"El flujo «{flujo.titulo}» de {flujo.institucion} no se pudo publicar.")
        v.estado = VersionFlujo.Estado.PUBLICADA
        v.save()
        return v, creados

    def _flujo_de_fila(self, inst, area, grupo, titulo="Atención en guardia"):
        flujo = Flujo.objects.create(institucion=inst, area=area, titulo=titulo,
                                     descripcion="Ingreso, sala de espera y atención en consultorio.")
        v, nodos = self._publicar(flujo, [
            (Nodo.Tipo.INICIO, "Ingreso", None),
            (Nodo.Tipo.ATENCION, "Atención en consultorio", {"con_fila": True}),
            (Nodo.Tipo.FIN, "Alta", None),
        ], [(0, 1), (1, 2)], tipo_circuito=VersionFlujo.TipoCircuito.GUARDIA)
        nodos[1].grupos.set([grupo])
        return v

    def _flujo_de_internacion(self, inst, area, sala, grupo):
        flujo = Flujo.objects.create(institucion=inst, area=area, titulo="Internación",
                                     descripcion="Asignación de cama, evolución y alta.")
        v, nodos = self._publicar(flujo, [
            (Nodo.Tipo.INICIO, "Ingreso a internación", None),
            (Nodo.Tipo.CAMA, "Asignar cama", {"sector": sala.id}),
            (Nodo.Tipo.ATENCION, "Evolución médica", None),
            (Nodo.Tipo.FIN, "Alta médica", None),
        ], [(0, 1), (1, 2), (2, 3)])
        nodos[1].grupos.set([grupo])
        nodos[2].grupos.set([grupo])
        return v

    # ----------------------------------------------------------------- #
    # Operación
    # ----------------------------------------------------------------- #
    def _pacientes(self, inst, cantidad):
        hoy = self.ahora.date()
        pacientes, usados = [], set()
        for i in range(cantidad):
            # Del rango de DNI que todavía no se asignó a nadie (ver `seed_volumen`),
            # sin repetir: la institución no admite dos veces el mismo documento.
            documento = str(self.azar.randint(90_000_000, 99_999_999))
            while documento in usados:
                documento = str(self.azar.randint(90_000_000, 99_999_999))
            usados.add(documento)
            mujer = self.azar.random() < 0.52
            edad = self.azar.randint(1, 90)
            ciudadano = Ciudadano.objects.create(
                institucion=inst, codigo=f"CIU-{i + 1:04d}",
                nombre=self.azar.choice(NOMBRES_F if mujer else NOMBRES_M), apellido=self.azar.choice(APELLIDOS),
                documento=documento,
                fecha_nacimiento=hoy - timedelta(days=edad * 365 + self.azar.randint(0, 364)),
            )
            HistoriaClinica.objects.create(ciudadano=ciudadano)
            pacientes.append(ciudadano)
        return pacientes

    def _en(self, instante):
        """Pone el reloj del motor en `instante` (nunca después de ahora)."""
        self.reloj.t = min(instante, self.ahora)

    def _operar(self, inst, datos, e):
        # Lo anterior a la hora en punto previa ya se atendió; lo posterior está
        # en la sala. Se corta en la hora y no en «ahora menos una hora» para que
        # dos cargas con la misma ancla dejen los mismos casos: entre una y otra
        # el reloj corre unos segundos distinto.
        corte = self.ahora.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
        historicos = []
        for dia in range(DIAS, -1, -1):
            fecha = timezone.localtime(self.ahora - timedelta(days=dia))
            medianoche = fecha.replace(hour=0, minute=0, second=0, microsecond=0)
            for _ in range(self.azar.randint(*datos["por_dia"])):
                # La guardia atiende las 24 horas, con menos gente de noche. La
                # noche importa: la demo se carga anclada a las 8 y lo atendido
                # «hoy» es lo de la madrugada.
                hora = self.azar.choices(range(24), weights=[1] * 7 + [3] * 16 + [1])[0]
                ingreso = medianoche + timedelta(hours=hora, minutes=self.azar.randint(0, 59))
                if ingreso < corte:
                    historicos.append(ingreso)
        # «Atendidos hoy» y la espera del día no pueden quedar en cero por azar
        # en un efector chico: de noche llega poca gente.
        hoy = self.ahora.replace(hour=0, minute=0, second=0, microsecond=0)
        faltan = ATENDIDOS_HOY - sum(ingreso >= hoy for ingreso in historicos)
        minutos = int((corte - hoy).total_seconds() // 60)
        if faltan > 0 and minutos > 0:
            historicos += [hoy + timedelta(minutes=self.azar.randint(0, minutos - 1)) for _ in range(faltan)]
        historicos.sort()
        pacientes = self._pacientes(inst, max(40, len(historicos) // 6) + datos["esperando"] + datos["internados"])
        en_sala = pacientes[:datos["esperando"]]
        internados = pacientes[datos["esperando"]:datos["esperando"] + datos["internados"]]
        consultantes = pacientes[datos["esperando"] + datos["internados"]:]

        with patch("django.utils.timezone.now", side_effect=self.reloj):
            # Un paciente no vuelve a la guardia el mismo día: si dos visitas se
            # superponen, la historia firma la segunda antes que la primera y la
            # cadena de sellos se rompe.
            ultima_visita = {}
            atendidos = 0
            for ingreso in historicos:
                libres = [p for p in consultantes if ultima_visita.get(p.pk, ingreso - timedelta(days=2))
                          < ingreso - timedelta(days=1)]
                if not libres:
                    continue
                paciente = self.azar.choice(libres)
                ultima_visita[paciente.pk] = ingreso
                self._atender(inst, e, paciente, ingreso)
                atendidos += 1
            for paciente in en_sala:
                self._en(self.ahora - timedelta(minutes=self.azar.randint(5, 110)))
                self._ingresar(inst, e["fila"], paciente)
            for paciente in internados:
                self._internar(inst, e, paciente)

        # Como en `seed_volumen._sellar_notificaciones`: lo viejo ya se leyó.
        Notificacion.objects.filter(caso__institucion=inst, creada__lt=self.ahora - timedelta(days=2)).update(leida=True)
        camas = f" · {len(internados)} de {e['internacion'].camas.count()} camas ocupadas" if e["internacion"] else ""
        return f"{inst.nombre}: {atendidos} atenciones en {DIAS} días · {len(en_sala)} esperando{camas}"

    def _ingresar(self, inst, version, paciente):
        caso = Caso.objects.create(institucion=inst, version=version, ciudadano=paciente,
                                   area_actual=version.flujo.area)
        motor.iniciar(caso)
        caso.refresh_from_db()
        return caso

    def _atender(self, inst, e, paciente, ingreso):
        self._en(ingreso)
        caso = self._ingresar(inst, e["fila"], paciente)
        self._en(ingreso + timedelta(minutes=self.azar.randint(8, 95)))
        motor.llamar(caso, box_id=self.azar.choice(e["boxes"]).id, autor=e["medico"])
        caso.refresh_from_db()
        self._en(self.reloj.t + timedelta(minutes=self.azar.randint(7, 25)))
        motor.avanzar(caso, {
            "titulo": "Atención en consultorio",
            "contenido": f"{self.azar.choice(MOTIVOS)} Diagnóstico: {self.azar.choice(DIAGNOSTICOS).lower()}.",
            "firmada": True,
        }, autor=e["medico"])

    def _internar(self, inst, e, paciente):
        self._en(self.ahora - timedelta(hours=self.azar.randint(6, 9 * 24)))
        caso = self._ingresar(inst, e["cama"], paciente)
        libre = motor.camas_disponibles(caso.nodo_actual).order_by("nombre").first()
        if libre is None:
            raise CommandError(f"{inst.nombre} no tiene camas libres para internar.")
        self._en(self.reloj.t + timedelta(minutes=self.azar.randint(20, 90)))
        motor.asignar_cama(caso, libre.id, autor=e["medico"])

    def _en_alta(self, red):
        datos = EN_ALTA
        inst = Institucion.objects.create(
            nombre=datos["nombre"], tipo=datos["tipo"], latitud=datos["lat"], longitud=datos["lon"],
            estado=Institucion.Estado.EN_ALTA,
        )
        # La fecha de alta es la que dispara la alerta: se corrige después de crearla.
        Institucion.objects.filter(pk=inst.pk).update(creada=self.ahora - timedelta(days=datos["dias_en_alta"]))
        areas = [Area.objects.create(institucion=inst, nombre=nombre) for nombre in datos["areas"]]
        self._persona(inst, datos["prefijo"], *datos["admin"], R.ADMIN_INSTITUCION, areas)
        red.instituciones.add(inst)
        return f"{inst.nombre}: en puesta en marcha hace {datos['dias_en_alta']} días, sin flujos ni agendas"
