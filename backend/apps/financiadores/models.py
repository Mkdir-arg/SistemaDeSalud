"""Cobertura administrativa. No constituye una historia clínica compartida."""
import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


class Financiador(models.Model):
    nombre = models.CharField(max_length=160)
    tipo = models.CharField(max_length=20, choices=[("obra_social", "Obra social"), ("mutual", "Mutual"), ("otro", "Otro financiador")])
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre", "id"]


class MembresiaFinanciador(models.Model):
    financiador = models.ForeignKey(Financiador, on_delete=models.PROTECT)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    rol = models.CharField(max_length=10, choices=[("admin", "Administrador"), ("operador", "Operador"), ("auditor", "Auditor")])
    activo = models.BooleanField(default=True)
    creo_cuenta = models.BooleanField(default=False, editable=False)
    resuelve_autorizaciones = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["financiador", "usuario"], name="fin_membresia_unica")]


class PrestacionComun(models.Model):
    codigo = models.CharField(max_length=60, unique=True)
    nombre = models.CharField(max_length=160)
    categoria = models.CharField(max_length=80)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["codigo"]


class VinculoPrestacion(models.Model):
    prestacion = models.OneToOneField("finanzas.Prestacion", on_delete=models.PROTECT)
    comun = models.ForeignKey(PrestacionComun, on_delete=models.PROTECT)


class Plan(models.Model):
    financiador = models.ForeignKey(Financiador, on_delete=models.PROTECT)
    codigo = models.CharField(max_length=60)
    nombre = models.CharField(max_length=160)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["codigo", "id"]
        constraints = [models.UniqueConstraint(fields=["financiador", "codigo"], name="fin_plan_codigo")]


class ReglaCobertura(models.Model):
    financiador = models.ForeignKey(Financiador, on_delete=models.PROTECT)
    plan = models.ForeignKey(Plan, null=True, blank=True, on_delete=models.PROTECT)
    prestacion = models.ForeignKey(PrestacionComun, null=True, blank=True, on_delete=models.PROTECT)
    categoria = models.CharField(max_length=80, blank=True)
    porcentaje = models.DecimalField(max_digits=5, decimal_places=2)
    cupo = models.PositiveIntegerField(null=True, blank=True)
    periodo = models.CharField(max_length=4, choices=[("mes", "Mes calendario"), ("anio", "Año calendario")], default="anio")
    vigente_desde = models.DateField()
    requiere_autorizacion = models.BooleanField(default=False)
    creado = models.DateTimeField(auto_now_add=True)
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        ordering = ["-vigente_desde", "-id"]
        constraints = [models.CheckConstraint(condition=Q(porcentaje__gte=0, porcentaje__lte=100), name="fin_porcentaje_valido")]


class Convenio(models.Model):
    financiador = models.ForeignKey(Financiador, on_delete=models.PROTECT)
    institucion = models.ForeignKey("instituciones.Institucion", on_delete=models.PROTECT)
    estado = models.CharField(max_length=12, default="propuesto", choices=[("propuesto", "Propuesto"), ("activo", "Activo"), ("rechazado", "Rechazado"), ("finalizado", "Finalizado")])
    propuesto_por = models.CharField(max_length=12, choices=[("hospital", "Hospital"), ("financiador", "Financiador"), ("plataforma", "Plataforma")])
    porcentaje_default = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    plazo_autorizacion_horas = models.PositiveIntegerField(null=True, blank=True)
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="convenios_creados")
    aceptado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name="convenios_aceptados")
    aceptado_en = models.DateTimeField(null=True)
    cerrado_en = models.DateTimeField(null=True, blank=True)
    cerrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="convenios_cerrados")
    motivo_cierre = models.CharField(max_length=255, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["financiador", "institucion"], condition=Q(estado__in=["propuesto", "activo"]), name="fin_convenio_abierto_unico")]


class Afiliado(models.Model):
    """Identidad estable del pagador; cambiar el número/plan no reinicia su cupo."""
    financiador = models.ForeignKey(Financiador, on_delete=models.PROTECT)
    numero = models.CharField(max_length=80)
    documento = models.CharField(max_length=80)
    nombre = models.CharField(max_length=160)
    plan = models.ForeignKey(Plan, null=True, blank=True, on_delete=models.PROTECT)
    desde = models.DateField()
    finalizado_en = models.DateTimeField(null=True, blank=True)
    finalizado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="afiliaciones_finalizadas")
    motivo_finalizacion = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["nombre", "id"]
        constraints = [models.UniqueConstraint(fields=["financiador", "documento"], name="fin_afiliado_documento")]


