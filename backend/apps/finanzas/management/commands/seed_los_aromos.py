"""Finanzas y costos de un hospital ficticio: Hospital General Los Aromos.

Qué carga
---------
Un año de operación económica de tres servicios ambulatorios —Clínica médica,
Cardiología y Diagnóstico por imágenes—: atenciones costeadas, gastos mensuales
con su reparto, cuentas por pagar y por cobrar, y sus pagos. Todo sobre los doce
meses que terminan hoy (ver `apps.demo.calendario`).

El mes en curso es el *presente* del escenario, y el que Finanzas abre por
defecto. Deja trabajo pendiente para cada rol:

- un gasto por aprobar y un ajuste de gasto por aprobar (administración);
- un pago y un cobro registrados por la administrativa, esperando aprobación;
- una atención sin responsable de pago (la administrativa);
- un componente de costo sin valor (el configurador);
- el mes sin la carga de gastos confirmada;
- un caso abierto por profesional.

El mes anterior tiene la electricidad pagada en dos partes, la segunda ya en el
mes en curso. Hace cinco meses se revisaron los valores de costo y los aranceles.

Requisitos
----------
- PostgreSQL migrado.
- `ENTORNO` distinto de `produccion`.
- Que Los Aromos no esté cargado. Para rehacerlo se vacía la base con
  `seed_entorno_demo`: el escenario no se borra ni se mezcla por partes.

Los usuarios toman la clave de `DEMO_PASSWORD` (ver `apps.demo.claves`).

La cronología simulada sólo vive dentro de esta carga: los servicios productivos
conservan sus validaciones prospectivas e inmutabilidad.
"""
import json
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.db.models import F, Sum

from apps.accounts.models import LegajoProfesional, Membresia, Usuario
from apps.casos import motor
from apps.casos.models import Caso
from apps.demo.calendario import Calendario
from apps.demo.claves import clave_demo
from apps.demo.entorno import exigir_entorno_de_prueba
from apps.flujos.models import Conexion, Flujo, Nodo, VersionFlujo
from apps.instituciones.models import Area, Institucion
from apps.registros.models import Ciudadano
from apps.finanzas.cobros import registrar_politica_cobro, resolver_pendiente_cobro
from apps.finanzas.dinero import (
    crear_obligacion_pago, estado_obligacion, previsualizar_reintegro,
    registrar_movimiento, reintegrar_movimiento,
)
from apps.finanzas.models import (
    AjusteGasto, AtribucionReparto, ConceptoGasto, ConcesionFinanciera,
    DefinicionComponente, Gasto, HechoAtencionCosteable, ImputacionCosto,
    MovimientoDinero, ObligacionFinanciera, PendienteCosteo, Prestacion,
    RepartoGasto, TrabajoReparto, ValorComponente,
)
from apps.finanzas.models_cobros import PendienteCobro, PoliticaCobro
from apps.finanzas.procesamiento import procesar_siguiente
from apps.finanzas.services import (
    indicar_carga_esperada, procesar_hecho_atencion, rechazar_gasto,
    registrar_ajuste_gasto, registrar_cobertura_actividad,
    registrar_expectativa_gasto, registrar_gasto, registrar_regla_reparto,
    verificar_integridad_actividad,
)


