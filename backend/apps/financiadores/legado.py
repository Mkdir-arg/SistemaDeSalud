"""Diagnóstico de texto legado: sólo SELECT, nunca acredita una afiliación.

Los IDs del resultado sirven para una revisión dentro del sistema. Ni el documento,
ni nombres, números de afiliado o el texto libre se trasladan al reporte.
"""
from collections import defaultdict
import hashlib
import json
import unicodedata

from django.core.exceptions import ValidationError
from django.db.models import F
from django.utils import timezone

from apps.registros.models import Ciudadano, normalizar_documento
from .models import Afiliado, Financiador, HistorialAfiliacion, Plan, VinculoCiudadano
from .vigencias import convenios_vigentes


CRITERIO = "documento_y_alias_exacto_v1"
CLASIFICACIONES = (
    "sin_dato", "sin_documento", "identidad_en_conflicto", "sin_padron_verificado",
    "ambiguo", "plan_desconocido", "sin_convenio", "candidato_unico",
)
DOCUMENTOS_NN = frozenset({"NN", "SINDOCUMENTO", "INDOCUMENTADO", "DESCONOCIDO"})


def normalizar_alias(valor):
    """No quita tildes, signos ni palabras: una semejanza no es un alias revisado."""
    return " ".join(unicodedata.normalize("NFKC", valor).casefold().split())


def validar_aliases(datos):
    """Mapa explícito texto -> IDs; rechaza ambigüedades sin imprimir el texto."""
    if not isinstance(datos, dict):
        raise ValidationError("El archivo de alias debe contener un objeto JSON.")
    aliases = {}
    for texto, destino in datos.items():
        if not isinstance(texto, str) or not texto.strip() or len(texto) > 120:
            raise ValidationError("Cada alias debe tener un texto de hasta 120 caracteres.")
        clave = normalizar_alias(texto)
        if clave in aliases:
            raise ValidationError("Hay alias repetidos después de normalizar mayúsculas y espacios.")
        if not isinstance(destino, dict) or set(destino) - {"financiador", "plan"}:
            raise ValidationError("Cada alias admite sólo financiador y plan opcional.")
        financiador, plan = destino.get("financiador"), destino.get("plan")
        if type(financiador) is not int or financiador <= 0:
            raise ValidationError("Cada alias requiere un ID de financiador válido.")
        if plan is not None and (type(plan) is not int or plan <= 0):
            raise ValidationError("El plan del alias debe ser un ID válido o null.")
        aliases[clave] = {"financiador": financiador, "plan": plan}
    financiadores = set(Financiador.objects.filter(
        pk__in={a["financiador"] for a in aliases.values()},
    ).values_list("pk", flat=True))
    planes = dict(Plan.objects.filter(
        pk__in={a["plan"] for a in aliases.values() if a["plan"] is not None},
    ).values_list("pk", "financiador_id"))
    for destino in aliases.values():
        if destino["financiador"] not in financiadores:
            raise ValidationError("Un alias refiere a un financiador inexistente.")
        if destino["plan"] is not None and planes.get(destino["plan"]) != destino["financiador"]:
            raise ValidationError("Un plan del archivo no pertenece al financiador indicado o no existe.")
    return aliases