class HistorialAfiliacion(models.Model):
    afiliado = models.ForeignKey(Afiliado, on_delete=models.PROTECT, related_name="historial")
    numero = models.CharField(max_length=80)
    documento = models.CharField(max_length=80, blank=True)
    plan = models.ForeignKey(Plan, null=True, blank=True, on_delete=models.PROTECT)
    desde = models.DateField()
    registrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    registrado = models.DateTimeField(auto_now_add=True)
    tipo = models.CharField(max_length=15, default="actualizacion", choices=[("actualizacion", "Actualización"), ("finalizacion", "Finalización"), ("reactivacion", "Reactivación")])
    motivo = models.CharField(max_length=255, blank=True)


class VinculoCiudadano(models.Model):
    afiliado = models.ForeignKey(Afiliado, on_delete=models.PROTECT)
    ciudadano = models.ForeignKey("registros.Ciudadano", on_delete=models.PROTECT)
    verificado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["afiliado", "ciudadano"], name="fin_vinculo_ciudadano")]


class AfiliacionCaso(models.Model):
    caso = models.ForeignKey("casos.Caso", on_delete=models.PROTECT, related_name="afiliaciones_financieras")
    afiliado = models.ForeignKey(Afiliado, null=True, on_delete=models.PROTECT)
    plan = models.ForeignKey(Plan, null=True, on_delete=models.PROTECT)
    estado = models.CharField(max_length=12, choices=[("verificada", "Verificada"), ("pendiente", "Pendiente"), ("particular", "Particular")])
    declaracion = models.CharField(max_length=160, blank=True)
    hecho_revision = models.ForeignKey("finanzas.HechoAtencionCosteable", null=True, blank=True, on_delete=models.PROTECT)
    motivo = models.CharField(max_length=255)
    registrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]


class ConfiguracionHospital(models.Model):
    institucion = models.OneToOneField("instituciones.Institucion", on_delete=models.PROTECT)
    activo = models.BooleanField(default=False)
    dias_reserva_antigua = models.PositiveIntegerField(default=7)


class ArancelConvenio(models.Model):
    convenio = models.ForeignKey(Convenio, on_delete=models.PROTECT)
    prestacion = models.ForeignKey("finanzas.Prestacion", on_delete=models.PROTECT)
    # None registra la vuelta deliberada al arancel general. No es un precio
    # pendiente ni una negociación: el hospital carga acuerdos ya definidos.
    importe = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    vigente_desde = models.DateField()
    creado = models.DateTimeField(auto_now_add=True)
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        ordering = ["-vigente_desde", "-id"]
        constraints = [models.CheckConstraint(condition=Q(importe__isnull=True) | Q(importe__gt=0), name="fin_arancel_excepcion_positivo")]


class ReservaCobertura(models.Model):
    caso = models.ForeignKey("casos.Caso", on_delete=models.PROTECT)
    afiliacion = models.ForeignKey(AfiliacionCaso, on_delete=models.PROTECT)
    afiliado = models.ForeignKey(Afiliado, null=True, on_delete=models.PROTECT)
    prestacion = models.ForeignKey("finanzas.Prestacion", on_delete=models.PROTECT)
    comun = models.ForeignKey(PrestacionComun, on_delete=models.PROTECT)
    fecha = models.DateField()
    cantidad = models.PositiveIntegerField()
    cubiertas = models.PositiveIntegerField(default=0)
    estado = models.CharField(max_length=12, default="reservada", choices=[("reservada", "Reservada"), ("realizada", "Realizada"), ("liberada", "Liberada")])
    evaluacion = models.JSONField()
    aceptacion = models.JSONField(default=dict)
    discrepancia = models.BooleanField(default=False)
    clave = models.UUIDField(default=uuid.uuid4, unique=True)
    solicitud = models.JSONField(default=dict)
    hecho = models.ForeignKey("finanzas.HechoAtencionCosteable", null=True, on_delete=models.PROTECT)
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name="reservas_cobertura")
    creado = models.DateTimeField(auto_now_add=True)
    cerrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name="cierres_cobertura")
    cerrado_en = models.DateTimeField(null=True)
    motivo = models.CharField(max_length=255, blank=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(cantidad__gt=0) & Q(cubiertas__lte=models.F("cantidad")), name="fin_reserva_cantidades")]
        indexes = [models.Index(fields=["afiliado", "comun", "fecha", "estado"])]


