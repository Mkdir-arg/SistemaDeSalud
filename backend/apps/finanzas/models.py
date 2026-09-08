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


    def clean(self):
        super().clean()
        if self.accion in {
            self.Accion.CONFIGURAR_COMPONENTES,
            self.Accion.CORREGIR_COSTOS,
        } and self.membresia.rol != "admin":
            raise ValidationError(
                "La configuración y corrección de costos requieren una membresía administrativa."
            )
        if self.permite_sensibles and self.membresia.rol != "admin":
            raise ValidationError(
                "El acceso a costos sensibles requiere una membresía administrativa."
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


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
