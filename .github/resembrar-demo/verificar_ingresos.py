"""Prueba el ingreso de cada cuenta de la demo con DEMO_PASSWORD y escribe el resumen.

    python verificar_ingresos.py cuentas.json

`cuentas.json` es lo que imprime `cuentas.py` en el contenedor. 200 es OK; lo
demás se lista como fallido. Sale con 1 si alguna falla.

El ingreso institucional limita los fallos (10 por email y 100 por IP cada
15 minutos) y el del portal todos los intentos (30 por IP por hora): se prueba
cada cuenta una sola vez, con una pausa entre pedidos.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

API = os.environ.get("DEMO_API", "https://cauce-api-production.up.railway.app")
RUTAS = {"institucionales": "/api/auth/token/", "portal": "/api/mi/cuenta/ingresar/"}


def ingresar(ruta, email, clave):
    pedido = urllib.request.Request(API + ruta, json.dumps({"email": email, "password": clave}).encode(),
                                    {"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(pedido, timeout=30) as respuesta:
            return respuesta.status
    except urllib.error.HTTPError as error:
        return error.code
    except urllib.error.URLError as error:
        return f"sin respuesta ({error.reason})"


def main():
    clave = os.environ["DEMO_PASSWORD"]
    with open(sys.argv[1], encoding="utf-8") as archivo:
        cuentas = json.load(archivo)

    fallidas, total = [], 0
    for tipo, ruta in RUTAS.items():
        for email in cuentas[tipo]:
            total += 1
            codigo = ingresar(ruta, email, clave)
            if codigo != 200:
                fallidas.append((tipo, email, codigo))
            time.sleep(0.3)

    lineas = [f"### Ingresos con DEMO_PASSWORD: {total - len(fallidas)} de {total} OK",
              f"{len(cuentas['institucionales'])} institucionales y {len(cuentas['portal'])} del portal del paciente."]
    if fallidas:
        lineas += ["", "| Tipo | Cuenta | Respuesta |", "|---|---|---|"]
        lineas += [f"| {tipo} | {email} | {codigo} |" for tipo, email, codigo in fallidas]
    texto = "\n".join(lineas) + "\n"
    print(texto)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as resumen:
            resumen.write(texto)
    if total == 0:
        print("::error::La base no tiene cuentas para probar.")
        return 1
    return 1 if fallidas else 0


if __name__ == "__main__":
    sys.exit(main())
