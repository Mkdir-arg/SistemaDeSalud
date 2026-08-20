from datetime import date, timedelta

from django.db import transaction
from django.db.models import Avg, Case, Count, DurationField, ExpressionWrapper, F, IntegerField, Q, When
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.casos import motor
from apps.common import BaseModelViewSet, CapacidadPermission, _coerce, tiene_capacidad

from apps.agenda.models import Turno

from .models import Area, Box, Cama, EstadiaCama, Grupo, Institucion, Subarea
from .serializers import (
    AreaSerializer, BoxSerializer, CamaSerializer, EstadiaCamaSerializer,
    GrupoSerializer, InstitucionSerializer, SubareaSerializer,
)


# Techo del rango que puede pedir un tablero.
#
# El costo de la consulta lo fija quien escribe la URL: `?desde=2020-01-01` son
# seis años de buckets, y el tablero se refresca solo cada minuto contra la misma
# base en la que se están admitiendo pacientes. Un año es más de lo que cualquier
# panel operativo mira; lo que exceda se recorta y se informa en `periodo`.
MAX_DIAS_RANGO = 366

# La institución de capacitación del recorrido guiado. Es el único nombre que
# `reset-escuela` acepta vaciar: ver InstitucionViewSet.reset_escuela.
NOMBRE_ESCUELA = "Hospital Escuela Cauce"

# Los usuarios de práctica del escenario: `escuela.med@cauce.local` y compañía.
# `reset-escuela` los borra junto con la institución, y el prefijo más el dominio
# son lo que evita que se lleve puesto a nadie más.
PREFIJO_USUARIO_ESCUELA = "escuela."
DOMINIO_USUARIO_ESCUELA = "@cauce.local"


def _rango_pedido(request):
    """Rango del tablero: (desde, hasta) inclusivo, acotado a `MAX_DIAS_RANGO`."""
    def _fecha(v, por_defecto):
        try:
            return date.fromisoformat(v)
        except (TypeError, ValueError):
            return por_defecto

    hasta = _fecha(request.query_params.get("hasta"), timezone.localdate())
    desde = _fecha(request.query_params.get("desde"), hasta - timedelta(days=29))
    if desde > hasta:
        desde, hasta = hasta, desde
    if (hasta - desde).days + 1 > MAX_DIAS_RANGO:
        desde = hasta - timedelta(days=MAX_DIAS_RANGO - 1)
    return desde, hasta


