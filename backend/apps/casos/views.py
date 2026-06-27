from django.db.models import Count
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
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
    filter_fields = ("institucion", "version", "estado", "prioridad", "area_actual", "asignado_a", "ciudadano")

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
    def rellamar(self, request, pk=None):
        """Vuelve a llamar al paciente (atención con fila) que no se presentó.

        Solo puede rellamar quien integre un grupo responsable del paso."""
        caso = self.get_object()
        if not motor.usuario_puede_tomar(request.user, caso):
            return Response(
                {"detail": "No integrás ningún grupo responsable de este paso."},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            motor.rellamar(caso, autor=request.user)
        except motor.ErrorMotor as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        caso = self.get_queryset().get(pk=caso.pk)
        return Response(CasoDetalleSerializer(caso, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"])
    def receta(self, request, pk=None):
        """Médico o enfermería emite una receta (cuerpo: {"detalle": "..."}) en la HC del paciente."""
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
        """Médico o enfermería solicita un estudio (cuerpo: {"tipo": "...", "area_id": <opcional>}).

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
        mis_grupo_ids = set(grupos.values_list("id", flat=True))
        mis_nodos = list(
            Nodo.objects.filter(
                grupos__in=grupos, version__estado=VersionFlujo.Estado.PUBLICADA
            ).select_related("version__flujo__area").prefetch_related("grupos").distinct()
        )
        mis_nodo_ids = {n.id for n in mis_nodos}
        nodo_por_id = {n.id: n for n in mis_nodos}
        fila_nodo_ids = {
            n.id for n in mis_nodos
            if n.tipo == Nodo.Tipo.ATENCION and (n.config or {}).get("con_fila")
        }

        iniciar = self._iniciar(inst_id, mis_nodo_ids)
        iniciar_node_ids = {i["paso_nodo_id"] for i in iniciar}
        tareas, esperando = self._tareas_y_esperando(
            inst_id, mis_nodo_ids, fila_nodo_ids, nodo_por_id, user, mis_grupo_ids
        )
        filas = self._filas(fila_nodo_ids, nodo_por_id, user, mis_grupo_ids)
        # "Mis puestos" (indicadores vivos de cada paso) + "Tu turno" (producción del día).
        puestos, turno = self._puestos_y_turno(
            inst_id, nodo_por_id, fila_nodo_ids, iniciar_node_ids, user
        )
        mis_casos = self._mis_casos(inst_id, user)
        resumen_areas = self._resumen_areas(inst_id, nodo_por_id)
        mis_ingresos = self._mis_ingresos_hoy(inst_id, user)

        return Response({
            "iniciar": iniciar,
            "tareas": tareas,
            "filas": filas,
            "esperando": esperando,
            # Indicadores VIVOS de los pasos de los que soy responsable + mi turno.
            "puestos": puestos,
            "turno": turno,
            # Casos a mi nombre, activos (para retomar de un toque).
            "mis_casos": mis_casos,
            # Pulso por área (hoy) + lo que ingresé/toqué hoy.
            "resumen_areas": resumen_areas,
            "mis_ingresos": mis_ingresos,
        })

    def _resumen_areas(self, inst_id, nodo_por_id):
        """Pulso por área (las áreas donde trabajo): estado de la guardia hoy."""
        areas = {}
        for n in nodo_por_id.values():
            flujo = n.version.flujo
            if flujo.area_id:
                areas[flujo.area_id] = flujo.area.nombre
        hoy = timezone.localdate()
        now = timezone.now()
        out = {}
        for aid, nombre in areas.items():
            base = Caso.objects.filter(institucion_id=inst_id, version__flujo__area_id=aid)
            activos = base.exclude(estado__in=[Caso.Estado.CERRADO, Caso.Estado.CANCELADO])
            esperas = list(
                ItemFila.objects.filter(
                    caso__version__flujo__area_id=aid, atendido=False, box__isnull=True
                ).values_list("ingreso", flat=True)
            )
            espera_prom = (
                round(sum((now - i).total_seconds() / 60 for i in esperas) / len(esperas)) if esperas else 0
            )
            out[nombre] = {
                "en_espera": activos.filter(estado=Caso.Estado.EN_ESPERA).count(),
                "en_atencion": activos.filter(estado=Caso.Estado.EN_EVALUACION).count(),
                "ingresos_hoy": base.filter(creado__date=hoy).count(),
                "urgentes": activos.filter(prioridad=Caso.Prioridad.URGENTE).count(),
                "espera_prom_min": espera_prom,
            }
        return out

    def _mis_ingresos_hoy(self, inst_id, user):
        """Casos que toqué hoy (los que ingresé/avancé), para seguirlos/corregirlos."""
        hoy = timezone.localdate()
        ids = list(
            EventoCaso.objects.filter(autor=user, caso__institucion_id=inst_id, fecha__date=hoy)
            .values_list("caso_id", flat=True).distinct()
        )
        casos = (
            Caso.objects.filter(id__in=ids)
            .select_related("ciudadano", "nodo_actual", "version__flujo__area")
            .order_by("-actualizado")[:20]
        )
        return [{
            "id": c.id,
            "ciudadano_nombre": self._nombre(c.ciudadano),
            "area_nombre": c.version.flujo.area.nombre if c.version.flujo.area_id else None,
            "paso_actual": c.nodo_actual.titulo if c.nodo_actual_id else None,
            "estado": c.estado, "estado_display": c.get_estado_display(),
            "creado": c.creado,
        } for c in casos]

    def _mis_casos(self, inst_id, user):
        casos = (
            Caso.objects.filter(institucion_id=inst_id, asignado_a=user)
            .exclude(estado__in=[Caso.Estado.CERRADO, Caso.Estado.CANCELADO])
            .select_related("ciudadano", "nodo_actual", "area_actual", "version__flujo")
            .order_by("-actualizado")[:20]
        )
        return [{
            "id": c.id,
            "ciudadano_nombre": self._nombre(c.ciudadano),
            "paso_actual": c.nodo_actual.titulo if c.nodo_actual_id else None,
            "area_nombre": c.area_actual.nombre if c.area_actual_id else None,
            "flujo_titulo": c.version.flujo.titulo,
            "estado": c.estado, "estado_display": c.get_estado_display(),
            "prioridad": c.prioridad, "esperando": c.esperando,
        } for c in casos]

    # -- bandas -------------------------------------------------------------
    def _bucket(self, nodo, mis_grupo_ids):
        """Crea un bucket de paso, anotando el/los grupo(s) tuyos responsables."""
        flujo = nodo.version.flujo
        grupos = [g.nombre for g in nodo.grupos.all() if g.id in mis_grupo_ids]
        return {
            "nodo_id": nodo.id, "nodo_titulo": nodo.titulo, "nodo_tipo": nodo.tipo,
            "flujo_titulo": flujo.titulo,
            "area_nombre": flujo.area.nombre if flujo.area_id else None,
            "grupos": grupos,
            "casos": [],
        }

    def _tareas_y_esperando(self, inst_id, mis_nodo_ids, fila_nodo_ids, nodo_por_id, user, mis_grupo_ids):
        casos = (
            Caso.objects.filter(institucion_id=inst_id, nodo_actual_id__in=mis_nodo_ids)
            .exclude(estado__in=[Caso.Estado.CERRADO, Caso.Estado.CANCELADO])
            .select_related("ciudadano", "version__flujo", "area_actual", "estudio")
            .prefetch_related("en_filas")
        )
        # Boxes que ocupa el usuario: una atención con fila ya llamada solo es "mía"
        # si la llamé a un box que estoy ocupando.
        mis_box_ids = set(Box.objects.filter(ocupado_por=user).values_list("id", flat=True))

        buckets, esperando = {}, []
        for c in casos:
            nodo = nodo_por_id.get(c.nodo_actual_id)
            if nodo is None:
                continue
            # Atención con fila: separar la cola (banda Filas) de la atención en curso.
            if c.nodo_actual_id in fila_nodo_ids:
                item = next((it for it in c.en_filas.all() if it.nodo_id == c.nodo_actual_id and not it.atendido), None)
                if item is None or item.box_id is None:
                    continue  # en cola (sin box) → se opera desde la banda de filas
                if item.box_id not in mis_box_ids:
                    continue  # llamado a un box que no es el tuyo → no es tu atención
            if c.esperando:
                d = self._caso_dict(c, user)
                d["nodo_titulo"] = nodo.titulo
                d["espera_de"] = c.estudio.tipo if c.estudio_id else "interconsulta"
                esperando.append(d)
                continue
            if nodo.id not in buckets:
                buckets[nodo.id] = self._bucket(nodo, mis_grupo_ids)
            buckets[nodo.id]["casos"].append(self._caso_dict(c, user))

        # Solo pasos CON casos accionables (la visión completa de responsabilidades
        # vive en la banda "Mis puestos").
        tareas = []
        for b in buckets.values():
            b["casos"].sort(key=lambda d: (PRIORIDAD_RANK.get(d["prioridad"], 9), d["creado"]))
            b["total"] = len(b["casos"])
            b["urgentes"] = sum(1 for d in b["casos"] if d["prioridad"] == "urgente")
            tareas.append(b)
        tareas.sort(key=lambda b: (-b["urgentes"], b["nodo_titulo"]))
        esperando.sort(key=lambda d: d["creado"])
        return tareas, esperando

    def _filas(self, fila_nodo_ids, nodo_por_id, user, mis_grupo_ids):
        if not fila_nodo_ids:
            return []
        items = list(
            ItemFila.objects.filter(nodo_id__in=fila_nodo_ids, atendido=False, box__isnull=True)
            .select_related("caso__ciudadano")
        )
        # La cola se ordena por prioridad del caso (urgente > alta > normal) y luego por llegada.
        items.sort(key=lambda it: (PRIORIDAD_RANK.get(it.caso.prioridad, 9), it.ingreso))
        por_nodo = {}
        for it in items:
            por_nodo.setdefault(it.nodo_id, []).append(it)

        filas = []
        for nid in fila_nodo_ids:
            nodo = nodo_por_id[nid]
            flujo = nodo.version.flujo
            area = flujo.area
            cola = por_nodo.get(nid, [])
            boxes_qs = list(Box.objects.filter(area=area, activo=True).select_related("ocupado_por")) if area else []
            boxes = [{
                "id": b.id, "nombre": b.nombre,
                "ocupado_por": b.ocupado_por_id,
                "ocupado_por_nombre": b.ocupado_por.nombre_completo if b.ocupado_por_id else None,
            } for b in boxes_qs]
            mi_box = next((b["id"] for b in boxes if b["ocupado_por"] == user.id), None)
            filas.append({
                "nodo_id": nid, "nodo_titulo": nodo.titulo, "flujo_titulo": flujo.titulo,
                "area_id": area.id if area else None,
                "area_nombre": area.nombre if area else None,
                "grupos": [g.nombre for g in nodo.grupos.all() if g.id in mis_grupo_ids],
                "en_cola": len(cola),
                "urgentes": sum(1 for it in cola if it.urgente),
                "boxes": boxes,
                "mi_box": mi_box,
                "casos": [{
                    "id": it.caso_id, "item_id": it.id,
                    "ciudadano_nombre": self._nombre(it.caso.ciudadano),
                    "urgente": it.urgente, "prioridad": it.caso.prioridad, "ingreso": it.ingreso,
                } for it in cola],
            })
        filas.sort(key=lambda f: (-f["urgentes"], f["nodo_titulo"]))
        return filas

    def _puestos_y_turno(self, inst_id, nodo_por_id, fila_nodo_ids, iniciar_node_ids, user):
        """Indicadores **vivos** de cada paso del que soy responsable + mi turno.

        - ``puestos``: una tarjeta por nodo mío con su carga del momento (casos
          parados ahí, urgentes, el más antiguo) y cuántos casos resolví hoy en
          él. Sirve para todos los roles; para el administrativo de admisión —cuyo
          único nodo es la entrada— convierte una pantalla vacía en su tablero.
        - ``turno``: producción personal del día (casos tocados hoy, último
          movimiento, casos en curso a mi nombre).
        """
        hoy = timezone.localdate()
        nodo_ids = list(nodo_por_id.keys())
        if not nodo_ids:
            return [], {"resueltos_hoy": 0, "ultimo_at": None, "en_curso": 0}

        # Snapshot del momento: casos activos parados en mis nodos (sin los que
        # esperan el retorno de un sub-proceso, que viven en su propia banda).
        activos = (
            Caso.objects
            .filter(institucion_id=inst_id, nodo_actual_id__in=nodo_ids, esperando=False)
            .exclude(estado__in=[Caso.Estado.CERRADO, Caso.Estado.CANCELADO])
            .values_list("nodo_actual_id", "prioridad", "creado")
        )
        snap = {}
        for nid, prio, creado in activos:
            s = snap.setdefault(nid, {"ahora": 0, "urgentes": 0, "desde": None})
            s["ahora"] += 1
            if prio == Caso.Prioridad.URGENTE:
                s["urgentes"] += 1
            if s["desde"] is None or creado < s["desde"]:
                s["desde"] = creado

        # Resueltos hoy: casos DISTINTOS que toqué hoy en cada nodo (cada paso que
        # completo deja un EventoCaso con autor=yo y nodo=ese paso).
        eventos = (
            EventoCaso.objects
            .filter(autor=user, nodo_id__in=nodo_ids, fecha__date=hoy)
            .values_list("nodo_id", "caso_id", "fecha")
        )
        hoy_por_nodo, casos_hoy, ultimo = {}, set(), None
        for nid, cid, fecha in eventos:
            hoy_por_nodo.setdefault(nid, set()).add(cid)
            casos_hoy.add(cid)
            if ultimo is None or fecha > ultimo:
                ultimo = fecha

        puestos = []
        for nid, nodo in nodo_por_id.items():
            s = snap.get(nid, {})
            flujo = nodo.version.flujo
            rol = ("entrada" if nid in iniciar_node_ids
                   else "fila" if nid in fila_nodo_ids else "tarea")
            puestos.append({
                "nodo_id": nid, "nodo_titulo": nodo.titulo, "nodo_tipo": nodo.tipo,
                "flujo_titulo": flujo.titulo,
                "area_nombre": flujo.area.nombre if flujo.area_id else None,
                "rol": rol,
                "ahora": s.get("ahora", 0),
                "urgentes": s.get("urgentes", 0),
                "desde": s.get("desde"),
                "hoy": len(hoy_por_nodo.get(nid, ())),
                "_orden": (flujo.titulo, nodo.x, nodo.id),  # posición en el flujo (de izq. a der.)
            })
        # Orden del FLUJO: por flujo y posición del nodo en el lienzo (no por carga).
        puestos.sort(key=lambda p: p.pop("_orden"))

        en_curso = (
            Caso.objects
            .filter(institucion_id=inst_id, asignado_a=user, esperando=False)
            .exclude(estado__in=[Caso.Estado.CERRADO, Caso.Estado.CANCELADO])
            .count()
        )
        turno = {"resueltos_hoy": len(casos_hoy), "ultimo_at": ultimo, "en_curso": en_curso}
        return puestos, turno

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
                    "paso": paso.titulo, "paso_nodo_id": paso.id,
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


class PuestoDetalleView(APIView):
    """Detalle de un **paso** (nodo) del que soy responsable: indicadores del
    momento + la tabla de casos parados ahí. Lo abre cada tarjeta de «Mis puestos»."""

    def get(self, request, nodo_id):
        user = request.user
        nodo = (
            Nodo.objects.select_related("version__flujo__area")
            .prefetch_related("grupos").filter(pk=nodo_id).first()
        )
        if nodo is None:
            return Response({"detail": "El paso no existe."}, status=status.HTTP_404_NOT_FOUND)
        # Seguridad: tenés que ser responsable del paso (o super admin).
        if not user.is_superuser and not nodo.grupos.filter(miembros=user).exists():
            return Response({"detail": "No sos responsable de este paso."}, status=status.HTTP_403_FORBIDDEN)

        flujo = nodo.version.flujo
        con_fila = nodo.tipo == Nodo.Tipo.ATENCION and (nodo.config or {}).get("con_fila")
        casos = list(
            Caso.objects.filter(nodo_actual=nodo)
            .exclude(estado__in=[Caso.Estado.CERRADO, Caso.Estado.CANCELADO])
            .select_related("ciudadano", "asignado_a", "area_actual")
            .prefetch_related("en_filas")
        )

        def item_de(c):
            return next((it for it in c.en_filas.all() if it.nodo_id == nodo.id and not it.atendido), None)

        rank = {"urgente": 0, "alta": 1, "normal": 2}
        casos.sort(key=lambda c: (rank.get(c.prioridad, 9), c.creado))

        filas = [{
            "id": c.id,
            "ciudadano_nombre": self._nombre(c.ciudadano),
            "prioridad": c.prioridad, "prioridad_display": c.get_prioridad_display(),
            "estado": c.estado, "estado_display": c.get_estado_display(),
            "creado": c.creado,
            "asignado_nombre": c.asignado_a.nombre_completo if c.asignado_a_id else None,
            "mio": c.asignado_a_id == user.id,
            "asignado": bool(c.asignado_a_id),
            "esperando": c.esperando,
            "en_fila": bool((it := item_de(c)) and it.box_id is None),
            "llamado": bool(item_de(c) and item_de(c).box_id is not None),
        } for c in casos]

        # Box que ocupo en el área (para poder llamar desde este paso si es con fila).
        mi_box = None
        if con_fila and flujo.area_id:
            mi_box = Box.objects.filter(area_id=flujo.area_id, ocupado_por=user).values_list("id", flat=True).first()

        en_cola = sum(1 for f in filas if f["en_fila"])
        urgentes = sum(1 for f in filas if f["prioridad"] == "urgente")
        hoy = (
            EventoCaso.objects.filter(nodo=nodo, fecha__date=timezone.localdate())
            .values("caso").distinct().count()
        )
        return Response({
            "nodo": {
                "id": nodo.id, "titulo": nodo.titulo, "tipo": nodo.tipo, "con_fila": bool(con_fila),
                "flujo_titulo": flujo.titulo,
                "area_nombre": flujo.area.nombre if flujo.area_id else None,
            },
            "mi_box": mi_box,
            "indicadores": {
                "ahora": en_cola if con_fila else len(filas),
                "en_cola": en_cola,
                "urgentes": urgentes,
                "hoy": hoy,
                "desde": min((c.creado for c in casos), default=None),
            },
            "casos": filas,
        })

    @staticmethod
    def _nombre(ciudadano):
        return f"{ciudadano.nombre} {ciudadano.apellido}".strip() if ciudadano else None


class PantallaLlamadosView(APIView):
    """Pantalla pública de llamados de un nodo con fila (TV de sala de espera).

    Sin autenticación: se accede por un token impredecible que se genera al
    configurar el nodo (`/api/pantalla/<token>/`). Devuelve los últimos pacientes
    llamados y desde qué box, para que la pantalla muestre a quién toca pasar.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, token):
        if not token:
            return Response({"detail": "Token requerido."}, status=status.HTTP_404_NOT_FOUND)
        nodo = (
            Nodo.objects.select_related("version__flujo__area")
            .filter(pantalla_token=token).first()
        )
        if nodo is None:
            return Response({"detail": "Pantalla no encontrada."}, status=status.HTTP_404_NOT_FOUND)

        from django.db.models.functions import Coalesce

        flujo = nodo.version.flujo
        # Orden por el ÚLTIMO llamado (un rellamado vuelve a ponerlo arriba).
        llamados = list(
            ItemFila.objects.filter(nodo=nodo, llamado_at__isnull=False)
            .select_related("caso__ciudadano", "box")
            .annotate(ultimo=Coalesce("rellamado_at", "llamado_at"))
            .order_by("-ultimo")[:8]
        )
        en_espera = ItemFila.objects.filter(nodo=nodo, atendido=False, box__isnull=True).count()

        def nombre(c):
            return f"{c.ciudadano.nombre} {c.ciudadano.apellido}".strip() if c and c.ciudadano_id else None

        return Response({
            "nodo": {"id": nodo.id, "titulo": nodo.titulo},
            "area_nombre": flujo.area.nombre if flujo.area_id else None,
            "flujo_titulo": flujo.titulo,
            "en_espera": en_espera,
            "llamados": [{
                "id": it.id,
                "persona": nombre(it.caso),
                "turno": it.turno or f"#{it.caso_id}",
                "box": it.box.nombre if it.box_id else None,
                "urgente": it.urgente,
                "llamado_at": it.ultimo,
                "veces": it.veces_llamado,
            } for it in llamados],
        })


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
