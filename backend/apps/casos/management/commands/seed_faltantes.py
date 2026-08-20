"""
Completa los huecos que `seed_volumen` no cubre, para que TODOS los módulos se
puedan demostrar.

`seed_guardia` arma la estructura y `seed_volumen` carga el volumen del circuito
asistencial, pero cinco cosas quedan sin datos y por lo tanto sin pantalla que
mostrar:

- **Farmacia**: hay stock, lotes y movimientos, pero cero pedidos de reposición.
  Preparar, entregar, entrega parcial y rechazo son cuatro funcionalidades que
  existen y no se pueden ver.
- **Trazabilidad de lote**: ningún consumo queda imputado a un caso, así que
  `trazar-lote` contesta que no llegó a ningún paciente. La pregunta que
  justifica la función —«se retira el lote, a quién se le aplicó»— queda sin
  respuesta.
- **Agenda**: hay agendas, franjas y turnos, pero ningún bloqueo. El bloqueo
  parcial —que se calcula por solape con la duración del turno y no por hora de
  inicio— no se puede mostrar.
- **Pantalla pública de llamados**: el token se genera a pedido desde el editor,
  así que recién sembrado no hay ninguno y `/pantalla/<token>` no se puede abrir.
- **Roles de gobierno**: no hay usuario con rol `plataforma`, `auditor` ni
  `reportes`, ni un `admin` de institución. Sin ellos, el gobierno estatal y la
  pantalla de administración sólo se pueden demostrar como superusuario, que es
  precisamente el rol que no representa a nadie en un hospital.

Es idempotente y hay que correrlo **después** de `seed_volumen --rehacer`, que
borra lo que este comando siembra:

    python manage.py seed_volumen --rehacer
    python manage.py seed_faltantes
"""
import random
import secrets
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Membresia, Usuario
from apps.agenda.models import Bloqueo, Turno
from apps.agenda import motor as agenda_motor
from apps.farmacia import motor as farmacia_motor
from apps.casos.models import Caso, ItemFila
from apps.farmacia.models import Deposito, Insumo, LineaPedido, Lote, Pedido
from apps.flujos.models import Nodo
from apps.instituciones.models import Institucion

CLAVE = "demo1234"

# Rol, email y nombre de los usuarios que faltan para demostrar autoridad.
#
# `plataforma` y `auditor` son roles estatales: su capacidad es global, pero la
# membresía necesita una institución donde colgar, así que se los ancla al
# hospital de referencia. Eso no les da permisos clínicos ahí.
USUARIOS = [
    ("plataforma", "plataforma@cauce.local", "Autoridad", "de Plataforma"),
    ("auditor", "auditor@cauce.local", "Auditoría", "Estatal"),
    ("reportes", "reportes@cauce.local", "Reportes", "Ministerio"),
    ("admin", "admin.central@hospital.gob.ar", "Dirección", "Hospital Central"),
    ("configurador", "config.central@hospital.gob.ar", "Configurador", "de Procesos"),
]


