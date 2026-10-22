import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("accounts", "0007_correo_institucional_outbox")]

    operations = [
        migrations.CreateModel(
            name="SesionInstitucional",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("creada", models.DateTimeField(auto_now_add=True)),
                ("revocada_at", models.DateTimeField(blank=True, null=True)),
                ("refresh_jti_hash", models.CharField(editable=False, max_length=64)),
                ("refresh_vence", models.DateTimeField()),
                ("usuario", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                    related_name="sesiones_institucionales", to=settings.AUTH_USER_MODEL)),
            ],
            options={"verbose_name": "sesión institucional", "verbose_name_plural": "sesiones institucionales"},
        ),
    ]
