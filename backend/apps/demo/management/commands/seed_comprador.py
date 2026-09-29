"""El usuario de quien recibe la demo: puede entrar a todo y le queda algo por hacer.

Qué carga
---------
Los usuarios de las otras cargas son uno por rol: sirven para mostrar cada
perfil, pero quien prueba el sistema por su cuenta choca con «Acceso denegado» en
cada pantalla que no es la suya. Este comando crea `comprador@salud.local`:

- **Plataforma:** entra al tablero de instituciones, como la autoridad estatal.
- **Hospital Central:** todos los roles, todas las áreas y todos los equipos.
  Tiene casos por tomar, pacientes en fila, turnos por confirmar y traslados por
  responder, los mismos que el resto del personal.
- **Los Aromos:** administración con todos los permisos de finanzas. Es donde
  están los gastos, los costos, los cobros y las coberturas. Tiene los mismos
  permisos en las otras dos instituciones donde administra, para que Finanzas
  no le niegue ninguna pestaña.
- **Mutual del Valle:** administración del portal del financiador, con
  autorizaciones por responder.
- **Hospital Piloto:** su propia institución, en puesta en marcha. Tiene áreas y
  personal asignado, pero ni agendas ni flujo publicado: completar la guía de
  Inicio queda para él.

Además recibe las notificaciones recientes de los equipos a los que se suma, para
no entrar con la campana vacía.

Requisitos
----------
- `ENTORNO` distinto de `produccion`.
- Cargados Hospital Central (`seed_guardia`), Los Aromos (`seed_los_aromos`) y
  Mutual del Valle (`seed_financiadores`).

No es idempotente: se carga una vez por `seed_entorno_demo`, que vacía la base.
La clave es la de `DEMO_PASSWORD` (ver `apps.demo.claves`).

    python manage.py seed_comprador
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import LegajoProfesional, Membresia, Usuario
from apps.casos.models import Notificacion
from apps.demo.claves import clave_demo
from apps.demo.entorno import exigir_entorno_de_prueba
from apps.finanzas.models import ConcesionFinanciera
from apps.financiadores.models import Financiador, MembresiaFinanciador
from apps.instituciones.models import Area, Grupo, Institucion

EMAIL = "comprador@salud.local"
CENTRAL = "Hospital Central"
LOS_AROMOS = "Hospital General Los Aromos"
FINANCIADOR = "Mutual del Valle"
PILOTO = "Hospital Piloto"
AREAS_PILOTO = ["Guardia", "Consultorios externos", "Internación"]
# Las que se copian de los equipos: suficientes para la campana, no un historial.
NOTIFICACIONES = 12

R = Membresia.Rol


class Command(BaseCommand):
    help = "Crea el usuario de quien recibe la demo, con acceso a todo y una institución propia por configurar."

    @transaction.atomic
    def handle(self, *args, **opciones):
        exigir_entorno_de_prueba("seed_comprador")
        central = self._institucion(CENTRAL, "seed_guardia")
        aromos = self._institucion(LOS_AROMOS, "seed_los_aromos")
        financiador = Financiador.objects.filter(nombre=FINANCIADOR).first()
        if financiador is None:
            raise CommandError(f"No existe «{FINANCIADOR}». Corré `seed_financiadores` primero.")

        comprador = Usuario.objects.create_user(EMAIL, clave_demo(), nombre="Comprador", apellido="Demo")
        # Firma atenciones como médico: el motor pide matrícula.
        LegajoProfesional.objects.create(usuario=comprador, especialidad="Clínica médica", matricula="MP 00065")

        areas_central = list(central.areas.filter(activa=True))
        for rol in R.values:
            membresia = Membresia.objects.create(usuario=comprador, institucion=central, rol=rol)
            membresia.areas.set(areas_central)
            if rol == R.ADMIN_INSTITUCION:
                self._finanzas(membresia)
        grupos = Grupo.objects.filter(area__institucion=central, activo=True)
        for grupo in grupos:
            grupo.miembros.add(comprador)

        admin_aromos = Membresia.objects.create(usuario=comprador, institucion=aromos, rol=R.ADMIN_INSTITUCION)
        admin_aromos.areas.set(aromos.areas.filter(activa=True))
        self._finanzas(admin_aromos)

        MembresiaFinanciador.objects.create(financiador=financiador, usuario=comprador, rol="admin",
                                            resuelve_autorizaciones=True)

        piloto = self._piloto(comprador)
        copiadas = self._notificaciones(comprador, grupos)

        self.stdout.write(self.style.SUCCESS(
            f"\n{EMAIL}: plataforma y {len(R.values)} roles en {central.nombre} ({grupos.count()} equipos), "
            f"finanzas completas en {aromos.nombre}, portal de {financiador.nombre} y "
            f"«{piloto.nombre}» en puesta en marcha · {copiadas} notificaciones sin leer."
        ))

    def _finanzas(self, membresia):
        """Todos los permisos de finanzas, en todas las áreas.

        Donde es administrador: sin ellos, Finanzas le responde «No tenés
        permiso» en las pestañas de dinero y reportes, aunque no haya datos.
        """
        for accion in ConcesionFinanciera.Accion.values:
            ConcesionFinanciera.objects.create(membresia=membresia, accion=accion, todas_las_areas=True)

    def _institucion(self, nombre, comando):
        inst = Institucion.objects.filter(nombre=nombre).first()
        if inst is None:
            raise CommandError(f"No existe «{nombre}». Corré `{comando}` primero.")
        return inst

    def _piloto(self, comprador):
        """La institución del comprador: tres de los seis pasos de la guía hechos.

        Áreas, usuarios y asignaciones sí; agendas y flujo no. Son los pasos que
        muestran el diseñador de flujos y la agenda, que es lo que el comprador
        va a querer probar con su propia estructura.
        """
        piloto = Institucion.objects.create(nombre=PILOTO, tipo="Hospital general",
                                            estado=Institucion.Estado.EN_ALTA)
        areas = [Area.objects.create(institucion=piloto, nombre=nombre) for nombre in AREAS_PILOTO]
        admin = Membresia.objects.create(usuario=comprador, institucion=piloto, rol=R.ADMIN_INSTITUCION)
        admin.areas.set(areas)
        self._finanzas(admin)
        # Quien lo acompaña en la configuración: sin él, la institución tiene
        # un solo usuario y la guía no muestra para qué sirve asignar personal.
        referente = Usuario.objects.create_user("piloto.config@hospital.gob.ar", clave_demo(),
                                                nombre="Referente", apellido="de Sistemas")
        Membresia.objects.create(usuario=referente, institucion=piloto, rol=R.CONFIGURADOR).areas.set(areas)
        return piloto

    def _notificaciones(self, comprador, grupos):
        """Las últimas notificaciones de sus compañeros de equipo, como si fueran suyas.

        Llegaron antes de que se sumara, así que no las recibió. Se copian las
        más recientes (sin repetir caso y título) y quedan sin leer.
        """
        companeros = Usuario.objects.filter(grupos__in=grupos).exclude(pk=comprador.pk).distinct()
        vistas, copias, fechas = set(), [], []
        for n in Notificacion.objects.filter(usuario__in=companeros).order_by("-creada", "-id")[:200]:
            if (n.caso_id, n.titulo) in vistas:
                continue
            vistas.add((n.caso_id, n.titulo))
            copias.append(Notificacion(usuario=comprador, titulo=n.titulo, detalle=n.detalle, caso_id=n.caso_id))
            fechas.append(n.creada)
            if len(copias) == NOTIFICACIONES:
                break
        creadas = Notificacion.objects.bulk_create(copias)
        # `creada` es auto_now_add: la fecha original se pone después.
        for copia, fecha in zip(creadas, fechas):
            Notificacion.objects.filter(pk=copia.pk).update(creada=fecha)
        return len(creadas)
