"""Hechos e importes internos de finanzas y costos."""
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q


class ConcesionFinanciera(models.Model):
    """Permiso explícito de finanzas, ligado a una membresía institucional."""

    class Accion(models.TextChoices):
        VER_COSTOS = "ver_costos", "Ver costos"
        CONFIGURAR_COMPONENTES = "configurar_componentes", "Configurar componentes"
        CORREGIR_COSTOS = "corregir_costos", "Corregir costos"
        VER_GASTOS = "ver_gastos", "Ver gastos"
        REGISTRAR_GASTOS = "registrar_gastos", "Registrar gastos"
        APROBAR_GASTOS = "aprobar_gastos", "Aprobar gastos"
        CORREGIR_GASTOS = "corregir_gastos", "Corregir gastos"
        CONFIGURAR_GASTOS_ESPERADOS = "configurar_gastos_esperados", "Configurar gastos esperados"
        AUDITAR_FINANZAS = "auditar_finanzas", "Auditar accesos financieros"
        CONFIGURAR_REPARTOS = "configurar_repartos", "Configurar repartos"

    membresia = models.ForeignKey(
        "accounts.Membresia",
        on_delete=models.CASCADE,
        related_name="concesiones_financieras",
    )
    accion = models.CharField(max_length=40, choices=Accion.choices)
    todas_las_areas = models.BooleanField(default=False)
    permite_sensibles = models.BooleanField(default=False)
    areas = models.ManyToManyField(
        "instituciones.Area",
        blank=True,
        related_name="concesiones_financieras",
    )

    class Meta:
        unique_together = [("membresia", "accion")]
        ordering = ["membresia_id", "accion", "id"]

    @classmethod
    def accion_requiere_administracion(cls, accion):
        return accion in {
            cls.Accion.CONFIGURAR_COMPONENTES,
            cls.Accion.CORREGIR_COSTOS,
            cls.Accion.APROBAR_GASTOS,
            cls.Accion.CORREGIR_GASTOS,
            cls.Accion.CONFIGURAR_GASTOS_ESPERADOS,
            cls.Accion.AUDITAR_FINANZAS,
            cls.Accion.CONFIGURAR_REPARTOS,
        }

    def clean(self):
        super().clean()
        if self.accion_requiere_administracion(self.accion) and self.membresia.rol != "admin":
            raise ValidationError(
                "Esta acción financiera requiere una membresía administrativa."
            )
        if self.permite_sensibles and self.membresia.rol != "admin":
            raise ValidationError(
                "El acceso a costos sensibles requiere una membresía administrativa."
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class AccesoFinanciero(models.Model):
    """Metadatos de una lectura financiera; nunca copia importes ni texto libre."""

    usuario = models.ForeignKey("accounts.Usuario", on_delete=models.PROTECT)
    institucion = models.ForeignKey("instituciones.Institucion", on_delete=models.PROTECT, null=True)
    area = models.ForeignKey("instituciones.Area", on_delete=models.PROTECT, null=True)
    sensible = models.BooleanField(default=False)
    recurso = models.CharField(max_length=60)
    accion = models.CharField(max_length=30)
    objeto_id = models.PositiveBigIntegerField(null=True)
    periodo_economico = models.DateField(null=True)
    resultados = models.PositiveIntegerField(default=0)
    registrado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-registrado", "-id"]

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Un acceso financiero no se modifica.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Un acceso financiero no se elimina.")


class Prestacion(models.Model):
    institucion = models.ForeignKey("instituciones.Institucion", on_delete=models.CASCADE, related_name="prestaciones_costo")
    nodo = models.ForeignKey("flujos.Nodo", on_delete=models.SET_NULL, null=True, blank=True, related_name="prestaciones_costo")
    codigo = models.CharField(max_length=60)
    nombre = models.CharField(max_length=160)
    activo = models.BooleanField(default=True)
    class Meta:
        unique_together = [("institucion", "codigo")]
        ordering = ["institucion_id", "codigo"]


class DefinicionComponente(models.Model):
    class Fuente(models.TextChoices):
        ATENCION_DIRECTA = "atencion_directa", "Atención directa"

    class Unidad(models.TextChoices):
        ATENCION = "atencion", "Atención"

    class BaseCalculo(models.TextChoices):
        POR_ATENCION = "por_atencion", "Por atención"

    prestacion = models.ForeignKey(Prestacion, on_delete=models.PROTECT, related_name="componentes")
    codigo = models.CharField(max_length=60)
    nombre = models.CharField(max_length=160)
    fuente = models.CharField(max_length=40, choices=Fuente.choices, default=Fuente.ATENCION_DIRECTA)
    unidad = models.CharField(max_length=30, choices=Unidad.choices, default=Unidad.ATENCION)
    base_calculo = models.CharField(
        max_length=30,
        choices=BaseCalculo.choices,
        default=BaseCalculo.POR_ATENCION,
    )
    activo = models.BooleanField(default=True)
    sensible = models.BooleanField(default=False)
    orden = models.PositiveSmallIntegerField(default=0)
    class Meta:
        unique_together = [("prestacion", "codigo")]
        ordering = ["prestacion_id", "orden", "id"]


class ValorComponente(models.Model):
    class Moneda(models.TextChoices):
        ARS = "ARS", "Peso argentino"

    componente = models.ForeignKey(DefinicionComponente, on_delete=models.PROTECT, related_name="valores")
    importe = models.DecimalField(max_digits=14, decimal_places=2)
    moneda = models.CharField(max_length=3, choices=Moneda.choices, default=Moneda.ARS)
    vigente_desde = models.DateTimeField()
    vigente_hasta = models.DateTimeField(null=True, blank=True)
    fuente = models.CharField(max_length=255, blank=True)
    registrado_por = models.ForeignKey("accounts.Usuario", on_delete=models.SET_NULL, null=True, blank=True, related_name="valores_costo_registrados")
    registrado = models.DateTimeField(auto_now_add=True)
    reemplaza = models.OneToOneField("self", on_delete=models.PROTECT, null=True, blank=True, related_name="reemplazado_por")
    motivo_correccion = models.CharField(max_length=255, blank=True)
    class Meta:
        ordering = ["componente_id", "vigente_desde", "id"]
        constraints = [
            models.CheckConstraint(condition=Q(importe__gte=0), name="valor_componente_no_negativo"),
            models.CheckConstraint(condition=Q(vigente_hasta__isnull=True) | Q(vigente_hasta__gt=models.F("vigente_desde")), name="vigencia_componente_valida"),
        ]

    def clean(self):
        super().clean()
        if self.reemplaza_id:
            if self.reemplaza.componente_id != self.componente_id:
                raise ValidationError("Un valor sucesor debe pertenecer al mismo componente.")
            if self.vigente_desde < self.reemplaza.vigente_desde:
                raise ValidationError("Un valor sucesor no puede empezar antes del valor reemplazado.")
            if self.vigente_desde == self.reemplaza.vigente_desde:
                if self.vigente_hasta != self.reemplaza.vigente_hasta:
                    raise ValidationError("Una corrección conserva la vigencia del valor corregido.")
                if not self.motivo_correccion:
                    raise ValidationError("Una corrección requiere un motivo.")
        solapa = Q(vigente_hasta__isnull=True) | Q(vigente_hasta__gt=self.vigente_desde)
        if self.vigente_hasta is not None:
            solapa &= Q(vigente_desde__lt=self.vigente_hasta)
        existentes = ValorComponente.objects.filter(componente=self.componente, reemplazado_por__isnull=True).exclude(pk=self.pk)
        if self.reemplaza_id:
            existentes = existentes.exclude(pk=self.reemplaza_id)
        if existentes.filter(solapa).exists():
            raise ValidationError("Ya existe un valor vigente para ese intervalo; corregilo explícitamente.")

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Un valor de componente no se edita; se corrige con una nueva versión.")
        if self.componente_id is None:
            self.full_clean()
            return super().save(*args, **kwargs)
        with transaction.atomic(using=kwargs.get("using")):
            DefinicionComponente.objects.select_for_update().get(pk=self.componente_id)
            self.full_clean()
            return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Un valor de componente no se elimina.")


class ConceptoGasto(models.Model):
    """Catálogo institucional de conceptos para gastos reales y esperados."""

    institucion = models.ForeignKey(
        "instituciones.Institucion",
        on_delete=models.PROTECT,
        related_name="conceptos_gasto",
    )
    codigo = models.CharField(max_length=60)
    nombre = models.CharField(max_length=160)
    activo = models.BooleanField(default=True)
    sensible = models.BooleanField(default=False)
    registrado_por = models.ForeignKey(
        "accounts.Usuario",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="conceptos_gasto_registrados",
    )
    registrado = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("institucion", "codigo")]
        ordering = ["institucion_id", "codigo", "id"]

    def clean(self):
        super().clean()
        if not self.codigo.strip():
            raise ValidationError("Un concepto de gasto requiere un código.")
        if not self.nombre.strip():
            raise ValidationError("Un concepto de gasto requiere un nombre.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class ExpectativaGasto(models.Model):
    """Vigencia trazable de un concepto cuya carga se espera en un ámbito."""

    concepto = models.ForeignKey(
        ConceptoGasto,
        on_delete=models.PROTECT,
        related_name="expectativas",
    )
    institucion = models.ForeignKey(
        "instituciones.Institucion",
        on_delete=models.PROTECT,
        related_name="expectativas_gasto",
    )
    area = models.ForeignKey(
        "instituciones.Area",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="expectativas_gasto",
    )
    vigente_desde = models.DateField()
    vigente_hasta = models.DateField(null=True, blank=True)
    sensible = models.BooleanField(default=False, editable=False)
    reemplaza = models.OneToOneField(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reemplazada_por",
    )
    motivo_correccion = models.CharField(max_length=255, blank=True)
    registrado_por = models.ForeignKey(
        "accounts.Usuario",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="expectativas_gasto_registradas",
    )
    registrado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["institucion_id", "concepto_id", "area_id", "vigente_desde", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(vigente_hasta__isnull=True) | Q(vigente_hasta__gt=models.F("vigente_desde")),
                name="vigencia_expectativa_gasto_valida",
            ),
        ]

    def clean(self):
        super().clean()
        if self.vigente_desde and self.vigente_desde.day != 1:
            raise ValidationError("La vigencia de una expectativa empieza el primer día del mes.")
        if self.vigente_hasta and self.vigente_hasta.day != 1:
            raise ValidationError("La vigencia de una expectativa termina el primer día de un mes.")
        if self.concepto_id and self.institucion_id and self.concepto.institucion_id != self.institucion_id:
            raise ValidationError("El concepto debe pertenecer a la institución de la expectativa.")
        if self.area_id and self.institucion_id and self.area.institucion_id != self.institucion_id:
            raise ValidationError("El área debe pertenecer a la institución de la expectativa.")
        if self.reemplaza_id:
            if (
                self.reemplaza.concepto_id != self.concepto_id
                or self.reemplaza.institucion_id != self.institucion_id
                or self.reemplaza.area_id != self.area_id
            ):
                raise ValidationError("Una expectativa sucesora conserva concepto y ámbito.")
            if self.vigente_desde < self.reemplaza.vigente_desde:
                raise ValidationError("Una expectativa sucesora no puede empezar antes de la reemplazada.")
            if self.vigente_desde == self.reemplaza.vigente_desde:
                if self.vigente_hasta != self.reemplaza.vigente_hasta:
                    raise ValidationError("Una corrección conserva la vigencia de la expectativa corregida.")
                if not self.motivo_correccion.strip():
                    raise ValidationError("Una corrección de expectativa requiere un motivo.")

        if not (self.concepto_id and self.institucion_id and self.vigente_desde):
            return
        solapa = Q(vigente_hasta__isnull=True) | Q(vigente_hasta__gt=self.vigente_desde)
        if self.vigente_hasta is not None:
            solapa &= Q(vigente_desde__lt=self.vigente_hasta)
        existentes = ExpectativaGasto.objects.filter(
            concepto_id=self.concepto_id,
            institucion_id=self.institucion_id,
            area_id=self.area_id,
            reemplazada_por__isnull=True,
        ).exclude(pk=self.pk)
        if self.reemplaza_id:
            existentes = existentes.exclude(pk=self.reemplaza_id)
        if existentes.filter(solapa).exists():
            raise ValidationError("Ya existe una expectativa vigente para ese intervalo; corregila explícitamente.")

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Una expectativa de gasto no se edita; se corrige con una nueva versión.")
        if self.concepto_id is None:
            self.full_clean()
            return super().save(*args, **kwargs)
        with transaction.atomic(using=kwargs.get("using")):
            concepto = ConceptoGasto.objects.select_for_update().get(pk=self.concepto_id)
            self.concepto = concepto
            self.sensible = concepto.sensible
            self.full_clean()
            return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Una expectativa de gasto no se elimina.")