class Command(BaseCommand):
    help = "Siembra pedidos de farmacia, un bloqueo de agenda y los roles de gobierno que faltan."

    def add_arguments(self, parser):
        parser.add_argument("--institucion", type=int, default=None,
                            help="Id de la institución de referencia (por defecto, la primera activa).")
        parser.add_argument("--semilla", type=int, default=2026,
                            help="Semilla del azar (misma semilla = mismos datos).")

    @transaction.atomic
    def handle(self, *args, **opciones):
        random.seed(opciones["semilla"])
        inst = self._institucion(opciones["institucion"])
        self.stdout.write(self.style.MIGRATE_HEADING(f"Completando la demo de «{inst.nombre}»"))

        self._usuarios(inst)
        self._pedidos(inst)
        self._consumos(inst)
        self._bloqueo(inst)
        self._pantallas(inst)

        self.stdout.write(self.style.SUCCESS("\nListo. Claves de los usuarios nuevos: " + CLAVE))

    # ----------------------------------------------------------------- #
    def _institucion(self, id_pedido):
        if id_pedido:
            inst = Institucion.objects.filter(pk=id_pedido).first()
            if not inst:
                raise CommandError(f"No existe la institución {id_pedido}.")
            return inst
        inst = Institucion.objects.filter(estado="activa").order_by("id").first()
        if not inst:
            raise CommandError("No hay ninguna institución activa. Corré seed_guardia primero.")
        return inst

    # ----------------------------------------------------------------- #
    def _usuarios(self, inst):
        self.stdout.write("\n· Roles de gobierno y administración")
        for rol, email, nombre, apellido in USUARIOS:
            u = Usuario.objects.filter(email=email).first()
            if not u:
                u = Usuario.objects.create_user(email, CLAVE, nombre=nombre, apellido=apellido)
                creado = "creado"
            else:
                u.set_password(CLAVE)
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

    # ----------------------------------------------------------------- #
    def _pedidos(self, inst):
        """
        Cinco pedidos, uno por estado, hechos con el motor real.

        Se usan `preparar_pedido` y `entregar_pedido` en vez de escribir el
        estado a mano: así el pedido parcial queda con su faltante real y las
        transferencias de stock dejan sus movimientos, que es lo que después se
        ve al trazar un lote.
        """
        self.stdout.write("\n· Pedidos de farmacia")
        central = Deposito.objects.filter(institucion=inst, central=True, activo=True).first()
        pide = Deposito.objects.filter(institucion=inst, activo=True, central=False).first()
        if not central or not pide:
            self.stdout.write(self.style.WARNING(
                "    Faltan depósitos (hace falta una central y uno de área): se omite."))
            return

        insumos = list(Insumo.objects.filter(institucion=inst, activo=True)[:6])
        if len(insumos) < 2:
            self.stdout.write(self.style.WARNING("    Menos de dos insumos cargados: se omite."))
            return

        autor = Usuario.objects.filter(email="admin.central@hospital.gob.ar").first()
        Pedido.objects.filter(origen=pide, destino=central).delete()
        ahora = timezone.now()

        def armar(cuantos_insumos, urgente, hace_horas, obs=""):
            p = Pedido.objects.create(origen=pide, destino=central, urgente=urgente,
                                      observaciones=obs, creado_por=autor)
            # `creado` es auto_now_add: se refecha con update() para que los
            # pedidos no aparezcan todos nacidos en el mismo segundo.
            Pedido.objects.filter(pk=p.pk).update(creado=ahora - timedelta(hours=hace_horas))
            for ins in random.sample(insumos, min(cuantos_insumos, len(insumos))):
                LineaPedido.objects.create(pedido=p, insumo=ins,
                                           pedido_cant=random.choice([5, 10, 20, 30]))
            return p

        hechos = []

        # 1. Pendiente: recién pedido, nadie lo tocó.
        hechos.append(("pendiente", armar(3, False, 5, "Reposición semanal del botiquín.")))

        # 2. Urgente pendiente: el que encabeza la lista.
        hechos.append(("pendiente urgente", armar(2, True, 1, "Faltante en guardia, turno noche.")))

        # 3. Preparado: pasó el picking, todavía no se despachó.
        p = armar(2, False, 8, "Listo para retirar por camillero.")
        try:
            farmacia_motor.preparar_pedido(p, autor=autor)
            hechos.append(("preparado", p))
        except Exception as e:  # sin stock suficiente para prometerlo
            hechos.append((f"quedó pendiente ({e})", p))

        # 4. Parcial: se entregó una parte y el faltante queda a la vista.
        p = armar(2, False, 26, "Se entregó lo disponible; falta reponer el resto.")
        lineas = list(p.lineas.all())
        entregas = {}
        for i, linea in enumerate(lineas):
            # Al primer renglón se le entrega de menos a propósito: es lo que
            # deja el pedido en `parcial` en vez de cerrarlo.
            disp = farmacia_motor.disponible(central, linea.insumo)
            objetivo = linea.pedido_cant // 2 if i == 0 else linea.pedido_cant
            entregas[linea.id] = max(0, min(objetivo, disp))
        try:
            # `entregar_pedido` relee el pedido bajo candado y devuelve ESA
            # instancia: la copia local queda vieja y decir `p.estado` acá
            # informaría «pendiente» sobre un pedido ya parcial.
            p = farmacia_motor.entregar_pedido(p, entregas, autor=autor)
            hechos.append((f"{p.estado}", p))
        except Exception as e:
            hechos.append((f"no se pudo entregar ({e})", p))

        # 5. Entregado completo.
        p = armar(1, False, 50, "Entregado completo.")
        linea = p.lineas.first()
        disp = farmacia_motor.disponible(central, linea.insumo)
        if disp < linea.pedido_cant:
            LineaPedido.objects.filter(pk=linea.pk).update(pedido_cant=max(1, disp))
            linea.refresh_from_db()
        try:
            p = farmacia_motor.entregar_pedido(p, {linea.id: linea.pedido_cant}, autor=autor)
            hechos.append((f"{p.estado}", p))
        except Exception as e:
            hechos.append((f"no se pudo entregar ({e})", p))

        # 6. Rechazado con motivo (misma regla que la acción de la API).
        p = armar(2, False, 72)
        p.estado = Pedido.Estado.RECHAZADO
        p.observaciones = "Rechazado: el insumo se discontinuó, pedir el equivalente."
        p.resuelto = ahora - timedelta(hours=70)
        p.save(update_fields=["estado", "observaciones", "resuelto"])
        hechos.append(("rechazado", p))

        for etiqueta, p in hechos:
            faltantes = sum(linea.faltante for linea in p.lineas.all())
            self.stdout.write(f"    #{p.pk:<5} {etiqueta:22} renglones={p.lineas.count()} "
                              f"faltante_total={faltantes}")

    # ----------------------------------------------------------------- #
    def _consumos(self, inst):
        """
        Consumo de insumos imputado a casos reales.

        Sin esto `trazar-lote` contesta `pacientes: []`: hay movimientos de
        stock, pero ninguno atado a un paciente, así que la pregunta que
        justifica la trazabilidad —«se retira el lote L-1-A, a quién se le
        aplicó»— no tiene respuesta que mostrar.
        """
        self.stdout.write("\n· Consumo de insumos imputado a casos")
        deposito = (Deposito.objects.filter(institucion=inst, activo=True, central=False).first()
                    or Deposito.objects.filter(institucion=inst, activo=True).first())
        if not deposito:
            self.stdout.write(self.style.WARNING("    Sin depósitos: se omite."))
            return

        casos = list(Caso.objects.filter(institucion=inst)
                     .exclude(estado__in=Caso.ESTADOS_FINALIZADOS)
                     .select_related("ciudadano")[:8])
        if not casos:
            self.stdout.write(self.style.WARNING("    Sin casos activos: se omite."))
            return

        autor = Usuario.objects.filter(email="admin.central@hospital.gob.ar").first()
        hechos = 0
        for caso in casos:
            # Sólo insumos que hoy tengan stock usable en ese depósito: pedirle
            # al motor un consumo sin existencias sería sembrar un error.
            for insumo in Insumo.objects.filter(institucion=inst, activo=True):
                if farmacia_motor.disponible(deposito, insumo) < 2:
                    continue
                try:
                    farmacia_motor.consumir(deposito, insumo, random.choice([1, 2]),
                                            caso=caso, autor=autor,
                                            motivo="Consumo durante la atención")
                    hechos += 1
                except Exception:
                    continue
                break

        # `trazar_lote` devuelve el queryset de movimientos, no el dict que arma
        # la vista: lo que interesa acá es si el lote llegó a algún paciente.
        trazables = sum(
            1 for lote in Lote.objects.filter(insumo__institucion=inst)
            if farmacia_motor.trazar_lote(lote).exists()
        )
        self.stdout.write(f"    {hechos} consumo(s) imputado(s) a casos · "
                          f"{trazables} lote(s) ya trazables hasta el paciente")

    # ----------------------------------------------------------------- #
    def _bloqueo(self, inst):
        """
        Un bloqueo que pisa turnos ya dados.

        Se elige el rango a partir de turnos futuros reales para que
        `turnos_afectados` devuelva algo: un bloqueo sobre una franja vacía no
        muestra la funcionalidad que importa, que es enterarse de a quién hay
        que reprogramar.
        """
        self.stdout.write("\n· Bloqueo de agenda")
        ahora = timezone.now()
        turno = (Turno.objects
                 .filter(agenda__institucion=inst,
                         estado__in=[Turno.Estado.RESERVADO, Turno.Estado.CONFIRMADO],
                         inicio__gt=ahora)
                 .select_related("agenda")
                 .order_by("inicio")
                 .first())
        if not turno:
            self.stdout.write(self.style.WARNING(
                "    No hay turnos futuros vigentes: se omite (sembrá volumen primero)."))
            return

        agenda = turno.agenda
        # Arranca media hora ANTES del turno y termina dentro de su duración: así
        # el solape es parcial, que es el caso que el cálculo por hora de inicio
        # dejaba pasar.
        desde = turno.inicio - timedelta(minutes=30)
        hasta = turno.inicio + timedelta(hours=3)
        Bloqueo.objects.filter(agenda=agenda, desde=desde, hasta=hasta).delete()
        b = Bloqueo.objects.create(agenda=agenda, desde=desde, hasta=hasta,
                                   motivo="Mantenimiento del equipo · demo")

        afectados = agenda_motor.turnos_en_rango(agenda, desde, hasta)
        self.stdout.write(
            f"    agenda «{agenda}» bloqueada {desde:%d/%m %H:%M}–{hasta:%H:%M} "
            f"(#{b.pk}) · turnos afectados: {len(afectados)}"
        )

    # ----------------------------------------------------------------- #
    def _pantallas(self, inst):
        """
        Token de la pantalla pública de llamados, para los nodos que hoy tienen cola.

        La pantalla vive en `/pantalla/<token>` y no pide login, pero el token se
        genera a pedido desde el editor: recién sembrado no existe ninguno, así
        que la pantalla de sala de espera —de las que más se muestran— no se puede
        abrir sin ir antes a generarlo. Se siembra para que esté lista.
        """
        self.stdout.write("\n· Pantalla pública de llamados")
        con_cola = (ItemFila.objects
                    .filter(caso__institucion=inst, atendido=False, ausente=False)
                    .values_list("nodo_id", flat=True))
        nodos = list(Nodo.objects.filter(pk__in=set(con_cola)).select_related("version__flujo"))
        if not nodos:
            self.stdout.write(self.style.WARNING("    Ninguna cola con pacientes: se omite."))
            return
        for nodo in nodos:
            if not nodo.pantalla_token:
                nodo.pantalla_token = secrets.token_urlsafe(12)
                nodo.save(update_fields=["pantalla_token"])
            cola = ItemFila.objects.filter(nodo=nodo, atendido=False, ausente=False).count()
            self.stdout.write(f"    «{nodo.titulo}» ({nodo.version.flujo.titulo}) · en cola {cola} "
                              f"-> /pantalla/{nodo.pantalla_token}")
