"""Congelación durable de definiciones: Version/Caso → Formulario → Campo.

Los escritores llaman dentro de atomic y jamás toman Version después de Form.
El fallback focal cubre registros legacy directos; las referencias indirectas
se marcan por migración/publicación, sin volver a recorrer todo JSON al editar.
"""
from django.utils import timezone
from rest_framework.exceptions import APIException, NotFound

from .models import Campo, Formulario


class FormularioCongelado(APIException):
    status_code = 409
    default_detail = "La definición del formulario está congelada. Duplicalo para modificarla y asigná la copia manualmente."


def bloquear_formularios(ids):
    ids = {int(pk) for pk in ids if pk is not None}
    formularios = {form.pk: form for form in Formulario.objects.order_by("pk").select_for_update().filter(pk__in=ids)}
    if set(formularios) != ids:
        raise NotFound("Uno de los formularios ya no existe. Recargá antes de continuar.")
    return formularios


def congelar_formularios(ids):
    formularios = bloquear_formularios(ids)
    pendientes = [form.pk for form in formularios.values() if form.congelado_at is None]
    if pendientes:
        ahora = timezone.now()
        Formulario.objects.filter(pk__in=pendientes, congelado_at__isnull=True).update(congelado_at=ahora)
        for pk in pendientes:
            formularios[pk].congelado_at = ahora
    return formularios


def asegurar_congelados(ids):
    """Runtime: sólo bloquear definiciones cuya marca durable aún sea NULL.

    Los llamadores preparan el conjunto completo de la operación por PK antes
    de guardar valores o recorrer nodos automáticos. Una marca confirmada es
    indeleble por API/Admin: no vuelve a NULL y esa definición no se elimina.
    Por eso leerla fresh permite omitir locks sobre definiciones ya inmutables.
    No protege escrituras SQL/ORM privilegiadas que omitan esa invariante.
    """
    ids = {int(pk) for pk in ids if pk is not None}
    formularios = {form.pk: form for form in Formulario.objects.only("pk", "congelado_at").filter(pk__in=ids)}
    if set(formularios) != ids:
        raise NotFound("Uno de los formularios ya no existe. Recargá antes de continuar.")
    pendientes = [pk for pk, form in formularios.items() if form.congelado_at is None]
    if pendientes:
        formularios.update(congelar_formularios(pendientes))
    return formularios


def esta_congelado(formulario):
    if formulario.congelado_at is not None:
        return True
    return (formulario.nodos.exclude(version__estado="borrador").exists()
            or Campo.objects.filter(formulario_id=formulario.pk, valores__isnull=False).exists())


def exigir_editable(formulario, *, instancia=None, cambios=None):
    instancia = instancia if instancia is not None else formulario
    if cambios is not None and all(getattr(instancia, clave) == valor for clave, valor in cambios.items()):
        return
    if esta_congelado(formulario):
        raise FormularioCongelado()


def _entero(valor):
    # Equivalente a los IDs del motor: int acepta strings, bool y números.
    try:
        return int(valor)
    except (TypeError, ValueError, OverflowError):
        return None


def _campos_condicion(condicion):
    if not isinstance(condicion, dict) or not condicion:
        return set()
    if "reglas" in condicion:
        reglas = condicion.get("reglas")
        if not isinstance(reglas, list):
            return set()
        return {pk for regla in reglas for pk in _campos_condicion(regla)}
    pk = _entero(condicion.get("campo"))
    return {pk} if pk else set()


def ids_formularios_de_version(version_id):
    from apps.flujos.models import Conexion, Nodo

    formularios, campos = set(), set()
    for formulario_id, config in Nodo.objects.filter(version_id=version_id).values_list("formulario_id", "config"):
        if formulario_id is not None:
            formularios.add(formulario_id)
        if isinstance(config, dict):
            for clave in ("guardar_en", "prioridad_campo"):
                pk = _entero(config.get(clave))
                if pk:
                    campos.add(pk)
    for condicion in Conexion.objects.filter(version_id=version_id).values_list("condicion", flat=True):
        campos.update(_campos_condicion(condicion))
    formularios.update(Campo.objects.filter(pk__in=campos).values_list("formulario_id", flat=True))
    return formularios
