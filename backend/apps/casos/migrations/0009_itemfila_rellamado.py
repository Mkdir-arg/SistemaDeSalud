from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("casos", "0008_itemfila_atendido_at_itemfila_llamado_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="itemfila",
            name="rellamado_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="rellamado"),
        ),
        migrations.AddField(
            model_name="itemfila",
            name="veces_llamado",
            field=models.PositiveIntegerField(default=1),
        ),
    ]
