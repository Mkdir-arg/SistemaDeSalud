"""El año económico de `seed_los_aromos`, dentro de Hospital Central.

Qué carga
---------
Hospital Central es el hospital con la operación clínica completa, y sin esto
tenía Finanzas vacía: quien recorre el sistema desde ahí no veía gastos, costos
ni cobros. Este comando carga el mismo escenario que Los Aromos —doce meses de
gastos con su reparto, costos por atención, cuentas, pagos y cobros, y lo
pendiente de cada rol— en tres servicios ambulatorios propios de Central.

Van en áreas nuevas y no en las de la guardia o las especialidades por la misma
razón que `seed_financiadores` usa un área propia: el reparto distribuye cada
gasto entre las atenciones elegibles de su área. En un área con cientos de
atenciones de otro circuito, las cifras del escenario dejarían de ser las que
se verifican al final de la carga.

La administración la llevan la dirección y el configurador de Central
(`seed_roles`), que suman estas áreas y los permisos de finanzas. Los
profesionales y la administrativa del escenario son personas nuevas.

Requisitos
----------
- PostgreSQL migrado y `ENTORNO` distinto de `produccion`.
- Hospital Central con su dirección y su configurador (`seed_guardia` y
  `seed_roles`).
- El escenario todavía no cargado en Central. Para rehacerlo se vacía la base
  con `seed_entorno_demo`.

    python manage.py seed_finanzas_central
"""
from django.core.management.base import CommandError

from apps.demo.entorno import exigir_entorno_de_prueba
from apps.finanzas.management.commands import seed_los_aromos
from apps.finanzas.models import ConceptoGasto
from apps.instituciones.models import Institucion

CENTRAL = "Hospital Central"


class Command(seed_los_aromos.Command):
    help = "Carga en Hospital Central el año económico de Los Aromos: gastos, costos, pagos y cobros."

    NOMBRE = CENTRAL
    DOMINIO = "hospital.gob.ar"
    ESPACIO = "hospital-central"
    PREFIJO_PACIENTE, PREFIJO_DOCUMENTO = "HC-AMB", "FICHC"
    # Mismos servicios, importes y aranceles que Los Aromos; otras áreas y otras
    # personas. Central ya tiene «Cardiología» y «Diagnóstico por imágenes».
    AREAS = (
        ("CM", "Consultorios de clínica médica", "Consulta de clínica médica", "Nora", "Villegas",
         "nora.villegas", "70412", 15000, 1000, 30000),
        ("CAR", "Consultorios de cardiología", "Consulta cardiológica", "Julio", "Barreto",
         "julio.barreto", "81205", 22000, 1500, 45000),
        ("IMG", "Radiología ambulatoria", "Radiografía digital de tórax", "Carolina", "Espinosa",
         "carolina.espinosa", "93118", 7000, 3000, 35000),
    )
    # Otras personas que las de Los Aromos, en el mismo orden: el escenario las
    # usa por posición.
    PACIENTES = tuple(reversed(seed_los_aromos.PACIENTES))
    PERSONAL = {
        "admin": ("Dirección", "Hospital Central", "admin.central"),
        "configurador": ("Configurador", "de Procesos", "config.central"),
        "administrativa": ("Mariela", "Quintero", "m.quintero"),
    }

    def handle(self, *args, **options):
        # Antes que nada, la guarda de entorno: el test de producción corre el
        # comando sin datos y espera ese error, no el de «falta Central».
        exigir_entorno_de_prueba("seed_finanzas_central")
        if not Institucion.objects.filter(nombre=CENTRAL).exists():
            raise CommandError(f"No existe «{CENTRAL}». Corré `seed_guardia` y `seed_roles` primero.")
        return super().handle(*args, **options)

    def _ya_cargado(self):
        return ConceptoGasto.objects.filter(institucion__nombre=CENTRAL).exists()

    def _crear_institucion(self):
        return Institucion.objects.get(nombre=CENTRAL)
