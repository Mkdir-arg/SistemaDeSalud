"""Resumen de fuentes y distribución: no suma un gasto y su reparto dos veces."""
from collections import Counter, defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import BigIntegerField, Case, Count, DecimalField, F, IntegerField, Max, OuterRef, Q, Subquery, Sum, Value, When
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.auditoria.latidos import Latido
from apps.instituciones.models import Area
from .auditoria import AuditaLecturaFinanciera
from .calendario import calendario_mensual
from .models import AjusteGasto, AtribucionReparto, ConcesionFinanciera, ExpectativaGasto, Gasto, IndicacionCargaGasto, TrabajoReparto
from .permisos import concesiones_financieras_de, gastos_en_alcance_financiero, instituciones_admin_financiero, tiene_concesion_financiera
from .procesamiento import SERVICIO


class ContextoReporte(serializers.Serializer):
    institucion = serializers.IntegerField(min_value=1)
    periodo_economico = serializers.DateField()
    area = serializers.IntegerField(min_value=1, required=False)
    area_sin_asignar = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        if attrs["periodo_economico"].day != 1:
            raise serializers.ValidationError("Indicá el primer día del mes económico.")
        if attrs.get("area") and attrs["area_sin_asignar"]:
            raise serializers.ValidationError("Elegí un área o los gastos institucionales sin área, no ambos.")
        return attrs


class ContextoEvolucion(ContextoReporte):
    meses = serializers.ChoiceField(choices=[6, 12], default=12)
    concepto = serializers.IntegerField(min_value=1, required=False)


