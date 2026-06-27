from datetime import date, timedelta

from django.db.models import Avg, Case, Count, DurationField, ExpressionWrapper, F, IntegerField, Q, When
from django.utils import timezone
from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.common import BaseModelViewSet

from .models import Area, Box, Grupo, Institucion, Subarea
from .serializers import AreaSerializer, BoxSerializer, GrupoSerializer, InstitucionSerializer, SubareaSerializer


class InstitucionViewSet(BaseModelViewSet):
    queryset = Institucion.objects.all()
    serializer_class = InstitucionSerializer
    capacidad_requerida = "config"
    institucion_path = "id"
    filter_fields = ("activa",)
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["nombre", "cuit"]
    ordering_fields = ["nombre", "creada"]

    @action(detail=True, methods=["get"])
    def metricas(self, request, pk=None):
        """Conteos para el panel de la institución."""
        from apps.accounts.models import Membresia
        from apps.casos.models import Caso

        inst = self.get_object()
        return Response({
            "areas": inst.areas.count(),
            "subareas": Subarea.objects.filter(area__institucion=inst).count(),
            "staff": Membresia.objects.filter(institucion=inst).values("usuario").distinct().count(),
            "casos_activos": Caso.objects.filter(institucion=inst).exclude(estado=Caso.Estado.CERRADO).count(),
        })

    @action(detail=True, methods=["get"])
    def tablero(self, request, pk=None):
        """Tablero general del hospital: números, tiempos por área y series para gráficos.

        Acepta ?desde=YYYY-MM-DD&hasta=YYYY-MM-DD (por defecto, últimos 30 días).
        Las métricas de "carga viva" (activos, en cola, urgentes) son siempre del
        momento; las de período (ingresos, cerrados, espera, atención, resolución y
        la serie) se acotan al rango. Tiempos:
        - espera   = ItemFila.llamado_at − ingreso
        - atención = ItemFila.atendido_at − llamado_at
        - resolución = Caso.actualizado − Caso.creado (cerrados)
        """
        from apps.casos.models import Caso, ItemFila

        inst = self.get_object()
        now = timezone.now()

        def _fecha(v, por_defecto):
            try:
                return date.fromisoformat(v)
            except (TypeError, ValueError):
                return por_defecto

        hasta = _fecha(request.query_params.get("hasta"), timezone.localdate())
        desde = _fecha(request.query_params.get("desde"), hasta - timedelta(days=29))
        if desde > hasta:
            desde, hasta = hasta, desde
        rango = (desde, hasta)  # inclusivo en ambos extremos (lookups __date__range)

        ACTIVO = ~Q(estado__in=[Caso.Estado.CERRADO, Caso.Estado.CANCELADO])
        dur = ExpressionWrapper(F("actualizado") - F("creado"), output_field=DurationField())

        casos = Caso.objects.filter(institucion=inst)
        activos = casos.filter(ACTIVO)
        items = ItemFila.objects.filter(caso__institucion=inst)
        cola = list(items.filter(atendido=False).select_related("caso", "caso__ciudadano", "caso__area_actual", "nodo"))
        espera_expr = ExpressionWrapper(F("llamado_at") - F("ingreso"), output_field=DurationField())
        atencion_expr = ExpressionWrapper(F("atendido_at") - F("llamado_at"), output_field=DurationField())

        def _avg_min(qs):
            a = qs.aggregate(a=Avg("w"))["a"]
            return round(a.total_seconds() / 60, 1) if a else None

        def espera_min(items_qs, cola_items):
            # Espera real medida (llamado − ingreso) en el rango; si no hay, espera en vivo.
            v = _avg_min(items_qs.filter(llamado_at__isnull=False, ingreso__date__range=rango).annotate(w=espera_expr))
            if v is not None:
                return v
            difs = [(now - it.ingreso).total_seconds() / 60 for it in cola_items]
            return round(sum(difs) / len(difs), 1) if difs else 0

        def atencion_min(items_qs):
            # Atención real (atendido − llamado); excluye filas clásicas (duración nula).
            return _avg_min(items_qs.filter(
                atendido_at__isnull=False, atendido_at__gt=F("llamado_at"), atendido_at__date__range=rango
            ).annotate(w=atencion_expr)) or 0

        def resol_prom_h(qs):
            avg = qs.filter(estado=Caso.Estado.CERRADO, actualizado__date__range=rango).annotate(d=dur).aggregate(a=Avg("d"))["a"]
            return round(avg.total_seconds() / 3600, 1) if avg else 0

        resumen = {
            "casos_activos": activos.count(),
            "ingresos": casos.filter(creado__date__range=rango).count(),
            "cerrados": casos.filter(estado=Caso.Estado.CERRADO, actualizado__date__range=rango).count(),
            "en_cola": len(cola),
            "urgentes": activos.filter(prioridad=Caso.Prioridad.URGENTE).count(),
            "espera_prom_min": espera_min(items, cola),
            "atencion_prom_min": atencion_min(items),
            "resolucion_prom_h": resol_prom_h(casos),
        }

        por_area = []
        for area in inst.areas.all():
            a_casos = casos.filter(area_actual=area)
            a_items = items.filter(nodo__version__flujo__area_id=area.id)
            a_cola = [it for it in cola if it.caso.area_actual_id == area.id]
            por_area.append({
                "area_id": area.id,
                "nombre": area.nombre,
                "activos": a_casos.filter(ACTIVO).count(),
                "en_cola": len(a_cola),
                "atendidos": a_casos.filter(estado=Caso.Estado.ATENDIDO).count(),
                "espera_prom_min": espera_min(a_items, a_cola),
                "atencion_prom_min": atencion_min(a_items),
                "resolucion_prom_h": resol_prom_h(a_casos),
            })
        por_area.sort(key=lambda x: (x["activos"], x["en_cola"]), reverse=True)

        por_estado = {
            e["estado"]: e["n"]
            for e in casos.exclude(estado=Caso.Estado.CANCELADO).values("estado").annotate(n=Count("id"))
        }

        # Top de demoras: quién está esperando más en cola AHORA (en vivo, no por rango).
        def _paciente(c):
            return f"{c.ciudadano.nombre} {c.ciudadano.apellido}".strip() if c.ciudadano_id else None

        top_demoras = [
            {
                "caso_id": it.caso_id,
                "paciente": _paciente(it.caso),
                "area": it.caso.area_actual.nombre if it.caso.area_actual_id else None,
                "nodo": it.nodo.titulo if it.nodo_id else None,
                "urgente": it.urgente,
                "espera_min": round((now - it.ingreso).total_seconds() / 60, 1),
            }
            for it in sorted(cola, key=lambda x: x.ingreso)[:8]
        ]

        # Serie de ingresos: diaria si el rango es corto, semanal si es largo.
        span = (hasta - desde).days + 1
        en_rango = casos.filter(creado__date__range=rango)
        if span <= 45:
            serie_ingresos = [
                {"fecha": (desde + timedelta(days=i)).isoformat(),
                 "casos": en_rango.filter(creado__date=desde + timedelta(days=i)).count()}
                for i in range(span)
            ]
            agrupacion = "dia"
        else:
            serie_ingresos = []
            for w in range((span + 6) // 7):
                ini = desde + timedelta(weeks=w)
                fin = min(ini + timedelta(days=6), hasta)
                serie_ingresos.append({
                    "fecha": ini.isoformat(),
                    "casos": en_rango.filter(creado__date__range=(ini, fin)).count(),
                })
            agrupacion = "semana"

        return Response({
            "periodo": {"desde": desde.isoformat(), "hasta": hasta.isoformat(), "dias": span, "agrupacion": agrupacion},
            "resumen": resumen,
            "por_area": por_area,
            "por_estado": por_estado,
            "serie_ingresos": serie_ingresos,
            "top_demoras": top_demoras,
        })


class AreaViewSet(BaseModelViewSet):
    queryset = Area.objects.select_related("institucion").prefetch_related("subareas")
    serializer_class = AreaSerializer
    capacidad_requerida = "config"
    institucion_path = "institucion"
    filter_fields = ("institucion", "activa")

    @action(detail=True, methods=["get"])
    def tablero(self, request, pk=None):
        """Tablero de un área: números, distribución por paso del flujo y tiempos.

        El detalle "por paso" se arma en base al flujo: agrupa los casos activos
        por el nodo en el que están ahora. Acepta ?desde=&hasta= (default 30 días).
        """
        from apps.casos.models import Caso, ItemFila

        area = self.get_object()
        now = timezone.now()

        def _fecha(v, por_defecto):
            try:
                return date.fromisoformat(v)
            except (TypeError, ValueError):
                return por_defecto

        hasta = _fecha(request.query_params.get("hasta"), timezone.localdate())
        desde = _fecha(request.query_params.get("desde"), hasta - timedelta(days=29))
        if desde > hasta:
            desde, hasta = hasta, desde
        rango = (desde, hasta)

        ACTIVO = ~Q(estado__in=[Caso.Estado.CERRADO, Caso.Estado.CANCELADO])
        dur = ExpressionWrapper(F("actualizado") - F("creado"), output_field=DurationField())
        espera_expr = ExpressionWrapper(F("llamado_at") - F("ingreso"), output_field=DurationField())
        atencion_expr = ExpressionWrapper(F("atendido_at") - F("llamado_at"), output_field=DurationField())

        casos = Caso.objects.filter(area_actual=area)
        activos = casos.filter(ACTIVO)
        items = ItemFila.objects.filter(nodo__version__flujo__area=area)
        cola = list(items.filter(atendido=False).select_related("caso__ciudadano", "caso__area_actual", "nodo"))

        def _avg_min(qs):
            a = qs.aggregate(a=Avg("w"))["a"]
            return round(a.total_seconds() / 60, 1) if a else None

        espera_v = _avg_min(items.filter(llamado_at__isnull=False, ingreso__date__range=rango).annotate(w=espera_expr))
        if espera_v is None:
            difs = [(now - it.ingreso).total_seconds() / 60 for it in cola]
            espera_v = round(sum(difs) / len(difs), 1) if difs else 0
        atencion_v = _avg_min(items.filter(
            atendido_at__isnull=False, atendido_at__gt=F("llamado_at"), atendido_at__date__range=rango
        ).annotate(w=atencion_expr)) or 0
        resol_avg = casos.filter(estado=Caso.Estado.CERRADO, actualizado__date__range=rango).annotate(d=dur).aggregate(a=Avg("d"))["a"]

        resumen = {
            "activos": activos.count(),
            "en_cola": len(cola),
            "atendidos": casos.filter(estado=Caso.Estado.ATENDIDO).count(),
            "ingresos": casos.filter(creado__date__range=rango).count(),
            "cerrados": casos.filter(estado=Caso.Estado.CERRADO, actualizado__date__range=rango).count(),
            "espera_prom_min": espera_v,
            "atencion_prom_min": atencion_v,
            "resolucion_prom_h": round(resol_avg.total_seconds() / 3600, 1) if resol_avg else 0,
        }

        # Por paso del flujo: casos activos agrupados por el nodo donde están ahora.
        cola_por_nodo = {}
        for it in cola:
            cola_por_nodo[it.nodo_id] = cola_por_nodo.get(it.nodo_id, 0) + 1
        por_paso = [
            {
                "nodo_id": p["nodo_actual"],
                "titulo": p["nodo_actual__titulo"],
                "tipo": p["nodo_actual__tipo"],
                "casos": p["n"],
                "en_cola": cola_por_nodo.get(p["nodo_actual"], 0),
            }
            for p in activos.exclude(nodo_actual__isnull=True)
            .values("nodo_actual", "nodo_actual__titulo", "nodo_actual__tipo")
            .annotate(n=Count("id")).order_by("-n")
        ]

        por_estado = {
            e["estado"]: e["n"]
            for e in casos.exclude(estado=Caso.Estado.CANCELADO).values("estado").annotate(n=Count("id"))
        }

        def _paciente(c):
            return f"{c.ciudadano.nombre} {c.ciudadano.apellido}".strip() if c.ciudadano_id else None

        top_demoras = [
            {
                "caso_id": it.caso_id, "paciente": _paciente(it.caso),
                "nodo": it.nodo.titulo if it.nodo_id else None, "urgente": it.urgente,
                "espera_min": round((now - it.ingreso).total_seconds() / 60, 1),
            }
            for it in sorted(cola, key=lambda x: x.ingreso)[:6]
        ]

        span = (hasta - desde).days + 1
        en_rango = casos.filter(creado__date__range=rango)
        if span <= 45:
            serie_ingresos = [
                {"fecha": (desde + timedelta(days=i)).isoformat(),
                 "casos": en_rango.filter(creado__date=desde + timedelta(days=i)).count()}
                for i in range(span)
            ]
            agrupacion = "dia"
        else:
            serie_ingresos = []
            for w in range((span + 6) // 7):
                ini = desde + timedelta(weeks=w)
                fin = min(ini + timedelta(days=6), hasta)
                serie_ingresos.append({"fecha": ini.isoformat(), "casos": en_rango.filter(creado__date__range=(ini, fin)).count()})
            agrupacion = "semana"

        # Casos activos del área (urgentes primero, luego los más antiguos).
        peso = Case(
            When(prioridad=Caso.Prioridad.URGENTE, then=0),
            When(prioridad=Caso.Prioridad.ALTA, then=1),
            default=2, output_field=IntegerField(),
        )
        casos_activos = [
            {
                "id": c.id,
                "paciente": _paciente(c),
                "estado": c.estado,
                "prioridad": c.prioridad,
                "paso": c.nodo_actual.titulo if c.nodo_actual_id else None,
                "asignado": c.asignado_a.nombre_completo if c.asignado_a_id else None,
                "creado": c.creado.isoformat(),
            }
            for c in activos.annotate(_p=peso).select_related("ciudadano", "nodo_actual", "asignado_a").order_by("_p", "creado")[:50]
        ]

        # Mini-mapa del flujo: grafo de la versión publicada (o la última) de cada
        # flujo del área, con la carga viva (casos activos parados en cada nodo).
        from apps.flujos.models import Flujo, Nodo

        carga = {
            row["nodo_actual"]: row["n"]
            for row in activos.exclude(nodo_actual__isnull=True).values("nodo_actual").annotate(n=Count("id"))
        }

        def _es_destino(nodo):
            return nodo.tipo == Nodo.Tipo.DERIVAR and str((nodo.config or {}).get("area_destino_id")) == str(area.id)

        def _payload(flujo, relacion):
            ver = flujo.version_publicada or flujo.versiones.order_by("-numero").first()
            if not ver:
                return None
            return {
                "flujo_id": flujo.id, "titulo": flujo.titulo, "version": ver.numero,
                "estado": ver.estado, "relacion": relacion,
                "nodos": [
                    {"id": n.id, "tipo": n.tipo, "titulo": n.titulo, "x": n.x, "y": n.y,
                     "casos": carga.get(n.id, 0), "destino": relacion == "deriva" and _es_destino(n)}
                    for n in ver.nodos.all()
                ],
                "conexiones": [
                    {"origen": c.origen_id, "destino": c.destino_id, "etiqueta": c.etiqueta}
                    for c in ver.conexiones.all()
                ],
            }

        # Flujos propios del área.
        propios = list(area.flujos.all())
        propio_ids = {f.id for f in propios}

        # Flujos de la institución que DERIVAN a esta área (nodo "derivar" → área).
        deriva_ids = {
            r["version__flujo"]
            for r in Nodo.objects.filter(tipo=Nodo.Tipo.DERIVAR, version__flujo__institucion=area.institucion_id)
            .values("config", "version__flujo")
            if str((r["config"] or {}).get("area_destino_id")) == str(area.id)
        } - propio_ids
        derivan = list(Flujo.objects.filter(id__in=deriva_ids))

        flujos = [p for f in propios if (p := _payload(f, "propio"))]
        flujos += [p for f in derivan if (p := _payload(f, "deriva"))]

        return Response({
            "area": {"id": area.id, "nombre": area.nombre},
            "periodo": {"desde": desde.isoformat(), "hasta": hasta.isoformat(), "dias": span, "agrupacion": agrupacion},
            "resumen": resumen,
            "por_paso": por_paso,
            "por_estado": por_estado,
            "serie_ingresos": serie_ingresos,
            "top_demoras": top_demoras,
            "casos": casos_activos,
            "flujos": flujos,
        })


class SubareaViewSet(BaseModelViewSet):
    queryset = Subarea.objects.select_related("area")
    serializer_class = SubareaSerializer
    capacidad_requerida = "config"
    institucion_path = "area__institucion"
    filter_fields = ("area", "activa")


class GrupoViewSet(BaseModelViewSet):
    queryset = Grupo.objects.select_related("area").prefetch_related("miembros")
    serializer_class = GrupoSerializer
    capacidad_requerida = "config"
    institucion_path = "area__institucion"
    filter_fields = ("area", "area__institucion", "activo")


class BoxViewSet(BaseModelViewSet):
    queryset = Box.objects.select_related("area", "ocupado_por")
    serializer_class = BoxSerializer
    capacidad_requerida = "config"
    institucion_path = "area__institucion"
    filter_fields = ("area", "area__institucion", "activo", "ocupado_por")

    def get_permissions(self):
        # Ocupar/liberar son acciones OPERATIVAS (no de configuración): cualquier
        # miembro de la institución del box puede hacerlas (el scope ya lo limita).
        if self.action in ("ocupar", "liberar"):
            return [IsAuthenticated()]
        return super().get_permissions()

    @action(detail=True, methods=["post"])
    def ocupar(self, request, pk=None):
        """El profesional se registra en el box; libera cualquier otro que ocupara."""
        box = self.get_object()
        Box.objects.filter(ocupado_por=request.user).exclude(pk=box.pk).update(ocupado_por=None, ocupado_desde=None)
        box.ocupado_por = request.user
        box.ocupado_desde = timezone.now()
        box.save(update_fields=["ocupado_por", "ocupado_desde"])
        return Response(self.get_serializer(box).data)

    @action(detail=True, methods=["post"])
    def liberar(self, request, pk=None):
        """Libera el box. Solo quien lo ocupa (o el super admin)."""
        box = self.get_object()
        if box.ocupado_por_id and box.ocupado_por_id != request.user.id and not request.user.is_superuser:
            return Response({"detail": "Solo quien ocupa el box puede liberarlo."}, status=status.HTTP_403_FORBIDDEN)
        box.ocupado_por = None
        box.ocupado_desde = None
        box.save(update_fields=["ocupado_por", "ocupado_desde"])
        return Response(self.get_serializer(box).data)
