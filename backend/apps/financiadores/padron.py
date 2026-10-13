"""Ficha administrativa ampliada: sin efectos sobre derechos ni integraciones externas."""
from datetime import date
import re

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import APIException

from apps.registros.models import normalizar_documento
from apps.simulacion.contexto import autor_real
from . import models as m
from .permisos import requerir_financiador, requerir_padron_protegido
from .services import auditar


CAMPOS_GENERALES = (
    "tipo_documento", "cuil", "nombres", "apellidos", "sexo", "fecha_nacimiento",
    "nacionalidad", "estado_civil", "calle", "altura", "piso", "departamento",
    "codigo_postal", "localidad", "partido", "provincia", "telefono", "celular", "email",
    "regimen", "empleador", "actividad_laboral", "cuit_empleador", "domicilio_laboral",
    "telefono_laboral", "email_laboral", "subsidio_desde", "subsidio_hasta",
    "alta_administrativa", "delegacion", "estado_tramite", "credencial_tipo", "credencial_fecha",
    "solicitud_baja", "baja_efectiva", "fin_prestacional_informado", "motivo_baja", "causa_baja",
    "titular", "parentesco",
)
CAMPOS_EDITABLES = ("numero", "documento", "nombre", "plan", *CAMPOS_GENERALES)
CAMPOS_SALUD = ("cud", "cud_numero", "cud_presentado_en", "cud_vencimiento", "cud_referencia", "dbt", "cronicas", "parentesco_sensible")
CAMPOS_COBRANZA = ("situacion", "fuente", "informado_en", "modalidad", "dia_vencimiento", "cupon", "cbu", "cuit_titular", "titular_cuenta", "emisor_tarjeta", "banco", "proveedor_cupon")
CAMPOS_LEGAJO = ("tipo", "estado", "presentado_en", "verificado_en", "vence_en", "referencia")


class ConflictoPadron(APIException):
    status_code = 409

    def __init__(self, revision):
        super().__init__({"detail": "El registro cambió. Recargá antes de guardar."})
        self.detail["revision"] = revision


def comprobar_revision(objeto, revision):
    if objeto.revision != revision:
        raise ConflictoPadron(objeto.revision)


def validar_entrada_servicio(entrada, campos):
    if set(entrada) - set(campos) - {"revision", "motivo"}:
        raise ValidationError("La petición contiene campos no admitidos para este recurso.")
    if not isinstance(entrada.get("revision"), int) or isinstance(entrada["revision"], bool) or entrada["revision"] < 1:
        raise ValidationError("Indicá la revisión actual del registro.")
    motivo = entrada.get("motivo")
    if not isinstance(motivo, str) or not motivo.strip() or len(motivo) > 255:
        raise ValidationError("Registrá un motivo de hasta 255 caracteres.")


def validar_cuit(valor, campo="cuil"):
    if not valor:
        return
    if len(valor) != 11 or not valor.isascii() or not valor.isdecimal() or not int(valor):
        raise ValidationError({campo: "Debe tener 11 dígitos, conservando sus ceros."})
    pesos = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)
    verificador = (11 - sum(int(n) * p for n, p in zip(valor[:10], pesos)) % 11) % 11
    if verificador == 10 or verificador != int(valor[-1]):
        raise ValidationError({campo: "Dígito verificador inválido."})


def validar_cbu(valor):
    if not valor:
        return
    if len(valor) != 22 or not valor.isascii() or not valor.isdecimal() or not int(valor):
        raise ValidationError({"cbu": "El CBU debe tener 22 dígitos."})
    for bloque, pesos in ((valor[:8], (7, 1, 3, 9, 7, 1, 3)), (valor[8:], (3, 9, 7, 1, 3, 9, 7, 1, 3, 9, 7, 1, 3))):
        if (10 - sum(int(n) * p for n, p in zip(bloque[:-1], pesos)) % 10) % 10 != int(bloque[-1]):
            raise ValidationError({"cbu": "Dígito verificador de CBU inválido."})


