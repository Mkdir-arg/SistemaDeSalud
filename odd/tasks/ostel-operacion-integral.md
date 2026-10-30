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

## Tasks

| ID | Specs | Unidad y condición | Ruta | Estado / evidencia |
| --- | --- | --- | --- | --- |
| T0 | S1–S6 | Reconciliar base, tablero y primer frente; registrar evidencia sin DB | Inline + mapa delegado por presupuesto de exploración | Completo: commit local `38fe688a07014e964a6e93405bf5b44768bb34dd`; evaluación pasiva |
| T1 | S2–S5 | #181 + #142: relación familiar y equivalencias internas | Inline; verificación independiente si cambia seguridad, contratos compartidos o concurrencia | Necesita decisión D1; sin código nuevo |
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
