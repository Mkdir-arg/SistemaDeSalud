"""Roles de gobierno y de administración del hospital de referencia.

Qué carga
---------
`seed_guardia` crea el personal que opera: administrativos, enfermería, médicos y
la jefatura de guardia. Faltan los roles que no operan casos, y sin ellos el
gobierno estatal y la administración sólo se pueden demostrar como superusuario,
que es precisamente el rol que no representa a nadie en un hospital:

- `plataforma`, `auditor` y `reportes`: roles estatales. Su capacidad es global,
  pero la membresía necesita una institución donde colgar, así que se los ancla
  al hospital de referencia. Eso no les da permisos clínicos ahí.
- `admin` y `configurador` del hospital de referencia.

Requisitos
----------
- `ENTORNO` distinto de `produccion`.
- El hospital de referencia ya cargado (`seed_guardia`).

Es idempotente: si el usuario existe, lo reactiva y le repone la clave de
`DEMO_PASSWORD` (ver `apps.demo.claves`).
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import Membresia, Usuario
from apps.demo.claves import clave_demo
from apps.demo.entorno import exigir_entorno_de_prueba
from apps.instituciones.models import Institucion

INSTITUCION_POR_DEFECTO = "Hospital Central"

# Rol, email y nombre de cada usuario.
USUARIOS = [
    ("plataforma", "plataforma@salud.local", "Autoridad", "de Plataforma"),
    ("auditor", "auditor@salud.local", "Auditoría", "Estatal"),
    ("reportes", "reportes@salud.local", "Reportes", "Ministerio"),
    ("admin", "admin.central@hospital.gob.ar", "Dirección", "Hospital Central"),
    ("configurador", "config.central@hospital.gob.ar", "Configurador", "de Procesos"),
]


class Command(BaseCommand):
    help = "Crea los usuarios de gobierno y de administración del hospital de referencia."

    def add_arguments(self, parser):
        parser.add_argument("--institucion", type=int, default=None,
                            help=f"Id de la institución de referencia (por defecto, «{INSTITUCION_POR_DEFECTO}»).")

    @transaction.atomic
    def handle(self, *args, **opciones):
        exigir_entorno_de_prueba("seed_roles")
        inst = self._institucion(opciones["institucion"])
        self.stdout.write(self.style.MIGRATE_HEADING(f"Roles de gobierno y administración en «{inst.nombre}»"))
        clave = clave_demo()
        for rol, email, nombre, apellido in USUARIOS:
            u = Usuario.objects.filter(email=email).first()
            if not u:
                u = Usuario.objects.create_user(email, clave, nombre=nombre, apellido=apellido)
                creado = "creado"
            else:
                u.set_password(clave)
                u.nombre, u.apellido, u.is_active = nombre, apellido, True
                u.save()
                creado = "actualizado"

            m, nueva = Membresia.objects.get_or_create(
                usuario=u, institucion=inst, rol=rol, defaults={"activo": True},
            )
            if not m.activo:
                m.activo = True
                m.save(update_fields=["activo"])
            # El admin institucional necesita áreas para que la supervisión y las
            # bandejas por área tengan algo que mostrar.
            if rol == "admin" and not m.areas.exists():
                m.areas.set(inst.areas.filter(activa=True)[:3])
            self.stdout.write(f"    {email:38} rol={rol:14} usuario {creado}"
                              f"{', membresía nueva' if nueva else ''}")

    def _institucion(self, id_pedido):
        if id_pedido:
            inst = Institucion.objects.filter(pk=id_pedido).first()
            if not inst:
                raise CommandError(f"No existe la institución {id_pedido}.")
            return inst
        inst = Institucion.objects.filter(nombre=INSTITUCION_POR_DEFECTO).first()
        if not inst:
            raise CommandError(f"No existe «{INSTITUCION_POR_DEFECTO}». Corré seed_guardia primero o indicá --institucion.")
        return inst
