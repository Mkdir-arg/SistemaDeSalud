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
relativas al momento de la carga (ver `apps.demo.calendario`), y lo pendiente
—casos abiertos, autorizaciones con 48 h de plazo, pacientes en la sala de
espera— es de las últimas horas antes de ese momento.

`--ancla` corre la carga como si ocurriera en otro momento: todo el reloj de la
carga se desplaza hasta ahí. Sirve para cargar días antes una demo que tiene
que verse recién cargada a una hora fija. Hasta que llega el ancla, la
aplicación muestra datos con fecha futura; y lo que se opere antes queda con la
hora real, anterior a esos datos: después de ensayar, se vuelve a cargar con la
misma ancla.

    python manage.py seed_entorno_demo            # pide confirmación
    python manage.py seed_entorno_demo --noinput  # sin preguntar (Railway, CI)
    python manage.py seed_entorno_demo --noinput --ancla 2026-10-01T08:00
"""
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone

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
        parser.add_argument("--ancla", default=None,
                            help="Momento en que la carga tiene que parecer recién hecha, en hora local "
                                 "(AAAA-MM-DDTHH:MM). Por defecto, ahora.")

    def handle(self, *args, **opciones):
        exigir_entorno_de_prueba("seed_entorno_demo")
        if connection.vendor != "postgresql":
            raise CommandError("La carga requiere PostgreSQL.")
        base = connection.settings_dict.get("NAME")
        ancla = self._ancla(opciones["ancla"])
        if opciones["interactive"]:
            respuesta = input(f"Esto BORRA todos los datos de la base «{base}» y carga la demo. "
                              "Escribí «vaciar» para seguir: ")
            if respuesta.strip().lower() != "vaciar":
                raise CommandError("Cancelado. No se modificó ningún dato.")

        inicio = time.monotonic()
        with self._reloj_en(ancla):
            self._cargar(base, opciones)
            self.stdout.write(self.style.SUCCESS(f"\nEntorno de demo cargado en {time.monotonic() - inicio:.0f} s.\n"))
            self._resumen()
        if ancla:
            self.stdout.write(self.style.WARNING(
                f"\nCarga anclada en {ancla:%d/%m/%Y %H:%M}. Hasta esa hora la aplicación muestra datos con "
                "fecha futura, y lo que se opere antes queda desordenado respecto de ellos: si ensayás, "
                "volvé a cargar con la misma ancla. Las autorizaciones abiertas vencen unas 48 h después."
            ))

    def _ancla(self, texto):
        if not texto:
            return None
        try:
            ancla = datetime.fromisoformat(texto)
        except ValueError as error:
            raise CommandError(f"--ancla {texto!r} no es una fecha y hora válida (AAAA-MM-DDTHH:MM).") from error
        return timezone.make_aware(ancla) if timezone.is_naive(ancla) else ancla

    @contextmanager
    def _reloj_en(self, ancla):
        """El reloj de la carga: arranca en el ancla (o ahora) y avanza sin volver atrás.

        El sellado de la historia clínica busca la última entrada firmada por su
        hora de firma. La carga firma cientos de entradas por segundo, y el reloj
        de pared puede retroceder unos milisegundos cuando el sistema corrige la
        hora: dos entradas del mismo paciente elegían entonces el mismo eslabón
        previo, y la base rechazaba la cadena bifurcada. Por eso el reloj sale de
        `time.monotonic()`, que nunca retrocede. Tampoco se congela en un
        instante: con todas las firmas a la misma hora pasaría lo mismo por
        empate. Adentro, `Calendario.sintetica` sigue fijando sus instantes.
        """
        base = ancla or timezone.now()
        inicio = time.monotonic()
        with patch("django.utils.timezone.now",
                   side_effect=lambda: base + timedelta(seconds=time.monotonic() - inicio)):
            yield

    def _cargar(self, base, opciones):
        with transaction.atomic():
            self.stdout.write(f"Vaciando «{base}»…")
            call_command("flush", interactive=False, verbosity=0)
            for comando, parametros in pasos(opciones["dias"], opciones["casos"]):
                t0 = time.monotonic()
                self.stdout.write(f"  {comando}…", ending="")
                self.stdout.flush()
                salida, avisos = StringIO(), StringIO()
                try:
                    call_command(comando, stdout=salida, stderr=avisos, **parametros)
                except Exception as error:
                    raise CommandError(f"{comando} falló y se revirtió toda la carga: {error}") from error
                # Los pasos anotan en stderr lo que no pudieron hacer y siguen (un
                # consultorio ocupado, un caso que no se pudo llamar). No frena la
                # carga, pero no puede quedar invisible.
                lineas = [linea for linea in avisos.getvalue().splitlines() if linea.strip()]
                nota = f" · {len(lineas)} avisos" if lineas else ""
                self.stdout.write(f" {time.monotonic() - t0:.0f} s{nota}")
                for linea in lineas:
                    if "trabajo para" in linea:
                        self.stdout.write(self.style.WARNING(f"    {linea.strip()}"))

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
