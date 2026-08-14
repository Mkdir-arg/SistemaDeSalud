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

    def _anotar(self, tipo, ciudadano=None, objeto_id="", detalle="", resultados=0):
        try:
            inst = getattr(ciudadano, "institucion", None)
            AccesoClinico.objects.create(
                usuario=self.request.user,
                ciudadano=ciudadano,
                institucion=inst,
                tipo=tipo,
                # El nombre del MODELO y no el de la URL: una ruta se puede
                # renombrar y el registro tiene que seguir diciendo lo mismo
                # dentro de diez años, que es cuanto hay que conservarlo.
                recurso=self.queryset.model._meta.model_name,
                objeto_id=str(objeto_id or "")[:40],
                detalle=detalle[:300],
                resultados=resultados,
                ip=_ip(self.request),
            )
        except Exception:
            # Ver la regla de oro del módulo: la atención no se detiene porque
            # falle la auditoría. Queda en el log del servidor para que alguien
            # lo vea, en vez de desaparecer.
            log.exception("no se pudo registrar el acceso clínico")

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

        # Qué se buscó. Es lo que distingue «buscó a una persona por documento»
        # de «abrió el padrón entero», que son dos accesos muy distintos.
        filtros = {
            k: v for k, v in request.query_params.items()
            if k not in ("page", "page_size", "ordering", "formato", "sep")
        }
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
            if filtros.get(clave):
                from apps.registros.models import Ciudadano

                ciudadano = Ciudadano.objects.filter(pk=filtros[clave]).first()
                break

        self._anotar(
            AccesoClinico.Tipo.EXPORTACION
            if request.query_params.get("formato") == "csv"
            else AccesoClinico.Tipo.LISTADO,
            ciudadano=ciudadano,
            detalle=" ".join(f"{k}={v}" for k, v in sorted(filtros.items())),
            resultados=cuantos or 0,
        )
        return respuesta
