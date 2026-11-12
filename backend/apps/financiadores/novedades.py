"""Evidencia administrativa conciliable; sin ejecutor de padrón ni derechos."""
import hashlib
import json

from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone

from apps.simulacion.contexto import autor_real
from .models import Afiliado, Financiador, HistorialAfiliacion, Importacion
from .permisos import requerir_financiador
from .services import auditar

TIPO = "novedades"
VERSION = 1
ESTADOS = ("pendiente", "conciliada", "descartada")


def _huella(datos):
    return hashlib.sha256(json.dumps(datos, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":")).encode()).hexdigest()


def _persona(afiliado):
    return {"id": afiliado.pk, "documento": afiliado.documento,
            "numero": afiliado.numero, "nombre": afiliado.nombre,
            "revision": afiliado.revision, "finalizada": afiliado.finalizado_en is not None,
            "cobertura_habilitada": afiliado.cobertura_habilitada}


def consultar(*, financiador, novedad_id):
    return get_object_or_404(Importacion, pk=novedad_id, financiador=financiador,
                             tipo=TIPO, version=VERSION)


def comparar(obj):
    original = obj.filas[0]["original"]
    persona = get_object_or_404(Afiliado, pk=original["afiliado"], financiador=obj.financiador_id)
    coincidencias = []
    if original["referencia"]:
        coincidencias = list(Importacion.objects.filter(financiador=obj.financiador_id,
            tipo=TIPO, version=VERSION, resumen__fuente=original["fuente"],
            resumen__referencia=original["referencia"]).exclude(pk=obj.pk)
            .order_by("pk").values_list("pk", flat=True)[:100])
    conflictos = []
    if persona.revision != obj.filas[0]["persona_inicial"]["revision"]:
        conflictos.append("padron_modificado")
    if coincidencias:
        conflictos.append("referencia_repetida")
    return {"persona_actual": _persona(persona), "coincidencias": coincidencias,
            "conflictos": conflictos}


def presentar(obj):
    fila = obj.filas[0]
    operacion = fila.get("habilitacion_cobertura")
    return {"id": obj.pk, "clave": str(obj.clave), "estado": obj.estado,
            "revision": fila["revision"], "original": fila["original"],
            "persona_inicial": fila["persona_inicial"], "historia": fila["historia"],
            "creado": obj.creado, "efectos_aplicados": False,
            "habilitacion_cobertura": ({k: v for k, v in operacion.items()
                                        if k != "decision_huella"} if operacion else None),
            **comparar(obj)}


def resumir(obj):
    return {"id": obj.pk, "estado": obj.estado, "creado": obj.creado,
            "original": obj.filas[0]["original"], "efectos_aplicados": False}


@transaction.atomic
def registrar(*, financiador, usuario, clave, **entrada):
    Financiador.objects.select_for_update().get(pk=financiador.pk)
    requerir_financiador(usuario, financiador.pk, escritura=True)
    original = {**entrada, "fecha_informada": entrada["fecha_informada"].isoformat()
                if entrada["fecha_informada"] else None}
    huella = _huella(original)
    anterior = Importacion.objects.filter(financiador=financiador, clave=clave).first()
    if anterior:
        if anterior.tipo != TIPO or anterior.version != VERSION or anterior.huella != huella:
            raise ValidationError("La clave ya identifica otra propuesta o un contenido diferente.")
        return anterior, False
    persona = get_object_or_404(Afiliado.objects.select_for_update(),
                                pk=original["afiliado"], financiador=financiador)
    if original["rectifica"] is not None:
        antecedente = consultar(financiador=financiador, novedad_id=original["rectifica"])
        if antecedente.resumen["afiliado"] != persona.pk:
            raise ValidationError("La rectificación debe referir a la misma persona del financiador.")
    obj = Importacion.objects.create(financiador=financiador, tipo=TIPO, version=VERSION,
        clave=clave, huella=huella, creado_por=usuario, estado="pendiente",
        resumen={k: original[k] for k in ("afiliado", "fuente", "referencia")},
        filas=[{"original": original, "persona_inicial": _persona(persona), "revision": 1,
                "historia": [{"accion": "registrar", "motivo": original["motivo"],
                              "usuario": usuario.pk, "fecha": timezone.now().isoformat()}]}])
    auditar(usuario, "crear_novedad", obj.pk, financiador=financiador)
    return obj, True