class IndicacionCargaGasto(models.Model):
    """Estado declarado de una expectativa mensual, sin generar un gasto."""

    class Estado(models.TextChoices):
        FALTA_CARGAR = "falta_cargar", "Falta cargar"
        CARGA_COMPLETA = "carga_completa", "Carga completa"
        NO_CORRESPONDE = "no_corresponde", "No corresponde"

    expectativa = models.ForeignKey(
        ExpectativaGasto,
        on_delete=models.PROTECT,
        related_name="indicaciones_carga",
    )
    periodo_economico = models.DateField()
    estado = models.CharField(max_length=30, choices=Estado.choices)
    registrado_por = models.ForeignKey(
        "accounts.Usuario",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="indicaciones_carga_gasto_registradas",
    )
    registrado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["periodo_economico", "registrado", "id"]

    def clean(self):
        super().clean()
        if self.periodo_economico and self.periodo_economico.day != 1:
            raise ValidationError("El período económico de una indicación empieza el primer día del mes.")
        if not self.expectativa_id or not self.periodo_economico:
            return
        expectativa = self.expectativa
        if ExpectativaGasto.objects.filter(
            pk=expectativa.pk,
            reemplazada_por__vigente_desde__lte=self.periodo_economico,
        ).exists():
            raise ValidationError("La expectativa fue reemplazada para ese mes.")
        if self.periodo_economico < expectativa.vigente_desde or (
            expectativa.vigente_hasta is not None
            and self.periodo_economico >= expectativa.vigente_hasta
        ):
            raise ValidationError("La indicación debe pertenecer a la vigencia de su expectativa.")

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Una indicación de carga no se edita; registrá una nueva indicación.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Una indicación de carga no se elimina.")


