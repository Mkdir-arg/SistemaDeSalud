from django.db import transaction
from django.db.models import Q
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.common import (
    BaseModelViewSet,
    _coerce,
    capacidades_por_institucion_de,
    roles_por_institucion_de,
    tiene_capacidad,
)

from .models import LegajoProfesional, Membresia, Usuario
from .serializers import (
    LegajoProfesionalSerializer,
    MembresiaSerializer,
    UsuarioSerializer,
    validar_rol_asignable,
)


class UsuarioViewSet(BaseModelViewSet):
    """
    Padrón de personas. **No es un directorio global**: cada institución ve sólo
    a las suyas.

    `Usuario` no tiene FK a institución (la pertenencia vive en `Membresia`), así
    que el scope no lo puede dar `institucion_path` y se arma acá a mano. Sin
    esto, el admin del Hospital A veía nombre y email del padrón completo de la
    plataforma —incluido el del Hospital B— y podía asignar a un área a alguien
    de otra institución. Un centro recién creado mostraba un desplegable lleno de
    gente ajena, que es lo que hizo aparecer el problema.

    El super admin de plataforma sí ve todo: administra el directorio en Cauce
    Plataforma, que es donde se dan de alta las instituciones y sus admins.
    """

    queryset = Usuario.objects.all()
    serializer_class = UsuarioSerializer
    capacidad_requerida = ("config_institucional", "gobierno_plataforma")
    # `is_superuser` se filtra en el servidor porque el directorio lista sólo
    # candidatos a admin de institución. Excluirlos en el cliente descontaba de la
    # página ya paginada: el total quedaba mal y podían faltar usuarios reales.
    filter_fields = ("is_active", "is_staff", "is_superuser")
    search_fields = ["email", "nombre", "apellido"]
    ordering_fields = ["apellido", "nombre", "creado", "email"]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        # `?institucion=<id>`: el padrón de esa institución (quien tenga allí una
        # membresía activa). Es lo que necesita cualquier selector de personas de
        # una pantalla de institución.
        inst = (self.request.query_params.get("institucion") or "").strip()
        if inst.isdigit():
            qs = qs.filter(membresias__institucion_id=int(inst), membresias__activo=True)

        if user.is_authenticated and not user.is_superuser and not tiene_capacidad(user, "gobierno_plataforma"):
            # Uno mismo entra siempre: si no, quien no tiene membresía activa no
            # podría ni leer su propia ficha.
            qs = qs.filter(
                Q(membresias__institucion__in=self.instituciones_del_usuario()) | Q(pk=user.pk)
            )

        # Las membresías son varias por persona: sin esto, quien tiene dos roles
        # sale repetido en la lista y descuadra el total de la paginación.
        return qs.distinct()

    def perform_create(self, serializer):
        """Crea la persona y, en el mismo commit, su membresía.

        Una persona sin membresía no pertenece a ninguna institución: con el
        padrón ya acotado, quien la creó no la vuelve a ver ni puede asignarle
        acceso. Era un callejón sin salida, así que el alta desde una institución
        exige decir en qué institución entra y con qué rol.
        """
        user = self.request.user
        datos = self.request.data
        inst = (str(datos.get("institucion") or "")).strip()
        rol = str(datos.get("rol") or Membresia.Rol.ADMINISTRATIVO).strip()

        if not inst.isdigit():
            if user.is_superuser or tiene_capacidad(user, "gobierno_plataforma"):
                serializer.save()  # alta desde Plataforma: la membresía se asigna después
                return
            propias = self.instituciones_del_usuario()
            if len(propias) != 1:
                raise ValidationError({"institucion": ["Indicá en qué institución entra la persona."]})
            inst_id = propias[0]
        else:
            inst_id = int(inst)
            if (
                not user.is_superuser
                and not tiene_capacidad(user, "gobierno_plataforma")
                and inst_id not in self.instituciones_del_usuario()
            ):
                raise ValidationError({"institucion": ["No podés dar de alta personas en esa institución."]})

        if rol not in Membresia.Rol.values:
            raise ValidationError({"rol": [f"Rol inválido: {rol}."]})
        validar_rol_asignable(rol, user)

        with transaction.atomic():
            usuario = serializer.save()
            Membresia.objects.create(usuario=usuario, institucion_id=inst_id, rol=rol)

    @action(detail=False, methods=["get"])
    def me(self, request):
        """Datos del usuario autenticado."""
        data = self.get_serializer(request.user).data
        data["roles_por_institucion"] = roles_por_institucion_de(request.user)
        data["capacidades_por_institucion"] = capacidades_por_institucion_de(request.user)
        return Response(data)

    @action(detail=True, methods=["get"])
    def legajo(self, request, pk=None):
        """Dashboard del legajo profesional: métricas + actividad reciente."""
        from apps.casos.models import Caso, EventoCaso

        user = self.get_object()
        casos = Caso.objects.filter(asignado_a=user)
        atendidos = casos.filter(estado__in=[Caso.Estado.ATENDIDO, Caso.Estado.CERRADO]).count()
        pacientes = casos.exclude(ciudadano=None).values("ciudadano").distinct().count()
        eventos_qs = EventoCaso.objects.filter(autor=user).select_related("caso", "caso__ciudadano")
        atenciones = eventos_qs.filter(titulo__icontains="Atención").count()
        llamados_fila = eventos_qs.filter(titulo__icontains="Llamado desde la fila").count()
        recientes = list(eventos_qs.order_by("-fecha")[:10])
        actividad = [{
            "fecha": e.fecha,
            "paciente": (f"{e.caso.ciudadano.nombre} {e.caso.ciudadano.apellido}".strip()
                         if e.caso and e.caso.ciudadano_id else None),
            "accion": e.titulo,
            "caso": e.caso_id,
        } for e in recientes]
        legajo = getattr(user, "legajo", None)
        return Response({
            "usuario": {
                "id": user.id, "nombre": user.nombre_completo, "email": user.email,
                "especialidad": legajo.especialidad if legajo else "",
                "matricula": legajo.matricula if legajo else "",
            },
            "casos_atendidos": atendidos,
            "pacientes_vistos": pacientes,
            "atenciones": atenciones,
            "llamados_fila": llamados_fila,
            "ultima_actividad": recientes[0].fecha if recientes else None,
            "actividad": actividad,
        })


