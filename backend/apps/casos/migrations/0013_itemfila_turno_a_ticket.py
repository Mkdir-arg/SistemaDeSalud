"""
`ItemFila.turno` pasa a llamarse `ticket`.

Es un número de ticket de fila («A-042»), no un turno agendado. Con la agenda de
turnos de por medio, dos cosas muy distintas compartían nombre en la misma
pantalla.

Se escribe a mano con `RenameField` a propósito: `makemigrations` no puede
deducir un rename sin preguntar, y contestándole que no genera un borrar +
crear que se lleva puestos todos los tickets existentes.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("casos", "0012_alter_valorcampo_options"),
    ]

    operations = [
        migrations.RenameField(
            model_name="itemfila",
            old_name="turno",
            new_name="ticket",
        ),
    ]
