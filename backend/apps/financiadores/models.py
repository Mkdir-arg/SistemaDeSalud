"""Cobertura administrativa. No constituye una historia clínica compartida."""
import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.db.models.signals import post_delete
from django.dispatch import receiver


class Financiador(models.Model):
    nombre = models.CharField(max_length=160)
    tipo = models.CharField(max_length=20, choices=[("obra_social", "Obra social"), ("mutual", "Mutual"), ("otro", "Otro financiador")])
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre", "id"]


class MembresiaFinanciadorManager(models.Manager):
    """Oculta al actor sus pertenencias con una baja posterior al inicio de su sesión.

    Misma regla que `accounts.MembresiaManager` (#172, decisión 5 del 19/10): una
    baja en el financiador A cierra A para las sesiones anteriores aunque se
    reactive. Los filtros por join (`membresiafinanciador__...`) no pasan por acá.
    """

    def get_queryset(self):
        from apps.accounts.sesiones import aplicar_corte_financiadores

        return aplicar_corte_financiadores(super().get_queryset())


class MembresiaFinanciador(models.Model):
    financiador = models.ForeignKey(Financiador, on_delete=models.PROTECT)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    rol = models.CharField(max_length=10, choices=[("admin", "Administrador"), ("operador", "Operador"), ("auditor", "Auditor")])
    activo = models.BooleanField(default=True)
    creo_cuenta = models.BooleanField(default=False, editable=False)
    resuelve_autorizaciones = models.BooleanField(default=False)
    acceso_padron_salud = models.BooleanField(default=False, db_default=False)
    acceso_padron_cobranza = models.BooleanField(default=False, db_default=False)

    objects = MembresiaFinanciadorManager()
    objects_sin_corte = models.Manager()

    class Meta:
        base_manager_name = "objects_sin_corte"
        constraints = [models.UniqueConstraint(fields=["financiador", "usuario"], name="fin_membresia_unica")]

    def save(self, *args, **kwargs):
        # Igual que `accounts.Membresia`: se compara contra la fila guardada.
        # `.update()` masivo no pasa por acá.
        anterior = None
        if self.pk is not None:
            anterior = MembresiaFinanciador.objects_sin_corte.filter(pk=self.pk).values("activo", "financiador_id", "rol").first()
        super().save(*args, **kwargs)
        if anterior and anterior["activo"] and (
            not self.activo or anterior["financiador_id"] != self.financiador_id or anterior["rol"] != self.rol
        ):
            BajaMembresiaFinanciador.objects.create(usuario_id=self.usuario_id, financiador_id=anterior["financiador_id"])


class BajaMembresiaFinanciador(models.Model):
    """Registro append-only de bajas de pertenencia a un financiador.

    Una sesión institucional creada en o antes de la baja ya no ve ese
    financiador. Tabla propia y no una FK más en `accounts.BajaMembresia`: allí
    `institucion` nula significa alcance global y `accounts` no depende de
    `financiadores` en sus migraciones.
    """
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    financiador = models.ForeignKey(Financiador, on_delete=models.CASCADE, related_name="+")
    momento = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        indexes = [models.Index(fields=["usuario", "momento"], name="fin_baja_usuario_idx")]
        verbose_name = "baja de membresía de financiador"
        verbose_name_plural = "bajas de membresía de financiador"


