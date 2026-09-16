"""Resumen de fuentes y distribución: no suma un gasto y su reparto dos veces."""
from collections import Counter, defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Count, F, Max
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
from .reportes import resumir_gastos
from .comparativas import ContextoComparativa, periodos_comparados, comparar
from .models import ConcesionFinanciera, ExpectativaGasto, Gasto, IndicacionCargaGasto, TrabajoReparto
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

    def expectativas(self, usuario, ctx):
        fuentes = gastos_en_alcance_financiero(ExpectativaGasto.objects.all(), usuario).filter(institucion_id=ctx["institucion"])
        if ctx.get("area"):
            fuentes = fuentes.filter(area_id=ctx["area"])
        elif ctx["area_sin_asignar"]:
            fuentes = fuentes.filter(area_id__isnull=True)
        return fuentes

    def fuentes(self, request, periodo=None):
        entrada = ContextoReporte(data=request.query_params)
        entrada.is_valid(raise_exception=True)
        ctx = entrada.validated_data
        if periodo is not None:
            ctx["periodo_economico"] = periodo
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
    @action(detail=False, methods=["get"], serializer_class=ContextoComparativa)
    def comparativa(self, request):
        actual, anterior, serie = periodos_comparados(request.query_params)
        resultados, auditoria = {}, Counter()
        for mes in sorted(set([*serie, anterior])):
            ctx, fuentes = self.fuentes(request, periodo=mes)
            fuentes = fuentes.exclude(estado=Gasto.Estado.RECHAZADO)
            datos = resumir_gastos(fuentes)
            datos["periodo_economico"] = mes.isoformat()
            datos["mes_abierto"] = mes >= timezone.localdate().replace(day=1)
            controles = list(calendario_mensual(self.expectativas(request.user, ctx), request.user, mes).values("area_id", "sensible", "estado_carga"))
            datos["controles"] = len(controles)
            datos["controles_sin_completar"] = sum(f["estado_carga"] == IndicacionCargaGasto.Estado.FALTA_CARGAR for f in controles)
            datos["provisional"] = datos["mes_abierto"] or datos["controles_sin_completar"] > 0 or datos["ajustes_pendientes"] > 0 or Decimal(datos["pendientes_aprobacion"]) != 0
            resultados[mes] = datos
            for fila in controles:
                auditoria[(ctx["institucion"], fila["area_id"], fila["sensible"], mes)] += 1
            for fila in fuentes.order_by().values("area_id", "sensible").annotate(cantidad=Count("pk")):
                auditoria[(ctx["institucion"], fila["area_id"], fila["sensible"], mes)] += fila["cantidad"]
        presente, previo = resultados[actual], resultados[anterior]
        campos = ("aprobados", "pendientes_aprobacion", "distribuido", "sin_distribuir")
        indices = [{(g["area"], g["concepto"]): g for g in d["agrupaciones"]} for d in (presente, previo)]
        grupos = []
        for clave in sorted(indices[0].keys() | indices[1].keys(), key=lambda k: (k[0] or 0, k[1])):
            a, b = indices[0].get(clave), indices[1].get(clave)
            origen = a or b
            grupos.append({
                **{k: origen[k] for k in ("area", "area_nombre", "concepto", "concepto_nombre")},
                "actual": a, "anterior": b,
                "variacion": comparar(a["aprobados"] if a else None, b["aprobados"] if b else None),
            })
        return self.auditar_respuesta(Response({
            "actual": presente, "anterior": previo, "serie": [resultados[m] for m in serie],
            "variaciones": {c: comparar(presente[c], previo[c], presente["cantidad_registros"] > 0 and previo["cantidad_registros"] > 0) for c in campos},
            "agrupaciones": grupos, "moneda": "ARS", "calculado_en": timezone.now(),
            "alcance": "Gastos registrados visibles, con ajustes aprobados, por mes económico. Valores nominales sin ajuste por inflación. Una baja no demuestra ahorro ni carga completa.",
        }), grupos=auditoria)

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
        expectativas = self.expectativas(request.user, ctx)
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
        datos = resumir_gastos(qs)
        datos["incluye_sensibles"] = sensible
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
