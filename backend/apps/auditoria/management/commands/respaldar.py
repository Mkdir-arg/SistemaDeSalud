"""
Respaldo de la base, con la restauración incluida en el mismo comando.

**Un respaldo que nunca se restauró no es un respaldo.** Es la falla clásica y
siempre la misma historia: el cron corrió dos años, los archivos estaban ahí, y
el día que hizo falta ninguno servía —la contraseña había cambiado, el volcado
salía truncado, el disco se había llenado en silencio—. Nadie lo supo antes
porque nadie lo abrió nunca.

Por eso este comando **verifica por defecto**: saca el volcado, lo restaura en
una base descartable y cuenta filas de las tablas que importan. Si algo no
cuadra, falla con código distinto de cero, que es lo que un monitor puede mirar.

    python manage.py respaldar                      # saca y verifica
    python manage.py respaldar --destino /respaldos # dónde dejarlo
    python manage.py respaldar --sin-verificar      # sólo para una corrida rápida

Necesita `pg_dump`/`psql` en el contenedor y las credenciales de la base, que ya
salen de DATABASE_URL.
"""
import os
import secrets
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from apps.auditoria.latidos import latir

# Tablas cuyo conteo se compara entre el original y el restaurado.
#
# No se comparan todas: alcanza con las que dolería perder y las que un volcado
# truncado dejaría cortadas. Si estas cinco están completas, el archivo se leyó
# entero.
TABLAS = [
    "registros_ciudadano",
    "registros_entradahistoria",
    "casos_caso",
    "auditoria_accesoclinico",
    "accounts_usuario",
]


def _credenciales():
    """Datos de conexión, sacados de lo que Django ya resolvió."""
    cfg = settings.DATABASES["default"]
    url = os.environ.get("DATABASE_URL", "")
    partes = urlparse(url) if url else None
    return {
        "host": cfg.get("HOST") or (partes.hostname if partes else "localhost"),
        "port": str(cfg.get("PORT") or (partes.port if partes else 5432) or 5432),
        "user": cfg.get("USER") or (partes.username if partes else ""),
        "password": cfg.get("PASSWORD") or (partes.password if partes else ""),
        "name": cfg.get("NAME") or "",
    }


