"""Pedidos de reposición y consumos imputados a pacientes en la farmacia del hospital.

Qué carga
---------
`seed_guardia` deja catálogo, depósitos, lotes y stock, pero ningún pedido ni
ningún consumo atado a un caso. Sin esto:

- **Pedidos:** preparar, entregar, entregar en parte y rechazar son cuatro
  funciones que existen y no se pueden ver. Se crea un pedido por estado, con el
  motor real, así el parcial queda con su faltante y las transferencias dejan
  sus movimientos.
- **Trazabilidad de lote:** `trazar-lote` contesta que el lote no llegó a ningún
  paciente, y la pregunta que justifica la función —«se retira el lote, a quién
  se le aplicó»— queda sin respuesta.

Requisitos
----------
- `ENTORNO` distinto de `produccion`.
- El hospital ya cargado (`seed_guardia`), con casos en curso (`seed_volumen`).
- Su administración institucional (`seed_roles`), que figura como autora.

Es idempotente respecto de los pedidos: borra los del mismo origen y destino
antes de crearlos. Los consumos se suman en cada corrida.
"""
import random
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Membresia, Usuario
from apps.casos.models import Caso
from apps.demo.entorno import exigir_entorno_de_prueba
from apps.farmacia import motor as farmacia_motor
from apps.farmacia.models import Deposito, Insumo, LineaPedido, Lote, Pedido
from apps.instituciones.models import Institucion

INSTITUCION_POR_DEFECTO = "Hospital Central"


class Command(BaseCommand):
    help = "Siembra pedidos de farmacia en cada estado y consumos imputados a casos."

    def add_arguments(self, parser):
        parser.add_argument("--institucion", type=int, default=None,
                            help=f"Id de la institución (por defecto, «{INSTITUCION_POR_DEFECTO}»).")
        parser.add_argument("--semilla", type=int, default=2026,
                            help="Semilla del azar (misma semilla = mismos datos).")

    @transaction.atomic
    def handle(self, *args, **opciones):
        exigir_entorno_de_prueba("seed_farmacia")
        random.seed(opciones["semilla"])
        inst = self._institucion(opciones["institucion"])
        self.autor = Usuario.objects.filter(
            membresias__institucion=inst, membresias__rol=Membresia.Rol.ADMIN_INSTITUCION,
        ).order_by("id").first()
        if not self.autor:
            raise CommandError(f"«{inst.nombre}» no tiene administración institucional. Corré seed_roles primero.")
        self.stdout.write(self.style.MIGRATE_HEADING(f"Farmacia de «{inst.nombre}»"))
        self._pedidos(inst)
        self._consumos(inst)

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

    # ----------------------------------------------------------------- #
    def _pedidos(self, inst):
        """Seis pedidos, uno por estado, hechos con el motor real."""
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

        autor = self.autor
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
        """Consumo de insumos imputado a casos en curso."""
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

        hechos = 0
        for caso in casos:
            # Sólo insumos que hoy tengan stock usable en ese depósito: pedirle
            # al motor un consumo sin existencias sería sembrar un error.
            for insumo in Insumo.objects.filter(institucion=inst, activo=True):
                if farmacia_motor.disponible(deposito, insumo) < 2:
                    continue
                try:
                    farmacia_motor.consumir(deposito, insumo, random.choice([1, 2]),
                                            caso=caso, autor=self.autor,
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
