"""Conserva pedidos al eliminar sus depósitos mediante el ORM de Django."""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("farmacia", "0002_pedido_estado_parcial")]

    operations = [
        migrations.AlterField(
            model_name="pedido",
            name="origen",
            field=models.ForeignKey(
                help_text="Depósito que pide.",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="pedidos_hechos",
                to="farmacia.deposito",
            ),
        ),
        migrations.AlterField(
            model_name="pedido",
            name="destino",
            field=models.ForeignKey(
                help_text="Depósito al que se le pide (normalmente la central).",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="pedidos_recibidos",
                to="farmacia.deposito",
            ),
        ),
    ]
