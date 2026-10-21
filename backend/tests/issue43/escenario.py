"""Preparación ficticia y lecturas ORM; nunca se instala como API ni comando global."""
import json
import os
import sys
from pathlib import Path

if os.environ.get("DJANGO_SETTINGS_MODULE", "config.settings_issue43_test") != "config.settings_issue43_test":
    raise RuntimeError("El escenario #43 sólo admite config.settings_issue43_test")
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings_issue43_test"

import django
django.setup()

from django.db import connection, transaction
from django.utils import timezone
from apps.accounts.models import Membresia, Usuario
from apps.casos.models import Caso
from apps.finanzas.models import ConcesionFinanciera, HechoAtencionCosteable, MovimientoDinero, ObligacionFinanciera
from apps.finanzas.dinero import estado_obligacion
from apps.flujos.models import Conexion, Nodo
from apps.financiadores import models as m
from apps.financiadores.cobertura import seleccionar_afiliacion
from apps.financiadores.test_esperas import EsperaSetup


def validar_destino():
    destino = connection.settings_dict
    if (os.environ.get("SALUD_ISSUE43_AISLADO") != "1"
            or destino["NAME"] != "salud_issue43"
            or destino["HOST"] != "127.0.0.1" or str(destino["PORT"]) != "55443"):
        raise RuntimeError("Se rechaza un destino fuera del PostgreSQL exclusivo de #43")


@transaction.atomic
def preparar():
    validar_destino()
    # No flush ni borrado: una repetición requiere un contenedor nuevo.
    if Usuario.objects.exists():
        raise RuntimeError("#43 requiere una base vacía; no se sobrescriben datos existentes")
    s = EsperaSetup()
    s.setUp()
    s.caso.estado = Caso.Estado.EN_EVALUACION
    s.caso.save(update_fields=["estado"])
    final = Nodo.objects.create(version=s.caso.version, tipo=Nodo.Tipo.FIN, titulo="Fin #43")
    Conexion.objects.create(version=s.caso.version, origen=s.nodo, destino=final)
    for accion in ("registrar_aceptacion", "ver_dinero", "registrar_dinero", "aprobar_dinero"):
        ConcesionFinanciera.objects.create(membresia=s.miembro_hospital, accion=accion, todas_las_areas=True)
    rechazo = Caso.objects.create(
        institucion=s.institucion, version=s.caso.version, ciudadano=s.paciente,
        area_actual=s.area, nodo_actual=s.nodo, paso_desde=timezone.now(),
        estado=Caso.Estado.EN_EVALUACION,
    )
    seleccionar_afiliacion(caso=rechazo, usuario=s.usuario, afiliado=s.afiliado, motivo="Escenario ficticio #43")
    return {
        "hospital": {"id": s.institucion.pk, "nombre": s.institucion.nombre},
        "caso": s.caso.pk, "rechazo": rechazo.pk, "prestacion": s.prestacion.pk,
        "financiador": s.financiador.pk, "hospital_email": s.usuario.email,
        "resolutor_email": s.operador.email, "fecha": str(s.hoy),
    }


def estado(caso_id):
    validar_destino()
    caso = Caso.objects.get(pk=caso_id)
    reservas = m.ReservaCobertura.objects.filter(caso=caso)
    hechos = HechoAtencionCosteable.objects.filter(caso_origen_id=caso.pk)
    cuentas = ObligacionFinanciera.objects.filter(hecho__in=hechos)
    movimientos = MovimientoDinero.objects.filter(obligacion__in=cuentas)
    return {
        "caso_estado": caso.estado, "nodo": caso.nodo_actual_id,
        "solicitudes": list(m.SolicitudAutorizacion.objects.filter(caso=caso).values("id", "estado", "revision")),
        "reservas": list(reservas.values("id", "estado", "hecho_id")),
        "hechos": hechos.count(),
        "cuentas": [{"id": cuenta.pk, "importe_original": cuenta.importe_original,
                     "contraparte_nombre": cuenta.contraparte_nombre,
                     "pendiente": estado_obligacion(cuenta)["pendiente"]} for cuenta in cuentas.order_by("pk")],
        "movimientos": list(movimientos.values("id", "importe", "estado", "tipo")),
        "usos": list(m.UsoAutorizacion.objects.filter(reserva__in=reservas).values("estado", "hecho_id")),
    }


if __name__ == "__main__":
    if sys.argv[1] == "preparar":
        Path(sys.argv[2]).write_text(json.dumps(preparar()), encoding="utf-8")
    elif sys.argv[1] == "estado":
        print(json.dumps(estado(int(sys.argv[2])), default=str))
    else:
        raise SystemExit("Usar preparar <metadata.json> o estado <caso>")
