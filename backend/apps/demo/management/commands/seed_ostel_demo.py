"""Carga adicional OSTEL. Nunca invoca seeds destructivos ni repara ensayos.

Una transacción crea el escenario completo y su marcador. Una repetición sólo
devuelve el inventario actual; no restablece claves, permisos ni pendientes.
"""
import json
import os
from datetime import time, timedelta
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

from django.conf import settings
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone

from apps.accounts.models import LegajoProfesional, Membresia, Usuario
from apps.agenda import motor as agenda_motor
from apps.agenda.models import Agenda, Disponibilidad
from apps.casos import motor
from apps.casos.models import Caso
from apps.farmacia import motor as farmacia_motor
from apps.farmacia.models import Deposito, Insumo, LineaPedido, Lote, Pedido
from apps.financiadores import autorizaciones, models as m
from apps.financiadores.cobertura import cotizacion, reservar, seleccionar_afiliacion
from apps.financiadores.facturas import clave_duplicado
from apps.financiadores.padron import validar_generales
from apps.financiadores.management.commands.seed_padron_demo import identificador_fiscal
from apps.financiadores.services import auditar, registrar_afiliado, registrar_consumo_externo
from apps.finanzas.cobros import registrar_politica_cobro
from apps.finanzas.dinero import crear_obligacion_pago, registrar_movimiento
from apps.finanzas.models import (
    ConceptoGasto, ConcesionFinanciera, DefinicionComponente,
    HechoAtencionCosteable, Prestacion, ValorComponente,
)
from apps.finanzas.services import procesar_hecho_atencion, registrar_gasto
from apps.flujos.models import Conexion, Flujo, Nodo, VersionFlujo
from apps.formularios.models import Campo, Formulario
from apps.instituciones.models import Area, Box, Cama, Grupo, Institucion, Subarea
from apps.portal.models import CuentaPaciente
from apps.red import motor as red_motor
from apps.red.models import Red
from apps.registros.models import Ciudadano, Estudio, HistoriaClinica


ESCENARIO = "ostel-demo-v1"
ORGANIZACION = "OSTEL · Demostración"
LOCK = 2026101901
DOMINIO = "ostel.demo.test"
PRESTADORES = (
    # código, nombre ficticio, tipo, consulta acordada, radiografía acordada
    ("sanatorio", "Sanatorio del Parque · Demo OSTEL", "Sanatorio", 28000, 45000),
    ("ambulatorio", "Centro Ambulatorio del Sur · Demo OSTEL", "Centro ambulatorio", 22000, None),
    ("diagnostico", "Diagnóstico Norte · Demo OSTEL", "Centro de diagnóstico", None, 38000),
)
CATALOGO = {
    "CONS": ("Consulta de clínica médica", "consultas"),
    "RX": ("Radiografía de tórax", "imagenes"),
}
FAMILIAS = ("Pereyra", "Benítez", "Sosa", "Acosta", "Vega", "Medina")
PERFILES = {
    "consultora": ("admin", True, True, True),
    "admin": ("admin", True, True, True),
    "autorizaciones": ("operador", True, False, False),
    "salud": ("operador", False, True, False),
    "cobranza": ("operador", False, False, True),
    "auditor": ("auditor", False, True, True),
}


def clave(texto):
    return uuid5(NAMESPACE_URL, f"{ESCENARIO}/{texto}")


def exigir_destino():
    if settings.ENTORNO != "demo":
        raise CommandError(f"seed_ostel_demo exige ENTORNO=demo; destino actual ENTORNO={settings.ENTORNO}. No se modificó ningún dato.")
    if connection.vendor != "postgresql":
        raise CommandError("seed_ostel_demo exige PostgreSQL; no se modificó ningún dato.")


