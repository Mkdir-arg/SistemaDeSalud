"""Circuito de financiadores sobre un hospital ya cargado: doce meses que terminan hoy.

Qué carga
---------
Obras sociales, planes, reglas, convenios, aranceles acordados, padrón, consumos
externos, autorizaciones previas y atenciones con copago, SOBRE Los Aromos (o la
institución que se indique), sin tocar sus datos anteriores. Las fechas siguen el
calendario relativo de `apps.demo.calendario`.

Deja trabajo pendiente para cada lado:

- **Financiador:** autorizaciones pendientes de respuesta, la liquidación del mes
  en curso sin pagar, un padrón con bajas y una reactivación.
- **Hospital:** una autorización observada para reenviar, saldos del mes en
  curso sin decidir quién los paga, un caso con reserva y copago aceptado, un
  caso sin cupo porque el afiliado lo consumió en otro prestador, y un convenio
  que propuso una prepaga y espera la aceptación del hospital.

Por qué un área nueva y no las existentes
-----------------------------------------
Las atenciones nuevas entran en un área propia («Consultorios externos») creada
por este comando. No es una decisión estética: el reparto distribuye cada gasto
entre las atenciones elegibles DE SU ÁREA, así que sumar atenciones a un área con
gastos repartidos le cambia la porción a todas las demás. En Los Aromos eso
reescribiría en silencio las cifras por atención de `seed_los_aromos`. El área
nueva no tiene gastos ni reglas de reparto, así que no entra en ningún reparto
existente y los importes anteriores quedan intactos.

Requisitos
----------
- PostgreSQL migrado.
- `ENTORNO` distinto de `produccion`.
- La institución destino ya cargada, con administrador institucional.
- Ningún financiador cargado. Para rehacerlo se vacía la base con
  `seed_entorno_demo`: el escenario no se borra ni se mezcla por partes.

Los usuarios toman la clave de `DEMO_PASSWORD` (ver `apps.demo.claves`).
"""
import json
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from uuid import NAMESPACE_URL, uuid4, uuid5

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone

from apps.accounts.models import LegajoProfesional, Membresia, Usuario
from apps.casos import motor
from apps.casos.models import Caso
from apps.demo.calendario import Calendario
from apps.demo.claves import clave_demo
from apps.demo.entorno import exigir_entorno_de_prueba
from apps.finanzas.cobros import registrar_politica_cobro
from apps.finanzas.dinero import registrar_movimiento
from apps.finanzas.models import (
    ConcesionFinanciera, HechoAtencionCosteable, ObligacionFinanciera, Prestacion,
)
from apps.finanzas.services import procesar_hecho_atencion
from apps.flujos.models import Conexion, Flujo, Nodo, VersionFlujo
from apps.instituciones.models import Area, Institucion
from apps.registros.models import Ciudadano

from apps.financiadores import models as m
from apps.financiadores import autorizaciones
from apps.financiadores.cobertura import cotizacion, reservar, seleccionar_afiliacion
from apps.financiadores.cobros import resolver_saldo
from apps.financiadores.services import registrar_afiliado, registrar_consumo_externo


INSTITUCION_POR_DEFECTO = "Hospital General Los Aromos"
CENTAVOS = Decimal("0.01")
CANTIDAD_DE_MESES = 12
# Días nominales del primer mes: la configuración va el 5 y el padrón el 8, así
# que las atenciones de ese mes arrancan después.
DIA_CONFIGURACION, DIA_PADRON = 5, 8

# Aranceles generales del área nueva: los que rigen cuando no hay un acuerdo de
# convenio para esa prestación.
ARANCEL_CONSULTA = 28000
ARANCEL_RADIOGRAFIA = 35000

PRESTACIONES = (
    # código, título, arancel general, categoría del catálogo común
    ("CEX", "Consulta ambulatoria externa", ARANCEL_CONSULTA, "consultas"),
    ("RXE", "Radiografía ambulatoria de tórax", ARANCEL_RADIOGRAFIA, "imagenes"),
)

FINANCIADORES = (
    {
        "slug": "mutual-del-valle",
        # Mismo nombre que ya figura como contraparte de cobro en Los Aromos: el
        # escenario anterior la nombraba sin que existiera como financiador.
        "nombre": "Mutual del Valle",
        "tipo": "mutual",
        "dominio": "mutualdelvalle.test",
        "plan_codigo": "MV-INTEGRAL",
        "plan_nombre": "Plan Integral",
        # código -> (porcentaje, cupo, periodo, requiere_autorizacion)
        "reglas": {"CEX": ("80", 6, "anio", False), "RXE": ("70", 2, "anio", True)},
        # Acuerdo por debajo del arancel general: se negoció, no es un descuento.
        "aranceles": {"CEX": 26000},
        "convenio": "activo",
    },
    {
        "slug": "obra-social-provincial",
        "nombre": "Obra Social Provincial",
        "tipo": "obra_social",
        "dominio": "osprovincial.test",
        "plan_codigo": "OSP-BASE",
        "plan_nombre": "Plan Base",
        "reglas": {"CEX": ("70", 4, "anio", False), "RXE": ("50", None, "anio", False)},
        "aranceles": {"RXE": 32000},
        "convenio": "activo",
    },
    {
        # Recién llegada: propuso convenio y el hospital todavía no lo aceptó.
        # Es lo que deja trabajo en «Coberturas → Configuración».
        "slug": "prepaga-horizonte",
        "nombre": "Prepaga Horizonte Salud",
        "tipo": "otro",
        "dominio": "horizontesalud.test",
        "plan_codigo": "PH-300",
        "plan_nombre": "Plan 300",
        "reglas": {"CEX": ("90", 12, "anio", False), "RXE": ("80", 4, "anio", False)},
        "aranceles": {},
        "convenio": "propuesto",
    },
)