@receiver(post_delete, sender=MembresiaFinanciador, dispatch_uid="financiadores_baja_por_borrado")
def registrar_baja_por_borrado(sender, instance, **kwargs):
    # Borrar y volver a crear no rehabilita sesiones anteriores. Usuario y
    # Financiador protegen la membresía: no hay cascada que excluir.
    if instance.activo:
        BajaMembresiaFinanciador.objects.create(usuario_id=instance.usuario_id, financiador_id=instance.financiador_id)


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
    tipo = models.CharField(max_length=12, blank=True, choices=[("base", "Base"), ("superador", "Superador"), ("privado", "Privado")], default='', db_default='')

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
    geografia = models.ForeignKey("geografia.Ubicacion", null=True, blank=True, on_delete=models.PROTECT, related_name="afiliados")
    geografia_laboral = models.ForeignKey("geografia.Ubicacion", null=True, blank=True, on_delete=models.PROTECT, related_name="afiliados_laboral")
    numero = models.CharField(max_length=80)
    numero_interno = models.CharField(max_length=80, blank=True, default="", db_default="")
    # El registro administrativo puede existir sin habilitar usos prestacionales.
    cobertura_habilitada = models.BooleanField(default=True, db_default=True)
    documento = models.CharField(max_length=80)
    nombre = models.CharField(max_length=160)
    plan = models.ForeignKey(Plan, null=True, blank=True, on_delete=models.PROTECT)
    desde = models.DateField()
    finalizado_en = models.DateTimeField(null=True, blank=True)
    finalizado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="afiliaciones_finalizadas")
    motivo_finalizacion = models.CharField(max_length=255, blank=True)
    revision = models.PositiveIntegerField(default=1, db_default=1)
    tipo_documento = models.CharField(max_length=5, blank=True, choices=[(x, x) for x in ("DNI", "LE", "LC", "CI", "PAS", "OTRO")], default='', db_default='')
    cuil = models.CharField(max_length=11, blank=True, default='', db_default='')
    nombres = models.CharField(max_length=160, blank=True, default='', db_default='')
    apellidos = models.CharField(max_length=160, blank=True, default='', db_default='')
    sexo = models.CharField(max_length=1, blank=True, choices=[(x, x) for x in ("F", "M", "X")], default='', db_default='')
    fecha_nacimiento = models.DateField(null=True, blank=True)
    nacionalidad = models.CharField(max_length=80, blank=True, default='', db_default='')
    estado_civil = models.CharField(max_length=40, blank=True, default='', db_default='')
    calle = models.CharField(max_length=160, blank=True, default='', db_default='')
    altura = models.CharField(max_length=20, blank=True, default='', db_default='')
    piso = models.CharField(max_length=20, blank=True, default='', db_default='')
    departamento = models.CharField(max_length=20, blank=True, default='', db_default='')
    codigo_postal = models.CharField(max_length=20, blank=True, default='', db_default='')
    localidad = models.CharField(max_length=100, blank=True, default='', db_default='')
    partido = models.CharField(max_length=100, blank=True, default='', db_default='')
    provincia = models.CharField(max_length=100, blank=True, default='', db_default='')
    telefono = models.CharField(max_length=60, blank=True, default='', db_default='')
    celular = models.CharField(max_length=60, blank=True, default='', db_default='')
    email = models.EmailField(blank=True, default='', db_default='')
    regimen = models.CharField(max_length=12, blank=True, choices=[(x, x) for x in ("dependencia", "monotributo", "pasivo", "desempleo", "adherente")], default='', db_default='')
    empleador = models.CharField(max_length=160, blank=True, default='', db_default='')
    actividad_laboral = models.CharField(max_length=160, blank=True, default='', db_default='')
    cuit_empleador = models.CharField(max_length=11, blank=True, default='', db_default='')
    domicilio_laboral = models.CharField(max_length=255, blank=True, default='', db_default='')
    telefono_laboral = models.CharField(max_length=60, blank=True, default='', db_default='')
    email_laboral = models.EmailField(blank=True, default='', db_default='')
    subsidio_desde = models.DateField(null=True, blank=True)
    subsidio_hasta = models.DateField(null=True, blank=True)
    alta_administrativa = models.DateField(null=True, blank=True)
    delegacion = models.CharField(max_length=100, blank=True, default='', db_default='')
    estado_tramite = models.CharField(max_length=12, default="pendiente", choices=[(x, x) for x in ("pendiente", "en_revision", "observado", "completo")], db_default='pendiente')
    credencial_tipo = models.CharField(max_length=80, blank=True, default='', db_default='')
    credencial_fecha = models.DateField(null=True, blank=True)
    solicitud_baja = models.DateField(null=True, blank=True)
    baja_efectiva = models.DateField(null=True, blank=True)
    fin_prestacional_informado = models.DateField(null=True, blank=True)
    motivo_baja = models.CharField(max_length=255, blank=True, default='', db_default='')
    causa_baja = models.CharField(max_length=16, blank=True, choices=[(x, x) for x in ("cese_laboral", "traspaso", "fallecimiento", "edad", "renuncia", "mora", "judicial", "otra")], default='', db_default='')
    titular = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="familiares")
    parentesco = models.CharField(max_length=12, blank=True, choices=[(x, x) for x in ("conyuge", "hijo", "hija", "conviviente", "otro")], default='', db_default='')

    class Meta:
        ordering = ["nombre", "id"]
        constraints = [
            models.UniqueConstraint(fields=["financiador", "documento"], name="fin_afiliado_documento"),
            models.UniqueConstraint(fields=["financiador", "numero_interno"], condition=~Q(numero_interno=""), name="fin_afiliado_numero_interno"),
            models.UniqueConstraint(fields=["financiador", "cuil"], condition=~Q(cuil=""), name="fin_afiliado_cuil"),
            models.CheckConstraint(condition=~Q(titular=models.F("pk")), name="fin_familia_no_autovinculo"),
        ]
        indexes = [
            models.Index(fields=["financiador", "alta_administrativa"], name="fin_padron_alta"),
            models.Index(fields=["financiador", "baja_efectiva"], name="fin_padron_baja"),
            models.Index(fields=["financiador", "regimen"], name="fin_padron_regimen"),
        ]