def _serie_ingresos(en_rango, desde, hasta):
    """Serie de ingresos del período en UNA consulta agrupada.

    Antes se contaba con un `.count()` por bucket dentro de un bucle: 30
    consultas para el rango por defecto y cientos para un rango largo, en una
    pantalla que se refresca sola cada minuto. La cantidad de consultas no puede
    depender del rango que pida el cliente.
    """
    por_dia = {
        r["f"]: r["n"]
        for r in en_rango.annotate(f=TruncDate("creado")).values("f").annotate(n=Count("id"))
    }
    span = (hasta - desde).days + 1
    if span <= 45:
        serie = [
            {"fecha": (desde + timedelta(days=i)).isoformat(),
             "casos": por_dia.get(desde + timedelta(days=i), 0)}
            for i in range(span)
        ]
        return serie, "dia"
    serie = []
    for w in range((span + 6) // 7):
        ini = desde + timedelta(weeks=w)
        fin = min(ini + timedelta(days=6), hasta)
        serie.append({
            "fecha": ini.isoformat(),
            "casos": sum(por_dia.get(ini + timedelta(days=i), 0) for i in range((fin - ini).days + 1)),
        })
    return serie, "semana"


def _minutos(delta):
    """Un promedio de duración en minutos; None si no hubo ninguna medición."""
    return round(delta.total_seconds() / 60, 1) if delta else None


class InstitucionViewSet(BaseModelViewSet):
    queryset = Institucion.objects.all()
    serializer_class = InstitucionSerializer
    capacidad_requerida = "gobierno_plataforma"
    institucion_path = "id"
    filter_fields = ("activa",)
    search_fields = ["nombre", "cuit"]
    ordering_fields = ["nombre", "creada"]

    def get_queryset(self):
        qs = Institucion.objects.all()
        user = self.request.user
        if user.is_authenticated and not user.is_superuser and not tiene_capacidad(user, "gobierno_plataforma"):
            qs = qs.filter(id__in=self.instituciones_del_usuario())
        for field in self.filter_fields:
            value = self.request.query_params.get(field)
            if value not in (None, ""):
                qs = qs.filter(**{field: _coerce(value)})
        return qs

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
            "casos_activos": Caso.objects.filter(institucion=inst).exclude(estado__in=Caso.ESTADOS_FINALIZADOS).count(),
        })

    @action(detail=True, methods=["get"])
    def tablero(self, request, pk=None):
        """Tablero general del hospital: números, tiempos por área y series para gráficos.

        Acepta ?desde=YYYY-MM-DD&hasta=YYYY-MM-DD (por defecto, últimos 30 días;
        tope `MAX_DIAS_RANGO`, y `periodo` devuelve el rango que se usó de verdad).
        Las métricas de "carga viva" (activos, en cola, urgentes, top de demoras)
        son siempre del momento; las de período (ingresos, cerrados, espera,
        atención, resolución, la serie y la distribución por estado) se acotan al
        rango. Tiempos:
        - espera   = ItemFila.llamado_at − ingreso
        - atención = ItemFila.atendido_at − llamado_at
        - resolución = Caso.actualizado − Caso.creado (cerrados)
        """
        from apps.casos.models import Caso, ItemFila

        inst = self.get_object()
        now = timezone.now()

        desde, hasta = _rango_pedido(request)
        rango = (desde, hasta)  # inclusivo en ambos extremos (lookups __date__range)

        ACTIVO = ~Q(estado__in=[Caso.Estado.CERRADO, Caso.Estado.CANCELADO])
        dur = ExpressionWrapper(F("actualizado") - F("creado"), output_field=DurationField())

        casos = Caso.objects.filter(institucion=inst)
        activos = casos.filter(ACTIVO)
        en_rango = casos.filter(creado__date__range=rango)
        items = ItemFila.objects.filter(caso__institucion=inst)
        # La cola son los que ESPERAN. Quien ya fue llamado a un box sigue con
        # `atendido=False` a propósito (ver motor.mover_en_fila), así que sin el
        # `box__isnull=True` la cola cuenta a los que están adentro del
        # consultorio: infla la dotación que se mira para llamar más personal y
        # pone primero en «quién espera más» justo al que hace más rato que está
        # con el médico.
        cola = list(
            items.filter(atendido=False, box__isnull=True)
            .select_related("caso", "caso__ciudadano", "caso__area_actual", "nodo")
        )
        espera_expr = ExpressionWrapper(F("llamado_at") - F("ingreso"), output_field=DurationField())
        atencion_expr = ExpressionWrapper(F("atendido_at") - F("llamado_at"), output_field=DurationField())
        medidos_espera = items.filter(llamado_at__isnull=False, ingreso__date__range=rango)
        medidos_atencion = items.filter(
            atendido_at__isnull=False, atendido_at__gt=F("llamado_at"), atendido_at__date__range=rango
        )
        cerrados_rango = casos.filter(estado=Caso.Estado.CERRADO, actualizado__date__range=rango)

        def espera_en_vivo(cola_items):
            difs = [(now - it.ingreso).total_seconds() / 60 for it in cola_items]
            return round(sum(difs) / len(difs), 1) if difs else None

        def espera_min(medida, cola_items):
            # Espera real medida (llamado − ingreso) en el rango; si no hay, espera
            # en vivo; si tampoco hay nadie en cola, `None`: «no hay ninguna
            # medición» no es «cero minutos de espera», y colapsarlo a 0 pintaba de
            # verde —el mejor color de la tabla— justo a las áreas sin dato.
            return medida if medida is not None else espera_en_vivo(cola_items)

        # Ocupación de camas: se cuenta acá y no con una consulta por sector
        # porque el resumen es una sola foto, y el porcentaje va sobre camas EN
        # SERVICIO —contar las que están fuera de servicio en el denominador
        # haría parecer desahogado a un servicio que no lo está—.
        camas = Cama.objects.filter(area__institucion=inst, activa=True)
        camas_total = camas.count()
        camas_fuera = camas.filter(estado=Cama.Estado.BLOQUEADA).count()
        camas_ocupadas = camas.filter(estado=Cama.Estado.OCUPADA).count()
        operativas = camas_total - camas_fuera

        # Agenda del período. El ausentismo es EL indicador de un consultorio
        # —cuánta hora de profesional se perdió— y sólo tiene sentido sobre los
        # turnos que YA PASARON.
        turnos = Turno.objects.filter(
            agenda__institucion=inst, inicio__date__range=rango
        )
        pasados = turnos.filter(inicio__lt=now)
        t_presentes = pasados.filter(estado=Turno.Estado.PRESENTE).count()
        t_ausentes = pasados.filter(estado=Turno.Estado.AUSENTE).count()
        t_cancelados = pasados.filter(estado=Turno.Estado.CANCELADO).count()
        # Los que pasaron y nadie resolvió. Se cuentan aparte y NO se reparten
        # entre ausentes y presentes: meterlos en ausentes inflaría el
        # ausentismo con gente que sí vino y nadie registró, y el número dejaría
        # de servir para decidir. Que se vean es la forma de que alguien los
        # cierre.
        t_sin_registrar = pasados.filter(
            estado__in=[Turno.Estado.RESERVADO, Turno.Estado.CONFIRMADO]
        ).count()
        # Sobre los que tuvieron desenlace: un ausentismo calculado sobre los
        # sin registrar sube o baja según la prolijidad administrativa, no según
        # cuánta gente faltó.
        resueltos = t_presentes + t_ausentes

        resumen = {
            "casos_activos": activos.count(),
            "turnos_periodo": turnos.count(),
            "turnos_presentes": t_presentes,
            "turnos_ausentes": t_ausentes,
            "turnos_cancelados": t_cancelados,
            "turnos_sin_registrar": t_sin_registrar,
            "ausentismo": round(100 * t_ausentes / resueltos) if resueltos else 0,
            "camas_total": camas_total,
            "camas_operativas": operativas,
            "camas_ocupadas": camas_ocupadas,
            "camas_libres": camas.filter(estado=Cama.Estado.LIBRE).count(),
            "ocupacion_camas": round(100 * camas_ocupadas / operativas) if operativas else 0,
            "ingresos": en_rango.count(),
            "cerrados": cerrados_rango.count(),
            "en_cola": len(cola),
            "urgentes": activos.filter(prioridad=Caso.Prioridad.URGENTE).count(),
            "espera_prom_min": espera_min(_minutos(medidos_espera.aggregate(a=Avg(espera_expr))["a"]), cola),
            "atencion_prom_min": _minutos(medidos_atencion.aggregate(a=Avg(atencion_expr))["a"]) or 0,
            "resolucion_prom_h": round(
                (cerrados_rango.aggregate(a=Avg(dur))["a"] or timedelta()).total_seconds() / 3600, 1
            ),
        }

        # Una consulta por métrica y no una por área: con ocho áreas el bucle
        # anterior hacía cuarenta agregaciones en una pantalla que se refresca
        # sola cada minuto, contra la misma base donde se admiten pacientes.
        AREA_ITEM = "nodo__version__flujo__area"
        # Dos definiciones de «área», una por pregunta, y NO mezcladas en la misma
        # fila. `area_actual` es un puntero móvil —el nodo `derivar` lo pisa con el
        # área destino mientras el caso sigue corriendo el flujo de origen—, así
        # que responde bien «quién está acá AHORA» (activos, en cola) y responde
        # mal la producción del PERÍODO: el caso que Guardia resolvió se lo
        # contaba el área a la que lo derivó, y la atribución cambiaba hacia
        # atrás. La producción se cuelga del área del flujo que lo procesó, igual
        # que la espera y la atención, que ya se agrupaban así.
        AREA_CASO = "version__flujo__area"

        def _por_clave(qs, clave, campo, valor):
            return {r[clave]: r[valor] for r in qs.values(clave).annotate(**{valor: campo})}

        act_area = _por_clave(activos, "area_actual", Count("id"), "n")
        aten_area = _por_clave(casos.filter(estado=Caso.Estado.ATENDIDO), "area_actual", Count("id"), "n")
        esp_area = _por_clave(medidos_espera, AREA_ITEM, Avg(espera_expr), "w")
        ate_area = _por_clave(medidos_atencion, AREA_ITEM, Avg(atencion_expr), "w")
        res_area = _por_clave(cerrados_rango, AREA_CASO, Avg(dur), "d")

        por_area = []
        for area in inst.areas.all():
            a_cola = [it for it in cola if it.caso.area_actual_id == area.id]
            d = res_area.get(area.id)
            por_area.append({
                "area_id": area.id,
                "nombre": area.nombre,
                "activos": act_area.get(area.id, 0),
                "en_cola": len(a_cola),
                # Foto viva de un estado de paso, no producción del período (ver
                # el comentario del tablero de área).
                "atendidos": aten_area.get(area.id, 0),
                "espera_prom_min": espera_min(_minutos(esp_area.get(area.id)), a_cola),
                "atencion_prom_min": _minutos(ate_area.get(area.id)) or 0,
                "resolucion_prom_h": round(d.total_seconds() / 3600, 1) if d else 0,
            })
        por_area.sort(key=lambda x: (x["activos"], x["en_cola"]), reverse=True)

        # Por estado DEL PERÍODO, como el resto del panel. Sobre todos los casos
        # de la institución la dona no se movía al cambiar el selector de rango
        # —tres meses y siete días daban lo mismo—, y el total que muestra en el
        # centro se leía como el volumen de la semana cuando era la historia
        # entera del hospital.
        por_estado = {
            e["estado"]: e["n"]
            for e in en_rango.exclude(estado=Caso.Estado.CANCELADO).values("estado").annotate(n=Count("id"))
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
        serie_ingresos, agrupacion = _serie_ingresos(en_rango, desde, hasta)

        return Response({
            "periodo": {"desde": desde.isoformat(), "hasta": hasta.isoformat(), "dias": span, "agrupacion": agrupacion},
            "resumen": resumen,
            "por_area": por_area,
            "por_estado": por_estado,
            "serie_ingresos": serie_ingresos,
            "top_demoras": top_demoras,
        })

    @action(detail=True, methods=["post"], url_path="reset-escuela")
    def reset_escuela(self, request, pk=None):
        """Vacía la institución de capacitación para que el recorrido guiado
        pueda volver a construirla desde cero.

        El recorrido dejó de sembrar por API: ahora completa los formularios de
        la propia app. Eso le quita la red de `crear_si_falta` —el segundo
        recorrido se comería un «ya existe un área con ese nombre»—, así que
        necesita poder arrancar de una institución limpia.

        Sólo super admin, y sólo sobre la institución escuela: es un borrado en
        cascada, y apuntarlo a un hospital real vaciaría el hospital. El nombre
        es el candado, no una convención.
        """
        from django.db.models import ProtectedError

        from apps.accounts.models import Usuario
        from apps.auditoria.models import AccesoClinico
        from apps.casos.models import Caso
        from apps.farmacia.models import Movimiento

        inst = self.get_object()

        if not request.user.is_superuser:
            return Response(
                {"detail": "Vaciar una institución es exclusivo de super admin."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if inst.nombre != NOMBRE_ESCUELA:
            return Response(
                {"detail": f"Sólo se puede vaciar «{NOMBRE_ESCUELA}», la institución de capacitación."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            # Las tres tablas que hay que borrar a mano, y por qué.
            #
            # PROTECT aborta el borrado SIEMPRE, incluso cuando lo que protege se
            # está borrando en la misma operación —esa tolerancia es de RESTRICT,
            # no de PROTECT—. Así que no alcanza con que todo cuelgue de la
            # institución por CASCADE: hay que sacar a los protectores primero, y
            # en orden.
            #
            # - AccesoClinico.institucion y .ciudadano: quién miró una historia
            #   clínica no se borra por arrastre. Acá sí, son pacientes de práctica.
            # - Movimiento.insumo: Movimiento no cuelga de nada que se borre, así
            #   que protege a los insumos de la escuela.
            # - Caso.version protege a VersionFlujo, que sí cuelga de la
            #   institución (Institucion → Flujo → VersionFlujo). Los casos tienen
            #   que irse ANTES que el flujo que los originó.
            # Los usuarios de práctica no cuelgan de la institución —una persona
            # puede tener membresías en varias—, así que vaciar la escuela los
            # dejaba vivos y el recorrido siguiente se comía un «ese email ya
            # existe» al querer darlos de alta de nuevo. Se van con la escuela,
            # acotados a los del escenario por prefijo y dominio.
            del_usuarios = Usuario.objects.filter(
                email__startswith=PREFIJO_USUARIO_ESCUELA,
                email__endswith=DOMINIO_USUARIO_ESCUELA,
                is_superuser=False,
            )
            accesos, _ = AccesoClinico.objects.filter(
                Q(institucion=inst) | Q(ciudadano__institucion=inst) | Q(usuario__in=del_usuarios)
            ).delete()
            movimientos, _ = Movimiento.objects.filter(insumo__institucion=inst).delete()
            casos, _ = Caso.objects.filter(
                Q(institucion=inst) | Q(version__flujo__institucion=inst)
            ).delete()
            usuarios, _ = del_usuarios.delete()
            try:
                borrados, detalle = inst.delete()
            except ProtectedError as e:
                # Si el grafo gana un PROTECT nuevo, que se vea qué lo frenó en
                # vez de un 500 opaco.
                modelos = sorted({type(o)._meta.label for o in e.protected_objects})
                return Response(
                    {"detail": "No se pudo vaciar la escuela: hay datos protegidos.",
                     "protegido_por": modelos},
                    status=status.HTTP_409_CONFLICT,
                )

        return Response({
            "vaciada": NOMBRE_ESCUELA,
            "borrados": borrados + accesos + movimientos + casos + usuarios,
            "detalle": detalle,
        })


class AreaViewSet(BaseModelViewSet):
    queryset = Area.objects.select_related("institucion").prefetch_related("subareas")
    serializer_class = AreaSerializer
    capacidad_requerida = "config_institucional"
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

        desde, hasta = _rango_pedido(request)
        rango = (desde, hasta)

        ACTIVO = ~Q(estado__in=[Caso.Estado.CERRADO, Caso.Estado.CANCELADO])
        dur = ExpressionWrapper(F("actualizado") - F("creado"), output_field=DurationField())
        espera_expr = ExpressionWrapper(F("llamado_at") - F("ingreso"), output_field=DurationField())
        atencion_expr = ExpressionWrapper(F("atendido_at") - F("llamado_at"), output_field=DurationField())

        # Dos preguntas distintas, dos definiciones de «área».
        #
        # `area_actual` es un puntero MÓVIL: el nodo `derivar` lo pisa con el área
        # destino mientras el caso sigue corriendo el flujo del área de origen.
        # Sirve para la carga VIVA (quién está parado acá ahora) y arruina la
        # producción del PERÍODO: los ingresos y cerrados de Guardia se los
        # llevaba el área a la que derivó, y la atribución cambiaba HACIA ATRÁS
        # —el ingreso contado a las 10:00 desaparecía de la serie a las 11:00, así
        # que el tablero de ayer no era el mismo hoy y el jefe no podía
        # reconciliarlo con su turno—. Lo que el área procesó se cuelga del flujo,
        # que no se mueve.
        vivos = Caso.objects.filter(area_actual=area)
        procesados = Caso.objects.filter(version__flujo__area=area)
        activos = vivos.filter(ACTIVO)
        en_rango = procesados.filter(creado__date__range=rango)
        cerrados_rango = procesados.filter(estado=Caso.Estado.CERRADO, actualizado__date__range=rango)
        items = ItemFila.objects.filter(nodo__version__flujo__area=area)
        # Sin `box__isnull=True` la cola incluye a los que ya están adentro del
        # box: el jefe lee «12 esperando» cuando la mitad está siendo atendida.
        cola = list(
            items.filter(atendido=False, box__isnull=True)
            .select_related("caso__ciudadano", "caso__area_actual", "nodo")
        )

        espera_v = _minutos(
            items.filter(llamado_at__isnull=False, ingreso__date__range=rango)
            .aggregate(a=Avg(espera_expr))["a"]
        )
        if espera_v is None:
            # `None` y no 0 cuando no hay ni medición ni cola: un 0 se lee como
            # «acá no se espera» y se pinta del mejor color de la pantalla.
            difs = [(now - it.ingreso).total_seconds() / 60 for it in cola]
            espera_v = round(sum(difs) / len(difs), 1) if difs else None
        atencion_v = _minutos(items.filter(
            atendido_at__isnull=False, atendido_at__gt=F("llamado_at"), atendido_at__date__range=rango
        ).aggregate(a=Avg(atencion_expr))["a"]) or 0
        resol_avg = cerrados_rango.aggregate(a=Avg(dur))["a"]

        resumen = {
            "activos": activos.count(),
            "en_cola": len(cola),
            # OJO: es la foto viva de cuántos casos están parados EN el estado
            # `atendido`, que es un estado de paso —el motor lo pisa con
            # `cerrado` en cuanto el caso llega al nodo Fin—. No mide lo que el
            # área atendió en el período: para eso está `cerrados`, que es lo que
            # dibuja la pantalla.
            "atendidos": vivos.filter(estado=Caso.Estado.ATENDIDO).count(),
            "ingresos": en_rango.count(),
            "cerrados": cerrados_rango.count(),
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

        # Del período, como el resto del panel: sobre todos los casos del área la
        # dona no se movía al cambiar el selector de rango.
        por_estado = {
            e["estado"]: e["n"]
            for e in en_rango.exclude(estado=Caso.Estado.CANCELADO).values("estado").annotate(n=Count("id"))
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
        serie_ingresos, agrupacion = _serie_ingresos(en_rango, desde, hasta)

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
    capacidad_requerida = "config_institucional"
    institucion_path = "area__institucion"
    filter_fields = ("area", "area__institucion", "activa")


class GrupoViewSet(BaseModelViewSet):
    queryset = Grupo.objects.select_related("area").prefetch_related("miembros")
    serializer_class = GrupoSerializer
    capacidad_requerida = "config_institucional"
    institucion_path = "area__institucion"
    filter_fields = ("area", "area__institucion", "activo")


class BoxViewSet(BaseModelViewSet):
    queryset = Box.objects.select_related("area", "ocupado_por")
    serializer_class = BoxSerializer
    capacidad_requerida = "config_institucional"
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


class CamaViewSet(BaseModelViewSet):
    """
    Camas de internación.

    Dar de alta o de baja una cama es configurar el hospital (`config`), pero
    marcarla higienizada o fuera de servicio es operación de todos los días y la
    hace enfermería (`trabajo`). De ahí las dos capacidades.
    """

    queryset = Cama.objects.select_related("area", "subarea", "caso__ciudadano")
    serializer_class = CamaSerializer
    capacidad_requerida = "config_institucional"
    capacidad_por_accion = {"estado": "internacion"}
    institucion_path = "area__institucion"
    filter_fields = ("area", "area__institucion", "subarea", "estado", "activa")
    search_fields = ("nombre",)
    ordering_fields = ("nombre", "estado", "desde")
    nombre_csv = "camas"
    columnas_csv = [
        ("nombre", "Cama"),
        ("sector", "Sector"),
        ("estado_display", "Estado"),
        ("paciente", "Paciente"),
        ("desde", "Desde"),
        ("motivo", "Motivo"),
    ]

    @action(detail=True, methods=["post"])
    def estado(self, request, pk=None):
        """Higiene → libre, o poner/sacar de servicio.

        Cuerpo: {"estado": "libre"|"higiene"|"bloqueada", "motivo": "..."}.
        Ocupar y desocupar NO pasan por acá: eso lo mueve el motor junto con la
        estadía del paciente.
        """
        cama = self.get_object()
        # Cama huérfana: figura ocupada y no hay a quién darle el egreso, porque
        # el caso se borró y su estadía se fue con él. El motor corta en OCUPADA
        # —con razón: marcar libre una cama con paciente lo dejaría internado en
        # ningún lado—, pero acá no hay paciente, y sin esta salida la cama se
        # pierde del stock del sector para siempre. No es un egreso: es reparar
        # una inconsistencia, y por eso se hace antes de pedirle nada al motor.
        if (
            cama.estado == Cama.Estado.OCUPADA
            and cama.caso_id is None
            and not cama.estadias.filter(hasta__isnull=True).exists()
        ):
            cama.estado = Cama.Estado.HIGIENE
            cama.save(update_fields=["estado"])
        try:
            cama = motor.cambiar_estado_cama(
                cama, request.data.get("estado"), autor=request.user,
                motivo=(request.data.get("motivo") or "").strip(),
            )
        except motor.ErrorMotor as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(cama).data)

    @action(detail=False, methods=["get"])
    def tablero(self, request):
        """
        Ocupación por sector: lo que se mira para saber si entra otro paciente.

        Es una sola consulta agrupada y no la lista de camas: un hospital con
        400 camas no necesita mandarlas todas para contestar «¿cuántas quedan?».
        Las camas dadas de baja no cuentan para nada — no existen a los fines de
        la ocupación.
        """
        qs = self.filter_queryset(self.get_queryset()).filter(activa=True)
        sectores = {}
        for cama in qs:
            clave = cama.subarea_id or f"area-{cama.area_id}"
            s = sectores.setdefault(clave, {
                "sector_id": cama.subarea_id,
                "area_id": cama.area_id,
                "sector": cama.sector_nombre,
                # El área va aparte porque el nombre del sector NO alcanza para
                # nombrarlo: `Subarea` es única por área, no por institución, así
                # que «Sala general» de Clínica médica y «Sala general» de
                # Cirugía conviven. Agrupadas están bien —la clave es el id—,
                # pero rotuladas igual el jefe de Cirugía lee la ocupación del
                # otro servicio como si fuera la suya.
                "area": cama.area.nombre,
                "total": 0, "ocupadas": 0, "libres": 0, "higiene": 0, "bloqueadas": 0,
            })
            s["total"] += 1
            s[{
                Cama.Estado.OCUPADA: "ocupadas",
                Cama.Estado.LIBRE: "libres",
                Cama.Estado.HIGIENE: "higiene",
                Cama.Estado.BLOQUEADA: "bloqueadas",
            }[cama.estado]] += 1

        for s in sectores.values():
            # Sobre camas EN SERVICIO: una cama fuera de servicio no está
            # disponible ni ocupada, y contarla en el denominador haría que un
            # sector con la mitad de las camas rotas parezca desahogado.
            operativas = s["total"] - s["bloqueadas"]
            s["operativas"] = operativas
            s["ocupacion"] = round(100 * s["ocupadas"] / operativas) if operativas else 0

        lista = sorted(sectores.values(), key=lambda s: (s["sector"], s["area"]))
        totales = {
            k: sum(s[k] for s in lista)
            for k in ("total", "operativas", "ocupadas", "libres", "higiene", "bloqueadas")
        }
        totales["ocupacion"] = (
            round(100 * totales["ocupadas"] / totales["operativas"]) if totales["operativas"] else 0
        )
        return Response({"sectores": lista, "totales": totales})


class EstadiaCamaViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    Historial de paso por camas. Sólo lectura: las estadías las abre y cierra el
    motor junto con la cama, y editarlas a mano rompería la correspondencia.
    """

    queryset = EstadiaCama.objects.select_related("cama__subarea", "cama__area")
    serializer_class = EstadiaCamaSerializer
    permission_classes = [IsAuthenticated, CapacidadPermission]
    capacidad_requerida = "internacion"
    institucion_path = "cama__area__institucion"
    filter_fields = ("cama", "caso", "cama__subarea")

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.is_superuser:
            return qs
        inst = self.request.user.membresias.filter(activo=True).values_list("institucion_id", flat=True)
        return qs.filter(cama__area__institucion_id__in=list(inst))
