"""Prestaciones de cobertura, cuentas y faltantes desde el ámbito hospitalario."""
from decimal import Decimal

from django.db.models import BooleanField, Case, Count, DecimalField, F, Q, Sum, Value, When
from django.db.models.functions import Coalesce, TruncDate, TruncMonth
from django.utils import timezone
from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework import serializers, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from cauce.pagination import Paginacion
from apps.finanzas.auditoria import AuditaLecturaFinanciera
from apps.finanzas.models import HechoAtencionCosteable, ObligacionFinanciera
from apps.finanzas.permisos import alcance_financiero_q, concesiones_financieras_de
from apps.finanzas.saldos import CAMPOS_SALDO, saldos_obligaciones
from apps.instituciones.models import Area
from .models import Financiador, ReservaCobertura


ESTADOS_CUENTAS = ("pendiente", "saldada", "a_devolver", "por_aprobar")
ESTADOS_PENDIENTES = ("pendiente", "arancel_pendiente", "evaluacion_pendiente", "sin_distribucion")


class FiltrosSeguimiento(serializers.Serializer):
    institucion = serializers.IntegerField(min_value=1)
    vista = serializers.ChoiceField(choices=("cuentas", "pendientes", "captura"), default="cuentas")
    desde = serializers.DateField(required=False)
    hasta = serializers.DateField(required=False)
    area = serializers.IntegerField(min_value=1, required=False)
    area_sin_asignar = serializers.BooleanField(required=False)
    financiador = serializers.IntegerField(min_value=1, required=False)
    responsable = serializers.ChoiceField(choices=("financiador", "paciente"), required=False)
    estado = serializers.ChoiceField(choices=tuple(dict.fromkeys(ESTADOS_CUENTAS + ESTADOS_PENDIENTES)), required=False)
    search = serializers.CharField(max_length=160, allow_blank=True, required=False)

    def validate(self, datos):
        if datos.get("area_sin_asignar") and "area" in datos:
            raise serializers.ValidationError({"area": "Elegí un área o los registros sin área asignada."})
        if datos.get("desde") and datos.get("hasta") and datos["desde"] > datos["hasta"]:
            raise serializers.ValidationError({"hasta": "La fecha final debe ser igual o posterior a la inicial."})
        vista = datos["vista"]
        incompatibles = ("financiador", "responsable", "estado") if vista == "captura" else ("responsable",) if vista == "pendientes" else ()
        for campo in incompatibles:
            if campo in datos:
                raise serializers.ValidationError({campo: "Este filtro no corresponde a la vista elegida."})
        estados = ESTADOS_CUENTAS if vista == "cuentas" else ESTADOS_PENDIENTES
        if "estado" in datos and datos["estado"] not in estados:
            raise serializers.ValidationError({"estado": "El estado no corresponde a la vista elegida."})
        return datos


def puede_seguimiento(usuario, institucion):
    return bool(usuario.is_active and (usuario.is_superuser or concesiones_financieras_de(
        usuario, "ver_dinero",
    ).filter(membresia__institucion_id=institucion).exists()))


def cuentas_cobertura(usuario, institucion):
    rutas = ("distribucion_financiador__reserva", "distribucion_paciente__reserva", "resolucionsaldo__distribucion__reserva")

    def origen(campo):
        return Coalesce(*(F(f"{ruta}__{campo}") for ruta in rutas))

    # Las tres relaciones con la obligación son OneToOne: no multiplican filas.
    qs = ObligacionFinanciera.objects.filter(tipo="cobrar", institucion_id=institucion).filter(
        alcance_financiero_q(usuario, "ver_dinero"),
    ).annotate(
        reserva_reporte=origen("pk"), prestacion_reporte=origen("prestacion__nombre"),
        financiador_reporte=origen("afiliado__financiador_id"),
        financiador_nombre_reporte=origen("afiliado__financiador__nombre"),
        caso_reporte=F("hecho__caso_origen_id"), fecha_reporte=TruncDate("hecho__ocurrida_en"),
        area_reporte=F("area_id"), sensible_reporte=F("sensible"),
        responsable_reporte=Case(
            When(distribucion_financiador__isnull=False, then=Value("financiador")),
            When(distribucion_paciente__isnull=False, then=Value("paciente")),
            default=F("resolucionsaldo__decision"),
        ),
    ).filter(reserva_reporte__isnull=False, hecho__isnull=False)
    return saldos_obligaciones(qs)


