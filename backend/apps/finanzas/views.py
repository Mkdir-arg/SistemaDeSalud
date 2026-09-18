from datetime import date, datetime, time
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.db.models import Case, CharField, DateField, DecimalField, Exists, F, OuterRef, Prefetch, Q, Subquery, Sum, Value, When
from django.db.models.functions import Coalesce, TruncMonth
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed, NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response

from apps.auditoria.mixins import AuditaLecturaClinica
from apps.common import BaseModelViewSet, tiene_capacidad
from apps.accounts.models import Membresia
from apps.flujos.models import Nodo, VersionFlujo

from .models import (
    AjusteCosto,
    AjusteGasto,
    AtribucionReparto,
    ConceptoGasto,
    ConcesionFinanciera,
    DefinicionComponente,
    ExpectativaGasto,
    Gasto,
    HechoAtencionCosteable,
    ObligacionFinanciera,
    Prestacion,
    TrabajoReparto,
    ValorComponente,
)
from .permisos import alcance_financiero_q, concesiones_financieras_de, hechos_en_alcance_financiero, tiene_concesion_financiera, tiene_accion_financiera, instituciones_admin_financiero, gastos_en_alcance_financiero
from .auditoria import AuditaLecturaFinanciera
from .filtros import filtrar_rangos
from .calendario import gastos_de_control_mensual
from .editor_permisos import EditorPermisosSerializer, version_editor
from .serializers import (
    AjusteCostoSerializer,
    AjusteGastoSerializer,
    ConceptoGastoSerializer,
    ConcesionFinancieraSerializer,
    ConcesionesMultiplesSerializer,
    CorreccionSnapshotCosteoSerializer,
    DefinicionComponenteSerializer,
    GastoSerializer,
    HechoAtencionCosteableSerializer,
    PrestacionSerializer,
    RechazoGastoSerializer,
    ValorComponenteSerializer,
)
from .services import aprobar_gasto, corregir_snapshot_componentes, decidir_ajuste, rechazar_gasto, registrar_ajuste_costo, registrar_ajuste_gasto, registrar_gasto


class PuedeVerCostosPaciente(BasePermission):
    """El detalle se habilita por área y por sensibilidad congelada."""

    def has_permission(self, request, view):
        usuario = request.user
        return bool(
            usuario and usuario.is_authenticated and (
                usuario.is_superuser
                or tiene_accion_financiera(usuario, ConcesionFinanciera.Accion.VER_COSTOS)
            )
        )

    def has_object_permission(self, request, view, obj):
        if tiene_concesion_financiera(
            request.user,
            ConcesionFinanciera.Accion.VER_COSTOS,
            obj.institucion_id,
            obj.area_origen_id,
            sensible=True,
        ):
            return True
        return (
            tiene_concesion_financiera(
                request.user,
                ConcesionFinanciera.Accion.VER_COSTOS,
                obj.institucion_id,
                obj.area_origen_id,
            )
            and not obj.componentes_esperados.filter(sensible=True).exists()
            and not obj.atribuciones_reparto.filter(
                reparto__gasto__sensible=True,
                reparto__reemplazado_por__isnull=True,
            ).exists()
        )


class PuedeConfigurarCatalogoCostos(BasePermission):
    """La configuración de catálogo es institucional, no clínica."""

    def has_permission(self, request, view):
        usuario = request.user
        return bool(
            usuario and usuario.is_authenticated and (
                usuario.is_superuser
                or concesiones_financieras_de(
                    usuario,
                    ConcesionFinanciera.Accion.CONFIGURAR_COMPONENTES,
                ).filter(todas_las_areas=True).exists()
            )
        )

    def has_object_permission(self, request, view, obj):
        institucion_id = _institucion_catalogo(obj)
        return institucion_id is not None and tiene_concesion_financiera(
            request.user,
            ConcesionFinanciera.Accion.CONFIGURAR_COMPONENTES,
            institucion_id,
        )


class PuedeGestionarValoresComponentes(BasePermission):
    """Lee valores configurables y habilita alta/corrección según su acción."""

    ACCIONES = (
        ConcesionFinanciera.Accion.CONFIGURAR_COMPONENTES,
        ConcesionFinanciera.Accion.CORREGIR_COSTOS,
    )

    def has_permission(self, request, view):
        usuario = request.user
        if not (usuario and usuario.is_authenticated):
            return False
        if usuario.is_superuser:
            return True
        return any(
            concesiones_financieras_de(usuario, accion).filter(todas_las_areas=True).exists()
            for accion in self.ACCIONES
        )

    def has_object_permission(self, request, view, obj):
        return any(
            tiene_concesion_financiera(
                request.user,
                accion,
                _institucion_catalogo(obj),
                sensible=obj.componente.sensible,
            )
            for accion in self.ACCIONES
        )


class PuedeCorregirCosto(BasePermission):
    def has_permission(self, request, view):
        usuario = request.user
        return bool(
            usuario and usuario.is_authenticated and (
                usuario.is_superuser
                or concesiones_financieras_de(
                    usuario,
                    ConcesionFinanciera.Accion.CORREGIR_COSTOS,
                    sensible=True,
                ).exists()
            )
        )


