from django.db.models import Count, Max, Min
from django.utils.dateparse import parse_date
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response

from apps.common import OrdenEstable

from .models import AccesoClinico

# Los roles que conducen y por lo tanto auditan. Está en una constante y no
# escrito dos veces porque el permiso y el alcance TIENEN que preguntar lo
# mismo: cuando cada mitad usó su propio criterio, quien era jefe en un hospital
# y médico en otro pasaba el portero por el primero y se llevaba el registro
# entero del segundo.
ROLES_QUE_AUDITAN = ("admin", "jefe_area")


def _instituciones_que_audita(usuario):
    """
    En qué instituciones esta persona puede leer el registro de accesos.

    Una membresía activa no alcanza: tiene que ser de conducción. Trabajar en un
    hospital no da derecho a leer quiénes se atendieron ahí —con nombre y
    documento— ni a preguntarle al buscador si tal DNI es paciente de la casa.
    """
    return list(
        usuario.membresias.filter(activo=True, rol__in=ROLES_QUE_AUDITAN)
        .values_list("institucion_id", flat=True)
    )


def _fecha(valor):
    """
    Una fecha de filtro, o nada.

    `parse_date` devuelve None si el texto no tiene forma de fecha y levanta
    ValueError si la tiene pero no existe («2026-02-31»). Ninguna de las dos la
    traduce DRF: llegaban crudas al ORM y salían como 500 sobre la pantalla con
    la que se contesta quién miró una historia.
    """
    try:
        return parse_date((valor or "").strip())
    except ValueError:
        return None


class PuedeAuditar(BasePermission):
    """
    Quién puede leer el registro de accesos.

    El registro dice quién miró la historia de quién: es tan sensible como lo
    que audita. Lo ven el superusuario de plataforma y los roles de conducción
    —admin de institución y jefe de área—, que son quienes tienen que responder
    ante un reclamo. Un médico no audita a sus colegas.

    Es sólo el portero que evita el 200 vacío: QUÉ ve cada uno lo decide
    `get_queryset` con la misma consulta.
    """

    def has_permission(self, request, view):
        u = request.user
        if not (u and u.is_authenticated):
            return False
        if u.is_superuser:
            return True
        return bool(_instituciones_que_audita(u))


class AccesoClinicoSerializer(serializers.ModelSerializer):
    usuario_nombre = serializers.SerializerMethodField()
    usuario_email = serializers.CharField(source="usuario.email", read_only=True)
    paciente = serializers.SerializerMethodField()
    documento = serializers.CharField(source="ciudadano.documento", read_only=True, default=None)
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)
    institucion_nombre = serializers.CharField(
        source="institucion.nombre", read_only=True, default=None
    )

    class Meta:
        model = AccesoClinico
        fields = [
            "id", "usuario", "usuario_nombre", "usuario_email", "ciudadano", "paciente",
            "documento", "institucion", "institucion_nombre", "tipo", "tipo_display",
            "recurso", "objeto_id", "detalle", "resultados", "ip", "momento",
        ]
        read_only_fields = fields

    def get_usuario_nombre(self, obj) -> str | None:
        return obj.usuario.nombre_completo if obj.usuario_id else None

    def get_paciente(self, obj) -> str | None:
        c = obj.ciudadano
        return f"{c.nombre} {c.apellido}".strip() if c else None


class AccesoClinicoViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    """
    Registro de accesos a datos clínicos (Ley 26.529).

    **Sólo lectura, y a propósito.** No hay create, update ni delete: un
    registro de auditoría que se puede escribir o borrar desde la API no sirve
    para auditar nada. Lo escribe el sistema al leer, y nadie más.
    """

    queryset = AccesoClinico.objects.select_related("usuario", "ciudadano", "institucion")
    serializer_class = AccesoClinicoSerializer
    permission_classes = [IsAuthenticated, PuedeAuditar]
    filter_backends = [OrdenEstable, SearchFilter]
    # `ciudadano__nombre` va con `ciudadano__apellido`, igual que el profesional
    # lleva nombre y apellido. SearchFilter parte la consulta en términos y los
    # exige todos: sin el nombre, copiar «Elena Acosta» de la columna «De quién»
    # —el gesto natural el día que llega la carta documento— devolvía cero filas
    # sobre 638 accesos reales, y con eso se redacta un descargo que dice que
    # nadie consultó sus datos.
    search_fields = (
        "usuario__email", "usuario__nombre", "usuario__apellido",
        "ciudadano__nombre", "ciudadano__apellido", "ciudadano__documento",
        "ciudadano__codigo", "recurso",
    )
    ordering_fields = ("momento", "usuario", "recurso")

    def get_queryset(self):
        qs = super().get_queryset()
        u = self.request.user
        if not u.is_superuser:
            # Cada institución audita lo suyo, y «lo suyo» se calcula con la
            # MISMA consulta que el permiso: sólo donde la persona conduce. Con
            # todas las membresías activas, quien es jefe de área en el Hospital
            # A y médico en el B entraba por el A y leía entero el registro del
            # B, buscador por documento incluido.
            #
            # Un listado o una exportación no apuntan a un paciente, así que su
            # institución sale del contexto del pedido (ver
            # `_institucion_del_pedido`): sin eso, el evento más grave del
            # registro —alguien se bajó el padrón— era invisible justo para
            # quien tiene que responder por él. Lo que sigue quedando sólo para
            # plataforma es lo que no se pudo atribuir a ninguna.
            qs = qs.filter(institucion_id__in=_instituciones_que_audita(u))
        p = self.request.query_params
        # Los filtros por id se aplican sólo si el valor puede ser uno. Un
        # `?ciudadano=undefined` —un link viejo, un integrador que manda
        # `Patient/12`— llegaba crudo al ORM y salía 500: el registro se
        # convertía en la razón por la que no se puede contestar quién miró la
        # historia. Mismo criterio que `mixins._anotar_listado`.
        for campo in ("ciudadano", "usuario", "institucion"):
            valor = p.get(campo)
            if valor and str(valor).isdigit():
                qs = qs.filter(**{f"{campo}_id": valor})
        for campo in ("tipo", "recurso"):
            if p.get(campo):
                qs = qs.filter(**{campo: p[campo]})
        desde, hasta = _fecha(p.get("desde")), _fecha(p.get("hasta"))
        if desde:
            qs = qs.filter(momento__date__gte=desde)
        if hasta:
            qs = qs.filter(momento__date__lte=hasta)
        return qs

    @action(detail=False, methods=["get"], url_path="de-paciente")
    def de_paciente(self, request):
        """
        Quién consultó la historia de una persona: `?ciudadano=<id>`.

        Es el derecho concreto que da la ley —el paciente puede pedir esta
        lista— y por eso está separado del listado general: quien atiende un
        reclamo necesita esta respuesta, no un filtro más entre otros.
        """
        cid = request.query_params.get("ciudadano")
        # Un id que no es un id contesta lo mismo que la falta de id: 400 con la
        # frase que la pantalla sabe mostrar. Antes reventaba contra la base y
        # quien atendía el reclamo no podía distinguir «el sistema se rompió» de
        # «nadie miró tu historia».
        if not cid or not str(cid).isdigit():
            return Response({"detail": "Falta el paciente."}, status=400)
        qs = self.filter_queryset(self.get_queryset()).filter(ciudadano_id=cid)
        pagina = self.paginate_queryset(qs)
        datos = self.get_serializer(pagina if pagina is not None else qs, many=True).data
        if pagina is None:
            return Response(datos)
        respuesta = self.get_paginated_response(datos)
        respuesta.data["personas"] = self._personas(qs)
        return respuesta

    def _personas(self, qs):
        """
        Quiénes consultaron, que es la pregunta que hace el paciente.

        La lista cronológica sola contesta «637 accesos en 26 páginas» a alguien
        que preguntó «quién». Abrir la historia una vez escribe más de una fila
        —la ficha y la historia son dos lecturas—, así que el total de eventos
        exagera y nadie lo puede corregir de memoria: acá se cuenta por persona.
        """
        return [
            {
                "usuario": r["usuario"],
                "nombre": f"{r['usuario__nombre']} {r['usuario__apellido']}".strip()
                          or r["usuario__email"],
                "email": r["usuario__email"],
                "veces": r["veces"],
                "primera": r["primera"],
                "ultima": r["ultima"],
            }
            for r in qs.order_by()
            .values("usuario", "usuario__nombre", "usuario__apellido", "usuario__email")
            .annotate(veces=Count("id"), primera=Min("momento"), ultima=Max("momento"))
            .order_by("-veces")
        ]
