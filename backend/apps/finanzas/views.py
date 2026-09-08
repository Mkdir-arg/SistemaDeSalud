from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed, NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response

from apps.auditoria.mixins import AuditaLecturaClinica
from apps.common import BaseModelViewSet

from .models import (
    AjusteCosto,
    AjusteGasto,
    ConceptoGasto,
    ConcesionFinanciera,
    DefinicionComponente,
    Gasto,
    HechoAtencionCosteable,
    Prestacion,
    ValorComponente,
)
from .permisos import concesiones_financieras_de, tiene_concesion_financiera
from .serializers import (
    AjusteCostoSerializer,
    AjusteGastoSerializer,
    ConceptoGastoSerializer,
    ConcesionFinancieraSerializer,
    CorreccionSnapshotCosteoSerializer,
    DefinicionComponenteSerializer,
    GastoSerializer,
    HechoAtencionCosteableSerializer,
    PrestacionSerializer,
    RechazoGastoSerializer,
    ValorComponenteSerializer,
)
from .services import aprobar_gasto, corregir_snapshot_componentes, rechazar_gasto, registrar_ajuste_costo, registrar_ajuste_gasto, registrar_gasto


class PuedeVerCostosPaciente(BasePermission):
    """El detalle se habilita por área y por sensibilidad congelada."""

    def has_permission(self, request, view):
        usuario = request.user
        return bool(
            usuario and usuario.is_authenticated and (
                usuario.is_superuser
                or concesiones_financieras_de(
                    usuario,
                    ConcesionFinanciera.Accion.VER_COSTOS,
                ).exists()
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
            concesiones_financieras_de(usuario, accion).exists()
            for accion in (
                ConcesionFinanciera.Accion.CONFIGURAR_GASTOS_ESPERADOS,
                ConcesionFinanciera.Accion.REGISTRAR_GASTOS,
            )
        )


class PuedeVerGastos(BasePermission):
    def has_permission(self, request, view):
        usuario = request.user
        return bool(
            usuario and usuario.is_authenticated and (
                usuario.is_superuser
                or concesiones_financieras_de(
                    usuario,
                    ConcesionFinanciera.Accion.VER_GASTOS,
                ).exists()
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
                    "permite_sensibles": administrativa and concesion.permite_sensibles,
                    "administrativa": administrativa,
                })
        return Response({"superusuario": request.user.is_superuser, "concesiones": filas})


class PrestacionViewSet(CatalogoCostosInstitucionalMixin, BaseModelViewSet):
    queryset = Prestacion.objects.select_related("institucion", "nodo")
    serializer_class = PrestacionSerializer
    institucion_path = "institucion"
    http_method_names = ["get", "head", "options", "post", "patch"]
    filter_fields = ("institucion", "nodo", "activo")
    ordering_fields = ("codigo", "nombre", "id")

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
        serializer.save()


class ConceptoGastoViewSet(BaseModelViewSet):
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
        ):
            for institucion_id, permite_sensibles in concesiones_financieras_de(
                usuario,
                accion,
            ).values_list("membresia__institucion_id", "permite_sensibles"):
                scope = Q(institucion_id=institucion_id)
                if not permite_sensibles:
                    scope &= ~Q(sensible=True)
                alcance |= scope
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


class GastoViewSet(BaseModelViewSet):
    """Fuentes de gasto sin reparto clínico, cargos ni movimientos de dinero."""

    queryset = Gasto.objects.select_related(
        "concepto", "institucion", "area", "registrado_por", "aprobado_por", "rechazado_por",
        "reemplazado_por",
    ).prefetch_related("ajustes__registrado_por")
    serializer_class = GastoSerializer
    permission_classes = [IsAuthenticated, PuedeVerGastos]
    institucion_path = "institucion"
    http_method_names = ["get", "head", "options", "post"]
    filter_fields = ("institucion", "area", "concepto", "estado", "origen", "periodo_economico", "sensible")
    ordering_fields = ("periodo_economico", "registrado", "id")

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
        if usuario.is_superuser:
            return qs
        alcance = Q(pk__in=[])
        concesiones = concesiones_financieras_de(usuario, ConcesionFinanciera.Accion.VER_GASTOS)
        for institucion_id, permite_sensibles in concesiones.filter(todas_las_areas=True).values_list(
            "membresia__institucion_id", "permite_sensibles"
        ):
            scope = Q(institucion_id=institucion_id)
            if not permite_sensibles:
                scope &= ~Q(sensible=True)
            alcance |= scope
        for institucion_id, area_id, permite_sensibles in concesiones.filter(todas_las_areas=False).values_list(
            "membresia__institucion_id", "areas__id", "permite_sensibles"
        ):
            if area_id is not None:
                scope = Q(institucion_id=institucion_id, area_id=area_id)
                if not permite_sensibles:
                    scope &= ~Q(sensible=True)
                alcance |= scope
        return qs.filter(alcance).distinct()

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


class AjusteGastoViewSet(BaseModelViewSet):
    queryset = AjusteGasto.objects.none()
    serializer_class = AjusteGastoSerializer
    permission_classes = [IsAuthenticated, PuedeCorregirGastos]
    http_method_names = ["post", "options"]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            ajuste = registrar_ajuste_gasto(
                serializer.validated_data["gasto"].id,
                serializer.validated_data["importe"],
                serializer.validated_data["motivo"],
                request.user,
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


class AjusteCostoViewSet(BaseModelViewSet):
    """Alta de correcciones históricas; se leen dentro del hecho costeable."""

    queryset = AjusteCosto.objects.none()
    serializer_class = AjusteCostoSerializer
    permission_classes = [IsAuthenticated, PuedeCorregirCosto]
    http_method_names = ["post", "options"]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ajuste = registrar_ajuste_costo(
            serializer.validated_data["imputacion"],
            serializer.validated_data["importe"],
            serializer.validated_data["motivo"],
            request.user,
        )
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
        qs = super().get_queryset()
        usuario = self.request.user
        if usuario.is_superuser:
            return qs

        alcance = Q(pk__in=[])
        concesiones = concesiones_financieras_de(usuario, ConcesionFinanciera.Accion.VER_COSTOS)
        for institucion_id, permite_sensibles in concesiones.filter(todas_las_areas=True).values_list(
            "membresia__institucion_id", "permite_sensibles"
        ):
            scope = Q(institucion_id=institucion_id)
            if not permite_sensibles:
                scope &= ~Q(componentes_esperados__sensible=True)
            alcance |= scope
        for institucion_id, area_id, permite_sensibles in concesiones.filter(todas_las_areas=False).values_list(
            "membresia__institucion_id", "areas__id", "permite_sensibles"
        ):
            if area_id is not None:
                scope = Q(institucion_id=institucion_id, area_origen_id=area_id)
                if not permite_sensibles:
                    scope &= ~Q(componentes_esperados__sensible=True)
                alcance |= scope
        return qs.filter(alcance).distinct()
