from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("financiadores", "0016_afiliado_geografia_afiliado_geografia_laboral"),
    ]

    operations = [
        migrations.AddField(
            model_name="saludpadron",
            name="codpar_ostel",
            field=models.CharField(blank=True, db_default="", default="", max_length=40),
        ),
    ]
