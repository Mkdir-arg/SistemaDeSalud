"""Consulta administrativa del pagador. No calcula saldos ni registra dinero."""
import csv
from decimal import Decimal
from io import StringIO

from django.db import transaction
from django.db.models import Case, Count, DecimalField, F, OuterRef, Q, Subquery, Sum, Value, When
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import serializers

from apps.instituciones.models import Institucion
from apps.registros.models import normalizar_documento
from .acceso import actividad_visible, auditar_actividad
from .csv import texto_csv_seguro
from .models import Plan, PrestacionComun, ReservaCobertura, ResolucionSaldo
from .services import auditar


LIMITE_EXPORTACION = 5000
ESTADOS_CONOCIDOS = ("pendiente", "resuelta", "sin_cobro")


class FiltrosActividad(serializers.Serializer):
    desde = serializers.DateField(required=False)
    hasta = serializers.DateField(required=False)
    institucion = serializers.IntegerField(min_value=1, required=False)
    plan = serializers.IntegerField(min_value=1, required=False)
    sin_plan = serializers.BooleanField(required=False)
    prestacion = serializers.IntegerField(min_value=1, required=False)
    estado = serializers.ChoiceField(choices=ReservaCobertura._meta.get_field("estado").choices, required=False)
    discrepancia = serializers.BooleanField(required=False)
    search = serializers.CharField(max_length=160, required=False, allow_blank=True)
    formato = serializers.ChoiceField(choices=("json", "csv"), default="json")

    def validate(self, attrs):
        if attrs.get("sin_plan") and "plan" in attrs:
            raise serializers.ValidationError({"plan": "Elegí un plan o la opción sin plan."})
        if attrs.get("desde") and attrs.get("hasta") and attrs["desde"] > attrs["hasta"]:
            raise serializers.ValidationError({"hasta": "La fecha final debe ser igual o posterior a la inicial."})
        return attrs


def filtrar_actividad(visible, filtros):
    qs = visible
    campos = {"desde": "fecha__gte", "hasta": "fecha__lte", "institucion": "hospital_origen",
              "plan": "afiliacion__plan_id", "prestacion": "comun_id", "estado": "estado", "discrepancia": "discrepancia"}
    for parametro, campo in campos.items():
        if parametro in filtros:
            qs = qs.filter(**{campo: filtros[parametro]})
    if "sin_plan" in filtros:
        qs = qs.filter(afiliacion__plan__isnull=filtros["sin_plan"])
    texto = filtros.get("search", "")
    if texto:
        busqueda = (Q(afiliado__numero__icontains=texto) | Q(afiliado__nombre__icontains=texto)
                    | Q(prestacion__nombre__icontains=texto) | Q(comun__codigo__icontains=texto)
                    | Q(comun__nombre__icontains=texto))
        documento = normalizar_documento(texto)
        if documento:
            busqueda |= Q(afiliado__documento__icontains=documento)
        qs = qs.filter(busqueda)
    return qs


def con_importes(qs):
    dinero = DecimalField(max_digits=20, decimal_places=2)
    cero = Value(Decimal("0.00"), output_field=dinero)
    # La subconsulta evita multiplicar el cargo original al unir resoluciones.
    acuerdos = ResolucionSaldo.objects.filter(
        distribucion__reserva_id=OuterRef("pk"), decision="financiador", obligacion__isnull=False,
    ).order_by().values("distribucion__reserva_id").annotate(total=Sum("importe")).values("total")
    return qs.annotate(importe_acuerdos=Coalesce(Subquery(acuerdos, output_field=dinero), cero)).annotate(
        importe_asignado=Case(
            When(estado="realizada", distribucion__estado__in=ESTADOS_CONOCIDOS,
                 then=F("distribucion__importe_financiador") + F("importe_acuerdos")),
            default=Value(None), output_field=dinero,
        ),
    ).select_related("afiliacion__plan", "comun")


def resumen_actividad(qs):
    realizada = Q(estado="realizada")
    resultado = qs.aggregate(
        registros=Count("pk"),
        reservadas=Count("pk", filter=Q(estado="reservada")),
        realizadas=Count("pk", filter=realizada),
        liberadas=Count("pk", filter=Q(estado="liberada")),
        cantidad_realizada=Sum("cantidad", filter=realizada, default=0),
        cubiertas_realizadas=Sum("cubiertas", filter=realizada, default=0),
        discrepancias=Count("pk", filter=Q(discrepancia=True)),
        importes_pendientes=Count("pk", filter=realizada & Q(importe_asignado__isnull=True)),
        total_asignado=Sum("importe_asignado", default=Decimal("0.00")),
    )
    resultado["importe_asignado"] = f'{resultado.pop("total_asignado"):.2f}'
    return resultado


def opciones_actividad(visible):
    # Sólo metadatos presentes en el alcance vigente o histórico permitido.
    return {
        "instituciones": list(Institucion.objects.filter(pk__in=visible.values("hospital_origen")).order_by("nombre", "pk").values("id", "nombre")),
        "planes": list(Plan.objects.filter(pk__in=visible.values("afiliacion__plan_id")).order_by("nombre", "pk").values("id", "nombre")),
        "prestaciones": list(PrestacionComun.objects.filter(pk__in=visible.values("comun_id")).order_by("nombre", "pk").values("id", "nombre", "codigo")),
    }


