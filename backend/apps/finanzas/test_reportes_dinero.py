from datetime import date
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import Membresia, Usuario
from apps.instituciones.models import Area, Institucion
from .models import AccesoFinanciero, ConceptoGasto, ConcesionFinanciera, EstadoAprobacion, Gasto, HechoAtencionCosteable, MovimientoDinero, Prestacion
from .dinero import crear_obligacion_cobro, crear_obligacion_pago, registrar_movimiento


class ReportesDineroTests(APITestCase):
    def setUp(self):
        self.institucion = Institucion.objects.create(nombre='Hospital dinero aislado')
        self.area = Area.objects.create(institucion=self.institucion, nombre='Consultorios')
        self.otra_area = Area.objects.create(institucion=self.institucion, nombre='Guardia')
        self.usuario = Usuario.objects.create_superuser('dinero-reportes@demo.local', 'x')
        self.client.force_authenticate(self.usuario)
        self.concepto = ConceptoGasto.objects.create(institucion=self.institucion, codigo='SERV', nombre='Servicio')
        self.parametros = dict(institucion=self.institucion.pk, fecha_desde='2026-09-01', fecha_hasta='2026-09-30')

    def cuenta(self, importe='100.00', area=None, sensible=False):
        concepto = self.concepto
        if sensible:
            concepto = ConceptoGasto.objects.create(institucion=self.institucion, codigo=str(uuid4()), nombre='Sensible', sensible=True)
        gasto = Gasto.objects.create(
            institucion=self.institucion, area=area or self.area, concepto=concepto,
            importe=Decimal(importe), periodo_economico=date(2026, 8, 1),
            origen=Gasto.Origen.CENTRAL, registrado_por=self.usuario,
            estado=Gasto.Estado.APROBADO, aprobado_por=self.usuario, aprobado_en=timezone.now(),
        )
        return crear_obligacion_pago(gasto=gasto, contraparte_nombre='Proveedor identificado', clave=uuid4(), usuario=self.usuario)

    def consultar(self, **filtros):
        return self.client.get('/api/reportes-dinero/', {**self.parametros, **filtros})

    def pago(self, obligacion, importe='30.00', fecha=date(2026, 9, 10)):
        return registrar_movimiento(obligacion=obligacion, importe=importe, fecha=fecha, clave=uuid4(), usuario=self.usuario)

    def test_fecha_efectiva_no_mes_economico_y_audita_fuente(self):
        cuenta = self.cuenta()
        self.pago(cuenta)
        self.pago(cuenta, '20.00', date(2026, 8, 31))
        respuesta = self.consultar()
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data['pagos_brutos'], '30.00')
        self.assertEqual(respuesta.data['pagos_netos'], '30.00')
        self.assertEqual(respuesta.data['diferencia'], '-30.00')
        self.assertEqual(respuesta.data['cantidad_movimientos'], 1)
        self.assertTrue(AccesoFinanciero.objects.filter(
            recurso='movimientodinero', periodo_economico=date(2026, 8, 1), area=self.area,
        ).exists())
        self.assertEqual(cuenta.gasto.importe, Decimal('100.00'))

    def test_brutos_reintegros_netos_sin_multiplicar_original(self):
        cuenta = self.cuenta()
        original = self.pago(cuenta, '100.00', date(2026, 8, 31))
        # Fixture histórica: sólo los reintegros son de septiembre. No se usa
        # el servicio porque estos tests prueban agregación y no su contrato.
        for importe in ('10.01', '19.99'):
            MovimientoDinero.objects.create(
                obligacion=cuenta, institucion=self.institucion, tipo='reintegro',
                original=original, importe=Decimal(importe), fecha=date(2026, 9, 10),
                motivo='Devolución recibida', clave=uuid4(), solicitud={'fixture': importe}, autor=self.usuario,
            )
        respuesta = self.consultar()
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data['pagos_brutos'], '0.00')
        self.assertEqual(respuesta.data['reintegros_pagos'], '30.00')
        self.assertEqual(respuesta.data['pagos_netos'], '-30.00')
        self.assertEqual(respuesta.data['diferencia'], '30.00')
        self.assertEqual(respuesta.data['cantidad_movimientos'], 2)

    def test_cobros_y_pagos_se_reportan_separados(self):
        hecho = HechoAtencionCosteable.objects.create(
            institucion=self.institucion, area=self.area, area_origen_id=self.area.pk,
            evento_origen_id=1, caso_origen_id=1, nodo_origen_id=1, ocurrida_en=timezone.now(),
        )
        cuenta = crear_obligacion_cobro(
            hecho=hecho, importe='100.00', contraparte_nombre='Responsable del pago', clave=uuid4(),
        )
        self.pago(cuenta, '40.01')
        self.pago(cuenta, '59.99')
        self.pago(self.cuenta(), '30.00')
        respuesta = self.consultar()
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data['cobros_brutos'], '100.00')
        self.assertEqual(respuesta.data['pagos_brutos'], '30.00')
        self.assertEqual(respuesta.data['diferencia'], '70.00')

    def test_pendientes_separados_y_rechazados_fuera_de_totales(self):
        cuenta = self.cuenta()
        confirmado = self.pago(cuenta, '40.00')
        pendiente = self.pago(cuenta, '20.00')
        rechazado = self.pago(cuenta, '10.00')
        # Estados de fixture: la transición con permisos/bloqueos se verifica
        # en los tests de servicios; aquí se aísla la agregación del reporte.
        MovimientoDinero.objects.filter(pk=pendiente.pk).update(estado=EstadoAprobacion.PENDIENTE)
        MovimientoDinero.objects.filter(pk=rechazado.pk).update(estado=EstadoAprobacion.RECHAZADO)
        MovimientoDinero.objects.create(
            obligacion=cuenta, institucion=self.institucion, tipo='reintegro',
            original=confirmado, importe=Decimal('5.00'), fecha=date(2026, 9, 10),
            estado=EstadoAprobacion.PENDIENTE, motivo='Pendiente de revisión',
            clave=uuid4(), solicitud={'fixture': True}, autor=self.usuario,
        )
        respuesta = self.consultar()
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data['pagos_brutos'], '40.00')
        self.assertEqual(respuesta.data['reintegros_pagos'], '0.00')
        self.assertEqual(respuesta.data['pagos_netos'], '40.00')
        self.assertEqual(respuesta.data['cantidad_movimientos'], 1)
        self.assertEqual(respuesta.data['por_aprobar'], {
            'cobros': '0.00', 'pagos': '20.00', 'reintegros_cobros': '0.00',
            'reintegros_pagos': '5.00', 'cantidad': 2,
        })
        # La aprobación posterior conserva la fecha efectiva del dinero.
        MovimientoDinero.objects.filter(pk=pendiente.pk).update(
            estado=EstadoAprobacion.APROBADO, aprobado_por=self.usuario,
            aprobado_en=timezone.now(),
        )
        respuesta = self.consultar()
        self.assertEqual(respuesta.data['pagos_netos'], '60.00')
        self.assertEqual(respuesta.data['por_aprobar']['pagos'], '0.00')
        self.assertEqual(respuesta.data['por_aprobar']['cantidad'], 1)

    def test_area_sensible_y_membresia_no_se_mezclan(self):
        self.pago(self.cuenta())
        self.pago(self.cuenta(area=self.otra_area), '50.00')
        self.pago(self.cuenta(sensible=True), '60.00')
        operador = Usuario.objects.create_user('dinero-area@demo.local', 'x')
        membresia = Membresia.objects.create(usuario=operador, institucion=self.institucion, rol=Membresia.Rol.ADMINISTRATIVO)
        concesion = ConcesionFinanciera.objects.create(membresia=membresia, accion='ver_dinero')
        concesion.areas.add(self.area)
        self.client.force_authenticate(operador)
        respuesta = self.consultar()
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data['pagos_brutos'], '30.00')
        self.assertEqual(self.consultar(area=self.otra_area.pk).status_code, 403)
        self.assertEqual(self.consultar(area_sin_asignar=True).status_code, 403)
        otra = Institucion.objects.create(nombre='Otra institución')
        self.assertEqual(self.consultar(institucion=otra.pk).status_code, 403)

    def test_administrador_sin_permiso_dinero_no_recibe_grant_automatico(self):
        usuario = Usuario.objects.create_user('admin-sin-dinero@demo.local', 'x')
        Membresia.objects.create(usuario=usuario, institucion=self.institucion, rol=Membresia.Rol.ADMIN_INSTITUCION)
        self.client.force_authenticate(usuario)
        self.assertEqual(self.consultar().status_code, 403)

    def test_filtros_invalidos_y_reporte_vacio_explicito(self):
        self.assertEqual(self.consultar(fecha_desde='2026-10-01').status_code, 400)
        self.assertEqual(self.consultar(fecha_hasta='error').status_code, 400)
        self.assertEqual(self.consultar(area=self.area.pk, area_sin_asignar=True).status_code, 400)
        respuesta = self.consultar()
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data['cantidad_movimientos'], 0)
        self.assertEqual(respuesta.data['cobros_netos'], '0.00')
        self.assertIn('no es saldo disponible', respuesta.data['alcance'])

    def test_auditoria_falla_cerrada_sin_devolver_montos(self):
        self.pago(self.cuenta())
        with patch('apps.finanzas.auditoria.AccesoFinanciero.objects.create', side_effect=RuntimeError('no disponible')):
            respuesta = self.consultar()
        self.assertEqual(respuesta.status_code, 503)
        self.assertNotIn('pagos_brutos', respuesta.data)

    def test_configurar_cobros_lee_prestaciones_no_componentes_ni_edita(self):
        usuario = Usuario.objects.create_user('config-cobros@demo.local', 'x')
        membresia = Membresia.objects.create(usuario=usuario, institucion=self.institucion, rol=Membresia.Rol.ADMINISTRATIVO)
        ConcesionFinanciera.objects.create(membresia=membresia, accion='configurar_cobros', todas_las_areas=True)
        prestacion = Prestacion.objects.create(institucion=self.institucion, codigo='CONS', nombre='Consulta')
        self.client.force_authenticate(usuario)
        respuesta = self.client.get('/api/prestaciones-costo/', {'institucion': self.institucion.pk})
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data['results'][0]['id'], prestacion.pk)
        self.assertEqual(self.client.get('/api/componentes-costo/').status_code, 403)
        self.assertEqual(self.client.patch(f'/api/prestaciones-costo/{prestacion.pk}/', {'activo': False}, format='json').status_code, 403)
