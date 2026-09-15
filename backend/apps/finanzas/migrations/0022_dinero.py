from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("finanzas", "0021_trabajo_reparto"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.AlterField(model_name="concesionfinanciera", name="accion", field=models.CharField(max_length=40, choices=[
            ("ver_costos", "Ver costos"), ("configurar_componentes", "Configurar componentes"),
            ("corregir_costos", "Corregir costos"), ("ver_gastos", "Ver gastos"),
            ("registrar_gastos", "Registrar gastos"), ("aprobar_gastos", "Aprobar gastos"),
            ("corregir_gastos", "Corregir gastos"), ("configurar_gastos_esperados", "Configurar gastos esperados"),
            ("auditar_finanzas", "Auditar accesos financieros"), ("configurar_repartos", "Configurar repartos"),
            ("ver_dinero", "Ver pagos y cobros"), ("registrar_dinero", "Registrar pagos y cobros"),
            ("corregir_dinero", "Reducir obligaciones y reintegrar dinero"), ("configurar_cobros", "Configurar cobros"),
        ])),
        migrations.CreateModel(name="ObligacionFinanciera", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("tipo", models.CharField(max_length=6, choices=[("pagar", "A pagar"), ("cobrar", "A cobrar")])),
            ("sensible", models.BooleanField(default=False)),
            ("importe_original", models.DecimalField(max_digits=14, decimal_places=2)),
            ("moneda", models.CharField(max_length=3, default="ARS", editable=False)),
            ("periodo_economico", models.DateField()),
            ("contraparte_nombre", models.CharField(max_length=160)),
            ("contraparte_referencia", models.CharField(max_length=160, blank=True)),
            ("clave", models.UUIDField()), ("solicitud", models.JSONField(default=dict)),
            ("creado", models.DateTimeField(auto_now_add=True)),
            ("gasto", models.OneToOneField(to="finanzas.gasto", on_delete=django.db.models.deletion.PROTECT, null=True, blank=True, related_name="obligacion")),
            ("hecho", models.ForeignKey(to="finanzas.hechoatencioncosteable", on_delete=django.db.models.deletion.PROTECT, null=True, blank=True, related_name="obligaciones")),
            ("institucion", models.ForeignKey(to="instituciones.institucion", on_delete=django.db.models.deletion.PROTECT)),
            ("area", models.ForeignKey(to="instituciones.area", on_delete=django.db.models.deletion.PROTECT, null=True, blank=True)),
            ("creado_por", models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.PROTECT, null=True, blank=True)),
        ], options={"ordering": ["-creado", "-id"], "constraints": [
            models.UniqueConstraint(fields=["institucion", "clave"], name="obligacion_clave_unica"),
            models.CheckConstraint(condition=models.Q(importe_original__gt=0), name="obligacion_importe_positivo"),
            models.CheckConstraint(condition=(models.Q(tipo="pagar", gasto__isnull=False, hecho__isnull=True) | models.Q(tipo="cobrar", gasto__isnull=True, hecho__isnull=False)), name="obligacion_fuente_valida"),
        ]}),
        migrations.CreateModel(name="AjusteObligacion", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("importe", models.DecimalField(max_digits=14, decimal_places=2)),
            ("motivo", models.CharField(max_length=255)),
            ("clave", models.UUIDField()), ("solicitud", models.JSONField(default=dict)),
            ("registrado", models.DateTimeField(auto_now_add=True)),
            ("obligacion", models.ForeignKey(to="finanzas.obligacionfinanciera", on_delete=django.db.models.deletion.PROTECT, related_name="ajustes")),
            ("institucion", models.ForeignKey(to="instituciones.institucion", on_delete=django.db.models.deletion.PROTECT)),
            ("autor", models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.PROTECT)),
        ], options={"ordering": ["registrado", "id"], "constraints": [
            models.UniqueConstraint(fields=["institucion", "clave"], name="ajuste_obligacion_clave_unica"),
            models.CheckConstraint(condition=models.Q(importe__lt=0), name="ajuste_obligacion_negativo"),
        ]}),
        migrations.CreateModel(name="MovimientoDinero", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("tipo", models.CharField(max_length=10, choices=[("pago", "Pago"), ("cobro", "Cobro"), ("reintegro", "Reintegro")])),
            ("importe", models.DecimalField(max_digits=14, decimal_places=2)),
            ("fecha", models.DateField()),
            ("referencia", models.CharField(max_length=160, blank=True)),
            ("motivo", models.CharField(max_length=255, blank=True)),
            ("clave", models.UUIDField()), ("solicitud", models.JSONField(default=dict)),
            ("registrado", models.DateTimeField(auto_now_add=True)),
            ("obligacion", models.ForeignKey(to="finanzas.obligacionfinanciera", on_delete=django.db.models.deletion.PROTECT, related_name="movimientos")),
            ("institucion", models.ForeignKey(to="instituciones.institucion", on_delete=django.db.models.deletion.PROTECT)),
            ("original", models.ForeignKey(to="finanzas.movimientodinero", on_delete=django.db.models.deletion.PROTECT, null=True, blank=True, related_name="reintegros")),
            ("ajuste", models.ForeignKey(to="finanzas.ajusteobligacion", on_delete=django.db.models.deletion.PROTECT, null=True, blank=True, related_name="reintegros")),
            ("autor", models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.PROTECT)),
        ], options={"ordering": ["-fecha", "-registrado", "-id"], "constraints": [
            models.UniqueConstraint(fields=["institucion", "clave"], name="movimiento_dinero_clave_unica"),
            models.CheckConstraint(condition=models.Q(importe__gt=0), name="movimiento_importe_positivo"),
            models.CheckConstraint(condition=(models.Q(tipo="reintegro", original__isnull=False) | models.Q(tipo__in=["pago", "cobro"], original__isnull=True, ajuste__isnull=True)), name="movimiento_original_valido"),
        ]}),
    ]
