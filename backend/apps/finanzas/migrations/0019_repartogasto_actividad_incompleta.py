from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("finanzas", "0018_alter_concesionfinanciera_accion_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="repartogasto",
            name="motivo",
            field=models.CharField(
                blank=True,
                choices=[
                    ("sin_regla", "Sin regla aplicable"),
                    ("sin_cobertura", "Sin cobertura acreditada"),
                    ("actividad_incompleta", "Actividad técnicamente incompleta"),
                    ("fuente_no_elegible", "Fuente no elegible"),
                ],
                max_length=30,
            ),
        ),
    ]

