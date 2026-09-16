"""Archivo hospitalario acotado: sólo campos financieros ya visibles en JSON."""
import csv
from collections import Counter
from io import StringIO

from django.http import HttpResponse
from django.utils import timezone
from rest_framework import serializers

from apps.finanzas.auditoria import AuditaLecturaFinanciera
from apps.finanzas.saldos import CAMPOS_SALDO
from .csv import texto_csv_seguro
from .seguimiento import fila_seguimiento


LIMITE_EXPORTACION = 5000
ORIGEN = (
    ("institucion", "Hospital (ID; texto)"), ("generado_en", "Generado el (ISO 8601)"),
    ("caso", "Caso (ID; texto)"), ("fecha", "Fecha de prestación"),
    ("area", "Área de origen (ID; texto)"), ("sensible", "Sensible"),
)
COBERTURA = (
    ("prestacion", "Prestación"), ("financiador", "Financiador de la cobertura (ID; texto)"),
    ("financiador_nombre", "Financiador de la cobertura"),
)
DINERO = (
    ("importe_original", "Importe original (ARS; coma decimal)"),
    ("ajustes_aprobados", "Ajustes aprobados (ARS; coma decimal)"),
    ("obligacion_actual", "Importe actual de la cuenta (ARS; coma decimal)"),
    ("registrado_neto", "Cobrado neto confirmado (ARS; coma decimal)"),
    ("pendiente", "Saldo pendiente de cobro (ARS; coma decimal)"),
    ("saldo_a_devolver", "Saldo a devolver (ARS; coma decimal)"),
    ("por_aprobar", "Cobros por aprobar (ARS; coma decimal)"),
    ("reintegros_por_aprobar", "Devoluciones por aprobar (ARS; coma decimal)"),
    ("ajustes_por_aprobar", "Reducciones por aprobar (ARS; coma decimal)"),
)
COLUMNAS = {
    "cuentas": ORIGEN + (("id", "Cuenta (ID; texto)"), ("reserva", "Reserva (ID; texto)")) + COBERTURA + (
        ("responsable", "Tipo de responsable"), ("contraparte_nombre", "Responsable del cobro"),
    ) + DINERO,
    "pendientes": ORIGEN + (("id", "Reserva (ID; texto)"),) + COBERTURA + (
        ("estado", "Estado administrativo (no constituye deuda asignada)"), ("motivo", "Motivo"),
        ("importe_pendiente", "Importe administrativo (ARS; coma decimal; vacío = por determinar)"),
    ),
    "captura": ORIGEN + (("id", "Hecho de atención (ID; texto)"), ("estado", "Estado de captura"), ("motivo", "Motivo")),
}
ETIQUETAS = {
    "responsable": {"financiador": "Financiador", "paciente": "Paciente"},
    "estado": {
        "pendiente": "Pendiente de resolución", "arancel_pendiente": "Arancel pendiente",
        "evaluacion_pendiente": "Evaluación pendiente", "sin_distribucion": "Sin distribución",
        "captura_pendiente": "Captura pendiente",
    },
}
IDENTIFICADORES = {"id", "institucion", "caso", "area", "financiador", "reserva"}
TEXTOS_LIBRES = {"prestacion", "financiador_nombre", "contraparte_nombre", "motivo"}


def celda_seguimiento(campo, valor):
    if valor is None:
        return ""
    if isinstance(valor, bool):
        return "Sí" if valor else "No"
    if campo == "fecha":
        return valor.isoformat()
    if campo in CAMPOS_SALDO or campo == "importe_pendiente":
        # Son decimales producidos por el cálculo de saldos, nunca texto libre.
        return valor.replace(".", ",")
    # El CSV no tiene tipos de celda: el prefijo conserva también nombres que
    # Excel podría interpretar como fechas o números. Es una convención del archivo.
    return texto_csv_seguro(ETIQUETAS.get(campo, {}).get(valor, valor), identificador=campo in IDENTIFICADORES | TEXTOS_LIBRES)


def exportar_seguimiento(view, qs, *, institucion, vista, generado_en):
    objetos = list(qs[:LIMITE_EXPORTACION + 1])
    if len(objetos) > LIMITE_EXPORTACION:
        raise serializers.ValidationError(f"La exportación admite hasta {LIMITE_EXPORTACION} registros. Acotá las fechas u otros filtros.")
    contenido = StringIO(newline="")
    escritor = csv.writer(contenido, delimiter=";")
    columnas = COLUMNAS[vista]
    escritor.writerow([titulo for _, titulo in columnas])
    grupos = Counter()
    generado_iso = timezone.localtime(generado_en).isoformat()
    for objeto in objetos:
        fila = fila_seguimiento(objeto, vista)
        fila.update(institucion=institucion, generado_en=generado_iso)
        escritor.writerow([celda_seguimiento(campo, fila[campo]) for campo, _ in columnas])
        grupos[(institucion, fila["area"], fila["sensible"], fila["fecha"].replace(day=1))] += 1
    if not grupos:
        grupos[(institucion, None, False, None)] = 0
    respuesta = HttpResponse("\ufeff" + contenido.getvalue(), content_type="text/csv; charset=utf-8")
    respuesta["Content-Disposition"] = f'attachment; filename="seguimiento-{vista}-hospital-{institucion}-{timezone.localtime(generado_en):%Y%m%d-%H%M%S}.csv"'
    respuesta["X-Content-Type-Options"] = "nosniff"
    # Se auditan exactamente las filas materializadas. Sin streaming: un fallo
    # revierte todos los grupos y no entrega ningún byte del archivo.
    return AuditaLecturaFinanciera.auditar_respuesta(
        view, respuesta, grupos=grupos, recurso="seguimiento-cobros", accion=f"exportar_{vista}",
    )