NOMBRE = "Hospital General Los Aromos"
# Meses del escenario, por distancia al mes en curso.
ACTUAL, ANTERIOR, REVISION = 0, -1, -5
CANTIDAD_DE_MESES = 12
CENTAVOS = Decimal("0.01")
AREAS = (
    ("CM", "Clínica médica", "Consulta de clínica médica", "Lucía", "Ferreyra", "lucia.ferreyra", "76841", 15000, 1000, 30000),
    ("CAR", "Cardiología", "Consulta cardiológica", "Andrés", "Molina", "andres.molina", "82316", 22000, 1500, 45000),
    ("IMG", "Diagnóstico por imágenes", "Radiografía digital de tórax", "Valeria", "Costa", "valeria.costa", "91427", 7000, 3000, 35000),
)
CONCEPTOS = (
    ("ELEC", "Electricidad", "Cooperativa Eléctrica del Bosque"),
    ("LIMP", "Limpieza de espacios asistenciales", "Higiene Integral del Sur"),
    ("MANT", "Mantenimiento de instalaciones y equipos", "Servicios Técnicos Robles"),
)
# Importes de cada servicio: no se replica una misma factura en tres áreas.
# Son los gastos seleccionados para el recorrido, no el presupuesto hospitalario.
BASES = {"CM": (80000, 80000, 30000), "CAR": (50000, 60000, 25000), "IMG": (100000, 65000, 70000)}
MES_EN_CURSO = {"CM": (120000, 100000, 45000), "CAR": (65000, 85000, 35000), "IMG": (150000, 90000, 60000)}
# Series ficticias explícitas y reproducibles. No son índices económicos ni
# tarifas reales.
#
# La electricidad sigue al CALENDARIO —más consumo en verano y en invierno, por
# la climatización— y se indexa por número de mes. Limpieza y mantenimiento
# siguen a la HISTORIA del escenario —escalones de contrato cada tres meses,
# intervenciones irregulares— y se indexan por posición: el primer mes de la
# serie es el 0, el anterior al actual es el 10.
ELECTRICIDAD_POR_MES = {
    1: "1.30", 2: "1.22", 3: "1.10", 4: "1.06", 5: "1.16", 6: "1.32",
    7: "1.40", 8: "1.30", 9: "1.20", 10: "1.00", 11: "1.05", 12: "1.18",
}
FACTORES_HISTORICOS = {
    "LIMP": ("1.00", "1.00", "1.00", "1.08", "1.08", "1.08", "1.16", "1.16", "1.16", "1.24", "1.24"),
    "MANT": ("1.00", "0.75", "1.30", "0.85", "1.05", "1.55", "0.80", "1.15", "1.40", "0.90", "1.20"),
}
# Atenciones del mes en curso: (día nominal, índice de paciente) por área.
ATENCIONES_DEL_MES = {"CM": ((4, 2), (8, 1), (11, 4)), "CAR": ((10, 0), (11, 6)), "IMG": ((5, 8), (14, 10))}
PACIENTES = (
    ("Clara", "Benítez"), ("Daniel", "Peralta"), ("Julia", "Acosta"),
    ("Roberto", "Ledesma"), ("Inés", "Quiroga"), ("Esteban", "Ponce"),
    ("Marta", "Villalba"), ("Hugo", "Cabrera"), ("Natalia", "Soria"),
    ("Federico", "Almada"), ("Beatriz", "Correa"), ("Julián", "Vera"),
    ("Alicia", "Figueroa"), ("Gabriel", "Pereyra"), ("Cecilia", "Luna"),
    ("Pablo", "Arce"), ("Silvia", "Godoy"), ("Marcos", "Medina"),
    ("Laura", "Oviedo"), ("Sergio", "Páez"), ("Elisa", "Roldán"),
    ("Tomás", "Navarro"), ("Graciela", "Rivero"), ("Diego", "Bustamante"),
    ("Teresa", "Ibarra"), ("Adrián", "Franco"), ("Mónica", "Sosa"),
    ("Ramiro", "Oliva"), ("Patricia", "Bustos"), ("Nicolás", "Agüero"),
)


def dinero(valor):
    return Decimal(str(valor)).quantize(CENTAVOS)


def clave(texto):
    return uuid5(NAMESPACE_URL, f"los-aromos/{texto}")


