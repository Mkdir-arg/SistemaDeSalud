"""Calendario y variaciones nominales; la falta de registros no prueba un cero."""
from datetime import date
from decimal import Decimal

from rest_framework import serializers


class ContextoComparativa(serializers.Serializer):
    institucion = serializers.IntegerField(min_value=1)
    area = serializers.IntegerField(min_value=1, required=False)
    area_sin_asignar = serializers.BooleanField(default=False)
    periodo_economico = serializers.DateField()
    comparar = serializers.ChoiceField(choices=["mes_anterior", "anio_anterior"], default="mes_anterior")
    meses = serializers.ChoiceField(choices=[6, 12], default=6)

    def validate(self, attrs):
        mes = attrs["periodo_economico"]
        if mes.day != 1 or mes.year < 2:
            raise serializers.ValidationError("Elegí el primer día de un mes desde el año 0002.")
        return attrs


def desplazar_mes(mes, cantidad):
    numero = mes.year * 12 + mes.month - 1 + cantidad
    return date(numero // 12, numero % 12 + 1, 1)


def periodos_comparados(parametros):
    entrada = ContextoComparativa(data=parametros)
    entrada.is_valid(raise_exception=True)
    datos = entrada.validated_data
    actual = datos["periodo_economico"]
    anterior = desplazar_mes(actual, -12 if datos["comparar"] == "anio_anterior" else -1)
    serie = [desplazar_mes(actual, n) for n in range(1 - datos["meses"], 1)]
    return actual, anterior, serie


def comparar(actual, anterior, disponible=True):
    if not disponible or actual is None or anterior is None:
        return {"importe": None, "porcentaje": None, "motivo": "Sin registros comparables"}
    actual, anterior = Decimal(actual), Decimal(anterior)
    diferencia = actual - anterior
    # Una base negativa hace ambiguo interpretar la variación relativa.
    porcentaje = diferencia / anterior * 100 if anterior > 0 else None
    return {
        "importe": format(diferencia, ".2f"),
        "porcentaje": format(porcentaje, ".2f") if porcentaje is not None else None,
        "motivo": None if porcentaje is not None else "Base anterior cero o negativa; comparar en pesos",
    }
