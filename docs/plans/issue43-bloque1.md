# Issue #43: CI y circuito financiero real (bloque 1)

## Alcance aprobado el 21/10/2026

Entregar el bloque 1 completo mediante PR draft independiente. #43 permanece
abierto y en progreso: los bloques 2 y 3 no forman parte de esta entrega.
Se autorizó PostgreSQL 16 descartable exclusivo, instalación de dependencias
declaradas/Chromium si hiciera falta, servicios locales, migraciones y preparación
ficticia sólo en ese destino, suites focales y completa, build y checks.
También se autorizó la ejecución automática de CI al publicar el draft;
no se ejecutan dispatch manual, merge ni despliegue.

Se preservan los contratos de PR #41, incorporado por
`0c155517680a7e83bbaa390ad093eb084da0ef4c`. No se rehace el circuito.

## Dónde está trabajado

- `.github/workflows/issue43.yml`: navegador, backend y PostgreSQL 16 reales en CI.
- `docker-compose.issue43.yml`: PostgreSQL descartable exclusivo local.
- `backend/config/settings_issue43_test.py`: destino fijo y bloqueo de `.env`.
- `backend/tests/issue43/ejecutar.py`: comandos reproducibles.
- `backend/tests/issue43/escenario.py`: preparación ficticia y lectura ORM.
- `backend/tests/issue43/test_circuito.py`: integración de observación hasta cobro.
- `frontend/playwright.issue43-real.config.js` y
  `frontend/e2e/issue43-finanzas-real.spec.js`: acciones de usuario sobre API real.

Se reutilizan `backend.yml` (suite PostgreSQL y migraciones), `calidad.yml`
(OpenAPI y build), los escenarios `EsperaSetup`/`CoberturaSetup` y las suites
existentes. Las pruebas con API interceptada siguen siendo complementarias.
El CI real del portal del paciente usa SQLite y no acredita este circuito.

## Contratos y criterios observables

| Criterio | Evidencia automatizada prevista |
| --- | --- |
| Solicitar, observar, reenviar y aprobar | E2E principal: cada acción por navegador; estados leídos de PostgreSQL |
| Rechazar | Segundo E2E: conserva paso, cero atención, deuda y movimientos |
| Aprobar no realiza ni cobra | E2E antes/después: mismo nodo, cero hechos, cuentas y movimientos |
| Reserva y aceptación por prestación/importe | E2E: aceptación explícita, reserva antes de realizar; suites clínica/esperas para negativos y cambio de importe |
| Realización, cargo y cobro | E2E: un hecho, uso consumido, cuentas 80/20; cobro 80 aprobado, saldo financiador 0 y paciente 20 |
| Persistencia | Lecturas ORM en procesos separados; recargas de pantalla después de decisiones y cobro |
| Reintentos y concurrencia | `test_circuito`, `test_autorizaciones`, `test_uso_autorizaciones`, `test_concurrencia_clinica`, `test_dinero` |
| Hospital/financiador/resolutor explícito | Suites existentes de autorizaciones y piloto; actores E2E con membresía real y concesiones explícitas |
| Urgencia, supervisión y vencimiento | `test_esperas`, incluidas carreras reloj/aprobación y doble reloj |
| Aprobación tardía | `test_uso_autorizaciones`: conserva hecho, copago y resolución explícita; no duplica cargos |
| Migraciones/OpenAPI/build | Checks existentes y ejecución local separada |

El setup puede crear datos ficticios directamente, pero las transiciones del
recorrido se ejecutan mediante la interfaz. No se usa `page.route`, respuestas
inventadas ni `force_authenticate` como evidencia del recorrido de navegador.
Los tests Django complementarios sí usan su cliente habitual de integración.

Los nuevos escenarios no conceden acceso implícito a plataforma ni cambian su
contrato. #170 conserva la propiedad de la lógica de permisos y sus documentos.
Un fallo productivo se informa para resolverlo con su propietario: no se cambia
la prueba para aceptar el bug. Revalidar integración cuando se incorpore #170.

