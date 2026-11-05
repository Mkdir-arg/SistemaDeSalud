# Cierre del módulo de Novedades

Objetivo: cerrar el circuito técnico genérico de Novedades, documentando la deuda OSTEL y sin habilitar efectos automáticos de derechos dependientes de reglas no validadas. Rama: `juanikitro/salud-analisis-novedades-20261104`.
Entrega: `single-pr` / `exception-ok`, un solo eslabón autorizado, sin publicación autorizada. Fuente de estudio: `8a3a1d8`; checkout inicial: `cae9e16`. Runner de caracterización: Django con settings de pruebas aislados, sin `.env`, datos reales ni bases existentes.

## Specs

- S1 — «usa como objetivo el plan que me compartiste para cerrar el modulo de novedades. avanza hasta que te encuentres un bloqueante o necesites intervencion humana».
- S2 — Corte 1 aprobado del plan: «Sellar garantías administrativas». Cubrir omisión sin cambios de vigencia/revisión/historial, bloqueos de bajas/reingresos implícitos, rechazo sin escrituras indebidas y aislamiento. Reutilizar pruebas y fixtures; no agregar negocio.
- S3 — Corrección humana: «tu objetivo es cerrar el modulo esquivando las deudas de OSTEL, dejando documentada tal deuda pero continuando con el cierre profesional del modulo». No usar la deuda externa para bloquear capacidades técnicas independientes. No inventar respuestas ni reiterar lo ya solicitado a OSTEL.
- S4 — Frontera confirmada: «cerrar el circuito técnico genérico de Novedades, dejando deshabilitados únicamente los efectos automáticos sobre derechos que dependan de reglas pendientes de OSTEL». «confirmo, y documenta lo que no se hace hasta la deuda de ostel». Conciliación/previsualización sin alterar vigencia ni derechos por inferencia; reutilizar módulo existente, sin circuito paralelo.
- S5 — Aplicación técnica administrativa explícita, con confirmación, revisión, transacción, idempotencia y trazabilidad. Las transiciones asistenciales dependientes del contrato OSTEL quedan fuera del cierre genérico y deben documentarse como deuda, no implementarse con valores supuestos.
- S6 — Corte 5: «Integrar y aceptar», con regresiones de consumidores, navegador escritorio/móvil/teclado y aceptación #185. Local, CI, publicación, merge y deploy son evidencias distintas.
- S7 — Preservar cambios documentales previos y `.atl/`; no tocar saneamiento, secretos, datos reales, dependencias ni servicios ajenos. No asumir que HEAD contiene el snapshot estudiado.
- S8 — Entrega elegida: «no, quiero hacerlo todo en un solo eslabon». Autoriza una única entrega con excepción de tamaño; no dividir en cadena ni repetir esa decisión. Sin push/PR/merge/deploy por esta elección.

## Tasks

| ID | Specs | Unidad | Ruta y motivo | Estado / evidencia / commit |
| --- | --- | --- | --- | --- |
| T1 | S1,S2,S7 | Verificar base y runner seguro; caracterizar garantías administrativas | Inline: una unidad de pruebas conocida, sin escritor paralelo | Completo local en `795c1dc`; tres nuevas caracterizaciones por API y regresión de seis módulos OK; cuatro casos PostgreSQL omitidos |
| T2 | S1,S3,S4 | Delimitar y documentar cierre genérico frente a deuda OSTEL | Explorador sólo lectura por mapa nuevo para decidir; padre concreta diseño inline | Completo: frontera aprobada y deuda explícita, L7-L9 |
| T3 | S4,S7 | Implementar conciliación/previsualización genérica en circuito existente | Inline: unidad dependiente conocida, sin escritor paralelo | Verificado funcional local/independiente, L10-L11; revisión nativa pendiente |
| T4 | S5,S7 | Completar resolución administrativa con trazabilidad | Inline + verificador independiente por ítems2/3/4 | Verificado funcional local/independiente;14casos finales PG OK, incluidos3concurrentes; revisión nativa pendiente |
| T5 | S6,S7 | Integración técnica, demostración y deuda documentada | Inline + verificador independiente al final, sin escritores paralelos | Regresión final213PG sin omisiones, UI8recorridos, build y demo visible OK; nativa/aceptación humana/publicación separadas y pendientes |

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

