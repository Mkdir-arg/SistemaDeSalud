"""Carga puntual autorizada para la demo 8090; ejecutar dentro de manage.py shell.

Sin FINANZAS_HISTORICO_DEMO=APLICAR_20260914 sólo muestra el plan.
No se instala como comando ni se ejecuta al arrancar la aplicación.
"""
import os
from datetime import date
from decimal import Decimal

from django.db import transaction
from apps.accounts.models import Usuario
from apps.instituciones.models import Area, Institucion
from apps.finanzas.models import ConceptoGasto, Gasto, ExpectativaGasto, IndicacionCargaGasto
from apps.finanzas.permisos import tiene_concesion_financiera
from apps.finanzas.services import (
    aprobar_gasto, indicar_carga_esperada, registrar_expectativa_gasto, registrar_gasto,
)

PREFIJO = "DEMO-HIST-20260914-"
MESES = [date(2025, m, 1) for m in (10, 11, 12)] + [date(2026, m, 1) for m in range(1, 10)]
SERIES = [
    ("ELEC", "Electricidad", "12000", [10200, 10800, 11600, 12900, 12100, 11200, 11800, 12400, 13900, 13200, 12600, 13100]),
    ("LIMP", "Limpieza", "8000", [7000, 7000, 7200, 7500, 7400, 7600, 7600, 7800, 7900, 8100, 8000, 8200]),
    ("MANT", "Mantenimiento", "5000", [4200, 5100, 3900, 6200, 4300, 4800, 7100, 4500, 5200, 4600, 3200, 5400]),
]


def ejecutar():
    # Identidades constatadas en la demo; nunca adivinar otro destino/actor.
    institucion = Institucion.objects.get(pk=2, nombre="Hospital Demo Finanzas")
    area = Area.objects.get(pk=5, institucion=institucion, nombre="Consultorio escuela")
    actor = Usuario.objects.get(pk=8, is_active=True)
    for accion in ("registrar_gastos", "aprobar_gastos", "configurar_gastos_esperados"):
        if not tiene_concesion_financiera(actor, accion, institucion.pk, area.pk):
            raise RuntimeError("Faltan permisos actuales; no se crean ni se amplían concesiones.")
    print("Destino:", institucion.nombre, "/", area.nombre)
    print("Plan: 3 conceptos Demo histórico; 4 vigencias; 36 cierres; 37 gastos.")
    print("Períodos: 2025-10 a 2026-09. Mantenimiento agosto: 3200 aprobado + 1800 pendiente.")
    if os.environ.get("FINANZAS_HISTORICO_DEMO") != "APLICAR_20260914":
        print("Sólo inspección: ninguna escritura.")
        return
    with transaction.atomic():
        Institucion.objects.select_for_update().get(pk=institucion.pk)
        existentes = ConceptoGasto.objects.filter(institucion=institucion, codigo__startswith=PREFIJO)
        if existentes.exists():
            if existentes.count() != 3 or Gasto.objects.filter(concepto__in=existentes).count() != 37:
                raise RuntimeError("Lote existente inesperado. Revisar; no completar ni sobrescribir.")
            print("El lote ya existe. No se duplicó ni se modificó ningún registro.")
            return
        # Comprobar que las fuentes previas no sufrieron alteraciones.
        protegidos = [Gasto, ExpectativaGasto, IndicacionCargaGasto, ConceptoGasto]
        originales = [(modelo, list(modelo.objects.order_by("pk").values())) for modelo in protegidos]
        ids = []
        for codigo, nombre, referencia, valores in SERIES:
            concepto = ConceptoGasto.objects.create(
                institucion=institucion, codigo=PREFIJO + codigo,
                nombre="Demo histórico · " + nombre, registrado_por=actor,
            )
            control = registrar_expectativa_gasto(
                registrado_por=actor, concepto=concepto, institucion=institucion, area=area,
                vigente_desde=MESES[0], vigente_hasta=date(2026, 10, 1),
                monto_referencia=Decimal(referencia),
            )
            siguiente = None
            if codigo == "ELEC":
                siguiente = registrar_expectativa_gasto(
                    registrado_por=actor, concepto=concepto, institucion=institucion, area=area,
                    vigente_desde=date(2026, 4, 1), vigente_hasta=date(2026, 10, 1),
                    monto_referencia=Decimal("13500"), reemplaza=control,
                )
            for mes, importe in zip(MESES, valores, strict=True):
                gasto = registrar_gasto(concepto, institucion, area, Decimal(importe), mes, actor)
                if gasto.estado != Gasto.Estado.APROBADO:
                    aprobar_gasto(gasto.pk, actor)
                ids.append(gasto.pk)
                vigente = siguiente if siguiente and mes >= siguiente.vigente_desde else control
                indicar_carga_esperada(vigente.pk, mes, "carga_completa", actor)
            if codigo == "MANT":
                # El usuario de área existente puede cargar, pero no aprobar.
                cargador = Usuario.objects.get(pk=6, email="admision.escuela@demo.local", is_active=True)
                pendiente = registrar_gasto(concepto, institucion, area, Decimal("1800"), date(2026, 8, 1), cargador)
                if pendiente.estado != Gasto.Estado.PENDIENTE_APROBACION:
                    raise RuntimeError("El escenario debe conservar una aprobación pendiente.")
                ids.append(pendiente.pk)
        for modelo, filas in originales:
            actuales = list(modelo.objects.filter(pk__in=[f["id"] for f in filas]).order_by("pk").values())
            if actuales != filas:
                raise RuntimeError("Cambió una fuente previa durante la carga. Se revierte el lote nuevo.")
        print("Gastos creados:", ids)
        print("Fuentes previas intactas. Sin atenciones, reglas, usuarios ni permisos nuevos.")


ejecutar()