def validar_generales(obj):
    validar_cuit(obj.cuil)
    validar_cuit(obj.cuit_empleador, "cuit_empleador")
    if obj.cuil and obj.tipo_documento == "DNI":
        if not obj.documento.isascii() or not obj.documento.isdecimal() or len(obj.documento) > 8 or obj.cuil[2:10] != obj.documento.zfill(8):
            raise ValidationError({"cuil": "El CUIL no coincide con el DNI. No se fusionan identidades."})
    if obj.fecha_nacimiento and obj.fecha_nacimiento > timezone.localdate():
        raise ValidationError({"fecha_nacimiento": "El nacimiento no puede ser futuro."})
    for inicio, fin in (("subsidio_desde", "subsidio_hasta"), ("solicitud_baja", "baja_efectiva"), ("baja_efectiva", "fin_prestacional_informado")):
        if getattr(obj, inicio) and getattr(obj, fin) and getattr(obj, fin) < getattr(obj, inicio):
            raise ValidationError({fin: f"No puede anteceder {inicio}."})
    if obj.baja_efectiva and not obj.motivo_baja.strip():
        raise ValidationError({"motivo_baja": "Registrá un motivo administrativo de baja."})
    if bool(obj.credencial_tipo) != bool(obj.credencial_fecha):
        raise ValidationError("La credencial externa requiere tipo y fecha conjuntamente.")
    if bool(obj.titular_id) != bool(obj.parentesco):
        raise ValidationError("Indicá titular y parentesco conjuntamente; ambos vacíos para un titular.")
    if obj.estado_tramite == "completo":
        documentos = obj.legajo.all() if obj.pk else m.DocumentoLegajo.objects.none()
        if not obj.credencial_tipo or not documentos.exists() or documentos.exclude(estado__in=["verificado", "exento"]).exists():
            raise ValidationError({"estado_tramite": "Completar requiere credencial informada y documentación registrada verificada o exenta."})


def estado_administrativo(obj):
    if obj.baja_efectiva:
        return "baja_programada" if obj.baja_efectiva > timezone.localdate() else "baja_administrativa"
    return "activo" if obj.estado_tramite == "completo" else "en_tramite"


def _json(valor):
    if isinstance(valor, date):
        return valor.isoformat()
    return valor


def cambios(obj, entrada):
    return {campo: {"anterior": _json(getattr(obj, campo)), "nuevo": _json(valor)} for campo, valor in entrada.items() if getattr(obj, campo) != valor}


def registrar_historial(obj, usuario, delta, motivo, origen="manual", lote=None):
    m.HistorialAfiliacion.objects.create(
        afiliado=obj, numero=obj.numero, documento=obj.documento, plan=obj.plan,
        desde=obj.desde, registrado_por=autor_real(usuario), cambios=delta,
        motivo=motivo, origen=origen, lote=lote,
    )
    auditar(usuario, "editar_ficha_padron", obj.pk, financiador=obj.financiador, motivo="Campos: " + ", ".join(delta))


@transaction.atomic
def registrar_ficha(*, financiador, usuario, basicos, nuevos, revision=None, motivo="Alta de padrón", solo_crear=False):
    """Alta ampliada atómica; el POST legado conserva su contrato incremental."""
    from .services import registrar_afiliado
    if "titular" in nuevos:
        m.Financiador.objects.select_for_update().get(pk=financiador.pk)
    anterior = m.Afiliado.objects.select_for_update().filter(financiador=financiador, documento=normalizar_documento(basicos["documento"])).first()
    if anterior and nuevos and not solo_crear:
        if revision is None:
            raise ValidationError("Para actualizar una ficha existente con campos nuevos indicá revisión y motivo o usá PATCH.")
        comprobar_revision(anterior, revision)
    obj = registrar_afiliado(financiador=financiador, usuario=usuario, motivo=motivo, solo_crear=solo_crear, **basicos)
    if nuevos:
        obj = editar_ficha(afiliado=obj, usuario=usuario, entrada={**nuevos, "revision": obj.revision, "motivo": motivo})
    return obj


