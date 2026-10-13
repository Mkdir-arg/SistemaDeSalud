"""
Las cuentas de referencia pasan de `referencia.hen.invalid` a
`referencia.plexo.invalid` (docs/NOMBRE-DEL-SISTEMA.md).

Siguen funcionando sin esto, porque se reconocen por `CuentaReferencia`. Se
migran igual para que `perfiles.email_canonico` y los filtros por dominio
(listados de usuarios, alta de usuarios del financiador) vean un único dominio.
"""

from django.db import migrations
from django.db.models import Value
from django.db.models.functions import Replace

ANTERIOR = "@referencia.hen.invalid"
NUEVO = "@referencia.plexo.invalid"


def cambiar(desde, hacia):
    def migrar(apps, schema_editor):
        Usuario = apps.get_model("accounts", "Usuario")
        Usuario.objects.filter(email__endswith=desde).update(email=Replace("email", Value(desde), Value(hacia)))
    return migrar


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0006_membresia_estatal_global"),
        ("simulacion", "0002_cuenta_estatal_global"),
    ]

    operations = [migrations.RunPython(cambiar(ANTERIOR, NUEVO), cambiar(NUEVO, ANTERIOR))]
