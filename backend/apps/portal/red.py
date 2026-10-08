"""
La persona del portal en toda la red de HEN (#121).

`Ciudadano` es por institución: la misma persona tiene un registro en cada
hospital donde la atendieron. Acá se juntan por el documento validado con
RENAPER, en TODAS las instituciones (decisión del 08/10/2026, no sólo las de una
`Red`).

R1: entra un `Ciudadano` sólo si su documento coincide con el validado. Nunca
los NN ni los vacíos. Se descarta el que tiene fecha de nacimiento cargada y
distinta a la de RENAPER: es un DNI mal tipeado en algún hospital, y mostrarlo
le daría a esta persona los datos de otra.
"""
import re
from dataclasses import dataclass, field

from apps.registros.models import DOCUMENTOS_NN, Ciudadano

from .models import EventoPortal


def patron_documento(documento):
    """Regex del documento con o sin ceros a la izquierda.

    La cuenta lo guarda sin ceros y `Ciudadano` tal como se cargó: «08123456» y
    «8123456» son el mismo DNI. Devuelve None si no hay nada que buscar.
    """
    documento = (documento or "").lstrip("0")
    if not documento or documento in DOCUMENTOS_NN:
        return None
    return rf"^0*{re.escape(documento)}$"


@dataclass
class Persona:
    ciudadanos: list = field(default_factory=list)
    # Ids con el mismo documento y otra fecha de nacimiento.
    descartados: set = field(default_factory=set)

    @property
    def ids(self):
        return [c.pk for c in self.ciudadanos]


def persona_de(cuenta):
    """Los `Ciudadano` de la cuenta en toda la red, y los descartados por R1.

    Cada descarte nuevo queda en `EventoPortal`, una sola vez por ciudadano: la
    app consulta el llamado cada 5 segundos y un evento por consulta taparía
    todo lo demás.
    """
    patron = patron_documento(cuenta.documento)
    if patron is None or not cuenta.validada:
        return Persona()
    persona = Persona()
    for c in Ciudadano.objects.filter(documento__regex=patron).select_related("institucion").order_by("id"):
        if cuenta.fecha_nacimiento and c.fecha_nacimiento and c.fecha_nacimiento != cuenta.fecha_nacimiento:
            persona.descartados.add(c.pk)
        else:
            persona.ciudadanos.append(c)
    if persona.descartados:
        _auditar_descartes(cuenta, persona.descartados)
    return persona


def _auditar_descartes(cuenta, descartados):
    ya = {
        (e.get("ciudadano") if isinstance(e, dict) else None)
        for e in EventoPortal.objects.filter(
            cuenta=cuenta, tipo=EventoPortal.Tipo.DESCARTE_POR_NACIMIENTO,
        ).values_list("detalle", flat=True)
    }
    nuevos = sorted(set(descartados) - ya)
    if not nuevos:
        return
    instituciones = dict(Ciudadano.objects.filter(pk__in=nuevos).values_list("pk", "institucion_id"))
    # Sin nombres ni fechas: el registro descartado puede ser de otra persona.
    EventoPortal.objects.bulk_create([
        EventoPortal(
            tipo=EventoPortal.Tipo.DESCARTE_POR_NACIMIENTO, cuenta=cuenta, email=cuenta.email,
            detalle={"ciudadano": pk, "institucion": instituciones.get(pk)},
        )
        for pk in nuevos
    ])
