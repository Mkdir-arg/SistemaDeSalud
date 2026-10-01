"""El año económico ficticio de Hospital Central.

Qué carga
---------
Hospital Central es el hospital con la operación clínica completa. Este comando
carga doce meses de gastos con su reparto, costos por atención, cuentas, pagos
y cobros, y lo pendiente de cada rol, en tres servicios ambulatorios propios.

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
- Hospital Central con su dirección y su configurador (`seed_guardia` y `seed_roles`).
- El escenario todavía no cargado en Central. Para rehacerlo se vacía la base
  con `seed_entorno_demo`.

    python manage.py seed_finanzas_central
"""
from django.core.management.base import CommandError

from apps.demo.entorno import exigir_entorno_de_prueba
from apps.finanzas.escenario_economico import EscenarioEconomico
from apps.finanzas.models import ConceptoGasto
from apps.instituciones.models import Institucion

CENTRAL = "Hospital Central"


class Command(EscenarioEconomico):
    help = "Carga en Hospital Central un año económico ficticio: gastos, costos, pagos y cobros."

    COMANDO = "seed_finanzas_central"
    NOMBRE = CENTRAL
    DOMINIO = "hospital.gob.ar"
    ESPACIO = "hospital-central"
    PREFIJO_PACIENTE, PREFIJO_DOCUMENTO = "HC-AMB", "FICHC"
    # Áreas propias: Central ya tiene «Cardiología» y «Diagnóstico por imágenes».
    AREAS = (
        ("CM", "Consultorios de clínica médica", "Consulta de clínica médica", "Nora", "Villegas",
         "nora.villegas", "70412", 15000, 1000, 30000),
        ("CAR", "Consultorios de cardiología", "Consulta cardiológica", "Julio", "Barreto",
         "julio.barreto", "81205", 22000, 1500, 45000),
        ("IMG", "Radiología ambulatoria", "Radiografía digital de tórax", "Carolina", "Espinosa",
         "carolina.espinosa", "93118", 7000, 3000, 35000),
    )
    # El escenario selecciona personas por posición; preservar este orden.
    PACIENTES = (
        ("Nicolás", "Agüero"), ("Patricia", "Bustos"), ("Ramiro", "Oliva"),
        ("Mónica", "Sosa"), ("Adrián", "Franco"), ("Teresa", "Ibarra"),
        ("Diego", "Bustamante"), ("Graciela", "Rivero"), ("Tomás", "Navarro"),
        ("Elisa", "Roldán"), ("Sergio", "Páez"), ("Laura", "Oviedo"),
        ("Marcos", "Medina"), ("Silvia", "Godoy"), ("Pablo", "Arce"),
        ("Cecilia", "Luna"), ("Gabriel", "Pereyra"), ("Alicia", "Figueroa"),
        ("Julián", "Vera"), ("Beatriz", "Correa"), ("Federico", "Almada"),
        ("Natalia", "Soria"), ("Hugo", "Cabrera"), ("Marta", "Villalba"),
        ("Esteban", "Ponce"), ("Inés", "Quiroga"), ("Roberto", "Ledesma"),
        ("Julia", "Acosta"), ("Daniel", "Peralta"), ("Clara", "Benítez"),
    )
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