class Gasto(models.Model):
    """Fuente real de gasto, separada de su reparto y de cualquier pago."""

    class Estado(models.TextChoices):
        PENDIENTE_APROBACION = "pendiente_aprobacion", "Pendiente de aprobación"
        APROBADO = "aprobado", "Aprobado"
        RECHAZADO = "rechazado", "Rechazado"

    class Origen(models.TextChoices):
        CENTRAL = "central", "Administración central"
        AREA = "area", "Área"

    concepto = models.ForeignKey(
        ConceptoGasto,
        on_delete=models.PROTECT,
        related_name="gastos",
    )
    concepto_codigo = models.CharField(max_length=60, editable=False)
    concepto_nombre = models.CharField(max_length=160, editable=False)
    institucion = models.ForeignKey(
        "instituciones.Institucion",
        on_delete=models.PROTECT,
        related_name="gastos",
    )
    area = models.ForeignKey(
        "instituciones.Area",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="gastos",
    )
    importe = models.DecimalField(max_digits=14, decimal_places=2)
    moneda = models.CharField(max_length=3, default="ARS", editable=False)
    periodo_economico = models.DateField()
    origen = models.CharField(max_length=20, choices=Origen.choices)
    estado = models.CharField(
        max_length=30,
        choices=Estado.choices,
        default=Estado.PENDIENTE_APROBACION,
    )
    sensible = models.BooleanField(default=False, editable=False)
    registrado_por = models.ForeignKey(
        "accounts.Usuario",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="gastos_registrados",
    )
    registrado = models.DateTimeField(auto_now_add=True)
    aprobado_por = models.ForeignKey(
        "accounts.Usuario",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="gastos_aprobados",
    )
    aprobado_en = models.DateTimeField(null=True, blank=True)
    rechazado_por = models.ForeignKey(
        "accounts.Usuario",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="gastos_rechazados",
    )
    rechazado_en = models.DateTimeField(null=True, blank=True)
    motivo_rechazo = models.CharField(max_length=255, blank=True)
    reemplaza = models.OneToOneField(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reemplazado_por",
    )

    class Meta:
        ordering = ["periodo_economico", "institucion_id", "area_id", "id"]
        constraints = [
            models.CheckConstraint(condition=Q(importe__gt=0), name="gasto_importe_positivo"),
        ]

    def clean(self):
        super().clean()
        if self.periodo_economico and self.periodo_economico.day != 1:
            raise ValidationError("El período económico de un gasto empieza el primer día del mes.")
        if self.moneda != "ARS":
            raise ValidationError("Los gastos de V1 se registran exclusivamente en ARS.")
        if self.concepto_id and self.institucion_id and self.concepto.institucion_id != self.institucion_id:
            raise ValidationError("El concepto debe pertenecer a la institución del gasto.")
        if self.area_id and self.institucion_id and self.area.institucion_id != self.institucion_id:
            raise ValidationError("El área debe pertenecer a la institución del gasto.")
        if self.origen == self.Origen.CENTRAL and self.estado != self.Estado.APROBADO:
            raise ValidationError("Una carga central debe registrarse aprobada.")
        if self.estado == self.Estado.PENDIENTE_APROBACION:
            if any((
                self.aprobado_por_id, self.aprobado_en, self.rechazado_por_id,
                self.rechazado_en, self.motivo_rechazo,
            )):
                raise ValidationError("Un gasto pendiente no tiene decisión registrada.")
        elif self.estado == self.Estado.APROBADO:
            if self.aprobado_por_id is None or self.aprobado_en is None:
                raise ValidationError("Un gasto aprobado requiere autor y fecha de aprobación.")
            if any((self.rechazado_por_id, self.rechazado_en, self.motivo_rechazo)):
                raise ValidationError("Un gasto aprobado no puede conservar datos de rechazo.")
        elif self.estado == self.Estado.RECHAZADO:
            if self.rechazado_por_id is None or self.rechazado_en is None or not self.motivo_rechazo.strip():
                raise ValidationError("Un gasto rechazado requiere autor, fecha y motivo.")
            if self.aprobado_por_id is not None or self.aprobado_en is not None:
                raise ValidationError("Un gasto rechazado no puede conservar una aprobación.")
        if self.reemplaza_id:
            if self.reemplaza.institucion_id != self.institucion_id:
                raise ValidationError("Un gasto sucesor debe pertenecer a la misma institución.")
            if self.reemplaza.estado == self.Estado.APROBADO:
                raise ValidationError("Un gasto aprobado se corrige mediante un ajuste, no se reemplaza.")

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            original = type(self).objects.get(pk=self.pk)
            campos_inmutables = (
                "concepto_id", "concepto_codigo", "concepto_nombre", "institucion_id",
                "area_id", "importe", "moneda", "periodo_economico", "origen",
                "sensible", "registrado_por_id", "registrado", "reemplaza_id",
            )
            if any(getattr(self, campo) != getattr(original, campo) for campo in campos_inmutables):
                raise ValidationError("Un gasto no edita su carga original; registrá un reemplazo o ajuste.")
            if original.estado != self.Estado.PENDIENTE_APROBACION:
                raise ValidationError("Un gasto ya decidido no se edita.")
            if self.estado not in {self.Estado.APROBADO, self.Estado.RECHAZADO}:
                raise ValidationError("Un gasto pendiente sólo puede aprobarse o rechazarse.")
            self.full_clean()
            return super().save(*args, **kwargs)

        if self.origen == self.Origen.AREA and self.estado != self.Estado.PENDIENTE_APROBACION:
            raise ValidationError("Una carga de área nace pendiente de aprobación.")
        if self.concepto_id is None:
            self.full_clean()
            return super().save(*args, **kwargs)
        with transaction.atomic(using=kwargs.get("using")):
            concepto = ConceptoGasto.objects.select_for_update().get(pk=self.concepto_id)
            self.concepto = concepto
            self.concepto_codigo = concepto.codigo
            self.concepto_nombre = concepto.nombre
            self.sensible = concepto.sensible
            self.full_clean()
            return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Un gasto no se elimina.")


