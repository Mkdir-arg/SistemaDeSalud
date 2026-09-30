from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0006_membresia_estatal_global"),
        ("simulacion", "0001_initial"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="cuentareferencia",
            name="simulacion_cuenta_ambito_valido",
        ),
        migrations.AddConstraint(
            model_name="cuentareferencia",
            constraint=models.CheckConstraint(
                condition=(
                    Q(ambito="financiador", financiador__isnull=False, institucion__isnull=True)
                    | Q(ambito="plataforma", financiador__isnull=True)
                    | Q(ambito="institucion", institucion__isnull=False, financiador__isnull=True)
                ),
                name="simulacion_cuenta_ambito_valido",
            ),
        ),
    ]