class PuedeGestionarConceptosGasto(BasePermission):
    """El catálogo se consulta para cargar gastos y se administra aparte."""

    def has_permission(self, request, view):
        usuario = request.user
        if not (usuario and usuario.is_authenticated):
            return False
        if usuario.is_superuser:
            return True
        if getattr(view, "action", None) in {"create", "partial_update"}:
            return concesiones_financieras_de(
                usuario,
                ConcesionFinanciera.Accion.CONFIGURAR_GASTOS_ESPERADOS,
            ).filter(todas_las_areas=True).exists()
        return any(
            tiene_accion_financiera(usuario, accion)
            for accion in (
                ConcesionFinanciera.Accion.VER_GASTOS,
                ConcesionFinanciera.Accion.CONFIGURAR_GASTOS_ESPERADOS,
                ConcesionFinanciera.Accion.REGISTRAR_GASTOS,
                ConcesionFinanciera.Accion.CONFIGURAR_REPARTOS,
            )
        )


class PuedeVerGastos(BasePermission):
    def has_permission(self, request, view):
        usuario = request.user
        return bool(
            usuario and usuario.is_authenticated and (
                usuario.is_superuser
                or tiene_accion_financiera(usuario, ConcesionFinanciera.Accion.VER_GASTOS)
            )
        )


class PuedeRegistrarGastos(BasePermission):
    accion = ConcesionFinanciera.Accion.REGISTRAR_GASTOS

    def has_permission(self, request, view):
        usuario = request.user
        return bool(
            usuario and usuario.is_authenticated and (
                usuario.is_superuser or concesiones_financieras_de(usuario, self.accion).exists()
            )
        )


class PuedeAprobarGastos(PuedeRegistrarGastos):
    accion = ConcesionFinanciera.Accion.APROBAR_GASTOS


class PuedeCorregirGastos(PuedeRegistrarGastos):
    accion = ConcesionFinanciera.Accion.CORREGIR_GASTOS


class PuedeAprobarCostos(PuedeRegistrarGastos):
    accion = ConcesionFinanciera.Accion.APROBAR_COSTOS


class PuedeVerAjustesCosto(BasePermission):
    def has_permission(self, request, view):
        return tiene_accion_financiera(request.user, ConcesionFinanciera.Accion.VER_COSTOS)


def _institucion_catalogo(obj):
    if getattr(obj, "institucion_id", None) is not None:
        return obj.institucion_id
    prestacion = getattr(obj, "prestacion", None)
    if prestacion is not None:
        return prestacion.institucion_id
    componente = getattr(obj, "componente", None)
    if componente is not None:
        return componente.prestacion.institucion_id
    return None


class CatalogoCostosInstitucionalMixin:
    permission_classes = [IsAuthenticated, PuedeConfigurarCatalogoCostos]

    def get_queryset(self):
        qs = super().get_queryset()
        usuario = self.request.user
        if usuario.is_superuser:
            return qs
        instituciones = concesiones_financieras_de(
            usuario,
            ConcesionFinanciera.Accion.CONFIGURAR_COMPONENTES,
        ).filter(todas_las_areas=True).values_list("membresia__institucion_id", flat=True)
        return qs.filter(**{f"{self.institucion_path}__in": instituciones}).distinct()

    def verificar_institucion_configurable(self, institucion_id):
        if not tiene_concesion_financiera(
            self.request.user,
            ConcesionFinanciera.Accion.CONFIGURAR_COMPONENTES,
            institucion_id,
        ):
            raise PermissionDenied("No tenés autorización para configurar costos en esta institución.")

    def perform_update(self, serializer):
        if set(serializer.validated_data) != {"activo"}:
            raise ValidationError({"detail": "Sólo podés cambiar el estado activo del catálogo."})
        serializer.save()