def pendientes_cobertura(usuario, institucion):
    qs = ReservaCobertura.objects.filter(estado="realizada", hecho__institucion_id=institucion).annotate(
        area_reporte=F("hecho__area_origen_id"), fecha_reporte=TruncDate("hecho__ocurrida_en"),
        caso_reporte=F("hecho__caso_origen_id"), prestacion_reporte=F("prestacion__nombre"),
        financiador_reporte=F("afiliado__financiador_id"),
        financiador_nombre_reporte=F("afiliado__financiador__nombre"),
        # Sin política identificada, False puede ser un valor por defecto de la
        # evaluación incompleta, no una clasificación financiera confirmada.
        sensible_reporte=Case(When(~Q(evaluacion__politica=None), evaluacion__politica__isnull=False,
                                  evaluacion__politica__gt=0, evaluacion__sensible=False, then=Value(False)),
                              default=Value(True), output_field=BooleanField()),
        estado_reporte=Coalesce("distribucion__estado", Value("sin_distribucion")),
    ).filter(estado_reporte__in=ESTADOS_PENDIENTES).filter(alcance_financiero_q(
        usuario, "ver_dinero", institucion_path="hecho__institucion_id", area_path="area_reporte", sensible_path="sensible_reporte",
    )).annotate(
        importe_pendiente=Case(When(estado_reporte="pendiente", then=F("distribucion__importe_paciente")),
                               default=Value(None), output_field=DecimalField(max_digits=20, decimal_places=2)),
    )
    return qs


def capturas_cobertura(usuario, institucion):
    return HechoAtencionCosteable.objects.filter(institucion_id=institucion).exclude(cobertura_contexto={}).filter(
        Q(snapshot_cobro__isnull=True) | Q(snapshot_cobro__capturado=False),
    ).annotate(
        area_reporte=F("area_origen_id"), sensible_reporte=Value(True, output_field=BooleanField()),
        fecha_reporte=TruncDate("ocurrida_en"), caso_reporte=F("caso_origen_id"),
    ).filter(alcance_financiero_q(
        usuario, "ver_dinero", area_path="area_reporte", sensible_path="sensible_reporte",
    ))


def filtrar_seguimiento(qs, filtros):
    campos = {"desde": "fecha_reporte__gte", "hasta": "fecha_reporte__lte", "area": "area_reporte",
              "financiador": "financiador_reporte", "responsable": "responsable_reporte"}
    for parametro, campo in campos.items():
        if parametro in filtros:
            qs = qs.filter(**{campo: filtros[parametro]})
    if filtros.get("area_sin_asignar"):
        qs = qs.filter(area_reporte__isnull=True)
    estado = filtros.get("estado")
    if estado and filtros["vista"] == "cuentas":
        por_aprobar = Q(por_aprobar__gt=0) | Q(reintegros_por_aprobar__gt=0) | Q(ajustes_por_aprobar__gt=0)
        condiciones = {
            "pendiente": Q(pendiente__gt=0), "a_devolver": Q(saldo_a_devolver__gt=0), "por_aprobar": por_aprobar,
            "saldada": Q(pendiente=0, saldo_a_devolver=0) & ~por_aprobar,
        }
        qs = qs.filter(condiciones[estado])
    elif estado:
        qs = qs.filter(estado_reporte=estado)
    texto = filtros.get("search", "")
    if texto:
        busqueda = Q(caso_reporte=int(texto)) if texto.isdecimal() and len(texto) < 19 else Q(pk__in=[])
        if filtros["vista"] != "captura":
            busqueda |= Q(prestacion_reporte__icontains=texto)
        if filtros["vista"] == "cuentas":
            busqueda |= Q(contraparte_nombre__icontains=texto)
        qs = qs.filter(busqueda)
    return qs


def resumen_seguimiento(qs, vista):
    if vista == "cuentas":
        # Alias distintos a las anotaciones para no ocultarlas durante aggregate.
        totales = qs.aggregate(registros=Count("pk"), **{
            f"total_{campo}": Sum(campo, default=Decimal("0.00")) for campo in CAMPOS_SALDO
        })
        return {"registros": totales["registros"], **{campo: f'{totales[f"total_{campo}"]:.2f}' for campo in CAMPOS_SALDO}}
    if vista == "pendientes":
        totales = qs.aggregate(registros=Count("pk"), importes_desconocidos=Count("pk", filter=Q(importe_pendiente__isnull=True)),
                               total=Sum("importe_pendiente", default=Decimal("0.00")))
        return {"registros": totales["registros"], "importes_desconocidos": totales["importes_desconocidos"], "importe_pendiente": f'{totales["total"]:.2f}'}
    return {"registros": qs.count()}


