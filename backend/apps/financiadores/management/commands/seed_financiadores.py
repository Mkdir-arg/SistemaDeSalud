"""Escenario ficticio de financiadores; nunca se ejecuta al iniciar la aplicación.

Monta el circuito de cobertura —obras sociales, planes, reglas, convenios,
aranceles acordados, padrón, consumos externos y atenciones con copago— SOBRE
una institución ya sembrada, sin tocar sus datos anteriores.

Por qué un área nueva y no las existentes
-----------------------------------------
Las atenciones nuevas entran en un área propia («Consultorios externos») creada
por este comando. No es una decisión estética: el reparto distribuye cada gasto
entre las atenciones elegibles DE SU ÁREA, así que sumar atenciones a un área con
gastos repartidos le cambia la porción a todas las demás. En Los Aromos eso
reescribiría en silencio las cifras por atención ya verificadas y documentadas.
El área nueva no tiene gastos ni reglas de reparto, así que no entra en ningún
reparto existente y los importes anteriores quedan intactos.

Requiere una base PostgreSQL migrada, la institución destino ya sembrada, que no
exista ningún financiador, --confirmar ESCENARIO_FINANCIADORES y
DEMO_FINANCIADORES_PASSWORD. No borra ni actualiza datos clínicos ni económicos
previos. La cronología simulada sólo vive dentro de esta carga.
"""
import json
import os
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from uuid import NAMESPACE_URL, uuid4, uuid5

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone

from apps.accounts.models import LegajoProfesional, Membresia, Usuario
from apps.casos import motor
from apps.casos.models import Caso
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
from apps.financiadores.cobertura import cotizacion, reservar, seleccionar_afiliacion
from apps.financiadores.cobros import resolver_saldo
from apps.financiadores.services import registrar_afiliado, registrar_consumo_externo


CONFIRMACION = "ESCENARIO_FINANCIADORES"
INSTITUCION_POR_DEFECTO = "Hospital General Los Aromos"
CENTAVOS = Decimal("0.01")

# La historia va de julio a septiembre de 2026. Septiembre queda IMPAGO a
# propósito: es el caso real —la obra social todavía no liquidó— y es lo que
# permite mostrar deuda de financiador separada del copago del paciente.
MESES = (date(2026, 7, 1), date(2026, 8, 1), date(2026, 9, 1))
MES_SIN_PAGO = date(2026, 9, 1)
VIGENCIA = date(2026, 6, 15)

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
    },
)

# Personas propias del área nueva. Ficticias, como todo el escenario.
PERSONAS = (
    ("Rosa", "Maidana"), ("Ernesto", "Bogado"), ("Silvina", "Alegre"),
    ("Gustavo", "Ramallo"), ("Noelia", "Cáceres"), ("Ariel", "Domínguez"),
    ("Mirta", "Zalazar"), ("Fabián", "Leguizamón"), ("Carina", "Ojeda"),
    ("Rubén", "Maldonado"), ("Andrea", "Paniagua"), ("Claudio", "Insaurralde"),
    ("Viviana", "Escalante"), ("Marcelo", "Aguirre"), ("Susana", "Barrios"),
)

# Reparto del padrón sobre esas personas, por orden de alta. Las que no figuran
# quedan sin cobertura: ese estado también hay que poder mostrarlo.
PADRON = {
    "mutual-del-valle": (0, 1, 2, 3, 4, 5, 6),
    "obra-social-provincial": (7, 8, 9, 10, 11),
}

# (índice de mes, día, prestación, financiador, índice de paciente)
AGENDA = (
    (0, 7, "CEX", "mutual-del-valle", 0),
    (0, 9, "CEX", "obra-social-provincial", 7),
    (0, 14, "CEX", "mutual-del-valle", 1),
    (0, 16, "RXE", "obra-social-provincial", 8),
    (0, 21, "CEX", "mutual-del-valle", 2),
    (0, 23, "CEX", "obra-social-provincial", 9),
    (1, 4, "CEX", "mutual-del-valle", 0),
    (1, 6, "RXE", "mutual-del-valle", 1),
    (1, 11, "CEX", "obra-social-provincial", 7),
    (1, 13, "CEX", "mutual-del-valle", 4),
    (1, 18, "CEX", "obra-social-provincial", 8),
    (1, 20, "RXE", "obra-social-provincial", 9),
    (1, 25, "CEX", "mutual-del-valle", 5),
    (2, 3, "CEX", "mutual-del-valle", 0),
    (2, 4, "CEX", "obra-social-provincial", 7),
    (2, 8, "RXE", "mutual-del-valle", 2),
    (2, 9, "CEX", "mutual-del-valle", 1),
    (2, 10, "CEX", "obra-social-provincial", 10),
    (2, 11, "CEX", "mutual-del-valle", 4),
)