class ConsumoExterno(models.Model):
    financiador = models.ForeignKey(Financiador, on_delete=models.PROTECT)
    afiliado = models.ForeignKey(Afiliado, on_delete=models.PROTECT)
    prestacion = models.ForeignKey(PrestacionComun, on_delete=models.PROTECT)
    fecha = models.DateField()
    cantidad = models.IntegerField()
    referencia = models.CharField(max_length=120, blank=True)
    corrige = models.OneToOneField("self", null=True, on_delete=models.PROTECT, related_name="correccion")
    motivo = models.CharField(max_length=255, blank=True)
    registrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha", "-id"]
        constraints = [models.UniqueConstraint(fields=["financiador", "referencia"], condition=~Q(referencia=""), name="fin_consumo_referencia")]
        indexes = [models.Index(fields=["afiliado", "prestacion", "fecha"])]


class DistribucionCobro(models.Model):
    reserva = models.OneToOneField(ReservaCobertura, on_delete=models.PROTECT, related_name="distribucion")
    importe_financiador = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    importe_paciente = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    estado = models.CharField(max_length=25, default="pendiente", choices=[("pendiente", "Pendiente de resolución administrativa"), ("resuelta", "Resuelta"), ("arancel_pendiente", "Arancel pendiente"), ("evaluacion_pendiente", "Pendiente de evaluación"), ("autorizacion_pendiente", "Responsabilidad pendiente de autorización"), ("sin_cobro", "Sin cobro")])
    obligacion_financiador = models.OneToOneField("finanzas.ObligacionFinanciera", null=True, on_delete=models.PROTECT, related_name="distribucion_financiador")
    obligacion_paciente = models.OneToOneField("finanzas.ObligacionFinanciera", null=True, on_delete=models.PROTECT, related_name="distribucion_paciente")


class ResolucionSaldo(models.Model):
    distribucion = models.ForeignKey(DistribucionCobro, on_delete=models.PROTECT, related_name="resoluciones")
    parte = models.CharField(max_length=12, default="paciente", choices=[("paciente", "Saldo del paciente"), ("financiador", "Responsabilidad pendiente de autorización")])
    decision = models.CharField(max_length=12, choices=[("rechazar", "Rechazar asunción"), ("asumir", "Asumir hospital"), ("paciente", "Aceptación paciente"), ("financiador", "Aceptación financiador")])
    importe = models.DecimalField(max_digits=14, decimal_places=2)
    motivo = models.CharField(max_length=255)
    evidencia = models.TextField(blank=True)
    obligacion = models.OneToOneField("finanzas.ObligacionFinanciera", null=True, on_delete=models.PROTECT)
    clave = models.UUIDField(unique=True)
    registrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    creado = models.DateTimeField(auto_now_add=True)


class Importacion(models.Model):
    financiador = models.ForeignKey(Financiador, on_delete=models.PROTECT)
    tipo = models.CharField(max_length=10)
    clave = models.UUIDField()
    huella = models.CharField(max_length=64)
    filas = models.JSONField(default=list)
    estado = models.CharField(max_length=20, default="preview")
    resumen = models.JSONField(default=dict)
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["financiador", "clave"], name="fin_importacion_clave")]


class EventoCobertura(models.Model):
    """Auditoría administrativa mínima, sin datos de la historia clínica."""
    financiador = models.ForeignKey(Financiador, null=True, on_delete=models.PROTECT)
    institucion = models.ForeignKey("instituciones.Institucion", null=True, on_delete=models.PROTECT)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    accion = models.CharField(max_length=60)
    objeto = models.CharField(max_length=80)
    motivo = models.CharField(max_length=255, blank=True)
    creado = models.DateTimeField(auto_now_add=True)


class RevisionContexto(models.Model):
    hecho = models.OneToOneField("finanzas.HechoAtencionCosteable", on_delete=models.PROTECT)
    contexto = models.JSONField()
    motivo = models.CharField(max_length=255)
    registrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    creado = models.DateTimeField(auto_now_add=True)


