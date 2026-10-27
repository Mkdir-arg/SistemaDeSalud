"""Descarga pública y publicación atómica; jamás se ejecuta al buscar un lugar."""
import hashlib
import json
from datetime import timedelta
from time import monotonic
from urllib.request import Request

from django.db import transaction
from django.utils import timezone

from apps.http_seguro import abrir_sin_redirecciones
from .contrato import SEMANA, validar_catalogo
from .models import Catalogo, Lugar

RECURSOS = {"provincia": "provincias", "partido": "departamentos", "localidad": "localidades"}
MAX_RESPUESTA = 8 * 1024 * 1024
MAX_ENTIDADES = 100000


def descargar(abrir=abrir_sin_redirecciones):
    resultado = {}
    comienzo, acumulado = monotonic(), 0
    for tipo, recurso in RECURSOS.items():
        filas, inicio, total = [], 0, None
        while total is None or inicio < total:
            if monotonic() - comienzo > 120:
                raise ValueError("Se excedió el plazo de descarga del catálogo.")
            url = f"https://apis.datos.gob.ar/georef/api/{recurso}?max=1000&inicio={inicio}&orden=id"
            with abrir(Request(url, headers={"Accept": "application/json", "User-Agent": "PLEXO-Geografia/1"}), timeout=20) as respuesta:
                datos = respuesta.read(MAX_RESPUESTA + 1)
            acumulado += len(datos)
            if len(datos) > MAX_RESPUESTA or acumulado > 32 * 1024 * 1024:
                raise ValueError("Respuesta territorial demasiado grande.")
            if monotonic() - comienzo > 120:
                raise ValueError("Se excedió el plazo de descarga del catálogo.")
            pagina = json.loads(datos)
            if not isinstance(pagina, dict):
                raise ValueError("Respuesta territorial inválida.")
            nuevo_total, lote = pagina.get("total"), pagina.get(recurso)
            if (not isinstance(nuevo_total, int) or isinstance(nuevo_total, bool)
                    or not 0 < nuevo_total <= MAX_ENTIDADES or not isinstance(lote, list)
                    or not lote or len(lote) > 1000 or type(pagina.get("inicio")) is not int or pagina["inicio"] != inicio
                    or type(pagina.get("cantidad")) is not int or pagina["cantidad"] != len(lote)
                    or total is not None and total != nuevo_total):
                raise ValueError("Descarga territorial parcial o inconsistente.")
            total = nuevo_total
            filas.extend(lote)
            inicio += len(lote)
            if inicio > total:
                raise ValueError("La descarga excede el total informado.")
        resultado[tipo] = filas
    return validar_catalogo(resultado)


def sincronizar(*, seco=False, descargar_fn=descargar):
    if seco:
        return {"entidades": len(descargar_fn()), "publicado": False}
    catalogo, _ = Catalogo.objects.get_or_create(pk=1)
    version = catalogo.version
    intento = timezone.now()
    Catalogo.objects.filter(pk=1, version=version).update(intento=intento)
    try:
        filas = descargar_fn()
        # Revalidar también resultados de un transporte sustituido por pruebas.
        if not filas or any(f.get("tipo") not in RECURSOS for f in filas):
            raise ValueError("Catálogo territorial inválido.")
        huella = hashlib.sha256(json.dumps(filas, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        with transaction.atomic():
            actual = Catalogo.objects.select_for_update().get(pk=1)
            if actual.version != version:
                return {"entidades": len(filas), "publicado": False, "superado": True}
            por_codigo, presentes = {}, []
            for fila in filas:
                lugar, _ = Lugar.objects.update_or_create(origen="georef", tipo=fila["tipo"], codigo=fila["codigo"], defaults={
                    "nombre": fila["nombre"], "activo": True,
                    "provincia": por_codigo.get(("provincia", fila["provincia"])),
                    "partido": por_codigo.get(("partido", fila["partido"])),
                })
                por_codigo[(fila["tipo"], fila["codigo"])] = lugar
                presentes.append(lugar.pk)
            Lugar.objects.filter(origen="georef").exclude(pk__in=presentes).update(activo=False)
            actual.version += 1
            actual.actualizado, actual.intento, actual.huella, actual.error = timezone.now(), intento, huella, ""
            actual.save()
        return {"entidades": len(filas), "publicado": True}
    except Exception:
        # Sin URL, payload ni texto arbitrario de respuestas externas.
        Catalogo.objects.filter(pk=1, version=version, intento=intento).update(error="No se completó la actualización de Georef; se conserva el catálogo anterior.")
        raise


def corresponde(catalogo, ahora=None):
    ahora = ahora or timezone.now()
    if catalogo and catalogo.actualizado and ahora - catalogo.actualizado < timedelta(seconds=SEMANA):
        return False
    # Ante fallas, como máximo un intento por día, sin bloquear cargas manuales.
    return not catalogo or not catalogo.intento or ahora - catalogo.intento >= timedelta(days=1)
