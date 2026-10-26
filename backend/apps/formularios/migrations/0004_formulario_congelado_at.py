"""Marca definiciones históricas usadas sin tocar campos ni respuestas.

La marca registra el momento del backfill, no inventa una fecha de publicación.
Aplicar con escritores detenidos; revertir el campo pierde esta protección.
"""
from django.db import migrations, models
from django.utils import timezone


def _entero(valor):
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


def congelar_legacy(apps, schema_editor):
    alias = schema_editor.connection.alias
    formulario = apps.get_model("formularios", "Formulario")
    campo = apps.get_model("formularios", "Campo")
    nodo = apps.get_model("flujos", "Nodo")
    conexion = apps.get_model("flujos", "Conexion")
    valor = apps.get_model("casos", "ValorCampo")
    formularios, campos = set(), set(valor.objects.using(alias).values_list("campo_id", flat=True))
    for formulario_id, config in nodo.objects.using(alias).exclude(version__estado="borrador").values_list("formulario_id", "config").iterator():
        if formulario_id is not None:
            formularios.add(formulario_id)
        if isinstance(config, dict):
            for clave in ("guardar_en", "prioridad_campo"):
                pk = _entero(config.get(clave))
                if pk:
                    campos.add(pk)
    for condicion in conexion.objects.using(alias).exclude(version__estado="borrador").values_list("condicion", flat=True).iterator():
        campos.update(_campos_condicion(condicion))
    formularios.update(campo.objects.using(alias).filter(pk__in=campos).values_list("formulario_id", flat=True))
    formulario.objects.using(alias).filter(pk__in=formularios, congelado_at__isnull=True).update(congelado_at=timezone.now())


class Migration(migrations.Migration):
    dependencies = [
        ("formularios", "0003_alter_campo_tipo"),
        ("flujos", "0008_versionflujo_tipo_circuito"),
        ("casos", "0014_caso_espera_autorizacion"),
    ]
    operations = [
        migrations.AddField(
            model_name="formulario",
            name="congelado_at",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.RunPython(congelar_legacy, migrations.RunPython.noop),
    ]
