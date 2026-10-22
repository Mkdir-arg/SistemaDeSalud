"""Dueño autoritativo de adjuntos clínicos (#172, AUD-050).

El backfill solo asocia lo inequívoco: metadata que ya dice Estudio=<id>, un
único estudio que usa esa ruta y la misma institución del paciente. Todo lo
demás queda sin dueño y oculto del portal hasta que un admin lo confirme. No se
infiere pertenencia por ruta ni por nombre.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.utils import timezone


def asociar_inequivocos(apps, schema_editor):
    ArchivoClinico = apps.get_model("registros", "ArchivoClinico")
    Estudio = apps.get_model("registros", "Estudio")
    ahora = timezone.now()
    candidatos = ArchivoClinico.objects.filter(
        objeto_tipo="Estudio", objeto_id__isnull=False, asociado_at__isnull=True,
    ).exclude(proposito="consentimiento")
    for meta in candidatos.iterator():
        usos = list(Estudio.objects.filter(archivo=meta.ruta).values(
            "pk", "historia__ciudadano_id", "historia__ciudadano__institucion_id",
        )[:2])
        if (len(usos) != 1 or usos[0]["pk"] != meta.objeto_id
                or usos[0]["historia__ciudadano__institucion_id"] != meta.institucion_id):
            continue
        meta.ciudadano_id = usos[0]["historia__ciudadano_id"]
        meta.proposito = "estudio"
        meta.asociado_at = ahora
        meta.save(update_fields=["ciudadano", "proposito", "asociado_at"])


class Migration(migrations.Migration):

    dependencies = [
        ('registros', '0011_consentimientodatos_consentimiento_referido_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='archivoclinico',
            name='asociado_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='archivoclinico',
            name='asociado_por',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='archivos_clinicos_asociados', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='archivoclinico',
            name='ciudadano',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='archivos_clinicos', to='registros.ciudadano'),
        ),
        # Reversa: las columnas se retiran con los AddField; no hay datos que restaurar.
        migrations.RunPython(asociar_inequivocos, migrations.RunPython.noop),
    ]