## Ejecución reproducible y aislamiento

Requiere Docker, Python con `backend/requirements.txt`, Node con `npm ci` desde
`frontend` y Chromium (`npx playwright install chromium`). No se agregan dependencias.
Comprobar primero que los puertos 55443, 8143 y 5243 están disponibles.

Desde la raíz:

```text
docker compose -f docker-compose.issue43.yml up -d --wait
```

Desde `backend`:

```text
python tests/issue43/ejecutar.py checks
python tests/issue43/ejecutar.py suites
python tests/issue43/ejecutar.py completa
python tests/issue43/ejecutar.py preparar ../issue43-metadata.json
```

Desde `frontend`:

```text
npx playwright test -c playwright.issue43-real.config.js
npm run build
```

El runner fija el settings dedicado, no lee `.env` y no admite URLs externas.
PostgreSQL escucha sólo en loopback local; autenticación trust únicamente para
el contenedor ficticio descartable. No usar este compose en un host compartido
con usuarios no confiables ni combinarlo con el compose operativo.
No hay volumen persistente: sus datos viven en tmpfs. Bases propias
`salud_issue43` y `test_salud_issue43`; nunca compartirlas con otro agente.
La preparación falla si ya existen usuarios y no borra datos para poder pasar.
Los E2E modifican su escenario; para repetir desde cero, finalizar todas las
pruebas de #43 y recrear exclusivamente este contenedor:

```text
docker compose -f docker-compose.issue43.yml down
docker compose -f docker-compose.issue43.yml up -d --wait
```

Después repetir preparación y E2E. La suite Django usa otra base y su limpieza
es la del test runner; no ejecutar dos suites Django simultáneas sobre ella.
No usar flush, seeds globales, restore ni migraciones contra localhost:8090,
la demo, el destino real o bases de #170. Las trazas y vídeos están apagados
para evitar capturar sesiones; las capturas de fallo contienen sólo ficticios.

## Evidencia de esta entrega

Base de publicación: `9ddce1445c9794f6e842293c3c5d0a56bbc30001` (`origin/main`
consultado el 21/10/2026). Checkout compartido observado:
`25849b7332f927b2db3399f873516ba6aff37469`, rama
`feat/ostel-prevalidacion-escenarios`, con cambios ajenos concurrentes.
La validación se realiza sobre un archivo de Git de la base más exclusivamente
los archivos de #43, extraído a un directorio temporal sin metadatos Git.
No es otro worktree. Así los cambios concurrentes no alteran el estado probado.
La publicación usa un índice temporal y no modifica el índice ni la rama activos.

Evidencia local sobre esa copia aislada (Windows, Python 3.14, Django 5.2.15,
psycopg 3.3.5, Node 24.13.0, PostgreSQL 16.15):

| Comando | Resultado |
| --- | --- |
| `python tests/issue43/ejecutar.py suites` | 141 pruebas, OK, 41,583 s; sin omisiones |
| `python tests/issue43/ejecutar.py checks` | Django sin problemas, sin migraciones nuevas y OpenAPI sin avisos |
| `npx playwright test -c playwright.issue43-real.config.js` | 2/2, OK, 39,0 s en la repetición final, backend/PG reales; incluye aceptación exacta y reserva sin cargos |
| `npm run build` | OK, 5,40 s |
| Guardas negativas del settings | Marcador inválido y ENTORNO=produccion rechazados antes de conectar |
| Repetir preparación sobre escenario existente | Rechazado; metadata intacta, sin sobrescribir escenario |
| `collectstatic --noinput` + `apps.accounts.test_admin_cuentas_auditoria172` | Estáticos OK; 10/10 pruebas del admin OK tras corregir la preparación |

