from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("flujos", "0003_nodo_grupos"),
    ]

    operations = [
        migrations.AddField(
            model_name="nodo",
            name="pantalla_token",
            field=models.CharField(blank=True, db_index=True, default="", max_length=32),
        ),
    ]
