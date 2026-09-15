import uuid

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("finanzas", "0022_dinero"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="PoliticaCobro",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nodo_origen_id", models.PositiveBigIntegerField()),
                ("nombre_prestacion", models.CharField(max_length=160)),
                ("cobrar", models.BooleanField(default=False)),
                ("importe", models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True)),
                ("contraparte_nombre", models.CharField(blank=True, max_length=160)),
                ("contraparte_referencia", models.CharField(blank=True, max_length=160)),
                ("sensible", models.BooleanField(default=False)),
                ("vigente_desde", models.DateTimeField(default=django.utils.timezone.now)),
                ("registrado", models.DateTimeField(auto_now_add=True)),
                ("registrado_por", models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ("institucion", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="instituciones.institucion")),
                ("prestacion", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="finanzas.prestacion")),
            ],
            options={"ordering": ["-vigente_desde", "-id"], "constraints": [models.CheckConstraint(condition=models.Q(importe__isnull=True) | models.Q(importe__gt=0), name="cobro_arancel_positivo")]},
        ),
        migrations.CreateModel(
            name="SnapshotCobroAtencion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("capturado", models.BooleanField(default=False)),
                ("creado", models.DateTimeField(auto_now_add=True)),
                ("hecho", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="snapshot_cobro", to="finanzas.hechoatencioncosteable")),
            ],
        ),
        migrations.CreateModel(
            name="PendienteCobro",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sensible", models.BooleanField(default=False)),
                ("importe", models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True)),
                ("contraparte_nombre", models.CharField(blank=True, max_length=160)),
                ("contraparte_referencia", models.CharField(blank=True, max_length=160)),
                ("clave", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("creado", models.DateTimeField(auto_now_add=True)),
                ("resuelto_en", models.DateTimeField(blank=True, null=True)),
                ("area", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to="instituciones.area")),
                ("hecho", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="pendientes_cobro", to="finanzas.hechoatencioncosteable")),
                ("institucion", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="instituciones.institucion")),
                ("obligacion", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to="finanzas.obligacionfinanciera")),
                ("politica", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="finanzas.politicacobro")),
                ("prestacion", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="finanzas.prestacion")),
                ("resuelto_por", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-id"], "constraints": [models.UniqueConstraint(fields=("hecho", "prestacion"), name="cargo_unico_hecho_prestacion")]},
        ),
    ]
