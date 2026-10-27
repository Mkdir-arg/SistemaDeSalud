"""Integración en PostgreSQL aislado autorizado; nunca usar settings productivos."""
from datetime import date
from unittest.mock import patch

from django.db import transaction
from django.test import TestCase
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.accounts.models import Usuario, Membresia
from apps.financiadores.models import Afiliado, Financiador
from apps.instituciones.models import Institucion
from apps.instituciones.serializers import InstitucionSerializer
from apps.registros.models import Ciudadano
from apps.registros.serializers import CiudadanoListadoSerializer, CiudadanoSerializer
from .api import LugaresView
from .contrato import validar_catalogo
from .issue136_test_puros import catalogo_ficticio
from .models import Catalogo, Lugar
from .servicios import ambito, para_traslado, resolver, visibles
from .sincronizacion import sincronizar


class GeografiaIntegracionTest(TestCase):
    def setUp(self):
        self.inst = Institucion.objects.create(nombre="Institución ficticia A")
        self.otra = Institucion.objects.create(nombre="Institución ficticia B")
        self.fin = Financiador.objects.create(nombre="Financiador ficticio", tipo="mutual")
        self.dueno = ambito(institucion_id=self.inst.pk)
        self.usuario = Usuario.objects.create_user("issue136@example.invalid", nombre="Operador ficticio")
        Membresia.objects.create(usuario=self.usuario, institucion=self.inst, rol="admin")
        sincronizar(descargar_fn=lambda: validar_catalogo(catalogo_ficticio()))

    def entrada_oficial(self):
        return {n: {"id": Lugar.objects.get(tipo=n, origen="georef", codigo=c).pk}
                for n, c in (("provincia", "01"), ("partido", "01001"), ("localidad", "01001000001"))}

    def test_manual_se_reutiliza_solo_en_su_organizacion(self):
        entrada = {"localidad": {"manual": "Lugar rural ficticio"}}
        a = resolver(entrada, dueno=self.dueno)
        b = resolver(entrada, dueno=self.dueno)
        c = resolver(entrada, dueno=ambito(institucion_id=self.otra.pk))
        self.assertEqual(a.localidad_id, b.localidad_id)
        self.assertNotEqual(a.localidad_id, c.localidad_id)
        self.assertFalse(visibles(self.dueno).filter(pk=c.localidad_id).exists())
        with self.assertRaises(ValidationError):
            resolver({"localidad": {"id": c.localidad_id}}, dueno=self.dueno)

    def test_fallo_del_guardado_no_deja_sugerencias(self):
        anteriores = Lugar.objects.filter(origen="manual").count()
        with self.assertRaises(ValueError):
            with transaction.atomic():
                resolver({"localidad": {"manual": "No debe persistir"}}, dueno=self.dueno)
                raise ValueError("Guardado ficticio fallido")
        self.assertEqual(Lugar.objects.filter(origen="manual").count(), anteriores)

    def test_actualizacion_repetida_no_duplica_y_no_reescribe_domicilio(self):
        ubicacion = resolver(self.entrada_oficial(), dueno=self.dueno)
        ids = list(Lugar.objects.filter(origen="georef").order_by("pk").values_list("pk", flat=True))
        datos = catalogo_ficticio()
        datos["localidad"][0]["nombre"] = "Nombre actualizado"
        sincronizar(descargar_fn=lambda: validar_catalogo(datos))
        ubicacion.refresh_from_db()
        self.assertEqual(ubicacion.datos()["localidad"]["nombre"], "Localidad de prueba")
        self.assertEqual(ids, list(Lugar.objects.filter(origen="georef").order_by("pk").values_list("pk", flat=True)))

    def test_fallo_de_descarga_conserva_catalogo_valido(self):
        version = Catalogo.objects.get(pk=1).version
        def fallar():
            raise ValueError("Descarga ficticia incompleta")
        with self.assertRaises(ValueError):
            sincronizar(descargar_fn=fallar)
        self.assertEqual(Catalogo.objects.get(pk=1).version, version)
        self.assertEqual(Lugar.objects.filter(origen="georef", activo=True).count(), 4)
        self.assertTrue(Catalogo.objects.get(pk=1).error)

    def test_jerarquia_incompatible_se_rechaza(self):
        entrada = self.entrada_oficial()
        entrada["provincia"] = {"id": Lugar.objects.get(tipo="provincia", codigo="02").pk}
        with self.assertRaises(ValidationError):
            resolver(entrada, dueno=self.dueno)

    def test_traslado_conserva_marca_manual_sin_compartir_referencia(self):
        ubicacion = resolver({"localidad": {"manual": "Lugar privado ficticio"}}, dueno=self.dueno)
        copia = para_traslado(ubicacion)
        self.assertIsNone(copia.localidad_id)
        self.assertEqual(copia.datos()["localidad"]["origen"], "manual")
        self.assertEqual(copia.textos, ubicacion.textos)
        self.assertFalse(visibles(ambito(institucion_id=self.otra.pk)).filter(pk=ubicacion.localidad_id).exists())

    def test_serializers_persisten_y_el_listado_no_revela_geografia(self):
        p = CiudadanoSerializer(data={"institucion": self.inst.pk, "nombre": "Paciente ficticio", "domicilio": "Detalle ficticio", "geografia": self.entrada_oficial()})
        p.is_valid(raise_exception=True)
        obj = p.save()
        self.assertEqual(p.data["geografia"]["provincia"]["origen"], "georef")
        self.assertNotIn("geografia", CiudadanoListadoSerializer(obj).data)
        self.assertEqual(CiudadanoListadoSerializer(obj).data["domicilio"], "••••••")
        i = InstitucionSerializer(self.inst, data={"geografia": self.entrada_oficial()}, partial=True)
        i.is_valid(raise_exception=True)
        self.assertIsNotNone(i.save().geografia_id)

    def test_actualizacion_textual_legacy_no_deja_referencias_falsas(self):
        obj = Ciudadano.objects.create(institucion=self.inst, nombre="Paciente ficticio", domicilio="Texto anterior", geografia=resolver(self.entrada_oficial(), dueno=self.dueno))
        p = CiudadanoSerializer(obj, data={"domicilio": "Nuevo texto no homologado"}, partial=True)
        p.is_valid(raise_exception=True)
        self.assertIsNone(p.save().geografia_id)

    def test_api_no_permite_consultar_sugerencias_de_otra_institucion(self):
        factory = APIRequestFactory()
        for institucion, esperado in ((self.inst.pk, 200), (self.otra.pk, 403)):
            req = factory.get("/api/geografia/lugares/", {"ambito": "institucion", "organizacion": institucion, "tipo": "localidad"})
            force_authenticate(req, self.usuario)
            self.assertEqual(LugaresView.as_view()(req).status_code, esperado)

    def test_afiliado_conserva_plantilla_v2_y_registra_origen(self):
        from apps.financiadores import padron
        from apps.financiadores.importaciones import CAMPOS_V2
        from apps.financiadores.models import MembresiaFinanciador
        from apps.financiadores.serializers import AfiliadoSerializer
        MembresiaFinanciador.objects.create(usuario=self.usuario, financiador=self.fin, rol="operador")
        obj = Afiliado.objects.create(financiador=self.fin, numero="ficticio", documento="99900000", nombre="Persona ficticia", desde=date(2026, 1, 1))
        obj = padron.editar_ficha(afiliado=obj, usuario=self.usuario, entrada={"revision": obj.revision, "motivo": "Prueba sintética de ubicación", "geografia": {"localidad": {"manual": "Lugar nuevo ficticio"}}})
        self.assertEqual(obj.localidad, "Lugar nuevo ficticio")
        self.assertEqual(AfiliadoSerializer(obj).data["geografia"]["localidad"]["origen"], "manual")
        self.assertNotIn("geografia", CAMPOS_V2)
        self.assertTrue(obj.historial.filter(cambios__has_key="geografia").exists())

    def test_retiro_conserva_historia_pero_impide_nuevas_selecciones(self):
        entrada = self.entrada_oficial()
        ubicacion = resolver(entrada, dueno=self.dueno)
        anterior = ubicacion.datos()
        datos = catalogo_ficticio()
        datos["localidad"][0]["id"] = "01001000002"
        sincronizar(descargar_fn=lambda: validar_catalogo(datos))
        self.assertFalse(Lugar.objects.get(pk=ubicacion.localidad_id).activo)
        ubicacion.refresh_from_db()
        self.assertEqual(ubicacion.datos(), anterior)
        self.assertEqual(resolver(entrada, dueno=self.dueno, anterior=ubicacion).pk, ubicacion.pk)
        with self.assertRaises(ValidationError):
            resolver(entrada, dueno=self.dueno)

    def test_fallo_durante_publicacion_revierte_todos_los_cambios(self):
        version = Catalogo.objects.get(pk=1).version
        anteriores = list(Lugar.objects.order_by("pk").values())
        datos = catalogo_ficticio()
        datos["provincia"][0]["nombre"] = "Cambio que debe revertirse"
        publicar = Lugar.objects.update_or_create
        llamadas = 0

        def fallar_en_segunda_fila(*args, **kwargs):
            nonlocal llamadas
            llamadas += 1
            if llamadas == 2:
                raise RuntimeError("Falla sintética de publicación")
            return publicar(*args, **kwargs)

        with patch.object(Lugar.objects, "update_or_create", side_effect=fallar_en_segunda_fila):
            with self.assertRaises(RuntimeError):
                sincronizar(descargar_fn=lambda: validar_catalogo(datos))
        self.assertEqual(list(Lugar.objects.order_by("pk").values()), anteriores)
        self.assertEqual(Catalogo.objects.get(pk=1).version, version)
        self.assertTrue(Catalogo.objects.get(pk=1).error)

    def test_edicion_geografica_preserva_coordenadas_exactas_y_legado(self):
        self.inst.latitud, self.inst.longitud = -34.12345678, -58.87654321
        self.inst.direccion = "Dirección histórica ficticia"
        self.inst.save()
        serializer = InstitucionSerializer(self.inst, data={"geografia": self.entrada_oficial()}, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        self.inst.refresh_from_db()
        self.assertEqual((self.inst.latitud, self.inst.longitud), (-34.12345678, -58.87654321))
        self.assertEqual(self.inst.direccion, "Dirección histórica ficticia")

    def test_consumidores_fhir_y_exportacion_conservan_marca_manual(self):
        from apps.fhir.recursos import organization, patient
        from apps.financiadores.padron_consulta import valor_columna_padron

        ubicacion = resolver({"localidad": {"manual": "Localidad manual ficticia"}}, dueno=self.dueno)
        paciente = Ciudadano.objects.create(institucion=self.inst, nombre="Paciente ficticio", geografia=ubicacion)
        self.inst.geografia = ubicacion
        self.inst.save(update_fields=["geografia"])
        for recurso in (patient(paciente), organization(self.inst)):
            self.assertIn("Localidad manual ficticia (Manual · sin verificar)", recurso["address"][0]["text"])
        afiliado = Afiliado.objects.create(financiador=self.fin, numero="exportacion-ficticia", documento="99900001",
            nombre="Persona ficticia", desde=date(2026, 1, 1), localidad="Localidad manual ficticia",
            geografia=resolver({"localidad": {"manual": "Localidad manual ficticia"}}, dueno=ambito(financiador_id=self.fin.pk)))
        self.assertEqual(valor_columna_padron(afiliado, "localidad"), "Localidad manual ficticia · Manual · sin verificar")

    def test_productor_de_traslado_no_publica_manuales_del_origen(self):
        from apps.red.motor import _paciente_en

        origen = Ciudadano.objects.create(institucion=self.inst, nombre="Paciente ficticio", documento="99900002",
            domicilio="Domicilio ficticio", geografia=resolver({"localidad": {"manual": "Localidad privada ficticia"}}, dueno=self.dueno))
        destino = _paciente_en(self.otra, origen)
        self.assertNotEqual(destino.geografia_id, origen.geografia_id)
        self.assertIsNone(destino.geografia.localidad_id)
        self.assertEqual(destino.geografia.datos()["localidad"]["origen"], "manual")
        self.assertEqual(destino.domicilio, origen.domicilio)
        self.assertFalse(Lugar.objects.filter(origen="manual", institucion=self.otra).exists())
