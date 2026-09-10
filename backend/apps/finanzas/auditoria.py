"""Registro de lecturas de gastos, sin intervenir en la atención clínica."""
import logging
from collections import Counter

from django.db import transaction
from rest_framework.exceptions import APIException

from apps.auditoria.mixins import _institucion_del_pedido
from .models import AccesoFinanciero

log = logging.getLogger(__name__)


class AuditoriaFinancieraNoDisponible(APIException):
    status_code = 503
    default_detail = "No se pudo registrar la consulta financiera. Intentá nuevamente."
    default_code = "auditoria_financiera_no_disponible"


class AuditaLecturaFinanciera:
    def list(self, request, *args, **kwargs):
        return self.auditar_respuesta(super().list(request, *args, **kwargs))

    def retrieve(self, request, *args, **kwargs):
        return self.auditar_respuesta(super().retrieve(request, *args, **kwargs))

    def auditar_respuesta(self, respuesta, contexto=None):
        """Usa la página ya autorizada/serializada, no repite la consulta de datos."""
        try:
            datos = respuesta.data
            filas = datos.get("results", [datos]) if isinstance(datos, dict) else datos
            periodo = datos.get("periodo_economico") if isinstance(datos, dict) else None
            if contexto is not None:
                grupos = {(contexto.institucion_id, contexto.area_id, contexto.sensible, periodo): len(filas)}
            else:
                grupos = Counter(
                    (fila["institucion"], fila.get("area"), fila["sensible"], fila.get("periodo_economico", periodo))
                    for fila in filas
                )
            if not grupos:
                # Sin filas no se inventa área/sensibilidad desde filtros del usuario.
                grupos = {(_institucion_del_pedido(self.request), None, False, periodo): 0}
            objeto_id = None
            if contexto is not None:
                objeto_id = contexto.pk
            elif self.action == "retrieve":
                objeto_id = datos["id"]
            with transaction.atomic():
                for (institucion_id, area_id, sensible, mes), cantidad in grupos.items():
                    AccesoFinanciero.objects.create(
                        usuario=self.request.user, institucion_id=institucion_id,
                        area_id=area_id, sensible=sensible,
                        recurso=self.queryset.model._meta.model_name, accion=self.action,
                        objeto_id=objeto_id, periodo_economico=mes, resultados=cantidad,
                    )
        except Exception as error:
            # No imprimir excepción/payload: podrían contener datos financieros.
            log.error("No se pudo persistir la auditoría financiera (%s).", type(error).__name__)
            raise AuditoriaFinancieraNoDisponible() from error
        return respuesta