class AjusteGasto(models.Model):
    """Corrección aditiva de una fuente aprobada, sin alterar el gasto original."""

    gasto = models.ForeignKey(Gasto, on_delete=models.PROTECT, related_name="ajustes")
    importe = models.DecimalField(max_digits=14, decimal_places=2)
    motivo = models.CharField(max_length=255)
    registrado_por = models.ForeignKey(
        "accounts.Usuario",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ajustes_gasto_registrados",
    )
    registrado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["registrado", "id"]
        constraints = [
            models.CheckConstraint(condition=~Q(importe=0), name="ajuste_gasto_no_cero"),
        ]

    def clean(self):
        super().clean()
        if self.gasto_id and self.gasto.estado != Gasto.Estado.APROBADO:
            raise ValidationError("Sólo se ajusta un gasto aprobado.")
        if not self.motivo.strip():
            raise ValidationError("Un ajuste de gasto requiere un motivo.")

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Un ajuste de gasto no se edita; se registra otro ajuste.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Un ajuste de gasto no se elimina.")


class HechoAtencionCosteable(models.Model):
    """Atención completada: origen durable, sin narrativa clínica."""
    institucion = models.ForeignKey("instituciones.Institucion", on_delete=models.PROTECT, related_name="hechos_atencion_costeables")
    evento = models.ForeignKey("casos.EventoCaso", on_delete=models.SET_NULL, null=True, blank=True, related_name="hechos_costo")
    evento_origen_id = models.BigIntegerField(unique=True)
    caso = models.ForeignKey("casos.Caso", on_delete=models.SET_NULL, null=True, blank=True, related_name="hechos_costo")
    caso_origen_id = models.BigIntegerField()
    ciudadano = models.ForeignKey("registros.Ciudadano", on_delete=models.SET_NULL, null=True, blank=True, related_name="hechos_costo")
    ciudadano_origen_id = models.BigIntegerField(null=True, blank=True)
    nodo = models.ForeignKey("flujos.Nodo", on_delete=models.SET_NULL, null=True, blank=True, related_name="hechos_costo")
    nodo_origen_id = models.BigIntegerField()
    area = models.ForeignKey("instituciones.Area", on_delete=models.SET_NULL, null=True, blank=True, related_name="hechos_costo")
    area_origen_id = models.BigIntegerField(null=True, blank=True)
    autor = models.ForeignKey("accounts.Usuario", on_delete=models.SET_NULL, null=True, blank=True, related_name="hechos_costo")
    ocurrida_en = models.DateTimeField()
    creado = models.DateTimeField(auto_now_add=True)
    componentes_congelados = models.BooleanField(default=False)
    ultimo_costeo_en = models.DateTimeField(null=True, blank=True)
    class Meta:
        ordering = ["ocurrida_en", "id"]

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Un hecho de atención costeable no se edita; los cambios económicos son ajustes.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Un hecho de atención costeable no se elimina.")


