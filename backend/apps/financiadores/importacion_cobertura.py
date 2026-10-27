"""La opción del lote rige altas nuevas; una diferencia nunca cambia cobertura existente."""
from django.core.exceptions import ValidationError


def validar_opcion(valor):
    if valor is not None and not isinstance(valor, bool):
        raise ValidationError("Indicá si las personas nuevas tendrán habilitada la cobertura.")


def revisar_cobertura(fila, afiliado, solicitada, motivo=""):
    """Exige revisar la diferencia observada, nunca acepta una foto desactualizada."""
    if solicitada is None:
        return  # Lotes anteriores conservan su contrato original.
    if afiliado is None or afiliado.cobertura_habilitada == solicitada:
        fila.pop("conflicto_cobertura", None)
        return
    actual = {"afiliado": afiliado.pk, "revision": afiliado.revision,
              "actual": afiliado.cobertura_habilitada, "solicitada": solicitada}
    anterior = fila.get("conflicto_cobertura")
    fila["conflicto_cobertura"] = actual
    if motivo.strip() and anterior == actual:
        fila["cobertura_revisada"] = actual.copy()
        fila["motivo_cobertura"] = motivo.strip()
    if fila.get("cobertura_revisada") != actual:
        estado = "habilitada" if actual["actual"] else "sin habilitar"
        raise ValidationError(
            f"Conflicto de cobertura: el padrón la tiene {estado} y difiere de la opción del lote. "
            "Confirmá con un motivo que se conserva la cobertura actual.", code="conflicto_cobertura")


def es_conflicto_cobertura(error):
    return any(getattr(e, "code", None) == "conflicto_cobertura" for e in getattr(error, "error_list", []))
