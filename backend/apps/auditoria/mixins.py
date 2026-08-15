"""
Cómo un viewset deja registrado que alguien miró datos clínicos.

La regla de oro: **registrar no puede hacer fallar la lectura**. Si el registro
de auditoría rompe, un médico tiene que poder seguir viendo la historia del
paciente que tiene delante. Se anota el problema y se sigue: perder una línea de
auditoría es malo, no poder atender es peor.
"""
import logging

from .models import AccesoClinico

log = logging.getLogger(__name__)


def _ip(request):
    reenviado = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if reenviado:
        # El primero de la cadena es el cliente; el resto son los proxies.
        return reenviado.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _institucion_del_pedido(request):
    """
    De qué institución habla un acceso que NO apunta a una persona.

    Un listado o una exportación no tienen un ciudadano de quien tomar la
    institución, y sin institución el acceso queda afuera de lo que
    `AccesoClinicoViewSet` deja leer: el admin del hospital abre el filtro
    «Exportación a archivo» y ve una lista vacía, o sea que el registro le
    contesta «acá no pasó nada» el día que alguien se bajó el padrón entero con
    documento, obra social y alergias. Quien responde ante el paciente y ante la
    Ley 25.326 es la institución, no el proveedor del software.

    Se toma del contexto del pedido: el `?institucion=` del listado —si el
    usuario actúa ahí— o su única membresía activa. Con varias membresías y sin
    filtro, elegir una sería anotar algo que no pasó: queda en nulo.

    Es el último recurso. Un listado con resultados se atribuye a las
    instituciones de las filas que devolvió (`_instituciones_alcanzadas`), que es
    el dato real; acá se cae sólo cuando no hay filas de donde sacarlo.
    """
    u = getattr(request, "user", None)
    if not (u and u.is_authenticated):
        return None
    ids = set(u.membresias.filter(activo=True).values_list("institucion_id", flat=True))
    pedida = (request.query_params.get("institucion") or "").strip()
    if pedida.isdigit():
        pedida = int(pedida)
        # Sin este chequeo, cualquiera podría ensuciar el registro de otra
        # institución mandando un id que no le corresponde.
        return pedida if (u.is_superuser or pedida in ids) else None
    return next(iter(ids)) if len(ids) == 1 else None


def registrar_acceso(
    request, tipo, recurso, ciudadano=None, objeto_id="", detalle="", resultados=0,
    institucion_id=None,
):
    """
    Escribe UNA línea del registro de accesos.

    Está suelta y no dentro del mixin para que cualquier camino que exponga
    datos clínicos —el viewset, la fachada FHIR, lo que venga— anote por el
    mismo lado. Una segunda implementación es una segunda forma de olvidarse.

    `recurso` es el nombre del MODELO y no el de la URL: una ruta se puede
    renombrar y el registro tiene que seguir diciendo lo mismo dentro de diez
    años, que es cuanto hay que conservarlo.

    `institucion_id` es para quien ya sabe a qué institución pertenece lo que se
    leyó —un listado sabe de dónde salieron sus filas—; sin eso hay que
    adivinarlo del contexto del pedido, y adivinar mal deja el acceso fuera de
    la vista de quien tiene que responder por él.
    """
    try:
        AccesoClinico.objects.create(
            usuario=request.user,
            ciudadano=ciudadano,
            institucion_id=(
                getattr(ciudadano, "institucion_id", None)
                or institucion_id
                or _institucion_del_pedido(request)
            ),
            tipo=tipo,
            recurso=recurso,
            objeto_id=str(objeto_id or "")[:40],
            detalle=(detalle or "")[:300],
            resultados=resultados,
            ip=_ip(request),
        )
    except Exception:
        # Ver la regla de oro del módulo: la atención no se detiene porque falle
        # la auditoría. Queda en el log del servidor para que alguien lo vea, en
        # vez de desaparecer.
        log.exception("no se pudo registrar el acceso clínico")