def campos_entrada(modelo, campos, data, controles=("revision", "motivo"), requerido=True):
    """DRF ignora claves desconocidas por defecto; aquí se rechazan explícitamente."""
    if not isinstance(data, dict):
        raise serializers.ValidationError("Se espera un objeto JSON.")
    desconocidos = set(data) - set(campos) - set(controles)
    if desconocidos:
        # No repetir contenido ni nombres aportados por clientes en auditoría.
        raise serializers.ValidationError("La petición contiene campos no admitidos para este recurso.")
    for campo in ("documento", "numero", "cuil", "cuit_empleador", "cbu", "cuit_titular"):
        if campo in data and not isinstance(data[campo], str):
            raise serializers.ValidationError({campo: "Debe ser texto para conservar sus ceros iniciales."})
    meta = type("Meta", (), {"model": modelo, "fields": list(campos)})
    clase = type("EntradaPadron", (serializers.ModelSerializer,), {"Meta": meta})
    serializer = clase(data={k: v for k, v in data.items() if k in campos}, partial=True)
    # No construir querysets de otras organizaciones al validar claves relacionadas.
    for campo in ("titular", "plan"):
        if campo in serializer.fields:
            serializer.fields[campo] = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    serializer.is_valid(raise_exception=True)
    entrada = dict(serializer.validated_data)
    if requerido:
        control = serializers.Serializer(data={k: data[k] for k in controles if k in data})
        control.fields["revision"] = serializers.IntegerField(min_value=1)
        control.fields["motivo"] = serializers.CharField(max_length=255, allow_blank=False)
        control.is_valid(raise_exception=True)
        entrada.update(control.validated_data)
    return entrada


@transaction.atomic
def editar_ficha(*, afiliado, usuario, entrada, origen="manual", lote=None):
    validar_entrada_servicio(entrada, CAMPOS_EDITABLES)
    # El lock del financiador serializa cambios estructurales de familia incluso
    # sin integrantes previos; luego se toman filas por PK en orden estable.
    if "titular" in entrada:
        m.Financiador.objects.select_for_update().get(pk=afiliado.financiador_id)
    requerir_financiador(usuario, afiliado.financiador_id, escritura=True)
    titular_id = entrada.get("titular")
    ids = sorted({afiliado.pk, titular_id} - {None})
    bloqueados = {x.pk: x for x in m.Afiliado.objects.select_for_update().filter(financiador_id=afiliado.financiador_id, pk__in=ids).order_by("pk")}
    obj = bloqueados[afiliado.pk]
    entrada = dict(entrada)
    comprobar_revision(obj, entrada.pop("revision"))
    motivo = entrada.pop("motivo")
    for relacion in ("plan", "titular"):
        if relacion in entrada:
            entrada[relacion + "_id"] = entrada.pop(relacion)
    if "documento" in entrada:
        entrada["documento"] = normalizar_documento(entrada["documento"])
    if "plan_id" in entrada and obj.finalizado_en:
        raise ValidationError({"plan": "La afiliación está finalizada. Reactivala expresamente antes de cambiar el plan."})
    if entrada.get("plan_id") is not None and "plan_id" in entrada:
        plan = m.Plan.objects.select_for_update().filter(pk=entrada["plan_id"], financiador=obj.financiador).first()
        if not plan or not plan.activo:
            raise ValidationError({"plan": "El plan debe estar activo y pertenecer al financiador."})
    delta = cambios(obj, entrada)
    for campo, valor in entrada.items():
        setattr(obj, campo, valor)
    if obj.titular_id:
        titular = bloqueados.get(obj.titular_id) or m.Afiliado.objects.filter(pk=obj.titular_id, financiador=obj.financiador).first()
        if not titular or titular.pk == obj.pk or titular.titular_id or obj.familiares.exists():
            raise ValidationError({"titular": "La familia debe pertenecer al mismo financiador y tener un único nivel, sin ciclos."})
    validar_generales(obj)
    obj.full_clean()
    if delta:
        obj.revision += 1
        obj.save()
        registrar_historial(obj, usuario, delta, motivo, origen, lote)
    return obj