@transaction.atomic
def resolver(*, financiador, usuario, novedad_id, **decision):
    Financiador.objects.select_for_update().get(pk=financiador.pk)
    requerir_financiador(usuario, financiador.pk, escritura=True)
    obj = get_object_or_404(Importacion.objects.select_for_update(), pk=novedad_id,
                            financiador=financiador, tipo=TIPO, version=VERSION)
    fila = obj.filas[0]
    firma = _huella(decision)
    if obj.estado != "pendiente":
        if fila.get("decision_huella") == firma:
            return obj
        raise ValidationError("La propuesta ya fue resuelta; su decisión anterior se conserva.")
    persona = get_object_or_404(Afiliado.objects.select_for_update(),
        pk=fila["original"]["afiliado"], financiador=financiador)
    if decision["revision"] != fila["revision"] or decision["revision_padron"] != persona.revision:
        raise ValidationError("La propuesta o el padrón cambiaron. Compare nuevamente antes de resolver.")
    comparacion = comparar(obj)
    if decision["accion"] == "conciliar" and comparacion["conflictos"] and not decision["confirmar_conflictos"]:
        raise ValidationError("Revise y confirme expresamente los conflictos antes de conciliar.")
    obj.estado = "conciliada" if decision["accion"] == "conciliar" else "descartada"
    fila["revision"] += 1
    fila["decision_huella"] = firma
    fila["historia"].append({"accion": decision["accion"], "motivo": decision["motivo"],
        "usuario": usuario.pk, "fecha": timezone.now().isoformat(),
        "comparacion": comparacion, "efectos_aplicados": False})
    obj.save(update_fields=["estado", "filas"])
    auditar(usuario, "resolver_novedad", obj.pk, financiador=financiador)
    return obj


@transaction.atomic
def habilitar_cobertura(*, financiador, usuario, novedad_id, **decision):
    """Aplica una decisión explícita y única sobre cobertura, desde una novedad conciliada."""
    Financiador.objects.select_for_update(no_key=True).get(pk=financiador.pk)
    requerir_financiador(usuario, financiador.pk, escritura=True)
    obj = get_object_or_404(Importacion.objects.select_for_update(), pk=novedad_id,
                            financiador=financiador, tipo=TIPO, version=VERSION)
    fila = obj.filas[0]
    firma = _huella(decision)
    operacion_previa = fila.get("habilitacion_cobertura")
    if operacion_previa:
        if operacion_previa["decision_huella"] == firma:
            return obj
        raise ValidationError("La novedad ya tiene una decisión de cobertura diferente; no se aplicó otro cambio.")
    if obj.estado != "conciliada":
        raise ValidationError("Sólo una novedad conciliada admite una decisión explícita de cobertura.")
    if decision["revision"] != fila["revision"]:
        raise ValidationError("La novedad cambió. Consultala nuevamente antes de decidir la cobertura.")

    original = fila["original"]
    persona = get_object_or_404(Afiliado.objects.select_for_update(),
        pk=original["afiliado"], financiador=financiador)
    if obj.resumen.get("afiliado") != persona.pk:
        raise ValidationError("La identidad de la novedad no coincide con la persona del financiador.")
    if decision["revision_padron"] != persona.revision:
        raise ValidationError("El padrón cambió. Compará nuevamente antes de decidir la cobertura.")

    comparacion = comparar(obj)
    if comparacion["conflictos"]:
        raise ValidationError("La novedad tiene conflictos pendientes de revisión; no se aplicó la decisión.")
    rectificada = any(
        fila_novedad[0]["original"].get("rectifica") == obj.pk
        for fila_novedad in Importacion.objects.filter(
            financiador=financiador, tipo=TIPO, version=VERSION,
        ).exclude(pk=obj.pk).values_list("filas", flat=True)
    )
    if rectificada:
        raise ValidationError("La novedad fue rectificada; no se aplicó la decisión.")

    valor_anterior = persona.cobertura_habilitada
    valor_nuevo = decision["cobertura_habilitada"]
    resultado = "sin_cambios"
    historial_id = None
    if valor_anterior != valor_nuevo:
        from .padron import editar_ficha

        persona = editar_ficha(afiliado=persona, usuario=usuario,
            entrada={"revision": decision["revision_padron"],
                     "motivo": decision["motivo"],
                     "cobertura_habilitada": valor_nuevo},
            origen="novedad", lote=obj)
        historial_id = HistorialAfiliacion.objects.filter(
            afiliado_id=persona.pk, lote=obj,
        ).order_by("-pk").values_list("pk", flat=True).first()
        resultado = "cambiada"

    fila["revision"] += 1
    fila["habilitacion_cobertura"] = {
        "decision_huella": firma,
        "cobertura_habilitada": valor_nuevo,
        "resultado": resultado,
        "historial_id": historial_id,
        "registrado_por": autor_real(usuario).pk,
        "registrado": timezone.now().isoformat(),
        "motivo": decision["motivo"],
        "revision_padron": decision["revision_padron"],
    }
    obj.filas = [fila, *obj.filas[1:]]
    obj.save(update_fields=["filas"])
    auditar(usuario, "habilitar_cobertura_desde_novedad", obj.pk,
            financiador=financiador, motivo=resultado)
    return obj
