from django.db import migrations


class Migration(migrations.Migration):
    # Las ramas modifican modelos distintos; conservar ambas historias aplicadas.
    dependencies = [
        ("financiadores", "0013_administrativa_cobertura"),
        ("financiadores", "0013_baja_membresia_financiador"),
    ]

    operations = []
