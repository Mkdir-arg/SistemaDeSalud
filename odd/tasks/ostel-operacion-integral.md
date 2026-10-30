# Operación integral OSTEL

Orden rector: [#141, Plan de ejecución OSTEL — 30/10/2026](https://github.com/Mkdir-arg/SistemaDeSalud/issues/141). Rama: `juanikitro/ostel-operacion-integral-20261030`; base: `cae9e16a80559a1c936dc9e2f8727aa3bf3ad3d7`.
Entrega: `ask-on-risk`, sólo local; sin push, PR nuevo, merge ni deploy. Runner inicial sin DB: `python -B -m unittest backend.apps.financiadores.tests_ostel_scenarios -v`.

## Specs

- S1 — Solicitud original: «asigna esas tareas a juanikitro, movelas a "in progress" (aprovecha a quitar de esa columna las que no esten en progreso), asigna las prioridades segun veas necesarias y documenta ese orden para poder seguirlo. Luego desplega un agente especializado con GPT Astra para orquestar la planificacion e implementacion de cada tarea». Verificar el trabajo remoto ya realizado, no repetirlo.
- S2 — Orden de continuidad: «Selected issues: #141 coordination; #181 + #142 identity/families; #143 then #183 rights/lifecycle; #185 transversal verification; #184 operational UI QA; #147 medical authorizations; #144 then #145 contributions/accounts; #149 settlements; #148 medical reimbursements; #153 treasury/accounting; conditional #146 SSSalud.» Leer cada issue completo antes de su unidad; no ampliar a #150–#152.
- S3 — Identidad: «Never deduce family from a shared NROAFI.» Conservar NUMERO individual y CUIL; familias desde CUILTIT/CODPAR, sólo bajo equivalencias confirmadas. #181 exige resolución de ambigüedades, orden de filas independiente, ausencia de ciclos y aislamiento por financiador. No fusionar, renumerar ni reactivar automáticamente.
- S4 — Límite: «No Docker startup or DB connection is granted by this handoff.» Sólo fixtures completamente ficticios y pruebas puras/estáticas hasta autorización específica. Datos reales, secretos, SSH, integraciones, pagos y publicación de código quedan excluidos.
- S5 — Continuidad: «The user authorizes planning AND necessary in-scope LOCAL implementation, documentation and proportionate verification, not planning-only.» Consultar decisiones materiales sin inventar política. Reutilizar los servicios, revisiones, locks e historial existentes. Separar local, CI, commit, merge, despliegue y aceptación humana.
- S6 — Modelo: «Your selected model must remain gpt-6-astra; do not silently substitute it.» Corrección del usuario para el explorador: «no, para el epxlorador usa gpt-6-luna».
- S7 — Decisión D1 aprobada: «apruebo», en respuesta a conservar CODPAR como dato separado, sin modificar derechos médicos. No reducir automáticamente los códigos al parentesco genérico ni completar familias por inferencia.
- S8 — Autorización de prueba: «autorizo», para PostgreSQL efímero en Docker local, datos ficticios, loopback, pruebas seriales y eliminación del contenedor al terminar; ninguna base existente.

## Tasks

| ID | Specs | Unidad y condición | Ruta | Estado / evidencia |
| --- | --- | --- | --- | --- |
| T0 | S1–S6 | Reconciliar base, tablero y primer frente; registrar evidencia sin DB | Inline + mapa delegado por presupuesto de exploración | Completo: commit local `38fe688a07014e964a6e93405bf5b44768bb34dd`; evaluación pasiva |
| T1 | S2–S5,S7,S8 | #181 + #142: relación familiar y equivalencias internas | Inline; verificación independiente por seguridad/persistencia | En curso: T1a representación protegida; vinculación e importación automática posteriores |
| T2 | S2,S4,S5 | #143: contrato de fechas, motivos y derechos | Inline | Pendiente de lectura integral y decisiones de negocio |
| T3 | S2,S4,S5 | #183: novedades bajo contrato de T2 | Inline | Dependiente de T2 |
| T4 | S2,S4,S5 | #185: verificar cada incremento e integración | Inline; suites largas delegadas cuando corresponda | 22 pruebas puras base aprobadas; integración y aceptación pendientes |
| T5 | S2,S4,S5 | #184: QA de entrega existente con familias/novedades | Inline | PR196 incorporado; In QA; no reconstruir |
| T6 | S2,S4,S5 | #147: contraste de autorizaciones con reglas OSTEL | Inline | Pendiente de lectura integral; reutilizar motor existente |
| T7 | S2,S4,S5 | #144 → #145: aportes, conciliación y cuenta corriente | Inline | Pendiente de contratos; sin cobros reales |
| T8 | S2,S4,S5 | #149: liquidación a prestadores | Inline | Pendiente de contrato |
| T9 | S2,S4,S5 | #148: reintegros médicos, no devolución financiera | Inline | Pendiente de contrato |
| T10 | S2,S4,S5 | #153: tesorería/contabilidad ligada a eventos | Inline | Dependiente de contratos financieros |
| T11 | S2,S4,S5 | #146: intercambio oficial SSSalud | Inline | Condicional a necesidad operativa y layout oficial |

## Log

### L1 — Solicitud original

asigna esas tareas a juanikitro, movelas a "in progress" (aprovecha a quitar de esa columna las que no esten en progreso), asigna las prioridades segun veas necesarias y documenta ese orden para poder seguirlo. Luego desplega un agente especializado con GPT Astra para orquestar la planificacion e implementacion de cada tarea

### L2 — Reconciliación del 30/10/2026

- Cwd y rama corresponden al worktree independiente. HEAD y main remoto coinciden en `cae9e16a80559a1c936dc9e2f8727aa3bf3ad3d7`. `.atl/` preexistente se conserva sin agregar a commits. CodeGraph inicializado localmente; no se copió otro índice.
- #141, #181 y #142 leídos completos, incluidos comentarios. El orden superior de #141 prevalece sobre estados históricos.
- Readback GraphQL: 14 seleccionados asignados a juanikitro; PabloCao1 conservado en #148/#153. Prioridad Alta en #141/#181/#142/#143/#183/#185/#184/#147; Media en #144/#145/#149/#148/#153/#146. Todos In progress salvo #184 In QA. #180 In QA, #172/#198 Roadmap, #182 CLOSED/In QA. No se repitieron mutaciones.
- PR186, PR200 y PR196 MERGED. PR197 OPEN/DRAFT en `a7cc18287e693188b76454152563829105b6db74`, cinco checks SUCCESS en consulta actual; su descripción con tres checks es histórica. Sus tres archivos son evidencia, no implementación familiar. No se incorporó ni publicó ese PR.
- Configuración declara `gpt-6-astra`. El modelo prescrito del explorador `gpt-6.1-luna` fue rechazado; no se sustituyó automáticamente.

### L3 — Corrección del usuario y mapa

no, para el epxlorador usa gpt-6-luna

- Explorador `ostel_identity_map`, `gpt-6-luna/high`, completó mapa de sólo lectura; no editó ni ejecutó tests. Ruta delegada por necesidad de mapa de flujo más allá del presupuesto inline; no hay escritores paralelos.
- El primer handoff describía bloqueos demasiado amplios. Se corrigió contra la matriz de aceptación existente: NUMERO individual, CUIL personal, NROAFI compartible y referencia CUILTIT ya están documentados. No se vuelven a preguntar.
- Los 56 valores del escenario `parentescos_confirmados` son muestras de extremos de rangos, no un catálogo completo de sólo 56 códigos.
- D1 pendiente: representación del CODPAR original frente a `Afiliado.parentesco` (`conyuge`, `hijo`, `hija`, `conviviente`, `otro`). No hay equivalencia aprobada para comprimir todos los vínculos ni debe inferirse sexo desde el código. Recomendación a confirmar: conservar una referencia explícita al código OSTEL, separada de la clasificación genérica; más fidelidad a cambio de integración adicional. No implica derechos médicos ni habilita migraciones de datos existentes.
- Evidencia y límites se agregan al documento existente `docs/funcionalidades/financiadores-cobertura/ostel-aceptacion.md`, sin crear otro informe funcional.

### L4 — Verificación local y límites

- `python -B -m unittest backend.apps.financiadores.tests_ostel_scenarios -v`: 22 pruebas OK, 3.366 s. Ejecutadas en esta base; generador/lector puro, sin Django/DB. Temporales gestionados por `TemporaryDirectory` fuera del worktree.
- No hubo cambio de comportamiento: RED/GREEN y comparación diferencial no aplican a esta unidad documental. No se ejecutaron PostgreSQL, Docker, importación persistente, concurrencia, navegador ni pruebas de derechos. No se inició servidor ni se accedió a datos reales.
- No se acredita aceptación humana, despliegue ni CI de esta rama por las pruebas locales o los checks de PR197.
- Primera unidad prevista: aproximadamente 100 líneas documentales, sin cambio de producto. La estimación del programa completo depende de contratos aún pendientes; no se anticipa estrategia de PR ni se publica código.
- RDD observado `on (global)`. Para esta unidad pasiva, readback estructural y evaluación nativa; no fabricar aprobación ni revisión semántica.
- Próximo paso: resolver D1 antes de escribir vínculos familiares. El resto conserva orden y dependencias de #141; sus contratos no se presuponen aprobados.

### L5 — Cierre de la unidad documental

- Commit local T0: `38fe688a07014e964a6e93405bf5b44768bb34dd`, 84 líneas agregadas, dos documentos. Rollback acotado a esa documentación; no modifica comportamiento ni datos.
- `git diff --check` sin errores. Evaluación nativa del commit contra `cae9e16`: `passive`, `review_due=false`, `non_executable_only`. `.atl/` excluido explícitamente del inventario. No hubo START ni consentimiento de revisión solicitado para esta unidad pasiva.
- No hubo push, PR nuevo, merge ni despliegue. CI de estos commits y aceptación humana pendientes; pruebas DB/navegador no ejecutadas por alcance.

### L6 — D1 aprobada y verificación necesaria (30/10/2026)

apruebo

- Respuesta a conservar CODPAR como dato separado, evitando comprimir vínculos distintos en `otro`, sin modificar derechos médicos. Resuelve D1; no autoriza conexiones DB ni cambia permisos.
- Nuevo mapa de sólo lectura con `gpt-6-luna`: CODPAR incluye categorías de discapacidad; agregarlo al padrón general ampliaría la exposición. La representación por afiliado debe respetar el bloque protegido de salud y su historial, no `CAMPOS_GENERALES` (también define XLSX v2).
- `CodigoFinanciador` conserva el diccionario por financiador/tabla/código; no sustituye la asociación de cada afiliado con el código informado. `Importacion.filas.original` ya conserva CODPAR por fila y lote; no duplicar esta evidencia con otra tabla de importación.
- Hallazgo a considerar en la integración: el serializer de importaciones ya expone las filas originales bajo acceso general. Es comportamiento preexistente, no prueba de autorización para ampliar la consulta de datos sensibles. No se modificó ni se declaró corregido.
- Fronteras a verificar: importación/consulta/historial protegido, revisión optimista, aislamiento por financiador y ausencia de cambios de parentesco genérico, vínculos o derechos. Reutilizar `editar_protegido` y sus guards/auditoría; comprobar el orden de locks antes de integrarlo con aplicación de lotes. La ruta de lectura nueva no debe ampliar permisos existentes.
- El runner de pruebas de persistencia/permisos requiere DB. La política actual prohíbe conexiones, incluso de prueba: no se ejecutó RED ni se fabricó su resultado. Tampoco se escribió migración o código funcional sin poder observar el contrato de persistencia.
- Autorización a solicitar: PostgreSQL local efímero en Docker, puerto loopback, almacenamiento temporal, sólo datos totalmente ficticios y ejecución serial; nunca una base existente, demo o producción. Crear y retirar exclusivamente el contenedor de prueba identificado. Sin nuevas dependencias del proyecto ni credenciales existentes.
- T1 sigue pendiente, no completo. Riesgos previstos de su implementación: ítems 1 (esquema persistido), 2 (confidencialidad/guards), 4 (locks compartidos). La decisión de representación no constituye aceptación de negocio de familias.

### L7 — Pruebas autorizadas y primer corte T1a

autorizo

- Autoriza el contenedor PostgreSQL descartable descrito en L6; no bases existentes ni remotas. Imagen local `postgres:16-alpine`, sin descarga; ejecución serial.
- T1a: campo opcional `codpar_ostel` en `SaludPadron`, conservado como texto separado de `parentesco`, con los permisos, revisión e historial de `editar_protegido` y el endpoint protegido existente. No se infiere catálogo, parentesco, familia, sexo ni elegibilidad. No hay backfill ni cambio de exportación genérica.
- La carga manual usa el contrato PATCH protegido ya existente; el endpoint general no admite el nuevo campo. La copia automática desde el importador queda fuera de T1a: su acceso general no equivale a designación de salud y no se agregará un bypass.
- Frontera RED/GREEN: API de salud del padrón e historial, con regresión del campo protegido previo; permisos de lectura/escritura, revisión obsoleta, aislamiento y rechazo en API general. Migración aditiva verificada sólo sobre la base ficticia.
- Ruta: escritura inline (sin motivo para escritor delegado); verificador independiente por ítems 1/2/3, tras checks propios. Estimación T1a: menos de 250 líneas; no cambiar contratos existentes, dependencias ni UI. No se ejecuta navegador porque no hay cambio de pantalla.
- RED: test de PATCH protegido `test_codigo_literal_separado_con_historial_y_sin_efectos_generales`, HTTP 400 por campo desconocido. GREEN: mismo test pasa tras campo opcional, serializer literal y guard de tipo; ampliado a tres tests API, todos OK (0.398 s). Un fallo de fixture esperaba 400 de cobranza sin designación; se corrigió sólo el permiso del usuario ficticio y pasó.
- `makemigrations financiadores --check --dry-run` con settings PostgreSQL aislados: sin cambios faltantes. La migración se aplicó sólo al test database del contenedor identificado `ostel-codpar-01a18cf3` (ID comienza `34b61a9b749e`), loopback y tmpfs. Sin lectura de `.env` (`PYTHON_DOTENV_DISABLED=1`).
- Modelo/servicio no cambia locks: se reutilizan los de salud. Regresiones e inspección independiente pendientes; no se afirma T1 completo ni importación de códigos implementada.

### L8 — Evidencia T1a

- Verificador independiente `codpar_verify` (`gpt-6.1-sol/medium`) sobre copia temporal aislada: PASS acotado a T1a, 79 tests + 3 probes candidatos + 1 probe base. Seis respuestas API normalizadas equivalentes (campos previos de salud e historial; rechazos en general/cobranza). No usa git histórico dentro de tests comprometidos.
- Probes de preservación de todos los campos en migración y de hash sin cambios ante rechazo incorporados a `test_codpar_ostel.py`. Repetición padre de la suite reportada con esos probes: 81 tests OK, 14.411 s. `makemigrations --check --dry-run`: sin cambios faltantes. Sin cambios de locks ni permisos.
- La alerta de `staticfiles` ausente no impidió los tests; no se generaron estáticos por no cambiar frontend. No se verificó navegador ni aceptación de OSTEL. CI/push/merge/deploy no ejecutados.
- Risk: items 1 (migración aditiva), 2 (dato sensible), 3 (servicio compartido). Verificación independiente realizada; evaluación y consentimiento nativos de este candidato pendientes. T1 global permanece en curso: falta integración desde importación y construcción familiar bajo contratos seguros.