# Personas propias del área nueva. Ficticias, como todo el escenario.
PERSONAS = (
    ("Rosa", "Maidana"), ("Ernesto", "Bogado"), ("Silvina", "Alegre"),
    ("Gustavo", "Ramallo"), ("Noelia", "Cáceres"), ("Ariel", "Domínguez"),
    ("Mirta", "Zalazar"), ("Fabián", "Leguizamón"), ("Carina", "Ojeda"),
    ("Rubén", "Maldonado"), ("Andrea", "Paniagua"), ("Claudio", "Insaurralde"),
    ("Viviana", "Escalante"), ("Marcelo", "Aguirre"), ("Susana", "Barrios"),
    ("Hernán", "Villagra"), ("Lorena", "Quintana"), ("Walter", "Sanabria"),
    ("Gisela", "Toledo"), ("Mauricio", "Benavídez"), ("Estela", "Carrizo"),
    ("Damián", "Frías"), ("Romina", "Pacheco"), ("Osvaldo", "Duarte"),
    ("Liliana", "Arévalo"), ("Ignacio", "Montiel"),
)

# Padrón: qué personas están afiliadas a cada financiador. Las que no figuran
# quedan sin cobertura: ese estado también hay que poder mostrarlo.
PADRON = {
    "mutual-del-valle": tuple(range(0, 12)),
    "obra-social-provincial": tuple(range(12, 21)),
}
SIN_COBERTURA = tuple(range(21, 26))
# Personas con una historia propia en el padrón. Quedan fuera de la rotación
# mensual para que esa historia no choque con atenciones de rutina.
SIN_CUPO = 3          # Mutual: consumió sus radiografías del año en otro prestador.
REACTIVADA = 6        # Mutual: baja por falta de pago y reactivación en el mes.
DADA_DE_BAJA = 20     # Obra Social Provincial: cese laboral.
EN_CURSO_CEX_MV, EN_CURSO_CEX_OSP = 1, 17
AUTORIZACION_PENDIENTE = (8, 10)   # Mutual: radiografías esperando respuesta.
AUTORIZACION_OBSERVADA = 11        # Mutual: el financiador pidió más datos.

# Rotación mensual, pensada para no agotar cupos por año calendario:
# ~3 consultas por persona de la Mutual (cupo 6) y ~3 por persona de la Obra
# Social (cupo 4). Las radiografías de la Mutual rotan de a una por mes entre
# siete personas: nadie pasa de dos en doce meses, que es justo el cupo anual.
# Sacar a alguien más de esa rotación puede dejar a otro sin cobertura.
ROTACION_CEX_MV = tuple(i for i in PADRON["mutual-del-valle"] if i not in (REACTIVADA,))
ROTACION_RXE_MV = tuple(i for i in PADRON["mutual-del-valle"] if i not in (SIN_CUPO, REACTIVADA, *AUTORIZACION_PENDIENTE, AUTORIZACION_OBSERVADA))
ROTACION_OSP = tuple(i for i in PADRON["obra-social-provincial"] if i != DADA_DE_BAJA)
# Días nominales de las atenciones de un mes pasado y del mes en curso: uno por
# cada fila de `_agenda_del_mes`. El primer mes arranca después del padrón y
# tiene menos días, así que ahí entran las primeras filas y no todas.
DIAS_HISTORIA = (4, 7, 10, 13, 16, 19, 22, 25)
DIAS_EN_CURSO = (3, 4, 8, 9, 10, 11, 12, 13)
# Meses (por distancia al actual) en que la Mutual rechazó la radiografía.
RECHAZOS = (-8, -3)


def dinero(valor):
    return Decimal(str(valor)).quantize(CENTAVOS)


def clave(texto):
    return uuid5(NAMESPACE_URL, "financiadores/" + texto)


def es_de_paciente(obligacion):
    """Cargo a una persona y no a un financiador.

    Se distingue por la referencia que deja `cobros._obligacion`: el copago
    va a `ciudadano:<id>` y lo que la persona acepta al resolver un saldo, a
    `paciente:<id>`. El nombre no sirve: los dos llevan uno.
    """
    return obligacion.contraparte_referencia.startswith(("ciudadano:", "paciente:"))