class ConcesionFinancieraViewSet(BaseModelViewSet):
    """Administración institucional de los permisos propios de Finanzas."""

    queryset = ConcesionFinanciera.objects.select_related(
        "membresia__usuario", "membresia__institucion"
    ).prefetch_related("areas")
    serializer_class = ConcesionFinancieraSerializer
    capacidad_requerida = "config_institucional"
    protege_lectura = True
    institucion_path = "membresia__institucion"
    filter_fields = ("membresia", "accion", "todas_las_areas", "permite_sensibles", "areas")

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.is_superuser:
            return qs
        # Tener config en A y una membresía operativa en B no permite
        # administrar (ni listar) las concesiones de B.
        instituciones = [
            institucion_id for institucion_id in set(self.instituciones_del_usuario())
            if tiene_capacidad(self.request.user, self.capacidad_requerida, institucion_id)
        ]
        return qs.filter(membresia__institucion_id__in=instituciones)

    def perform_create(self, serializer):
        self._guardar_en_institucion_autorizada(serializer)

    def perform_update(self, serializer):
        # El permiso sobre el objeto original no autoriza una FK de destino.
        self._guardar_en_institucion_autorizada(serializer)

    def _guardar_en_institucion_autorizada(self, serializer):
        membresia = serializer.validated_data.get("membresia")
        if membresia is None:
            membresia = serializer.instance.membresia
        if not tiene_capacidad(self.request.user, self.capacidad_requerida, membresia.institucion_id):
            raise PermissionDenied("No podés administrar concesiones de esa institución.")
        with transaction.atomic():
            # También bloquea el origen si un PATCH traslada una concesión.
            # Todos los caminos de escritura coordinan sobre la membresía.
            ids = {membresia.pk}
            if serializer.instance is not None:
                ids.add(serializer.instance.membresia_id)
            bloqueadas = {m.pk: m for m in Membresia.objects.select_for_update().filter(pk__in=ids).order_by("pk")}
            if membresia.pk not in bloqueadas:
                raise NotFound("La membresía ya no existe.")
            membresia = bloqueadas[membresia.pk]
            if not tiene_capacidad(self.request.user, self.capacidad_requerida, membresia.institucion_id):
                raise PermissionDenied("No podés administrar concesiones de esa institución.")
            actual = None
            if serializer.instance is not None:
                actual = get_object_or_404(self.get_queryset(), pk=serializer.instance.pk)
                if actual.membresia_id != serializer.instance.membresia_id:
                    raise ValidationError("La concesión cambió de membresía. Volvé a consultarla.")
                self.check_object_permissions(self.request, actual)
            # La validación previa al lock no alcanza: otro administrador pudo
            # cambiar la acción, el alcance o la vigencia de la membresía.
            vigente = self.get_serializer(actual, data=self.request.data, partial=serializer.partial)
            vigente.is_valid(raise_exception=True)
            try:
                serializer.instance = vigente.save(membresia=membresia)
            except DjangoValidationError as error:
                raise ValidationError(getattr(error, "message_dict", error.messages)) from error

    def perform_destroy(self, instance):
        with transaction.atomic():
            get_object_or_404(Membresia.objects.select_for_update(), pk=instance.membresia_id)
            actual = get_object_or_404(self.get_queryset(), pk=instance.pk)
            if actual.membresia_id != instance.membresia_id:
                raise ValidationError("La concesión cambió de membresía. Volvé a consultarla.")
            self.check_object_permissions(self.request, actual)
            actual.delete()

    def _estado_editor(self, membresia):
        concesiones = list(self.get_serializer(
            self.queryset.filter(membresia=membresia).order_by("accion"), many=True,
        ).data)
        heredadas = [accion for accion in ConcesionFinanciera.Accion.values if
                     instituciones_admin_financiero(membresia.usuario, accion).filter(institucion_id=membresia.institucion_id).exists()]
        otras = list(self.get_serializer(self.queryset.filter(
            membresia__usuario_id=membresia.usuario_id,
            membresia__institucion_id=membresia.institucion_id, membresia__activo=True,
        ).exclude(membresia=membresia).order_by("membresia_id", "accion"), many=True).data)
        return {
            "membresia": membresia.pk, "activo": membresia.activo,
            "concesiones": concesiones, "heredadas": heredadas,
            "otras_membresias": otras,
            "version_esperada": version_editor(membresia, concesiones, heredadas),
        }

    @action(detail=False, methods=["get", "put"], url_path="editar-membresia")
    def editar_membresia(self, request):
        """Reemplaza sólo el bloque explícito elegido, sin sumar otros alcances."""
        if request.method == "PUT":
            entrada = EditorPermisosSerializer(data=request.data)
            entrada.is_valid(raise_exception=True)
            datos = entrada.validated_data
            membresia_id = datos["membresia"]
        else:
            valor = str(request.query_params.get("membresia", ""))
            if not valor.isdigit() or int(valor) < 1:
                raise ValidationError({"membresia": "Elegí una membresía válida."})
            membresia_id = int(valor)
        with transaction.atomic():
            membresia = get_object_or_404(Membresia.objects.select_for_update(), pk=membresia_id)
            if not tiene_capacidad(request.user, self.capacidad_requerida, membresia.institucion_id):
                raise PermissionDenied("No podés administrar concesiones de esa institución.")
            estado = self._estado_editor(membresia)
            if request.method == "GET":
                return Response(estado)
            if datos["version_esperada"] != estado["version_esperada"]:
                return Response({"detail": "Los permisos cambiaron mientras editabas. Volvé a consultarlos antes de guardar."}, status=status.HTTP_409_CONFLICT)
            actuales = {c.accion: c for c in self.queryset.filter(membresia=membresia)}
            entradas = []
            conservar = set()
            for fila in datos["concesiones"]:
                actual = actuales.get(fila["accion"])
                conservar.add(fila["accion"])
                if not membresia.activo:
                    # En una membresía inactiva se permite conservar o revocar,
                    # nunca otorgar ni cambiar alcances.
                    iguales = actual is not None and all((
                        actual.todas_las_areas == fila["todas_las_areas"],
                        actual.permite_sensibles == fila["permite_sensibles"],
                        sorted(a.pk for a in actual.areas.all()) == sorted(fila["areas"]),
                    ))
                    if not iguales:
                        raise ValidationError({"membresia": "La membresía está inactiva: sólo podés conservar o revocar sus permisos."})
                    continue
                serializer = self.get_serializer(actual, data={**fila, "membresia": membresia.pk})
                serializer.is_valid(raise_exception=True)
                entradas.append(serializer)
            # Nada se escribe hasta que el bloque completo pasó validación.
            self.queryset.filter(membresia=membresia).exclude(accion__in=conservar).delete()
            for serializer in entradas:
                serializer.save(membresia=membresia)
            return Response(self._estado_editor(membresia))

    @action(detail=False, methods=["post"], url_path="otorgar-multiples")
    def otorgar_multiples(self, request):
        entrada = ConcesionesMultiplesSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        datos = entrada.validated_data
        if not tiene_capacidad(request.user, self.capacidad_requerida, datos["membresia"].institucion_id):
            raise PermissionDenied("No podés administrar concesiones de esa institución.")
        with transaction.atomic():
            # Serializa altas para la misma persona, incluida la comprobación de duplicados.
            membresia = get_object_or_404(Membresia.objects.select_for_update(), pk=datos["membresia"].pk)
            if not tiene_capacidad(request.user, self.capacidad_requerida, membresia.institucion_id):
                raise PermissionDenied("No podés administrar concesiones de esa institución.")
            comunes = {
                "membresia": membresia.pk,
                "todas_las_areas": datos["todas_las_areas"],
                "permite_sensibles": datos["permite_sensibles"],
                "areas": [area.pk for area in datos.get("areas", [])],
            }
            entradas = [self.get_serializer(data={**comunes, "accion": accion}) for accion in datos["acciones"]]
            for serializer in entradas:
                serializer.is_valid(raise_exception=True)
            for serializer in entradas:
                serializer.save()
            return Response([serializer.data for serializer in entradas], status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def mias(self, request):
        """Describe permisos propios para UI; nunca concede autorización nueva."""
        filas = []
        for accion in ConcesionFinanciera.Accion.values:
            for concesion in concesiones_financieras_de(request.user, accion).select_related(
                "membresia"
            ).prefetch_related("areas"):
                administrativa = concesion.membresia.rol == "admin"
                filas.append({
                    "institucion": concesion.membresia.institucion_id,
                    "accion": accion,
                    "todas_las_areas": concesion.todas_las_areas,
                    "areas": [area.pk for area in concesion.areas.all()],
                    "permite_sensibles": concesion.permite_sensibles,
                    "administrativa": administrativa,
                })
            for institucion_id in instituciones_admin_financiero(request.user, accion).distinct():
                filas.append({
                    "institucion": institucion_id, "accion": accion,
                    "todas_las_areas": True, "areas": [], "permite_sensibles": True,
                    "administrativa": True, "origen": "rol_admin",
                })
        return Response({"superusuario": request.user.is_superuser, "concesiones": filas})


class PrestacionViewSet(CatalogoCostosInstitucionalMixin, BaseModelViewSet):
    queryset = Prestacion.objects.select_related("institucion", "nodo")
    serializer_class = PrestacionSerializer
    institucion_path = "institucion"
    http_method_names = ["get", "head", "options", "post", "patch"]
    filter_fields = ("institucion", "nodo", "activo")
    ordering_fields = ("codigo", "nombre", "id")

    def get_permissions(self):
        # Configurar cobros necesita identificar prestaciones, no sus costos.
        # Sólo esta lectura amplía el catálogo: no habilita cambios ni valores.
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated()]
        return super().get_permissions()

    def get_queryset(self):
        if self.action not in ("list", "retrieve"):
            return super().get_queryset()
        usuario = self.request.user
        if usuario.is_active and usuario.is_superuser:
            return BaseModelViewSet.get_queryset(self)
        instituciones = set()
        for accion in (ConcesionFinanciera.Accion.CONFIGURAR_COMPONENTES, ConcesionFinanciera.Accion.CONFIGURAR_COBROS):
            instituciones.update(concesiones_financieras_de(usuario, accion).filter(
                todas_las_areas=True,
            ).values_list("membresia__institucion_id", flat=True))
        if not instituciones:
            raise PermissionDenied("No tenés autorización para consultar el catálogo de prestaciones.")
        return BaseModelViewSet.get_queryset(self).filter(institucion_id__in=instituciones)

    @action(detail=False, methods=["get"], url_path="atenciones-disponibles")
    def atenciones_disponibles(self, request):
        try:
            institucion_id = int(request.query_params.get("institucion", ""))
        except (TypeError, ValueError):
            raise ValidationError({"institucion": "Indicá una institución válida."})
        self.verificar_institucion_configurable(institucion_id)
        nodos = Nodo.objects.filter(
            version__flujo__institucion_id=institucion_id,
            version__estado=VersionFlujo.Estado.PUBLICADA, tipo=Nodo.Tipo.ATENCION,
        ).select_related("version__flujo__area").order_by("version__flujo__titulo", "version__numero", "id")
        return Response([{
            "id": nodo.pk, "titulo": nodo.titulo,
            "flujo_nombre": nodo.version.flujo.titulo, "version_numero": nodo.version.numero,
            "area": nodo.version.flujo.area_id,
            "area_nombre": nodo.version.flujo.area.nombre if nodo.version.flujo.area_id else None,
        } for nodo in nodos])

    def perform_create(self, serializer):
        self.verificar_institucion_configurable(serializer.validated_data["institucion"].id)
        serializer.save()


