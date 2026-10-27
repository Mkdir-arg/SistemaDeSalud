"""Consulta administrativa compartida por listado y XLSX, sin ampliar permisos.

El llamador autoriza el financiador antes de invocar consultar_padron. La consulta
se construye aquí, nunca a partir de un queryset o un scope recibido por URL.
"""
import json
import re
import unicodedata
from pathlib import Path

from django.db.models import Case, CharField, F, Q, Value, When
from django.utils import timezone
from rest_framework import serializers

from apps.registros.models import normalizar_documento
from . import models as m
from .padron import estado_administrativo
from .padron_api import filtrar_padron


COLUMNAS_PADRON = {c["key"]: c for c in json.loads(Path(__file__).with_name("padron_columnas.json").read_text(encoding="utf-8"))}
COLUMNAS_PREDETERMINADAS = tuple(k for k, c in COLUMNAS_PADRON.items() if c.get("default"))
_LEGACY = {"plan", "estado", "derecho", "documento", "search", "estado_administrativo", "regimen", "alta_desde", "alta_hasta", "baja_desde", "baja_hasta"}
_TRANSPORTE = {"ordering", "columnas", "page", "page_size", "formato"}
_ERROR = "Consulta de padrón inválida. Revisá los filtros, el orden y las columnas."
_LETRAS_BUSQUEDA = {
    "a": "[aáàâäãå]", "e": "[eéèêë]", "i": "[iíìîï]",
    "o": "[oóòôöõ]", "u": "[uúùûü]", "n": "[nñ]", "c": "[cç]",
}


def _patron_nombre(texto):
    """Equivalencias de letras latinas, con símbolos literales y sin extensión SQL."""
    letras = unicodedata.normalize("NFD", texto).casefold()
    return "".join(
        _LETRAS_BUSQUEDA.get(letra, re.escape(letra)) + ("[\u0300-\u036f]*" if letra.isalpha() else "")
        for letra in letras if not unicodedata.combining(letra)
    )


def _invalida():
    raise serializers.ValidationError(_ERROR)


def validar_columnas_padron(valor=None):
    if valor is None:
        return COLUMNAS_PREDETERMINADAS
    if not isinstance(valor, str):
        _invalida()
    claves = tuple(valor.split(","))
    if not claves or len(set(claves)) != len(claves) or any(k not in COLUMNAS_PADRON for k in claves):
        _invalida()
    if any(c.get("required") and k not in claves for k, c in COLUMNAS_PADRON.items()):
        _invalida()
    return claves


def _campo(clave):
    if clave == "cobertura_habilitada":
        return "_padron_habilitada"
    return {"plan": "plan__nombre", "plan_tipo": "plan__tipo", "derecho": "_padron_derecho", "estado_administrativo": "_padron_administrativo", "titular": "titular_id"}.get(clave, clave)


def _anotar(qs, claves):
    hoy = timezone.localdate()
    if "cobertura_habilitada" in claves:
        qs = qs.annotate(_padron_habilitada=Case(
            When(cobertura_habilitada=True, then=Value("true")),
            default=Value("false"), output_field=CharField(),
        ))
    if "derecho" in claves:
        qs = qs.annotate(_padron_derecho=Case(
            When(finalizado_en__isnull=False, then=Value("finalizadas")),
            When(cobertura_habilitada=False, then=Value("administrativas")),
            When(desde__gt=hoy, then=Value("futuras")),
            default=Value("vigentes"), output_field=CharField(),
        ))
    if "estado_administrativo" in claves:
        qs = qs.annotate(_padron_administrativo=Case(
            When(baja_efectiva__gt=hoy, then=Value("baja_programada")),
            When(baja_efectiva__lte=hoy, then=Value("baja_administrativa")),
            When(estado_tramite="completo", then=Value("activo")),
            default=Value("en_tramite"), output_field=CharField(),
        ))
    return qs


def _filtros_admitidos():
    admitidos = {}
    for clave, col in COLUMNAS_PADRON.items():
        if col["type"] in ("date", "datetime"):
            for extremo in ("desde", "hasta"):
                admitidos[f"flt_{clave}_{extremo}"] = (clave, extremo)
        else:
            admitidos[f"flt_{clave}"] = (clave, "valor")
        if col.get("nullable"):
            admitidos[f"flt_{clave}_vacio"] = (clave, "vacio")
    return admitidos


_FILTROS = _filtros_admitidos()


def consultar_padron(*, financiador, parametros):
    """Devuelve queryset scoped, filtrado y ordenado; no lo evalúa ni pagina."""
    try:
        return _consultar_padron(financiador=financiador, parametros=parametros)
    except serializers.ValidationError:
        # Ni los valores rechazados ni nombres de recursos protegidos se reflejan.
        _invalida()


