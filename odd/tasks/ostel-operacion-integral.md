# Operación integral OSTEL

Orden rector: [#141, Plan de ejecución OSTEL — 30/10/2026](https://github.com/Mkdir-arg/SistemaDeSalud/issues/141). Rama: `juanikitro/ostel-operacion-integral-20261030`; base: `cae9e16a80559a1c936dc9e2f8727aa3bf3ad3d7`.
Entrega: `ask-on-risk`, cadena elegida `feature-branch-chain`, sólo local; sin push, PR nuevo, merge ni deploy. Runner inicial sin DB: `python -B -m unittest backend.apps.financiadores.tests_ostel_scenarios -v`.

## Specs

- S1 — Solicitud original: «asigna esas tareas a juanikitro, movelas a "in progress" (aprovecha a quitar de esa columna las que no esten en progreso), asigna las prioridades segun veas necesarias y documenta ese orden para poder seguirlo. Luego desplega un agente especializado con GPT Astra para orquestar la planificacion e implementacion de cada tarea». Verificar el trabajo remoto ya realizado, no repetirlo.
- S2 — Orden de continuidad: «Selected issues: #141 coordination; #181 + #142 identity/families; #143 then #183 rights/lifecycle; #185 transversal verification; #184 operational UI QA; #147 medical authorizations; #144 then #145 contributions/accounts; #149 settlements; #148 medical reimbursements; #153 treasury/accounting; conditional #146 SSSalud.» Leer cada issue completo antes de su unidad; no ampliar a #150–#152.
- S3 — Identidad: «Never deduce family from a shared NROAFI.» Conservar NUMERO individual y CUIL; familias desde CUILTIT/CODPAR, sólo bajo equivalencias confirmadas. #181 exige resolución de ambigüedades, orden de filas independiente, ausencia de ciclos y aislamiento por financiador. No fusionar, renumerar ni reactivar automáticamente.
- S4 — Límite: «No Docker startup or DB connection is granted by this handoff.» Sólo fixtures completamente ficticios y pruebas puras/estáticas hasta autorización específica. Datos reales, secretos, SSH, integraciones, pagos y publicación de código quedan excluidos.
- S5 — Continuidad: «The user authorizes planning AND necessary in-scope LOCAL implementation, documentation and proportionate verification, not planning-only.» Consultar decisiones materiales sin inventar política. Reutilizar los servicios, revisiones, locks e historial existentes. Separar local, CI, commit, merge, despliegue y aceptación humana.
- S6 — Modelo vigente: «no, sos gpt-6.1-sol, cambie de decision». Orquestador `gpt-6.1-sol`; explorador `gpt-6-luna/high`; verificador `gpt-6.1-sol/medium`. Historia: «Your selected model must remain gpt-6-astra; do not silently substitute it.» Corrección del usuario para el explorador: «no, para el epxlorador usa gpt-6-luna».
- S7 — Decisión D1 aprobada: «apruebo», en respuesta a conservar CODPAR como dato separado, sin modificar derechos médicos. No reducir automáticamente los códigos al parentesco genérico ni completar familias por inferencia.
- S8 — Autorización de prueba: «autorizo», para PostgreSQL efímero en Docker local, datos ficticios, loopback, pruebas seriales y eliminación del contenedor al terminar; ninguna base existente.
- S9 — Decisión D2 aprobada: «apruebo», en respuesta a mantener la importación administrativa para operadores y reservar la aplicación de CODPAR a un paso protegido por un usuario designado de salud. Conservar el código original y la procedencia, sin modificar familias ni derechos.
- S10 — Estrategia elegida: «1», correspondiente a «Cadena sobre rama de funcionalidad — recomendada: integrar los cortes antes de llevarlos a main». No autoriza publicación ni incorporación a main.
- S11 — Decisión D3 aprobada: «autorizo», a persistir vínculos CUILTIT→CUIL confirmados con parentesco vacío, cambiando el contrato compartido y sus consumidores. Titular conocido con clasificación pendiente no equivale a titular sin vínculo, ni permite parentesco sin titular, ciclos o cruces de financiador.
- S12 — Entorno visual autorizado: «autorizo», para instalar dependencias desde el lockfile existente sin agregar ni actualizar, iniciar frontend/backend sólo en localhost con PostgreSQL descartable y datos ficticios, y verificar escritorio, móvil y teclado.
- S13 — Continuidad local: «sigue sin eso», después del bloqueo de la revisión nativa T1e. Continuar el desarrollo autorizado sin esperar esa revisión, sin declararla aprobada ni desactivar globalmente las revisiones. No amplía permisos de publicación, datos reales ni decisiones de derechos.

- S14 — Parametrización aprobada: «ya fue solicitado esa informacion a ostel. apruebo tu propuesta para parametrizacion. avanza con lo que puedas sin la respuesta de ostel». Autoriza base controlada/versionada y previsualización no operativa, no valores normativos ni activación de derechos.

- S15 — Nombre y funcionalidad: «me gusta tu propuesta. debe demostrar seguridad al desarrollo, debe estar hecho para funcionar». Aprueba «Reglas de derechos» como módulo y «Borrador» como estado; conservar límites entre base implementada y motor operativo pendiente, sin inventar normativa ni activar derechos.

## Tasks

| ID | Specs | Unidad y condición | Ruta | Estado / evidencia |
| --- | --- | --- | --- | --- |
| T0 | S1–S6 | Reconciliar base, tablero y primer frente; registrar evidencia sin DB | Inline + mapa delegado por presupuesto de exploración | Completo: commit local `38fe688a07014e964a6e93405bf5b44768bb34dd`; evaluación pasiva |
| T1 | S2–S5,S7–S13 | #181 + #142: relación familiar y equivalencias internas | Inline; verificación independiente por seguridad/persistencia | T1a verificado/revisado en `e0aec12`; T1b completo local en `4212293`; T1c completo local/revisado en `0e2eb40`; T1d API local verificada en `476cfb2`, revisión omitida; T1e UI verificada localmente en `f72c89b`, consentimiento omitido, autoridad residual sin cierre (L20). Sin aceptación operativa |
| T2 | S2,S4,S5,S13 | #143: contrato de fechas, motivos y derechos | Mapa delegado para decidir; análisis y futura escritura inline | Lectura integral y matriz de decisiones pendientes documentadas (L21); falta fuente validada por OSTEL antes de implementar derechos |
| T2a | S5,S6,S14 | Borrador inmutable versionado y consulta de coincidencias/conflictos por ámbito/fecha, sin efectos | Inline tras mapa delegado por presupuesto; Risk: none (módulo nuevo aislado) | Completo local en `3a23cf132b28f0be841e10df54c7ba6fc1c8dd73`; RED→GREEN; evaluación medium/under_budget; espejo pendiente (L22) |
| T2b | S5,S14 | Comparar propuesta completa contra historial sin borrar/redefinir versiones | Inline; sin helper compartido modificado, Risk: none | Completo local en `317269865c043a935f571798cf6e3465c3df9aef`; RED→GREEN/regresión; evaluación medium/under_budget |
| T2c | S5,S8,S14 | Persistir propuestas de borradores con autoría y auditoría, sin activación | Inline; verificador independiente por ítems 1/2/4 | Verificado local/independiente en `85214f4`; nativa high pendiente por preflight no ejecutable, sin START (L24) |
| T2d | S5,S14 | API administrativa de consulta/guardado de borradores, sin activar | Inline; verificador independiente por ítem 2 | Verificado local/independiente en `ecd5f90`; revisión nativa pendiente por continuación incompleta (L25) |
| T2e | S5,S12,S14 | UI administrativa de versiones no operativas | Inline tras mapa; verificador independiente por ítem 4 | Verificado local/independiente en `ff3b803`; navegador visible ficticio; nativa pendiente por continuación incompleta (L26) |
| T2f | S5,S14,S15 | Nombre del módulo y estado Borrador sin prometer un motor terminado | Inline, Risk: none (texto solicitado, sin lógica compartida modificada) | Completo local en `2211e03`; RED→GREEN, ocho recorridos reales/build OK; evaluación medium/under_budget |
| T2g | S5,S14,S15 | Primer mecanismo ejecutable: simulación de umbral en días corridos | Inline, Risk: none (módulo puro nuevo sin consumidores operativos) | Implementado/verificado local; baseline `36be68a`; RED→GREEN y 40 pruebas puras OK; commit/evaluación pendientes |
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
- Commit T1a: `e0aec1201a4109a017ce7db44bd3ead4f1e0ee73`, 240 líneas modificadas en seis archivos. Evaluación nativa contra `fa3f353`: high, `review_due=true`, por migración ejecutable e ítem 2 explícito. Consentimiento pendiente; no equivale a aprobación ni publicación.
- Limpieza bloqueada por política de la herramienta antes de ejecutar la orden. Readback posterior: contenedor `34b61a9b749e1fe03be37e85adeb14863103c1484083dacf38483f6f84689f06` sigue activo y scratch `ostel_codpar_verify_i38c54az` sigue presente en el directorio temporal del usuario. No se reintentó por otra vía. Limpieza pendiente; no afirmar eliminación. No hay datos reales ni credenciales del usuario en esos recursos.

### L9 — Revisión consentida y continuación (30/10/2026)

1

- Respuesta a «Revisar este cambio» (`granted`). Dos capturas nativas concurrentes, en orden riesgo/confiabilidad, inspeccionaron los seis parches inmutables y devolvieron cero hallazgos. No ejecutaron pruebas; los 81 tests son evidencia separada.
- Cierre nativo confirmado por `gentle-ai.review-acknowledged/v1`: `action=acknowledged`, `authority=burned`, lineage `review-36eadf9276829d86`, target `sha256:e1712b4dba8ccca5ba2680eccc30922614bd287b5c7383f276332ac0dee89ef7`. No se reinicia esta revisión ni se infiere autorización de entrega.
- T1a completo sólo como capacidad local protegida; sin publicación, despliegue ni aceptación humana. La limpieza de recursos de prueba sigue pendiente por el bloqueo anterior.
- D2 a consultar antes de automatizar la copia: mantener la importación administrativa para operadores sin designación de salud y reservar la aplicación de CODPAR a un paso protegido por un usuario designado. Recomendación: esta separación evita conceder acceso de salud a todo importador, a cambio de una intervención adicional. No está aprobada aún y no autoriza el acceso general a códigos sensibles ni elimina el hallazgo preexistente de filas originales.

### L10 — D2 aprobada y corte T1b (30/10/2026)

apruebo

- Resuelve D2 de L9. Paso backend explícito por afiliado, lote y ordinal de fila aplicada; toma el destino persistido de esa fila y exige que coincida con el afiliado solicitado y el financiador. Reutiliza `editar_protegido`, revisión optimista, designación e historial de salud. Conserva CODPAR literal; fuente vacía, no textual o inválida no borra un valor existente.
- Procedencia lote/hoja/fila Excel sólo en el motivo del historial protegido. Sin cambios en importación ordinaria, JSON original, parentesco, vínculos, derechos ni auditoría general con valores sensibles. Sin UI en este corte.
- Ruta inline tras mapa delegado `ostel_identity_map`; Risk: items 2 (guard de salud), 4 (lock de lote antes del servicio compartido). Verificación independiente tras RED/GREEN API y regresiones. Runner: `python -B manage.py test apps.financiadores.test_codpar_importacion apps.financiadores.test_codpar_ostel apps.financiadores.test_padron130 apps.financiadores.test_ostel_importacion apps.financiadores.test_concurrencia_padron130 --settings=config.settings_financiadores_postgres_test --noinput --keepdb --verbosity 0`, sólo contenedor efímero autorizado.
- Estimación: 250–350 líneas para T1b; acumulado anterior 349. Estrategia `ask-on-risk`: elegir cadena antes del próximo commit; ninguna publicación autorizada. Limpieza anterior continúa pendiente por denegación de herramienta.
- RED observado: nuevo POST devuelve 404. GREEN: copia literal y procedencia protegida tras importación administrativa sin designación, sin cambios de derechos/lote. Al ampliar rechazos, el serializer generó 500 por devolver lista desde `to_internal_value`; corregido a errores de campo (`non_field_errors`). El fixture de membresía inactiva esperaba 403 pero el contrato existente oculta el financiador con 404; se corrigió sólo la expectativa.
- Regresión completa indicada arriba: 87 tests OK, 26.441 s; `git diff --check` sin errores. Verificador independiente pendiente (permisos, locks, invariantes y comparación con baseline `f6ad97b`). Sin normalizadores mutantes configurados para este corte; no hay migración ni cambio UI. No hay CI/publicación/despliegue.
- Verificador `codpar_copy_verify`, `gpt-6.1-sol/medium`: PASS acotado a S3/S5/S7/S8/S9, 87 tests y tres probes; nueve respuestas API previas equivalentes al baseline. Sin bloqueantes. Carrera copia/copia y revocación durante espera probadas; copia/aplicación administrativa sólo inspeccionada. Probes de concurrencia y destino ajeno incorporados como regresiones; repetición padre de la suite: 90 tests OK, 31.171 s. `git diff --check` sin errores.
- Scratch adicional retenido: `C:/Users/Juanito/AppData/Local/Temp/ostel_t1b_verify_w_k0rjbi`. No se reintenta limpieza denegada por otra vía. Sin datos reales. El contenedor y el scratch de T1a siguen pendientes de limpieza.
- Próxima decisión antes del commit: cadena `stacked-to-main` (entregas incrementales) o `feature-branch-chain` (integrar cortes antes de main, recomendada para el frente familiar aún incompleto). Límite T1a: base `fa3f353` → `e0aec12`; T1b: base `f6ad97b` → candidato actual. No se crea PR ni se publica al elegir la estrategia. RDD del nuevo candidato aún no iniciado; T1a cerrado no se reabre. Risk: items 2 y 4.

### L11 — Cadena seleccionada (30/10/2026)

1

- Respuesta a la estrategia de entrega: `feature-branch-chain`. La rama de integración acumulará los cortes; el futuro tracker será draft/no-merge y sus hijos apuntarán al padre inmediato. No crear tracker, PR ni push sin autorización posterior. Se conservan la rama de trabajo y todos los commits actuales, sin rebase ni reescritura.
- Cadena prevista: `main@cae9e16` → integración OSTEL → corte 1 (`cae9e16..f6ad97b`: coordinación y T1a, 349 líneas autoradas acumuladas) → corte 2 actual (`f6ad97b..T1b`: copia protegida, pruebas y documentación, menos de 400 líneas previstas) → familia y unidades siguientes de #141 según sus contratos. El corte 2 depende del campo protegido del corte 1; ninguno representa operación integral aceptada.
- Antes de una publicación autorizada, materializar ramas de cada límite y comprobar que cada diff contiene sólo su corte y puede revisarse en menos de 60 minutos. La revisión nativa de T1b usa `f6ad97b` como límite, sin reabrir T1a. No hay estrategia mixta ni publicación incremental directa a main.

### L12 — Cierre local T1b y revisión declinada (30/10/2026)

2

- Respuesta a «Omitir esta vez». Invocación exacta de `consent/v3` ejecutada una vez: `action=declined`, `consent=declined_this_candidate`, target `sha256:467dd80ba4e60184d9a9c21055ee4733ce1c121b5d309ac4925609814c688d2e`. No se creó aprobación de revisión; el modo global permanece habilitado. No volver a ofrecer revisión de este mismo candidato por una actualización documental.
- Commit T1b `4212293048ced27a0c69aea91270f86073145a31`: 358 adiciones + 6 eliminaciones, cinco archivos; acumulado autorado del programa 713. Corte 2 dentro de 400 líneas. Evaluación high por ítem 2; verificación independiente y regresiones de L10 conservadas. La negativa sólo afecta la revisión nativa, no revoca la implementación ni habilita publicación.
- Siguiente trabajo autorizado: determinar el primer incremento de familias según #181/#142, sin deducir vínculos de NROAFI ni comprimir CODPAR en parentesco genérico. Todavía faltan familia/UI y aceptación operativa; los hallazgos de exposición y limpieza de recursos continúan abiertos.

### L13 — Contrato familiar a resolver antes de escribir (30/10/2026)

- `ostel_family_next_map`, `gpt-6-luna/high`, leyó #141/#181/#142 y comentarios vigentes; utilizó CodeGraph sincronizado. La antigua falta de CUILTIT no es un bloqueo actual. El catálogo 00–05 de #142 es una propuesta, no una equivalencia aprobada al enum local. El importador genérico resuelve referencias en orden de filas y no satisface por sí solo el requerimiento OSTEL de orden independiente.
- El mapa inicial recomendó titular con parentesco vacío. Se descartó tras contrastarlo con `padron.validar_generales`: exige ambos presentes o ambos vacíos. El explorador corrigió su conclusión. `editar_ficha` aplica este guard junto con locks, aislamiento y estructura familiar de un nivel. No se escribió código familiar ni se eludió validación.
- D3 pendiente: persistir un vínculo CUILTIT→CUIL inequívoco con titular conocido y clasificación genérica pendiente exige cambiar el contrato compartido y ajustar sus consumidores; alternativa conservadora, mantener propuesta/revisión sin persistir hasta confirmar equivalencias. D1 conserva CODPAR separado pero no aprueba implícitamente ese cambio de invariante. Decisión del usuario necesaria, sin volver a preguntar las claves de identidad ya confirmadas. No usar `otro` como equivalencia inventada.
- Riesgos previstos: ítem 3 (contrato compartido por edición, importación y consulta) e ítem 4 (concurrencia de vínculos). Requerir regresiones de comportamiento previo, igualdad diferencial y verificación independiente; no afirmar familia operativa antes de esas pruebas y aceptación. El circuito financiero y de derechos sigue el orden de #141, no se presume desbloqueado por T1b.
- Cierre documental previo `9990576`: evaluación pasiva, sin nueva revisión de T1b. La cadena elegida no habilita publicar ni crear PR. Limpieza de recursos de prueba aún pendiente por la denegación registrada.

### L14 — D3 aprobada: representación antes del ensamblado (30/10/2026)

autorizo

- Aprueba el cambio de contrato consultado en L13. T1c permite titular conocido con `parentesco=""`; conserva rechazo de clasificación sin titular, ciclos, familia multinivel, financiador distinto, revisión obsoleta y permisos existentes. No agrega enum, no migra datos ni deduce equivalencias de CODPAR. T1d resolverá posteriormente CUILTIT por lote; T1c no lo declara implementado.
- Mapa adicional con `gpt-6-luna`: API familiar, listado y exportación ya derivan la relación del FK titular, no de parentesco. La interfaz existente distingue la raíz por su ID y muestra «Parentesco sin informar» para integrantes sin clasificación. No requiere cambio visual para representar el contrato; no se agregan labels cosméticos en este corte. Frontend sin node_modules: recorrido browser no disponible, sin instalaciones automáticas.
- Escritura inline de la validación compartida y pruebas API/importación/XLSX, reutilizando los servicios existentes. Estimación 180–250 líneas en corte independiente de `feature-branch-chain`. Risk: item 3 (contrato compartido); locks sin cambio, verificar invariantes concurrentes existentes por ítem 4. Runner PostgreSQL autorizado: `python -B manage.py test apps.financiadores.test_familia_pendiente apps.financiadores.test_padron130 apps.financiadores.test_importaciones apps.financiadores.test_concurrencia_padron130 apps.financiadores.test_padron_consulta apps.financiadores.test_padron_exportacion --settings=config.settings_financiadores_postgres_test --noinput --keepdb --verbosity 0`.
- Observar RED de vínculo con clasificación pendiente, luego GREEN; conservar altas/edición/importación anteriores y rechazo sin mutaciones; comparación diferencial y verificador independiente tras checks propios. Sin cambio de API/exportación de forma, derechos, estado de salud ni permisos.
- RED observado: PATCH titular con parentesco vacío devuelve 400 por el guard anterior. GREEN tras cambiar sólo la condición y su mensaje para clasificaciones sin titular. API confirma FK, clasificación vacía, revisión/historial, sin efectos de salud/derechos; se agregaron regresiones de clasificación posterior, desvinculación, ciclos, aislamiento, revisión, escritor legacy y XLSX v2/exportación. Un fixture de exportación omitía columnas obligatorias y devolvió 400; se corrigió el fixture, no el contrato de exportación.
- Runner de L14: 115 tests OK, 26.472 s. El traceback de auditoría no disponible pertenece a un fallo simulado en los tests de exportación; la suite terminó correctamente. `git diff --check` sin errores. Verificación independiente pendiente; sin navegador, CI ni publicación.
- Verificador `family_contract_verify` (`gpt-6.1-sol/medium`): 115 tests OK (25.551 s), 14 observaciones de interfaces previas equivalentes al baseline `212bc73`, dos probes de concurrencia con parentesco vacío aprobados; sin bloqueantes. Probes integrados en `test_concurrencia_padron130.py` manteniendo también las variantes clasificadas. Repetición padre: 117 tests OK, 26.547 s. La diferencia intencional es aceptar vínculo pendiente y actualizar el mensaje del parentesco sin titular.
- Scratch adicional retenido por política de limpieza ya registrada: `C:/Users/Juanito/AppData/Local/Temp/ostel_t1c_verify_f49py1mu`. No se intentó eliminarlo por otra vía. Sin datos reales. Browser no ejecutado, sin cambios frontend; no equivale a demostración o aceptación. Revisión nativa de este candidato todavía pendiente.
- Regresión adicional de los cortes ya entregados: `python -B manage.py test apps.financiadores.test_ostel_importacion apps.financiadores.test_codpar_ostel apps.financiadores.test_codpar_importacion --settings=config.settings_financiadores_postgres_test --noinput --keepdb --verbosity 0`: 40 tests OK, 7.125 s. No se modificaron migraciones ni esquema. Corte T1c parte de `212bc739`; límites locales conservados para futura cadena, sin publicar.

### L15 — Revisión T1c consentida y cerrada (30/10/2026)

1

- Aprueba revisar T1c, no publicar. Commit `0e2eb4079447c83e585de9af5b2f5e208d0310fc`: 225 adiciones + 5 eliminaciones, cinco archivos. Capturas nativas concurrentes de riesgo y confiabilidad inspeccionaron los cinco parches inmutables sin hallazgos; no ejecutaron tests nuevos.
- Acuse exacto confirmado por `gentle-ai.review-acknowledged/v1`: `action=acknowledged`, `authority=burned`, lineage `review-40d66b2863de36d4`, target `sha256:72845de51ff77c4e440697e17a35891b306a51ba3f83f735ac36f8f3cc88145d`. No reabrir este candidato. T1b mantiene su decisión independiente de omisión.
- Main remoto revalidado en `cae9e16a80559a1c936dc9e2f8727aa3bf3ad3d7`; sin rebase ni reset. Próxima unidad T1d: ensamblado seguro por CUILTIT, sin equivalencias de CODPAR inventadas ni cambios de derechos. #181 releído completo y su comentario vigente confirma disponibilidad de CUILTIT/diccionario; no se vuelve a bloquear por ausencia histórica.

### L16 — T1d: propuesta y confirmación familiar desde lote aplicado

- Mapa `ostel_family_batch_map` (`gpt-6-luna/high`): la aplicación administrativa procesa hasta 100 filas por llamada. Cambiarla para vincular durante cada tanda acoplaría familia al orden. Se mantiene ese circuito; nuevo paso explícito consulta la evidencia del lote completo y confirma un vínculo por vez mediante API. La integración visual será posterior, no se declara flujo operativo completo.
- La propuesta usa sólo filas aplicadas del mismo lote/financiador: CUIL original del integrante → CUILTIT → CUIL original único del titular, cuya propia referencia debe ser autorreferencia. Titular ausente, pendiente de aplicar, duplicado, ciclo, estructura multinivel, baja o identidad actual discordante requieren revisión sin mutaciones. No buscar una persona de otro financiador, usar NROAFI/NROREF ni aceptar coincidencias estadísticas. Un titular no presente en este lote queda para revisión; no se presume su rol desde un CUIL aislado del padrón.
- Confirmación con ID del titular esperado y revisiones de ambos afiliados; revalidar fuente y estado bajo locks lote → financiador → afiliados por PK. Reutilizar `editar_ficha`/historial. No reemplazar otro titular existente, no deshacer una raíz ni borrar clasificación previamente informada. Un vínculo ya coincidente es idempotente. CODPAR, salud, cobertura y el JSON original del lote permanecen intactos.
- Ruta inline tras mapa necesario para decidir la costura. Risk: items 1 (vínculos persistidos), 3 (nueva operación sobre estado compartido), 4 (locks/revisiones). Pruebas primero en API pública: orden invertido, dependencia fuera de tanda de 100, propuesta sin efectos, confirmación auditada, conflictos/rechazos con huella intacta e idempotencia. Verificador independiente tras checks propios. Runner focal `apps.financiadores.test_familia_ostel`; regresiones `test_ostel_importacion`, `test_familia_pendiente`, `test_padron130`, `test_concurrencia_padron130`, `test_codpar_importacion`, con settings PostgreSQL aislados de L14.
- Corte previsto 300–400 líneas de comportamiento/pruebas/documentación; la claridad y cobertura prevalecen sobre la estimación. Sin migración, dependencias ni frontend en este corte. Sin backfill, carga real, reactivación, derechos, publicación o cierre de #181.

- RED observado: GET del recurso nuevo devolvía 404. GREEN focal: 7 tests OK (9.682 s); regresión serial de L16: 99 tests OK (30.296 s). Se corrigió una inserción de assertions mal ubicada en el archivo de pruebas, sin cambio de comportamiento. OpenAPI distingue parámetros GET del cuerpo POST. `git diff --check` sin errores.
- Verificador `family_lot_verify` (`gpt-6.1-sol/medium`): 99 tests OK (28.292 s), cinco probes OK (3.245 s), ocho observaciones públicas previas idénticas al baseline `e5e55ad` tras normalizar timestamps. Confirmaciones concurrentes 200/409, una sola historia; cambios de identidad de ambas personas y fuente durante espera rechazados sin mutaciones. Generación OpenAPI correcta. Sin bloqueantes; primer fallo de su harness por Client se corrigió a APIClient, sin cambio del candidato.
- Probes incorporados como regresiones y fixture compartido, sin comprimir el código. Repetición padre: 12 tests focales OK (9.981 s); runner final de L16 más `apps.financiadores.test_concurrencia_familia_ostel`: 104 tests OK (32.913 s). Scratch retenido por la restricción de limpieza: `C:/Users/Juanito/AppData/Local/Temp/ostel_t1d_verify_4981ofuy`. El contenedor de pruebas sigue disponible; no se reintentó eliminarlo.
- Corte T1d sobre `e5e55ad`, posterior a T1c: API, pruebas y documentación forman una sola conducta revisable. La incorporación de regresiones concurrentes supera la estimación de 400 líneas; separar pruebas del vínculo dejaría un corte sin evidencia propia. Se conserva este corte cohesivo y se recomienda `size:exception` si se autoriza su futura PR; no se publica ni se presume esa excepción concedida. Cadena elegida sin cambios. Revisión nativa pendiente; sin navegador, CI, merge, deploy ni aceptación humana.

### L17 — Revisión T1d omitida por decisión del usuario (30/10/2026)

2

- Selección «Omitir esta vez»: ejecución exacta confirmada con `action=declined`, `consent=declined_this_candidate`, target `sha256:65c20db82a5814c766c904aad31448ea7e375c3b2c5a13e711927c0f78a63c9f`. Sin revisión nativa ni registro de aprobación; las revisiones futuras siguen habilitadas. Se conserva la prueba funcional e independiente de L16.
- Corte local `476cfb245c73581577f34c952b50df9519412ed5`: 455 adiciones + 1 eliminación, seis archivos, base `e5e55ad`. Sin publicación. Próxima unidad: mapear la integración visual con el circuito de importación existente y comprobar disponibilidad del entorno antes de cambios de UI.

### L18 — Preparación de integración visual, entorno pendiente

- Cierre documental `7459562`: evaluación nativa pasiva, sin revisión debida. Mapa de `family_ui_map` (`gpt-6-luna/high`) y spot check: `ImportacionAdministrativa.jsx` ya ofrece acciones por fila aplicada; reutilizar esa costura para propuesta y confirmación explícita, sin modificar la importación administrativa. Mostrar contexto de integrante/titular por nombre y número interno, sin ampliar exposición de CUIL/CODPAR.
- `frontend/node_modules` ausente; existe `frontend/package-lock.json`, runners Vite/Playwright. La configuración E2E general presupone una demo sembrada y dos servidores: no ejecutarla ciegamente ni usar `seed_volumen --rehacer` sobre una base existente. No se instalaron paquetes, iniciaron servidores ni modificó UI.
- Se requiere autorización concreta para instalar las dependencias ya fijadas (sin agregar ni actualizar), iniciar frontend/backend sólo en loopback con la base PostgreSQL descartable autorizada y fixtures ficticios, y verificar escritorio/móvil/teclado. No usar `.env`, datos reales ni servicios externos. Hasta entonces, T1 visual pendiente por entorno; no afirmar validación browser ni aceptación.

### L19 — Entorno visual autorizado e integración T1e

autorizo

- Autoriza el entorno descrito en S12/L18. Instalación delegada acotada `ui_dependencies`: `npm ci --ignore-scripts --no-audit --no-fund` completada; hashes de manifiesto/lockfile intactos, Vite 5.4.21 y módulo Playwright disponibles. No se ejecutaron scripts de instalación. PostgreSQL dedicado existente, fixtures propios sin datos reales; no usar la siembra general ni credenciales existentes.
- T1e inline: acción por fila aplicada → diálogo de propuesta → confirmación explícita. Reutilizar Modal/Button, API autenticada y callback de actualización. El servidor decide el vínculo; la UI no interpreta CUILTIT/CODPAR. Ante conflicto o respuesta perdida se invalida la propuesta y se exige consultar otra antes de confirmar; nunca afirmar rollback ni reintentar escritura automáticamente.
- Diseño: operador administrativo que revisa integrante, titular y procedencia antes de vincular. Mantener tipografía, superficies, borde sutil, acento y espaciado del modal existente; no rediseñar el padrón. Datos y revisiones primero, advertencia de clasificación/cobertura después, acción explícita al final. No agregar identificadores personales al diálogo; nombre/número interno tomados de la misma evidencia aplicada.
- Runner público real: Playwright con API/Django/PostgreSQL aislados; pruebas focales de confirmación, cancelación, revisión obsoleta, respuesta perdida, móvil/teclado y regresión del detalle aplicado. Observar RED antes de UI. Risk: items 1/3/4 (confirma estado compartido con solicitudes asíncronas); verificación independiente al final. Sin cambios de contrato backend, homologación, permisos, derechos o dependencias.
- RED observado en navegador real: no existe el botón «Vincular familia» después de importar y consultar detalle. Primera implementación reprodujo pérdida del foco al cerrar: deshabilitar el disparador antes del montaje hacía que Modal capturara un foco incorrecto; se mantiene enfocable sólo ese disparador bajo el diálogo, sin cambiar el Modal compartido. Un selector de prueba ambiguo entre dos estados transitorios se acotó al mensaje de confirmación. GREEN: cuatro recorridos reales OK (8.7 s), desktop/móvil, conflicto 409, pérdida de respuesta después del commit y recuperación idempotente.
- Entorno autorizado iniciado sólo en loopback: frontend `http://127.0.0.1:5189`, API `http://127.0.0.1:8232`, PostgreSQL existente puerto 63214/base dedicada. Migraciones aplicadas a la base descartable, no a una base operativa. Fixture en temporal `ostel-familia-ui-fe94fcc46ab5499f9f2a7ece7d441268`, sin imprimir credenciales; ventana Chromium visible con propuesta ficticia sin confirmar, captura del diálogo inspeccionada. Build y verificación independiente pendientes; no publicación ni aceptación humana.
- Verificador `family_ui_verify` (`gpt-6.1-sol/medium`): build OK (4.06 s), cuatro recorridos familiares reales OK (11.1 s), cuatro regresiones de importación en baseline `7459562` OK (44.2 s) y en candidato OK (41.8 s). Dos probes adicionales aprobados: cuerpo POST igual a la propuesta/fuente, bloqueo durante petición y descarte tras 403, consulta pendiente y nueva apertura. 403 inyectado: prueba de UI, no de revocación real. Sin bloqueantes.
- Incorporados ambos probes. Repetición padre final: seis recorridos OK (11.9 s). Un intento intermedio falló al cerrar el contexto antes del segundo GET de StrictMode; el teardown ahora espera handlers pendientes, sin ocultar errores. La prueba de revisión modifica efectivamente el contacto incluso al repetir la fixture. `git diff --check` OK; manifiesto y lockfile de dependencias sin cambios. Scratch del verificador `ostel_t1e_verify_8mc80mwr` y fixtures ficticios retenidos; sus servidores 5191/5192 detenidos, entorno visible 5189/8232 intacto.
- Unidad T1e sobre `7459562`: UI + pruebas reales + documentación. Rollback: retirar FamiliaFilaOstel y su acción de ImportacionAdministrativa, el spec/fixture nuevos y su entrada testMatch; conservar API T1d y vínculos/auditoría existentes. El corte cohesivo ronda 400 líneas, sin separar sus pruebas ni comprimirlas; si excede el límite de una futura PR, se recomienda `size:exception`, no concedida por esta implementación local. Revisión nativa pendiente, sin publicación ni aceptación humana.

### L20 — Revisión T1e y límite de la continuación (02/11/2026)

1

- La primera selección autorizó la revisión de T1e. Las cuatro capturas nativas concluyeron en `correction_required`; no se obtuvo aprobación ni detalle accionable de la corrección. La continuación exacta solicitó nuevamente la selección de archivos no versionados previamente excluidos y emitió una presentación sin los selectores del candidato y su linaje.

1

- La segunda selección autorizó reportar y continuar. Ocurrencia registrada una sola vez en [Gentle AI #5424](https://github.com/Gentleman-Programming/gentle-ai/issues/5424#issuecomment-6578919606), sin datos privados ni cambios de etiquetas. El consentimiento exacto de omisión devolvió `declined_this_candidate` para T1e, pero STATUS conservó la autoridad original en `correction_required`. No se interpreta como aprobación, cierre ni descarte de los hallazgos.
- No repetir el reporte, la omisión ni reconstruir parámetros de recuperación. La continuación de esa revisión requiere una corrección publicada o una recuperación nativa documentada; no se modificó la configuración global. Las pruebas funcionales e independientes de L19 se conservan como evidencia local separada.
- Tras el reinicio, HEAD `f72c89bec3540ff9bd22ac1274d4819376ca04ce` y archivos versionados intactos; `.atl/` preexistente fuera del candidato. Los servidores 5189/8232 estaban detenidos. No se reinstalaron dependencias ni se repitieron pruebas, cargas o demostraciones.

### L21 — Continuidad autorizada y contrato pendiente de #143 (02/11/2026)

sigue sin eso

- Se continúa el trabajo local sin esperar la revisión T1e; permanece documentada, no aprobada. Mapa delegado `ostel_next_unit_map` (`gpt-6-luna/high`) por necesidad de reconciliar requisitos y costuras antes de decidir. Leyó íntegros #141/#181/#142/#143 y sus comentarios; CodeGraph sincronizado antes de explorar. Sin escrituras ni ejecución de pruebas por el explorador. Main remoto continúa en `cae9e16a80559a1c936dc9e2f8727aa3bf3ad3d7`; no hubo rebase ni cambios de tablero.
- T1a–T1e cubren el contrato familiar autorizado hasta ahora, no la aceptación completa de #181/#142 ni una homologación de parentescos. CUILTIT/diccionario disponibles, vínculo explícito desde evidencia aplicada, clasificación pendiente y CODPAR protegido siguen separados de los derechos. La secuencia siguiente es #143 → #183.
- [#143](https://github.com/Mkdir-arg/SistemaDeSalud/issues/143) es un análisis: exige acordar decisiones materiales antes de implementar. Sus referencias al material recibido no acreditan vigencia normativa ni aprobación de las propuestas. La mención de tres meses no se convierte en una constante de negocio.

#### Matriz para validación de OSTEL — no ejecutable ni aprobada

| Situación que debe resolverse | Evidencia necesaria | Decisión pendiente | Ejemplo de límite por acordar |
| --- | --- | --- | --- |
| Alta administrativa / trámite | Estado documentado, fuente y fechas | Inicio de derechos y prestaciones permitidas por estado | Evaluar antes, en y después de la fecha aprobada |
| Cese, falta de aportes, despido o renuncia | Causal confirmada y evidencia de aporte/cese | Inicio, duración y calendario de gracia; continuidad y excepciones | Último día con derechos y primer día sin ellos |
| Desempleo | Inicio y fin acreditados del subsidio | Relación entre subsidio y derechos del titular/familia | Fin del subsidio y documentación recibida tarde |
| Edad de familiar, certificado o CUD | Tipo, vigencia y validación de evidencia protegida | Efecto del vencimiento, tolerancias y responsable | Vencimiento frente a renovación pendiente |
| Mora de superador | Aporte de ley y deuda diferencial discriminados | Condiciones para pasar al plan base; conservar derechos que correspondan | Diferencial impago con aporte acreditado |
| Mora privada/adherente | Deuda, avisos y constancia de notificación | Avisos, tolerancias y eventual suspensión/corte | Pago o comprobante recibido junto al vencimiento |
| Opción de otra OS, fallecimiento o decisión judicial | Fuente competente, fecha y alcance de la causal | Fecha efectiva, excepciones y tratamiento de integrantes | Orden judicial vigente frente a otro evento de baja |

- Cada regla acordada deberá identificar régimen/plan, fecha de evaluación, fuente/versionado, evidencia, acción permitida, excepción, quién confirma/revierte y política ante decisiones concurrentes. Ninguna fila habilita por sí sola una transición.
- Reutilización a preservar: `afiliados_vigentes` para vigencia compartida; `seleccionar_afiliacion` para nuevas selecciones con guards y locks; historial/revisión existentes para cambios confirmados. La selección actual comprueba habilitación explícita, inicio/finalización, financiador/plan y convenio. No equivale a un motor normativo de gracia o mora.
- Invariantes: no derivar un corte de FECVTO, ausencia en lote, código de parentesco o registro administrativo; no reescribir prestaciones, reservas, autorizaciones, cargos ni selecciones históricas. No confundir deuda diferencial con mora privada. No agregar permisos ni datos sensibles a interfaces generales.
- Próxima decisión concreta: identificar la fuente vigente validada por OSTEL para completar esta matriz. Después se podrá elegir la primera regla y sus ejemplos públicos deterministas. Regresiones a conservar: `test_cobertura.py` y `test_habilitacion_cobertura.py`; runner y RED se fijarán con el comportamiento aprobado, no se inventan ahora.
- Esta unidad sólo actualiza el seguimiento y el análisis. RED/GREEN, DB, navegador y pruebas funcionales no aplican porque no cambia comportamiento. Verificación proporcional: readback, espejo completo y `git diff --check`. Sin aceptación humana de la matriz ni implementación de derechos. Rollback: retirar S13 y las actualizaciones de estado/L20–L21 de este documento, sin alterar código, datos o evidencia previa.

### L22 — Parametrización autorizada (02/11/2026)

ya fue solicitado esa informacion a ostel. apruebo tu propuesta para parametrizacion. avanza con lo que puedas sin la respuesta de ostel

no, sos gpt-6.1-sol, cambie de decision

- Baseline/rama verificados; sólo `.atl/` preexistente. Espejo completo #309 y archivo idénticos tras normalizar CRLF. #141/#143 y comentarios releídos íntegros. Mapa `parametrizacion_map` y spot check: `Afiliado.regimen` sí tiene catálogo en models.py:190; no introducir catálogo nuevo ni importar ORM para este corte puro.
- T2a: descriptor inmutable de versión/fuente/ámbito y vigencia técnica [desde,hasta), consulta pura de coincidencias, conflicto explícito sin elegir ganador. Régimen como clave literal del llamador; plan opcional abarca todos los planes. No verifica existencia/pertenencia en DB ni concede acceso. No es fecha de corte prestacional.
- Interfaz de prueba autorizada por el alcance: constructor del borrador y `previsualizar_borradores`; ejemplos exclusivamente ficticios. RED→GREEN por regla; regresión pura OSTEL. No se cambian consumidores previos: diferencial de comandos compartidos no aplica. Sin persistencia/API/UI, plazos normativos, causas/acciones de derechos, auditoría operativa ni activación. Esas etapas quedan pendientes, no opcionales.
- Estimación 250 líneas; cadena `feature-branch-chain` conservada. Rollback: retirar módulo/pruebas/entrada documental nuevos. Risk: none; sin helpers compartidos cambiados.

- RED observado: módulo inexistente; luego validación ausente aceptaba nueve descriptores inválidos, consulta pendiente lanzaba NotImplementedError y consultas inválidas vacías no fallaban. GREEN final: cinco tests focales y 27 tests puros combinados OK (3.017 s). `git diff --check` OK. Ningún consumidor anterior comparte el módulo nuevo; no hay diferencial pendiente de comandos previos. Sin DB, browser (no UI), CI ni aceptación normativa.
- Espejo #309: servidor truncó actualización al superar 50.000 bytes; se restauró inmediatamente la versión íntegra anterior de 47.950 bytes. Archivo local completo conservado; espejo actualizado PENDIENTE por límite del proveedor. Observación T2a separada conserva recuperación del progreso, no sustituye espejo completo. Sin pérdida silenciosa ni duplicación de documento local.

- Commit T2a `3a23cf132b28f0be841e10df54c7ba6fc1c8dd73`: 210 adiciones + 1 eliminación, cuatro archivos; unidad independiente, sin publicación. Evaluación inicial no disponible por inventario no versionado; preflight con lentes rechazado, preflight sin lentes obtuvo inventario. Repetición explícita de assess excluyendo `.atl/` con hash confirmado: medium, `review_due=false`, `under_budget` (211 líneas). No START, consentimiento ni aprobación; límite pendiente de este corte permanece `5b82a21`, sin reabrir T1e ni tocar su autoridad.
- T2a cubre S14 sólo en estructura/versionado/consulta técnica; T2/#143 y reglas operativas siguen pendientes de validación normativa. No hay incumplimiento de pruebas funcionales requeridas del corte; no hay verificador independiente porque ningún ítem de alto riesgo se modifica. El espejo actualizado sigue pendiente por capacidad; archivo local es la autoridad de continuidad junto a observación #620.

### L23 — Continuación: comparar propuestas sin reescribir historia (02/11/2026)

continua

- Archivo actual y evidencia #620 reconciliados con HEAD `5d3b30a`; espejo #309 permanece completo pero anterior a L22 por límite de capacidad, no se declara sincronizado. Se conserva esa divergencia conocida y todo el historial local.
- T2b inline: nueva función pura `comparar_borradores` en módulo separado. Recibe historial/propuesta completa y contexto ficticio explícito; valida versiones únicas por ámbito/código, conserva descriptores previos idénticos, admite sólo números nuevos mayores al máximo anterior de la misma clave y devuelve nuevas versiones + consulta antes/después reutilizando `previsualizar_borradores`. No elige precedencia ni resuelve superposiciones.
- El financiador del contexto debe coincidir con todos los descriptores suministrados; esto valida entradas, no autentica ni consulta pertenencia de planes. Ningún dato se persiste. Sin permisos/API/UI, constantes médicas, activación ni modificaciones del motor existente. Frontera de pruebas: función pública nueva, ejemplos sintéticos, RED→GREEN; pruebas previas de consulta como regresión. No se cambia código compartido previo: diferencial de comandos previo no aplica.
- Estimación 180–230 líneas con tests/docs. Cadena elegida sin cambios; rollback sólo módulo/pruebas y sección documental T2b. Sin nuevo motivo de delegación: corte entendido/contenido; no escribe en motores ni contratos existentes. Risk: none.

- RED: módulo nuevo ausente, luego cinco casos de borrado/reescritura aceptados, después duplicados/versión decreciente/financiador ajeno aceptados. GREEN: cinco tests focales y 32 combinados OK (3.114 s), sin cambios en inputs; solapamiento permanece conflicto y no recorta fechas. Ningún código previo modificado: se reusa consulta T2a por importación. `git diff --check` OK.
- La propuesta sólo valida las instantáneas entregadas; omisión en ambas no detectable sin repositorio persistido. No acredita integridad durable, auditoría, aprobación ni impacto en personas. Espejo actualizado pendiente por capacidad, sin reintentar escritura truncada. No browser (sin UI), DB ni CI requeridos por el módulo puro; no se acredita despliegue/aceptación.

- Commit T2b `317269865c043a935f571798cf6e3465c3df9aef`: 173 adiciones, cuatro archivos, sin edición de código T2a. Evaluación de la porción pendiente `5b82a21..3172698`: medium, `review_due=false`, `under_budget`, 387 líneas; no START ni aprobación nativa. Límite pendiente conservado. Seguimiento completo local, espejo actualizado pendiente; observación #624 permite recuperar T2b. Sin publicación ni aceptación de reglas operativas.

### L24 — Continuación: persistencia no operativa de borradores (02/11/2026)

continua

- Baseline `c6debba1ec8a2a9ea43d63cd25d5764a845114ff`, sólo `.atl/` preexistente. #141/#143 releídos completos, mapa `draft_storage_map` y spot check. Corrección al mapa: el catálogo de régimen sí existe en Afiliado.regimen, se reutiliza sin nuevo enum. Archivo actual/#624 reconciliados; espejo #309 continúa anterior por capacidad, sin truncar ni afirmar sincronización.
- T2c inline: modelo tipado aditivo de versión/fuente/ámbito/fechas/autor/motivo; servicio de consulta y guardado de propuesta completa. Reusar `requerir_financiador`, `auditar` y `comparar_borradores`; historial real cargado desde DB dentro de transacción, lock financiador y planes referenciados, sin cambios en escritores previos. Reservar escritura a admin como configuración; consulta bajo guard existente. No API/admin/UI ni activación, campos arbitrarios, derechos o datos reales.
- Lock por financiador: más simple que agregar anclas por ámbito, pero serializa propuestas no relacionadas de la misma organización. Validar existencia/pertenencia de planes, catálogo de régimen y longitudes. Identidad única incluso con plan nulo; motivo/autor obligatorios y evento atómico por versión nueva. Ningún escritor de edición/borrado de versiones en este servicio.
- Pruebas públicas de servicios de consulta/guardado, fixtures ficticios: persistencia, rechazo sin cambios, historia conservada, roles/aislamiento, rollback si falla auditoría y concurrencia en PostgreSQL. Migración aditiva sin backfill; verificador independiente después de checks propios por ítems 1 (formato persistido), 2 (guard), 4 (serialización). Risk: items 1/2/4.
- Contenedor dedicado anterior detenido; inicio necesario dentro del alcance ya autorizado. Puerto efímero actual verificado `127.0.0.1:50152`, no usar 63214 histórico. Sin lectura de .env/credenciales. Runner: `python -B manage.py test apps.financiadores.test_borradores_derechos --settings=config.settings_financiadores_postgres_test --noinput --keepdb --verbosity 1`, con PYTHON_DOTENV_DISABLED=1 y URL local explícita de la base ficticia autorizada.
- Corte coherente estimado 350–450 líneas con migración/tests/docs; cadena feature-branch-chain ya elegida. Antes de su commit se debe cerrar la porción pendiente T2a/T2b según revisión nativa. Rollback: retirar servicio/modelo/tabla nuevos sólo en base ficticia; no tocar datos ni motores previos.

- RED de servicio ausente; GREEN inicial persistencia/consulta idempotente. RED de consulta con booleano y guard inconsistente; corrección acotada valida IDs antes de guards en ambos servicios. Focal final siete tests OK (1.258 s), incluye dos carreras PostgreSQL reales. Regresión padre: 68 tests OK (12.738 s), incluidos cobertura/habilitación; trazas de fallos de captura corresponden a errores simulados existentes y la suite termina OK. Dry-run de migraciones sin cambios faltantes; diff --check OK. Verificación independiente pendiente.

- Verificador `draft_storage_verify` (gpt-6.1-sol/medium): PASS acotado S5/S8/S14, sin bloqueantes; 68 tests OK (13.297 s), migraciones dryclean, tres probes OK (1.728 s) y diferencial público puro contra `c6debba` con stdout/stderr/exit iguales. Probes: huella intacta tras rechazo/constraint de plan nulo, revocación mientras espera lock, 0017→0018 conserva filas previas. Scratch retenido `C:/Users/Juanito/AppData/Local/Temp/ostel_t2c_verify_vx47_fyj`, sin reintentar limpieza.
- Probes incorporados como `test_borradores_integridad.py`; spot check y regresión padre finales: 71 tests OK (13.775 s). Ningún fallo requerido pendiente. Sin navegador por no cambiar UI, sin CI/despliegue/aceptación normativa. Espejo actualizado pendiente por capacidad; observación #636 conserva recuperación de T2c.
- Límites locales: porción pura T2a/T2b pendiente `5b82a21..c6debba`, medium/under_budget; persistencia T2c usa `c6debba` como base independiente por ítems 1/2/4, sin acumularla en su candidato. La porción previa no se declara aprobada ni consumida. `.atl/` y futuros cortes ajenos no son parte de T2c; no se toca autoridad T1e.

- T2c commit `85214f4cabbee400461532c22e04046942937a4d`, 411 adiciones (37 generadas por migración; 374 autoradas), siete archivos. Corte cohesivo con pruebas/migración/docs, cadena elegida conservada, sin publicación. Evaluación previa pura actualizada: medium/under_budget, 389 líneas. T2c evaluado aisladamente contra `c6debba`, high por ítem 1 explícito (y verificación independiente 1/2/4), `review_due=true`.
- Preflight exacto devuelto por assess con cuatro lentes pertinentes rechazó por selección no versionada pendiente. Repetición permitida sin lentes devuelve collect intended_untracked_selection_required para `.atl/`; su submission carece nuevamente de base-ref/committed-only y ofrece schema_bound_json sin captura ejecutable disponible. No reconstruir selectores/JSON ni ejecutar contra otro candidato. No START, linaje ni consentimiento v3 obtenido; no existe invocación exacta de omisión para este candidato. Target observado `sha256:52daaa97c044d6641d8e617f30762ca4ea35b3fc37160065a9c2c333eace637b`.
- Revisión nativa pendiente, no aprobada; no repetir reporte/decline de T1e ni desactivar globalmente. Próxima decisión: dejar explícitamente T2c sin revisión nativa para continuar desarrollo local, o esperar recuperación nativa publicada/documentada. Prueba funcional e independiente completa; no se altera derecho alguno por esta decisión. Espejo actualizado pendiente por límite de capacidad.

### L25 — T2c sin revisión nativa y API administrativa (02/11/2026)

autorizo

- Responde exactamente a dejar T2c sin revisión nativa y continuar localmente. Sólo ese corte; no aprobación nativa ni cambio global. Sin START/consent v3 no existe comando exacto de decline: no se fabrica ni se reusa T1e. Siguiente candidato conserva revisión propia. Baseline `fe2b2db`, sólo `.atl/` preexistente; archivo actual y #636 reconciliados, espejo #309 sigue anterior por capacidad.
- T2d inline: acción GET/POST `borradores-derechos` del FinanciadorViewSet mediante mixin nuevo; organización/guards y servicios T2c existentes. GET devuelve descriptores; POST propuesta completa + motivo/contexto devuelve nuevas/antes/después de guardar sólo borradores. Financiador determinado por URL, campos desconocidos rechazados en cada nivel. No aprobar ni activar reglas; sin UI, schemas/deps nuevas, lógica de plazos o modificaciones de permisos.
- Frontera RED→GREEN: HTTP autenticado vía APIClient, endpoints reales. Casos: guardar/consultar/idempotencia, operador/auditor sólo lectura, ajenos/inactivos, campos arbitrarios/financiador embebido, fechas/plan inválidos, historia incompleta sin mutaciones. Reusar el servicio y esquema de errores de CoberturaBaseViewSet; no replicar persistencia/locks/auditoría. Riesgo ítem 2 por nueva superficie autenticada; verificador independiente al final. Risk: item 2.
- Estimación 300 líneas con tests/docs. Sin cambios de contratos previos: sólo nueva acción/import/mixin; diferencial de respuestas previas al verificar. Runner PostgreSQL ficticio de L24, suite `test_borradores_api` más servicios/integridad/cobertura. Espejo pendiente conocido; no truncar.

- RED HTTP observado: GET nuevo devuelve 404. GREEN: cuatro tests API OK (0.412 s), incluidos campos desconocidos/booleanos, auditoría idempotente, historia, roles y aislamiento. Servicio/guards previos intactos. No se creó UI ni se afirma browser E2E; ausencia de staticfiles es advertencia preexistente, sin generar archivos. Verificación independiente y regresión final pendientes.

- Verificador `draft_storage_verify` sobre scratch nuevo `C:/Users/Juanito/AppData/Local/Temp/ostel_t2d_verify_k5rppn34`: PASS S5/S14 sin bloqueantes, 75 tests OK (14.716 s), tres probes OK (1.250 s), 15 observaciones HTTP previas idénticas frente a `fe2b2db` (normalizada sólo duración). Primer fallo fue del harness diferencial corregido sólo en scratch. Probes cubren identidad/autor/rol embebidos, 405 sin cambios y revocación durante POST en espera. Sin DB/servicios externos ni edición del workspace. Scratch retenido, sin limpieza por vía alternativa.
- Probes incorporados en test_borradores_api_seguridad.py. OpenAPI de GET/POST y request/response presente; no se escribió esquema generado en el workspace. Padre verificó antes 75 tests OK (12.344 s). Repetición final con probes pendiente; Risk: item 2.

- Final padre con probes: 78 tests OK (14.654 s), diff --check sin errores. Sin bloqueantes funcionales/independientes. Se conserva sólo `.atl/` fuera de cambios autorizados. Risk: item 2 (superficie HTTP autenticada nueva), sin modificar guards ni servicios; revisión nativa de T2d no cubierta por omisión T2c.

- T2d commit `ecd5f90e6201505d9a8d7d2dc89bfbd2d5cca667`: 282 adiciones + 1 eliminación, seis archivos. Evaluación aislada contra `fe2b2db`: high por ítem 2 explícito, review_due=true. El preflight exacto devuelto con lentes riesgo/legibilidad/confiabilidad vuelve a fallar por selección de no versionados. Reentrada permitida sin lentes retorna collect para `.atl/`, submission sin selectores base-ref/committed-only y captura externa no ejecutable aquí. Target `sha256:fe37afa7b1fcb695362592a246ff9ee283dbcb798efc358d64bfefe1c009d55b`; no START, linaje ni consentimiento v3.
- Revisión de T2d no iniciada ni aprobada; no se fabrica JSON de captura, comando de omisión ni restauración nativa. La autorización de omisión T2c sigue limitada a ese corte. Próxima decisión: dejar explícitamente T2d sin revisión nativa para continuar localmente o esperar recuperación publicada/documentada. Sin nuevo reporte, toggles, publicación ni cambios de derechos. Seguimiento local completo; espejo actualizado sigue pendiente por capacidad.

### L26 — T2d sin revisión nativa y UI de borradores (02/11/2026)

autorizo

- Sólo T2d queda explícitamente sin revisión nativa; no aprobación ni configuración global modificada. Sin START/v3 no se inventa decline. HEAD `845d06d`, sólo `.atl/`; archivo y #644 reconciliados, espejo completo aún pendiente por límite del proveedor.
- Mapa `draft_ui_map`, spot check: integrar sección dedicada en menú/portal, no dentro de reglas vigentes; reutilizar api/rutaFinanciador/opcionesFinanciador, REGIMENES y Field/Input/Select/Button/Card. Escritura inline; ninguna razón para escritor delegado. Datos remotos con react-query ya instalado, clave usuario/financiador y componente keyed por ambos; respuesta vieja no cambia otra organización. No dependencias ni backend cambios.
- Humano: administración prepara versiones para validación posterior; operador/auditor consultan. Dominio: financiador, régimen, plan, fuente, versión, vigencia técnica. PLEXO existente: superficie clara, tinta, bordes sutiles, acento de marca y ámbar para límite no operativo. Firma: «No operativo» junto a versión y aviso permanente; sin KPIs genéricos, edición inline ni botón de activar. Lista y formulario; una columna móvil. Guardar no equivale a aprobar ni evaluar personas.
- T2e: listar y añadir descriptor mediante propuesta completa explícita; contexto/fechas/fuente/motivo controlados, sin plazos médicos. Rol del servidor decide permisos; UI no amplía grants. Bloquear doble envío; tras fallo/conflicto o respuesta perdida exigir consulta nueva, nunca reintentar POST automáticamente. No activar ni borrar historia ni mostrar autoría que el DTO no expone.
- RED→GREEN por interfaz real: login fixture y navegador desktop/móvil/teclado; guardado, sólo lectura, historia, respuesta perdida después de commit y cambio de organización con consulta en vuelo. Ficticios sólo en PostgreSQL dedicado loopback50152, frontend5189/backend8232. S12 autoriza entorno, sin .env, credenciales existentes ni siembra general. Verificador independiente por ítem 4 (orden de solicitudes/asíncronas y cambio de ámbito); backend locks/guards existentes sin tocar. Risk: item 4.
- Estimación 350–450 líneas con fixture/pruebas/docs; cadena elegida conservada. Runner nuevo focal reutiliza config real existente sin otras suites/fixtures; temporales fuera del worktree retenidos. Mostrar navegador visible antes de entrega; no equivale a aceptación.

- Entorno autorizado: migraciones sobre salud_financiadores_test descartable y fixture ostel-borradores-ui-9f2fc9781cfa4c6a993569c4cced9a6c; backend8232 (sesión69353), frontend5189 (sesión65508), sólo loopback. Credenciales ficticias sólo en manifiesto externo, no mostradas. RED real: título de pantalla ausente; GREEN inicial. Timeout posterior fue selector exacto de label implícito de select (incluía options): árbol accesible tenía nombre correcto; selector por rol combobox lo resolvió sin cambio UI. Una ejecución extensa se detuvo tras reproducir ese fallo de harness, no se presenta aprobada.
- Runner focal completo: seis recorridos reales OK (6.7 s), incluye guardar/reload/menú, auditor, móvil/teclado/sin overflow, pérdida de respuesta tras commit y consulta en vuelo al cambiar financiador. Se optimizó recarga independiente de planes/historia en paralelo antes de freeze. Build/verificador/inspección visible pendientes, sin aceptación de OSTEL.

- Verificador `draft_storage_verify` (gpt-6.1-sol/medium): PASS S5/S12/S14 sin bloqueantes. Build scratch OK (3.61 s), seis recorridos reales OK (8.2 s), dos probes de doble clic y 403/recarga fallida OK, diferencial visible planes/reglas/padrón idéntico a `845d06d` salvo enlace solicitado. Selector ambiguo role=status del probe se corrigió sólo en harness. Capturas desktop/móvil inspeccionadas, sin overflow; scratch retenido `C:/Users/Juanito/AppData/Local/Temp/ostel_t2e_verify_muoxy1jr`; servidores propios5191/5192 detenidos y padres5189/8232 preservados.
- Probes incorporados en spec real; 403/503 inyectados verifican UI, no revocación real de membresía (ya cubierta en backend T2d). Padre inspeccionó captura desktop; faltan spot check final y demostración visible. Sin cierre normativo ni revisión nativa de T2e.

- Spot check final padre: ocho recorridos reales OK (10.0 s), incluyendo probes incorporados; ninguna corrección productiva requerida por verificador. Capturas desktop/móvil inspeccionadas por padre. Chromium visible autenticado con fixture ficticia en `http://127.0.0.1:5189/financiadores/borradores?financiador=1`, formulario en blanco listo para probar; helper externo demo.mjs sesión11420. No datos reales ni credenciales expuestas; la demostración no es aceptación. Servidores padres5189/8232 quedan disponibles dentro de S12. Risk: item 4.

- T2e commit `ff3b803ef942972af6acf40a0b0d807ed06a18ef`: 353 adiciones + 1 eliminación, ocho archivos; corte cohesivo bajo 400 líneas, cadena elegida conservada. Evaluación aislada base `845d06d`: high por ítem 4 explícito, review_due=true. Preflight exacto con lentes pertinentes rechazó por selección de no versionados; repetición exacta sin lentes devuelve collect de `.atl/` con submission que vuelve a perder selectores base-ref/committed-only, sin captura ejecutable disponible. Target `sha256:dce32c5c055e25ab2befc0a05de62ae925ea2e38801b61081cc78b3fa3c274ea`; no START/linaje/consent v3 ni revisión aprobada.
- No trasladar omisión T2d a esta UI ni fabricar captura/decline/recuperación; no nuevo reporte ni toggle global. T2e funcionalmente verificado y demostrado local, revisión nativa pendiente: requiere decisión explícita de dejar este corte sin revisar o recuperación publicada/documentada. Sin publicación, CI, despliegue ni aceptación humana. Archivo completo local, espejo actualizado aún pendiente por capacidad del proveedor; observación #669 conserva reanudación.

### L27 — Nombre aprobado y objetivo funcional (02/11/2026)

me gusta tu propuesta. debe demostrar seguridad al desarrollo, debe estar hecho para funcionar

- Previa autorización «autorizo» deja sólo T2e sin revisión nativa; registrada en #669, no aprobación ni cambio global. Usuario preguntó por el nombre; código verificado: los registros actuales son descriptores versionados, no motor de gracia/mora/bajas. La nueva aprobación permite ajustar nombre/estado visibles, no activar políticas desconocidas.
- T2f inline: menú/título «Reglas de derechos», estado explícito «Borrador» por versión y explicación de que aún no decide derechos. Conservar rutas/API/modelos por compatibilidad, servicios y controles sin cambios. Pruebas HTTP/browser previas se conservan; RED→GREEN del nombre/estado, repetir recorrido real desktop/móvil/teclado. Sin nueva dependencia ni entorno. Risk: none; no lógica compartida nueva, únicamente denominaciones solicitadas.
- Criterio de avance del módulo existente: configuración controlada completa (hoy sólo metadatos), evaluación determinista con ejemplos/límites acordados, aprobación/activación autorizadas, auditoría e historia, verificación integrada de efectos y rechazos. Son garantías ya aprobadas en S14, no se declara el motor terminado por estos cambios visuales. La política ya fue solicitada a OSTEL; no pedirla otra vez ni inventar valores.

- RED real: encabezado «Reglas de derechos» ausente. GREEN: nombre en menú/título y estado Borrador verificados en los ocho recorridos reales (10.7 s), incluidos guardar/historia, desktop/móvil/teclado y pruebas de solicitudes previas sin cambiar lógica. Build OK (4.98 s) en temporal externo `ostel-nombre-build-a_lsliun`, sin eliminar contenido previo ni dependencias. diff --check OK. Ruta/contrato/guards/estado asíncrono no modificados; no verificador adicional porque no se toca ningún ítem de alto riesgo.

- Corte T2f `2211e0363d64ff2970f1704adcc90f888d648ed8`: 45 adiciones + 7 eliminaciones en cinco archivos. Evaluación nativa aislada base `1a3ec31`: medium, review_due=false, under_budget (52 líneas); sin START ni consentimiento requerido. Sólo T2e quedó sin revisar por autorización específica; esta evaluación no lo aprueba. Rutas y datos previos intactos, sólo `.atl/` fuera de commits. Sin CI/publicación/despliegue ni aceptación humana. Espejo completo actualizado aún pendiente por capacidad, archivo local completo y #669 conservan estado.

### L28 — Continuación: cálculo temporal explicable y no operativo (02/11/2026)

continua

- HEAD `36be68a`, sólo `.atl/`; seguimiento local reconciliado con L27/#669, espejo #309 pendiente por capacidad conocida. CodeGraph sincronizado antes de consulta de fecha_limite (sin resultados); no se deduce de eso ausencia global de helpers. Se reutiliza selección de borradores por ámbito/vigencia, sin tocarla.
- T2g inline: función pura pública `simular_plazo` recibe descriptor versionado, plazo explícito en días corridos, fecha de evaluación y referencia/evidencia informadas. Devuelve límite y posición antes/en/después, con copia inmutable de todos los insumos y la versión/fuente; no una habilitación o baja. No toma fecha del sistema ni infiere referencia de desde/FECVTO/ausencia. Sin evidencia suficiente, resultado explícito requiere_evidencia; ámbito/vigencia no coincidentes no calculan.
- Decisión técnica acotada, no normativa: primer mecanismo sólo aritmética de días corridos (incluido cero explícito), sin convertir meses legales a días, días hábiles ni elegir inclusividad prestacional. Devuelve igualdad como caso separado para no imponer ese límite de negocio. Parámetro por simulación, todavía no persistido ni parte de una regla activa. Nueva lógica/calendario requerirá otro corte; no hay motor arbitrario ni expresiones ejecutables.
- Frontera RED→GREEN: función pública, ejemplos ficticios antes/en/después, cero, fin de mes/año/bisiesto, evidencia ausente, ámbito/vigencia, tipos/rango rechazados e inmutabilidad. Runner puro con regresión de borradores/propuestas/escenarios OSTEL. Sin DB/API/UI ni cambios de contratos previos; no diferencial de comandos compartidos porque no se modifica implementación compartida. Risk: none; comprobación determinista posible.
- Estimación 200–260 líneas con tests/docs; cadena elegida conservada. Rollback retirar nuevo módulo/tests/sección de documentación; ningún consumidor operativo depende de ellos. No declarar completos parámetros normativos, activación, decisiones de derechos o el módulo integral.

- RED observado: módulo ausente; después evidencia incompleta calculaba/fallaba con TypeError y ámbito no coincidente calculaba; luego tipos inválidos/desbordes no se rechazaban de forma controlada. GREEN focal seis tests y final ocho casos de prueba; regresión combinada 40 tests OK (3.590 s), sin DB/reloj ni mutaciones. Fin de mes/año/bisiesto, cero y antes/en/después verificados con fechas literales independientes. Salida inmutable conserva descriptor/versión/insumos; variar plazo cambia cálculo sin cambiar código o resultado anterior.
- No hay consumidor API/UI ni derechos alterados; browser y DB no aplican a este módulo puro nuevo, no se repiten pruebas T2e. No hay contrato anterior modificado ni independiente requerido por riesgo. Verificación incluye readback/diff --check; no acredita política normativa, integración, CI o despliegue. Espejo actualizado sigue pendiente por capacidad; nuevo tópico de recuperación T2g conserva progreso sin sobrescribir otros cortes.