class DefinicionComponenteViewSet(CatalogoCostosInstitucionalMixin, BaseModelViewSet):
    queryset = DefinicionComponente.objects.select_related("prestacion__institucion", "prestacion__nodo")
    serializer_class = DefinicionComponenteSerializer
    institucion_path = "prestacion__institucion"
    http_method_names = ["get", "head", "options", "post", "patch"]
    filter_fields = ("prestacion", "fuente", "activo", "sensible")
    ordering_fields = ("codigo", "nombre", "orden", "id")

    def perform_create(self, serializer):
        self.verificar_institucion_configurable(
            serializer.validated_data["prestacion"].institucion_id
        )
        serializer.save()

    def perform_update(self, serializer):
        if not set(serializer.validated_data) <= {"activo", "sensible"}:
            raise ValidationError({"detail": "Sólo podés cambiar el estado activo o la sensibilidad del componente."})
        # Desclasificar expone los valores existentes: requiere permiso sobre
        # la sensibilidad original, no sólo sobre el resultado del PATCH.
        if serializer.instance.sensible and serializer.validated_data.get("sensible") is False:
            if not tiene_concesion_financiera(
                self.request.user, ConcesionFinanciera.Accion.CONFIGURAR_COMPONENTES,
                serializer.instance.prestacion.institucion_id, sensible=True,
            ):
                raise PermissionDenied("No tenés autorización para quitar la protección sensible de este componente.")
        serializer.save()


