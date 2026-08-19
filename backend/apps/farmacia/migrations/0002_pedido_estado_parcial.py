from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("farmacia", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="pedido",
            name="estado",
            field=models.CharField(
                choices=[
                    ("pendiente", "Pendiente"),
                    ("preparado", "Preparado"),
                    ("parcial", "Parcial"),
                    ("entregado", "Entregado"),
                    ("rechazado", "Rechazado"),
                ],
                default="pendiente",
                max_length=20,
            ),
        ),
    ]
