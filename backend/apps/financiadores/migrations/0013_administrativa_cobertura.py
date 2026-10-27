from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("financiadores", "0012_padron_legacy_db_defaults")]

    operations = [
        migrations.AddField(
            model_name="afiliado", name="cobertura_habilitada",
            field=models.BooleanField(default=True, db_default=True),
        ),
        migrations.AddField(
            model_name="afiliado", name="numero_interno",
            field=models.CharField(max_length=80, blank=True, default="", db_default=""),
        ),
        migrations.AddConstraint(
            model_name="afiliado",
            constraint=models.UniqueConstraint(
                fields=("financiador", "numero_interno"),
                condition=~models.Q(numero_interno=""), name="fin_afiliado_numero_interno",
            ),
        ),
    ]
