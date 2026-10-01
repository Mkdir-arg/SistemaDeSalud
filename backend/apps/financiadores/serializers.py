from rest_framework import serializers
from django.utils import timezone
from . import models
from .facturas import clave_duplicado


class RegistroFacturaSerializer(serializers.ModelSerializer):
    convenio = serializers.PrimaryKeyRelatedField(queryset=models.Convenio.objects.none(), allow_null=True, required=False)
    afiliado = serializers.PrimaryKeyRelatedField(queryset=models.Afiliado.objects.none(), allow_null=True, required=False)
    contraparte_nombre = serializers.CharField(max_length=160, required=False)
    contraparte_identificador = serializers.CharField(max_length=80, required=False, allow_blank=True)
    adjunto_disponible = serializers.SerializerMethodField()

    class Meta:
        model = models.RegistroFactura
        fields = ["id", "direccion", "contraparte_tipo", "convenio", "afiliado", "contraparte_nombre", "contraparte_identificador", "tipo", "letra", "numero", "fecha", "importe", "periodo", "concepto", "observaciones", "creado_por", "creado", "actualizado", "adjunto_nombre", "adjunto_content_type", "adjunto_tamano", "adjunto_disponible"]
        read_only_fields = ["creado_por", "creado", "actualizado", "adjunto_nombre", "adjunto_content_type", "adjunto_tamano"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        financiador = self.context.get("financiador")
        if financiador:
            self.fields["convenio"].queryset = models.Convenio.objects.filter(financiador=financiador)
            self.fields["afiliado"].queryset = models.Afiliado.objects.filter(financiador=financiador)

    def get_adjunto_disponible(self, obj):
        from django.conf import settings
        return bool(settings.SALUD_FACTURAS_ADJUNTOS)

    def validate(self, attrs):
        datos = {campo: getattr(self.instance, campo) for campo in ["direccion", "contraparte_tipo", "convenio", "afiliado", "contraparte_nombre", "contraparte_identificador", "tipo", "letra", "numero", "fecha", "importe", "periodo", "concepto", "observaciones"]} if self.instance else {}
        datos.update(attrs)
        tipo = datos.get("contraparte_tipo")
        convenio, afiliado = datos.get("convenio"), datos.get("afiliado")
        if (tipo == "institucion" and afiliado) or (tipo == "afiliado" and convenio) or (convenio and afiliado):
            raise serializers.ValidationError("La contraparte y su vínculo deben corresponder al mismo tipo.")
        vinculo_cambio = not self.instance or any(campo in attrs for campo in ("contraparte_tipo", "convenio", "afiliado"))
        if convenio and vinculo_cambio:
            datos["contraparte_nombre"] = convenio.institucion.nombre
        elif afiliado and vinculo_cambio:
            datos["contraparte_nombre"] = afiliado.nombre
        elif not str(datos.get("contraparte_nombre", "")).strip():
            raise serializers.ValidationError({"contraparte_nombre": "Indicá el nombre de la contraparte sin vínculo."})
        if datos.get("fecha") and datos["fecha"] > timezone.localdate():
            raise serializers.ValidationError({"fecha": "La fecha no puede ser futura."})
        if datos.get("importe") is not None and datos["importe"] <= 0:
            raise serializers.ValidationError({"importe": "El importe debe ser mayor que cero."})
        if all(datos.get(campo) is not None for campo in ["direccion", "contraparte_tipo", "tipo", "numero"]):
            attrs["clave_duplicado"] = clave_duplicado(datos)
            existentes = models.RegistroFactura.objects.filter(financiador=self.context.get("financiador"), clave_duplicado=attrs["clave_duplicado"])
            if self.instance:
                existentes = existentes.exclude(pk=self.instance.pk)
            if existentes.exists():
                raise serializers.ValidationError("Ya está registrada una factura con la misma dirección, contraparte, tipo, letra y número.")
        attrs["contraparte_nombre"] = datos["contraparte_nombre"].strip()
        return attrs


class FinanciadorSerializer(serializers.ModelSerializer):
    rol = serializers.SerializerMethodField()
    resuelve_autorizaciones = serializers.SerializerMethodField()
    carga_solicitudes_manuales = serializers.SerializerMethodField()
    planes_activos = serializers.SerializerMethodField()
    convenios_vigentes = serializers.SerializerMethodField()

    class Meta:
        model = models.Financiador
        fields = ["id", "nombre", "tipo", "activo", "rol", "resuelve_autorizaciones", "carga_solicitudes_manuales", "planes_activos", "convenios_vigentes"]

    def get_resuelve_autorizaciones(self, obj) -> bool:
        from .permisos import puede_resolver_autorizaciones
        return puede_resolver_autorizaciones(self.context["request"].user, obj.pk)

    def get_carga_solicitudes_manuales(self, obj) -> bool:
        from .permisos import puede_cargar_manual
        return puede_cargar_manual(self.context["request"].user, obj.pk)

    def get_planes_activos(self, obj) -> int:
        if hasattr(obj, "planes_activos"):
            return obj.planes_activos
        return obj.plan_set.filter(activo=True).count()

    def get_convenios_vigentes(self, obj) -> int:
        if hasattr(obj, "convenios_vigentes"):
            return obj.convenios_vigentes
        from .vigencias import convenios_vigentes
        return convenios_vigentes().filter(financiador=obj).count()

    def get_rol(self, obj) -> str:
        from .permisos import plataforma
        user = self.context["request"].user
        if plataforma(user):
            return "admin"
        return models.MembresiaFinanciador.objects.filter(financiador=obj, usuario=user, activo=True).values_list("rol", flat=True).first()


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Plan
        fields = ["id", "codigo", "nombre", "activo"]


class CatalogoSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.PrestacionComun
        fields = ["id", "codigo", "nombre", "categoria", "activo"]


class ReglaSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.ReglaCobertura
        fields = ["id", "plan", "prestacion", "categoria", "porcentaje", "cupo", "periodo", "vigente_desde", "requiere_autorizacion"]


class AfiliadoSerializer(serializers.ModelSerializer):
    vigente = serializers.SerializerMethodField()

    def get_vigente(self, obj) -> bool:
        from django.utils import timezone
        return obj.finalizado_en is None and obj.desde <= timezone.localdate()

    class Meta:
        model = models.Afiliado
        fields = ["id", "numero", "documento", "nombre", "plan", "desde", "vigente", "finalizado_en", "motivo_finalizacion"]


class ConsumoSerializer(serializers.ModelSerializer):
    afiliado_numero = serializers.CharField(source="afiliado.numero", read_only=True)
    afiliado_nombre = serializers.CharField(source="afiliado.nombre", read_only=True)
    afiliado_documento = serializers.CharField(source="afiliado.documento", read_only=True)
    class Meta:
        model = models.ConsumoExterno
        fields = ["id", "afiliado", "afiliado_numero", "afiliado_nombre", "afiliado_documento", "prestacion", "fecha", "cantidad", "referencia", "corrige", "motivo", "creado"]


class ConvenioSerializer(serializers.ModelSerializer):
    institucion_nombre = serializers.CharField(source="institucion.nombre")
    financiador_nombre = serializers.CharField(source="financiador.nombre")

    class Meta:
        model = models.Convenio
        fields = ["id", "institucion", "institucion_nombre", "financiador", "financiador_nombre", "estado", "propuesto_por", "porcentaje_default", "plazo_autorizacion_horas", "aceptado_en", "cerrado_en", "motivo_cierre"]


class ImportacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Importacion
        fields = ["id", "tipo", "estado", "resumen", "filas", "creado"]


class ReservaSerializer(serializers.ModelSerializer):
    distribucion = serializers.SerializerMethodField()
    uso_autorizacion = serializers.SerializerMethodField()
    antigua = serializers.SerializerMethodField()
    prestacion_nombre = serializers.CharField(source="prestacion.nombre")
    caso_titulo = serializers.SerializerMethodField()
    puede_liberar = serializers.SerializerMethodField()
    puede_resolver = serializers.SerializerMethodField()
    puede_completar = serializers.SerializerMethodField()
    puede_completar_arancel = serializers.SerializerMethodField()
    paciente_documento = serializers.SerializerMethodField()

    class Meta:
        model = models.ReservaCobertura
        fields = ["id", "caso", "caso_titulo", "prestacion", "prestacion_nombre", "fecha", "cantidad", "cubiertas", "estado", "evaluacion", "aceptacion", "discrepancia", "creado", "antigua", "puede_liberar", "puede_resolver", "puede_completar", "puede_completar_arancel", "paciente_documento", "distribucion", "uso_autorizacion"]

    def get_uso_autorizacion(self, obj) -> dict | None:
        uso = getattr(obj, "uso_autorizacion", None)
        return {"solicitud": uso.solicitud_id, "estado": uso.estado, "cantidad": uso.cantidad, "hecho": uso.hecho_id} if uso else None

    def get_puede_completar_arancel(self, obj) -> bool:
        from apps.finanzas.permisos import tiene_concesion_financiera
        request = self.context.get("request")
        return bool(self.get_puede_completar(obj) and tiene_concesion_financiera(request.user, "configurar_cobros", obj.caso.institucion_id, sensible=obj.evaluacion.get("sensible", True)))

    def get_paciente_documento(self, obj) -> str:
        ciudadano = obj.hecho.ciudadano if obj.hecho_id else obj.caso.ciudadano
        return ciudadano.documento if ciudadano else ""

    def get_puede_completar(self, obj) -> bool:
        from apps.finanzas.permisos import tiene_concesion_financiera
        request = self.context.get("request")
        distribucion = getattr(obj, "distribucion", None)
        return bool(request and distribucion and distribucion.estado in ["arancel_pendiente", "evaluacion_pendiente"] and tiene_concesion_financiera(request.user, "resolver_cobertura", obj.caso.institucion_id, obj.hecho.area_origen_id, sensible=obj.evaluacion.get("sensible", True)))

    def get_caso_titulo(self, obj) -> str:
        return f"Caso {obj.caso_id}"

    def get_puede_liberar(self, obj) -> bool:
        from django.core.exceptions import PermissionDenied
        from .permisos import requerir_caso
        request = self.context.get("request")
        if not request or obj.estado != "reservada":
            return False
        try:
            requerir_caso(request.user, obj.caso, certificar=True)
        except PermissionDenied:
            return False
        return True

    def get_puede_resolver(self, obj) -> bool:
        from apps.finanzas.permisos import tiene_concesion_financiera
        request = self.context.get("request")
        distribucion = getattr(obj, "distribucion", None)
        return bool(request and distribucion and distribucion.estado in ("pendiente", "autorizacion_pendiente") and tiene_concesion_financiera(request.user, "resolver_cobertura", obj.caso.institucion_id, obj.hecho.area_origen_id, sensible=obj.evaluacion.get("sensible", True)))

    def get_antigua(self, obj) -> bool:
        from datetime import timedelta
        from django.utils import timezone
        dias = models.ConfiguracionHospital.objects.filter(institucion=obj.caso.institucion).values_list("dias_reserva_antigua", flat=True).first() or 7
        return obj.estado == "reservada" and obj.creado <= timezone.now()-timedelta(days=dias)

    def get_distribucion(self, obj) -> dict | None:
        distribucion = getattr(obj, "distribucion", None)
        if not distribucion:
            return None
        return {"id": distribucion.pk, "estado": distribucion.estado, "importe_financiador": str(distribucion.importe_financiador), "importe_paciente": str(distribucion.importe_paciente), "obligacion_financiador": distribucion.obligacion_financiador_id, "obligacion_paciente": distribucion.obligacion_paciente_id}