Los intentos iniciales de E2E fallaron por selectores escritos incorrectamente
en el test (Revisar, Decisión y Ver cuenta). Se corrigieron sin cambios de
producto y se repitió la tanda completa. No se presentan como éxitos.
El workflow usa Python 3.12/Node 20: sus resultados remotos son independientes
de esta evidencia local. La primera suite completa local se interrumpió:
faltaba `collectstatic`, preparación requerida por `backend.yml`, y ya había
errores de manifiesto ausente de `admin/css/base.css`. No es una suite aprobada.
El runner `completa` ahora prepara estáticos antes de ejecutar pruebas. La suite
completa remota ya incluye ese paso oficial. El resultado actualizado de la suite
completa y su SHA se consultan en el check `test` de `backend` del
[PR draft #189](https://github.com/Mkdir-arg/SistemaDeSalud/pull/189).
El SHA de publicación y los demás checks remotos quedan asociados al PR;
no atribuir resultados al checkout compartido.

La revisión directa del diff agregó la comprobación explícita de aceptación
por importe/prestación y uso comprometido antes de realizar; se repitieron los
dos E2E completos tras ese cambio. Durante el trabajo el checkout compartido
avanzó a `5905eca2b6a2508cf52fe2572faa7b117f443d57` por trabajo ajeno; no se
incorpora ni se atribuye a este PR. Sus archivos permanecen sin sobrescribir.

Skills: `brainstorming` para fijar alcance y aprobación, `playwright` para la
automatización solicitada y `systematic-debugging` para contrastar los fallos
de selectores con código/capturas antes de corregirlos. La revisión se hace
directamente, sin lanzar agentes adicionales. El usuario prefirió omitir la
instancia de proponer modos de fallo; no se acredita comprensión humana.

## Pendiente del bloque 2: destino

- Identificar destino, versión, motor, volumen, responsables y autorización de
  copia. No hay copia productiva autorizada en este corte.
- Ensayar migración, respaldo/restauración y comparar identidades, importes y
  fuentes de obligaciones/movimientos conservando el origen.
- Designar permisos, coberturas, circuitos programados, plazos y esperas reales.
- Acordar operación periódica de `correr_tiempos`, fallos y señales, reutilizando
  #7 y #30; sin nueva infraestructura ni cambios de cadencia implícitos.
- Validar suspensión de nuevas operaciones y recuperación de compromisos.
  Desactivar cobertura no suspende todos los cobros legados ni borra reservas/deuda.
- Antecedente: `docs/historico/plans/financiadores/operacion-continuidad.md`.

## Pendiente del bloque 3: datos e integraciones

- Diagnosticar declaraciones históricas y resolver identidades ambiguas con el
  hospital; importar sólo padrón confirmado, sin fusionar por nombre ni deuda retroactiva.
- Verificar plantillas/rechazos en Excel de escritorio: ceros, fechas, decimales,
  mezcla de válidos/rechazados y neutralización de fórmulas.
- Si aplica FHIR externo: consumidor, versión/perfil y fixtures ficticias;
  comprobar Coverage bajo ámbito hospitalario. #8 no demuestra este intercambio.
- Decidir política operativa de avisos: aceptación de bandeja/monitoreo o reintento
  mínimo explícitamente requerido, conservando una sola decisión administrativa.
- Antecedente: `docs/historico/plans/financiadores/interoperabilidad-cobertura.md`.

## Límites, aceptación y reversión

No se validan destino real, Excel de escritorio, consumidor FHIR ni operación
productiva. Liquidación formal, factura fiscal, conciliación bancaria y pagos
desde el portal siguen fuera de #43. No merge, deploy ni cierre del issue.
La aceptación y comprensión humanas no se deducen de tests verdes ni de revisión IA.

Reversión del corte: retirar exclusivamente los archivos añadidos por #43 y
detener su compose. Sin cambios de esquema productivo ni migraciones inversas.
Preservar archivos y datos concurrentes de otros agentes.