class RegistroFactura(models.Model):
    financiador = models.ForeignKey(Financiador, on_delete=models.PROTECT)
    direccion = models.CharField(max_length=10, choices=[("recibida", "Recibida"), ("emitida", "Emitida por el financiador")])
    contraparte_tipo = models.CharField(max_length=12, choices=[("institucion", "Institución"), ("afiliado", "Afiliado")])
    convenio = models.ForeignKey(Convenio, null=True, blank=True, on_delete=models.PROTECT)
    afiliado = models.ForeignKey(Afiliado, null=True, blank=True, on_delete=models.PROTECT)
    contraparte_nombre = models.CharField(max_length=160)
    contraparte_identificador = models.CharField(max_length=80, blank=True)
    tipo = models.CharField(max_length=16, choices=[("factura", "Factura"), ("nota_credito", "Nota de crédito"), ("nota_debito", "Nota de débito"), ("otro", "Otro")])
    letra = models.CharField(max_length=1, blank=True, choices=[("", "Ninguna"), ("A", "A"), ("B", "B"), ("C", "C"), ("M", "M")])
    numero = models.CharField(max_length=120)
    fecha = models.DateField()
    importe = models.DecimalField(max_digits=14, decimal_places=2)
    periodo = models.CharField(max_length=100, blank=True)
    concepto = models.CharField(max_length=255, blank=True)
    observaciones = models.TextField(blank=True)
    clave_duplicado = models.CharField(max_length=64)
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="facturas_registradas")
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)
    adjunto_ruta = models.CharField(max_length=255, blank=True)
    adjunto_nombre = models.CharField(max_length=255, blank=True)
    adjunto_content_type = models.CharField(max_length=80, blank=True)
    adjunto_tamano = models.PositiveIntegerField(null=True, blank=True)
    adjunto_sha256 = models.CharField(max_length=64, blank=True)
    adjunto_subido_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="facturas_adjuntadas")
    adjunto_fecha = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-fecha", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["financiador", "clave_duplicado"], name="fin_factura_duplicado"),
            models.CheckConstraint(condition=Q(importe__gt=0), name="fin_factura_importe_positivo"),
        ]


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
    cambios = models.JSONField(default=dict, db_default={})
    origen = models.CharField(max_length=20, default="manual", db_default='manual')
    lote = models.ForeignKey("Importacion", null=True, blank=True, on_delete=models.PROTECT)


class DocumentoLegajo(models.Model):
    """Presentación administrativa registrada; sin adjunto binario ni datos de salud."""
    afiliado = models.ForeignKey(Afiliado, on_delete=models.PROTECT, related_name="legajo")
    tipo = models.CharField(max_length=12, choices=[(x, x) for x in ("dni", "cuil", "domicilio", "laboral", "estudio", "matrimonio", "nacimiento")])
    estado = models.CharField(max_length=12, default="pendiente", choices=[(x, x) for x in ("pendiente", "presentado", "observado", "verificado", "exento")])
    presentado_en = models.DateField(null=True, blank=True)
    verificado_en = models.DateField(null=True, blank=True)
    vence_en = models.DateField(null=True, blank=True)
    referencia = models.CharField(max_length=255, blank=True)


class SaludPadron(models.Model):
    """Condiciones declaradas del padrón. No modifica ni amplía historia clínica."""
    afiliado = models.OneToOneField(Afiliado, on_delete=models.PROTECT, related_name="salud_padron")
    revision = models.PositiveIntegerField(default=1)
    cud = models.BooleanField(null=True, blank=True)
    cud_numero = models.CharField(max_length=80, blank=True)
    cud_presentado_en = models.DateField(null=True, blank=True)
    cud_vencimiento = models.DateField(null=True, blank=True)
    cud_referencia = models.CharField(max_length=255, blank=True)
    dbt = models.BooleanField(null=True, blank=True)
    cronicas = models.CharField(max_length=1000, blank=True)
    parentesco_sensible = models.CharField(max_length=12, blank=True, choices=[("discapacidad", "Discapacidad")])


