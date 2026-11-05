# Cierre del módulo de Novedades

Objetivo: completar el plan aprobado hasta un bloqueo verificable o decisión humana. Rama: `juanikitro/salud-analisis-novedades-20261104`.
Entrega: `ask-on-risk`, sin publicación autorizada. Fuente de estudio: `8a3a1d8`; checkout inicial: `cae9e16`. Runner de caracterización: Django con settings de pruebas aislados, sin `.env`, datos reales ni bases existentes.

## Specs

- S1 — «usa como objetivo el plan que me compartiste para cerrar el modulo de novedades. avanza hasta que te encuentres un bloqueante o necesites intervencion humana».
- S2 — Corte 1 aprobado del plan: «Sellar garantías administrativas». Cubrir omisión sin cambios de vigencia/revisión/historial, bloqueos de bajas/reingresos implícitos, rechazo sin escrituras indebidas y aislamiento. Reutilizar pruebas y fixtures; no agregar negocio.
- S3 — Corte 2: «Cerrar el contrato de novedades». Requiere definir acontecimiento, episodio, duplicado/rectificación, precedencia, fecha efectiva, efectos, evidencia y autoridad; no inventar respuestas ni reiterar lo ya solicitado a OSTEL.
- S4 — Corte 3: «Construir conciliación y previsualización», condicionado al contrato; preview sin modificar vigencia ni derechos.
- S5 — Corte 4: «Aplicar una transición aprobada», con confirmación, revisión, transacción, idempotencia y trazabilidad; ninguna transición sin contrato.
- S6 — Corte 5: «Integrar y aceptar», con regresiones de consumidores, navegador escritorio/móvil/teclado y aceptación #185. Local, CI, publicación, merge y deploy son evidencias distintas.
- S7 — Preservar cambios documentales previos y `.atl/`; no tocar saneamiento, secretos, datos reales, dependencias ni servicios ajenos. No asumir que HEAD contiene el snapshot estudiado.

## Tasks

| ID | Specs | Unidad | Ruta y motivo | Estado / evidencia / commit |
| --- | --- | --- | --- | --- |
| T1 | S1,S2,S7 | Verificar base y runner seguro; caracterizar garantías administrativas | Inline: una unidad de pruebas conocida, sin escritor paralelo | Completo local; tres nuevas caracterizaciones por API y regresión de seis módulos OK; cuatro casos PostgreSQL omitidos. Commit pendiente de registrar |
| T2 | S1,S3 | Reconciliar contrato externo y decisión mínima | Inline: contraste de requisitos | Bloqueado por contrato validado ausente; cuerpo/comentarios #143/#183 revalidados05/11; no reiterar pedido OSTEL |
| T3 | S4,S7 | Diseñar/implementar conciliación no operativa | Inline salvo trigger concreto posterior | No iniciada; depende T2 |
| T4 | S5,S7 | Aplicar transiciones aprobadas | Inline + verificación independiente por ítems 1/2/4 | No iniciada; depende T2/T3 |
| T5 | S6,S7 | Integración y aceptación | Inline; delegar suites largas si corresponde | No iniciada; depende T4 y aceptación humana |

## Log

### L1 — Objetivo aprobado — 05/11/2026

usa como objetivo el plan que me compartiste para cerrar el modulo de novedades. avanza hasta que te encuentres un bloqueante o necesites intervencion humana

### L2 — Estado inicial y límites

- HEAD `cae9e16`, rama propia, matriz documental de Novedades modificada previamente y `.atl/` sin seguimiento; se preservan. Sin checkout/reset/merge ni cambio de base.
- `ostel_importacion.py`, `test_ostel_importacion.py` y `vigencias.py` coinciden con snapshot8a3a1d8; `padron.py` y `models.py` no. La nueva evidencia sólo acreditará el checkout real, no integración del snapshot completo.
- Python3.14.6 y Django5.2.15 disponibles. Settings de pruebas SQLite en memoria existe, pero importa settings base que carga `.env`: el launcher externo deberá impedir esa lectura antes de importar Django y limpiar el entorno; no se usan credenciales existentes.
- Primera opción de ejecución: SQLite en memoria con datos exclusivamente ficticios. Si no soporta el esquema real, no desactivar migraciones ni falsificar backend: detener esa ejecución y pedir el entorno PostgreSQL aislado si requiere consentimiento adicional.
- Caracterización de conducta existente: GREEN inicial es válido; no fabricar RED ni introducir lógica productiva. Riesgo del corte de pruebas: none. Pronóstico inicial: menos de400líneas; sin decisión de cadena necesaria por ahora.

