"""
Auditoría de permisos de escritura, extremo a extremo y por rol.

Los tests de `test_permisos.py` cubren combinaciones elegidas a mano: un médico
no crea flujos, un configurador no crea áreas. Eso verifica lo que alguien pensó
en verificar, y el agujero típico es el otro: el viewset que se agregó después y
al que nadie le declaró `capacidad_requerida`, que queda abierto a cualquier
miembro de la institución sin que nada avise.

Acá se recorren TODOS los viewsets registrados contra TODOS los roles y se
compara lo que el servidor hace con lo que el rol declara poder hacer. Cubre
también los que se agreguen mañana.

Se prueba pegándole a la API, no llamando al permiso: lo que importa no es que
la clase devuelva False sino que el pedido HTTP termine en 403.
"""
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import Membresia, Usuario
from apps.common import ROL_CAPACIDADES
from apps.instituciones.models import Institucion
from cauce.api import router

# Sin `capacidad_requerida` un viewset queda abierto a cualquier miembro. Puede
# estar bien, pero tiene que ser una decisión escrita y no un olvido.
SIN_CAPACIDAD_A_PROPOSITO = {
    # Avisos personales: el queryset ya filtra por `usuario=request.user`, así
    # que cada uno sólo ve y marca como leídos los suyos. Una capacidad de rol
    # acá no protegería nada que el queryset no proteja ya.
    "notificaciones",
    # Registro de accesos clínicos: no se gatea por capacidad sino por rol de
    # conducción (`PuedeAuditar`). Ninguna de las cuatro capacidades sirve acá:
    # «registros» la tiene todo el que atiende, y el registro dice quién miró la
    # historia de quién —es tan sensible como lo que audita—. Además es de sólo
    # lectura, así que no hay escritura que gatear.
    "accesos-clinicos",
}


class BarridaDePermisosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.inst = Institucion.objects.create(nombre="Hospital Central")
        cls.usuarios = {}
        for rol in ROL_CAPACIDADES:
            u = Usuario.objects.create_user(f"{rol}@test.local", "x", nombre=rol)
            Membresia.objects.create(usuario=u, institucion=cls.inst, rol=rol, activo=True)
            cls.usuarios[rol] = u

    def _cliente(self, rol):
        c = APIClient()
        c.force_authenticate(self.usuarios[rol])
        return c

    def _capacidad_de(self, viewset, accion=None):
        por_accion = getattr(viewset, "capacidad_por_accion", None) or {}
        return por_accion.get(accion) or getattr(viewset, "capacidad_requerida", None)

    @staticmethod
    def _habilita(cap, caps):
        """
        ¿Las capacidades del rol alcanzan para `cap`?

        `capacidad_requerida` puede declarar varias capacidades alternativas
        (usuarios y membresías admiten `config_institucional` o
        `gobierno_plataforma`): cualquiera de ellas habilita. Comparar la tupla
        entera contra la lista de capacidades da siempre False, y entonces la
        barrida reporta como agujero justo el recurso más sensible que hay.
        """
        requeridas = cap if isinstance(cap, (tuple, list, set)) else (cap,)
        return any(c in caps for c in requeridas)

    def test_cada_rol_escribe_solo_donde_su_capacidad_lo_habilita(self):
        """
        Un POST con el cuerpo vacío alcanza: interesa si el pedido muere en el
        permiso (403) o llega al serializer (400). Que el cuerpo sea inválido es
        justamente lo que confirma que pasó el control de acceso.
        """
        fallas = []
        for prefijo, viewset, _ in router.registry:
            cap = self._capacidad_de(viewset, "create")
            if not cap:
                continue
            for rol, caps in ROL_CAPACIDADES.items():
                r = self._cliente(rol).post(f"/api/{prefijo}/", {}, format="json")
                if r.status_code == 405:
                    continue  # solo lectura
                prohibido = r.status_code == 403
                deberia_poder = self._habilita(cap, caps)
                if prohibido == deberia_poder:
                    fallas.append(
                        f"{rol} → POST /api/{prefijo}/ (requiere «{cap}»): "
                        f"{'lo rechazó y no debería' if prohibido else 'lo dejó pasar y no debería'} "
                        f"[HTTP {r.status_code}]"
                    )
        self.assertEqual(fallas, [], "\n" + "\n".join(fallas))

    def test_no_hay_viewsets_sin_capacidad_declarada_sin_querer(self):
        """
        El agujero que este archivo existe para tapar: un recurso nuevo que nadie
        gateó queda escribible por cualquier miembro de la institución.
        """
        sin_declarar = {
            prefijo
            for prefijo, viewset, _ in router.registry
            if not getattr(viewset, "capacidad_requerida", None)
        }
        nuevos = sin_declarar - SIN_CAPACIDAD_A_PROPOSITO
        self.assertEqual(
            nuevos, set(),
            "estos recursos no declaran `capacidad_requerida` y quedan abiertos a "
            "cualquier miembro: declarala, o agregalos a SIN_CAPACIDAD_A_PROPOSITO "
            "con el motivo escrito",
        )
        # Y al revés: si un recurso exento dejó de existir, que la lista no se
        # quede con nombres viejos que ya no eximen nada.
        self.assertEqual(
            SIN_CAPACIDAD_A_PROPOSITO - sin_declarar, set(),
            "la lista de exenciones nombra recursos que ya no existen o que ahora "
            "sí declaran capacidad",
        )

    def test_la_lectura_de_datos_clinicos_pide_capacidad(self):
        """
        `protege_lectura` es lo que distingue «cualquiera del hospital puede ver
        la lista de áreas» de «la historia clínica la ve quien atiende». Sin
        esto, la lectura queda abierta a cualquier miembro.
        """
        fallas = []
        for prefijo, viewset, _ in router.registry:
            if not getattr(viewset, "protege_lectura", False):
                continue
            cap = self._capacidad_de(viewset, "list")
            for rol, caps in ROL_CAPACIDADES.items():
                r = self._cliente(rol).get(f"/api/{prefijo}/")
                prohibido = r.status_code == 403
                if prohibido == self._habilita(cap, caps):
                    fallas.append(f"{rol} → GET /api/{prefijo}/ [HTTP {r.status_code}]")
        self.assertEqual(fallas, [], "\n" + "\n".join(fallas))

    def test_sin_sesion_no_se_lee_nada(self):
        anon = APIClient()
        for prefijo, _, _ in router.registry:
            with self.subTest(recurso=prefijo):
                self.assertIn(anon.get(f"/api/{prefijo}/").status_code, (401, 403))

    def test_todos_los_listados_tienen_un_orden(self):
        """
        Un queryset sin orden se pagina distinto entre pedidos: un registro puede
        salir en dos páginas o en ninguna. Con `nodos` y `conexiones` eso
        significa que un flujo grande puede cargarse sin un nodo o sin una
        flecha, y el editor no tiene cómo notarlo.

        El proyecto ya trata este problema (`OrdenEstable` agrega el id como
        desempate cuando se pide un orden), pero eso no cubre el caso de no pedir
        ninguno. Esto sí.
        """
        sin_orden = [
            f"/api/{prefijo}/ ({viewset.queryset.model.__name__})"
            for prefijo, viewset, _ in router.registry
            if getattr(viewset, "queryset", None) is not None
            and not (viewset.queryset.model._meta.ordering or viewset.queryset.query.order_by)
        ]
        self.assertEqual(sin_orden, [], "listados sin orden: la paginación es inestable")

    def test_el_superusuario_de_plataforma_pasa_siempre(self):
        """Es quien tiene que poder arreglar una institución rota."""
        su = Usuario.objects.create_user("su@test.local", "x", is_superuser=True, is_staff=True)
        c = APIClient()
        c.force_authenticate(su)
        for prefijo, viewset, _ in router.registry:
            if not getattr(viewset, "capacidad_requerida", None):
                continue
            with self.subTest(recurso=prefijo):
                self.assertNotEqual(c.post(f"/api/{prefijo}/", {}, format="json").status_code, 403)