class ImputacionCosto(models.Model):
    hecho = models.ForeignKey(HechoAtencionCosteable, on_delete=models.PROTECT, related_name="imputaciones")
    componente = models.ForeignKey(DefinicionComponente, on_delete=models.PROTECT, related_name="imputaciones")
    valor = models.ForeignKey(ValorComponente, on_delete=models.PROTECT, related_name="imputaciones")
    importe = models.DecimalField(max_digits=14, decimal_places=2)
    unidad = models.CharField(
        max_length=30,
        choices=DefinicionComponente.Unidad.choices,
        default=DefinicionComponente.Unidad.ATENCION,
    )
    base_calculo = models.CharField(
        max_length=30,
        choices=DefinicionComponente.BaseCalculo.choices,
        default=DefinicionComponente.BaseCalculo.POR_ATENCION,
    )
    moneda = models.CharField(max_length=3, choices=ValorComponente.Moneda.choices, default=ValorComponente.Moneda.ARS)
    creado = models.DateTimeField(auto_now_add=True)
    class Meta:
        unique_together = [("hecho", "componente")]
        constraints = [models.CheckConstraint(condition=Q(importe__gte=0), name="imputacion_costo_no_negativa")]

    def clean(self):
        super().clean()
        if self.valor_id and self.moneda != self.valor.moneda:
            raise ValidationError("La imputación conserva la moneda del valor aplicado.")
        if self.hecho_id and self.componente_id:
            esperado = ComponenteEsperadoHecho.objects.filter(
                hecho_id=self.hecho_id,
                componente_id=self.componente_id,
            ).first()
            if esperado is None:
                raise ValidationError("La imputación requiere un componente congelado para el hecho.")
            if (self.unidad, self.base_calculo) != (esperado.unidad, esperado.base_calculo):
                raise ValidationError("La imputación conserva la unidad y base congeladas del componente.")

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Una imputación de costo no se edita; se registra un ajuste.")
        self.full_clean()
        return super().save(*args, **kwargs)