### L3 — Caracterización y resultado observado

- Baseline del módulo sin modificar:26tests OK2.178s. Tres nuevas pruebas por API: omisión con corrección real de otra persona, bajas/reingreso bloqueados y revisión desactualizada. Padrón/historial de A/B y lotes de B no vacíos; mismas identidades en ambos financiadores. Comparación de todas las columnas, sin normalizar vigencia ni revisión. Reintento válido compara también el padrón/historia completos después de aplicar.
- Prueba focal: tres casos OK0.960s antes de reforzar la aserción final de reintento; versión final incluida en la regresión siguiente. Los primeros fallos eran expectativas del test: `_persona` retorna tupla; subsanar reingreso devuelve200 con fila en revisión, no400. Se comprobó `subsanar`/`_revisar` antes de corregir esas expectativas. No son RED de un fallo productivo ni justifican cambiar negocio.
- Regresión final de seis módulos:199tests24.404s, OK con4omitidos. Omitidos por SQLite: `ImportacionesConcurrenciaTests` y `CoberturaConcurrenciaTests`, cuyas guardas exigen PostgreSQL. No se acredita concurrencia ni locks reales; no se modifican esos comportamientos. Advertencia preexistente: directorio staticfiles ausente. Logs negativos400/403 y errores inducidos esperados no fueron fallos de la suite.
- Orden de módulos: `apps.financiadores.test_ostel_importacion apps.financiadores.test_importaciones apps.financiadores.test_padron130 apps.financiadores.test_vigencias apps.financiadores.test_cobertura apps.financiadores.test_habilitacion_cobertura`.
- Comando observado desde raíz: `python -I -B <scratch>/run.py <repo>/backend <módulos anteriores>`. Launcher propio temporal externo; SQLite en memoria, migraciones reales, sin Docker/servidores/.env/datos reales. No build/navegador: sólo pruebas de API, sin UI cambiada. Diferencial de comportamiento productivo no aplica: ningún servicio, endpoint o helper productivo fue modificado.
- Superficies de rollback: tres pruebas y dos helpers añadidos a `test_ostel_importacion.py`, sección fechada05/11 en aceptación y este seguimiento. La matriz documental previa04/11 se conserva como antecedente de la misma unidad temática. No tocar `.atl/` ni saneamiento.

### L4 — Reproducir el aislamiento sin guardar configuración ni secretos

Crear `run.py` fuera del worktree en un directorio temporal propio. Ejecutarlo con
`python -I -B <scratch>/run.py <ruta-backend> <módulos>`. Contenido del launcher:

```python
import os
import sys
from pathlib import Path

backend = Path(sys.argv[1]).resolve()
allowed = {key: os.environ[key] for key in ('SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'PATH') if key in os.environ}
os.environ.clear()
os.environ.update(allowed)
os.environ.update(DJANGO_SETTINGS_MODULE='config.settings_financiadores_test', ENTORNO='desarrollo', DJANGO_DEBUG='true', DJANGO_SECRET_KEY='synthetic-novedades-test-only', PYTHONDONTWRITEBYTECODE='1')
sys.path.insert(0, str(backend))
import dotenv
dotenv.load_dotenv = lambda *args, **kwargs: False
import socket
def no_network(*args, **kwargs):
    raise RuntimeError('Network disabled for isolated SQLite characterization')
socket.socket.connect = no_network
import django
django.setup()
from django.conf import settings
assert settings.DATABASES['default']['ENGINE'] == 'django.db.backends.sqlite3'
assert settings.DATABASES['default']['NAME'] == ':memory:'
from django.core.management import call_command
call_command('test', *(sys.argv[2:] or ['apps.financiadores.test_ostel_importacion']), verbosity=1, interactive=False)
```

### L5 — Bloqueo material y continuidad

- Consulta GitHub05/11: #143 sin comentarios; #183 tiene un comentario que exige decisiones verificadas de fechas, motivos y precedencia antes de aplicar bajas/reingresos, y permite sólo planificación/pruebas independientes mientras faltan. No aparece contrato validado nuevo.
- Falta para T2 una definición aprobada de evento/episodio y sus efectos: fuente/identificador, duplicado frente a rectificación, precedencia, fecha efectiva, acción permitida y autoridad/corrección. No se inventa normativa ni se reitera la solicitud OSTEL. T3–T5 no pueden comenzar con ese vacío.
- Primer turno del objetivo con este bloqueo: objetivo activo, no completo ni marcado bloqueado aún. Sin publicación/PR/CI/merge/deploy ni aceptación humana. No hay fallo productivo pendiente de corregir del corte T1. Risk: none.
