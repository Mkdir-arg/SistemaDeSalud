from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("registros", "0002_estudio_realizado"),
    ]

    operations = [
        migrations.AddField(
            model_name="entradahistoria",
            name="matricula",
            field=models.CharField(blank=True, max_length=60, verbose_name="matrícula"),
        ),
    ]