class AuditaLecturaClinica:
    """
    Registra quién consulta datos clínicos.

    Se aplica a los viewsets que exponen la historia de una persona. Los que
    declaran `protege_lectura` son exactamente esos, y hay un test que verifica
    que ninguno quede sin auditar: agregar un recurso clínico nuevo sin este
    mixin haría un agujero que nadie notaría.

    `ciudadano_path` dice cómo llegar desde el objeto hasta la persona, que es
    de quien habla la ley.
    """

    ciudadano_path: str = "ciudadano"

    def _ciudadano_de(self, obj):
        # `self` = el objeto YA es la persona (el padrón de pacientes).
        if self.ciudadano_path == "self":
            return obj
        cur = obj
        for parte in self.ciudadano_path.split("__"):
            if cur is None:
                return None
            cur = getattr(cur, parte, None)
        return cur

    def _anotar(self, tipo, ciudadano=None, objeto_id="", detalle="", resultados=0,
                institucion_id=None):
        registrar_acceso(
            self.request, tipo, self.queryset.model._meta.model_name,
            ciudadano=ciudadano, objeto_id=objeto_id, detalle=detalle,
            resultados=resultados, institucion_id=institucion_id,
        )

    def retrieve(self, request, *args, **kwargs):
        respuesta = super().retrieve(request, *args, **kwargs)
        obj = self.get_object()
        self._anotar(
            AccesoClinico.Tipo.DETALLE,
            ciudadano=self._ciudadano_de(obj),
            objeto_id=getattr(obj, "pk", ""),
        )
        return respuesta

    def list(self, request, *args, **kwargs):
        respuesta = super().list(request, *args, **kwargs)
        try:
            self._anotar_listado(request, respuesta)
        except Exception:
            # La regla de oro del módulo, que hasta acá no cubría este bloque:
            # sólo el `create` estaba adentro del guarda. Con `?ciudadano=undefined`
            # —un bug del frontend, un link viejo, un integrador que manda
            # `Patient/12`— la búsqueda del paciente levantaba ValueError DESPUÉS
            # de que la respuesta ya estaba armada, y el padrón dejaba de abrir en
            # medio de una guardia por culpa del registro de auditoría.
            log.exception("no se pudo registrar el listado clínico")
        return respuesta

    def _anotar_listado(self, request, respuesta):
        # Qué se buscó. Es lo que distingue «buscó a una persona por documento»
        # de «abrió el padrón entero», que son dos accesos muy distintos.
        filtros = {
            k: v for k, v in request.query_params.items()
            if k not in ("page", "page_size", "ordering", "formato", "sep")
        }

        exportacion = request.query_params.get("formato") == "csv"
        if exportacion:
            # La exportación devuelve un `StreamingHttpResponse`, que no tiene
            # `.data`: contar sobre la respuesta daba 0 SIEMPRE. El acceso más
            # grave que este registro tiene que poder mostrar —alguien se llevó
            # el padrón en un archivo— quedaba anotado sin decir si fueron tres
            # pacientes o cuarenta mil, que es toda la diferencia en un reclamo.
            cuantos = self.filter_queryset(self.get_queryset()).count()
        else:
            datos = getattr(respuesta, "data", None)
            cuantos = (
                datos.get("count", len(datos.get("results", [])))
                if isinstance(datos, dict) else (len(datos) if isinstance(datos, list) else 0)
            )

        # Un listado filtrado a UNA persona se registra como acceso a esa
        # persona: es lo que ocurrió, y si no, buscar por `?ciudadano=X` sería
        # una forma de leer una historia sin dejar rastro a su nombre.
        ciudadano = None
        for clave in ("ciudadano", "historia__ciudadano"):
            valor = filtros.get(clave)
            # Sólo se consulta si el valor puede ser un id. Un `?ciudadano=undefined`
            # buscado tal cual explota contra la base, y el listado clínico ya
            # está resuelto: el paciente se queda sin ver su historia porque el
            # registro no supo qué hacer con un parámetro basura.
            if valor and str(valor).isdigit():
                from apps.registros.models import Ciudadano

                ciudadano = Ciudadano.objects.filter(pk=valor).first()
                break

        tipo = AccesoClinico.Tipo.EXPORTACION if exportacion else AccesoClinico.Tipo.LISTADO
        texto = " ".join(f"{k}={v}" for k, v in sorted(filtros.items()))
        if ciudadano is not None:
            self._anotar(tipo, ciudadano=ciudadano, detalle=texto, resultados=cuantos or 0)
            return

        # A qué instituciones tocó de verdad este listado.
        #
        # Sin esto, un administrativo con cargo en dos hospitales pedía
        # `/api/ciudadanos/?formato=csv`, se llevaba los dos padrones en un
        # archivo —documento, fecha de nacimiento, obra social, condiciones y
        # alergias— y el acceso quedaba sin institución, o sea invisible para
        # los dos admins que responden por esa base ante la Ley 25.326. Igual
        # con el superusuario del proveedor, que no tiene ninguna membresía: el
        # hospital no podía auditar ni a su propio empleado con doble cargo ni a
        # su proveedor. Una fila por institución, cada una con SU cantidad: así
        # el admin de A lee «se exportaron 2 de sus pacientes» y el de B también.
        por_institucion = self._instituciones_alcanzadas()
        if len(por_institucion) <= 1:
            unica = por_institucion[0][0] if por_institucion else None
            self._anotar(tipo, detalle=texto, resultados=cuantos or 0, institucion_id=unica)
            return
        for institucion_id, n in por_institucion:
            self._anotar(tipo, detalle=texto, resultados=n, institucion_id=institucion_id)

    def _instituciones_alcanzadas(self):
        """`[(institucion_id, cuántas filas), …]` de lo que este listado devolvió."""
        campo = getattr(self, "institucion_path", None)
        if not campo:
            return []
        from django.db.models import Count

        modelo = self.queryset.model
        # Se rearma la consulta desde el modelo en vez de agrupar el queryset del
        # viewset: ése trae anotaciones y precargas que no tienen nada que ver
        # con contar por institución y romperían el GROUP BY.
        filas = (
            modelo.objects
            .filter(pk__in=self.filter_queryset(self.get_queryset()).values("pk"))
            .order_by()
            .values(campo)
            .annotate(n=Count("pk"))
        )
        return [(f[campo], f["n"]) for f in filas]
