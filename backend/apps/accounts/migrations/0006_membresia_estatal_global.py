from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0005_alter_membresia_rol"),
    ]

    operations = [
        migrations.AlterField(
            model_name="membresia",
            name="institucion",
            field=models.ForeignKey(
                to="instituciones.institucion", on_delete=models.CASCADE,
                related_name="membresias", null=True, blank=True,
            ),
        ),
        migrations.AddConstraint(
            model_name="membresia",
            constraint=models.CheckConstraint(
                condition=Q(institucion__isnull=False) | Q(rol__in=["plataforma", "auditor"]),
                name="accounts_membresia_global_solo_estatal",
            ),
        ),
        migrations.AddConstraint(
            model_name="membresia",
            constraint=models.UniqueConstraint(
                fields=["usuario", "rol"], condition=Q(institucion__isnull=True),
                name="accounts_membresia_global_unica",
            ),
        ),
    ]