def dinero(valor):
    return Decimal(str(valor)).quantize(CENTAVOS)


def clave(texto):
    return uuid5(NAMESPACE_URL, "financiadores/20260917/" + texto)


@contextmanager
def fecha_sintetica(fecha, hora=10):
    """Ordena fixtures históricas, sin hacer backfills en servicios productivos."""
    instante = timezone.make_aware(datetime.combine(fecha, datetime.min.time()).replace(hour=hora))
    # Nunca dejar registros con marcas posteriores a esta corrida.
    instante = min(instante, timezone.now())
    with patch("django.utils.timezone.now", return_value=instante):
        yield instante


class Command(BaseCommand):
    help = "Carga un escenario ficticio de financiadores sobre una institución ya sembrada."

    def add_arguments(self, parser):
        parser.add_argument("--confirmar", required=True)
        parser.add_argument("--institucion", type=int, default=None,
                            help="Id de la institución destino. Por defecto, la de Los Aromos.")
        parser.add_argument("--salida", help="Archivo JSON nuevo con el manifiesto; nunca sobrescribe otro.")

    def handle(self, *args, **options):
        if options["confirmar"] != CONFIRMACION:
            raise CommandError("Confirmación incorrecta; no se modificó ningún dato.")
        password = os.environ.get("DEMO_FINANCIADORES_PASSWORD", "")
        if len(password) < 12:
            raise CommandError("Definí DEMO_FINANCIADORES_PASSWORD con al menos 12 caracteres; no se imprime.")
        if connection.vendor != "postgresql":
            raise CommandError("La carga requiere PostgreSQL para verificar transacciones y bloqueo exclusivo.")
        salida = Path(options["salida"]).resolve() if options.get("salida") else None
        if salida and (salida.exists() or not salida.parent.is_dir()):
            raise CommandError("La salida debe ser un archivo nuevo dentro de un directorio existente.")

        with transaction.atomic():
            # Dos invocaciones no pueden observar simultáneamente la misma base.
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(%s)", [2026091701])
            if m.Financiador.objects.exists():
                raise CommandError("Ya hay financiadores cargados. No se borra, mezcla ni duplica el escenario.")
            self._institucion(options.get("institucion"))
            self._configurar(password)
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
                    "No existe «%s». Sembrala primero o indicá --institucion." % INSTITUCION_POR_DEFECTO
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
        self.afiliados = {}

        with fecha_sintetica(VIGENCIA) as desde:
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
                "irene.bustos@losaromos.test", password, nombre="Irene Bustos",
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
                    importe=dinero(arancel), contraparte_nombre="",
                    contraparte_referencia="Arancel general de consultorios externos",
                )
                # El catálogo común es lo que permite que un hospital y un
                # financiador hablen de la misma prestación.
                comun = m.PrestacionComun.objects.create(codigo=codigo, nombre=titulo, categoria=categoria)
                m.VinculoPrestacion.objects.create(prestacion=prestacion, comun=comun)
                self.comunes[codigo] = comun

            self._pacientes()
            for datos in FINANCIADORES:
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
        for indice, (nombre, apellido) in enumerate(PERSONAS, 1):
            self.pacientes.append(Ciudadano.objects.create(
                institucion=self.institucion, nombre=nombre, apellido=apellido,
                codigo="LA-CEX-%04d" % indice, documento="FIC1%05d" % indice,
                fecha_nacimiento=date(1958 + (indice * 5) % 45, 1 + indice % 12, 1 + indice % 27),
            ))

    def _financiador(self, datos, password, desde):
        slug = datos["slug"]
        financiador = m.Financiador.objects.create(nombre=datos["nombre"], tipo=datos["tipo"])
        self.financiadores[slug] = financiador

        # Un administrador que opera el portal y un auditor de sólo lectura: el
        # portal no es una sola cuenta que puede todo.
        admin_portal = Usuario.objects.create_user(
            "admin@" + datos["dominio"], password, nombre="Administración · " + datos["nombre"],
        )
        m.MembresiaFinanciador.objects.create(
            financiador=financiador, usuario=admin_portal, rol="admin", resuelve_autorizaciones=True,
        )
        auditor_portal = Usuario.objects.create_user(
            "auditor@" + datos["dominio"], password, nombre="Auditoría · " + datos["nombre"],
        )
        m.MembresiaFinanciador.objects.create(
            financiador=financiador, usuario=auditor_portal, rol="auditor",
        )
        self.operadores[slug] = admin_portal

        self.planes[slug] = m.Plan.objects.create(
            financiador=financiador, codigo=datos["plan_codigo"], nombre=datos["plan_nombre"],
        )
        self.convenios[slug] = m.Convenio.objects.create(
            financiador=financiador, institucion=self.institucion, estado="activo",
            propuesto_por="financiador", creado_por=admin_portal,
            aceptado_por=self.admin, aceptado_en=desde, plazo_autorizacion_horas=48,
        )
        for codigo, (porcentaje, cupo, periodo, autorizacion) in datos["reglas"].items():
            m.ReglaCobertura.objects.create(
                financiador=financiador, plan=self.planes[slug], prestacion=self.comunes[codigo],
                porcentaje=Decimal(porcentaje), cupo=cupo, periodo=periodo,
                vigente_desde=VIGENCIA, requiere_autorizacion=autorizacion, creado_por=admin_portal,
            )
        for codigo, importe in datos.get("aranceles", {}).items():
            m.ArancelConvenio.objects.create(
                convenio=self.convenios[slug], prestacion=self.prestaciones[codigo],
                importe=dinero(importe), vigente_desde=VIGENCIA, creado_por=self.admin,
            )

    # ------------------------------------------------------------------ #
    def _padron(self):
        """Afiliaciones sobre personas ya registradas, con historia de vigencias."""
        with fecha_sintetica(date(2026, 6, 20)):
            for slug, indices in PADRON.items():
                prefijo = "MV" if slug == "mutual-del-valle" else "OSP"
                for orden, indice in enumerate(indices, 1):
                    paciente = self.pacientes[indice]
                    afiliado = registrar_afiliado(
                        financiador=self.financiadores[slug], usuario=self.operadores[slug],
                        numero="%s%05d" % (prefijo, orden), documento=paciente.documento,
                        nombre=("%s %s" % (paciente.nombre, paciente.apellido)).strip(),
                        plan=self.planes[slug], desde=date(2026, 6, 20),
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
            ("obra-social-provincial", 11), date(2026, 8, 10),
            "Cese de la relación laboral informada por el empleador.",
        )
        self.afiliado_reactivado = self._finalizar(
            ("mutual-del-valle", 6), date(2026, 8, 25),
            "Falta de pago informada por la mutual.",
        )
        with fecha_sintetica(date(2026, 9, 2)):
            vuelve = self.afiliado_reactivado
            vuelve.finalizado_en, vuelve.finalizado_por, vuelve.motivo_finalizacion = None, None, ""
            vuelve.save(update_fields=["finalizado_en", "finalizado_por", "motivo_finalizacion"])
            m.HistorialAfiliacion.objects.create(
                afiliado=vuelve, numero=vuelve.numero, documento=vuelve.documento, plan=vuelve.plan,
                desde=date(2026, 9, 2), registrado_por=self.operadores["mutual-del-valle"],
                tipo="reactivacion", motivo="Regularización de aportes verificada por la mutual.",
            )

        # Consumos en otros prestadores: gastan cupo sin que el hospital los vea
        # en su propia actividad. Es la causa más común de «creí que estaba
        # cubierto y no lo estaba».
        with fecha_sintetica(date(2026, 7, 5)):
            agotado = self.afiliados[("mutual-del-valle", 3)]
            for numero in (1, 2):
                registrar_consumo_externo(
                    financiador=self.financiadores["mutual-del-valle"],
                    usuario=self.operadores["mutual-del-valle"], afiliado=agotado,
                    prestacion=self.comunes["RXE"], fecha=date(2026, 7, 5), cantidad=1,
                    referencia="EXT-RXE-%s-%02d" % (agotado.numero, numero),
                )
            self.afiliado_sin_cupo = agotado

    def _finalizar(self, referencia, fecha, motivo):
        slug = referencia[0]
        with fecha_sintetica(fecha):
            afiliado = self.afiliados[referencia]
            afiliado.finalizado_en = timezone.now()
            afiliado.finalizado_por = self.operadores[slug]
            afiliado.motivo_finalizacion = motivo
            afiliado.save(update_fields=["finalizado_en", "finalizado_por", "motivo_finalizacion"])
            m.HistorialAfiliacion.objects.create(
                afiliado=afiliado, numero=afiliado.numero, documento=afiliado.documento,
                plan=afiliado.plan, desde=fecha, registrado_por=self.operadores[slug],
                tipo="finalizacion", motivo=motivo,
            )
            return afiliado

    # ------------------------------------------------------------------ #
    def _historia(self):
        """Atenciones con cobertura, mes a mes, en el área nueva."""
        self.atenciones = []
        for indice_mes, dia, codigo, slug, indice_paciente in AGENDA:
            mes = MESES[indice_mes]
            fecha = mes.replace(day=dia)
            hecho = self._atencion(
                codigo, self.pacientes[indice_paciente], fecha,
                afiliado=self.afiliados[(slug, indice_paciente)],
            )
            self.atenciones.append((fecha, codigo, slug, hecho))

        # Una atención particular, sin cobertura: la comparación hace visible qué
        # aporta el convenio.
        self.hecho_particular = self._atencion("CEX", self.pacientes[14], date(2026, 9, 12), afiliado=None)

    def _resolver_saldos(self):
        """Decide quién se hace cargo de la parte no cubierta.

        El sistema NO convierte automáticamente en deuda del paciente lo que el
        financiador no cubre: deja la distribución pendiente y espera una
        decisión administrativa con su respaldo. Julio y agosto quedan resueltos;
        septiembre queda pendiente a propósito, que es la bandeja real de
        trabajo. Una de agosto la asume el hospital, para que se vea que
        «resuelto» no quiere decir «se lo cobramos al paciente».
        """
        self.resoluciones = {"aceptadas": 0, "asumidas": 0, "autorizadas": 0}
        asumida = False
        for fecha, codigo, slug, hecho in self.atenciones:
            reserva = m.ReservaCobertura.objects.filter(hecho=hecho).first()
            if not reserva:
                continue
            distribucion = m.DistribucionCobro.objects.filter(reserva=reserva).first()
            if not distribucion:
                continue
            if fecha.replace(day=1) == MES_SIN_PAGO:
                continue

            if distribucion.estado == "autorizacion_pendiente":
                # La mutual autorizó la práctica dentro del plazo del convenio.
                with fecha_sintetica(fecha, 16):
                    resolver_saldo(
                        reserva=reserva, usuario=self.admin, decision="financiador",
                        importe=distribucion.importe_financiador, parte="financiador",
                        motivo="Autorización otorgada por el financiador dentro del plazo del convenio.",
                        evidencia="Autorización %s-%s registrada por la mutual." % (codigo, reserva.pk),
                        clave=clave("aut-%s" % reserva.pk),
                    )
                self.resoluciones["autorizadas"] += 1
                distribucion.refresh_from_db()

            if distribucion.estado != "pendiente" or distribucion.importe_paciente <= 0:
                continue
            if not asumida and fecha.replace(day=1) == date(2026, 8, 1):
                with fecha_sintetica(fecha, 16):
                    resolver_saldo(
                        reserva=reserva, usuario=self.admin, decision="asumir",
                        importe=distribucion.importe_paciente,
                        motivo="El hospital asume el saldo por continuidad de tratamiento.",
                        clave=clave("asume-%s" % reserva.pk),
                    )
                self.resoluciones["asumidas"] += 1
                asumida = True
                continue
            with fecha_sintetica(fecha, 16):
                resolver_saldo(
                    reserva=reserva, usuario=self.admin, decision="paciente",
                    importe=distribucion.importe_paciente,
                    motivo="La persona aceptó abonar el saldo no cubierto.",
                    evidencia="Conformidad firmada %s-%s en admisión." % (codigo, reserva.pk),
                    clave=clave("acepta-%s" % reserva.pk),
                )
            self.resoluciones["aceptadas"] += 1

    def _pagos(self):
        """Cobra lo de julio y agosto; septiembre queda adeudado a propósito."""
        self.cobrado = Decimal("0")
        for fecha, codigo, slug, hecho in self.atenciones:
            if fecha.replace(day=1) == MES_SIN_PAGO:
                continue
            for obligacion in ObligacionFinanciera.objects.filter(hecho=hecho, tipo="cobrar"):
                self._movimiento(obligacion, fecha, codigo)
                self.cobrado += obligacion.importe_original

    def _atencion(self, codigo, paciente, fecha, afiliado=None):
        with fecha_sintetica(fecha):
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
        dia = min(fecha.day + 25, 28) if obligacion.contraparte_nombre else fecha.day
        efectiva = min(fecha.replace(day=dia), date(2026, 9, 15))
        with fecha_sintetica(efectiva, 15):
            return registrar_movimiento(
                obligacion=obligacion, importe=dinero(obligacion.importe_original), fecha=efectiva,
                clave=clave("mov-%s" % obligacion.pk), usuario=self.admin,
                referencia="LIQ-%s-%s-%s" % (efectiva.strftime("%Y%m%d"), codigo, obligacion.pk),
                aprobado=True,
            )

    # ------------------------------------------------------------------ #
    def _en_curso(self):
        """Deja casos abiertos para mostrar la evaluación en vivo, sin cerrarlos."""
        self.en_curso = []
        pendientes = (
            # (prestación, índice de paciente, financiador, reservar)
            ("CEX", 1, "mutual-del-valle", True),
            ("RXE", 3, "mutual-del-valle", False),   # sin cupo: consumido afuera
            ("CEX", 10, "obra-social-provincial", False),
        )
        with fecha_sintetica(date(2026, 9, 15), 9):
            for codigo, indice, slug, con_reserva in pendientes:
                caso = Caso.objects.create(
                    institucion=self.institucion, version=self.versiones[codigo],
                    ciudadano=self.pacientes[indice], area_actual=self.area, asignado_a=self.medico,
                )
                motor.iniciar(caso, autor=self.administrativa)
                seleccionar_afiliacion(
                    caso=caso, usuario=self.administrativa, afiliado=self.afiliados[(slug, indice)],
                    motivo="Afiliación verificada contra el padrón al admitir.",
                )
                reserva = None
                if con_reserva:
                    datos = dict(
                        caso=caso, prestacion=self.prestaciones[codigo],
                        fecha=date(2026, 9, 15), cantidad=1,
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

    # ------------------------------------------------------------------ #
    def _verificar_y_resumir(self):
        cobertura = ObligacionFinanciera.objects.filter(
            hecho__institucion=self.institucion, hecho__area=self.area, tipo="cobrar",
        )
        de_financiador = cobertura.exclude(contraparte_nombre="")
        de_paciente = cobertura.filter(contraparte_nombre="")
        if not de_financiador.exists():
            raise CommandError(
                "No se generó ninguna obligación a cargo de un financiador; se revierte la carga."
            )
        por_slug = {d["slug"]: d for d in FINANCIADORES}
        return {
            "escenario": "Financiadores sobre una institución ya sembrada",
            "institucion": {"id": self.institucion.pk, "nombre": self.institucion.nombre},
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
                    "portal": [
                        "admin@" + por_slug[slug]["dominio"],
                        "auditor@" + por_slug[slug]["dominio"],
                    ],
                }
                for slug, financiador in self.financiadores.items()
            ],
            "atenciones_con_cobertura": len(self.atenciones),
            "atencion_particular_comparativa": self.hecho_particular.pk,
            "cargos": {
                "a_financiadores": {
                    "cantidad": de_financiador.count(),
                    "importe": str(sum((o.importe_original for o in de_financiador), Decimal("0"))),
                },
                "copagos_de_pacientes": {
                    "cantidad": de_paciente.count(),
                    "importe": str(sum((o.importe_original for o in de_paciente), Decimal("0"))),
                },
                "nota": "Septiembre queda sin liquidar a propósito: es la deuda viva del financiador.",
            },
            "resolucion_de_saldos": {
                "aceptados_por_el_paciente": self.resoluciones["aceptadas"],
                "asumidos_por_el_hospital": self.resoluciones["asumidas"],
                "autorizaciones_otorgadas": self.resoluciones["autorizadas"],
                "pendientes": m.DistribucionCobro.objects.filter(estado="pendiente").count(),
                "pendientes_de_autorizacion": m.DistribucionCobro.objects.filter(
                    estado="autorizacion_pendiente").count(),
                "nota": "Lo no cubierto no se convierte solo en deuda del paciente: espera una decisión.",
            },
            "cobrado_julio_agosto": str(self.cobrado),
            "padron_con_historia": {
                "dado_de_baja": self.afiliado_dado_de_baja.numero,
                "reactivado": self.afiliado_reactivado.numero,
                "sin_cupo_por_consumo_externo": self.afiliado_sin_cupo.numero,
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
            "no_incluye": [
                "Facturación fiscal, conciliación bancaria y transferencias reales",
                "Personas, convenios o aranceles tomados de organizaciones reales",
                "Historia clínica compartida con el financiador",
            ],
        }