class AjusteCosto(models.Model):
    """Corrección histórica sin sobrescribir la imputación que la originó."""

    imputacion = models.ForeignKey(
        ImputacionCosto,
        on_delete=models.PROTECT,
        related_name="ajustes",
    )
    importe = models.DecimalField(max_digits=14, decimal_places=2)
    motivo = models.CharField(max_length=255)
    registrado_por = models.ForeignKey(
        "accounts.Usuario",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ajustes_costo_registrados",
    )
    registrado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["registrado", "id"]
        constraints = [
            models.CheckConstraint(
                condition=~Q(importe=0),
                name="ajuste_costo_no_cero",
            ),
        ]

    def clean(self):
        super().clean()
        if not self.motivo.strip():
            raise ValidationError("Un ajuste de costo requiere un motivo.")

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Un ajuste de costo no se edita; se registra otro ajuste.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Un ajuste de costo no se elimina.")


class CorreccionSnapshotCosteo(models.Model):
    """Autoriza y explica aplicar catálogo actual a un snapshot fallido."""

    hecho = models.ForeignKey(
        HechoAtencionCosteable,
        on_delete=models.PROTECT,
        related_name="correcciones_snapshot",
    )
    motivo = models.CharField(max_length=255)
    registrado_por = models.ForeignKey(
        "accounts.Usuario",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="correcciones_snapshot_registradas",
    )
    registrado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["registrado", "id"]

    def clean(self):
        super().clean()
        if not self.motivo.strip():
            raise ValidationError("Una corrección de snapshot requiere un motivo.")

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Una corrección de snapshot no se edita; se registra otra corrección.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Una corrección de snapshot no se elimina.")


class ComponenteEsperadoHecho(models.Model):
    """Congela los componentes que podían costear una atención al resolverla."""
    hecho = models.ForeignKey(HechoAtencionCosteable, on_delete=models.PROTECT, related_name="componentes_esperados")
    componente = models.ForeignKey(DefinicionComponente, on_delete=models.PROTECT, related_name="hechos_esperados")
    sensible = models.BooleanField(default=False)
    unidad = models.CharField(
        max_length=30,
        choices=DefinicionComponente.Unidad.choices,
        default=DefinicionComponente.Unidad.ATENCION,
    )
    base_calculo = models.CharField(
        max_length=30,
        choices=DefinicionComponente.BaseCalculo.choices,
        default=DefinicionComponente.BaseCalculo.POR_ATENCION,
    )
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("hecho", "componente")]


class PendienteCosteo(models.Model):
    class Motivo(models.TextChoices):
        SIN_PRESTACION = "sin_prestacion", "Sin prestación configurada"
        SIN_COMPONENTES = "sin_componentes", "Sin componentes configurados"
        SIN_VALOR = "sin_valor", "Sin valor vigente"
        ERROR_RECUPERABLE = "error_recuperable", "Error recuperable"
        SNAPSHOT_INCOMPLETO = "snapshot_incompleto", "No se pudo congelar el catálogo aplicable"
    hecho = models.ForeignKey(HechoAtencionCosteable, on_delete=models.PROTECT, related_name="pendientes")
    componente = models.ForeignKey(DefinicionComponente, on_delete=models.PROTECT, null=True, blank=True, related_name="pendientes")
    motivo = models.CharField(max_length=40, choices=Motivo.choices)
    resuelto = models.BooleanField(default=False)
    creado = models.DateTimeField(auto_now_add=True)
    resuelto_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["hecho", "motivo"],
                condition=Q(componente__isnull=True),
                name="pendiente_sin_componente_unico",
            ),
            models.UniqueConstraint(
                fields=["hecho", "componente", "motivo"],
                condition=Q(componente__isnull=False),
                name="pendiente_con_componente_unico",
            ),
        ]