class ConsultaReporte(AuditaLecturaFinanciera, viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Gasto.objects.none()
    serializer_class = ContextoReporte
    http_method_names = ["get", "head", "options"]

    def fuentes(self, request):
        entrada = ContextoReporte(data=request.query_params)
        entrada.is_valid(raise_exception=True)
        ctx = entrada.validated_data
        usuario = request.user
        accion = ConcesionFinanciera.Accion.VER_GASTOS
        inst = ctx["institucion"]
        autoriza_institucion = usuario.is_superuser or instituciones_admin_financiero(usuario, accion).filter(institucion_id=inst).exists() or concesiones_financieras_de(usuario, accion).filter(membresia__institucion_id=inst).exists()
        if not usuario.is_active or not autoriza_institucion:
            raise PermissionDenied("No tenés autorización para consultar gastos de esta institución.")
        if "area" in ctx or ctx["area_sin_asignar"]:
            if not tiene_concesion_financiera(usuario, accion, inst, ctx.get("area")):
                raise PermissionDenied("No tenés autorización para consultar gastos de esta área.")
        if ctx.get("area") and not Area.objects.filter(pk=ctx["area"], institucion_id=inst).exists():
            raise serializers.ValidationError("El área no pertenece a la institución elegida.")
        qs = gastos_en_alcance_financiero(Gasto.objects.all(), usuario).filter(
            institucion_id=inst, periodo_economico=ctx["periodo_economico"], reemplazado_por__isnull=True,
        )
        if ctx.get("area"):
            qs = qs.filter(area_id=ctx["area"])
        elif ctx["area_sin_asignar"]:
            qs = qs.filter(area_id__isnull=True)
        return ctx, qs

    def responder(self, ctx, datos, sensible, fuentes):
        datos.update(institucion=ctx["institucion"], area=ctx.get("area"), periodo_economico=ctx["periodo_economico"], sensible=sensible)
        grupos = {
            (ctx["institucion"], fila["area_id"], fila["sensible"], ctx["periodo_economico"]): fila["cantidad"]
            for fila in fuentes.order_by().values("area_id", "sensible").annotate(cantidad=Count("pk"))
        }
        return self.auditar_respuesta(Response(datos), grupos=grupos)


class ReporteFinanzasViewSet(ConsultaReporte):
    @action(detail=False, methods=["get"])
    def evolucion(self, request):
        # Reutiliza la validación institucional/territorial del resumen.
        ctx, _ = self.fuentes(request)
        entrada = ContextoEvolucion(data=request.query_params)
        entrada.is_valid(raise_exception=True)
        fin = ctx["periodo_economico"]
        numero_fin = fin.year * 12 + fin.month - 1
        numero_inicio = numero_fin - entrada.validated_data["meses"] + 1
        if numero_inicio < 12:
            raise serializers.ValidationError("El período no permite consultar tantos meses anteriores.")
        periodos = [date(n // 12, n % 12 + 1, 1) for n in range(numero_inicio, numero_fin + 1)]
        expectativas = gastos_en_alcance_financiero(ExpectativaGasto.objects.all(), request.user).filter(institucion_id=ctx["institucion"])
        if ctx.get("area"):
            expectativas = expectativas.filter(area_id=ctx["area"])
        elif ctx["area_sin_asignar"]:
            expectativas = expectativas.filter(area_id__isnull=True)
        # Una consulta por mes, no por concepto/área. Conserva el cálculo de
        # calendario y sus subconsultas: los ajustes nunca multiplican fuentes.
        calendarios = [list(calendario_mensual(expectativas, request.user, mes).values(
            "concepto_id", "concepto__nombre", "area_id", "sensible", "estado_carga",
            "gastos_pendientes", "gastos_aprobados", "ajustes_pendientes", "importe_aprobado", "monto_referencia",
        )) for mes in periodos]
        conceptos = {f["concepto_id"]: f["concepto__nombre"] for filas in calendarios for f in filas}
        opciones = sorted(({"id": pk, "nombre": nombre} for pk, nombre in conceptos.items()), key=lambda c: (c["nombre"], c["id"]))
        elegido = entrada.validated_data.get("concepto", opciones[0]["id"] if opciones else None)
        if elegido is not None and elegido not in conceptos:
            raise serializers.ValidationError("El concepto no tiene controles visibles en este período y área.")
        grupos = Counter()
        series = [{**opcion, "meses": []} for opcion in opciones]
        meses_vacios = []
        actual = timezone.localdate().replace(day=1)
        dinero = lambda valor: str(valor.quantize(Decimal("0.01")))
        for mes, calendario in zip(periodos, calendarios):
            por_concepto = defaultdict(list)
            # También audita los conceptos ofrecidos, aunque no estén elegidos.
            for fila in calendario:
                grupos[(ctx["institucion"], fila["area_id"], fila["sensible"], mes)] += 1
                por_concepto[fila["concepto_id"]].append(fila)
            for serie in series or [{"id": None, "meses": meses_vacios}]:
                filas = por_concepto[serie["id"]]
                falta = sum(f["estado_carga"] == IndicacionCargaGasto.Estado.FALTA_CARGAR for f in filas)
                pendientes = sum(f["gastos_pendientes"] for f in filas)
                ajustes_pendientes = sum(f["ajustes_pendientes"] for f in filas)
                registros = sum(f["gastos_aprobados"] for f in filas)
                estado = "sin_control" if not filas else "sin_carga" if falta and not registros else "incompleto" if falta or pendientes or ajustes_pendientes else "mes_abierto" if mes >= actual else "completo"
                serie["meses"].append({
                    "periodo_economico": mes.isoformat(), "controles": len(filas),
                    "importe_aprobado": dinero(sum((f["importe_aprobado"] for f in filas), Decimal(0))) if filas else None,
                    "monto_referencia": dinero(sum((f["monto_referencia"] for f in filas), Decimal(0))) if filas and all(f["monto_referencia"] is not None for f in filas) else None,
                    "estado": estado, "controles_sin_completar": falta, "gastos_pendientes": pendientes,
                    "ajustes_pendientes": ajustes_pendientes,
                    "gastos_aprobados": registros,
                })
        # Extensión aditiva: conserva la consulta de un concepto para clientes
        # anteriores. Todas las series reutilizan los mismos calendarios y auditoría.
        meses = next((s["meses"] for s in series if s["id"] == elegido), meses_vacios)
        return self.auditar_respuesta(Response({
            "conceptos": opciones, "concepto": elegido, "meses": meses, "series": series, "moneda": "ARS",
            "alcance": "Gastos aprobados incluidos en controles mensuales vigentes y visibles; no es el costo total del hospital.",
        }), grupos=grupos)

    def list(self, request):
        ctx, qs = self.fuentes(request)
        sensible = qs.filter(sensible=True).exists()
        moneda = DecimalField(max_digits=24, decimal_places=2)
        ajustes = AjusteGasto.objects.filter(gasto_id=OuterRef("pk"), estado="aprobado").order_by().values("gasto_id").annotate(total=Sum("importe")).values("total")[:1]
        ajustes_por_aprobar = AjusteGasto.objects.filter(
            gasto_id=OuterRef("pk"), estado="pendiente_aprobacion",
        ).order_by().values("gasto_id").annotate(cantidad=Count("pk")).values("cantidad")[:1]
        atribuciones = AtribucionReparto.objects.filter(
            reparto__gasto_id=OuterRef("pk"), reparto__reemplazado_por__isnull=True,
        ).order_by().values("reparto__gasto_id").annotate(total=Sum("importe_centavos")).values("total")[:1]
        qs = qs.annotate(
            importe_resultante=F("importe") + Coalesce(Subquery(ajustes, output_field=moneda), Value(Decimal("0"))),
            atribuido_centavos=Coalesce(Subquery(atribuciones), Value(0), output_field=BigIntegerField()),
            cantidad_ajustes_pendientes=Coalesce(Subquery(ajustes_por_aprobar), Value(0), output_field=IntegerField()),
        )
        grupos = qs.values("area_id", "area__nombre", "concepto_id", "concepto_nombre").annotate(
            aprobado=Coalesce(Sum(Case(When(estado=Gasto.Estado.APROBADO, then=F("importe_resultante")), default=Value(Decimal("0")), output_field=moneda)), Value(Decimal("0"))),
            por_aprobar=Coalesce(Sum(Case(When(estado=Gasto.Estado.PENDIENTE_APROBACION, then=F("importe_resultante")), default=Value(Decimal("0")), output_field=moneda)), Value(Decimal("0"))),
            ajustes_pendientes=Coalesce(Sum("cantidad_ajustes_pendientes"), Value(0)),
            distribuido_centavos=Coalesce(Sum(Case(When(estado=Gasto.Estado.APROBADO, then=F("atribuido_centavos")), default=Value(0), output_field=BigIntegerField())), Value(0), output_field=BigIntegerField()),
            actualizando=Max(Case(When(Q(estado=Gasto.Estado.APROBADO) & Q(trabajo_reparto__revision__gt=F("trabajo_reparto__revision_procesada")), then=Value(1)), default=Value(0), output_field=IntegerField())),
        ).order_by("area__nombre", "concepto_nombre", "area_id", "concepto_id")
        agrupaciones = []
        totales = {"aprobados": Decimal("0"), "pendientes_aprobacion": Decimal("0"), "distribuido": Decimal("0")}
        actualizando = False
        ajustes_pendientes = 0
        dinero = lambda valor: str(valor.quantize(Decimal("0.01")))
        for grupo in grupos:
            distribuido = Decimal(grupo["distribuido_centavos"]) / 100
            pendiente = bool(grupo["actualizando"])
            actualizando |= pendiente
            totales["aprobados"] += grupo["aprobado"]
            totales["pendientes_aprobacion"] += grupo["por_aprobar"]
            ajustes_pendientes += grupo["ajustes_pendientes"]
            totales["distribuido"] += distribuido
            agrupaciones.append({
                "area": grupo["area_id"], "area_nombre": grupo["area__nombre"] or "Institucional — sin área asignada",
                "concepto": grupo["concepto_id"], "concepto_nombre": grupo["concepto_nombre"],
                "aprobados": dinero(grupo["aprobado"]), "pendientes_aprobacion": dinero(grupo["por_aprobar"]),
                "ajustes_pendientes": grupo["ajustes_pendientes"],
                "distribuido": None if pendiente else dinero(distribuido),
                "sin_distribuir": None if pendiente else dinero(grupo["aprobado"] - distribuido),
                "actualizando": pendiente,
            })
        totales["sin_distribuir"] = totales["aprobados"] - totales["distribuido"]
        datos = {nombre: None if actualizando and nombre in {"distribuido", "sin_distribuir"} else dinero(valor) for nombre, valor in totales.items()}
        datos.update(
            moneda="ARS", agrupaciones=agrupaciones, actualizando=actualizando, incluye_sensibles=sensible,
            ajustes_pendientes=ajustes_pendientes,
            alcance="Gastos registrados visibles según tus permisos; no equivale al costo total del hospital.",
        )
        return self.responder(ctx, datos, sensible, qs)


class ProcesamientoFinanzasViewSet(ConsultaReporte):
    def list(self, request):
        ctx, qs = self.fuentes(request)
        sensible = qs.filter(sensible=True).exists()
        trabajos = TrabajoReparto.objects.filter(gasto_id__in=qs.values("id"))
        pendientes = trabajos.filter(revision__gt=F("revision_procesada"))
        cantidad = pendientes.count()
        latido = Latido.objects.filter(servicio=SERVICIO).first()
        activo = bool(latido and latido.momento >= timezone.now() - timedelta(minutes=2))
        estado = "actualizado"
        if pendientes.exclude(ultimo_error="").exists():
            estado = "error"
        elif pendientes.filter(reserva__isnull=False, reintentar_en__gt=timezone.now()).exists():
            estado = "procesando"
        elif cantidad:
            estado = "pendiente"
        mensajes = {
            "actualizado": "No hay cambios pendientes de procesar en este filtro.",
            "pendiente": "Cambios guardados. El reparto está pendiente de actualizar.",
            "procesando": "Actualizando repartos. Los cambios ya están guardados.",
            "error": "No se pudo actualizar algún reparto. El servicio lo reintentará automáticamente.",
        }
        mensaje = mensajes[estado]
        if not activo:
            mensaje += " El servicio de repartos no registra actividad reciente; avisá a soporte."
        return self.responder(ctx, {
            "estado": estado, "pendientes": cantidad, "mensaje": mensaje,
            "ultimo_exito": trabajos.aggregate(fecha=Max("procesado_en"))["fecha"],
            "worker_activo": activo, "ultimo_latido": latido.momento if latido else None,
        }, sensible, qs)
