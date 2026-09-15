from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("finanzas", "0020_expectativa_monto_referencia")]
    operations = [migrations.CreateModel(
        name="TrabajoReparto",
        fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("revision", models.PositiveBigIntegerField(default=1)),
            ("revision_procesada", models.PositiveBigIntegerField(default=0)),
            ("solicitado_en", models.DateTimeField(auto_now_add=True)),
            ("procesado_en", models.DateTimeField(null=True)),
            ("iniciado_en", models.DateTimeField(null=True)),
            ("reserva", models.UUIDField(null=True)),
            ("intentos", models.PositiveIntegerField(default=0)),
            ("reintentar_en", models.DateTimeField()),
            ("ultimo_error", models.CharField(blank=True, max_length=200)),
            ("gasto", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="trabajo_reparto", to="finanzas.gasto")),
        ],
        options={"indexes": [models.Index(fields=["reintentar_en"], name="reparto_reintento_idx")]},
    )]