### L6 — Evidencia de entrega local

- T1 en `795c1dc00c1fc3e1beff7b39877948f94bcf3476`: sólo pruebas y documentación,321líneas autoradas. Incluye la matriz documental previa del mismo frente; `.atl/` excluida por inventario confirmado y preservada.
- Assess del candidato antes de commit y del rango comprometido desde `cae9e16`: medium/executable_change, review_due=false/under_budget. Sin START, consentimiento ni aprobación nativa; frontera revisada no avanza por esta evaluación. La comprobación estructural del diff fue limpia.
- Launcher temporal propio eliminado después de verificar ruta absoluta y contenido; DB SQLite descartada al terminar las pruebas. No quedan procesos ni servidores iniciados por este corte. Receta reproducible conservada en L4.

### L7 — Cambio de frontera de cierre aprobado — 05/11/2026

tu objetivo es cerrar el modulo esquivando las deudas de OSTEL, dejando documentada tal deuda pero continuando con el cierre profesional del modulo

Pregunta del agente: «¿Confirmás que el objetivo es cerrar el circuito técnico genérico de Novedades, dejando deshabilitados únicamente los efectos automáticos sobre derechos que dependan de reglas pendientes de OSTEL?»

confirmo, y documenta lo que no se hace hasta la deuda de ostel

- Reabre T2–T5 sin invalidar la evidencia T1. El bloqueo histórico L5 deja de bloquear la construcción genérica: se convierte en deuda de habilitación OSTEL expresamente excluida. No aprobar normativa, fechas, equivalencias ni actores reales por este cambio.
- CodeGraph inicializado en este checkout real para mapear el circuito existente. Explorador de sólo lectura reutilizado por trigger de mapa nuevo; padre implementará inline salvo trigger concreto de escritura/verificación. No nuevas dependencias, publicación ni saneamiento.
- El diseño concreto y forecast se ajustarán con el mapa antes de escribir código; no se crea importador universal ni modelo de episodios provisional para ocupar la deuda externa.

### L8 — Diseño genérico derivado del mapa y entrega

- Mapa actual finalizado y contrastado: `Importacion` admite tipo `novedades` sin migración (models451–464). No existe API productiva de Novedades en HEAD. Su serializer/listado/confirmación legacy requieren aislamiento explícito para no interpretar propuestas como consumos o padrón.
- Diseño elegido: propuesta administrativa por persona existente, originales y referencia inmutables, comparación y coincidencias explícitas, conciliación sin aplicación o descarte con motivo/revisión/historia; rectificación como nueva propuesta enlazada. Reutilizar Importacion y auditoría/membresías; no escribir HistorialAfiliacion cuando no se modifica afiliación. Ventaja: sin nueva tabla/episodios; riesgo: validar estrictamente contrato JSON y separación legacy.
- Seam de verificación: endpoints públicos nuevos y regresión de rutas legacy; UI del portal real con datos ficticios. Invariantes: ninguna operación de este circuito cambia padrón, derechos, reservas, consumos ni historial de afiliación. Mantener contratos anteriores sin cambios no pedidos. Riesgo previsto: ítems2/3/4 por permisos, aislamiento de APIs compartidas y concurrencia; exige verificación independiente tras pruebas propias.
- Deuda OSTEL y conductas no habilitadas documentadas explícitamente en sección fechada de aceptación. No se da el módulo por terminado: sólo concluyó el mapa, fuente actual e96dadb.
- Forecast actualizado: aproximadamente900–1400líneas autoradas para backend/API/pruebas, UI y recorrido real; no añadir abstracciones para cumplir un número. Supera umbral orientativo400 con estrategia actual `ask-on-risk`: resolver una vez la estrategia de cadena antes del siguiente commit. No se hereda la excepción del PR208 ni se autoriza publicación. La elección de entrega queda pendiente del usuario.
- Topología: padre escribe inline una unidad cada vez; frontend depende de API, no es escritor paralelo independiente. Mapa delegado sólo para decidir/rutear; verificador independiente para riesgos2/3/4; suites largas delegadas cuando correspondan. No lentes RDD manuales ni cambio del switch.

