"""
Carga VOLUMEN e HISTORIA sobre el escenario de guardia (ver `seed_guardia`).

`seed_guardia` construye la estructura —áreas, staff, grupos, boxes, formularios y
los 8 flujos publicados— pero **borra los casos y no crea ninguno**. Sin casos, la
bandeja, las filas, la pantalla de llamados y el tablero se ven vacíos: no se puede
demostrar el sistema ni diseñar contra él (no hay densidad, ni tablas largas, ni
curvas). Este comando llena ese hueco.

Cómo funciona
-------------
Los casos **se recorren con el motor real** (`apps.casos.motor`), no se inventan
filas en la base. Eso garantiza que los datos sean coherentes: cada caso tiene su
trazabilidad, sus valores de campo, sus ítems de fila, su historia clínica y sus
derivaciones tal como los habría dejado la operación real.

El problema de hacerlo así es que todo quedaría fechado *ahora*. Por eso el
recorrido lleva un **reloj propio** (`Reloj`): cada acción del motor avanza el reloj
una cantidad de minutos plausible y, al terminar, los objetos creados en ese tramo
se refechan con `.update()` (que no dispara `auto_now_add` / `auto_now`).

Eso es lo que hace que el tablero muestre métricas reales, porque las calcula así:
    espera     = ItemFila.llamado_at − ingreso
    atención   = ItemFila.atendido_at − llamado_at
    resolución = Caso.actualizado − Caso.creado

Determinista: con la misma `--semilla` produce exactamente los mismos datos, así la
demo se puede resetear y queda idéntica.

    python manage.py seed_volumen --rehacer     # reset completo de la demo (un comando)
    python manage.py seed_volumen               # agrega volumen al escenario existente
    python manage.py seed_volumen --casos 500 --dias 120
"""
import random
import unicodedata
from datetime import datetime, time, timedelta

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.casos import motor
from apps.casos.models import Caso, EventoCaso, ItemFila, Notificacion
from apps.flujos.models import Flujo, Nodo, VersionFlujo
from apps.formularios.models import Campo, Formulario
from apps.instituciones.models import Area, Box, Institucion
from apps.registros.models import Ciudadano, EntradaHistoria, Estudio, HistoriaClinica, Receta

# --------------------------------------------------------------------------- #
# Padrón de pacientes
# --------------------------------------------------------------------------- #
NOMBRES_F = [
    "María", "Ana", "Lucía", "Sofía", "Valentina", "Camila", "Carmen", "Rosa",
    "Julieta", "Florencia", "Mercedes", "Beatriz", "Norma", "Silvia", "Gabriela",
    "Marta", "Elena", "Paula", "Daniela", "Verónica",
]
NOMBRES_M = [
    "Juan", "Carlos", "Jorge", "Miguel", "Roberto", "Luis", "Diego", "Martín",
    "Alberto", "Héctor", "Rubén", "Sergio", "Fernando", "Ricardo", "Osvaldo",
    "Matías", "Nicolás", "Facundo", "Gustavo", "Raúl",
]
APELLIDOS = [
    "González", "Rodríguez", "Fernández", "López", "Martínez", "Pérez", "Gómez",
    "Sánchez", "Romero", "Díaz", "Álvarez", "Torres", "Ruiz", "Ramírez", "Flores",
    "Benítez", "Acosta", "Medina", "Herrera", "Aguirre", "Sosa", "Giménez",
    "Molina", "Silva", "Castro", "Ortiz", "Núñez", "Luna", "Cabrera", "Rojas",
    "Vega", "Quiroga", "Ledesma", "Villalba", "Peralta", "Ojeda", "Maldonado",
    "Figueroa", "Suárez", "Escobar",
]
OBRAS_SOCIALES = [
    "PAMI", "IOMA", "OSDE", "Swiss Medical", "OSECAC", "Galeno", "Medifé",
    "Sancor Salud", "Unión Personal", "", "", "",  # sin cobertura: ~25 %
]
ALERGIAS = [
    "", "", "", "", "Penicilina", "AINEs", "Iodo", "Látex", "Sulfamidas",
    "Polen / ácaros",
]
CONDICIONES = [
    "", "", "", "Hipertensión arterial", "Diabetes tipo 2", "Asma",
    "Hipotiroidismo", "EPOC", "Insuficiencia cardíaca", "Artrosis",
    "Hipertensión arterial · Diabetes tipo 2", "Anticoagulado (dicumarínicos)",
]

