"""Dónde se guardan los archivos subidos: disco local o un bucket S3 (#171).

Sin las variables del bucket todo sigue en disco: `default` en `MEDIA_ROOT` y
las facturas en `SALUD_FACTURAS_ADJUNTOS_DIR`. Con las variables, los dos usan
el mismo bucket privado: los adjuntos clínicos con sus claves de siempre
(`uploads/<institución>/<uuid>.<ext>`) y las facturas bajo `facturas/`.

Los nombres son los que Railway Storage Buckets expone en el bucket
(https://docs.railway.com/storage-buckets): `BUCKET`, `ACCESS_KEY_ID`,
`SECRET_ACCESS_KEY`, `ENDPOINT` y `REGION`. Cualquier S3 compatible sirve con
esas mismas variables, y por eso migrar es copiar objetos y cambiarlas: la base
guarda claves de objeto, nunca URLs del proveedor.

La descarga no usa URLs del bucket: Django verifica el permiso, audita y
transmite el objeto (`FileResponse`), igual que con el disco. Por eso no hay
`url()` pública ni ACL: el bucket queda privado.
"""

VARIABLES_OBLIGATORIAS = ("BUCKET", "ACCESS_KEY_ID", "SECRET_ACCESS_KEY", "ENDPOINT")
PREFIJO_FACTURAS = "facturas"


def opciones_bucket(entorno):
    """Las opciones de `S3Storage`, o None si no hay bucket configurado.

    Configurar solo una parte es un error y no un «sin bucket»: caer a disco en
    silencio perdería los archivos en el próximo redespliegue.
    """
    valores = {nombre: (entorno.get(nombre) or "").strip() for nombre in VARIABLES_OBLIGATORIAS}
    if not any(valores.values()):
        return None
    faltan = [nombre for nombre, valor in valores.items() if not valor]
    if faltan:
        raise ValueError(
            "Configuración de bucket incompleta: faltan " + ", ".join(faltan)
            + ". Definí las cuatro o ninguna (sin ninguna se usa el disco local)."
        )
    estilo = (entorno.get("BUCKET_ADDRESSING_STYLE") or "virtual").strip().lower()
    if estilo not in {"virtual", "path"}:
        raise ValueError("BUCKET_ADDRESSING_STYLE debe ser «virtual» o «path».")
    return {
        "bucket_name": valores["BUCKET"],
        "access_key": valores["ACCESS_KEY_ID"],
        "secret_key": valores["SECRET_ACCESS_KEY"],
        "endpoint_url": valores["ENDPOINT"],
        "region_name": (entorno.get("REGION") or "").strip() or "auto",
        "addressing_style": estilo,
        "signature_version": "s3v4",
        # Privado: sin ACL propia (vale la del bucket) y sin URLs públicas.
        "default_acl": None,
        "querystring_auth": True,
        "querystring_expire": 60,
        # Como FileSystemStorage: un nombre ocupado nunca se pisa.
        "file_overwrite": False,
    }


def storages(entorno, carpeta_facturas):
    """`STORAGES["default"]`, `STORAGES["facturas"]` y si se usa el bucket."""
    bucket = opciones_bucket(entorno)
    if bucket is None:
        return {
            "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
            "facturas": {
                "BACKEND": "django.core.files.storage.FileSystemStorage",
                "OPTIONS": {"location": str(carpeta_facturas)},
            },
        }, False
    s3 = "storages.backends.s3.S3Storage"
    return {
        "default": {"BACKEND": s3, "OPTIONS": dict(bucket)},
        "facturas": {"BACKEND": s3, "OPTIONS": {**bucket, "location": PREFIJO_FACTURAS}},
    }, True
