"""Crea la tabla del cache `portal` (los contadores de intentos).

Va como migración y no como paso del despliegue para que exista en cualquier
base que haya corrido `migrate`: la de compose, la de un desarrollador y la de
las pruebas. Sin la tabla, el primer ingreso al portal da 500.
"""
from django.core.management import call_command
from django.db import migrations


def crear_tabla(apps, schema_editor):
    call_command("createcachetable", "portal_cache", database=schema_editor.connection.alias, verbosity=0)


class Migration(migrations.Migration):
    dependencies = [("portal", "0001_initial")]

    operations = [migrations.RunPython(crear_tabla, migrations.RunPython.noop)]