class ConceptoGastoViewSet(AuditaLecturaFinanciera, BaseModelViewSet):
    """Catálogo institucional que antecede a cualquier carga real de gasto."""

    queryset = ConceptoGasto.objects.select_related("institucion", "registrado_por")
    serializer_class = ConceptoGastoSerializer
    permission_classes = [IsAuthenticated, PuedeGestionarConceptosGasto]
    institucion_path = "institucion"
    http_method_names = ["get", "head", "options", "post", "patch"]
    filter_fields = ("institucion", "activo", "sensible")
    ordering_fields = ("codigo", "nombre", "id")

    def get_queryset(self):
        qs = super().get_queryset()
        usuario = self.request.user
        if usuario.is_superuser:
            return qs
        alcance = Q(pk__in=[])
        for accion in (
            ConcesionFinanciera.Accion.CONFIGURAR_GASTOS_ESPERADOS,
            ConcesionFinanciera.Accion.REGISTRAR_GASTOS,
            ConcesionFinanciera.Accion.CONFIGURAR_REPARTOS,
        ):
            for institucion_id, permite_sensibles in concesiones_financieras_de(
                usuario,
                accion,
            ).values_list("membresia__institucion_id", "permite_sensibles"):
                scope = Q(institucion_id=institucion_id)
                if not permite_sensibles:
                    scope &= ~Q(sensible=True)
                alcance |= scope
        if self.action in {"list", "retrieve"}:
            alcance |= Q(institucion_id__in=instituciones_admin_financiero(usuario, ConcesionFinanciera.Accion.VER_GASTOS))
            # Los lectores pueden elegir conceptos ya presentes en registros de
            # su área; no reciben todo el catálogo por tener permiso de lectura.
            for sensible in (False, True):
                for institucion_id, todas, area_id in concesiones_financieras_de(
                    usuario, ConcesionFinanciera.Accion.VER_GASTOS, sensible=sensible,
                ).values_list("membresia__institucion_id", "todas_las_areas", "areas__id"):
                    if not todas and area_id is None:
                        continue
                    origen = Q(institucion_id=institucion_id)
                    if not todas:
                        origen &= Q(area_id=area_id)
                    if not sensible:
                        origen &= Q(sensible=False)
                    presentes = Q(pk__in=Gasto.objects.filter(origen).values("concepto_id")) | Q(
                        pk__in=ExpectativaGasto.objects.filter(origen).values("concepto_id"),
                    )
                    alcance |= Q(institucion_id=institucion_id, sensible=sensible) & presentes
        return qs.filter(alcance).distinct()

    def _verificar_configuracion(self, institucion_id, sensible):
        if not tiene_concesion_financiera(
            self.request.user,
            ConcesionFinanciera.Accion.CONFIGURAR_GASTOS_ESPERADOS,
            institucion_id,
            sensible=sensible,
        ):
            raise PermissionDenied("No tenés autorización para configurar conceptos de gasto.")

    def perform_create(self, serializer):
        self._verificar_configuracion(
            serializer.validated_data["institucion"].id,
            serializer.validated_data.get("sensible", False),
        )
        serializer.save(registrado_por=self.request.user)

    def perform_update(self, serializer):
        if not set(serializer.validated_data) <= {"activo", "sensible"}:
            raise ValidationError({"detail": "Sólo podés cambiar el estado activo o la sensibilidad del concepto."})
        self._verificar_configuracion(
            serializer.instance.institucion_id,
            serializer.instance.sensible or serializer.validated_data.get("sensible", False),
        )
        serializer.save()


