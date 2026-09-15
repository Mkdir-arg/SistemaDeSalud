from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("finanzas", "0019_repartogasto_actividad_incompleta")]

    operations = [
        migrations.AddField(
            model_name="expectativagasto", name="monto_referencia",
            field=models.DecimalField(blank=True, null=True, max_digits=18, decimal_places=2),
        ),
        migrations.AddConstraint(
            model_name="expectativagasto",
            constraint=models.CheckConstraint(
                condition=models.Q(monto_referencia__isnull=True) | models.Q(monto_referencia__gte=0),
                name="referencia_expectativa_no_negativa",
            ),
        ),
    ]