class CoberturaActividadCosteable(models.Model):
    """Habilitación prospectiva e inmutable de hechos de atención por ámbito."""

    institucion = models.ForeignKey("instituciones.Institucion", on_delete=models.PROTECT)
    area = models.ForeignKey("instituciones.Area", on_delete=models.PROTECT)
    vigente_desde = models.DateField()
    vigente_hasta = models.DateField(null=True, blank=True)
    reemplaza = models.OneToOneField(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="reemplazada_por"
    )
    motivo_correccion = models.CharField(max_length=255, blank=True)
    registrado_por = models.ForeignKey(
        "accounts.Usuario", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="coberturas_actividad_registradas",
    )
    registrado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["institucion_id", "area_id", "vigente_desde", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(vigente_hasta__isnull=True) | Q(vigente_hasta__gt=models.F("vigente_desde")),
                name="vigencia_cobertura_actividad_valida",
            ),
        ]

    def clean(self):
        super().clean()
        if self.vigente_desde and self.vigente_desde.day != 1:
            raise ValidationError("La cobertura de actividad empieza el primer día del mes.")
        if self.vigente_hasta and self.vigente_hasta.day != 1:
            raise ValidationError("La cobertura de actividad termina el primer día de un mes.")
        if self.area_id and self.institucion_id and self.area.institucion_id != self.institucion_id:
            raise ValidationError("El área debe pertenecer a la institución de la cobertura.")
        if self.reemplaza_id and (
            self.reemplaza.institucion_id != self.institucion_id
            or self.reemplaza.area_id != self.area_id
        ):
            raise ValidationError("Una cobertura sucesora conserva institución y área.")
        if self.reemplaza_id and self.vigente_desde < self.reemplaza.vigente_desde:
            raise ValidationError("Una cobertura sucesora no puede empezar antes de la reemplazada.")
        if self.reemplaza_id:
            if not self.motivo_correccion.strip():
                raise ValidationError("Una corrección de cobertura requiere un motivo.")
            if (
                self.vigente_desde == self.reemplaza.vigente_desde
                and self.vigente_hasta != self.reemplaza.vigente_hasta
            ):
                raise ValidationError("Una corrección conserva la vigencia de la cobertura corregida.")
        if not (self.institucion_id and self.area_id and self.vigente_desde):
            return
        solapa = Q(vigente_hasta__isnull=True) | Q(vigente_hasta__gt=self.vigente_desde)
        if self.vigente_hasta is not None:
            solapa &= Q(vigente_desde__lt=self.vigente_hasta)
        existentes = type(self).objects.filter(
            institucion_id=self.institucion_id, area_id=self.area_id,
            reemplazada_por__isnull=True,
        ).exclude(pk=self.pk)
        if self.reemplaza_id:
            existentes = existentes.exclude(pk=self.reemplaza_id)
        if existentes.filter(solapa).exists():
            raise ValidationError("Ya existe una cobertura vigente para ese intervalo.")

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Una cobertura de actividad no se edita; registrá una versión.")
        # Toda vía de alta, incluida administración o scripts, toma el mismo
        # bloqueo. Dos confirmaciones simultáneas del área no pueden validar
        # contra el mismo estado vacío y crear intervalos superpuestos.
        using = kwargs.get("using")
        area_model = self._meta.get_field("area").remote_field.model
        with transaction.atomic(using=using):
            if self.area_id:
                area_model.objects.select_for_update().get(pk=self.area_id)
            self.full_clean()
            return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Una cobertura de actividad no se elimina.")


class ReglaRepartoActividad(models.Model):
    """Regla versionada de reparto por cantidad de atenciones del mismo ámbito."""

    concepto = models.ForeignKey(ConceptoGasto, on_delete=models.PROTECT)
    institucion = models.ForeignKey("instituciones.Institucion", on_delete=models.PROTECT)
    area = models.ForeignKey("instituciones.Area", on_delete=models.PROTECT)
    vigente_desde = models.DateField()
    vigente_hasta = models.DateField(null=True, blank=True)
    sensible = models.BooleanField(default=False, editable=False)
    reemplaza = models.OneToOneField(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="reemplazada_por"
    )
    motivo_correccion = models.CharField(max_length=255, blank=True)
    registrado_por = models.ForeignKey(
        "accounts.Usuario", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="reglas_reparto_registradas",
    )
    registrado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["institucion_id", "area_id", "concepto_id", "vigente_desde", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(vigente_hasta__isnull=True) | Q(vigente_hasta__gt=models.F("vigente_desde")),
                name="vigencia_regla_reparto_valida",
            ),
        ]

    def clean(self):
        super().clean()
        if self.vigente_desde and self.vigente_desde.day != 1:
            raise ValidationError("La regla de reparto empieza el primer día del mes.")
        if self.vigente_hasta and self.vigente_hasta.day != 1:
            raise ValidationError("La regla de reparto termina el primer día de un mes.")
        if self.concepto_id and self.institucion_id and self.concepto.institucion_id != self.institucion_id:
            raise ValidationError("El concepto debe pertenecer a la institución de la regla.")
        if self.area_id and self.institucion_id and self.area.institucion_id != self.institucion_id:
            raise ValidationError("El área debe pertenecer a la institución de la regla.")
        if self.reemplaza_id and (
            self.reemplaza.concepto_id != self.concepto_id
            or self.reemplaza.institucion_id != self.institucion_id
            or self.reemplaza.area_id != self.area_id
        ):
            raise ValidationError("Una regla sucesora conserva concepto, institución y área.")
        if self.reemplaza_id and self.vigente_desde < self.reemplaza.vigente_desde:
            raise ValidationError("Una regla sucesora no puede empezar antes de la reemplazada.")
        if self.reemplaza_id:
            if not self.motivo_correccion.strip():
                raise ValidationError("Una corrección de regla requiere un motivo.")
            if (
                self.vigente_desde == self.reemplaza.vigente_desde
                and self.vigente_hasta != self.reemplaza.vigente_hasta
            ):
                raise ValidationError("Una corrección conserva la vigencia de la regla corregida.")
        if not (self.concepto_id and self.institucion_id and self.area_id and self.vigente_desde):
            return
        solapa = Q(vigente_hasta__isnull=True) | Q(vigente_hasta__gt=self.vigente_desde)
        if self.vigente_hasta is not None:
            solapa &= Q(vigente_desde__lt=self.vigente_hasta)
        existentes = type(self).objects.filter(
            concepto_id=self.concepto_id, institucion_id=self.institucion_id,
            area_id=self.area_id, reemplazada_por__isnull=True,
        ).exclude(pk=self.pk)
        if self.reemplaza_id:
            existentes = existentes.exclude(pk=self.reemplaza_id)
        if existentes.filter(solapa).exists():
            raise ValidationError("Ya existe una regla vigente para ese intervalo.")

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Una regla de reparto no se edita; registrá una versión.")
        if self.concepto_id:
            self.sensible = self.concepto.sensible
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Una regla de reparto no se elimina.")


