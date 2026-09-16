"""Diagnóstico operativo no mutante; reporte optativo sin identificadores personales."""
from contextlib import nullcontext
import json
import os
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.instituciones.models import Institucion
from apps.registros.models import Ciudadano
from apps.financiadores.legado import (
    CLASIFICACIONES, CRITERIO, diagnosticar, huella_aliases, validar_aliases,
)


REPOSITORIO = Path(__file__).resolve().parents[5]


def _objeto_sin_repetidos(pares):
    datos = {}
    for clave, valor in pares:
        if clave in datos:
            raise ValueError("Claves JSON repetidas.")
        datos[clave] = valor
    return datos


def _abrir_reporte(ruta):
    destino = Path(ruta).expanduser().resolve()
    if destino == REPOSITORIO or REPOSITORIO in destino.parents:
        raise CommandError("Elegí una ruta privada fuera del repositorio para el reporte.")
    try:
        # O_EXCL impide pisar archivos, incluso ante ejecuciones concurrentes.
        # En Windows el operador debe elegir una carpeta con ACL privada; 0600
        # protege el archivo en los sistemas POSIX y no sustituye esas ACL.
        descriptor = os.open(destino, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        return os.fdopen(descriptor, "w", encoding="utf-8", newline="\n")
    except OSError:
        raise CommandError("No se pudo crear el reporte exclusivo; revisá ruta, permisos o si ya existe.") from None


class Command(BaseCommand):
    help = "Diagnostica coberturas legadas de una institución sin modificar datos."
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument("--institucion", type=int, required=True, help="ID del hospital a diagnosticar.")
        parser.add_argument("--lote", type=int, default=250, help="Ciudadanos por lote (1 a 500).")
        parser.add_argument("--aliases", help="JSON revisado: texto -> {financiador: ID, plan: ID opcional}.")
        parser.add_argument("--reporte", help="Archivo JSONL nuevo, en carpeta privada fuera del repositorio.")

    def handle(self, *args, **options):
        institucion_id = options["institucion"]
        if not Institucion.objects.filter(pk=institucion_id).exists():
            raise CommandError("La institución indicada no existe.")
        if not 1 <= options["lote"] <= 500:
            raise CommandError("El lote debe estar entre 1 y 500.")
        aliases = {}
        if options.get("aliases"):
            try:
                with Path(options["aliases"]).expanduser().open(encoding="utf-8-sig") as entrada:
                    datos = json.load(entrada, object_pairs_hook=_objeto_sin_repetidos)
                aliases = validar_aliases(datos)
            except (OSError, UnicodeError, ValueError):
                raise CommandError("No se pudo leer el JSON de alias; revisá el formato y las claves repetidas.") from None
            except ValidationError as error:
                raise CommandError(" ".join(error.messages)) from None
        corte = timezone.now()
        hasta_pk = Ciudadano.objects.filter(institucion_id=institucion_id).order_by("-pk").values_list("pk", flat=True).first() or 0
        metadatos = {
            "tipo": "metadatos", "version": 1, "criterio": CRITERIO,
            "institucion": institucion_id, "generado_en": corte.isoformat(),
            "fecha_padron": timezone.localdate(corte).isoformat(), "hasta_pk": hasta_pk,
            "aliases_sha256": huella_aliases(aliases), "solo_lectura": True,
            "instantanea_transaccional": False,
        }
        cantidades = dict.fromkeys(CLASIFICACIONES, 0)
        contexto = _abrir_reporte(options["reporte"]) if options.get("reporte") else nullcontext()
        with contexto as reporte:
            if reporte:
                reporte.write(json.dumps(metadatos, ensure_ascii=False) + "\n")
            for registro in diagnosticar(
                institucion_id=institucion_id, hasta_pk=hasta_pk, aliases=aliases,
                lote=options["lote"], corte=corte,
            ):
                cantidades[registro["clasificacion"]] += 1
                if reporte:
                    reporte.write(json.dumps({"tipo": "registro", **registro}, ensure_ascii=False) + "\n")
            resumen = {
                "tipo": "resumen", "institucion": institucion_id, "criterio": CRITERIO,
                "total": sum(cantidades.values()), "clasificaciones": cantidades,
                "reporte_generado": bool(reporte), "completo": True,
            }
            if reporte:
                reporte.write(json.dumps(resumen, ensure_ascii=False) + "\n")
        self.stdout.write(json.dumps(resumen, ensure_ascii=False))