@transaction.atomic
def editar_protegido(*, afiliado, usuario, bloque, entrada):
    validar_entrada_servicio(entrada, CAMPOS_SALUD if bloque == "salud" else CAMPOS_COBRANZA)
    m.MembresiaFinanciador.objects.select_for_update().filter(usuario=usuario, financiador_id=afiliado.financiador_id).first()
    requerir_padron_protegido(usuario, afiliado.financiador_id, bloque, escritura=True)
    afiliado = m.Afiliado.objects.select_for_update().get(pk=afiliado.pk)
    modelo = m.SaludPadron if bloque == "salud" else m.CobranzaPadron
    obj = modelo.objects.filter(afiliado=afiliado).first() or modelo(afiliado=afiliado)
    entrada = dict(entrada)
    comprobar_revision(obj, entrada.pop("revision"))
    motivo = entrada.pop("motivo")
    delta = cambios(obj, entrada)
    for campo, valor in entrada.items():
        setattr(obj, campo, valor)
    if bloque == "cobranza":
        validar_cbu(obj.cbu)
        validar_cuit(obj.cuit_titular, "cuit_titular")
        if obj.emisor_tarjeta and (not any(c.isalpha() for c in obj.emisor_tarjeta) or re.search(r"(?:\d[\s-]*){12,}|\bcvv\b", obj.emisor_tarjeta, re.IGNORECASE)):
            raise ValidationError({"emisor_tarjeta": "Informá sólo el nombre del emisor; no se almacenan números ni códigos de tarjeta."})
        if obj.situacion != "sin_informar" and (not obj.fuente.strip() or not obj.informado_en):
            raise ValidationError("La situación informada requiere fuente y fecha de información.")
        if obj.informado_en and obj.informado_en > timezone.localdate():
            raise ValidationError("La fecha de información no puede ser futura.")
        if obj.modalidad == "debito_cbu" and (not obj.cbu or not obj.cuit_titular or not obj.titular_cuenta):
            raise ValidationError("El débito informado requiere CBU, CUIT y titular de cuenta.")
    else:
        if obj.cud_presentado_en and obj.cud_presentado_en > timezone.localdate():
            raise ValidationError("La presentación del CUD no puede ser futura.")
        if obj.cud_presentado_en and obj.cud_vencimiento and obj.cud_vencimiento < obj.cud_presentado_en:
            raise ValidationError("El vencimiento del CUD no puede anteceder su presentación.")
    obj.full_clean()
    if delta:
        obj.revision += 1
        obj.save()
        m.HistorialPadronProtegido.objects.create(afiliado=afiliado, bloque=bloque, revision=obj.revision, cambios=delta, motivo=motivo, registrado_por=autor_real(usuario))
        # Sin motivo, nombres de campos ni valores del bloque en eventos generales.
        auditar(usuario, "editar_padron_protegido", afiliado.pk, financiador=afiliado.financiador)
    return obj


@transaction.atomic
def guardar_legajo(*, afiliado, usuario, entrada, documento_id=None):
    validar_entrada_servicio(entrada, CAMPOS_LEGAJO)
    requerir_financiador(usuario, afiliado.financiador_id, escritura=True)
    obj = m.Afiliado.objects.select_for_update().get(pk=afiliado.pk)
    entrada = dict(entrada)
    comprobar_revision(obj, entrada.pop("revision"))
    motivo = entrada.pop("motivo")
    if documento_id:
        from django.shortcuts import get_object_or_404
        documento = get_object_or_404(m.DocumentoLegajo.objects.select_for_update(), pk=documento_id, afiliado=obj)
    else:
        documento = m.DocumentoLegajo(afiliado=obj)
    antes = {k: _json(getattr(documento, k)) for k in CAMPOS_LEGAJO}
    for campo, valor in entrada.items():
        setattr(documento, campo, valor)
    if documento.estado in ("presentado", "verificado") and not documento.presentado_en:
        raise ValidationError("Registrá la fecha de presentación.")
    if documento.estado == "verificado" and not documento.verificado_en:
        raise ValidationError("Registrá la fecha de verificación.")
    if documento.verificado_en and (not documento.presentado_en or documento.verificado_en < documento.presentado_en):
        raise ValidationError("La verificación requiere presentación previa.")
    if any(v and v > timezone.localdate() for v in (documento.presentado_en, documento.verificado_en)):
        raise ValidationError("Presentación y verificación no pueden ser futuras.")
    documento.full_clean()
    documento.save()
    validar_generales(obj)
    obj.revision += 1
    obj.save(update_fields=["revision"])
    despues = {k: _json(getattr(documento, k)) for k in CAMPOS_LEGAJO}
    registrar_historial(obj, usuario, {f"legajo:{documento.pk}": {"anterior": antes, "nuevo": despues}}, motivo)
    return documento, obj.revision