def huella_aliases(aliases):
    """Permite identificar el mapeo revisado sin copiar sus textos al reporte."""
    contenido = json.dumps(aliases, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(contenido.encode("utf-8")).hexdigest()


def _clasificar(ciudadano, *, aliases, por_documento, conflictos, vinculados, convenios, fecha):
    documento = normalizar_documento(ciudadano["documento"])
    texto = normalizar_alias(ciudadano["obra_social"])
    alias = aliases.get(texto)
    encontrados = por_documento.get(documento, [])
    elegidos = [a for a in encontrados if not alias or a.financiador_id == alias["financiador"]]
    criterios = ["alias_explicito" if alias else "texto_sin_alias_revisado"] if texto else []
    if encontrados:
        criterios.append("coincidencia_documental")
    resultado = {
        "ciudadano": ciudadano["id"], "clasificacion": "sin_dato", "criterios": criterios,
        "alias": alias,
        "afiliados": [
            {"id": a.pk, "financiador": a.financiador_id, "plan": a.plan_id}
            for a in elegidos
        ],
    }

    def terminar(clasificacion, criterio):
        resultado["clasificacion"] = clasificacion
        criterios.append(criterio)
        return resultado

    if not texto:
        # El diagnóstico del texto no rellena una declaración ausente.
        return terminar("sin_dato", "texto_ausente")
    if not documento or documento in DOCUMENTOS_NN:
        return terminar("sin_documento", "documento_ausente_o_nn")
    ids_corregidos = conflictos.get(documento, set())
    ids_vinculados = {
        a.pk for a in vinculados.get(ciudadano["id"], [])
        if normalizar_documento(a.documento) != documento
    }
    if ciudadano["documento"] != documento or ids_corregidos or ids_vinculados:
        resultado["afiliados_en_conflicto"] = sorted(ids_corregidos | ids_vinculados)
        return terminar("identidad_en_conflicto", "documento_no_normalizado_o_corregido")
    vigentes = [a for a in elegidos if a.financiador.activo and not a.finalizado_en and a.desde <= fecha]
    if not vigentes:
        return terminar("sin_padron_verificado", "sin_afiliacion_documental_vigente")
    if len(vigentes) > 1:
        return terminar("ambiguo", "multiples_afiliaciones_vigentes")
    candidato = vigentes[0]
    if (not candidato.plan_id or not candidato.plan.activo
            or candidato.plan.financiador_id != candidato.financiador_id
            or (alias and alias["plan"] is not None and alias["plan"] != candidato.plan_id)):
        return terminar("plan_desconocido", "plan_ausente_inactivo_o_no_coincidente")
    if candidato.financiador_id not in convenios:
        return terminar("sin_convenio", "sin_convenio_vigente_en_hospital")
    resultado["candidato"] = candidato.pk
    return terminar("candidato_unico", "requiere_revision_no_acredita_cobertura")


def diagnosticar(*, institucion_id, hasta_pk, aliases=None, lote=250, corte=None):
    """Itera ciudadanos por PK y carga sólo identidades relacionadas con cada lote.

    El límite superior evita incorporar altas posteriores al inicio. No es una
    instantánea transaccional de un padrón en edición: aplicar cualquier resultado
    requiere revalidar la fuente. El comando no ofrece operación de aplicación.
    """
    if type(lote) is not int or not 1 <= lote <= 500:
        raise ValidationError("El lote debe estar entre 1 y 500.")
    corte = corte or timezone.now()
    fecha = timezone.localdate(corte)
    aliases = aliases or {}
    convenios = set(convenios_vigentes(corte).filter(
        institucion_id=institucion_id, estado="activo",
    ).values_list("financiador_id", flat=True))
    ultimo = 0
    while True:
        ciudadanos = list(Ciudadano.objects.filter(
            institucion_id=institucion_id, pk__gt=ultimo, pk__lte=hasta_pk,
        ).order_by("pk").values("id", "documento", "obra_social")[:lote])
        if not ciudadanos:
            return
        documentos = {
            normalizar_documento(c["documento"]) for c in ciudadanos
            if normalizar_documento(c["documento"]) not in DOCUMENTOS_NN
        } - {""}
        por_documento = defaultdict(list)
        for afiliado in Afiliado.objects.filter(documento__in=documentos).select_related(
            "financiador", "plan",
        ).only(
            "id", "documento", "financiador_id", "financiador__activo", "plan_id",
            "plan__activo", "plan__financiador_id", "desde", "finalizado_en",
        ).order_by("pk"):
            por_documento[afiliado.documento].append(afiliado)
        conflictos = defaultdict(set)
        for documento, afiliado_id in HistorialAfiliacion.objects.filter(
            documento__in=documentos,
        ).exclude(afiliado__documento=F("documento")).values_list("documento", "afiliado_id").distinct():
            conflictos[documento].add(afiliado_id)
        vinculados = defaultdict(list)
        for vinculo in VinculoCiudadano.objects.filter(
            ciudadano_id__in=[c["id"] for c in ciudadanos],
        ).select_related("afiliado").only("ciudadano_id", "afiliado_id", "afiliado__documento").order_by("pk"):
            vinculados[vinculo.ciudadano_id].append(vinculo.afiliado)
        for ciudadano in ciudadanos:
            yield _clasificar(
                ciudadano, aliases=aliases, por_documento=por_documento,
                conflictos=conflictos, vinculados=vinculados, convenios=convenios, fecha=fecha,
            )
        ultimo = ciudadanos[-1]["id"]
