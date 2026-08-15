"""
Cuánto le falta a la corrida de equipos por módulo.

    python avance.py

Lee el journal del workflow y el transcript de cada agente. No hace suposiciones
sobre el total: lo calcula de lo que el script realmente lanza —30 auditores
(3 por módulo), 1 verificador por módulo con hallazgos, y 1 corrector por dominio
de archivos con hallazgos confirmados—.

El porcentaje pondera las etapas por lo que tardan de verdad, no por cantidad de
agentes: la auditoría es el 60% del tiempo aunque después haya menos agentes.
"""
import json
import sys
from pathlib import Path

# La consola de Windows viene en cp1252 y no sabe escribir ni el bloque de la
# barra ni las tildes: revienta con UnicodeEncodeError antes de mostrar nada.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

RUN = "wf_3da0e3f2-97e"
BASE = Path.home() / ".claude/projects/c--Users-mkdir-Proyectos-salud"
CARPETA = next(BASE.glob(f"*/subagents/workflows/{RUN}"), None)

MODULOS = 10
AUDITORES = MODULOS * 3
# Peso de cada etapa en el tiempo total, medido de la primera corrida.
PESO = {"auditoria": 0.60, "verificacion": 0.20, "correccion": 0.20}


def rol_de(texto: str) -> str:
    if "Tu trabajo es REFUTAR" in texto or "SOS EL VERIFICADOR" in texto:
        return "verificacion"
    if "SOS EL DESARROLLADOR" in texto:
        return "correccion"
    return "auditoria"


def main():
    if CARPETA is None or not CARPETA.exists():
        print("No encuentro la carpeta del run. ¿Arrancó el workflow?")
        return 1

    # Lo entregado sale del journal: una línea por agente que terminó.
    entregados = {"auditoria": 0, "verificacion": 0, "correccion": 0}
    hallazgos = confirmados = refutados = 0
    arreglados = omitidos = 0

    journal = CARPETA / "journal.jsonl"
    if journal.exists():
        for linea in journal.read_text(encoding="utf-8").splitlines():
            try:
                e = json.loads(linea)
            except ValueError:
                continue
            r = e.get("result")
            if not isinstance(r, dict):
                continue
            if "hallazgos" in r:
                entregados["auditoria"] += 1
                hallazgos += len(r["hallazgos"])
            elif "veredictos" in r:
                entregados["verificacion"] += 1
                for v in r["veredictos"]:
                    if v.get("real"):
                        confirmados += 1
                    else:
                        refutados += 1
            elif "aplicados" in r:
                entregados["correccion"] += 1
                arreglados += len(r.get("aplicados") or [])
                omitidos += len(r.get("omitidos") or [])

    # Cuántos agentes corren AHORA no se puede saber desde acá, y probé dos
    # formas que mentían:
    #
    #   - por mtime del archivo: al retomar, el runtime toca los 254 transcripts
    #     para rearmar la caché → «185 verificadores corriendo», todos cadáveres
    #     de la corrida que murió por el límite de la cuenta;
    #   - por la hora de la última línea: cuando el proceso muere, el runtime le
    #     escribe una línea final a cada transcript en vuelo → «79 corriendo»,
    #     los mismos muertos con hora fresca.
    #
    # Un número inventado es peor que ninguno: se usa para decidir si esperar o
    # relanzar. Se informa lo único comprobable —hace cuánto que algo escribió—,
    # que es lo que contesta «¿sigue vivo o se colgó?».
    from datetime import datetime, timezone

    ahora = datetime.now(timezone.utc)
    ultima_actividad = None
    for f in CARPETA.glob("agent-*.jsonl"):
        try:
            lineas = [l for l in f.read_text(encoding="utf-8", errors="ignore").splitlines() if l.strip()]
            sello = json.loads(lineas[-1]).get("timestamp", "")
            t = datetime.fromisoformat(sello.replace("Z", "+00:00"))
        except (OSError, ValueError, IndexError, AttributeError):
            continue
        if ultima_actividad is None or t > ultima_actividad:
            ultima_actividad = t

    # Totales esperados. Los de verificación y corrección sólo se conocen cuando
    # la etapa anterior terminó; hasta entonces se estiman y se dice que es una
    # estimación, en vez de inventar un número que después baja.
    total = {"auditoria": AUDITORES, "verificacion": MODULOS, "correccion": MODULOS + 1}
    estimado = entregados["auditoria"] < AUDITORES

    print(f"\n  Corrida {RUN}\n")
    filas = [
        ("Auditoría", "auditoria", "analistas"),
        ("Verificación", "verificacion", "verificadores"),
        ("Corrección", "correccion", "correctores"),
    ]
    pct_total = 0.0
    for etiqueta, clave, unidad in filas:
        hechos, tope = entregados[clave], total[clave]
        pct = min(1.0, hechos / tope) if tope else 0.0
        pct_total += pct * PESO[clave]
        barra = "█" * int(pct * 24) + "·" * (24 - int(pct * 24))
        print(f"  {etiqueta:<14} {barra} {hechos:>3}/{tope:<3} {unidad}")

    print(f"\n  AVANCE TOTAL   {int(pct_total * 100)}%{'  (los totales de las 2 últimas etapas son estimados)' if estimado else ''}")

    if ultima_actividad is not None:
        seg = int((ahora - ultima_actividad).total_seconds())
        cuanto = f"{seg} s" if seg < 120 else f"{seg // 60} min"
        salud = "corriendo" if seg < 300 else "SIN ACTIVIDAD — puede estar cortado"
        print(f"  última escritura de un agente hace {cuanto} · {salud}")

    print(f"\n  hallazgos crudos     {hallazgos}")
    if confirmados or refutados:
        print(f"  verificados          {confirmados} confirmados · {refutados} refutados")
    if arreglados or omitidos:
        print(f"  correcciones         {arreglados} aplicadas · {omitidos} omitidas")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
