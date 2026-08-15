"""
Deja los documentos ya cargados en el mismo formato con el que ahora se comparan.

Sin este paso, la normalización nueva sólo protege a los pacientes que se
carguen de hoy en adelante: un «30.111.222» ya guardado sigue siendo invisible
para el alta de «30111222», que es exactamente el duplicado que se está tratando
de evitar.

Los que al normalizarse chocarían con otro de la misma institución se dejan como
están: ése es un paciente que YA tiene dos historias paralelas, el sistema no las
puede fusionar y hacer fallar la migración dejaría la instalación sin arrancar.
Queda como estaba, visible, para que alguien lo resuelva a mano.
"""
import re

from django.db import migrations

_SEPARADORES = re.compile(r"[^0-9A-Za-z]")


def normalizar(apps, schema_editor):
    Ciudadano = apps.get_model("registros", "Ciudadano")
    tomados = set(
        Ciudadano.objects.exclude(documento="").values_list("institucion_id", "documento")
    )
    for c in Ciudadano.objects.exclude(documento=""):
        nuevo = _SEPARADORES.sub("", c.documento).upper()
        if nuevo == c.documento:
            continue
        if (c.institucion_id, nuevo) in tomados:
            continue
        tomados.discard((c.institucion_id, c.documento))
        tomados.add((c.institucion_id, nuevo))
        c.documento = nuevo
        c.save(update_fields=["documento"])


def atras(apps, schema_editor):
    # No se puede reconstruir dónde iban los puntos, y tampoco hace falta: el
    # valor sin puntos identifica igual a la persona.
    pass


class Migration(migrations.Migration):

    dependencies = [("registros", "0007_historiaclinica_antecedentes_at_and_more")]

    operations = [migrations.RunPython(normalizar, atras)]