MOTIVOS = [
    "Dolor abdominal de 6 horas de evolución, sin fiebre.",
    "Dolor torácico opresivo irradiado a brazo izquierdo.",
    "Caída de propia altura con dolor e impotencia funcional en muñeca derecha.",
    "Fiebre de 38.5 °C y odinofagia desde hace dos días.",
    "Cefalea intensa de comienzo súbito.",
    "Dificultad respiratoria progresiva en las últimas horas.",
    "Traumatismo de tobillo jugando al fútbol.",
    "Vómitos y diarrea desde anoche, sin sangre.",
    "Mareos y sensación de desvanecimiento al incorporarse.",
    "Corte en mano izquierda con elemento cortante, sangrado controlado.",
    "Crisis de angustia con palpitaciones y sensación de ahogo.",
    "Lumbalgia aguda tras esfuerzo, sin déficit motor.",
    "Descompensación de tensión arterial, registro 180/110.",
    "Convulsión tónico-clónica presenciada, ya recuperado.",
    "Herida contusa en cuero cabelludo por golpe con objeto romo.",
    "Dolor en fosa lumbar derecha con disuria.",
]
LLEGADAS = ["Ambulancia", "Por sus medios", "Derivado de otro centro"]
DOLOR = ["Sin dolor", "Leve", "Moderado", "Severo"]

# Distribución tipo Manchester (el nivel fija la prioridad del caso).
TRIAGE = [
    ("Rojo - Emergencia", 3),
    ("Naranja - Muy urgente", 10),
    ("Amarillo - Urgente", 27),
    ("Verde - Poco urgente", 42),
    ("Azul - No urgente", 18),
]
CONDUCTAS = [("Alta", 55), ("Derivar a especialidad", 25), ("Internación", 12), ("Observación", 8)]
ESPECIALIDADES = [("Traumatología", 35), ("Cardiología", 30), ("Salud mental", 20), ("Neurología", 15)]

DIAGNOSTICOS = [
    "Gastroenteritis aguda", "Faringitis aguda", "Contusión de partes blandas",
    "Cólico renal", "Crisis hipertensiva", "Lumbalgia mecánica", "Cefalea tensional",
    "Síndrome febril sin foco", "Esguince de tobillo grado I", "Angina inestable a descartar",
    "Crisis de ansiedad", "Herida cortante superficial", "Bronquitis aguda",
]
ESTUDIOS_LAB = ["Hemograma completo", "Troponinas", "Función renal", "Hepatograma", "Coagulograma"]
ESTUDIOS_IMG = ["Radiografía de tórax", "Radiografía de muñeca", "Ecografía abdominal", "TAC de cerebro"]
RECETAS = [
    "Ibuprofeno 400 mg — 1 comprimido cada 8 h por 3 días.",
    "Paracetamol 1 g — 1 comprimido cada 8 h si dolor o fiebre.",
    "Amoxicilina 500 mg — 1 comprimido cada 8 h por 7 días.",
    "Diclofenac 75 mg — 1 comprimido cada 12 h por 5 días.",
    "Omeprazol 20 mg — 1 comprimido en ayunas por 14 días.",
]
SECTORES = ["Clínica médica", "Terapia intensiva", "Unidad coronaria"]

# Puntos donde puede quedar detenido un caso en curso (para poblar bandejas y filas),
# con la antigüedad plausible del ingreso en minutos. Cuanto más temprano el paso, más
# reciente tiene que ser: un paciente esperando en la sala hace 30 horas no es creíble.
PARADAS = {
    "admision": (2, 40),        # recién llegó, todavía en el mostrador
    "triage": (10, 90),         # admitido, esperando a enfermería
    "sala": (20, 300),          # en la sala de espera (hasta 5 h)
    "atencion": (40, 360),      # llamado a un box, en atención
    "conducta": (60, 480),      # atendido, falta cerrar la conducta
    "completo": (60, 600),      # cerró en guardia; sus derivaciones pueden seguir abiertas
}


def elegir(opciones):
    """Elige entre `[(valor, peso), …]`."""
    total = sum(p for _, p in opciones)
    r = random.uniform(0, total)
    acum = 0
    for valor, peso in opciones:
        acum += peso
        if r <= acum:
            return valor
    return opciones[-1][0]