class GastoViewSet(AuditaLecturaFinanciera, BaseModelViewSet):
    """Fuentes de gasto; el vínculo autorizado a su cuenta no duplica importes."""

    queryset = Gasto.objects.select_related(
        "concepto", "institucion", "area", "registrado_por", "aprobado_por", "rechazado_por",
        "reemplazado_por",
    ).prefetch_related("ajustes__registrado_por")
    serializer_class = GastoSerializer
    permission_classes = [IsAuthenticated, PuedeVerGastos]
    institucion_path = "institucion"
    http_method_names = ["get", "head", "options", "post"]
    filter_fields = ("id", "institucion", "area", "concepto", "estado", "origen", "periodo_economico", "sensible")
    ordering_fields = (
        "periodo_economico", "registrado", "id", "concepto_nombre", "area__nombre",
        "importe", "total_ajustes", "importe_resultante", "estado_operativo", "origen",
    )

    def filter_queryset(self, queryset):
        # Subconsulta independiente: otros joins de permisos o filtros nunca
        # multiplican los ajustes monetarios de un gasto.
        moneda = DecimalField(max_digits=22, decimal_places=2)
        ajustes = AjusteGasto.objects.filter(gasto_id=OuterRef("pk"), estado="aprobado").order_by().values(
            "gasto_id",
        ).annotate(total=Sum("importe")).values("total")[:1]
        queryset = queryset.annotate(
            total_ajustes=Coalesce(Subquery(ajustes), Value(0), output_field=moneda),
            estado_operativo=Case(
                When(reemplazado_por__isnull=False, then=Value("reemplazado")),
                default=F("estado"), output_field=CharField(),
            ),
        ).annotate(importe_resultante=F("importe") + F("total_ajustes"))
        estado = self.request.query_params.get("estado_operativo")
        if estado:
            if estado not in {"reemplazado", *Gasto.Estado.values}:
                raise ValidationError({"estado_operativo": "Estado de gasto no válido."})
            queryset = queryset.filter(estado_operativo=estado)
        vigente = self.request.query_params.get("vigente")
        control = self.request.query_params.get("control_mensual")
        if control:
            if control != "true":
                raise ValidationError({"control_mensual": "Usá true para consultar sólo gastos incluidos en Control mensual."})
            queryset = gastos_de_control_mensual(queryset, self.request.user)
        if vigente in {"true", "1", "false", "0"}:
            queryset = queryset.filter(reemplazado_por__isnull=vigente in {"true", "1"})
        queryset = filtrar_rangos(
            queryset, self.request.query_params,
            importes=("importe", "total_ajustes", "importe_resultante"),
            fechas=("registrado",),
        )
        return super().filter_queryset(queryset)

    def get_permissions(self):
        permisos = [IsAuthenticated()]
        if self.action == "create":
            permisos.append(PuedeRegistrarGastos())
        elif self.action in {"aprobar", "rechazar"}:
            permisos.append(PuedeAprobarGastos())
        else:
            permisos.append(PuedeVerGastos())
        return permisos

    @staticmethod
    def _error_validacion(error):
        return getattr(error, "message_dict", error.messages)

    def get_queryset(self):
        qs = super().get_queryset()
        usuario = self.request.user
        cuentas = ObligacionFinanciera.objects.filter(
            alcance_financiero_q(usuario, ConcesionFinanciera.Accion.VER_DINERO),
            gasto_id=OuterRef("pk"),
        ).order_by()
        return gastos_en_alcance_financiero(qs, usuario).annotate(
            cuenta_por_pagar=Subquery(cuentas.values("pk")[:1]),
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            gasto = registrar_gasto(
                serializer.validated_data["concepto"],
                serializer.validated_data["institucion"],
                serializer.validated_data.get("area"),
                serializer.validated_data["importe"],
                serializer.validated_data["periodo_economico"],
                request.user,
                serializer.validated_data.get("reemplaza"),
                aprobado=serializer.validated_data.get("aprobado"),
            )
        except DjangoValidationError as error:
            raise ValidationError(self._error_validacion(error)) from error
        return Response(self.get_serializer(gasto).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="aprobar")
    def aprobar(self, request, pk=None):
        try:
            gasto = aprobar_gasto(pk, request.user)
        except Gasto.DoesNotExist as error:
            raise NotFound() from error
        except DjangoValidationError as error:
            raise ValidationError(self._error_validacion(error)) from error
        return Response(self.get_serializer(gasto).data)

    @action(detail=True, methods=["post"], url_path="rechazar")
    def rechazar(self, request, pk=None):
        serializer = RechazoGastoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            gasto = rechazar_gasto(pk, serializer.validated_data["motivo"], request.user)
        except Gasto.DoesNotExist as error:
            raise NotFound() from error
        except DjangoValidationError as error:
            raise ValidationError(self._error_validacion(error)) from error
        return Response(self.get_serializer(gasto).data)


class RevisionAjusteMixin:
    @action(detail=True, methods=["post"])
    def aprobar(self, request, pk=None):
        return self._decidir(request, aprobar=True)

    @action(detail=True, methods=["post"])
    def rechazar(self, request, pk=None):
        entrada = RechazoGastoSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        return self._decidir(request, aprobar=False, motivo=entrada.validated_data["motivo"])

    def _decidir(self, request, *, aprobar, motivo=""):
        ajuste = self.get_object()
        try:
            ajuste = decidir_ajuste(ajuste.pk, modelo=type(ajuste), usuario=request.user, aprobar=aprobar, motivo=motivo)
        except DjangoValidationError as error:
            raise ValidationError(GastoViewSet._error_validacion(error)) from error
        return Response(self.get_serializer(ajuste).data)


class AjusteGastoViewSet(RevisionAjusteMixin, AuditaLecturaFinanciera, BaseModelViewSet):
    queryset = AjusteGasto.objects.select_related("gasto")
    serializer_class = AjusteGastoSerializer
    permission_classes = [IsAuthenticated, PuedeCorregirGastos]
    institucion_path = "gasto__institucion"
    filter_fields = ("id", "gasto", "estado")
    http_method_names = ["get", "head", "post", "options"]

    def get_permissions(self):
        permiso = PuedeCorregirGastos if self.action == "create" else PuedeAprobarGastos if self.action in {"aprobar", "rechazar"} else PuedeVerGastos
        return [IsAuthenticated(), permiso()]

    def get_queryset(self):
        fuentes = gastos_en_alcance_financiero(Gasto.objects.all(), self.request.user)
        return super().get_queryset().filter(gasto__in=fuentes)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            ajuste = registrar_ajuste_gasto(
                serializer.validated_data["gasto"].id,
                serializer.validated_data["importe"],
                serializer.validated_data["motivo"],
                request.user,
                aprobado=serializer.validated_data.get("aprobado"),
            )
        except Gasto.DoesNotExist as error:
            raise NotFound() from error
        except DjangoValidationError as error:
            raise ValidationError(GastoViewSet._error_validacion(error)) from error
        return Response(self.get_serializer(ajuste).data, status=status.HTTP_201_CREATED)


class ValorComponenteViewSet(BaseModelViewSet):
    queryset = ValorComponente.objects.select_related(
        "componente__prestacion__institucion", "reemplaza", "registrado_por"
    )
    serializer_class = ValorComponenteSerializer
    permission_classes = [IsAuthenticated, PuedeGestionarValoresComponentes]
    institucion_path = "componente__prestacion__institucion"
    http_method_names = ["get", "head", "options", "post"]
    filter_fields = ("componente", "reemplaza")
    ordering_fields = ("vigente_desde", "registrado", "id")

    def get_queryset(self):
        qs = super().get_queryset()
        usuario = self.request.user
        if usuario.is_superuser:
            return qs
        alcance = Q(pk__in=[])
        for accion in PuedeGestionarValoresComponentes.ACCIONES:
            for institucion_id, permite_sensibles in concesiones_financieras_de(usuario, accion).filter(
                todas_las_areas=True
            ).values_list("membresia__institucion_id", "permite_sensibles"):
                scope = Q(componente__prestacion__institucion_id=institucion_id)
                if not permite_sensibles:
                    scope &= ~Q(componente__sensible=True)
                alcance |= scope
        return qs.filter(alcance).distinct()

    def perform_create(self, serializer):
        componente = serializer.validated_data["componente"]
        reemplaza = serializer.validated_data.get("reemplaza")
        es_correccion = reemplaza and (
            reemplaza.vigente_desde,
            reemplaza.vigente_hasta,
        ) == (
            serializer.validated_data["vigente_desde"],
            serializer.validated_data.get("vigente_hasta"),
        )
        accion = (
            ConcesionFinanciera.Accion.CORREGIR_COSTOS
            if es_correccion
            else ConcesionFinanciera.Accion.CONFIGURAR_COMPONENTES
        )
        if not tiene_concesion_financiera(
            self.request.user,
            accion,
            componente.prestacion.institucion_id,
            sensible=componente.sensible,
        ):
            raise PermissionDenied("No tenés autorización para registrar este valor.")
        serializer.save(registrado_por=self.request.user)


class AjusteCostoViewSet(RevisionAjusteMixin, AuditaLecturaFinanciera, BaseModelViewSet):
    """Alta de correcciones históricas; se leen dentro del hecho costeable."""

    queryset = AjusteCosto.objects.select_related("imputacion__hecho")
    serializer_class = AjusteCostoSerializer
    permission_classes = [IsAuthenticated, PuedeCorregirCosto]
    institucion_path = "imputacion__hecho__institucion"
    filter_fields = ("id", "imputacion", "estado")
    http_method_names = ["get", "head", "post", "options"]

    def get_permissions(self):
        permiso = PuedeCorregirCosto if self.action == "create" else PuedeAprobarCostos if self.action in {"aprobar", "rechazar"} else PuedeVerAjustesCosto
        return [IsAuthenticated(), permiso()]

    def get_queryset(self):
        hechos = hechos_en_alcance_financiero(HechoAtencionCosteable.objects.all(), self.request.user)
        return super().get_queryset().filter(imputacion__hecho__in=hechos)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            ajuste = registrar_ajuste_costo(
                serializer.validated_data["imputacion"],
                serializer.validated_data["importe"],
                serializer.validated_data["motivo"],
                request.user,
                aprobado=serializer.validated_data.get("aprobado"),
            )
        except DjangoValidationError as error:
            raise ValidationError(GastoViewSet._error_validacion(error)) from error
        return Response(self.get_serializer(ajuste).data, status=status.HTTP_201_CREATED)


class HechoAtencionCosteableViewSet(AuditaLecturaClinica, BaseModelViewSet):
    """Costos de atenciones, separados de los recursos clínicos."""

    queryset = (
        HechoAtencionCosteable.objects
        .select_related("ciudadano", "area")
        .prefetch_related(
            "componentes_esperados",
            "pendientes__componente",
            "imputaciones__componente",
            "imputaciones__ajustes",
            Prefetch(
                "atribuciones_reparto",
                queryset=AtribucionReparto.objects.select_related(
                    "reparto__gasto", "reparto__reemplazado_por",
                ),
            ),
        )
    )
    serializer_class = HechoAtencionCosteableSerializer
    permission_classes = [IsAuthenticated, PuedeVerCostosPaciente]
    institucion_path = "institucion"
    ciudadano_path = "ciudadano"
    http_method_names = ["get", "head", "options", "post"]
    filter_fields = ("institucion", "ciudadano", "caso", "area")
    ordering = ("-ocurrida_en", "-id")
    ordering_fields = ("id", "ocurrida_en")

    def filter_queryset(self, queryset):
        periodo = self.request.query_params.get("periodo_economico")
        if periodo:
            try:
                inicio = date.fromisoformat(periodo)
                if inicio.day != 1:
                    raise ValueError
                fin = date(inicio.year + (inicio.month == 12), inicio.month % 12 + 1, 1)
            except (ValueError, OverflowError):
                raise ValidationError({"periodo_economico": "Indicá el primer día del mes (AAAA-MM-01)."})
            queryset = queryset.filter(
                ocurrida_en__gte=timezone.make_aware(datetime.combine(inicio, time.min)),
                ocurrida_en__lt=timezone.make_aware(datetime.combine(fin, time.min)),
            )
        sin_area = self.request.query_params.get("area_sin_asignar")
        if sin_area:
            if sin_area not in {"true", "false"}:
                raise ValidationError({"area_sin_asignar": "Usá true o false."})
            queryset = queryset.filter(area_origen_id__isnull=sin_area == "true")
        return super().filter_queryset(queryset)

    @action(
        detail=True,
        methods=["post"],
        url_path="corregir-snapshot",
        permission_classes=[IsAuthenticated, PuedeCorregirCosto],
    )
    def corregir_snapshot(self, request, pk=None):
        """Reconstruye sólo un snapshot fallido, con autorización y motivo."""
        serializer = CorreccionSnapshotCosteoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            correccion = corregir_snapshot_componentes(
                pk,
                serializer.validated_data["motivo"],
                request.user,
            )
        except DjangoValidationError as error:
            raise ValidationError(error.messages) from error
        return Response(
            CorreccionSnapshotCosteoSerializer(correccion).data,
            status=status.HTTP_201_CREATED,
        )

    def create(self, request, *args, **kwargs):
        # El hecho nace sólo al completar la atención en el motor clínico.
        raise MethodNotAllowed("POST")

    def get_queryset(self):
        trabajos = TrabajoReparto.objects.filter(
            gasto__institucion_id=OuterRef("institucion_id"),
            gasto__periodo_economico=OuterRef("_periodo_reparto"),
            gasto__reemplazado_por__isnull=True, revision__gt=F("revision_procesada"),
        )
        queryset = super().get_queryset().alias(
            _periodo_reparto=TruncMonth("ocurrida_en", tzinfo=timezone.get_current_timezone(), output_field=DateField()),
        ).annotate(reparto_actualizando=Case(
            When(area_origen_id__isnull=True, then=Exists(trabajos.filter(gasto__area_id__isnull=True))),
            default=Exists(trabajos.filter(gasto__area_id=OuterRef("area_origen_id"))),
        ))
        return hechos_en_alcance_financiero(queryset, self.request.user)