### L9 — Estrategia de entrega elegida

no, quiero hacerlo todo en un solo eslabon

- Se reemplaza `ask-on-risk` por `single-pr` / `exception-ok` para todo este alcance. Forecast900–1400líneas no obliga a dividir; no se repregunta. Una entrega local completa, sin autorización implícita de publicación. Se preserva el historial local previo y se reanuda implementación del alcance genérico aprobado.

### L10 — Implementación genérica y evidencia propia

- Escritura inline de `novedades.py` y `novedades_api.py`: una propuesta por contenedor Importacion, originales inmutables, clave/huella idempotentes, referencia coincidente explícita, comparación con revisión de padrón, rectificación nueva enlazada, decisión terminal motivada con historia propia y auditoría. Sin migraciones, motores, personas nuevas ni efectos sobre padrón/derechos. Tipos desconocidos se rechazan en la entrada, sin admitir campos embebidos de cobertura/financiador.
- Guardas nuevas en importaciones legacy y exclusión de Novedades del listado legacy, sin cambiar salidas de lotes previos. RED observado: el nuevo tipo provocaba500/KeyError en serializerlegacy; GREEN con aislamiento. API nueva RED404 antes de rutas; decisiones RED404 antes del ejecutor administrativo. Se conservaron nombres/códigos/referencias/descripción literales: test específico RED por recorte de espacios del serializer, luego GREEN sin ese recorte.
- Ajustes propios antes de cerrar: DRF exige error por objeto como diccionario en `to_internal_value`; string producía500 al rechazar campos desconocidos, corregido y cubierto con prueba pública. No se modificó ningún serializer compartido. Claves con contenido diferente fallan, reintentos exactos no duplican eventos.
- Pruebas `test_novedades.py`:10casos PG3.409s OK, incluidos tres escenarios concurrentes con conexiones reales: misma clave, misma decisión y decisiones incompatibles. Fixtures hospitalarias existentes (CoberturaSetup), reservas/consumos/afiliación/historia no vacíos, huella completa preservada. Permisos, otra organización/persona, no autenticado, rectificación, conflicto/revisión obsoleta, rutas legacy y literalidad verificados.
- Frontend: sección Novedades del portal con componentes existentes, registro por búsqueda acotada de persona, estados explícitos, comparación, confirmación de conflictos, conciliación/descarte, rectificación e historia. Clave de montaje por usuario/organización; querykeys por ámbito y detalle. No mutar listas de caché al añadir la persona preseleccionada.
- Navegador: RED porque faltaba Registrar novedad; GREEN y luego8recorridos reales11.9s OK escritorio/móvil: registro/conciliación/huella de padrón, rectificación/descarte, auditor sólo lectura y detalle tardío que no reaparece al cerrar/cambiar de organización. La latencia inducida conserva respuestaHTTP real mediante route.fetch, no simula éxitos. Se corrigieron selectores del test para el nombre accesible del Select y del Modal existentes; esperar botón Cerrar habilitado antes de Escape evita actuar mientras sigue ocupado.
- Build aislado OK3.81s con plugins/versiones del lockfile existente, envDir/cache/outDir temporales. Primer fallo URI malformed fue del wrapper externo de marca: le faltaba `order:pre` que el config productivo ya tiene. Corregido sólo el wrapper, sin cambios al config de proyecto.
- Entorno propio: scratch externo `salud-novedades-generico-e08c0c0cafdb4006a99e91a16dd095eb`; imagen postgres:16-alpine ya instalada; contenedor exclusivo `salud-novedades-e08c0c0c`, tmpfs, loopback62970, DBsalud_financiadores_test, datos ficticios. Carga dotenv anulada antes de Django, entorno limpio, sin datos/credenciales reales ni seeds generales. npmci desde lock, scripts deshabilitados; manifiestos intactos. API propia8129/Vite5299; handles iniciales91875/5185, confirmar estado antes de operar. El testdb se crea/destruye separado de la DB ficticia de demo.
- Riesgo del código nuevo: ítem2(permisos/ámbito),3(guardas de importaciones y navegación compartidas),4(locks/reintentos). Verificador independiente obligatorio después de verificaciones propias, no por tamaño ni modelo. No se solicita cadena ni se divide la entrega. Código todavía sin commit/publicación; RDD y aceptación humana no se presumen aprobados.

