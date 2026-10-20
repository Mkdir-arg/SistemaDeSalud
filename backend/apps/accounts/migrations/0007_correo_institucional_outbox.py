from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0006_membresia_estatal_global")]

    operations = [
        migrations.CreateModel(
            name="CorreoInstitucionalOutbox",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("solicitud", models.JSONField(default=dict)),
                ("estado", models.CharField(choices=[("pendiente", "Pendiente"), ("procesando", "Procesando"), ("enviado", "Aceptado por backend de correo"), ("descartado", "Descartado"), ("error", "Error definitivo")], default="pendiente", max_length=12)),
                ("creado", models.DateTimeField(auto_now_add=True)),
                ("vence", models.DateTimeField()),
                ("disponible_en", models.DateTimeField()),
                ("reserva", models.UUIDField(blank=True, null=True)),
                ("reservado_hasta", models.DateTimeField(blank=True, null=True)),
                ("intentos", models.PositiveIntegerField(default=0)),
                ("terminado_en", models.DateTimeField(blank=True, null=True)),
                ("resultado", models.CharField(blank=True, max_length=40)),
            ],
            options={
                "ordering": ["id"],
                "indexes": [
                    models.Index(fields=["estado", "disponible_en"], name="accounts_correo_listo_idx"),
                    models.Index(fields=["estado", "reservado_hasta"], name="accounts_correo_lease_idx"),
                ],
            },
        ),
    ]