class Command(BaseCommand):
    help = "Agrega OSTEL y tres prestadores ficticios sin borrar ni restablecer datos."

    def handle(self, *args, **options):
        exigir_destino()
        try:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_advisory_xact_lock(%s)", [LOCK])
                marcador = Group.objects.filter(name=ESCENARIO).first()
                existente = marcador is not None
                if not existente:
                    password = os.environ.get("DEMO_PASSWORD", "")
                    if not password.strip() or password.strip().casefold() == "demo1234":
                        raise CommandError("Provisioná DEMO_PASSWORD externa y distinta de la clave pública de demo.")
                    self._sin_colisiones()
                    self._crear(password)
                    marcador = Group.objects.create(name=ESCENARIO)
                    marcador.user_set.add(*self.usuarios)
                resumen = self._resumen(marcador)
        except ValidationError:
            # Los errores de campos protegidos no deben terminar en los logs.
            raise CommandError("La carga no cumple el contrato de datos; se revirtió completa.") from None
        self.stdout.write(json.dumps({"escenario": ESCENARIO, "existente": existente, **resumen},
                                     ensure_ascii=False, indent=2))

    def _sin_colisiones(self):
        # La ausencia del marcador nunca autoriza apropiarse de datos existentes.
        nombres = [p[1] for p in PRESTADORES]
        if (m.Financiador.objects.filter(nombre=ORGANIZACION).exists()
                or Institucion.objects.filter(nombre__in=nombres).exists()
                or Usuario.objects.filter(email__in=self._emails()).exists()
                or m.PrestacionComun.objects.filter(codigo__in=[f"OSTEL-{c}" for c in CATALOGO]).exists()
                or Red.objects.filter(nombre="Red de prestadores · Demo OSTEL").exists()
                or Ciudadano.objects.filter(documento__in=[str(99019000 + i) for i in range(1, 25)]).exists()
                or CuentaPaciente.objects.filter(email=f"paciente@{DOMINIO}").exists()
                or CuentaPaciente.objects.filter(documento="99019001", identidad="validada").exists()):
            raise CommandError("Hay identificadores reservados de OSTEL sin marcador completo. No se modifica ni se repara automáticamente.")

    @staticmethod
    def _emails():
        return [f"{p}@{DOMINIO}" for p in PERFILES] + [
            f"{rol}@{codigo}.ostel.demo.test"
            for codigo, *_ in PRESTADORES for rol in ("adm", "medico", "enfermeria")
        ]

    def _usuario(self, email, nombre, password):
        usuario = Usuario.objects.create_user(email, password, nombre=nombre, apellido="Demo OSTEL")
        self.usuarios.append(usuario)
        return usuario

    def _crear(self, password):
        self.usuarios, self.sedes, self.afiliados = [], {}, []
        self.hoy = timezone.localdate()
        self.org = m.Financiador.objects.create(nombre=ORGANIZACION, tipo="obra_social")
        self.cuentas = {}
        for perfil, (rol, autoriza, salud, cobranza) in PERFILES.items():
            usuario = self._usuario(f"{perfil}@{DOMINIO}", perfil.capitalize(), password)
            m.MembresiaFinanciador.objects.create(
                financiador=self.org, usuario=usuario, rol=rol, resuelve_autorizaciones=autoriza,
                acceso_padron_salud=salud, acceso_padron_cobranza=cobranza,
            )
            self.cuentas[perfil] = usuario
        self.evaluador = self.cuentas["consultora"]
        LegajoProfesional.objects.create(usuario=self.evaluador, matricula="DEMO-OSTEL-EVAL", especialidad="Evaluación ficticia")
        self.comunes = {
            codigo: m.PrestacionComun.objects.create(codigo=f"OSTEL-{codigo}", nombre=nombre, categoria=categoria)
            for codigo, (nombre, categoria) in CATALOGO.items()
        }
        self.planes = []
        for codigo, nombre, porcentaje, cupo in (
            ("DEMO-BASE", "Base · Ejemplo", 80, 6), ("DEMO-PLUS", "Plus · Ejemplo", 100, 12),
        ):
            plan = m.Plan.objects.create(financiador=self.org, codigo=codigo, nombre=nombre)
            self.planes.append(plan)
            for prestacion in CATALOGO:
                m.ReglaCobertura.objects.create(
                    financiador=self.org, plan=plan, prestacion=self.comunes[prestacion],
                    porcentaje=Decimal(porcentaje if prestacion == "CONS" else porcentaje - 10),
                    cupo=cupo if prestacion == "CONS" else cupo // 3, periodo="anio",
                    vigente_desde=self.hoy, requiere_autorizacion=prestacion == "RX",
                    creado_por=self.cuentas["admin"],
                )
        for codigo, nombre, tipo, consulta, radiografia in PRESTADORES:
            self._institucion(codigo, nombre, tipo, consulta, radiografia, password)
        self._padron()
        self._actividad()
        self._red()
        self._portal(password)
        auditar(self.cuentas["admin"], "seed_ostel_demo", self.org.pk, financiador=self.org)

    def _membresia(self, usuario, institucion, rol, areas, finanzas=False):
        membresia = Membresia.objects.create(usuario=usuario, institucion=institucion, rol=rol)
        membresia.areas.set(areas)
        if finanzas:
            for accion in ConcesionFinanciera.Accion.values:
                ConcesionFinanciera.objects.create(membresia=membresia, accion=accion, todas_las_areas=True)

    def _institucion(self, codigo, nombre, tipo, consulta, radiografia, password):
        inst = Institucion.objects.create(nombre=nombre, tipo=tipo, direccion="Domicilio ficticio de demostración")
        clinica = Area.objects.create(institucion=inst, nombre="Atención ambulatoria")
        areas = [clinica]
        internacion = None
        if codigo == "sanatorio":
            internacion = Area.objects.create(institucion=inst, nombre="Internación")
            areas.append(internacion)
        personal = {}
        for cuenta, rol in (("adm", "admin"), ("medico", "medico"), ("enfermeria", "enfermeria")):
            usuario = self._usuario(f"{cuenta}@{codigo}.ostel.demo.test", f"{cuenta.capitalize()} {codigo}", password)
            self._membresia(usuario, inst, rol, areas, finanzas=cuenta == "adm")
            personal[cuenta] = usuario
        LegajoProfesional.objects.create(usuario=personal["medico"], matricula=f"DEMO-{codigo}", especialidad="Clínica / diagnóstico")
        # Auditor y plataforma tienen alcance estatal aunque se les indique institución.
        # Administración ya habilita auditoría acotada a los prestadores propios.
        for rol in ("admin", "configurador", "jefe_area", "administrativo", "enfermeria", "medico", "reportes"):
            self._membresia(self.evaluador, inst, rol, areas, finanzas=rol == "admin")
        equipo = Grupo.objects.create(area=clinica, nombre="Equipo de atención")
        equipo.miembros.set([self.evaluador, *personal.values()])
        Box.objects.create(area=clinica, nombre="Consultorio 1")
        m.ConfiguracionHospital.objects.create(institucion=inst, activo=True, dias_reserva_antigua=7)
        convenio = m.Convenio.objects.create(
            financiador=self.org, institucion=inst, estado="activo", propuesto_por="financiador",
            creado_por=self.cuentas["admin"], aceptado_por=personal["adm"], aceptado_en=timezone.now(),
            plazo_autorizacion_horas=48 if codigo == "sanatorio" else 72,
        )
        sede = dict(inst=inst, area=clinica, personal=personal, convenio=convenio, flujos={}, prestaciones={}, agendas={})
        self.sedes[codigo] = sede
        for prestacion, importe in (("CONS", consulta), ("RX", radiografia)):
            if importe is None:
                continue
            nombre_prestacion = CATALOGO[prestacion][0]
            flujo, nodo = self._flujo(inst, clinica, nombre_prestacion, personal["adm"], equipo,
                                      recibe_derivaciones=prestacion == "CONS" or consulta is None)
            servicio = Prestacion.objects.create(institucion=inst, nodo=nodo, codigo=f"OSTEL-{prestacion}", nombre=nombre_prestacion)
            m.VinculoPrestacion.objects.create(prestacion=servicio, comun=self.comunes[prestacion])
            registrar_politica_cobro(prestacion=servicio, registrado_por=personal["adm"], cobrar=True, importe=Decimal(importe + 5000))
            m.ArancelConvenio.objects.create(convenio=convenio, prestacion=servicio, importe=Decimal(importe), vigente_desde=self.hoy, creado_por=personal["adm"])
            componente = DefinicionComponente.objects.create(prestacion=servicio, codigo="PROF", nombre="Trabajo profesional e insumos")
            ValorComponente.objects.create(componente=componente, importe=Decimal(importe) / 2, vigente_desde=timezone.now(), registrado_por=personal["adm"], fuente="Valor ficticio de demostración")
            agenda = Agenda.objects.create(institucion=inst, area=clinica, nombre=nombre_prestacion,
                tipo="profesional" if prestacion == "CONS" else "recurso",
                profesional=personal["medico"] if prestacion == "CONS" else None,
                flujo=flujo, duracion_min=20)
            for dia in range(5):
                Disponibilidad.objects.create(agenda=agenda, dia_semana=dia, desde=time(8), hasta=time(17))
            sede["flujos"][prestacion] = flujo
            sede["prestaciones"][prestacion] = servicio
            sede["agendas"][prestacion] = agenda
        self._farmacia(sede)
        if internacion:
            self._internacion(sede, internacion)

    def _flujo(self, inst, area, titulo, autor, equipo=None, cama=False, recibe_derivaciones=True):
        flujo = Flujo.objects.create(institucion=inst, area=area, titulo=titulo,
                                    descripcion="Circuito ficticio listo para evaluar; no representa protocolos reales de OSTEL.")
        version = VersionFlujo.objects.create(flujo=flujo, numero=1, autor=autor)
        # Un área debe tener un único receptor para que el traslado no sea ambiguo.
        inicio = Nodo.objects.create(version=version, tipo="inicio", titulo="Ingreso",
                                     config={"origen": "ambos" if recibe_derivaciones else "manual"}, x=60, y=100)
        anterior = inicio
        if cama:
            anterior = Nodo.objects.create(version=version, tipo="cama", titulo="Asignar cama", config={"area_id": area.pk}, x=250, y=100)
            Conexion.objects.create(version=version, origen=inicio, destino=anterior)
        form = Formulario.objects.create(institucion=inst, area=area, titulo=f"Registro · {titulo}")
        Campo.objects.create(formulario=form, label="Motivo de consulta", tipo="texto_largo", requerido=False)
        atencion = Nodo.objects.create(version=version, tipo="atencion", titulo=titulo, formulario=form,
                                       config={"con_fila": not cama}, x=450, y=100)
        if equipo:
            atencion.grupos.add(equipo)
        fin = Nodo.objects.create(version=version, tipo="fin", titulo="Finalizar atención", x=700, y=100)
        Conexion.objects.create(version=version, origen=anterior, destino=atencion)
        Conexion.objects.create(version=version, origen=atencion, destino=fin)
        if not motor.puede_publicar(version):
            raise CommandError("El flujo de demostración no es publicable; se revierte la carga.")
        version.estado = VersionFlujo.Estado.PUBLICADA
        version.save(update_fields=["estado"])
        return flujo, atencion

    def _farmacia(self, sede):
        inst, admin = sede["inst"], sede["personal"]["adm"]
        central = Deposito.objects.create(institucion=inst, nombre="Farmacia central", central=True)
        botiquin = Deposito.objects.create(institucion=inst, nombre="Botiquín de atención", area=sede["area"])
        for nombre, presentacion, cantidad in (("Paracetamol", "Comprimido 500 mg", 200), ("Guantes de examen", "Caja x100", 20)):
            insumo = Insumo.objects.create(institucion=inst, nombre=nombre, presentacion=presentacion,
                                          unidad="unidad", requiere_lote=True, stock_minimo=30)
            lote = Lote.objects.create(insumo=insumo, numero=f"OSTEL-{inst.pk}-{insumo.pk}", vencimiento=self.hoy + timedelta(days=120))
            farmacia_motor.ingresar(central, insumo, cantidad, lote=lote, autor=admin, motivo="Stock inicial ficticio")
            farmacia_motor.transferir(central, botiquin, insumo, min(cantidad, 10), lote=lote, autor=admin, motivo="Reposición inicial ficticia")
            pedido = Pedido.objects.create(origen=botiquin, destino=central, creado_por=admin, observaciones="Pedido pendiente para la evaluación")
            LineaPedido.objects.create(pedido=pedido, insumo=insumo, pedido_cant=10)
        sede["botiquin"] = botiquin

    def _internacion(self, sede, area):
        sector = Subarea.objects.create(area=area, nombre="Clínica médica")
        for indice in range(1, 9):
            estado = "higiene" if indice == 7 else "bloqueada" if indice == 8 else "libre"
            Cama.objects.create(area=area, subarea=sector, nombre=f"{100 + indice}", estado=estado,
                                desde=timezone.now() if estado != "libre" else None,
                                motivo="Mantenimiento ficticio" if estado == "bloqueada" else "")
        flujo, _ = self._flujo(sede["inst"], area, "Internación clínica", sede["personal"]["adm"], cama=True)
        sede["internacion"] = flujo

    def _padron(self):
        for familia, apellido in enumerate(FAMILIAS):
            titular = None
            for integrante, (nombre, edad, parentesco) in enumerate((("Martín", 46, ""), ("Lucía", 43, "conyuge"), ("Camila", 15, "hija"), ("Julián", 21, "hijo"))):
                indice = familia * 4 + integrante + 1
                documento = str(99019000 + indice)
                afiliado = registrar_afiliado(
                    financiador=self.org, usuario=self.cuentas["admin"], numero=f"OSTEL-D{familia + 1:03d}-{integrante:02d}",
                    documento=documento, nombre=f"{nombre} {apellido}", plan=self.planes[familia % 2], desde=self.hoy,
                )
                afiliado.tipo_documento, afiliado.cuil = "DNI", identificador_fiscal(int(documento))
                afiliado.nombres, afiliado.apellidos, afiliado.sexo = nombre, apellido, "X"
                afiliado.fecha_nacimiento = self.hoy.replace(year=self.hoy.year - edad, day=min(self.hoy.day, 28))
                afiliado.email = f"afiliado-{indice:02d}@{DOMINIO}"
                afiliado.localidad, afiliado.provincia = "Localidad de prueba", "Buenos Aires"
                afiliado.regimen = "dependencia" if familia < 3 else "monotributo" if familia == 3 else "pasivo" if familia == 4 else "adherente"
                afiliado.alta_administrativa = self.hoy
                afiliado.titular, afiliado.parentesco = titular, parentesco
                afiliado.credencial_tipo = "Credencial externa ficticia informada"
                afiliado.credencial_fecha = self.hoy
                afiliado.estado_tramite = "en_revision" if integrante == 3 else "pendiente"
                afiliado.full_clean()
                afiliado.save()
                titular = titular or afiliado
                m.DocumentoLegajo.objects.create(afiliado=afiliado, tipo="estudio" if integrante == 3 else "dni",
                    estado="presentado" if integrante == 3 else "verificado", presentado_en=self.hoy,
                    verificado_en=self.hoy if integrante != 3 else None,
                    vence_en=self.hoy + timedelta(days=30), referencia="Presentación ficticia; sin archivo adjunto")
                if integrante != 3:
                    afiliado.estado_tramite = "completo"
                validar_generales(afiliado)
                afiliado.save(update_fields=["estado_tramite"])
                m.SaludPadron.objects.create(afiliado=afiliado, dbt=familia == 4 and integrante == 0,
                                            cronicas="Declaración ficticia para evaluar permisos" if familia == 4 and integrante == 0 else "")
                m.CobranzaPadron.objects.create(afiliado=afiliado, situacion="deuda" if familia == 5 else "al_dia",
                    fuente="Situación declarada ficticia; no es deuda calculada", informado_en=self.hoy, modalidad="transferencia")
                self.afiliados.append(afiliado)
                for codigo, sede in self.sedes.items():
                    ciudadano = Ciudadano.objects.create(institucion=sede["inst"], documento=documento,
                        codigo=f"OSTEL-{indice:03d}", nombre=nombre, apellido=apellido, fecha_nacimiento=afiliado.fecha_nacimiento)
                    m.VinculoCiudadano.objects.create(afiliado=afiliado, ciudadano=ciudadano, verificado_por=sede["personal"]["adm"])
                    sede.setdefault("pacientes", []).append(ciudadano)

    def _caso(self, codigo, prestacion, indice):
        sede = self.sedes[codigo]
        flujo = sede["flujos"][prestacion]
        caso = Caso.objects.create(institucion=sede["inst"], area_actual=sede["area"], version=flujo.version_publicada,
                                    ciudadano=sede["pacientes"][indice], asignado_a=sede["personal"]["medico"])
        motor.iniciar(caso, autor=sede["personal"]["adm"])
        seleccionar_afiliacion(caso=caso, usuario=sede["personal"]["adm"], afiliado=self.afiliados[indice], motivo="Afiliación ficticia verificada para evaluar OSTEL")
        return caso

    def _autorizar(self, caso, sede, decision):
        caso.refresh_from_db()
        solicitud = autorizaciones.solicitar(caso=caso, prestacion=sede["prestaciones"]["RX"],
            usuario=sede["personal"]["adm"], intento=autorizaciones.intento_actual(caso), cantidad=1,
            justificacion="Orden ficticia de radiografía para evaluación", clave=clave(f"solicitud-{caso.pk}"))
        if decision:
            extra = dict(cantidad_aprobada=1, vigencia_desde=self.hoy, vigencia_hasta=self.hoy + timedelta(days=30),
                         evidencia="Orden ficticia revisada", numero_externo=f"DEMO-AUT-{caso.pk}") if decision == "aprobar" else {}
            solicitud = autorizaciones.resolver(solicitud=solicitud, usuario=self.cuentas["autorizaciones"],
                revision=solicitud.revision, decision=decision, motivo="Decisión ficticia de evaluación",
                clave=clave(f"respuesta-{caso.pk}"), **extra)
        return solicitud

    def _realizar(self, caso, sede, prestacion):
        box = Box.objects.get(area=sede["area"], nombre="Consultorio 1")
        motor.llamar(caso, box_id=box.pk, autor=sede["personal"]["medico"])
        # Simula la aceptación antes de prestar: el copago no se da por cobrado.
        datos = dict(caso=caso, prestacion=sede["prestaciones"][prestacion], fecha=self.hoy, cantidad=1)
        propuesta = cotizacion(**datos)
        reservar(**datos, usuario=sede["personal"]["adm"], clave=clave(f"reserva-{caso.pk}"), firma=propuesta["firma"], acepta=True)
        motor.avanzar(caso, {"titulo": CATALOGO[prestacion][0], "contenido": "Atención ficticia de evaluación. Se acuerda control.", "firmada": True}, autor=sede["personal"]["medico"])
        hecho = HechoAtencionCosteable.objects.get(caso=caso)
        procesar_hecho_atencion(hecho.pk)

    def _actividad(self):
        # Una misma afiliación usa el catálogo común en dos instituciones.
        for codigo in ("sanatorio", "ambulatorio"):
            sede = self.sedes[codigo]
            self._realizar(self._caso(codigo, "CONS", 0), sede, "CONS")
        for codigo, sede in self.sedes.items():
            for prestacion in sede["prestaciones"]:
                self._caso(codigo, prestacion, 2)
            if "RX" in sede["prestaciones"]:
                for indice, decision in ((4, None), (5, "observar"), (6, "rechazar"), (7, "aprobar")):
                    caso = self._caso(codigo, "RX", indice)
                    self._autorizar(caso, sede, decision)
                    if decision == "aprobar":
                        self._realizar(caso, sede, "RX")
            # Cupo agotado por consumos externos: no implica que se haya cobrado.
            if "CONS" in sede["prestaciones"]:
                self._caso(codigo, "CONS", 8)
            for prestacion, agenda in sede["agendas"].items():
                for indice in (0, 1, 3):
                    libres = agenda_motor.proximos_libres(agenda, desde=timezone.now() + timedelta(days=3 + indice), dias=14, cuantos=1)
                    if not libres:
                        raise CommandError("No se encontraron turnos futuros; se revierte la carga.")
                    agenda_motor.reservar(agenda, sede["pacientes"][indice], libres[0]["inicio"], autor=sede["personal"]["adm"], motivo="Control ficticio OSTEL")
            self._finanzas(sede)
        registrar_consumo_externo(financiador=self.org, usuario=self.cuentas["admin"], afiliado=self.afiliados[8],
            prestacion=self.comunes["CONS"], fecha=self.hoy, cantidad=6, referencia="OSTEL-EXTERNO-CUPO-AGOTADO")
        # Una baja administrativa informada no corta por sí sola prestaciones.
        baja = self.afiliados[20]
        baja.solicitud_baja = baja.baja_efectiva = self.hoy
        baja.fin_prestacional_informado = self.hoy + timedelta(days=60)
        baja.causa_baja, baja.motivo_baja = "renuncia", "Baja administrativa ficticia con continuidad informada"
        validar_generales(baja)
        baja.save()
        sede = self.sedes["sanatorio"]
        flujo = sede["internacion"]
        caso = Caso.objects.create(institucion=sede["inst"], area_actual=flujo.area, version=flujo.version_publicada,
                                    ciudadano=sede["pacientes"][12], asignado_a=sede["personal"]["medico"])
        motor.iniciar(caso, autor=sede["personal"]["adm"])
        seleccionar_afiliacion(caso=caso, usuario=sede["personal"]["adm"], afiliado=self.afiliados[12], motivo="Ingreso ficticio para evaluar internación")
        motor.asignar_cama(caso, Cama.objects.get(area=flujo.area, nombre="101").pk, autor=sede["personal"]["adm"])
        existencia = sede["botiquin"].existencias.filter(cantidad__gt=0).select_related("insumo", "lote").first()
        farmacia_motor.consumir(sede["botiquin"], existencia.insumo, 1, caso=caso, autor=sede["personal"]["enfermeria"], lote=existencia.lote, motivo="Consumo ficticio trazable")

    def _finanzas(self, sede):
        admin = sede["personal"]["adm"]
        periodo = self.hoy.replace(day=1)
        concepto = ConceptoGasto.objects.create(institucion=sede["inst"], codigo="OSTEL-INS", nombre="Insumos de atención · Demo", registrado_por=admin)
        gasto = registrar_gasto(concepto, sede["inst"], sede["area"], Decimal("150000"), periodo, admin, aprobado=True)
        obligacion = crear_obligacion_pago(gasto=gasto, contraparte_nombre="Proveedor ficticio de insumos", clave=clave(f"pagar-{sede['inst'].pk}"), usuario=admin)
        registrar_movimiento(obligacion=obligacion, importe=Decimal("50000"), fecha=self.hoy, clave=clave(f"pago-{sede['inst'].pk}"), usuario=admin, referencia="Pago parcial ficticio", aprobado=True)
        for numero, importe in (("001", "65000"), ("002", "42000")):
            datos = dict(direccion="recibida", contraparte_tipo="institucion", convenio=sede["convenio"],
                         contraparte_nombre=sede["inst"].nombre, tipo="factura", letra="C", numero=f"DEMO-{sede['inst'].pk}-{numero}",
                         fecha=self.hoy, importe=Decimal(importe))
            m.RegistroFactura.objects.create(financiador=self.org, creado_por=self.cuentas["admin"],
                clave_duplicado=clave_duplicado(datos), concepto="Comprobante ficticio registrado; sin emisión fiscal", **datos)

    def _red(self):
        red = Red.objects.create(nombre="Red de prestadores · Demo OSTEL", descripcion="Red ficticia; los convenios con OSTEL son independientes de la red de traslados.")
        red.instituciones.set([s["inst"] for s in self.sedes.values()])
        for indice, decision in ((16, None), (17, "aceptar"), (18, "rechazar")):
            caso = self._caso("ambulatorio", "CONS", indice)
            traslado = red_motor.solicitar(caso, self.sedes["sanatorio"]["inst"], "complejidad",
                detalle="Evaluación ficticia en institución de mayor complejidad", autor=self.sedes["ambulatorio"]["personal"]["adm"],
                area_destino=self.sedes["sanatorio"]["area"])
            if decision == "aceptar":
                red_motor.aceptar(traslado, autor=self.sedes["sanatorio"]["personal"]["adm"])
            elif decision == "rechazar":
                red_motor.rechazar(traslado, "Sin disponibilidad ficticia para evaluar rechazo", autor=self.sedes["sanatorio"]["personal"]["adm"])

    def _portal(self, password):
        cuenta = CuentaPaciente(email=f"paciente@{DOMINIO}", email_verificado_at=timezone.now(),
            identidad="validada", documento=self.afiliados[0].documento, sexo="X",
            identidad_validada_at=timezone.now(), nombre="Martín", apellido=FAMILIAS[0], fecha_nacimiento=self.afiliados[0].fecha_nacimiento)
        cuenta.set_password(password)
        cuenta.save()
        for codigo in ("sanatorio", "ambulatorio"):
            paciente = self.sedes[codigo]["pacientes"][0]
            historia, _ = HistoriaClinica.objects.get_or_create(ciudadano=paciente)
            Estudio.objects.create(historia=historia, tipo="Hemograma de demostración", fecha=self.hoy,
                                    realizado=True, resultado="normal", autor="Laboratorio ficticio")
        # No genera archivos de almacenamiento: el rollback de la base no revierte archivos.

    @staticmethod
    def _resumen(marcador):
        usuarios = marcador.user_set.all()
        org_ids = m.MembresiaFinanciador.objects.filter(usuario__in=usuarios).values_list("financiador_id", flat=True).distinct()
        instituciones = Institucion.objects.filter(membresias__usuario__in=usuarios).distinct().order_by("id")
        organizaciones = m.Financiador.objects.filter(pk__in=org_ids)
        if organizaciones.count() != 1 or instituciones.count() != 3 or usuarios.count() != len(Command._emails()):
            raise CommandError("El marcador OSTEL está incompleto o cambió su alcance. No se restaura automáticamente.")
        org = organizaciones.get()
        return {
            "organizacion": {"id": org.pk, "nombre": org.nombre},
            "instituciones": list(instituciones.values("id", "nombre")),
            "usuarios": list(usuarios.order_by("email").values_list("email", flat=True)),
            "afiliados": m.Afiliado.objects.filter(financiador=org).count(),
            "convenios": list(m.Convenio.objects.filter(financiador=org).values("id", "institucion_id", "estado")),
            "casos": Caso.objects.filter(institucion__in=instituciones).count(),
            "portal_paciente": f"paciente@{DOMINIO}",
            "nota": "Datos ficticios. No se imprimen claves ni datos de salud o cobranza. Repetir no restablece el escenario.",
        }