class MembresiaViewSet(BaseModelViewSet):
    queryset = Membresia.objects.select_related("usuario", "institucion").prefetch_related("areas")
    serializer_class = MembresiaSerializer
    capacidad_requerida = ("config_institucional", "gobierno_plataforma")
    institucion_path = "institucion"
    # `areas` filtra por la M2M: `?areas=3` devuelve el staff de esa área, que es
    # lo que necesita el selector de «reasignar» sin traerse todas las membresías.
    filter_fields = ("usuario", "institucion", "rol", "activo", "areas")
    search_fields = ("usuario__nombre", "usuario__apellido", "usuario__email")
    ordering_fields = ("usuario__apellido", "rol", "creado")

    def get_queryset(self):
        qs = self.queryset
        user = self.request.user
        if user.is_authenticated and not user.is_superuser and not tiene_capacidad(user, "gobierno_plataforma"):
            qs = qs.filter(institucion__in=self.instituciones_del_usuario())
        for field in self.filter_fields:
            value = self.request.query_params.get(field)
            if value not in (None, ""):
                qs = qs.filter(**{field: _coerce(value)})
        return qs


class LegajoProfesionalViewSet(BaseModelViewSet):
    """
    El legajo va con la persona: mismo límite que el padrón.

    Trae especialidad y matrícula —dato profesional identificable— y es
    escribible. Sin scope, el admin de una institución podía leer y pisar la
    matrícula de un médico de otra.
    """

    queryset = LegajoProfesional.objects.select_related("usuario")
    serializer_class = LegajoProfesionalSerializer
    capacidad_requerida = "config_institucional"
    filter_fields = ("usuario",)

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_authenticated and not user.is_superuser:
            qs = qs.filter(
                Q(usuario__membresias__institucion__in=self.instituciones_del_usuario())
                | Q(usuario_id=user.pk)
            ).distinct()
        return qs

    def perform_create(self, serializer):
        self._verificar_persona(serializer)
        serializer.save()

    def perform_update(self, serializer):
        # El objeto ya está acotado por el queryset, pero `usuario` es escribible:
        # sin este chequeo se podía mover el legajo a una persona de otro centro.
        self._verificar_persona(serializer)
        serializer.save()

    def _verificar_persona(self, serializer):
        user = self.request.user
        usuario = serializer.validated_data.get("usuario")
        if not usuario or user.is_superuser or usuario.pk == user.pk:
            return
        propias = set(self.instituciones_del_usuario())
        suyas = set(usuario.membresias.filter(activo=True).values_list("institucion_id", flat=True))
        if not propias & suyas:
            raise ValidationError({"usuario": ["Esa persona no pertenece a tu institución."]})
