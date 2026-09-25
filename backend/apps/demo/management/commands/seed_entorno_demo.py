"""Vacía la base y carga el entorno de demostración completo, siempre igual.

Es el único comando que conoce el orden entre los `seed_*`. Cada uno carga una
sola cosa y declara lo que necesita; este los encadena:

    1. seed_los_aromos     finanzas y costos de un hospital (12 meses)
    2. seed_financiadores  obras sociales, padrón y autorizaciones sobre ese hospital
    3. seed_guardia        estructura de Hospital Central: áreas, staff, flujos, farmacia, agendas
    4. seed_volumen        pacientes, casos y turnos de Hospital Central (365 días)
    5. seed_roles          gobierno estatal y administración de Hospital Central
    6. seed_farmacia       pedidos de reposición y consumos imputados a pacientes
    7. seed_red            un segundo hospital y los traslados entre los dos
    8. seed_accesos        el historial de accesos que revisa la auditoría

Todo corre en UNA transacción, vaciado incluido: si un paso falla, la base
queda como estaba y no a medio cargar. Mientras corre, la aplicación espera:
el vaciado bloquea todas las tablas hasta el final (entre 5 y 7 minutos).

Requiere PostgreSQL y `ENTORNO` distinto de `produccion`. Las fechas son
relativas al momento de la carga (ver `apps.demo.calendario`): conviene
correrlo el mismo día de la demo, porque lo pendiente —casos abiertos,
autorizaciones con 48 h de plazo, pacientes en la sala de espera— es de las
últimas horas.

    python manage.py seed_entorno_demo            # pide confirmación
    python manage.py seed_entorno_demo --noinput  # sin preguntar (Railway, CI)
"""
import time
from io import StringIO

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from apps.demo.claves import CLAVE_POR_DEFECTO, usa_clave_por_defecto
from apps.demo.entorno import exigir_entorno_de_prueba
from apps.demo.trabajo import INFORMATIVOS, trabajo_por_usuario


def pasos(dias, casos):
    return [
        ("seed_los_aromos", {}),
        ("seed_financiadores", {}),
        ("seed_guardia", {}),
        ("seed_volumen", {"dias": dias, "casos": casos}),
        ("seed_roles", {}),
        ("seed_farmacia", {}),
        ("seed_red", {}),
        ("seed_accesos", {}),
    ]


class Command(BaseCommand):
    help = "Vacía la base y carga el entorno de demostración completo."

    def add_arguments(self, parser):
        parser.add_argument("--noinput", "--no-input", action="store_false", dest="interactive",
                            help="No pedir confirmación.")
        parser.add_argument("--dias", type=int, default=365, help="Historia clínica hacia atrás (por defecto 365).")
        parser.add_argument("--casos", type=int, default=1200,
                            help="Casos históricos de guardia en esa ventana (por defecto 1200).")

    def handle(self, *args, **opciones):
        exigir_entorno_de_prueba("seed_entorno_demo")
        if connection.vendor != "postgresql":
            raise CommandError("La carga requiere PostgreSQL.")
        base = connection.settings_dict.get("NAME")
        if opciones["interactive"]:
            respuesta = input(f"Esto BORRA todos los datos de la base «{base}» y carga la demo. "
                              "Escribí «vaciar» para seguir: ")
            if respuesta.strip().lower() != "vaciar":
                raise CommandError("Cancelado. No se modificó ningún dato.")

        inicio = time.monotonic()
        with transaction.atomic():
            self.stdout.write(f"Vaciando «{base}»…")
            call_command("flush", interactive=False, verbosity=0)
            for comando, parametros in pasos(opciones["dias"], opciones["casos"]):
                t0 = time.monotonic()
                self.stdout.write(f"  {comando}…", ending="")
                self.stdout.flush()
                salida = StringIO()
                try:
                    call_command(comando, stdout=salida, stderr=StringIO(), **parametros)
                except Exception as error:
                    raise CommandError(f"{comando} falló y se revirtió toda la carga: {error}") from error
                self.stdout.write(f" {time.monotonic() - t0:.0f} s")

        self.stdout.write(self.style.SUCCESS(f"\nEntorno de demo cargado en {time.monotonic() - inicio:.0f} s.\n"))
        self._resumen()

    def _resumen(self):
        filas = trabajo_por_usuario()
        ancho = max(len(f["email"]) for f in filas)
        self.stdout.write("Usuarios, perfil y lo que encuentra cada uno al entrar:\n")
        for f in filas:
            trabajo = " · ".join(f"{n} {que}" for que, n in f["trabajo"].items()) or "—"
            self.stdout.write(f"  {f['email']:<{ancho}}  {f['perfil']:<24} {f['donde']:<34} {trabajo}")
        sin_trabajo = [f for f in filas if not f["consulta"] and not set(f["trabajo"]) - INFORMATIVOS]
        if sin_trabajo:
            self.stdout.write(self.style.WARNING(
                "\nSin trabajo pendiente: " + ", ".join(f"{f['email']} ({f['perfil']})" for f in sin_trabajo)
            ))
        if usa_clave_por_defecto():
            self.stdout.write(self.style.WARNING(
                f"\nDEMO_PASSWORD no está definida: todos los usuarios quedaron con la clave «{CLAVE_POR_DEFECTO}», "
                "que está publicada en el repositorio. En un entorno accesible desde internet, definila."
            ))
        else:
            self.stdout.write("\nTodos los usuarios usan la clave de DEMO_PASSWORD.")
