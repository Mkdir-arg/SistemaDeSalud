# Issue #42: auditoría por lotes

## Problema y plan

La actividad del financiador escribía una evidencia por persona, hospital y bloque
de hasta diez reservas mediante INSERT individuales. Una exportación de 5.000
personas ejecutaba 5.001 INSERT contando el evento final. Se necesita reducir esos
viajes a la base sin perder evidencia ni entregar datos si falla la auditoría.

Plan aplicado al PR #41, tomando como referencia anterior el commit
`abe8e4520558e158e0c5ee708d82a5b9cc12e1ec`:

1. Medir preparación/evaluación del queryset, serialización y auditoría por separado.
2. Compartir la normalización central y escribir lotes de hasta 500 evidencias.
3. Preservar los bloques de diez IDs, la institución original y la transacción
   exterior que incluye el evento final antes de entregar el resultado.
4. Verificar fallos de lotes/preparación/evento, permisos, historia y tolerancia clínica.
5. Comparar cinco ejecuciones por tamaño sobre las mismas fuentes e infraestructura.

No agrega colas, caché, streaming, dependencias, modelos ni migraciones. Conserva
CSV/JSON, filtros, orden, columnas, importes, encabezados privados y límite de filas.

## Implementación y contratos

- `apps.auditoria.mixins._datos_acceso` centraliza usuario, ciudadano, institución,
  tipo, recurso, objeto, detalle, resultados e IP. `registrar_acceso` mantiene
  su firma, precedencia de institución y tolerancia clínica anteriores.
- `registrar_accesos(request, tipo, recurso, accesos, estricto=False)` consume
  el iterable por lotes de hasta 500. Preparación y escritura están dentro de
  una transacción: una excepción revierte todos los lotes, incluso en modo tolerante.
- `auditar_actividad` llama **siempre con `estricto=True`**. Conserva la persona del
  hecho original o del caso si aún no hay hecho, y todos los IDs en bloques de diez.
  El registrador masivo da prioridad a la institución histórica explícita; no la
  sustituye por la actual del ciudadano si éste fue reasignado posteriormente.
- CSV y JSON conservan su transacción exterior con el evento final. Completar
  un lote o liberar el savepoint interior no confirma la descarga. Si falla el
  evento, se revierten también todos los accesos personales.
- `AccesoClinico` no redefine `save()` ni tiene señales asociadas en el repositorio.
  `auto_now_add` también se aplica con `bulk_create`. Futuros hooks deberán cubrir
  expresamente este camino masivo.
- Django puede subdividir el lote si el motor limita parámetros. En PostgreSQL,
  5.000 personas generan diez INSERT de accesos y uno del evento final.
- Revertir el código conserva todas las auditorías guardadas. No transforma
  afiliaciones, cupos, obligaciones, movimientos ni ajustes.

La integración reutiliza el commit `0a0096e` del trabajo concurrente y concilia
las pruebas adicionales y la medición por fases. No publica los otros incrementos
locales ni modifica el checkout compartido. La firma del registrador y la regla
histórica son las de ese commit; no quedan dos implementaciones paralelas.

## Medición final

Ejecutado el 16/09/2026: Django 5.2.15, psycopg 3.3.5 y PostgreSQL 16 local en puerto
55438. Antes y después se ejecutó sólo el método de medición en una base recién
creada, con las mismas 5.001 fuentes ficticias y filtros de fecha para obtener
100, 1.000 y 5.000 personas. Cada tamaño tiene cinco solicitudes. Cada repetición
revierte su auditoría sintética fuera del cronómetro, sin acumularla entre muestras.

Dispersión: desviación estándar poblacional y rango observado. Los INSERT incluyen
el evento final; la cantidad fue idéntica en las cinco solicitudes de cada tamaño.

| Personas | Versión | Mediana total (s) | Desvío (s) | Mínimo–máximo (s) | INSERT |
| ---: | --- | ---: | ---: | --- | ---: |
| 100 | Antes | 0,4369 | 0,0588 | 0,3989–0,5641 | 101 |
| 100 | Después | 0,2358 | 0,0604 | 0,2032–0,3689 | 2 |
| 1000 | Antes | 2,0938 | 0,4121 | 1,9428–3,0862 | 1001 |
| 1000 | Después | 0,6479 | 0,0648 | 0,5558–0,7382 | 3 |
| 5000 | Antes | 10,9474 | 0,5483 | 10,0822–11,5511 | 5001 |
| 5000 | Después | 2,6427 | 0,1590 | 2,3005–2,7265 | 11 |

Medianas por fase, en segundos:

| Personas | Versión | Consulta | CSV | Accesos personales | Evento |
| ---: | --- | ---: | ---: | ---: | ---: |
| 100 | Antes | 0,2597 | 0,0029 | 0,1415 | 0,0012 |
| 100 | Después | 0,2091 | 0,0031 | 0,0105 | 0,0014 |
| 1000 | Antes | 0,5057 | 0,0264 | 1,5506 | 0,0018 |
| 1000 | Después | 0,4030 | 0,0184 | 0,1945 | 0,0013 |
| 5000 | Antes | 2,4565 | 0,1150 | 8,4251 | 0,0015 |
| 5000 | Después | 1,9986 | 0,0876 | 0,4874 | 0,0013 |

Para 5.000 personas, la mediana total pasó de 10,9474 a 2,6427 s (75,9 % menos) y la
mediana de auditoría personal de 8,4251 a 0,4874 s. Las sentencias totales bajaron
de 5.008 a 20: cinco SELECT, once INSERT y cuatro instrucciones de savepoint/liberación.
Los resultados anteriores de la rama candidata se sustituyen por esta medición
realizada sobre el código final conciliado.