class RepartoGasto(models.Model):
    """Versión explicable de un reparto o de un pendiente de reparto."""

    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        DISTRIBUIDO = "distribuido", "Distribuido"
        SIN_ACTIVIDAD = "sin_actividad", "Sin actividad acreditada"

    class Motivo(models.TextChoices):
        SIN_REGLA = "sin_regla", "Sin regla aplicable"
        SIN_COBERTURA = "sin_cobertura", "Sin cobertura acreditada"
        ACTIVIDAD_INCOMPLETA = "actividad_incompleta", "Actividad técnicamente incompleta"
        FUENTE_NO_ELEGIBLE = "fuente_no_elegible", "Fuente no elegible"

    gasto = models.ForeignKey(Gasto, on_delete=models.PROTECT, related_name="repartos")
    regla = models.ForeignKey(ReglaRepartoActividad, on_delete=models.PROTECT, null=True, blank=True)
    cobertura = models.ForeignKey(CoberturaActividadCosteable, on_delete=models.PROTECT, null=True, blank=True)
    version = models.PositiveIntegerField()
    huella_insumos = models.CharField(max_length=64)
    importe_fuente_centavos = models.BigIntegerField()
    importe_ajustes_centavos = models.BigIntegerField()
    saldo_centavos = models.BigIntegerField()
    saldo_no_atribuido_centavos = models.BigIntegerField(default=0)
    estado = models.CharField(max_length=20, choices=Estado.choices)
    motivo = models.CharField(max_length=30, choices=Motivo.choices, blank=True)
    reemplaza = models.OneToOneField(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="reemplazado_por"
    )
    calculado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["gasto_id", "version"]
        constraints = [
            models.UniqueConstraint(fields=["gasto", "version"], name="version_reparto_gasto_unica"),
            models.UniqueConstraint(fields=["gasto", "huella_insumos"], name="insumos_reparto_gasto_unicos"),
        ]

    def clean(self):
        super().clean()
        if self.regla_id and self.gasto_id and (
            self.regla.concepto_id != self.gasto.concepto_id
            or self.regla.institucion_id != self.gasto.institucion_id
            or self.regla.area_id != self.gasto.area_id
        ):
            raise ValidationError("La regla debe coincidir con el ámbito del gasto.")
        if self.cobertura_id and self.gasto_id and (
            self.cobertura.institucion_id != self.gasto.institucion_id
            or self.cobertura.area_id != self.gasto.area_id
        ):
            raise ValidationError("La cobertura debe coincidir con el ámbito del gasto.")
        if self.estado == self.Estado.PENDIENTE and not self.motivo:
            raise ValidationError("Un reparto pendiente requiere motivo.")
        if self.estado != self.Estado.PENDIENTE and self.motivo:
            raise ValidationError("Sólo un reparto pendiente conserva motivo.")
        if self.estado == self.Estado.SIN_ACTIVIDAD and self.saldo_no_atribuido_centavos != self.saldo_centavos:
            raise ValidationError("Sin actividad, todo el saldo queda sin atribuir.")

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Un reparto de gasto no se edita; se genera una versión.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Un reparto de gasto no se elimina.")


class AtribucionReparto(models.Model):
    reparto = models.ForeignKey(RepartoGasto, on_delete=models.PROTECT, related_name="atribuciones")
    hecho = models.ForeignKey(HechoAtencionCosteable, on_delete=models.PROTECT, related_name="atribuciones_reparto")
    importe_centavos = models.BigIntegerField()

    class Meta:
        ordering = ["reparto_id", "hecho_id"]
        constraints = [
            models.UniqueConstraint(fields=["reparto", "hecho"], name="atribucion_reparto_hecho_unica"),
        ]

    def clean(self):
        super().clean()
        if self.reparto_id and self.hecho_id and (
            self.reparto.gasto.institucion_id != self.hecho.institucion_id
            or self.reparto.gasto.area_id != self.hecho.area_origen_id
        ):
            raise ValidationError("El hecho debe pertenecer al mismo ámbito del reparto.")

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Una atribución de reparto no se edita.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Una atribución de reparto no se elimina.")
