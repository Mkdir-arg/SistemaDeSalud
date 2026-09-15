"""Filtros de columnas aplicados antes de paginar los listados financieros."""
from rest_framework import serializers


def filtrar_rangos(queryset, parametros, *, importes=(), cantidades=(), fechas=()):
    campos = {}
    filtros = {}
    for nombre in (*importes, *cantidades):
        for sufijo, operador in (("min", "gte"), ("max", "lte")):
            clave = f"{nombre}_{sufijo}"
            campos[clave] = (
                serializers.DecimalField(max_digits=22, decimal_places=2, required=False)
                if nombre in importes else serializers.IntegerField(required=False)
            )
            filtros[clave] = f"{nombre}__{operador}"
    for nombre in fechas:
        for sufijo, operador in (("desde", "gte"), ("hasta", "lte")):
            clave = f"{nombre}_{sufijo}"
            campos[clave] = serializers.DateField(required=False)
            filtros[clave] = f"{nombre}__date__{operador}"
    entrada = serializers.Serializer()
    entrada.fields.update(campos)
    datos = {k: parametros[k] for k in campos if parametros.get(k) not in (None, "")}
    validos = entrada.run_validation(datos)
    return queryset.filter(**{filtros[k]: valor for k, valor in validos.items()})