class SolicitudAutorizacion(models.Model):
    """Permiso administrativo; no acredita realización ni asunción de otro importe."""
    ESTADOS = [(x, titulo) for x, titulo in (
        ("pendiente", "Pendiente"), ("observada", "Observada"), ("aprobada", "Aprobada"),
        ("rechazada", "Rechazada"), ("vencida", "Vencida"), ("anulada", "Anulada"),
    )]
    ABIERTAS = ("pendiente", "observada")
    institucion = models.ForeignKey("instituciones.Institucion", on_delete=models.PROTECT)
    financiador = models.ForeignKey(Financiador, on_delete=models.PROTECT)
    convenio = models.ForeignKey(Convenio, on_delete=models.PROTECT)
    afiliado = models.ForeignKey(Afiliado, on_delete=models.PROTECT)
    afiliacion = models.ForeignKey(AfiliacionCaso, on_delete=models.PROTECT)
    comun = models.ForeignKey(PrestacionComun, on_delete=models.PROTECT)
    prestacion = models.ForeignKey("finanzas.Prestacion", on_delete=models.PROTECT)
    caso = models.ForeignKey("casos.Caso", on_delete=models.PROTECT, related_name="autorizaciones")
    ciudadano = models.ForeignKey("registros.Ciudadano", null=True, on_delete=models.PROTECT)
    nodo = models.ForeignKey("flujos.Nodo", on_delete=models.PROTECT)
    intento = models.UUIDField()
    anterior = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="reintentos")
    cantidad_solicitada = models.PositiveIntegerField()
    cantidad_aprobada = models.PositiveIntegerField(default=0)
    justificacion = models.CharField(max_length=1000)
    urgente = models.BooleanField(default=False)
    estado = models.CharField(max_length=12, choices=ESTADOS, default="pendiente")
    revision = models.PositiveIntegerField(default=1)
    plazo_respuesta = models.DateTimeField(null=True, blank=True)
    vigencia_desde = models.DateField(null=True, blank=True)
    vigencia_hasta = models.DateField(null=True, blank=True)
    numero_externo = models.CharField(max_length=120, blank=True)
    motivo_resolucion = models.CharField(max_length=255, blank=True)
    evidencia = models.CharField(max_length=1000, blank=True)
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="autorizaciones_solicitadas")
    resuelto_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name="autorizaciones_resueltas")
    resuelto_en = models.DateTimeField(null=True)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["creado", "pk"]
        constraints = [
            models.CheckConstraint(condition=Q(cantidad_solicitada__gt=0) & Q(cantidad_aprobada__lte=models.F("cantidad_solicitada")), name="fin_autorizacion_cantidades"),
            models.CheckConstraint(condition=~Q(estado="aprobada") | (Q(cantidad_aprobada__gt=0) & Q(vigencia_desde__isnull=False, vigencia_hasta__isnull=False) & Q(vigencia_hasta__gte=models.F("vigencia_desde"))), name="fin_autorizacion_vigencia"),
            models.UniqueConstraint(fields=["caso", "intento", "prestacion"], condition=Q(estado__in=["pendiente", "observada", "aprobada"]), name="fin_autorizacion_intento_activo"),
        ]
        indexes = [models.Index(fields=["estado", "plazo_respuesta"]), models.Index(fields=["estado", "vigencia_hasta"]), models.Index(fields=["convenio", "afiliado", "comun", "estado"])]


class EventoAutorizacion(models.Model):
    """Historia administrativa y claves de reintento, sin edición desde la API."""
    solicitud = models.ForeignKey(SolicitudAutorizacion, on_delete=models.PROTECT, related_name="historial")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    clave = models.UUIDField(unique=True)
    accion = models.CharField(max_length=20)
    anterior = models.CharField(max_length=12, blank=True)
    estado = models.CharField(max_length=12)
    revision = models.PositiveIntegerField()
    motivo = models.CharField(max_length=1000)
    peticion = models.JSONField()
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["pk"]


class UsoAutorizacion(models.Model):
    solicitud = models.ForeignKey(SolicitudAutorizacion, on_delete=models.PROTECT, related_name="usos")
    reserva = models.OneToOneField(ReservaCobertura, on_delete=models.PROTECT, related_name="uso_autorizacion")
    cantidad = models.PositiveIntegerField()
    estado = models.CharField(max_length=12, choices=[("comprometido", "Comprometido"), ("consumido", "Consumido"), ("liberado", "Liberado")], default="comprometido")
    hecho = models.ForeignKey("finanzas.HechoAtencionCosteable", null=True, on_delete=models.PROTECT)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(cantidad__gt=0), name="fin_uso_autorizacion_positivo")]