def sin_tildes(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


class Reloj:
    """Tiempo simulado del recorrido de un caso."""

    def __init__(self, t0):
        self.t = t0

    def mas(self, minimo, maximo=None):
        self.t += timedelta(minutes=random.randint(minimo, maximo if maximo is not None else minimo))
        return self.t


class Command(BaseCommand):
    help = "Genera pacientes y casos con historia sobre el escenario de guardia."

    def add_arguments(self, parser):
        parser.add_argument("--casos", type=int, default=300, help="Casos históricos, ya cerrados (por defecto 300).")
        parser.add_argument("--activos", type=int, default=42, help="Casos en curso, de las últimas horas (por defecto 42).")
        parser.add_argument("--pacientes", type=int, default=40, help="Pacientes del padrón (por defecto 40).")
        parser.add_argument("--dias", type=int, default=90, help="Ventana histórica hacia atrás (por defecto 90).")
        parser.add_argument("--semilla", type=int, default=2026, help="Semilla del azar (misma semilla = mismos datos).")
        parser.add_argument("--limpiar", action="store_true", help="Borra los casos existentes antes de generar.")
        parser.add_argument("--rehacer", action="store_true",
                            help="Corre seed_guardia primero: deja la demo impecable con un solo comando.")

    @transaction.atomic
    def handle(self, *args, **opciones):
        random.seed(opciones["semilla"])

        if opciones["rehacer"]:
            call_command("seed_guardia", verbosity=0)
            self.stdout.write("Escenario de guardia recreado.")

        self.inst = Institucion.objects.filter(nombre="Hospital Central").first()
        if self.inst is None:
            raise CommandError("No existe «Hospital Central». Corré primero: python manage.py seed_guardia")

        self.ver_ingreso = (
            VersionFlujo.objects
            .filter(flujo__institucion=self.inst, flujo__titulo="Ingreso a Guardia",
                    estado=VersionFlujo.Estado.PUBLICADA)
            .first()
        )
        if self.ver_ingreso is None:
            raise CommandError("No hay una versión publicada de «Ingreso a Guardia». Corré: python manage.py seed_guardia")

        if opciones["limpiar"] or opciones["rehacer"]:
            self._limpiar()

        self._cargar_referencias()

        pacientes = self._crear_pacientes(opciones["pacientes"])
        self.stdout.write(f"Padrón: {len(pacientes)} pacientes.")

        # Cursor de sellado: los objetos con pk mayor a estos son "nuevos" y hay
        # que refecharlos. Se toma antes de generar para no tocar datos previos.
        self.cursor_evento = EventoCaso.objects.order_by("-pk").values_list("pk", flat=True).first() or 0
        self.cursor_entrada = EntradaHistoria.objects.order_by("-pk").values_list("pk", flat=True).first() or 0

        ahora = timezone.localtime()
        # Un caso solo puede quedar EN CURSO si es reciente: nadie espera tres meses
        # sentado en una sala. Sin este límite, el tablero informa demoras de 80 días.
        self.limite_cola = ahora - timedelta(hours=10)        # filas y estudios pendientes
        self.limite_internacion = ahora - timedelta(days=15)  # una internación sí dura días

        hechos = {"cerrados": 0, "en_curso": 0, "derivados": 0, "estudios": 0, "internados": 0}

        # 1. Histórico: casos completos repartidos por toda la ventana. Alimentan el
        #    tablero (curvas, tiempos promedio) y la historia clínica.
        for i, t0 in enumerate(sorted(self._momento_de_ingreso(ahora, opciones["dias"])
                                      for _ in range(opciones["casos"]))):
            try:
                self._recorrer_ingreso(random.choice(pacientes), t0, "completo", hechos)
            except motor.ErrorMotor as e:
                self.stderr.write(f"  histórico {i}: {e}")

        # 2. Carga viva: lo que se ve al abrir la app. Se rota por las paradas (en vez
        #    de sortearlas) para garantizar que ninguna bandeja ni fila quede vacía, y
        #    cada una usa su propia ventana de antigüedad.
        paradas = list(PARADAS)
        for i in range(opciones["activos"]):
            parada = paradas[i % len(paradas)]
            t0 = ahora - timedelta(minutes=random.randint(*PARADAS[parada]))
            try:
                self._recorrer_ingreso(random.choice(pacientes), t0, parada, hechos)
            except motor.ErrorMotor as e:
                self.stderr.write(f"  activo {i}: {e}")

        self._sellar_notificaciones(ahora)

        activos = Caso.objects.filter(institucion=self.inst).exclude(
            estado__in=[Caso.Estado.CERRADO, Caso.Estado.CANCELADO]).count()
        en_cola = ItemFila.objects.filter(caso__institucion=self.inst, atendido=False).count()

        self.stdout.write(self.style.SUCCESS(
            f"\nVolumen cargado en «Hospital Central» ({opciones['dias']} días de historia):\n"
            f"  {Caso.objects.filter(institucion=self.inst).count()} casos en total "
            f"({hechos['cerrados']} cerrados · {hechos['en_curso']} en curso)\n"
            f"  {hechos['derivados']} derivaciones a especialidad · {hechos['estudios']} estudios "
            f"· {hechos['internados']} internaciones\n"
            f"  {activos} casos activos ahora · {en_cola} pacientes esperando en filas\n"
            f"  {EntradaHistoria.objects.count()} entradas de historia clínica\n"
            f"\nReproducible: misma --semilla ({opciones['semilla']}) = mismos datos."
        ))

    def _limpiar(self):
        """Deja la institución sin datos de operación previos.

        Ojo con los registros clínicos: `seed_guardia` borra los casos, pero
        `EntradaHistoria.caso` es `SET_NULL`, así que las entradas, estudios y recetas
        **sobreviven huérfanos** y se acumulan en cada corrida (la historia de un
        paciente termina con la misma atención repetida N veces). Hay que borrarlos
        explícitamente.
        """
        casos = Caso.objects.filter(institucion=self.inst)
        historias = HistoriaClinica.objects.filter(ciudadano__institucion=self.inst)
        n_casos = casos.count()
        n_entradas = EntradaHistoria.objects.filter(historia__in=historias).count()

        casos.delete()  # cascada: valores, ítems de fila, eventos, notificaciones
        EntradaHistoria.objects.filter(historia__in=historias).delete()
        Estudio.objects.filter(historia__in=historias).delete()
        Receta.objects.filter(historia__in=historias).delete()
        Notificacion.objects.filter(caso__isnull=True).delete()

        self.stdout.write(f"Limpieza: {n_casos} casos y {n_entradas} registros clínicos previos.")

    # ----------------------------------------------------------------- #
    # Referencias del escenario (áreas, flujos, campos, staff, boxes)
    # ----------------------------------------------------------------- #
    def _cargar_referencias(self):
        self.areas = {a.nombre: a for a in Area.objects.filter(institucion=self.inst)}
        self.boxes = {}
        for box in Box.objects.filter(area__institucion=self.inst):
            self.boxes.setdefault(box.area_id, []).append(box)

        # Campos por (título de formulario, label) → id, para armar los `valores`.
        self.campos = {}
        for campo in Campo.objects.filter(formulario__institucion=self.inst).select_related("formulario"):
            self.campos[(campo.formulario.titulo, campo.label)] = campo.id

        self.admin = None
        from apps.accounts.models import Usuario
        self.admin = Usuario.objects.filter(is_superuser=True).first()

    def campo(self, formulario, label):
        try:
            return self.campos[(formulario, label)]
        except KeyError:
            raise CommandError(f"Falta el campo «{label}» en «{formulario}». ¿Corriste seed_guardia?")

    def _autor(self, caso):
        """Quién opera el paso actual: un integrante del grupo responsable del nodo."""
        nodo = caso.nodo_actual
        if nodo is not None:
            for grupo in nodo.grupos.all():
                miembro = grupo.miembros.first()
                if miembro:
                    return miembro
        return self.admin

    def _box(self, caso):
        opciones = self.boxes.get(caso.area_actual_id or 0, [])
        return random.choice(opciones).id if opciones else None

    # ----------------------------------------------------------------- #
    # Padrón
    # ----------------------------------------------------------------- #
    def _crear_pacientes(self, cantidad):
        pacientes = []
        hoy = timezone.localdate()
        usados = set()
        for i in range(cantidad):
            mujer = random.random() < 0.52
            nombre = random.choice(NOMBRES_F if mujer else NOMBRES_M)
            apellido = random.choice(APELLIDOS)
            # Pirámide etaria con sesgo a adultos y adultos mayores (perfil de guardia).
            edad = random.choice([random.randint(1, 17), random.randint(18, 64),
                                  random.randint(18, 64), random.randint(65, 92)])
            documento = str(random.randint(4_000_000, 55_000_000))
            while documento in usados:
                documento = str(random.randint(4_000_000, 55_000_000))
            usados.add(documento)

            ciu, _ = Ciudadano.objects.get_or_create(
                institucion=self.inst, documento=documento,
                defaults={
                    "nombre": nombre,
                    "apellido": apellido,
                    "fecha_nacimiento": hoy - timedelta(days=edad * 365 + random.randint(0, 364)),
                    "obra_social": random.choice(OBRAS_SOCIALES),
                    "codigo": f"CIU-{i + 1:04d}",
                    "domicilio": f"{random.choice(['Av. San Martín', 'Belgrano', 'Rivadavia', 'Sarmiento', 'Mitre', 'Alberdi'])} {random.randint(100, 4800)}",
                },
            )
            hc, _ = HistoriaClinica.objects.get_or_create(ciudadano=ciu)
            # Los mayores concentran los antecedentes, como en la realidad.
            if edad >= 60 or random.random() < 0.3:
                hc.alergias = random.choice(ALERGIAS)
                hc.condiciones = random.choice(CONDICIONES)
                hc.save(update_fields=["alergias", "condiciones"])
            pacientes.append(ciu)
        return pacientes

    # ----------------------------------------------------------------- #
    # Curva de llegadas
    # ----------------------------------------------------------------- #
    def _momento_de_ingreso(self, ahora, dias):
        """Un instante de ingreso plausible: menos los fines de semana y con los
        dos picos típicos de una guardia (media mañana y primera hora de la noche)."""
        while True:
            dia = ahora.date() - timedelta(days=random.randint(0, dias - 1))
            peso = {5: 0.8, 6: 0.7}.get(dia.weekday(), 1.0)
            if random.random() <= peso:
                break
        hora = elegir([(h, p) for h, p in zip(
            range(24),
            [3, 2, 2, 1, 1, 1, 2, 4, 7, 10, 11, 10, 8, 7, 6, 6, 7, 9, 11, 10, 8, 6, 5, 4],
        )])
        momento = datetime.combine(dia, time(hora, random.randint(0, 59), random.randint(0, 59)))
        if timezone.is_naive(momento):
            momento = timezone.make_aware(momento, timezone.get_current_timezone())
        return min(momento, ahora - timedelta(minutes=2))

    # ----------------------------------------------------------------- #
    # Sellado de tiempos
    # ----------------------------------------------------------------- #
    def _sellar(self, t):
        """Refecha los eventos y entradas de historia creados desde la última marca.

        Se usa `.update()` a propósito: `save()` volvería a poner la fecha real por
        los `auto_now_add`. Se separan unos segundos entre sí para que la línea de
        tiempo tenga un orden estable (EventoCaso ordena por fecha).
        """
        nuevos = list(EventoCaso.objects.filter(pk__gt=self.cursor_evento).order_by("pk").values_list("pk", flat=True))
        for i, pk in enumerate(nuevos):
            EventoCaso.objects.filter(pk=pk).update(fecha=t + timedelta(seconds=i * 7))
        if nuevos:
            self.cursor_evento = nuevos[-1]

        entradas = list(EntradaHistoria.objects.filter(pk__gt=self.cursor_entrada).order_by("pk").values_list("pk", flat=True))
        for pk in entradas:
            EntradaHistoria.objects.filter(pk=pk).update(fecha=t)
        if entradas:
            self.cursor_entrada = entradas[-1]

    def _sellar_arbol(self, raiz):
        """Fecha cada caso del árbol (raíz + derivados) según sus propios eventos."""
        pendientes, arbol = [raiz.pk], []
        while pendientes:
            arbol.extend(pendientes)
            pendientes = list(Caso.objects.filter(origen_id__in=pendientes).values_list("pk", flat=True))
        for pk in arbol:
            fechas = list(EventoCaso.objects.filter(caso_id=pk).order_by("fecha").values_list("fecha", flat=True))
            if fechas:
                Caso.objects.filter(pk=pk).update(creado=fechas[0], actualizado=fechas[-1])

            # El ingreso a la fila se toma del evento que encoló el caso. Es
            # indispensable para los que quedan ESPERANDO: si no, su `ingreso`
            # conserva el `auto_now_add` (el momento en que corrió el seed) y la
            # pantalla de filas muestra a todos con la misma espera al minuto.
            for item_pk, nodo_id in ItemFila.objects.filter(caso_id=pk).values_list("pk", "nodo_id"):
                entrada = (EventoCaso.objects.filter(caso_id=pk, nodo_id=nodo_id)
                           .order_by("fecha").values_list("fecha", flat=True).first())
                if entrada:
                    ItemFila.objects.filter(pk=item_pk).update(ingreso=entrada)
        # Los estudios llevan fecha (DateField): alinearlos con su caso.
        for pk in arbol:
            caso = Caso.objects.filter(pk=pk).values("estudio_id", "actualizado").first()
            if caso and caso["estudio_id"]:
                Estudio.objects.filter(pk=caso["estudio_id"]).update(
                    fecha=timezone.localtime(caso["actualizado"]).date())

    def _sellar_notificaciones(self, ahora):
        """Las notificaciones nacen con la fecha real: se alinean al caso y se marcan
        leídas salvo las de los últimos dos días (si no, la campana muestra cientos)."""
        for n in Notificacion.objects.filter(caso__isnull=False).select_related("caso").iterator():
            Notificacion.objects.filter(pk=n.pk).update(
                creada=n.caso.actualizado,
                leida=n.caso.actualizado < ahora - timedelta(days=2),
            )

    # ----------------------------------------------------------------- #
    # Recorrido de un ingreso a guardia
    # ----------------------------------------------------------------- #
    def _recorrer_ingreso(self, paciente, t0, parada, hechos):
        reloj = Reloj(t0)
        guardia = self.areas["Guardia"]

        caso = Caso.objects.create(
            institucion=self.inst, version=self.ver_ingreso,
            ciudadano=paciente, area_actual=guardia,
        )
        motor.iniciar(caso, autor=self._autor(caso))
        self._sellar(reloj.t)

        if parada == "admision":
            return self._cerrar_tramo(caso, hechos, en_curso=True)

        # 1. Admisión administrativa -------------------------------------
        reloj.mas(4, 14)
        motor.avanzar(caso, {"valores": {
            self.campo("Admisión administrativa", "Motivo de consulta"): random.choice(MOTIVOS),
            self.campo("Admisión administrativa", "Forma de llegada"): elegir([(LLEGADAS[0], 20), (LLEGADAS[1], 70), (LLEGADAS[2], 10)]),
            self.campo("Admisión administrativa", "Obra social / cobertura"): paciente.obra_social or "Sin cobertura",
            self.campo("Admisión administrativa", "Acompañante"): random.choice(["", "", "Familiar directo", "Cónyuge", "Hijo/a"]),
        }}, autor=self._autor(caso))
        self._sellar(reloj.t)

        if parada == "triage":
            return self._cerrar_tramo(caso, hechos, en_curso=True)

        # 2. Triage de enfermería (fija la prioridad del caso) -----------
        reloj.mas(5, 20)
        nivel = elegir(TRIAGE)
        motor.avanzar(caso, {"valores": {
            self.campo("Triage de enfermería", "Tensión arterial"): f"{random.randint(95, 185)}/{random.randint(55, 110)}",
            self.campo("Triage de enfermería", "Frecuencia cardíaca"): str(random.randint(52, 128)),
            self.campo("Triage de enfermería", "Temperatura"): f"{random.uniform(35.8, 39.4):.1f}",
            self.campo("Triage de enfermería", "Saturación de O₂"): f"{random.randint(88, 99)}%",
            self.campo("Triage de enfermería", "Escala de dolor"): random.choice(DOLOR),
            self.campo("Triage de enfermería", "Nivel de triage"): nivel,
            self.campo("Triage de enfermería", "Observaciones de enfermería"): random.choice(
                ["", "", "Paciente lúcido, orientado en tiempo y espacio.",
                 "Refiere el cuadro desde hace 48 h.", "Acompañado por familiar.",
                 "Se coloca vía periférica en miembro superior izquierdo."]),
        }}, autor=self._autor(caso))
        self._sellar(reloj.t)
        caso.refresh_from_db()

        if parada == "sala":
            # Queda esperando en la sala: es lo que puebla la fila y la pantalla de TV.
            return self._cerrar_tramo(caso, hechos, en_curso=True)

        # 3. Sala de espera: el médico ocupa un box y llama --------------
        espera = {
            Caso.Prioridad.URGENTE: (3, 12),
            Caso.Prioridad.ALTA: (15, 45),
        }.get(caso.prioridad, (40, 150))
        reloj.mas(*espera)
        medico = self._autor(caso)
        motor.llamar(caso, box_id=self._box(caso), autor=medico)
        self._marcar_llamado(caso, reloj.t)
        self._sellar(reloj.t)

        if parada == "atencion":
            return self._cerrar_tramo(caso, hechos, en_curso=True)

        # 4. Atención en el box ------------------------------------------
        reloj.mas(8, 30)
        caso.refresh_from_db()
        nodo_fila = caso.nodo_actual
        motor.avanzar(caso, {
            "titulo": "Atención en guardia",
            "contenido": f"Se evalúa al paciente. {random.choice(MOTIVOS)} Examen físico sin otros hallazgos relevantes.",
            "firmada": True,
        }, autor=medico)
        self._marcar_atendido(caso, nodo_fila, reloj.t)
        self._sellar(reloj.t)

        if parada == "conducta":
            return self._cerrar_tramo(caso, hechos, en_curso=True)

        # 5. Conducta médica ---------------------------------------------
        reloj.mas(5, 18)
        caso.refresh_from_db()
        conducta = elegir(CONDUCTAS)
        especialidad = elegir(ESPECIALIDADES) if conducta == "Derivar a especialidad" else ""
        motor.avanzar(caso, {"valores": {
            self.campo("Conducta médica de guardia", "Diagnóstico presuntivo"): random.choice(DIAGNOSTICOS),
            self.campo("Conducta médica de guardia", "Conducta"): conducta,
            self.campo("Conducta médica de guardia", "Especialidad de derivación"): especialidad,
        }}, autor=self._autor(caso))
        self._sellar(reloj.t)
        caso.refresh_from_db()

        # 5.b Observación: espera unas horas y se reevalúa (loop del flujo).
        if conducta == "Observación":
            reloj.mas(120, 360)
            motor.avanzar(caso, {}, autor=self._autor(caso))
            self._sellar(reloj.t)
            caso.refresh_from_db()
            # Tras la observación vuelve a Conducta: esta vez se resuelve.
            reloj.mas(6, 20)
            motor.avanzar(caso, {"valores": {
                self.campo("Conducta médica de guardia", "Diagnóstico presuntivo"): random.choice(DIAGNOSTICOS),
                self.campo("Conducta médica de guardia", "Conducta"): elegir([("Alta", 75), ("Internación", 25)]),
                self.campo("Conducta médica de guardia", "Especialidad de derivación"): "",
            }}, autor=self._autor(caso))
            self._sellar(reloj.t)
            caso.refresh_from_db()

        # 6. Sub-casos generados por la conducta -------------------------
        for sub in Caso.objects.filter(origen=caso).order_by("pk"):
            if sub.version.flujo.titulo == "Internación":
                hechos["internados"] += 1
                self._recorrer_internacion(sub, reloj, hechos)
            else:
                hechos["derivados"] += 1
                self._recorrer_especialidad(sub, reloj, hechos)

        self._cerrar_tramo(caso, hechos, en_curso=False)

    # ----------------------------------------------------------------- #
    # Sub-flujos
    # ----------------------------------------------------------------- #
    def _recorrer_especialidad(self, caso, reloj, hechos):
        """Atención con fila → (estudio opcional) → conducta → alta o internación."""
        # Una parte se deja en curso para que las filas de las especialidades no queden
        # vacías, pero solo si el caso es reciente (ver `limite_cola`).
        if reloj.t >= self.limite_cola and random.random() < 0.45:
            return

        reloj.mas(20, 90)
        medico = self._autor(caso)
        motor.llamar(caso, box_id=self._box(caso), autor=medico)
        self._marcar_llamado(caso, reloj.t)
        self._sellar(reloj.t)
        caso.refresh_from_db()

        # Durante la atención el médico puede pedir un estudio (ida y vuelta).
        if random.random() < 0.4:
            reloj.mas(3, 10)
            a_laboratorio = random.random() < 0.55
            area = self.areas["Laboratorio" if a_laboratorio else "Diagnóstico por imágenes"]
            tipo = random.choice(ESTUDIOS_LAB if a_laboratorio else ESTUDIOS_IMG)
            sub = motor.solicitar_estudio_derivado(caso, tipo, area, autor=medico)
            self._sellar(reloj.t)
            hechos["estudios"] += 1
            if not self._recorrer_estudio(sub, reloj, a_laboratorio):
                return  # el estudio quedó pendiente: el caso sigue esperando
            caso.refresh_from_db()

        if random.random() < 0.35:
            motor.agregar_receta(caso, random.choice(RECETAS), autor=medico)
            Receta.objects.filter(historia__ciudadano=caso.ciudadano).update(
                fecha=timezone.localtime(reloj.t).date())

        reloj.mas(10, 35)
        titulo_flujo = caso.version.flujo.titulo
        nodo_fila = caso.nodo_actual
        motor.avanzar(caso, {
            "titulo": f"Atención · {caso.area_actual.nombre if caso.area_actual else titulo_flujo}",
            "contenido": "Se evalúa al paciente derivado desde guardia. Se indica conducta según hallazgos.",
            "firmada": True,
        }, autor=medico)
        self._marcar_atendido(caso, nodo_fila, reloj.t)
        self._sellar(reloj.t)
        caso.refresh_from_db()

        # Conducta de la especialidad (el formulario varía por área).
        form = caso.nodo_actual.formulario if caso.nodo_actual else None
        if form is None:
            return
        clinico = next((c for c in form.campos.all()
                        if c.label not in ("Diagnóstico", "Disposición")), None)
        disposicion = elegir([("Alta", 70), ("Internación", 30)])
        valores = {
            self.campo(form.titulo, "Diagnóstico"): random.choice(DIAGNOSTICOS),
            self.campo(form.titulo, "Disposición"): disposicion,
        }
        if clinico is not None and clinico.opciones:
            valores[clinico.id] = random.choice(clinico.opciones)

        reloj.mas(4, 12)
        motor.avanzar(caso, {"valores": valores}, autor=self._autor(caso))
        self._sellar(reloj.t)

        for sub in Caso.objects.filter(origen=caso, version__flujo__titulo="Internación"):
            hechos["internados"] += 1
            self._recorrer_internacion(sub, reloj, hechos)

    def _recorrer_estudio(self, caso, reloj, es_laboratorio):
        """Laboratorio / Imágenes: toma o recepción → informe → vuelve al que lo pidió."""
        reciente = reloj.t >= self.limite_cola
        if reciente and random.random() < 0.35:
            return False  # queda pendiente: alimenta la bandeja de lab/imágenes

        reloj.mas(10, 40)
        if es_laboratorio:
            valores = {
                self.campo("Toma de muestra", "Tipo de muestra"): random.choice(["Sangre", "Orina", "Hisopado"]),
                self.campo("Toma de muestra", "Observaciones"): random.choice(["", "", "Muestra en ayunas."]),
            }
        else:
            valores = {
                self.campo("Recepción de imágenes", "Estudio a realizar"): random.choice(ESTUDIOS_IMG),
                self.campo("Recepción de imágenes", "Preparación"): random.choice(["Ninguna", "Ayuno", "Contraste"]),
            }
        motor.avanzar(caso, {"valores": valores}, autor=self._autor(caso))
        self._sellar(reloj.t)
        caso.refresh_from_db()

        if reciente and random.random() < 0.3:
            return False  # informe pendiente

        reloj.mas(25, 180)
        motor.avanzar(caso, {
            "titulo": "Informe del estudio",
            "contenido": "Se procesa la muestra y se emite el informe correspondiente."
            if es_laboratorio else "Se realiza el estudio y se emite el informe.",
            "firmada": True,
            "resultado": elegir([("normal", 68), ("alterado", 32)]),
        }, autor=self._autor(caso))
        self._sellar(reloj.t)
        return True

    def _recorrer_internacion(self, caso, reloj, hechos):
        """Asignar cama → evolución diaria (loop) → alta médica."""
        # Una internación sí puede llevar días, así que acá la ventana es más ancha.
        if reloj.t >= self.limite_internacion and random.random() < 0.3:
            return  # internación en curso: pobla la bandeja de Internación

        reloj.mas(20, 70)
        motor.avanzar(caso, {"valores": {
            self.campo("Asignación de cama", "Sector"): elegir([(SECTORES[0], 70), (SECTORES[1], 18), (SECTORES[2], 12)]),
            self.campo("Asignación de cama", "Cama"): f"{random.randint(1, 24)}-{random.choice('AB')}",
            self.campo("Asignación de cama", "Médico de cabecera"): "Dr. Gabriel Ferro",
        }}, autor=self._autor(caso))
        self._sellar(reloj.t)
        caso.refresh_from_db()

        for dia in range(random.randint(1, 4)):
            if caso.nodo_actual is None or caso.estado == Caso.Estado.CERRADO:
                break
            reloj.mas(600, 1200)  # una evolución por día
            motor.avanzar(caso, {
                "titulo": f"Evolución día {dia + 1}",
                "contenido": random.choice([
                    "Paciente hemodinámicamente estable, afebril. Continúa tratamiento indicado.",
                    "Buena evolución clínica. Tolera dieta. Se reduce analgesia.",
                    "Persiste con dolor moderado. Se ajusta esquema analgésico.",
                    "Sin intercurrencias en las últimas 24 h.",
                ]),
                "firmada": True,
            }, autor=self._autor(caso))
            self._sellar(reloj.t)
            caso.refresh_from_db()
            if caso.nodo_actual is None:
                break

            ultimo = dia == 3 or random.random() < 0.45
            reloj.mas(15, 45)
            motor.avanzar(caso, {"valores": {
                self.campo("Evolución diaria", "Evolución"): "Evolución favorable." if ultimo else "Continúa en observación clínica.",
                self.campo("Evolución diaria", "Decisión"): "Alta médica" if ultimo else "Continúa internado",
            }}, autor=self._autor(caso))
            self._sellar(reloj.t)
            caso.refresh_from_db()
            if ultimo:
                break

    # ----------------------------------------------------------------- #
    # Auxiliares de fila y cierre
    # ----------------------------------------------------------------- #
    def _marcar_llamado(self, caso, t):
        """Fecha el llamado (con el ingreso, da la espera que informa el tablero).

        El `ingreso` no se toca acá: lo fija `_sellar_arbol` para todos los ítems por
        igual, hayan sido llamados o no.
        """
        item = caso.en_filas.filter(nodo=caso.nodo_actual).order_by("-pk").first()
        if item is not None:
            ItemFila.objects.filter(pk=item.pk).update(llamado_at=t)

    def _marcar_atendido(self, caso, nodo, t):
        """Fecha el fin de la atención (de ahí sale el tiempo de atención del tablero).

        El nodo se recibe por parámetro a propósito: para cuando esto se llama, el
        motor ya movió `caso.nodo_actual` al paso siguiente y buscar el ítem por el
        nodo actual no encontraría nada.
        """
        item = caso.en_filas.filter(nodo=nodo).order_by("-pk").first()
        if item is not None:
            ItemFila.objects.filter(pk=item.pk).update(atendido_at=t)

    def _cerrar_tramo(self, caso, hechos, en_curso):
        self._sellar_arbol(caso)
        hechos["en_curso" if en_curso else "cerrados"] += 1
        return caso