class Command(BaseCommand):
    help = "Carga el circuito de financiadores (doce meses que terminan hoy) sobre una institución ya cargada."

    def add_arguments(self, parser):
        parser.add_argument("--institucion", type=int, default=None,
                            help="Id de la institución destino. Por defecto, la de Los Aromos.")
        parser.add_argument("--salida", help="Archivo JSON nuevo con el manifiesto; nunca sobrescribe otro.")

    def handle(self, *args, **options):
        exigir_entorno_de_prueba("seed_financiadores")
        if connection.vendor != "postgresql":
            raise CommandError("La carga requiere PostgreSQL para verificar transacciones y bloqueo exclusivo.")
        salida = Path(options["salida"]).resolve() if options.get("salida") else None
        if salida and (salida.exists() or not salida.parent.is_dir()):
            raise CommandError("La salida debe ser un archivo nuevo dentro de un directorio existente.")
        self.cal = Calendario()
        self.meses = self.cal.meses(CANTIDAD_DE_MESES)

        with transaction.atomic():
            # Dos invocaciones no pueden cargar el escenario a la vez.
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(%s)", [2026091701])
            if m.Financiador.objects.exists():
                raise CommandError(
                    "Ya hay financiadores cargados. No se borra, mezcla ni duplica por partes: "
                    "para rehacerlo, corré seed_entorno_demo."
                )
            self._institucion(options.get("institucion"))
            self._configurar(clave_demo())
            self._padron()
            self._historia()
            self._resolver_saldos()
            self._pagos()
            self._en_curso()
            resumen = self._verificar_y_resumir()

        contenido = json.dumps(resumen, ensure_ascii=False, indent=2, default=str)
        if salida:
            try:
                with salida.open("x", encoding="utf-8") as archivo:
                    archivo.write(contenido + "\n")
            except OSError as error:
                raise CommandError(
                    "Los datos se cargaron, pero no se pudo guardar el JSON. No repitas la carga; "
                    "conservá la base y revisá la salida."
                ) from error
        self.stdout.write(contenido)

    # ------------------------------------------------------------------ #
    def _institucion(self, id_pedido):
        if id_pedido:
            self.institucion = Institucion.objects.filter(pk=id_pedido).first()
            if not self.institucion:
                raise CommandError("No existe la institución %s." % id_pedido)
        else:
            self.institucion = Institucion.objects.filter(nombre=INSTITUCION_POR_DEFECTO).first()
            if not self.institucion:
                raise CommandError(
                    "No existe «%s». Cargala primero con seed_los_aromos o indicá --institucion." % INSTITUCION_POR_DEFECTO
                )
        self.admin = Usuario.objects.filter(
            membresias__institucion=self.institucion,
            membresias__rol=Membresia.Rol.ADMIN_INSTITUCION,
        ).order_by("id").first()
        if not self.admin:
            raise CommandError(
                "La institución no tiene administrador institucional; no hay quién registre la configuración."
            )
        self.administrativa = Usuario.objects.filter(
            membresias__institucion=self.institucion,
            membresias__rol=Membresia.Rol.ADMINISTRATIVO,
        ).order_by("id").first() or self.admin

    # ------------------------------------------------------------------ #
    def _configurar(self, password):
        self.prestaciones, self.versiones, self.comunes = {}, {}, {}
        self.financiadores, self.planes, self.convenios, self.operadores = {}, {}, {}, {}
        self.resolutores, self.afiliados = {}, {}
        self.vigencia = self.cal.dia(-(CANTIDAD_DE_MESES - 1), DIA_CONFIGURACION)

        with self.cal.sintetica(self.vigencia) as desde:
            # El circuito de cobertura se activa explícitamente por institución.
            # Sin esto el sistema sigue capturando cargos por política simple.
            m.ConfiguracionHospital.objects.update_or_create(
                institucion=self.institucion, defaults={"activo": True, "dias_reserva_antigua": 7},
            )
            self.area = Area.objects.create(
                institucion=self.institucion, nombre="Consultorios externos",
                responsable="Irene Bustos",
                descripcion=(
                    "Atención ambulatoria con cobertura de financiadores. "
                    "Todos los datos de este entorno son ficticios."
                ),
            )
            self.medico = Usuario.objects.create_user(
                "irene.bustos@losaromos.test", password, nombre="Irene", apellido="Bustos",
            )
            membresia_medico = Membresia.objects.create(
                usuario=self.medico, institucion=self.institucion, rol=Membresia.Rol.MEDICO,
            )
            membresia_medico.areas.add(self.area)
            LegajoProfesional.objects.create(
                usuario=self.medico, especialidad="Consultorios externos", matricula="64903",
            )
            # El área nueva tiene que entrar en el alcance de quienes ya operan
            # finanzas; si no, la configuración existe y nadie puede usarla.
            for membresia in Membresia.objects.filter(
                institucion=self.institucion, usuario__in=[self.admin, self.administrativa],
            ):
                membresia.areas.add(self.area)
                for concesion in membresia.concesiones_financieras.all():
                    concesion.areas.add(self.area)

            # Quien admite es quien registra que la persona aceptó su copago, así
            # que necesita ese permiso explícito. No se lo da el rol: se concede
            # por acción y acotado a esta área, que es el punto del modelo.
            membresia_admisiones = Membresia.objects.filter(
                institucion=self.institucion, usuario=self.administrativa,
            ).first()
            for accion in ("registrar_aceptacion", "resolver_cobertura"):
                concesion, _ = ConcesionFinanciera.objects.get_or_create(
                    membresia=membresia_admisiones, accion=accion,
                )
                concesion.areas.add(self.area)

            for codigo, titulo, arancel, categoria in PRESTACIONES:
                flujo = Flujo.objects.create(
                    institucion=self.institucion, area=self.area, titulo=titulo,
                    descripcion="Ingreso → atención profesional → cierre. La cobertura se resuelve al completar.",
                )
                version = VersionFlujo.objects.create(flujo=flujo, numero=1, autor=self.admin)
                inicio = Nodo.objects.create(version=version, tipo=Nodo.Tipo.INICIO, titulo="Ingreso", x=60, y=150)
                atencion = Nodo.objects.create(version=version, tipo=Nodo.Tipo.ATENCION, titulo=titulo, x=340, y=150)
                fin = Nodo.objects.create(version=version, tipo=Nodo.Tipo.FIN, titulo="Cierre", x=620, y=150)
                Conexion.objects.create(version=version, origen=inicio, destino=atencion)
                Conexion.objects.create(version=version, origen=atencion, destino=fin)
                if not motor.puede_publicar(version):
                    errores = [e for e in motor.validar_version(version) if e.get("nivel") == "error"]
                    raise CommandError("Flujo no publicable: %s" % errores)
                version.estado = VersionFlujo.Estado.PUBLICADA
                version.save(update_fields=["estado"])
                self.versiones[codigo] = version

                prestacion = Prestacion.objects.create(
                    institucion=self.institucion, nodo=atencion, codigo=codigo, nombre=titulo,
                )
                self.prestaciones[codigo] = prestacion
                # Arancel general: el que rige sin acuerdo de convenio.
                registrar_politica_cobro(
                    prestacion=prestacion, registrado_por=self.admin, cobrar=True,
                    importe=dinero(arancel),
                )
                # El catálogo común es lo que permite que un hospital y un
                # financiador hablen de la misma prestación.
                comun = m.PrestacionComun.objects.create(codigo=codigo, nombre=titulo, categoria=categoria)
                m.VinculoPrestacion.objects.create(prestacion=prestacion, comun=comun)
                self.comunes[codigo] = comun

            self._pacientes()
            for datos in FINANCIADORES:
                if datos["convenio"] == "activo":
                    self._financiador(datos, password, desde)
        # La prepaga llega en el mes en curso.
        with self.cal.sintetica(self.cal.dia(0, 13), 11) as desde:
            for datos in FINANCIADORES:
                if datos["convenio"] == "propuesto":
                    self._financiador(datos, password, desde)

    def _pacientes(self):
        """Personas propias del área nueva, sin historia clínica previa.

        No se reutilizan las personas ya atendidas a propósito. La historia
        clínica es una cadena sellada: cada entrada firmada encadena con la
        ÚLTIMA de esa persona. Insertar atenciones retrofechadas a alguien cuya
        última entrada es posterior haría que dos entradas encadenen con el mismo
        sello previo, y la base lo rechaza —correctamente— como cadena rota.
        """
        self.pacientes = []
        hoy = self.cal.hoy
        for indice, (nombre, apellido) in enumerate(PERSONAS, 1):
            self.pacientes.append(Ciudadano.objects.create(
                institucion=self.institucion, nombre=nombre, apellido=apellido,
                codigo="LA-CEX-%04d" % indice, documento="FIC1%05d" % indice,
                fecha_nacimiento=hoy.replace(year=hoy.year - 68 + (indice * 5) % 45, month=1 + indice % 12, day=1 + indice % 27),
            ))

    def _financiador(self, datos, password, desde):
        slug = datos["slug"]
        financiador = m.Financiador.objects.create(nombre=datos["nombre"], tipo=datos["tipo"])
        self.financiadores[slug] = financiador

        # El portal no es una sola cuenta que puede todo: un administrador, un
        # operador que responde autorizaciones y un auditor de sólo lectura.
        cuentas = [("admin", "Administración", "admin", True), ("auditor", "Auditoría", "auditor", False)]
        if datos["reglas"] and any(regla[3] for regla in datos["reglas"].values()):
            cuentas.insert(1, ("operador", "Autorizaciones", "operador", True))
        for cuenta, etiqueta, rol, resuelve in cuentas:
            usuario = Usuario.objects.create_user(
                "%s@%s" % (cuenta, datos["dominio"]), password, nombre=etiqueta, apellido=datos["nombre"],
            )
            m.MembresiaFinanciador.objects.create(
                financiador=financiador, usuario=usuario, rol=rol, resuelve_autorizaciones=resuelve,
            )
            if rol == "admin":
                self.operadores[slug] = usuario
            if rol == "operador":
                self.resolutores[slug] = usuario
        admin_portal = self.operadores[slug]
        self.resolutores.setdefault(slug, admin_portal)

        self.planes[slug] = m.Plan.objects.create(
            financiador=financiador, codigo=datos["plan_codigo"], nombre=datos["plan_nombre"],
        )
        activo = datos["convenio"] == "activo"
        self.convenios[slug] = m.Convenio.objects.create(
            financiador=financiador, institucion=self.institucion, estado=datos["convenio"],
            propuesto_por="financiador", creado_por=admin_portal,
            aceptado_por=self.admin if activo else None, aceptado_en=desde if activo else None,
            plazo_autorizacion_horas=48,
        )
        for codigo, (porcentaje, cupo, periodo, autorizacion) in datos["reglas"].items():
            m.ReglaCobertura.objects.create(
                financiador=financiador, plan=self.planes[slug], prestacion=self.comunes[codigo],
                porcentaje=Decimal(porcentaje), cupo=cupo, periodo=periodo,
                vigente_desde=timezone.localdate(), requiere_autorizacion=autorizacion, creado_por=admin_portal,
            )
        for codigo, importe in datos.get("aranceles", {}).items():
            m.ArancelConvenio.objects.create(
                convenio=self.convenios[slug], prestacion=self.prestaciones[codigo],
                importe=dinero(importe), vigente_desde=timezone.localdate(), creado_por=self.admin,
            )

    # ------------------------------------------------------------------ #
    def _padron(self):
        """Afiliaciones sobre personas ya registradas, con historia de vigencias."""
        alta = self.cal.dia(-(CANTIDAD_DE_MESES - 1), DIA_PADRON)
        with self.cal.sintetica(alta):
            for slug, indices in PADRON.items():
                prefijo = "MV" if slug == "mutual-del-valle" else "OSP"
                for orden, indice in enumerate(indices, 1):
                    paciente = self.pacientes[indice]
                    afiliado = registrar_afiliado(
                        financiador=self.financiadores[slug], usuario=self.operadores[slug],
                        numero="%s%05d" % (prefijo, orden), documento=paciente.documento,
                        nombre=("%s %s" % (paciente.nombre, paciente.apellido)).strip(),
                        plan=self.planes[slug], desde=timezone.localdate(),
                    )
                    # Vincular la afiliación a la persona del hospital es lo que
                    # permite reconocerla al admitirla, sin cargar el documento
                    # dos veces ni compartir historia clínica.
                    m.VinculoCiudadano.objects.create(
                        afiliado=afiliado, ciudadano=paciente, verificado_por=self.admin,
                    )
                    self.afiliados[(slug, indice)] = afiliado

        # Una baja y una baja con reactivación: sin esto el padrón se ve como si
        # las afiliaciones no cambiaran nunca, que es justo lo que sí pasa.
        self.afiliado_dado_de_baja = self._finalizar(
            ("obra-social-provincial", DADA_DE_BAJA), self.cal.dia(-2, 10),
            "Cese de la relación laboral informada por el empleador.",
        )
        self.afiliado_reactivado = self._finalizar(
            ("mutual-del-valle", REACTIVADA), self.cal.dia(-1, 25),
            "Falta de pago informada por la mutual.",
        )
        with self.cal.sintetica(self.cal.dia(0, 2)):
            vuelve = self.afiliado_reactivado
            vuelve.finalizado_en, vuelve.finalizado_por, vuelve.motivo_finalizacion = None, None, ""
            vuelve.save(update_fields=["finalizado_en", "finalizado_por", "motivo_finalizacion"])
            m.HistorialAfiliacion.objects.create(
                afiliado=vuelve, numero=vuelve.numero, documento=vuelve.documento, plan=vuelve.plan,
                desde=timezone.localdate(), registrado_por=self.operadores["mutual-del-valle"],
                tipo="reactivacion", motivo="Regularización de aportes verificada por la mutual.",
            )

        # La prepaga recién llegada ya tiene padrón aunque el convenio no esté
        # aceptado: son las personas que hasta ahora se atendían como
        # particulares. Sin esto su portal abría vacío.
        with self.cal.sintetica(self.cal.dia(0, 13), 12):
            prepaga = "prepaga-horizonte"
            for orden, indice in enumerate(SIN_COBERTURA, 1):
                paciente = self.pacientes[indice]
                self.afiliados[(prepaga, indice)] = registrar_afiliado(
                    financiador=self.financiadores[prepaga], usuario=self.operadores[prepaga],
                    numero="PH%05d" % orden, documento=paciente.documento,
                    nombre=("%s %s" % (paciente.nombre, paciente.apellido)).strip(),
                    plan=self.planes[prepaga], desde=timezone.localdate(),
                )

        # Consumos en otros prestadores: gastan cupo sin que el hospital los vea
        # en su propia actividad. Es la causa más común de «creí que estaba
        # cubierto y no lo estaba». Van en el mes en curso para que caigan en el
        # mismo año calendario que el caso que los encuentra.
        with self.cal.sintetica(self.cal.dia(0, 2), 9):
            agotado = self.afiliados[("mutual-del-valle", SIN_CUPO)]
            for numero in (1, 2):
                registrar_consumo_externo(
                    financiador=self.financiadores["mutual-del-valle"],
                    usuario=self.operadores["mutual-del-valle"], afiliado=agotado,
                    prestacion=self.comunes["RXE"], fecha=timezone.localdate(), cantidad=1,
                    referencia="EXT-RXE-%s-%02d" % (agotado.numero, numero),
                )
            self.afiliado_sin_cupo = agotado

    def _finalizar(self, referencia, fecha, motivo):
        slug = referencia[0]
        with self.cal.sintetica(fecha):
            afiliado = self.afiliados[referencia]
            afiliado.finalizado_en = timezone.now()
            afiliado.finalizado_por = self.operadores[slug]
            afiliado.motivo_finalizacion = motivo
            afiliado.save(update_fields=["finalizado_en", "finalizado_por", "motivo_finalizacion"])
            m.HistorialAfiliacion.objects.create(
                afiliado=afiliado, numero=afiliado.numero, documento=afiliado.documento,
                plan=afiliado.plan, desde=timezone.localdate(), registrado_por=self.operadores[slug],
                tipo="finalizacion", motivo=motivo,
            )
            return afiliado

    # ------------------------------------------------------------------ #
    def _agenda_del_mes(self, numero_mes, desplazamiento):
        """Atenciones de un mes: (día nominal, prestación, financiador, paciente, autorización)."""
        mv, osp = "mutual-del-valle", "obra-social-provincial"
        cex_mv = [ROTACION_CEX_MV[(numero_mes * 3 + k) % len(ROTACION_CEX_MV)] for k in range(3)]
        cex_osp = [ROTACION_OSP[(numero_mes * 2 + k) % len(ROTACION_OSP)] for k in range(2)]
        rxe_mv = ROTACION_RXE_MV[numero_mes % len(ROTACION_RXE_MV)]
        rxe_osp = ROTACION_OSP[(numero_mes * 3 + 1) % len(ROTACION_OSP)]
        particular = SIN_COBERTURA[numero_mes % len(SIN_COBERTURA)]
        decision = "rechazar" if desplazamiento in RECHAZOS else "aprobar"
        filas = [
            ("CEX", mv, cex_mv[0], None), ("CEX", osp, cex_osp[0], None),
            ("RXE", mv, rxe_mv, decision), ("CEX", mv, cex_mv[1], None),
            ("RXE", osp, rxe_osp, None), ("CEX", osp, cex_osp[1], None),
            ("CEX", mv, cex_mv[2], None), ("CEX", None, particular, None),
        ]
        if desplazamiento == 0:
            dias = DIAS_EN_CURSO
        elif numero_mes == 0:
            dias = [d for d in DIAS_HISTORIA if d > DIA_PADRON]
        else:
            dias = DIAS_HISTORIA
        return [(dia, *fila) for dia, fila in zip(dias, filas)]

    def _historia(self):
        """Atenciones con cobertura, mes a mes, en el área nueva."""
        self.atenciones = []
        self.autorizaciones_resueltas = {"aprobar": 0, "rechazar": 0}
        for numero_mes, mes in enumerate(self.meses):
            desplazamiento = numero_mes - (CANTIDAD_DE_MESES - 1)
            for dia, codigo, slug, indice, decision in self._agenda_del_mes(numero_mes, desplazamiento):
                afiliado = self.afiliados[(slug, indice)] if slug else None
                hecho = self._atencion(codigo, self.pacientes[indice], mes.replace(day=dia),
                                       afiliado=afiliado, slug=slug, autorizacion=decision)
                self.atenciones.append((mes, codigo, slug, hecho))

    def _resolver_saldos(self):
        """Decide quién se hace cargo de la parte no cubierta.

        El sistema NO convierte automáticamente en deuda del paciente lo que el
        financiador no cubre: deja la distribución pendiente y espera una
        decisión administrativa con su respaldo. Los meses pasados quedan
        resueltos; el mes en curso queda pendiente a propósito, que es la bandeja
        real de trabajo. Una del mes anterior la asume el hospital, para que se
        vea que «resuelto» no quiere decir «se lo cobramos al paciente».
        """
        self.resoluciones = {"aceptadas": 0, "asumidas": 0, "tras_rechazo": 0}
        asumida = False
        actual, anterior = self.cal.mes(0), self.cal.mes(-1)
        for mes, codigo, slug, hecho in self.atenciones:
            if mes == actual:
                continue
            reserva = m.ReservaCobertura.objects.filter(hecho=hecho).first()
            distribucion = m.DistribucionCobro.objects.filter(reserva=reserva).first() if reserva else None
            if not distribucion:
                continue
            momento = timezone.localtime(hecho.ocurrida_en)
            fecha, hora = momento.date(), min(momento.hour + 4, 23)

            if distribucion.estado == "autorizacion_pendiente":
                # La Mutual rechazó la radiografía: la persona acepta abonar
                # también la parte que iba a cubrir el financiador.
                with self.cal.sintetica(fecha, hora):
                    resolver_saldo(
                        reserva=reserva, usuario=self.admin, decision="paciente",
                        importe=distribucion.importe_financiador, parte="financiador",
                        motivo="Autorización rechazada por el financiador; la persona acepta abonar la prestación.",
                        evidencia="Conformidad firmada tras el rechazo %s-%s." % (codigo, reserva.pk),
                        clave=clave("rechazo-%s" % reserva.pk),
                    )
                self.resoluciones["tras_rechazo"] += 1
                distribucion.refresh_from_db()

            if distribucion.estado != "pendiente" or distribucion.importe_paciente <= 0:
                continue
            if not asumida and mes == anterior:
                with self.cal.sintetica(fecha, hora):
                    resolver_saldo(
                        reserva=reserva, usuario=self.admin, decision="asumir",
                        importe=distribucion.importe_paciente,
                        motivo="El hospital asume el saldo por continuidad de tratamiento.",
                        clave=clave("asume-%s" % reserva.pk),
                    )
                self.resoluciones["asumidas"] += 1
                asumida = True
                continue
            with self.cal.sintetica(fecha, hora):
                resolver_saldo(
                    reserva=reserva, usuario=self.admin, decision="paciente",
                    importe=distribucion.importe_paciente,
                    motivo="La persona aceptó abonar el saldo no cubierto.",
                    evidencia="Conformidad firmada %s-%s en admisión." % (codigo, reserva.pk),
                    clave=clave("acepta-%s" % reserva.pk),
                )
            self.resoluciones["aceptadas"] += 1

    def _pagos(self):
        """Cobra los meses pasados; el mes en curso queda adeudado a propósito."""
        self.cobrado = Decimal("0")
        actual = self.cal.mes(0)
        for mes, codigo, slug, hecho in self.atenciones:
            if mes == actual:
                continue
            for obligacion in ObligacionFinanciera.objects.filter(hecho=hecho, tipo="cobrar"):
                self._movimiento(obligacion, timezone.localtime(hecho.ocurrida_en).date(), codigo)
                self.cobrado += obligacion.importe_original

    def _solicitar(self, caso, codigo, momento, detalle):
        """La administrativa pide la autorización previa desde el caso."""
        # El intento se deriva de `paso_desde`, que el motor actualiza en la base
        # al avanzar: con la instancia en memoria saldría el de un paso anterior.
        caso.refresh_from_db()
        with self.cal.sintetica(*momento):
            return autorizaciones.solicitar(
                caso=caso, prestacion=self.prestaciones[codigo], usuario=self.administrativa,
                intento=autorizaciones.intento_actual(caso), cantidad=1,
                justificacion=detalle, clave=clave("solicita-%s" % caso.pk),
            )

    def _responder(self, solicitud, slug, decision, momento):
        """El financiador responde dentro del plazo del convenio."""
        motivos = {
            "aprobar": "Indicación médica consistente con el plan.",
            "rechazar": "La práctica no está justificada con la documentación enviada.",
            "observar": "Falta la orden médica firmada con diagnóstico presuntivo.",
        }
        with self.cal.sintetica(*momento):
            extra = {}
            if decision == "aprobar":
                hoy = timezone.localdate()
                extra = dict(cantidad_aprobada=1, vigencia_desde=hoy, vigencia_hasta=hoy + timedelta(days=30),
                             evidencia="Orden médica y pedido de la práctica verificados.",
                             numero_externo="AUT-%s-%05d" % (self.financiadores[slug].pk, solicitud.pk))
            return autorizaciones.resolver(
                solicitud=solicitud, usuario=self.resolutores[slug], revision=solicitud.revision,
                decision=decision, motivo=motivos[decision],
                clave=clave("responde-%s-%s" % (solicitud.pk, decision)), **extra,
            )

    def _atencion(self, codigo, paciente, fecha, afiliado=None, slug=None, autorizacion=None):
        with self.cal.sintetica(fecha):
            caso = Caso.objects.create(
                institucion=self.institucion, version=self.versiones[codigo],
                ciudadano=paciente, area_actual=self.area, asignado_a=self.medico,
            )
            motor.iniciar(caso, autor=self.administrativa)
            if afiliado is not None:
                seleccionar_afiliacion(
                    caso=caso, usuario=self.administrativa, afiliado=afiliado,
                    motivo="Afiliación verificada contra el padrón al admitir.",
                )
            else:
                seleccionar_afiliacion(
                    caso=caso, usuario=self.administrativa, particular=True,
                    motivo="La persona declara no tener cobertura.",
                )
        if autorizacion:
            solicitud = self._solicitar(caso, codigo, (fecha, 10, 5), "Radiografía de control solicitada por el profesional tratante.")
            self._responder(solicitud, slug, autorizacion, (fecha, 10, 40))
            self.autorizaciones_resueltas[autorizacion] += 1
        with self.cal.sintetica(fecha, 11):
            textos = {
                "CEX": "Consulta ambulatoria programada. Paciente estable; se acuerdan pautas de control.",
                "RXE": "Radiografía ambulatoria realizada. Informe disponible para el profesional solicitante.",
            }
            motor.avanzar(
                caso,
                {"titulo": self.prestaciones[codigo].nombre, "contenido": textos[codigo], "firmada": True},
                autor=self.medico,
            )
            hecho = HechoAtencionCosteable.objects.get(caso=caso)
            procesar_hecho_atencion(hecho.pk)
            return hecho

    def _movimiento(self, obligacion, fecha, codigo):
        # El financiador liquida a mes vencido; el paciente paga en el momento.
        dia = fecha.day if es_de_paciente(obligacion) else min(fecha.day + 25, 28)
        efectiva = fecha.replace(day=max(dia, fecha.day))
        with self.cal.sintetica(efectiva, 15):
            real = timezone.localdate()
            return registrar_movimiento(
                obligacion=obligacion, importe=dinero(obligacion.importe_original), fecha=real,
                clave=clave("mov-%s" % obligacion.pk), usuario=self.admin,
                referencia="LIQ-%s-%s-%s" % (real.strftime("%Y%m%d"), codigo, obligacion.pk),
                aprobado=True,
            )

    # ------------------------------------------------------------------ #
    def _en_curso(self):
        """Deja casos abiertos para mostrar la evaluación en vivo, sin cerrarlos."""
        self.en_curso = []
        pendientes = (
            # (prestación, índice de paciente, financiador, reservar)
            ("CEX", EN_CURSO_CEX_MV, "mutual-del-valle", True),
            ("RXE", SIN_CUPO, "mutual-del-valle", False),   # sin cupo: consumido afuera
            ("CEX", EN_CURSO_CEX_OSP, "obra-social-provincial", False),
        )
        presente = self.cal.dia(0, 15)
        with self.cal.sintetica(presente, 9):
            for codigo, indice, slug, con_reserva in pendientes:
                caso = self._abrir(codigo, indice, slug)
                reserva = None
                if con_reserva:
                    datos = dict(
                        caso=caso, prestacion=self.prestaciones[codigo],
                        fecha=timezone.localdate(), cantidad=1,
                    )
                    presentada = cotizacion(**datos)
                    # `acepta=True` registra que la persona aceptó el copago
                    # ANTES de realizar la prestación. Es una decisión suya, no
                    # un trámite del hospital.
                    reserva = reservar(
                        **datos, usuario=self.administrativa, clave=uuid4(),
                        firma=presentada["firma"], acepta=True,
                    )
                self.en_curso.append((caso, codigo, slug, reserva))

        # Autorizaciones abiertas. Se piden en las últimas horas porque el
        # convenio da 48 para responder: vencido el plazo, el financiador ya no
        # puede resolverlas y `correr_tiempos` las marca vencidas.
        self.autorizaciones_abiertas = []
        for indice in AUTORIZACION_PENDIENTE:
            with self.cal.sintetica(presente, 8):
                caso = self._abrir("RXE", indice, "mutual-del-valle")
            solicitud = self._solicitar(caso, "RXE", (presente, 8, 30), "Radiografía de tórax por tos persistente de tres semanas.")
            self.autorizaciones_abiertas.append(solicitud)
        with self.cal.sintetica(self.cal.dia(0, 14), 9):
            caso = self._abrir("RXE", AUTORIZACION_OBSERVADA, "mutual-del-valle")
        solicitud = self._solicitar(caso, "RXE", (self.cal.dia(0, 14), 9, 30), "Control radiológico posterior a neumonía.")
        self.autorizaciones_abiertas.append(self._responder(solicitud, "mutual-del-valle", "observar", (self.cal.dia(0, 14), 15)))

    def _abrir(self, codigo, indice, slug):
        caso = Caso.objects.create(
            institucion=self.institucion, version=self.versiones[codigo],
            ciudadano=self.pacientes[indice], area_actual=self.area, asignado_a=self.medico,
        )
        motor.iniciar(caso, autor=self.administrativa)
        seleccionar_afiliacion(
            caso=caso, usuario=self.administrativa, afiliado=self.afiliados[(slug, indice)],
            motivo="Afiliación verificada contra el padrón al admitir.",
        )
        return caso

    # ------------------------------------------------------------------ #
    def _verificar_y_resumir(self):
        cobertura = ObligacionFinanciera.objects.filter(
            hecho__institucion=self.institucion, hecho__area=self.area, tipo="cobrar",
        )
        de_paciente = [o for o in cobertura if es_de_paciente(o)]
        de_financiador = [o for o in cobertura if not es_de_paciente(o)]
        if not de_financiador:
            raise CommandError(
                "No se generó ninguna obligación a cargo de un financiador; se revierte la carga."
            )
        solicitudes = m.SolicitudAutorizacion.objects.filter(institucion=self.institucion)
        por_estado = {estado: solicitudes.filter(estado=estado).count() for estado, _ in m.SolicitudAutorizacion.ESTADOS}
        esperado = {"pendiente": len(AUTORIZACION_PENDIENTE), "observada": 1, "rechazada": len(RECHAZOS),
                    "aprobada": self.autorizaciones_resueltas["aprobar"]}
        if any(por_estado[estado] != cantidad for estado, cantidad in esperado.items()):
            raise CommandError("Las autorizaciones no quedaron como se esperaba (%s); se revierte la carga." % por_estado)
        por_slug = {d["slug"]: d for d in FINANCIADORES}
        actual = self.cal.mes(0)
        return {
            "escenario": "Financiadores sobre una institución ya cargada",
            "institucion": {"id": self.institucion.pk, "nombre": self.institucion.nombre},
            "periodos": [str(mes) for mes in self.meses],
            "area_nueva": {
                "id": self.area.pk, "nombre": self.area.nombre,
                "nota": "Sin gastos ni reglas de reparto: no altera los importes por atención anteriores.",
            },
            "financiadores": [
                {
                    "id": financiador.pk, "nombre": financiador.nombre, "tipo": financiador.tipo,
                    "plan": self.planes[slug].codigo,
                    "convenio": self.convenios[slug].estado,
                    "afiliados": m.Afiliado.objects.filter(financiador=financiador).count(),
                    "portal": list(m.MembresiaFinanciador.objects.filter(financiador=financiador)
                                   .order_by("id").values_list("usuario__email", flat=True)),
                }
                for slug, financiador in self.financiadores.items()
            ],
            "atenciones_con_cobertura": sum(1 for _, _, slug, _ in self.atenciones if slug),
            "atenciones_particulares": sum(1 for _, _, slug, _ in self.atenciones if not slug),
            "cargos": {
                "a_financiadores": {
                    "cantidad": len(de_financiador),
                    "importe": str(sum((o.importe_original for o in de_financiador), Decimal("0"))),
                },
                "a_pacientes": {
                    "cantidad": len(de_paciente),
                    "importe": str(sum((o.importe_original for o in de_paciente), Decimal("0"))),
                },
                "nota": "El mes en curso queda sin liquidar a propósito: es la deuda viva del financiador.",
            },
            "autorizaciones": por_estado,
            "resolucion_de_saldos": {
                "aceptados_por_el_paciente": self.resoluciones["aceptadas"],
                "asumidos_por_el_hospital": self.resoluciones["asumidas"],
                "pagados_por_el_paciente_tras_rechazo": self.resoluciones["tras_rechazo"],
                "pendientes": m.DistribucionCobro.objects.filter(reserva__caso__institucion=self.institucion, estado="pendiente").count(),
                "pendientes_de_autorizacion": m.DistribucionCobro.objects.filter(
                    reserva__caso__institucion=self.institucion, estado="autorizacion_pendiente").count(),
                "nota": "Lo no cubierto no se convierte solo en deuda del paciente: espera una decisión.",
            },
            "cobrado_meses_anteriores": str(self.cobrado),
            "atenciones_mes_en_curso": sum(1 for mes, *_ in self.atenciones if mes == actual),
            "padron_con_historia": {
                "dado_de_baja": self.afiliado_dado_de_baja.numero,
                "reactivado": self.afiliado_reactivado.numero,
                "sin_cupo_por_consumo_externo": self.afiliado_sin_cupo.numero,
            },
            "convenio_propuesto": {
                slug: self.convenios[slug].pk for slug, datos in por_slug.items() if datos["convenio"] == "propuesto"
            },
            "casos_abiertos_para_mostrar_en_vivo": [
                {
                    "caso": caso.pk, "prestacion": codigo,
                    "financiador": self.financiadores[slug].nombre,
                    "reserva": reserva.pk if reserva else None,
                    "paciente": ("%s %s" % (caso.ciudadano.nombre, caso.ciudadano.apellido)).strip(),
                }
                for caso, codigo, slug, reserva in self.en_curso
            ],
            "autorizaciones_abiertas": [
                {"solicitud": s.pk, "caso": s.caso_id, "estado": s.estado,
                 "paciente": ("%s %s" % (s.caso.ciudadano.nombre, s.caso.ciudadano.apellido)).strip()}
                for s in self.autorizaciones_abiertas
            ],
            "no_incluye": [
                "Facturación fiscal, conciliación bancaria y transferencias reales",
                "Personas, convenios o aranceles tomados de organizaciones reales",
                "Historia clínica compartida con el financiador",
            ],
        }