Consulta mide preparación/evaluación; CSV incluye filas, celdas, escritura del
archivo en memoria y apertura de la transacción exterior. Accesos y evento se
miden aparte. El total también incluye permisos, middleware y respuesta. Las
fases no explican exhaustivamente el total. No se imprime SQL ni datos personales.

Es un ensayo de APIClient/TestCase: no mide red HTTP, navegador, commit externo
definitivo ni carga concurrente. La máquina y el servidor son compartidos;
los tiempos varían. No se incorporan umbrales temporales en CI ni se promete un SLA.

## Validación de la integración

- **156/156 pruebas PostgreSQL, 27,433 s**, sin omisiones: auditoría, actividad y
  vigencias. Incluye la normalización, institución original, fecha, frontera
  500/501, iterable fallido, lotes primero/intermedio/último, evento final y
  compatibilidad de lecturas clínicas.
- **1/1 benchmark PostgreSQL, 30,110 s**: cinco muestras por tamaño; cifras arriba.
- **2/2 PostgreSQL, 28,997 s**: exportaciones de 5.000/5.001 filas y repetición del
  fallo SQL de lotes CSV/JSON, incluyendo la aserción final de no entregar tipo CSV.
  Los 5.000 accesos completos y los once INSERT se comprobaron en esta versión.
- `python manage.py check --settings=config.settings_financiadores_test` y
  `git diff --check`: correctos.

| Criterio | Evidencia |
| --- | --- |
| CSV/JSON y alcance sin cambios | Regresiones de `test_actividad` y `test_vigencias`; consultas, serialización y permisos productivos sin cambios. |
| 5.000 accesos completos y evento | Ensayo de volumen: persona, hospital, usuario, recurso, tipo, objeto, detalle, resultados, IP y fecha de cada evidencia. |
| Más de diez reservas | Test de 25 IDs largos: tres bloques completos; prueba de reasignación posterior del ciudadano conserva hospital del hecho. |
| Fallos de escritura y evento | Fallos SQL en lotes 1/2/3 para CSV y JSON, y fallo del evento después de tres lotes escritos: rollback y respuesta sin datos. |
| Límite y aislamiento | 5.001 filas devuelve 400 sin archivo parcial ni nueva auditoría; membresía revocada y financiador ajeno sin ampliar alcance. |
| Conservación de dinero | Cuentas, movimientos y ajustes conservados; nueve importes hospitalarios y asignación original verificados. |
| Reversión | Sin migraciones ni backfill; restablecer el registrador anterior conserva auditorías existentes. |

No se repitieron frontend/build ni la suite global: no cambia interfaz ni esquema.
Las pruebas no sustituyen la aceptación funcional ni la validación del entorno
productivo. Revisión estática de integración sin hallazgos bloqueantes; el segundo
revisor no ejecutó pruebas ni verificó tiempos de manera independiente.

## Reproducción y aislamiento

Se usó el Python existente en `%TEMP%/cauce-financiadores-venv` y exclusivamente
la base efímera `test_cauce_issue42_aislado`; el runner la creó y destruyó. No se
alteraron la demo, datos reales o configuraciones compartidas.

Desde `backend`, configurar `SALUD_TEST_POSTGRES_URL` para el PostgreSQL local
con base `salud_financiadores_test`, conforme al settings dedicado existente:

```powershell
python manage.py test apps.auditoria apps.financiadores.test_actividad apps.financiadores.test_vigencias --settings=config.settings_financiadores_postgres_test --noinput
python manage.py test apps.financiadores.validacion_volumen.ExportacionVolumenTests.test_medicion_auditoria_por_fases --settings=config.settings_financiadores_postgres_test --noinput
python manage.py test apps.financiadores.validacion_volumen.ExportacionVolumenTests.test_exportaciones_completas_y_rechazo_de_exceso apps.financiadores.test_actividad.ActividadReporteTests.test_fallo_en_cualquier_lote_revierte_auditoria_y_no_entrega_datos --settings=config.settings_financiadores_postgres_test --noinput
```

Para reproducir el nombre aislado utilizado, sin editar settings versionados:

```powershell
$env:DJANGO_SETTINGS_MODULE = 'config.settings_financiadores_postgres_test'
python -c "import sys; from django.conf import settings; settings.DATABASES['default']['TEST']['NAME']='test_cauce_issue42_aislado'; from django.core.management import execute_from_command_line; execute_from_command_line(['manage.py', 'test', *sys.argv[1:], '--noinput'])" apps.financiadores.validacion_volumen.ExportacionVolumenTests.test_medicion_auditoria_por_fases
```

Para medir el antes, incorporar sólo la instrumentación de ese método al commit
base y ejecutarlo aisladamente. Ejecutar primero el otro ensayo cambia condiciones
iniciales y no equivale al benchmark aislado. No comparar sus tiempos como si lo fuera.

Logs locales: `%TEMP%/cauce-issue42-antes.log`, `cauce-issue42-integracion-focales.log`,
`cauce-issue42-integracion-medicion.log` y `cauce-issue42-integracion-volumen.log`.
No son pruebas de CI remoto. Skills: `brainstorming` acotó el diseño al issue;
`systematic-debugging` organizó la medición y los fallos; `code-review` contrastó
contratos y mantenibilidad, también al conciliar la integración.
