"""Preflight sin limpieza y unicidad de stock incluyendo lote NULL."""
from django.db import migrations, models
from django.db.models import Count


def verificar_existencias_unicas(apps, schema_editor):
    conexion = schema_editor.connection
    existencia = apps.get_model("farmacia", "Existencia")
    # El mismo lock de DDL se toma antes de inspeccionar: ningún escritor puede
    # introducir duplicados entre el diagnóstico y la creación del constraint.
    tabla = schema_editor.quote_name(existencia._meta.db_table)
    if conexion.vendor == "postgresql":
        schema_editor.execute(f"LOCK TABLE {tabla} IN ACCESS EXCLUSIVE MODE")
    # SQLite admite el índice parcial y conserva además unique_together.
    # Su validación funcional queda separada del laboratorio PostgreSQL.
    duplicados = (
        existencia.objects.using(conexion.alias).order_by()
        .values("deposito_id", "insumo_id", "lote_id")
        .annotate(filas=Count("pk")).filter(filas__gt=1)
    )
    if duplicados.exists():
        raise RuntimeError(
            "AUD-013: existen existencias duplicadas. Migración detenida sin modificar stock; "
            "se requiere diagnóstico y resolución manual autorizada."
        )


class Migration(migrations.Migration):
    atomic = True
    dependencies = [("farmacia", "0003_proteger_depositos_de_pedidos")]

    operations = [
        migrations.RunPython(verificar_existencias_unicas, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="existencia",
            constraint=models.UniqueConstraint(
                fields=("deposito", "insumo"),
                condition=models.Q(lote__isnull=True),
                name="farmacia_existencia_unica_sin_lote",
            ),
        ),
    ]