class Command(BaseCommand):
    help = "Carga las finanzas y costos de Los Aromos: doce meses que terminan hoy."

    def add_arguments(self, parser):
        parser.add_argument("--salida", help="Archivo JSON nuevo para la guía; nunca sobrescribe otro archivo.")

    def handle(self, *args, **options):
        exigir_entorno_de_prueba("seed_los_aromos")
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
                cursor.execute("SELECT pg_advisory_xact_lock(%s)", [2026091501])
            if Institucion.objects.filter(nombre=NOMBRE).exists():
                raise CommandError(
                    "Los Aromos ya está cargado. No se borra, mezcla ni duplica por partes: "
                    "para rehacerlo, corré seed_entorno_demo."
                )
            self._configurar(clave_demo())
            self._historia()
            self._pendientes_y_recorrido()
            with self.cal.sintetica(self.cal.dia(ACTUAL, 15), 8):
                for hecho in HechoAtencionCosteable.objects.filter(institucion=self.institucion).order_by("id"):
                    procesar_hecho_atencion(hecho.pk)
                for _ in range(1000):
                    if not procesar_siguiente():
                        break
                if TrabajoReparto.objects.filter(revision__gt=F("revision_procesada")).exists():
                    raise CommandError("Quedó trabajo de reparto sin completar; se revierte la carga.")
            resumen = self._verificar_y_resumir()
        contenido = json.dumps(resumen, ensure_ascii=False, indent=2, default=str)
        if salida:
            try:
                with salida.open("x", encoding="utf-8") as archivo:
                    archivo.write(contenido + "\n")
            except OSError as error:
                raise CommandError("Los datos se cargaron, pero no se pudo guardar el JSON. No repitas la carga; conservá la base y revisá la salida.") from error
        self.stdout.write(contenido)

    def _usuario(self, nombre, apellido, email, rol, areas, password, acciones=()):
        usuario = Usuario.objects.create_user(f"{email}@losaromos.test", password, nombre=nombre, apellido=apellido)
        membresia = Membresia.objects.create(usuario=usuario, institucion=self.institucion, rol=rol)
        membresia.areas.add(*areas)
        for accion in acciones:
            concesion = ConcesionFinanciera.objects.create(
                membresia=membresia, accion=accion,
                todas_las_areas=rol in (Membresia.Rol.ADMIN_INSTITUCION, Membresia.Rol.CONFIGURADOR),
                permite_sensibles=False,
            )
            if not concesion.todas_las_areas:
                concesion.areas.add(*areas)
        return usuario

    def _configurar(self, password):
        self.areas, self.prestaciones, self.versiones, self.medicos = {}, {}, {}, {}
        self.componentes, self.conceptos, self.expectativas = {}, {}, {}
        self.gastos, self.cuentas, self.hechos = {}, {}, {}
        self.escenarios = {}
        inicio = self.meses[0]
        with self.cal.sintetica(inicio - timedelta(days=2)) as desde:
            self.institucion = Institucion.objects.create(
                nombre=NOMBRE, tipo="Hospital general",
                direccion="Av. de los Eucaliptos 1450 · Villa del Arroyo (localidad ficticia)",
            )
            for codigo, nombre, _, profesional, apellido, *_ in AREAS:
                self.areas[codigo] = Area.objects.create(
                    institucion=self.institucion, nombre=nombre,
                    responsable=f"{profesional} {apellido}",
                    descripcion="Servicio ambulatorio. Todos los datos de este entorno son ficticios.",
                )
            areas = list(self.areas.values())
            self.admin = self._usuario("Elena", "Rivas", "elena.rivas", Membresia.Rol.ADMIN_INSTITUCION,
                                       areas, password, ConcesionFinanciera.Accion.values)
            self.configurador = self._usuario(
                "Mateo", "Salvatierra", "mateo.salvatierra", Membresia.Rol.CONFIGURADOR, areas, password,
                ("ver_gastos", "ver_costos", "configurar_componentes", "configurar_gastos_esperados", "configurar_repartos", "configurar_cobros"),
            )
            self.administrativa = self._usuario(
                "Paula", "Benítez", "paula.benitez", Membresia.Rol.ADMINISTRATIVO, areas, password,
                ("ver_gastos", "registrar_gastos", "ver_dinero", "registrar_dinero"),
            )
            fin_valores = self.cal.instante(self.cal.mes(REVISION), 0)
            for codigo, area_nombre, titulo, nombre, apellido, email, matricula, profesional, insumos, arancel in AREAS:
                area = self.areas[codigo]
                medico = self._usuario(nombre, apellido, email, Membresia.Rol.MEDICO, [area], password)
                LegajoProfesional.objects.create(usuario=medico, especialidad=area_nombre, matricula=matricula)
                self.medicos[codigo] = medico
                flujo = Flujo.objects.create(
                    institucion=self.institucion, area=area, titulo=titulo,
                    descripcion="Ingreso → atención profesional → cierre. La configuración económica es administrativa.",
                )
                version = VersionFlujo.objects.create(flujo=flujo, numero=1, autor=self.configurador)
                inicio_nodo = Nodo.objects.create(version=version, tipo=Nodo.Tipo.INICIO, titulo="Ingreso", x=60, y=150)
                atencion = Nodo.objects.create(version=version, tipo=Nodo.Tipo.ATENCION, titulo=titulo, x=340, y=150)
                fin = Nodo.objects.create(version=version, tipo=Nodo.Tipo.FIN, titulo="Cierre", x=620, y=150)
                Conexion.objects.create(version=version, origen=inicio_nodo, destino=atencion)
                Conexion.objects.create(version=version, origen=atencion, destino=fin)
                errores = [e for e in motor.validar_version(version) if e.get("nivel") == "error"]
                if not motor.puede_publicar(version):
                    raise CommandError(f"Flujo no publicable: {errores}")
                version.estado = VersionFlujo.Estado.PUBLICADA
                version.save(update_fields=["estado"])
                self.versiones[codigo] = version
                prestacion = Prestacion.objects.create(institucion=self.institucion, nodo=atencion, codigo=codigo, nombre=titulo)
                self.prestaciones[codigo] = prestacion
                for orden, (cod, nombre_componente, valor) in enumerate((
                    ("PROF", "Trabajo profesional por atención", profesional),
                    ("INS", "Insumos directos por atención", insumos),
                )):
                    componente = DefinicionComponente.objects.create(
                        prestacion=prestacion, codigo=cod, nombre=nombre_componente, orden=orden,
                    )
                    self.componentes[(codigo, cod)] = componente
                    ValorComponente.objects.create(
                        componente=componente, importe=dinero(Decimal(valor) * Decimal("0.90")),
                        vigente_desde=desde, vigente_hasta=fin_valores,
                        fuente="Estimación interna ficticia por atención; no incluye servicios compartidos.",
                        registrado_por=self.configurador,
                    )
                registrar_politica_cobro(
                    prestacion=prestacion, registrado_por=self.admin, cobrar=True,
                    importe=dinero(Decimal(arancel) * Decimal("0.80")),
                )
                registrar_cobertura_actividad(
                    institucion=self.institucion, area=area, vigente_desde=inicio,
                    registrado_por=self.admin, confirmacion_operativa=True,
                )
            for cod, nombre, _ in CONCEPTOS:
                self.conceptos[cod] = ConceptoGasto.objects.create(
                    institucion=self.institucion, codigo=cod, nombre=nombre, registrado_por=self.admin,
                )
                for area_cod, area in self.areas.items():
                    self.expectativas[(area_cod, cod)] = registrar_expectativa_gasto(
                        registrado_por=self.admin, concepto=self.conceptos[cod], institucion=self.institucion,
                        area=area, vigente_desde=inicio,
                        monto_referencia=dinero(MES_EN_CURSO[area_cod][[c[0] for c in CONCEPTOS].index(cod)]),
                    )
                    registrar_regla_reparto(
                        concepto=self.conceptos[cod], institucion=self.institucion,
                        area=area, vigente_desde=inicio, registrado_por=self.admin,
                    )
            # La edad se calcula contra la fecha de la carga, no contra un año fijo:
            # si no, cada año que pasa el padrón envejece un año.
            self.pacientes = [Ciudadano.objects.create(
                institucion=self.institucion, nombre=nombre, apellido=apellido,
                codigo=f"LA-{i + 1:04d}", documento=f"FIC{i + 1:06d}",
                fecha_nacimiento=self.cal.hoy.replace(year=self.cal.hoy.year - 71 + (i * 3) % 48, month=1 + i % 12, day=1 + i % 27),
                obra_social="Mutual del Valle",
            ) for i, (nombre, apellido) in enumerate(PACIENTES)]

    def _actualizar_valores(self):
        """Revisión de valores y aranceles, cinco meses atrás."""
        with self.cal.sintetica(self.cal.mes(REVISION), 7) as desde:
            for codigo, _, _, _, _, _, _, profesional, insumos, arancel in AREAS:
                for cod, valor in (("PROF", profesional), ("INS", insumos)):
                    ValorComponente.objects.create(
                        componente=self.componentes[(codigo, cod)], importe=dinero(valor),
                        vigente_desde=desde, registrado_por=self.configurador,
                        fuente="Revisión interna ficticia de valores; conserva importes históricos.",
                    )
                registrar_politica_cobro(
                    prestacion=self.prestaciones[codigo], registrado_por=self.admin, cobrar=True,
                    importe=dinero(arancel),
                )

    def _atencion(self, codigo, paciente, fecha, cerrar=True):
        with self.cal.sintetica(fecha):
            caso = Caso.objects.create(
                institucion=self.institucion, version=self.versiones[codigo], ciudadano=paciente,
                area_actual=self.areas[codigo], asignado_a=self.medicos[codigo],
            )
            motor.iniciar(caso, autor=self.administrativa)
            if not cerrar:
                return caso
            textos = {
                "CM": "Control ambulatorio programado. Paciente estable. Se acuerdan pautas de seguimiento.",
                "CAR": "Control cardiovascular ambulatorio. Evolución estable; se explican pautas de seguimiento.",
                "IMG": "Estudio radiográfico programado realizado. Informe disponible para el profesional solicitante.",
            }
            motor.avanzar(caso, {"titulo": self.prestaciones[codigo].nombre, "contenido": textos[codigo], "firmada": True}, autor=self.medicos[codigo])
            hecho = HechoAtencionCosteable.objects.get(caso=caso)
            procesar_hecho_atencion(hecho.pk)
            return hecho

    def _responsable(self, hecho, fecha, mes):
        """Completa quién paga esa atención, como lo haría administración."""
        pendiente = PendienteCobro.objects.filter(hecho=hecho, obligacion__isnull=True).first()
        if not pendiente:
            return None
        with self.cal.sintetica(fecha, 11):
            return resolver_pendiente_cobro(
                pendiente.pk, usuario=self.admin, contraparte_nombre="Mutual del Valle",
                contraparte_referencia=f"Convenio ambulatorio MV-{mes:%Y}",
            )

    def _movimiento(self, cuenta, importe, fecha, referencia, aprobado=True):
        with self.cal.sintetica(fecha, 15):
            return registrar_movimiento(
                obligacion=cuenta, importe=dinero(importe), fecha=self.cal.fecha(fecha, 15),
                clave=clave(referencia), usuario=self.admin if aprobado else self.administrativa,
                referencia=referencia, aprobado=aprobado,
            )

    def _referencia(self, prefijo, fecha, sufijo):
        return f"{prefijo}-{self.cal.fecha(fecha, 15):%y%m%d}-{sufijo}"

    def _historia(self):
        actual, anterior = self.cal.mes(ACTUAL), self.cal.mes(ANTERIOR)
        for numero_mes, mes in enumerate(self.meses):
            en_curso = mes == actual
            if mes == self.cal.mes(REVISION):
                self._actualizar_valores()
            for numero_area, (codigo, area) in enumerate(self.areas.items()):
                if en_curso:
                    agenda = ATENCIONES_DEL_MES[codigo]
                else:
                    cantidad = (6 + numero_mes % 3, 4 + numero_mes % 2, 3 + numero_mes % 2)[numero_area]
                    agenda = [(3 + indice * 3, (numero_mes * 7 + numero_area * 9 + indice) % len(self.pacientes))
                              for indice in range(cantidad)]
                for indice, (dia, numero_paciente) in enumerate(agenda):
                    fecha = mes.replace(day=dia)
                    if en_curso and codigo == "IMG" and indice == 1:
                        with self.cal.sintetica(self.cal.dia(ACTUAL, 13), 7):
                            DefinicionComponente.objects.create(
                                prestacion=self.prestaciones[codigo], codigo="PROTECCION",
                                nombre="Protección descartable incorporada este mes", orden=2,
                            )
                    hecho = self._atencion(codigo, self.pacientes[numero_paciente], fecha)
                    self.hechos[(mes, codigo, indice)] = hecho
                    # El responsable no viene de la prestación: lo completa
                    # administración por atención. La segunda radiografía del mes
                    # queda sin completar a propósito, para mostrar ese estado.
                    if not (en_curso and codigo == "IMG" and indice == 1):
                        self._responsable(hecho, fecha, mes)
                    cuenta = ObligacionFinanciera.objects.filter(hecho=hecho).first()
                    if not cuenta:
                        continue
                    if not en_curso:
                        self._movimiento(cuenta, cuenta.importe_original, mes.replace(day=27), f"MV-{mes:%Y%m}-{codigo}-{indice + 1:02d}")
                    elif codigo == "CAR" and indice == 0:
                        primero, segundo = self.cal.dia(ACTUAL, 10), self.cal.dia(ACTUAL, 12)
                        self._movimiento(cuenta, 15000, primero, self._referencia("MV", primero, "CLARA-01"))
                        self._movimiento(cuenta, 10000, segundo, self._referencia("MV", segundo, "CLARA-02"), aprobado=False)
                        self.escenarios["cargo_clara_benitez"] = cuenta
                    elif codigo == "CM" and indice == 2:
                        self.escenarios["cargo_sin_cobro"] = cuenta
                    else:
                        movimiento = self._movimiento(cuenta, cuenta.importe_original, fecha, self._referencia("MV", fecha, f"{codigo}-{indice + 1:02d}"))
                        if codigo == "CM" and indice == 1:
                            self.movimiento_devolucion = movimiento
                            self.escenarios["cargo_con_devolucion"] = cuenta
                for indice, (concepto_cod, _, proveedor) in enumerate(CONCEPTOS):
                    if en_curso:
                        importe = dinero(MES_EN_CURSO[codigo][indice])
                    elif mes == anterior and codigo == "CM" and concepto_cod == "ELEC":
                        importe = dinero(110000)
                    else:
                        factor = ELECTRICIDAD_POR_MES[mes.month] if concepto_cod == "ELEC" else FACTORES_HISTORICOS[concepto_cod][numero_mes]
                        importe = dinero(Decimal(BASES[codigo][indice]) * Decimal(factor))
                    fecha_gasto = mes.replace(day=3 if en_curso else 25)
                    with self.cal.sintetica(fecha_gasto, 12):
                        gasto = registrar_gasto(self.conceptos[concepto_cod], self.institucion, area, importe, mes, self.admin)
                        cuenta = crear_obligacion_pago(
                            gasto=gasto, contraparte_nombre=proveedor,
                            contraparte_referencia=f"Factura {codigo}-{concepto_cod}-{mes:%Y%m}",
                            clave=clave(f"cuenta-{codigo}-{concepto_cod}-{mes:%Y%m}"), usuario=self.admin,
                        )
                        if not en_curso:
                            indicar_carga_esperada(self.expectativas[(codigo, concepto_cod)].pk, mes, "carga_completa", self.admin)
                    self.gastos[(mes, codigo, concepto_cod)] = gasto
                    self.cuentas[(mes, codigo, concepto_cod)] = cuenta
                    if mes == anterior and codigo == "CM" and concepto_cod == "ELEC":
                        segundo = self.cal.dia(ACTUAL, 5)
                        # El sufijo distingue cada pago: comprimido el mes en curso,
                        # dos pagos de días nominales distintos pueden caer el mismo
                        # día real, y la referencia también es la clave del pago.
                        self._movimiento(cuenta, 50000, mes.replace(day=25), self._referencia("CEB", mes.replace(day=25), "01"))
                        self._movimiento(cuenta, 60000, segundo, self._referencia("CEB", segundo, "02"))
                        self.escenarios["electricidad_mes_anterior"] = cuenta
                    elif en_curso and codigo == "CM" and concepto_cod == "ELEC":
                        primero, segundo = self.cal.dia(ACTUAL, 8), self.cal.dia(ACTUAL, 12)
                        self._movimiento(cuenta, 60000, primero, self._referencia("CEB", primero, "03"))
                        self._movimiento(cuenta, 20000, segundo, self._referencia("CEB", segundo, "04"), aprobado=False)
                        self.escenarios["electricidad_mes_en_curso"] = cuenta
                    elif en_curso and concepto_cod == "MANT":
                        continue
                    else:
                        self._movimiento(cuenta, importe, mes.replace(day=12 if en_curso else 28), f"PAGO-{mes:%Y%m}-{codigo}-{concepto_cod}")

    def _pendientes_y_recorrido(self):
        actual = self.cal.mes(ACTUAL)
        recorrido = self.cal.dia(ACTUAL, 14)
        with self.cal.sintetica(recorrido, 16):
            gasto = self.gastos[(actual, "CM", "ELEC")]
            ajuste = registrar_ajuste_gasto(
                gasto.pk, dinero(-10000), "Bonificación por interrupción del servicio, pendiente de conformidad administrativa.",
                self.admin, aprobado=False,
            )
            self.ajuste_pendiente_id = ajuste.pk
            pendiente = registrar_gasto(
                self.conceptos["MANT"], self.institucion, self.areas["IMG"], dinero(45000),
                actual, self.administrativa,
            )
            self.gasto_pendiente_id = pendiente.pk
            duplicado = registrar_gasto(
                self.conceptos["MANT"], self.institucion, self.areas["CAR"], dinero(22000),
                actual, self.administrativa,
            )
            rechazar_gasto(duplicado.pk, "Comprobante repetido: ya incluido en el servicio mensual de mantenimiento.", self.admin)
            parametros = dict(
                original=self.movimiento_devolucion, importe=dinero(5000), fecha=self.cal.fecha(recorrido, 16),
                motivo="Bonificación administrativa acordada con la mutual; devolución y reducción conjunta del cargo.",
                efecto="reducir", usuario=self.admin,
            )
            preview = previsualizar_reintegro(**parametros)
            reintegrar_movimiento(
                **parametros, clave=clave("devolucion-daniel-peralta"),
                version_esperada=preview["version_esperada"], pendiente_esperado=preview["pendiente_anterior"],
            )
        self.casos_abiertos = []
        for indice, codigo in enumerate(self.areas):
            caso = self._atencion(codigo, self.pacientes[15 + indice], self.cal.dia(ACTUAL, 15), cerrar=False)
            self.casos_abiertos.append({"id": caso.pk, "area": self.areas[codigo].nombre, "paciente": str(caso.ciudadano), "profesional": self.medicos[codigo].email})

    def _verificar_y_resumir(self):
        inst = self.institucion
        for mes in self.meses:
            for area in self.areas.values():
                integridad = verificar_integridad_actividad(institucion_id=inst.pk, area_id=area.pk, periodo=mes)
                if not integridad["integridad_tecnica"]:
                    raise CommandError("Un evento clínico no concilia con su hecho económico. Se revierte.")
        if PendienteCobro.objects.filter(institucion=inst, obligacion__isnull=True).count() != 1:
            raise CommandError("Se esperaba exactamente un cobro con responsable por confirmar.")
        if PendienteCosteo.objects.filter(hecho__institucion=inst, resuelto=False).count() != 1:
            raise CommandError("Se esperaba exactamente un componente sin valor histórico.")
        if PoliticaCobro.objects.filter(institucion=inst, pendientecobro__hecho__ocurrida_en__lt=F("registrado")).exists():
            raise CommandError("Una política fue aplicada antes de existir. Se revierte.")
        cuentas = {}
        for etiqueta, cuenta in self.escenarios.items():
            estado = estado_obligacion(cuenta)
            cuentas[etiqueta] = {
                "id": cuenta.pk, "gasto_id": cuenta.gasto_id, "hecho_id": cuenta.hecho_id,
                "caso_id": cuenta.hecho.caso_id if cuenta.hecho_id else None,
                "paciente": str(cuenta.hecho.ciudadano) if cuenta.hecho_id else None,
                "area": cuenta.area.nombre if cuenta.area_id else None,
                "periodo_economico": str(cuenta.periodo_economico),
                "contraparte": cuenta.contraparte_nombre, "original": str(cuenta.importe_original),
                **{k: str(v) for k, v in estado.items() if k != "version_esperada"},
            }
        esperado = {
            "electricidad_mes_en_curso": ("120000.00", "60000.00", "60000.00", "20000.00", "40000.00"),
            "cargo_clara_benitez": ("45000.00", "15000.00", "30000.00", "10000.00", "20000.00"),
            "cargo_con_devolucion": ("25000.00", "25000.00", "0.00", "0.00", "0.00"),
        }
        campos = ("obligacion_actual", "registrado_neto", "pendiente", "por_aprobar", "disponible_registro")
        for nombre, valores in esperado.items():
            if tuple(cuentas[nombre][c] for c in campos) != valores:
                raise CommandError(f"No concilia el caso de presentación {nombre}. Se revierte.")
        mes = self.cal.mes(ACTUAL)
        gastos = Gasto.objects.filter(institucion=inst, periodo_economico=mes)
        movimientos = MovimientoDinero.objects.filter(institucion=inst, fecha__range=(mes, self.cal.hoy))
        totales_dinero = {}
        for tipo in ("pago", "cobro", "reintegro"):
            for estado in ("aprobado", "pendiente_aprobacion"):
                totales_dinero[f"{tipo}_{estado}"] = str(movimientos.filter(tipo=tipo, estado=estado).aggregate(total=Sum("importe"))["total"] or dinero(0))
        pendientes_cobro = list(PendienteCobro.objects.filter(institucion=inst, obligacion__isnull=True).values("id", "hecho_id", "importe", "contraparte_nombre"))
        pendientes_costo = list(PendienteCosteo.objects.filter(hecho__institucion=inst, resuelto=False).values("id", "hecho_id", "componente_id", "motivo"))
        cantidades = {
            "Ciudadano": Ciudadano.objects.filter(institucion=inst),
            "Caso": Caso.objects.filter(institucion=inst),
            "HechoAtencionCosteable": HechoAtencionCosteable.objects.filter(institucion=inst),
            "ImputacionCosto": ImputacionCosto.objects.filter(hecho__institucion=inst),
            "Gasto": Gasto.objects.filter(institucion=inst),
            "AjusteGasto": AjusteGasto.objects.filter(gasto__institucion=inst),
            "ObligacionFinanciera": ObligacionFinanciera.objects.filter(institucion=inst),
            "MovimientoDinero": MovimientoDinero.objects.filter(institucion=inst),
            "RepartoGasto": RepartoGasto.objects.filter(gasto__institucion=inst),
            "AtribucionReparto": AtribucionReparto.objects.filter(reparto__gasto__institucion=inst),
        }
        return {
            "escenario": NOMBRE, "institucion_id": inst.pk,
            "advertencia": "Todos los datos son ficticios. Son tres servicios y gastos seleccionados; no el costo ni el volumen total de un hospital.",
            "periodos": [str(m) for m in self.meses],
            "usuarios": list(Usuario.objects.filter(membresias__institucion=inst).distinct().order_by("id").values("id", "email", "nombre", "apellido")),
            "areas": {codigo: {"id": area.pk, "nombre": area.nombre} for codigo, area in self.areas.items()},
            "cantidades": {nombre: qs.count() for nombre, qs in cantidades.items()},
            "mes_en_curso": {
                "periodo": str(mes),
                "gasto_aprobado": str(gastos.filter(estado="aprobado").aggregate(total=Sum("importe"))["total"]),
                "gasto_por_aprobar": str(gastos.filter(estado="pendiente_aprobacion").aggregate(total=Sum("importe"))["total"]),
                "ajuste_gasto_por_aprobar": "-10000.00", "carga_completa": False,
                "atenciones": HechoAtencionCosteable.objects.filter(institucion=inst, ocurrida_en__date__gte=mes).count(),
                "costo_directo_conocido": str(ImputacionCosto.objects.filter(hecho__institucion=inst, hecho__ocurrida_en__date__gte=mes).aggregate(total=Sum("importe"))["total"]),
                **totales_dinero,
            },
            "cuentas_del_recorrido": cuentas,
            "gasto_pendiente_id": self.gasto_pendiente_id, "ajuste_gasto_pendiente_id": self.ajuste_pendiente_id,
            "pendientes_cobro": pendientes_cobro, "pendientes_costo": pendientes_costo,
            "casos_abiertos_para_atender": self.casos_abiertos,
            "no_incluye": ["Stock, bancos, caja e ingresos libres", "Atenciones o políticas copiadas de personas reales", "Datos sensibles", "Nuevas funcionalidades o permisos implícitos"],
        }
