"""Carga idempotente del diccionario de códigos OSTEL para un financiador."""
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.financiadores.diccionario import MAX_BYTES, cargar_codigos, leer_diccionario_ostel
from apps.financiadores.models import Financiador


class Command(BaseCommand):
    help = ("Crea o actualiza los códigos del diccionario OSTEL (xlsx) para un financiador. "
            "No borra códigos ausentes ni asigna parentescos o familias.")

    def add_arguments(self, parser):
        parser.add_argument("archivo", help="Ruta del XLSX del diccionario de códigos.")
        parser.add_argument("--financiador", type=int, required=True, help="ID del financiador.")

    def handle(self, *args, archivo, financiador, **opciones):
        financiador_obj = Financiador.objects.filter(pk=financiador).first()
        if financiador_obj is None:
            raise CommandError("El financiador no existe.")
        ruta = Path(archivo)
        if not ruta.is_file() or ruta.stat().st_size > MAX_BYTES:
            raise CommandError("El archivo no existe o supera 5 MiB.")
        try:
            codigos, omitidas = leer_diccionario_ostel(ruta.read_bytes())
            resultado = {**cargar_codigos(financiador_obj, codigos), "filas_sin_codigo": omitidas}
        except ValidationError as exc:
            raise CommandError(" ".join(exc.messages)) from None
        self.stdout.write(", ".join(f"{k}: {v}" for k, v in resultado.items()))