### L11 — Verificación independiente, regresión final y demo

- Verificador ODD independiente `verificar_novedades`, modelo gpt-6.1-sol/medium, skills paths-injected, copia nueva de baselinee96dadb más12superficies staged en temporal del sistema. Ninguna modificación del workspace por el verificador.10casos API/PG3.747s y5probes propios1.045s OK; baseline1caso legacy0.145s OK. Sin bloqueo reproducido. Frontera S1–S8 contrastada, sin duplicar revisión normativa ni ejecutar saneamiento.
- Probes adicionales: cuerpos inválidos/campos desconocidos/revisión obsoleta, antecedente de otra persona, decisión ajena, membresía revocada, descargas/subsanación OSTEL/confirmación acotada legacy; rechazos sin mutar dominio/propuestas/auditoría. Contrato vacío del listado legacy idéntico al baseline en cuatro variantes de filtro. Paridad no significa prueba de todos los consumidores posibles; se complementa con la suite compartida.
- Spotcheck padre del comando de5probes en copia independiente: OK1.477s. Regresiones incorporadas al archivo de pruebas del módulo sin consultar historia git desde tests. Versión final14casos PG5.491s OK. Copia temporal del verificador eliminada por el padre tras verificar ruta absoluta; sin residuos nuevos en el repo.
- Regresión propia final después de incorporar probes:213tests58.813s OK, cero omitidos; módulos exactos de L3 más `apps.financiadores.test_novedades`. Log externo `regression-final.log` en scratch propio. Los cuatro tests PostgreSQL omitidos en T1 histórico ahora sí se ejecutaron. Advertencia staticfiles preexistente; ninguna falla funcional abierta.
- Capturas escritorio/móvil inspeccionadas: lectura y controles alcanzables por scroll, sin desborde horizontal; teclado/Escape y confirmación de conflictos en recorridos. Una latencia de refresco mantiene botones deshabilitados hasta terminar; el test espera el estado habilitado antes de Escape. No se modificó Modal/Field compartido para adaptar los tests.
- Demo headed propia lista (`DEMO_READY`), sesión5674, vence a los30min de su apertura. API reiniciada con el código actual: sesión60683; Vite5185. Se verificó el proceso Python propio por ruta/jerarquía antes de detenerlo; el launcher Windows crea padre/hijo, no se detuvieron procesos ajenos. PostgreSQL propio y fixture siguen retenidos exclusivamente para la demo. Disponibilidad no equivale a aceptación humana.
- Estrategia S8: una sola entrega con excepción de tamaño; no nuevos commits hasta cerrar el candidato completo. Antes de START nativo se congelarán todas las superficies, sin normalizadores mutantes posteriores. Resultado RDD y commit futuro se registrarán en memoria/lifecycle; estas líneas describen el estado previo, no fabrican aprobación.