def _consultar_padron(*, financiador, parametros):
    if financiador is None or not financiador.pk:
        _invalida()
    if set(parametros) - _LEGACY - _TRANSPORTE - set(_FILTROS):
        _invalida()
    if hasattr(parametros, "getlist") and any(len(parametros.getlist(k)) != 1 for k in parametros):
        _invalida()
    validar_columnas_padron(parametros.get("columnas"))
    for clave in ("page", "page_size"):
        if parametros.get(clave):
            serializers.IntegerField(min_value=1, **({"max_value": 200} if clave == "page_size" else {})).run_validation(parametros[clave])
    orden = parametros.get("ordering", "")
    clave_orden = orden.removeprefix("-")
    if orden and clave_orden not in COLUMNAS_PADRON:
        _invalida()
    qs = m.Afiliado.objects.filter(financiador=financiador).select_related("plan", "geografia__provincia", "geografia__partido", "geografia__localidad", "geografia_laboral__provincia", "geografia_laboral__partido", "geografia_laboral__localidad")
    if parametros.get("plan"):
        qs = qs.filter(plan_id=serializers.IntegerField(min_value=1).run_validation(parametros["plan"]))
    derecho = parametros.get("derecho") or parametros.get("estado")
    if derecho:
        derecho = serializers.ChoiceField(choices=["vigentes", "finalizadas", "futuras", "administrativas", "todos"]).run_validation(derecho)
        if derecho != "todos":
            qs = _anotar(qs, {"derecho"}).filter(_padron_derecho=derecho)
    if parametros.get("documento"):
        qs = qs.filter(documento=normalizar_documento(parametros["documento"]))
    if parametros.get("search"):
        texto = serializers.CharField(max_length=255).run_validation(parametros["search"])
        # Cada palabra debe coincidir en algún campo; nombre y apellido pueden
        # estar separados o en distinto orden. El filtrado sigue siendo SQL.
        for palabra in texto.split():
            condicion = Q(numero__icontains=palabra) | Q(cuil__icontains=palabra)
            patron = _patron_nombre(palabra)
            if patron:
                condicion |= Q(nombre__iregex=patron) | Q(nombres__iregex=patron) | Q(apellidos__iregex=patron)
            documento = normalizar_documento(palabra)
            if documento:
                # Un documento vacío produciría icontains="" y devolvería todo.
                condicion |= Q(documento__icontains=documento)
            qs = qs.filter(condicion)
    qs = filtrar_padron(qs, parametros)
    activos = [(k, *_FILTROS[k]) for k in parametros if k in _FILTROS and parametros.get(k) != ""]
    qs = _anotar(qs, {clave_orden, *(clave for _, clave, _ in activos)})
    rangos = {}
    for param, clave, operacion in activos:
        col = COLUMNAS_PADRON[clave]
        campo = "plan_id" if clave == "plan" else _campo(clave)
        valor = parametros[param]
        if operacion == "vacio":
            vacio = serializers.ChoiceField(choices=["true", "false"]).run_validation(valor) == "true"
            condicion = Q(**{f"{campo}__isnull": True})
            if col["type"] in ("text", "choice"):
                condicion |= Q(**{campo: ""})
            qs = qs.filter(condicion) if vacio else qs.exclude(condicion)
        elif operacion in ("desde", "hasta"):
            valor = serializers.DateField().run_validation(valor)
            rangos.setdefault(clave, {})[operacion] = valor
            fecha_campo = f"{campo}__date" if col["type"] == "datetime" else campo
            qs = qs.filter(**{f"{fecha_campo}__{'gte' if operacion == 'desde' else 'lte'}": valor})
        elif col["type"] == "relation":
            qs = qs.filter(**{campo: serializers.IntegerField(min_value=1).run_validation(valor)})
        elif col["type"] == "choice":
            qs = qs.filter(**{campo: serializers.ChoiceField(choices=col["options"]).run_validation(valor)})
        else:
            maximo = m.Afiliado._meta.get_field(clave).max_length
            valor = serializers.CharField(max_length=maximo).run_validation(valor)
            qs = qs.filter(**{f"{campo}__icontains": valor})
    for rango in rangos.values():
        if "desde" in rango and "hasta" in rango and rango["hasta"] < rango["desde"]:
            _invalida()
    if not orden:
        return qs.order_by("pk")
    expresion = F(_campo(clave_orden))
    return qs.order_by(expresion.desc(nulls_last=True) if orden.startswith("-") else expresion.asc(nulls_last=True), "pk")


def valor_columna_padron(afiliado, clave):
    """Proyección administrativa tipada; XLSX protege las cadenas al escribirlas."""
    if clave not in COLUMNAS_PADRON:
        _invalida()
    if clave in ("provincia", "partido", "localidad") and afiliado.geografia_id:
        dato = afiliado.geografia.datos()[clave]
        if dato["origen"] == "manual" and dato["nombre"]:
            return f"{dato['nombre']} · Manual · sin verificar"
    if clave == "domicilio_laboral" and afiliado.geografia_laboral_id:
        from apps.geografia.servicios import texto_territorial
        return " · ".join(v for v in (afiliado.domicilio_laboral, texto_territorial(afiliado, "geografia_laboral")) if v)
    if clave == "plan":
        return afiliado.plan.nombre if afiliado.plan_id else None
    if clave == "plan_tipo":
        valor = afiliado.plan.tipo if afiliado.plan_id else ""
    elif clave == "derecho":
        valor = "finalizadas" if afiliado.finalizado_en else "administrativas" if not afiliado.cobertura_habilitada else "futuras" if afiliado.desde > timezone.localdate() else "vigentes"
    elif clave == "estado_administrativo":
        valor = estado_administrativo(afiliado)
    elif clave == "titular":
        return afiliado.titular_id
    elif clave == "cobertura_habilitada":
        valor = "true" if afiliado.cobertura_habilitada else "false"
    else:
        valor = getattr(afiliado, clave)
    return COLUMNAS_PADRON[clave].get("options", {}).get(valor, valor)
