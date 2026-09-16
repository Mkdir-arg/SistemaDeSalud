# Continuidad de financiadores: implementación B1–B8

16/09/2026. Rama `codex/financiadores-cobertura`, [PR #41](https://github.com/Mkdir-arg/SistemaDeSalud/pull/41).
Ejecuta el [plan aprobado](continuidad-del-circuito.md). Las decisiones nuevas provienen
de sus recomendaciones, aceptadas bajo la instrucción de avanzar automáticamente.
No se afirma aceptación humana ni habilitación del entorno productivo.

## Resultado por bloque

| Bloque | Resultado observable | Archivos principales |
| --- | --- | --- |
| B1 | Diagnóstico del texto legado por hospital, sólo lectura, sin inferir afiliación ni crear deuda. | `financiadores/legado.py`, comando `diagnosticar_coberturas_legacy` |
| B2 | Padrón, búsqueda, ficha e historia distinguen declaración histórica y afiliaciones vigentes. La cobertura verificada se consulta por hospital; no se elige automáticamente. | `financiadores/administrativa.py`, `registros/serializers.py`, `Registros.jsx`, `PadronDetalle.jsx`, `ui/paciente.jsx` |
| B3 | Comprobación de catálogo, convenios, reglas, aranceles, padrón y responsables explícitos. Ensayo aislado de migración, respaldo/restauración y suspensión. | `financiadores/preparacion.py`, `test_preparacion.py`, [guía operativa](operacion-continuidad.md) |
| B4 | Solicitud, observación, reenvío, aprobación, rechazo, anulación e historia; bandeja integrada al sidebar de CAUCE. | `autorizaciones.py`, `api_autorizaciones.py`, `AutorizacionesFinanciador.jsx`, `AutorizacionesCaso.jsx` |
| B5 | Cantidad aprobada, comprometida y realizada; importe pendiente de autorización separado de deuda exigible y del copago. | `uso_autorizaciones.py`, `cobros.py`, `clinica.py`, `actividad.py`, `seguimiento.py` |
| B6 | Espera sólo en circuito programado explícito; aprobación libera el mismo paso; supervisión con motivo; vencimientos mediante el reloj existente. | `esperas.py`, `casos/motor.py`, `correr_tiempos`, `FlujoEditor.jsx` |
| B7 | Derivación reconsulta cobertura en destino y detecta conflictos de identidad. FHIR Coverage presenta afiliación vigente, sin prometer cobertura económica. | `red/motor.py`, `fhir/cobertura.py`, [contrato de interoperabilidad](interoperabilidad-cobertura.md) |
| B8 | Auditoría individual conservada con escrituras en lotes y rollback ante cualquier fallo. | `auditoria/mixins.py`, `financiadores/acceso.py`, [evidencia del issue #42](auditoria-por-lotes.md) |

## Contratos de autorización y dinero

- Una solicitud pertenece a un convenio/hospital, afiliado y prestación común.
  No es portable a otro hospital. El cupo del plan sigue compartido.
- El intento se deriva del caso, nodo y comienzo del paso. Actualizar datos
  administrativos no crea otro intento; volver al nodo sí lo hace.
- `resuelve_autorizaciones` requiere designación expresa. Un auditor de lectura
  no decide. Las migraciones no conceden esta capacidad a usuarios existentes.
- Observar conserva el plazo original. Vigencia de aprobación, plazo de respuesta
  y cantidad son conceptos separados. Sin plazo configurado no hay vencimiento
  automático de respuesta; la aprobación siempre tiene vigencia delimitada.
- Cada operación usa clave de reintento, revisión y evento. Las terminales no se
  reabren. Una nueva solicitud referencia la terminal anterior del mismo origen
  y ámbito; nunca expone una solicitud de otra obra social tras cambiar afiliación.
- Aprobar no crea una atención, no avanza el nodo, no amplía el cupo del plan ni
  acepta el importe del paciente. Puede comprometer una reserva ya existente.
- La realización registra el uso y genera el cargo según autorización, vigencia y
  condiciones conservadas. La recuperación financiera es idempotente.
- Si falta autorización, el importe del financiador queda como pendiente
  administrativo; el copago expresamente aceptado puede emitir su cuenta por separado.
  Aprobar después completa la distribución del hecho existente, sin otra atención.
- Rechazar no transfiere deuda automáticamente al paciente. Finanzas designada
  resuelve `parte=financiador` con motivo y evidencia cuando se asigna responsabilidad.
  Una aprobación posterior no duplica ni deshace esa resolución explícita.
- Completar un arancel conserva el cupo comprometido ante consumo externo tardío
  **y revalida la autorización**. Corregir una afiliación pendiente registra el uso
  de una aprobación aplicable antes de distribuir cargos. Si una regla nueva ya
  no la exige, el compromiso anterior se libera con vínculo al hecho y discrepancia.
- No se reasigna silenciosamente un uso histórico a otra solicitud. Si ya existe
  ese vínculo, renovar la reserva no realizada o resolver el hecho conserva la traza.
- Los caminos administrativos bloquean caso → hechos existentes ordenados → afiliado
  → convenio → solicitud. La captura conserva hecho → afiliado; nunca se toma un
  hecho después de bloquear al afiliado. Las reservas comparten ese bloqueo.

## Esperas y continuidad clínica

`VersionFlujo.tipo_circuito` admite `no_definido` (default), `guardia` y `programado`.
Sólo un nodo ATENCION de una versión programada puede tener
`config.esperar_autorizacion=true`. Se valida al editar, publicar y ejecutar;
las versiones publicadas conservan su configuración.

La espera usa `Caso.espera_autorizacion`, independiente del subproceso `esperando`
y del temporizador `reactivar_en`. Aprobar la levanta si todos los requisitos están
resueltos; la acción clínica posterior registra la realización. Guardia, circuitos
no definidos y urgencias originales mantienen continuidad. Si una espera ya
existente escala a urgente, el personal habilitado deja motivo explícito para continuar.

La supervisión clínica se verifica por hospital y área; el permiso financiero no la
sustituye. Cancelar anula solicitudes abiertas, pero conserva reservas salvo confirmación
expresa de no realización. El reloj vence solicitudes por plazo o vigencia, con índices
y exclusión concurrente, sin fabricar atención. Los avisos internos son posteriores
al commit; sus fallos se registran, sin una cola nueva de reintentos.

## Datos y reversión operativa

Migraciones aditivas: `financiadores/0006` y `0007`, `casos/0014`, `flujos/0008`.
Los defaults preservan las reglas existentes: sin autorización obligatoria, sin
resolutores nuevos y sin espera clínica implícita. No se convierten declaraciones
históricas ni se seleccionan afiliaciones retrospectivamente.

La guía de operación distingue desactivar nuevas operaciones de cobertura de
suspender todos los cobros: una atención nueva sin reserva puede seguir el circuito
legado. Se conservan cuentas, pagos, reservas, hechos e historia. No se prescribe
una migración inversa destructiva como mecanismo de reversión.

## Validación de esta implementación

- **641/641 pruebas PostgreSQL**, sin omisiones (159,797 s): financiadores completos,
  auditoría por lotes, registros, FHIR, integración de Red, guardas/permisos/esquema
  de Casos y Flujos. Incluye solicitudes y usos concurrentes, aceptación, Q01,
  resolución tardía, aislamiento y ensayo B3 sobre SQLite separado.
- **132/132 PostgreSQL** del incremento B6, con reloj, supervisión, permisos,
  guardas y carreras de aprobación/cancelación. No equivale a sumar 132 casos
  distintos a los 641: hay cobertura repetida.
- **59/59 PostgreSQL** posteriores al merge de auditoría (27,131 s): exportaciones
  de 5.000/5.001 y regresiones de cobros/dinero. El CSV de 5.000 personas conservó
  5.000 evidencias y once INSERT (20 sentencias totales; 2,953 s locales). La descarga
  hospitalaria tardó 0,355 s. No son comparaciones nuevas antes/después ni SLA.
- **56/56 PostgreSQL y 56/56 SQLite** después del ajuste final de Red: origen
  normalizado con destino legado único, variantes conflictivas, ceros y letras
  ASCII, además del circuito de traslados existente. La búsqueda está limitada
  al hospital y dos coincidencias; no carga todo el padrón en Python.
- **73/73 Playwright** para portal, clínica y autorizaciones, con API simulada;
  después **2/2** focales del vínculo al antecedente y **1/1** móvil de captura.
- Build Vite correcto (756 módulos). `check`, `makemigrations --check --dry-run`
  y `git diff --check` correctos. No se agregaron dependencias.
- Revisión estática cruzada por Claude de frontend, backend y contratos, con
  contraste del agente principal. Los hallazgos de completar arancel/afiliación
  y compromiso antiguo se reprodujeron antes de corregir y tienen regresiones.
- Navegador contra backend/base reales **ficticios**: la aprobación de Nora libera
  la espera, conserva el paso y deja una unidad comprometida, cero realizadas y
  dos disponibles. Sin errores JavaScript. Revisión visual conserva sidebar CAUCE.

Comando principal desde `backend`, con `CAUCE_TEST_POSTGRES_URL` apuntando sólo al
PostgreSQL local de pruebas permitido por el settings dedicado:

```text
python manage.py test apps.financiadores apps.auditoria.test_lotes apps.registros apps.fhir apps.red.test_cobertura apps.casos.test_motor_guardas apps.casos.test_permisos_barrida apps.casos.test_esquema apps.flujos --settings=cauce.settings_financiadores_postgres_test --noinput
```

Frontend:

```text
npx playwright test --config playwright.financiadores-ui.config.js financiadores-ui.spec.js cobertura-clinica-ui.spec.js autorizaciones-ui.spec.js
npm run build
```

Logs locales: `%TEMP%/cauce-continuidad-final-pg.log` y
`%TEMP%/cauce-continuidad-volumen-dinero-pg.log`. No son resultados de CI remoto.

## Demo y aceptación pendiente

Demo local: `http://127.0.0.1:5188`, backend `127.0.0.1:8766`. Se migró exclusivamente
su SQLite ficticio después de un respaldo consistente y se compararon todas las
obligaciones y movimientos anteriores. No se modificó `localhost:8090`.

- **Bruno, caso 10 / solicitud 1:** espera programada; pendiente para probar resolución.
- **Elena, caso 11 / solicitud 2:** prestación urgente ficticia realizada; $8.000
  pendientes de autorización y $2.000 de copago aceptado, sin cargo al financiador.
- **Nora, caso 12 / solicitud 3:** aprobada desde el navegador; mismo paso, pendiente
  de realización clínica. Los datos previos de la demo se conservan.

Se mantienen los usuarios ficticios `financiador@demo.local`, `consulta@demo.local`
y `hospital@demo.local`. Datos, respaldos y evidencia local viven fuera del repositorio
en `%LOCALAPPDATA%/Cauce/demos/financiadores-main2`.

Antes de incorporar a un hospital real faltan la copia autorizada del destino,
ensayo/restauración en su motor y volumen, responsables y permisos designados,
configuración explícita de esperas/plazos, operación del reloj y aceptación del
recorrido. No se validaron apertura en Excel de escritorio, un consumidor FHIR
externo ni infraestructura productiva. Los tiempos locales no constituyen SLA.
La comprensión y aceptación humana no se deducen de tests ni de otra revisión IA.

Liquidación formal, facturación fiscal, conciliación bancaria y pagos desde el portal
del financiador permanecen fuera de este plan. No se cierran las épicas #13–#20
por completar estos bloques. El usuario solicitó dejar el PR preparado para su
incorporación personal; #42 se cierra sólo al incorporar su cambio mediante el PR.

## Prioridad posterior y próxima sesión

El [issue #43](https://github.com/Mkdir-arg/SistemaDeSalud/issues/43) tiene prioridad
alta en Salud y debe atenderse antes de ampliar las funcionalidades financieras.
Reúne CI, recorrido integral con backend real, preparación del destino, datos e
integraciones aplicables; reutiliza los trabajos existentes de jobs y monitoreo.
Se registra para después: no se inicia su implementación en este cierre.

La próxima sesión será de comprensión guiada del módulo, de conceptos a operación
y trazabilidad técnica. El usuario realizará el merge por su cuenta y pospuso ese
acompañamiento a la sesión siguiente. Preparar el PR no acredita comprensión humana
ni aceptación del piloto o del despliegue; tampoco habilita operar sobre datos reales.