def opciones_seguimiento(qs, vista):
    return {
        "areas": list(Area.objects.filter(pk__in=qs.values("area_reporte")).order_by("nombre", "pk").values("id", "nombre")),
        "financiadores": [] if vista == "captura" else list(Financiador.objects.filter(
            pk__in=qs.values("financiador_reporte"),
        ).order_by("nombre", "pk").values("id", "nombre")),
    }


def fila_seguimiento(obj, vista):
    fila = {"id": obj.pk, "caso": obj.caso_reporte, "fecha": obj.fecha_reporte,
            "area": obj.area_reporte, "sensible": obj.sensible_reporte}
    if vista == "captura":
        return {**fila, "estado": "captura_pendiente", "motivo": "La atención se registró; la captura financiera no terminó. El importe y responsable aún deben verificarse."}
    fila.update(reserva=obj.reserva_reporte if vista == "cuentas" else obj.pk, prestacion=obj.prestacion_reporte,
                financiador=obj.financiador_reporte, financiador_nombre=obj.financiador_nombre_reporte)
    if vista == "cuentas":
        return {**fila, "responsable": obj.responsable_reporte, "contraparte_nombre": obj.contraparte_nombre,
                **{campo: f"{getattr(obj, campo):.2f}" for campo in CAMPOS_SALDO}}
    motivos = {
        "pendiente": "Diferencia sin aceptación de pago ni asunción del hospital; no es una deuda exigible.",
        "arancel_pendiente": "Falta definir el arancel de la prestación.",
        "evaluacion_pendiente": "Falta completar o verificar la evaluación de cobertura.",
        "sin_distribucion": "La prestación se realizó y todavía no tiene una distribución de cargos.",
    }
    return {**fila, "estado": obj.estado_reporte, "motivo": motivos[obj.estado_reporte],
            "importe_pendiente": f"{obj.importe_pendiente:.2f}" if obj.importe_pendiente is not None else None}


class SeguimientoCobrosViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = FiltrosSeguimiento
    pagination_class = Paginacion
    queryset = ObligacionFinanciera.objects.none()
    http_method_names = ["get", "head", "options"]

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "private, no-store"
        return response

    @extend_schema(parameters=[FiltrosSeguimiento], responses=OpenApiTypes.OBJECT)
    def list(self, request):
        entrada = FiltrosSeguimiento(data=request.query_params.dict())
        entrada.is_valid(raise_exception=True)
        filtros = entrada.validated_data
        institucion, vista = filtros["institucion"], filtros["vista"]
        if not puede_seguimiento(request.user, institucion):
            raise PermissionDenied("Necesitás permiso para consultar dinero de esta institución.")
        if "area" in filtros and not Area.objects.filter(pk=filtros["area"], institucion_id=institucion).exists():
            raise serializers.ValidationError({"area": "El área no pertenece a la institución."})
        fuentes = {"cuentas": cuentas_cobertura, "pendientes": pendientes_cobertura, "captura": capturas_cobertura}
        visible = fuentes[vista](request.user, institucion)
        qs = filtrar_seguimiento(visible, filtros).order_by("-fecha_reporte", "-pk")
        generado_en = timezone.now()
        pagina = list(self.paginate_queryset(qs))
        respuesta = self.get_paginated_response([fila_seguimiento(obj, vista) for obj in pagina])
        respuesta.data.update(resumen=resumen_seguimiento(qs, vista), opciones=opciones_seguimiento(visible, vista), generado_en=generado_en)
        # Auditar también las fuentes de los totales, no sólo la página visible.
        agrupados = qs.order_by().annotate(mes_reporte=TruncMonth("fecha_reporte")).values(
            "area_reporte", "sensible_reporte", "mes_reporte",
        ).annotate(cantidad=Count("pk"))
        grupos = {(institucion, fila["area_reporte"], fila["sensible_reporte"], fila["mes_reporte"]): fila["cantidad"] for fila in agrupados}
        if not grupos:
            grupos = {(institucion, None, False, None): 0}
        # Reusar la escritura estricta sin heredar las rutas list/retrieve del
        # mixin: este reporte no tiene un recurso de detalle independiente.
        return AuditaLecturaFinanciera.auditar_respuesta(
            self, respuesta, grupos=grupos, recurso="seguimiento-cobros", accion=vista,
        )