class CobranzaPadron(models.Model):
    """Información administrativa declarada, sin saldo contable ni verificación bancaria."""
    afiliado = models.OneToOneField(Afiliado, on_delete=models.PROTECT, related_name="cobranza_padron")
    revision = models.PositiveIntegerField(default=1)
    situacion = models.CharField(max_length=12, default="sin_informar", choices=[(x, x) for x in ("sin_informar", "al_dia", "deuda", "plan_pago", "exento")])
    fuente = models.CharField(max_length=160, blank=True)
    informado_en = models.DateField(null=True, blank=True)
    modalidad = models.CharField(max_length=14, blank=True, choices=[(x, x) for x in ("efectivo", "transferencia", "debito_cbu", "tarjeta", "cupon", "recibo_sueldo")])
    banco = models.CharField(max_length=120, blank=True)
    proveedor_cupon = models.CharField(max_length=80, blank=True)
    dia_vencimiento = models.PositiveSmallIntegerField(null=True, blank=True)
    cupon = models.CharField(max_length=120, blank=True)
    cbu = models.CharField(max_length=22, blank=True)
    cuit_titular = models.CharField(max_length=11, blank=True)
    titular_cuenta = models.CharField(max_length=160, blank=True)
    emisor_tarjeta = models.CharField(max_length=80, blank=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(dia_vencimiento__isnull=True) | Q(dia_vencimiento__gte=1, dia_vencimiento__lte=31), name="fin_padron_dia_vencimiento")]


class HistorialPadronProtegido(models.Model):
    """Sólo se consulta con la designación correspondiente al bloque."""
    afiliado = models.ForeignKey(Afiliado, on_delete=models.PROTECT)
    bloque = models.CharField(max_length=10, choices=[("salud", "Salud"), ("cobranza", "Cobranza")])
    revision = models.PositiveIntegerField()
    cambios = models.JSONField(default=dict)
    motivo = models.CharField(max_length=255)
    registrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    registrado = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["afiliado", "bloque", "-id"], name="fin_padron_hist_protegido")]


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
    version = models.PositiveSmallIntegerField(default=1, db_default=1)
    clave = models.UUIDField()
    huella = models.CharField(max_length=64)
    filas = models.JSONField(default=list)
    estado = models.CharField(max_length=20, default="preview")
    resumen = models.JSONField(default=dict)
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["financiador", "clave"], name="fin_importacion_clave")]


class CodigoFinanciador(models.Model):
    """Diccionario de códigos propio de un financiador (por ejemplo, OSTEL).

    Es un catálogo de consulta: no asigna parentescos, familias, planes ni
    derechos por sí mismo. Atributos guarda las columnas propias de cada tabla
    (VENCE, MOTIVO, TITULAR, CODSSS, etc.) tal como las informa el financiador.
    """
    financiador = models.ForeignKey(Financiador, on_delete=models.PROTECT, related_name="codigos")
    tabla = models.CharField(max_length=40)
    codigo = models.CharField(max_length=40)
    descripcion = models.CharField(max_length=160, blank=True)
    activo = models.BooleanField(default=True)
    atributos = models.JSONField(default=dict, blank=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["financiador", "tabla", "codigo"]
        constraints = [models.UniqueConstraint(fields=["financiador", "tabla", "codigo"], name="fin_codigo_tabla_unico")]
        verbose_name = "código del financiador"
        verbose_name_plural = "códigos del financiador"

    def __str__(self):
        return f"{self.tabla} {self.codigo}: {self.descripcion}"


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
    origen = models.CharField(max_length=12, choices=[("institucion", "Institución"), ("manual", "Manual")], default="institucion")
    institucion = models.ForeignKey("instituciones.Institucion", on_delete=models.PROTECT)
    financiador = models.ForeignKey(Financiador, on_delete=models.PROTECT)
    convenio = models.ForeignKey(Convenio, on_delete=models.PROTECT)
    afiliado = models.ForeignKey(Afiliado, on_delete=models.PROTECT)
    afiliacion = models.ForeignKey(AfiliacionCaso, null=True, blank=True, on_delete=models.PROTECT)
    comun = models.ForeignKey(PrestacionComun, on_delete=models.PROTECT)
    prestacion = models.ForeignKey("finanzas.Prestacion", null=True, blank=True, on_delete=models.PROTECT)
    caso = models.ForeignKey("casos.Caso", null=True, blank=True, on_delete=models.PROTECT, related_name="autorizaciones")
    ciudadano = models.ForeignKey("registros.Ciudadano", null=True, on_delete=models.PROTECT)
    nodo = models.ForeignKey("flujos.Nodo", null=True, blank=True, on_delete=models.PROTECT)
    intento = models.UUIDField(null=True, blank=True)
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
            models.CheckConstraint(condition=(Q(origen="institucion", caso__isnull=False, nodo__isnull=False, intento__isnull=False, afiliacion__isnull=False, prestacion__isnull=False) | Q(origen="manual", caso__isnull=True, nodo__isnull=True, intento__isnull=True, afiliacion__isnull=True, prestacion__isnull=True)), name="fin_autorizacion_origen_coherente"),
            models.UniqueConstraint(fields=["afiliado", "convenio", "comun"], condition=Q(origen="manual", estado__in=["pendiente", "observada"]), name="fin_autorizacion_manual_abierta"),
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
