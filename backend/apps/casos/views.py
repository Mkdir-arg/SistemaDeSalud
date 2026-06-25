from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common import BaseModelViewSet
from apps.flujos.models import Conexion, Nodo, VersionFlujo
from apps.instituciones.models import Box

from . import motor
from .models import Caso, EventoCaso, ItemFila, Notificacion, ValorCampo
from .serializers import (
    CasoDetalleSerializer,
    CasoSerializer,
    EventoCasoSerializer,
    ItemFilaSerializer,
    NotificacionSerializer,
    ValorCampoSerializer,
)


class CasoViewSet(BaseModelViewSet):
    queryset = Caso.objects.select_related(
        "institucion", "version__flujo", "ciudadano", "nodo_actual", "area_actual", "asignado_a",
        "origen__version__flujo",
    ).prefetch_related("valores", "eventos", "nodo_actual__grupos", "derivados__version__flujo", "en_filas")
    capacidad_requerida = "trabajo"
    institucion_path = "institucion"
    filter_fields = ("institucion", "version", "estado", "prioridad", "area_actual", "asignado_a")

    def get_serializer_class(self):
        if self.action == "retrieve":
            return CasoDetalleSerializer
        return CasoSerializer

    def get_serializer_context(self):
        # Para resolver `puede_tomar` sin N+1: precomputamos los grupos del usuario.
        ctx = super().get_serializer_context()
        u = self.request.user
        if u and u.is_authenticated:
            ctx["es_superuser"] = u.is_superuser
            ctx["user_grupo_ids"] = set(u.grupos.values_list("id", flat=True))
            ctx["areas_supervisadas"] = motor.areas_que_supervisa(u)
        return ctx

    def perform_create(self, serializer):
        # El ingreso siempre es de una persona: aseguramos su historia clínica.
        caso = serializer.save()
        motor.asegurar_historia(caso)

    @action(detail=True, methods=["get"])
    def eventos(self, request, pk=None):
        """Línea de tiempo (trazabilidad) del caso."""
        caso = self.get_object()
        data = EventoCasoSerializer(caso.eventos.all(), many=True).data
        return Response(data)

    @action(detail=True, methods=["post"])
    def tomar(self, request, pk=None):
        """Asigna el caso al usuario autenticado y registra el evento.

        Solo puede tomarlo quien integre alguno de los grupos responsables del
        paso actual (si el paso no declara grupos, queda abierto a todos).
        """
        caso = self.get_object()
        if not motor.usuario_puede_tomar(request.user, caso):
            return Response(
                {"detail": "No integrás ningún grupo responsable de este paso."},
                status=status.HTTP_403_FORBIDDEN,
            )
        caso.asignado_a = request.user
        caso.save(update_fields=["asignado_a", "actualizado"])
        EventoCaso.objects.create(
            caso=caso,
            titulo="Caso tomado",
            detalle=f"Asignado a {request.user.nombre_completo}",
            autor=request.user,
            nodo=caso.nodo_actual,
        )
        # Re-consulta para refrescar el prefetch de eventos/valores.
        caso = self.get_queryset().get(pk=caso.pk)
        return Response(CasoDetalleSerializer(caso).data)

    @action(detail=True, methods=["post"])
    def llamar(self, request, pk=None):
        """Llama al caso desde un box (cuerpo: {"box_id": <id>}).

        Solo puede llamar quien integre un grupo responsable del paso.
        """
        caso = self.get_object()
        if not motor.usuario_puede_tomar(request.user, caso):
            return Response(
                {"detail": "No integrás ningún grupo responsable de este paso."},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            motor.llamar(caso, box_id=request.data.get("box_id"), autor=request.user)
        except motor.ErrorMotor as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        caso = self.get_queryset().get(pk=caso.pk)
        return Response(CasoDetalleSerializer(caso, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"])
    def receta(self, request, pk=None):
        """El médico emite una receta (cuerpo: {"detalle": "..."}) en la HC del paciente."""
        caso = self.get_object()
        if not motor.usuario_puede_tomar(request.user, caso):
            return Response({"detail": "No integrás ningún grupo responsable de este paso."}, status=status.HTTP_403_FORBIDDEN)
        detalle = (request.data.get("detalle") or "").strip()
        if not detalle:
            return Response({"detail": "La receta necesita un detalle."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            motor.agregar_receta(caso, detalle, autor=request.user)
        except motor.ErrorMotor as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        caso = self.get_queryset().get(pk=caso.pk)
        return Response(CasoDetalleSerializer(caso, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"])
    def estudio(self, request, pk=None):
        """El médico solicita un estudio (cuerpo: {"tipo": "...", "area_id": <opcional>}).

        Sin `area_id` queda como pedido en la HC. Con `area_id`, se deriva a esa
        área (sub-proceso) y el caso espera hasta que el estudio vuelva.
        """
        caso = self.get_object()
        if not motor.usuario_puede_tomar(request.user, caso):
            return Response({"detail": "No integrás ningún grupo responsable de este paso."}, status=status.HTTP_403_FORBIDDEN)
        tipo = (request.data.get("tipo") or "").strip()
        if not tipo:
            return Response({"detail": "Indicá el tipo de estudio."}, status=status.HTTP_400_BAD_REQUEST)
        area_id = request.data.get("area_id")
        try:
            if area_id:
                from apps.instituciones.models import Area
                area = Area.objects.filter(pk=area_id).first()
                if not area:
                    return Response({"detail": "Área de estudio inválida."}, status=status.HTTP_400_BAD_REQUEST)
                motor.solicitar_estudio_derivado(caso, tipo, area, autor=request.user)
            else:
                motor.agregar_estudio(caso, tipo, autor=request.user)
        except motor.ErrorMotor as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        caso = self.get_queryset().get(pk=caso.pk)
        return Response(CasoDetalleSerializer(caso, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"])
    def interconsulta(self, request, pk=None):
        """Deriva el caso a otra área para una interconsulta y espera la vuelta
        (cuerpo: {"area_id": <id>, "motivo": "..."})."""
        caso = self.get_object()
        if not motor.usuario_puede_tomar(request.user, caso):
            return Response({"detail": "No integrás ningún grupo responsable de este paso."}, status=status.HTTP_403_FORBIDDEN)
        area_id = request.data.get("area_id")
        if not area_id:
            return Response({"detail": "Indicá el área de la interconsulta."}, status=status.HTTP_400_BAD_REQUEST)
        from apps.instituciones.models import Area
        area = Area.objects.filter(pk=area_id).first()
        if not area:
            return Response({"detail": "Área inválida."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            motor.solicitar_interconsulta(caso, area, (request.data.get("motivo") or "").strip(), autor=request.user)
        except motor.ErrorMotor as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        caso = self.get_queryset().get(pk=caso.pk)
        return Response(CasoDetalleSerializer(caso, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"])
    def asignar(self, request, pk=None):
        """Supervisor del área: reasigna el caso a un integrante (cuerpo {usuario_id})."""
        caso = self.get_object()
        if not motor.usuario_supervisa(request.user, caso):
            return Response({"detail": "Solo el jefe del área puede reasignar el caso."}, status=status.HTTP_403_FORBIDDEN)
        from apps.accounts.models import Usuario
        u = Usuario.objects.filter(pk=request.data.get("usuario_id")).first()
        if not u:
            return Response({"detail": "Usuario inválido."}, status=status.HTTP_400_BAD_REQUEST)
        caso.asignado_a = u
        caso.save(update_fields=["asignado_a", "actualizado"])
        EventoCaso.objects.create(caso=caso, titulo="Reasignado", detalle=f"a {u.nombre_completo}", autor=request.user, nodo=caso.nodo_actual)
        if u.id != request.user.id:
            paciente = f"{caso.ciudadano.nombre} {caso.ciudadano.apellido}".strip() if caso.ciudadano_id else ""
            detalle = " · ".join(x for x in (paciente, caso.version.flujo.titulo) if x)
            motor._notificar(u, "Te asignaron un caso", detalle=detalle, caso=caso)
        caso = self.get_queryset().get(pk=caso.pk)
        return Response(CasoDetalleSerializer(caso, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"])
    def priorizar(self, request, pk=None):
        """Supervisor del área: cambia la prioridad (cuerpo {prioridad})."""
        caso = self.get_object()
        if not motor.usuario_supervisa(request.user, caso):
            return Response({"detail": "Solo el jefe del área puede cambiar la prioridad."}, status=status.HTTP_403_FORBIDDEN)
        pri = request.data.get("prioridad")
        if pri not in dict(Caso.Prioridad.choices):
            return Response({"detail": "Prioridad inválida."}, status=status.HTTP_400_BAD_REQUEST)
        caso.prioridad = pri
        caso.save(update_fields=["prioridad", "actualizado"])
        # Reflejar la urgencia en la cola si el caso está esperando.
        caso.en_filas.filter(atendido=False).update(urgente=(pri == Caso.Prioridad.URGENTE))
        EventoCaso.objects.create(caso=caso, titulo="Prioridad cambiada", detalle=caso.get_prioridad_display(), autor=request.user, nodo=caso.nodo_actual)
        caso = self.get_queryset().get(pk=caso.pk)
        return Response(CasoDetalleSerializer(caso, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"])
    def cancelar(self, request, pk=None):
        """Supervisor del área: cancela el caso (cuerpo {motivo})."""
        caso = self.get_object()
        if not motor.usuario_supervisa(request.user, caso):
            return Response({"detail": "Solo el jefe del área puede cancelar el caso."}, status=status.HTTP_403_FORBIDDEN)
        try:
            motor.cancelar_caso(caso, autor=request.user, motivo=(request.data.get("motivo") or "").strip())
        except motor.ErrorMotor as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        caso = self.get_queryset().get(pk=caso.pk)
        return Response(CasoDetalleSerializer(caso, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"])
    def iniciar(self, request, pk=None):
        """Coloca el caso en el nodo Inicio y lo corre hasta la 1ª parada."""
        caso = self.get_object()
        try:
            motor.iniciar(caso, autor=request.user)
        except motor.ErrorMotor as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        caso = self.get_queryset().get(pk=caso.pk)
        return Response(CasoDetalleSerializer(caso).data)

    @action(detail=True, methods=["post"])
    def avanzar(self, request, pk=None):
        """
        Completa el nodo actual con los datos enviados y avanza al siguiente.
        Cuerpo según el tipo de nodo (ver `motor.avanzar`).
        """
        caso = self.get_object()
        if not motor.usuario_puede_tomar(request.user, caso):
            return Response(
                {"detail": "No integrás ningún grupo responsable de este paso."},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            motor.avanzar(caso, datos=request.data or {}, autor=request.user)
        except motor.ErrorMotor as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        caso = self.get_queryset().get(pk=caso.pk)
        return Response(CasoDetalleSerializer(caso).data)


PRIORIDAD_RANK = {"urgente": 0, "alta": 1, "normal": 2}


class MisTareasView(APIView):
    """
    Worklist del operador, segmentada por **paso** (nodo) del que es responsable.

    El sistema deriva todo de `usuario → grupos → nodos`: cada nodo que mi grupo
    posee, y los casos parados ahí, son mi trabajo. Devuelve cuatro bandas:

      - ``iniciar``:   flujos manuales cuyo **primer paso humano** es mío (puedo
                       arrancar un caso nuevo).
      - ``tareas``:    casos activos en nodos míos que NO son fila ni están
                       esperando un retorno, agrupados por paso.
      - ``filas``:     nodos míos de *atención con fila* + la cola + los boxes del
                       área (para llamar al siguiente).
      - ``esperando``: casos míos pausados esperando que vuelva un estudio o
                       interconsulta (no accionables todavía).

    Query param: ``?institucion=<id>`` (si falta, toma la 1ª membresía activa).
    """

    VACIO = {"iniciar": [], "tareas": [], "filas": [], "esperando": []}

    def get(self, request):
        user = request.user
        inst_id = request.query_params.get("institucion")
        if not inst_id:
            mem = user.membresias.filter(activo=True).first()
            inst_id = mem.institucion_id if mem else None
        if not inst_id:
            return Response(self.VACIO)

        # Grupos del usuario en la institución → nodos publicados de los que es responsable.
        grupos = user.grupos.filter(area__institucion_id=inst_id)
        mis_nodos = list(
            Nodo.objects.filter(
                grupos__in=grupos, version__estado=VersionFlujo.Estado.PUBLICADA
            ).select_related("version__flujo__area").distinct()
        )
        mis_nodo_ids = {n.id for n in mis_nodos}
        nodo_por_id = {n.id: n for n in mis_nodos}
        fila_nodo_ids = {
            n.id for n in mis_nodos
            if n.tipo == Nodo.Tipo.ATENCION and (n.config or {}).get("con_fila")
        }

        tareas, esperando = self._tareas_y_esperando(inst_id, mis_nodo_ids, fila_nodo_ids, nodo_por_id, user)
        filas = self._filas(fila_nodo_ids, nodo_por_id)
        iniciar = self._iniciar(inst_id, mis_nodo_ids)

        return Response({
            "iniciar": iniciar,
            "tareas": tareas,
            "filas": filas,
            "esperando": esperando,
        })

    # -- bandas -------------------------------------------------------------
    def _tareas_y_esperando(self, inst_id, mis_nodo_ids, fila_nodo_ids, nodo_por_id, user):
        casos = (
            Caso.objects.filter(institucion_id=inst_id, nodo_actual_id__in=mis_nodo_ids)
            .exclude(estado__in=[Caso.Estado.CERRADO, Caso.Estado.CANCELADO])
            .select_related("ciudadano", "version__flujo", "area_actual", "estudio")
            .prefetch_related("en_filas")
        )
        buckets, esperando = {}, []
        for c in casos:
            nodo = nodo_por_id.get(c.nodo_actual_id)
            if nodo is None:
                continue
            # Encolado y sin llamar (sin box) → se opera desde la banda de filas.
            if c.nodo_actual_id in fila_nodo_ids and self._en_cola(c):
                continue
            if c.esperando:
                d = self._caso_dict(c, user)
                d["nodo_titulo"] = nodo.titulo
                d["espera_de"] = c.estudio.tipo if c.estudio_id else "interconsulta"
                esperando.append(d)
                continue
            b = buckets.get(nodo.id)
            if b is None:
                flujo = nodo.version.flujo
                b = buckets[nodo.id] = {
                    "nodo_id": nodo.id, "nodo_titulo": nodo.titulo, "nodo_tipo": nodo.tipo,
                    "flujo_titulo": flujo.titulo,
                    "area_nombre": flujo.area.nombre if flujo.area_id else None,
                    "casos": [],
                }
            b["casos"].append(self._caso_dict(c, user))

        tareas = []
        for b in buckets.values():
            b["casos"].sort(key=lambda d: (PRIORIDAD_RANK.get(d["prioridad"], 9), d["creado"]))
            b["total"] = len(b["casos"])
            b["urgentes"] = sum(1 for d in b["casos"] if d["prioridad"] == "urgente")
            tareas.append(b)
        tareas.sort(key=lambda b: (-b["urgentes"], b["nodo_titulo"]))
        esperando.sort(key=lambda d: d["creado"])
        return tareas, esperando

    def _filas(self, fila_nodo_ids, nodo_por_id):
        if not fila_nodo_ids:
            return []
        items = (
            ItemFila.objects.filter(nodo_id__in=fila_nodo_ids, atendido=False, box__isnull=True)
            .select_related("caso__ciudadano").order_by("-urgente", "orden", "ingreso")
        )
        por_nodo = {}
        for it in items:
            por_nodo.setdefault(it.nodo_id, []).append(it)

        filas = []
        for nid in fila_nodo_ids:
            nodo = nodo_por_id[nid]
            flujo = nodo.version.flujo
            area = flujo.area
            cola = por_nodo.get(nid, [])
            boxes = list(Box.objects.filter(area=area, activo=True).values("id", "nombre")) if area else []
            filas.append({
                "nodo_id": nid, "nodo_titulo": nodo.titulo, "flujo_titulo": flujo.titulo,
                "area_id": area.id if area else None,
                "area_nombre": area.nombre if area else None,
                "en_cola": len(cola),
                "urgentes": sum(1 for it in cola if it.urgente),
                "boxes": boxes,
                "casos": [{
                    "id": it.caso_id, "item_id": it.id,
                    "ciudadano_nombre": self._nombre(it.caso.ciudadano),
                    "urgente": it.urgente, "ingreso": it.ingreso,
                } for it in cola],
            })
        filas.sort(key=lambda f: (-f["urgentes"], f["nodo_titulo"]))
        return filas

    def _iniciar(self, inst_id, mis_nodo_ids):
        iniciar = []
        versiones = (
            VersionFlujo.objects.filter(
                flujo__institucion_id=inst_id, estado=VersionFlujo.Estado.PUBLICADA
            ).select_related("flujo__area")
        )
        for ver in versiones:
            inicio = ver.nodos.filter(tipo=Nodo.Tipo.INICIO).first()
            if not inicio:
                continue
            if (inicio.config or {}).get("origen", "manual") not in ("manual", "ambos"):
                continue
            paso = self._primer_nodo_humano(ver, inicio)
            if paso and paso.id in mis_nodo_ids:
                iniciar.append({
                    "flujo_id": ver.flujo_id, "flujo_titulo": ver.flujo.titulo,
                    "version_id": ver.id,
                    "area_nombre": ver.flujo.area.nombre if ver.flujo.area_id else None,
                    "paso": paso.titulo,
                })
        iniciar.sort(key=lambda i: i["flujo_titulo"])
        return iniciar

    # -- helpers ------------------------------------------------------------
    @staticmethod
    def _nombre(ciudadano):
        if not ciudadano:
            return None
        return f"{ciudadano.nombre} {ciudadano.apellido}".strip()

    @staticmethod
    def _en_cola(caso):
        return any(
            it.nodo_id == caso.nodo_actual_id and not it.atendido and it.box_id is None
            for it in caso.en_filas.all()
        )

    def _caso_dict(self, c, user):
        return {
            "id": c.id,
            "ciudadano_nombre": self._nombre(c.ciudadano),
            "prioridad": c.prioridad,
            "prioridad_display": c.get_prioridad_display(),
            "estado": c.estado,
            "estado_display": c.get_estado_display(),
            "creado": c.creado,
            "asignado_a": c.asignado_a_id,
            "asignado_nombre": c.asignado_a.nombre_completo if c.asignado_a_id else None,
            "mio": c.asignado_a_id == user.id,
            "flujo_titulo": c.version.flujo.titulo,
            "area_nombre": c.area_actual.nombre if c.area_actual_id else None,
        }

    @staticmethod
    def _primer_nodo_humano(version, inicio):
        """Camina desde el Inicio por los nodos automáticos hasta el primer nodo
        que requiere acción humana (la puerta de entrada operable del flujo)."""
        actual, visitados = inicio, set()
        while actual is not None and actual.tipo in motor.TIPOS_AUTOMATICOS and actual.id not in visitados:
            visitados.add(actual.id)
            sig = Conexion.objects.filter(version=version, origen=actual).select_related("destino").first()
            actual = sig.destino if sig else None
        return actual


class ValorCampoViewSet(BaseModelViewSet):
    queryset = ValorCampo.objects.select_related("caso", "campo", "nodo")
    serializer_class = ValorCampoSerializer
    capacidad_requerida = "trabajo"
    institucion_path = "caso__institucion"
    filter_fields = ("caso", "campo")


class ItemFilaViewSet(BaseModelViewSet):
    queryset = ItemFila.objects.select_related("caso__ciudadano", "nodo__version__flujo__area", "box")
    serializer_class = ItemFilaSerializer
    capacidad_requerida = "trabajo"
    institucion_path = "caso__institucion"
    filter_fields = ("caso", "nodo", "urgente", "atendido", "nodo__version__flujo__area")


class EventoCasoViewSet(BaseModelViewSet):
    queryset = EventoCaso.objects.select_related("caso", "autor", "nodo")
    serializer_class = EventoCasoSerializer
    capacidad_requerida = "trabajo"
    institucion_path = "caso__institucion"
    filter_fields = ("caso", "autor")


class NotificacionViewSet(viewsets.ModelViewSet):
    """Avisos personales del usuario autenticado (no scopeado por institución)."""

    serializer_class = NotificacionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Notificacion.objects.filter(usuario=self.request.user).select_related("caso")

    @action(detail=False, methods=["get"])
    def resumen(self, request):
        """{no_leidas, items} — para la campana de la barra (poll liviano)."""
        qs = self.get_queryset()
        return Response({
            "no_leidas": qs.filter(leida=False).count(),
            "items": NotificacionSerializer(qs[:12], many=True).data,
        })

    @action(detail=False, methods=["post"])
    def leer(self, request):
        """Marca como leídas todas las del usuario (o solo las de `ids`)."""
        qs = self.get_queryset().filter(leida=False)
        ids = request.data.get("ids")
        if ids:
            qs = qs.filter(id__in=ids)
        return Response({"marcadas": qs.update(leida=True)})