def fila_actividad(reserva):
    distribucion = getattr(reserva, "distribucion", None)
    fuente = reserva.hecho if reserva.hecho_id else reserva.caso
    conocido = reserva.importe_asignado is not None
    return {
        "id": reserva.pk, "fecha": reserva.fecha, "hospital": fuente.institucion.nombre,
        "prestacion": reserva.prestacion.nombre, "codigo": reserva.comun.codigo,
        "nombre": reserva.afiliado.nombre, "numero": reserva.afiliado.numero, "documento": reserva.afiliado.documento,
        "plan": reserva.afiliacion.plan.nombre if reserva.afiliacion.plan_id else None,
        "cantidad": reserva.cantidad, "cubiertas": reserva.cubiertas, "estado": reserva.estado,
        "discrepancia": reserva.discrepancia,
        "importe_financiador": f"{distribucion.importe_financiador:.2f}" if conocido else None,
        "importe_acuerdos": f"{reserva.importe_acuerdos:.2f}",
        "importe_asignado": f"{reserva.importe_asignado:.2f}" if conocido else None,
        "estado_cobro": distribucion.estado if distribucion else "sin_cargo", "acceso": reserva.acceso,
    }


COLUMNAS_CSV = (
    ("id", "ID"), ("fecha", "Fecha"), ("hospital", "Hospital"), ("nombre", "Afiliado"),
    ("documento", "Documento (texto)"), ("numero", "Número de afiliado (texto)"),
    ("plan", "Plan de la afiliación del caso"), ("codigo", "Código común"), ("prestacion", "Prestación"),
    ("cantidad", "Cantidad"), ("cubiertas", "Cantidad cubierta"), ("estado", "Estado"),
    ("discrepancia", "Discrepancia"), ("importe_financiador", "Cargo inicial del financiador (coma decimal)"),
    ("importe_acuerdos", "Acuerdos posteriores del financiador (coma decimal)"),
    ("importe_asignado", "Importe asignado original (sin descontar pagos ni ajustes; coma decimal)"),
    ("estado_cobro", "Estado administrativo (no acredita pago)"), ("acceso", "Alcance de acceso"),
)

ETIQUETAS_CSV = {
    "estado": dict(ReservaCobertura._meta.get_field("estado").choices),
    "estado_cobro": {
        "sin_cargo": "Cargo todavía no emitido", "sin_cobro": "Prestación sin cargo",
        "resuelta": "Responsable definido", "pendiente": "Pendiente de resolución administrativa",
        "arancel_pendiente": "Arancel pendiente", "evaluacion_pendiente": "Evaluación pendiente",
    },
    "acceso": {"vigente": "Relación vigente", "pendiente_historico": "Histórico pendiente"},
}


def celda_csv(campo, valor):
    if valor is None:
        return ""
    if campo == "fecha":
        return valor.isoformat()
    if isinstance(valor, bool):
        return "Sí" if valor else "No"
    if campo.startswith("importe_"):
        return valor.replace(".", ",")
    # El formateador CSV genérico interpreta textos semejantes a fechas.
    # Un identificador o nombre se conserva literalmente aunque tenga ese aspecto.
    texto = ETIQUETAS_CSV.get(campo, {}).get(valor, str(valor))
    return texto_csv_seguro(texto, identificador=campo in ("documento", "numero", "codigo"))


def exportar_actividad(request, org, qs):
    reservas = list(qs[:LIMITE_EXPORTACION + 1])
    if len(reservas) > LIMITE_EXPORTACION:
        raise serializers.ValidationError(f"La exportación admite hasta {LIMITE_EXPORTACION} registros. Acotá las fechas u otros filtros.")
    contenido = StringIO(newline="")
    escritor = csv.writer(contenido, delimiter=";")
    escritor.writerow([titulo for _, titulo in COLUMNAS_CSV])
    for reserva in reservas:
        fila = fila_actividad(reserva)
        escritor.writerow([celda_csv(campo, fila[campo]) for campo, _ in COLUMNAS_CSV])
    # Sin streaming: ningún byte sale si falla la auditoría de cualquier persona.
    with transaction.atomic():
        auditar_actividad(request, org, reservas, recurso="financiadores-actividad-csv")
        auditar(request.user, "exportar_actividad", org.pk, financiador=org, motivo=f"CSV; registros={len(reservas)}")
    response = HttpResponse("\ufeff" + contenido.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="actividad-financiador-{org.pk}-{timezone.localdate().isoformat()}.csv"'
    response["X-Content-Type-Options"] = "nosniff"
    return response


def consultar_actividad(view, request, org):
    # Un QueryDict se interpreta como formulario HTML: un booleano ausente
    # pasa a False. En filtros de API, ausente significa no filtrar.
    filtros = FiltrosActividad(data=request.query_params.dict())
    filtros.is_valid(raise_exception=True)
    visible = actividad_visible(org)
    qs = con_importes(filtrar_actividad(visible, filtros.validated_data)).order_by("-fecha", "-pk")
    if filtros.validated_data["formato"] == "csv":
        return exportar_actividad(request, org, qs)
    generado_en = timezone.now()
    pagina = list(view.paginate_queryset(qs))
    response = view.get_paginated_response([fila_actividad(reserva) for reserva in pagina])
    response.data.update(resumen=resumen_actividad(qs), opciones=opciones_actividad(visible),
                         limite_exportacion=LIMITE_EXPORTACION, generado_en=generado_en)
    with transaction.atomic():
        auditar_actividad(request, org, pagina)
        auditar(request.user, "consultar_actividad", org.pk, financiador=org)
    return response