class Command(BaseCommand):
    help = "Saca un respaldo de la base y verifica que se pueda restaurar."

    def add_arguments(self, parser):
        parser.add_argument("--destino", default="/respaldos", help="Carpeta donde dejar el archivo.")
        parser.add_argument(
            "--sin-verificar", action="store_true",
            help="No restaura para comprobar. Sólo para una corrida rápida a mano.",
        )
        parser.add_argument(
            "--conservar", type=int, default=14,
            help="Cuántos respaldos dejar. 0 = no borrar ninguno.",
        )

    # ------------------------------------------------------------------ #
    def handle(self, *args, **op):
        cred = _credenciales()
        if not cred["name"]:
            raise CommandError("No se pudo determinar la base de datos.")

        destino = Path(op["destino"])
        try:
            destino.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise CommandError(f"No se puede escribir en {destino}: {e}")

        self._comprobar_versiones(cred)

        sello = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        archivo = destino / f"salud-{sello}.sql.gz"

        self.stdout.write(f"Respaldando {cred['name']} → {archivo}")
        conteos = self._volcar_y_contar(cred, archivo)

        tamano = archivo.stat().st_size
        if tamano < 1024:
            # Un archivo de 20 bytes es lo que deja `pg_dump` cuando falla y
            # nadie mira el código de salida. Es el respaldo inútil por excelencia.
            raise CommandError(f"El respaldo salió de {tamano} bytes: algo falló.")
        self.stdout.write(f"  {tamano / 1_048_576:.1f} MB")

        if op["sin_verificar"]:
            self.stdout.write(self.style.WARNING(
                "\nSIN VERIFICAR. Un respaldo que nunca se restauró no es un respaldo:\n"
                "no hay forma de saber si este archivo sirve hasta que haga falta."
            ))
        else:
            self._verificar(cred, archivo, conteos)

        self._rotar(destino, op["conservar"])

        # Sólo late si VERIFICÓ. Un respaldo sin verificar no prueba nada, y
        # dejar el latido igual haría que el monitor diga «al día» sobre una
        # carpeta que quizás no tenga un solo archivo restaurable.
        if not op["sin_verificar"]:
            latir("respaldar", f"{archivo.name} · {tamano / 1_048_576:.1f} MB · verificado")

        self.stdout.write(self.style.SUCCESS(f"\nListo: {archivo}"))

    # ------------------------------------------------------------------ #
    def _comprobar_versiones(self, cred):
        """
        El cliente no puede ser de otra versión mayor que el servidor.

        Con `pg_dump` 17 contra un servidor 16, el volcado sale bien —tamaño
        razonable, código de salida cero— y **no se puede restaurar**: incluye
        parámetros que el 16 no conoce. O sea, un archivo con nombre de respaldo,
        que es la peor forma de no tener respaldo.

        Se avisa acá, con las dos versiones y qué hacer, porque el error que da
        Postgres al restaurar es «unrecognized configuration parameter
        transaction_timeout» y no lleva a nadie a la causa.
        """
        with connection.cursor() as cur:
            cur.execute("SHOW server_version")
            servidor = cur.fetchone()[0]

        r = subprocess.run(["pg_dump", "--version"], capture_output=True, text=True)
        if r.returncode != 0:
            raise CommandError(
                "No hay `pg_dump` en esta imagen. Es lo que usa este comando para "
                "sacar el respaldo."
            )

        def mayor(texto):
            for parte in texto.replace("(", " ").replace(")", " ").split():
                if parte[0].isdigit():
                    return int(parte.split(".")[0])
            return None

        cliente = mayor(r.stdout)
        srv = mayor(servidor)
        if cliente and srv and cliente != srv:
            raise CommandError(
                f"pg_dump es de la versión {cliente} y el servidor es {srv}.\n"
                "Un volcado hecho con un cliente de otra versión puede salir "
                "sin errores y NO poder restaurarse.\n"
                f"Reconstruí la imagen con:  docker compose build --build-arg PG_MAJOR={srv} backend"
            )

    def _entorno(self, cred):
        # La contraseña va por PGPASSWORD y no en la línea de comandos: `ps` la
        # muestra a cualquiera que esté en la máquina.
        return {**os.environ, "PGPASSWORD": cred["password"] or ""}

    def _volcar_y_contar(self, cred, archivo):
        """
        Vuelca y cuenta filas de TODAS las tablas en el mismo snapshot (#172, AUD-015).

        Antes se contaba la base viva después del volcado: una atención cargada
        entre medio daba «incompleto» a un respaldo válido, y dos conteos fallidos
        (None == None) daban «verificado» a uno que nadie pudo contar. Acá la
        transacción REPEATABLE READ exporta su snapshot, cuenta ahí y `pg_dump`
        vuelca exactamente ese mismo estado.
        """
        with transaction.atomic():
            with connection.cursor() as cur:
                cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                cur.execute("SELECT pg_export_snapshot()")
                snapshot = cur.fetchone()[0]
                cur.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename")
                tablas = [fila[0] for fila in cur.fetchall()]
                faltan = [t for t in TABLAS if t not in tablas]
                if faltan:
                    raise CommandError("Faltan tablas que el respaldo tiene que contener: " + ", ".join(faltan))
                self._volcar(cred, archivo, snapshot)
                # Después del volcado y en la misma transacción: el snapshot es el
                # mismo, así que lo escrito mientras tanto no entra en ninguno.
                conteos = {}
                for tabla in tablas:
                    cur.execute(f"SELECT count(*) FROM {connection.ops.quote_name(tabla)}")
                    conteos[tabla] = cur.fetchone()[0]
        return conteos

    def _volcar(self, cred, archivo, snapshot):
        orden = (
            f'pg_dump -h {cred["host"]} -p {cred["port"]} -U {cred["user"]} '
            f'-d {cred["name"]} --snapshot={snapshot} --no-owner --no-acl | gzip > "{archivo}"'
        )
        # `pipefail`: sin eso el código de salida es el de `gzip`, que comprime
        # feliz la nada que le mandó un pg_dump que falló.
        r = subprocess.run(
            ["sh", "-o", "pipefail", "-c", orden],
            env=self._entorno(cred), capture_output=True, text=True,
        )
        if r.returncode != 0:
            archivo.unlink(missing_ok=True)
            raise CommandError(f"pg_dump falló: {r.stderr.strip()[:500]}")

    # ------------------------------------------------------------------ #
    def _psql(self, cred, base, sql):
        """psql sin shell; la sentencia va por stdin para no interpolarla."""
        return subprocess.run(
            ["psql", "-h", cred["host"], "-p", cred["port"], "-U", cred["user"], "-d", base,
             "-X", "-tA", "-v", "ON_ERROR_STOP=1", "-F", "|", "-f", "-"],
            input=sql, env=self._entorno(cred), capture_output=True, text=True,
        )

    def _contar_restaurado(self, cred, base, tablas):
        """Conteos de la base restaurada; cualquier falla es error, nunca None."""
        consulta = " UNION ALL ".join(
            f"SELECT '{t}', count(*) FROM {connection.ops.quote_name(t)}" for t in tablas
        ) + ";"
        r = self._psql(cred, base, consulta)
        if r.returncode != 0:
            raise CommandError("No se pudieron contar las filas restauradas: " + r.stderr.strip()[:300])
        conteos = {}
        for linea in r.stdout.splitlines():
            if "|" in linea:
                tabla, n = linea.rsplit("|", 1)
                conteos[tabla] = int(n)
        return conteos

    def _base_verificacion(self, cred):
        """Nombre único y marca propia (#172, AUD-016): nunca se borra una base ajena."""
        ficha = secrets.token_hex(6)
        sello = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        nombre = f'{cred["name"][:30]}_verif_{sello}_{ficha}'.lower()
        return nombre, f"salud-verificacion-respaldo:{ficha}"

    def _crear_verificacion(self, cred, nombre, marca):
        creada = self._psql(cred, "postgres", f'CREATE DATABASE "{nombre}";')
        if creada.returncode != 0:
            # Si ya existe no es nuestra: no se toca.
            raise CommandError(f"No se pudo crear la base de prueba: {creada.stderr.strip()[:300]}")
        marcada = self._psql(cred, "postgres", f"COMMENT ON DATABASE \"{nombre}\" IS '{marca}';")
        if marcada.returncode != 0:
            self._borrar_verificacion(cred, nombre, marca, forzar_propia=True)
            raise CommandError(f"No se pudo marcar la base de prueba: {marcada.stderr.strip()[:300]}")

    def _borrar_verificacion(self, cred, nombre, marca, *, forzar_propia=False):
        """Borra la base de prueba solo si lleva la marca de esta corrida."""
        if not forzar_propia:
            r = self._psql(cred, "postgres",
                           f"SELECT shobj_description(oid, 'pg_database') FROM pg_database WHERE datname = '{nombre}';")
            if r.returncode != 0 or r.stdout.strip() != marca:
                self.stderr.write(f"No se borra {nombre}: no lleva la marca de esta verificación.")
                return
        borrada = self._psql(cred, "postgres", f'DROP DATABASE "{nombre}";')
        if borrada.returncode != 0:
            self.stderr.write(f"No se pudo borrar la base de prueba {nombre}: {borrada.stderr.strip()[:200]}")

    def _verificar(self, cred, archivo, conteos):
        """
        Restaura el archivo en una base descartable y compara contra el snapshot.

        Es lo único que distingue un respaldo de un archivo con nombre de
        respaldo. Los conteos de referencia son los del mismo snapshot que se
        volcó, así que una escritura posterior no invalida un respaldo válido.
        """
        prueba, marca = self._base_verificacion(cred)
        self.stdout.write(f"Verificando: restauro en {prueba}…")

        # La conexión de Django queda abierta contra la base original; no
        # interfiere con crear otra, pero sí conviene cerrarla para no arrastrar
        # una transacción larga mientras corre la restauración.
        connection.close()
        self._crear_verificacion(cred, prueba, marca)
        try:
            orden = (
                f'gunzip -c "{archivo}" | psql -h {cred["host"]} -p {cred["port"]} '
                f'-U {cred["user"]} -d {prueba} -v ON_ERROR_STOP=1 -q'
            )
            r = subprocess.run(
                ["sh", "-o", "pipefail", "-c", orden],
                env=self._entorno(cred), capture_output=True, text=True,
            )
            if r.returncode != 0:
                raise CommandError(
                    "El respaldo NO se pudo restaurar. El archivo existe y no sirve:\n"
                    + r.stderr.strip()[:800]
                )

            restaurado = self._contar_restaurado(cred, prueba, list(conteos))
            problemas = []
            for tabla in sorted(conteos):
                a, b = conteos[tabla], restaurado.get(tabla)
                if a != b:
                    problemas.append(f"{tabla}: {a} en el snapshot, {b} en el respaldo")
                if tabla in TABLAS or a != b:
                    self.stdout.write(f"  {tabla:<32} {a} → {b}  {'ok' if a == b else 'NO COINCIDE'}")
            self.stdout.write(f"  {len(conteos)} tablas comparadas.")

            if problemas:
                raise CommandError("El respaldo está incompleto:\n  " + "\n  ".join(problemas))

            self.stdout.write(self.style.SUCCESS("Restauración verificada."))
        finally:
            # La base de prueba se borra siempre, incluso si falló: dejarla
            # ocupando disco es cómo se llena el volumen que después trunca el
            # respaldo siguiente. Solo la que creó esta corrida.
            self._borrar_verificacion(cred, prueba, marca)

    # ------------------------------------------------------------------ #
    def _rotar(self, destino, conservar):
        """
        Borra los más viejos.

        Sin rotación el disco se llena, y cuando se llena `pg_dump` sigue
        escribiendo hasta donde puede: quedan archivos truncados con nombre de
        respaldo, que es peor que no tener ninguno.
        """
        if not conservar:
            return
        archivos = sorted(destino.glob("salud-*.sql.gz"))
        for viejo in archivos[:-conservar]:
            viejo.unlink(missing_ok=True)
            self.stdout.write(f"  rotado: {viejo.name}")
