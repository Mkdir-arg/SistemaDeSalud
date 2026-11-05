# Cierre de Autorizaciones

Objetivo: completar el plan de cierre sin inventar contratos clínicos ni duplicar saneamiento. Rama: `juanikitro/salud-cierre-autorizaciones-20261105`; base: `8a3a1d8b87a25380c85e15519fc0683f09ef6c49`.
Entrega: `ask-on-risk`, local, sin publicación/merge/deploy. Previsión: menos de 400 líneas autoras en el primer corte. Runners: API Django aislada SQLite/PostgreSQL y Playwright real de prescripciones, con entorno propio autorizado S6.

## Specs

- S1 — Objetivo exacto: «usa como objetivo el plan que me compartiste para cerrar autorizaciones. avanza hasta que te encuentres un bloqueante o necesites intervencion humana».
- S2 — Solicitud de planificación referida: «analiza lo que queda por hacer para cerrar el modulo y planifica su implementacion». El plan acordado comprende precisión documental y caracterización de prescripción con observación/reenvío; contrato mínimo; implementación de diferencias aprobadas; integración; aceptación y entrega separadas.
- S3 — Restricción vigente: «no toque saneamiento, eso lo hace otro agente». Sin inspeccionar ni modificar su checkout, repetir sus arreglos ni asumir sus resultados.
- S4 — Preservar S17–S21 ya aprobados: adjunto privado PDF/imagen, presentación institucional, consulta designada y resolución de la misma solicitud con capacidades independientes; no dictamen paralelo ni exclusividad médica inferida. Fuente: `odd/tasks/ostel-operacion-integral.md`, S17–S21.
- S5 — Contratos aún no aprobados: criterios PMO, suficiencia/obligatoriedad clínica, vigencias/renovación/excepciones, conservación/reemplazo y aceptación OSTEL. La continuidad autoriza avanzar técnicamente, no decidir estas reglas ni activar cobros/pagos o publicar/desplegar.
- S6 — Entorno autorizado: «autorizo», en respuesta a PostgreSQL descartable en Docker, dependencias desde el lockfile existente y servidores sólo en localhost, con datos ficticios, para completar concurrencia y navegador. No bases existentes/remotas, dependencias nuevas, saneamiento ni publicación.

## Tasks

| ID | Specs | Corte | Ruta / riesgo | Estado / evidencia |
| --- | --- | --- | --- | --- |
| T1 | S1–S4 | Precisar los efectos de aprobación y recuperar la matriz documental previa sin perder historia | Inline; pasivo | Completo local: matriz recuperada y precisión financiera; commit `e7aeb75` |
| T2 | S1,S4 | Caracterizar por API presentación privada → observación → reenvío → resolución; conservar original/ID/plazo, revisión, reintento y permisos | Inline; pruebas de contrato existente, Risk: none; sin cambio de producto | Completo local: dos caracterizaciones API aprobadas; commit `e7aeb75` |
| T3 | S1,S4,S6 | Ejecutar focal y suite pertinente en entorno aislado, registrar alcance y límites | Focal inline; suite delegada por duración de preparación/migraciones | Completo local: PostgreSQL 82 tests OK sin omisiones y navegador final 11 OK; evidencia L6 |
| T4 | S1,S2,S5 | Traducir contrato clínico aprobado a casos y configuración existente, implementar únicamente brechas | No ejecutar sin fuente y decisiones aprobadas; ruta/riesgo por determinar | Bloqueado por contrato |
| T5 | S1,S2,S4,S5,S6 | Integración representativa, escritorio/móvil/teclado y aceptación funcional/clínica; entrega separada | No sustituir por caracterización local; sin deploy ni aceptación implícita | Parcial: recorrido técnico real completo; aceptación clínica/humana dependiente de T4 |

## Log

### L1 — Objetivo original (05/11/2026)

usa como objetivo el plan que me compartiste para cerrar autorizaciones. avanza hasta que te encuentres un bloqueante o necesites intervencion humana

### L2 — Base y límites

- Worktree hijo aislado creado mediante Orca en `salud-cierre-autorizaciones-20261105`, desde el snapshot exacto. No se altera HEAD, rama ni documento local del worktree analítico de origen.
- El análisis anterior encontró `aplicar_resolucion` en `uso_autorizaciones.py:137–155`: aprobar no crea atención, pero puede completar distribución de un hecho ya realizado. La frase documental absoluta anterior requiere precisión, no un cambio funcional.
- T2 es caracterización: el comportamiento existe, por lo que no corresponde fabricar RED ni modificar lógica para aparentar TDD. Interfaz pública acordada en el plan: API institucional/financiador, sin mocks positivos. Se reutilizan `AutorizacionSetup`, `presentar`, `huella` y los endpoints existentes; no duplicar servicio ni escritor.
- El checkout nuevo no tiene `.env`; la prueba usará un entorno de proceso saneado, SQLite en memoria y almacenamiento efímero. No DB remota, credenciales, Docker, servidores ni datos reales. Si el runner aislado no es suficiente, registrar el límite y pedir sólo la intervención concreta necesaria.
- La matriz documental previa sigue sin commit en el worktree analítico. Se incorporará aquí como extensión del documento completo del snapshot, no como sustitución de ese documento por la versión antigua del otro checkout.

### L3 — Caracterización y límite observado

- T1/T2 completos localmente: matriz anterior recuperada como sección inicial sobre documento íntegro del snapshot; precisión sobre distribución de hechos ya realizados; dos casos públicos API de observación/reenvío con aprobación/rechazo. Sin cambio productivo.
- Error inicial del lanzador externo: `RENAPER_MODO=mock` no admitido; corregido únicamente allí a `simulado`. No se cargó `.env`, no hay conexión RENAPER.
- Primera prueba focal falló por la huella del test: `EventoCobertura` contiene también auditoría de lectura. Una reproducción diagnóstica delegada confirmó una sola consulta nueva y cero cambios de dominio en el retry. Aserción localizada corregida: preservar dominio y eventos anteriores, permitir exactamente la consulta esperada. No corrección de producto ni prueba de defecto funcional.
- Focal exacto: `python -B <scratch>/run.py apps.financiadores.test_prescripciones_autorizacion.PrescripcionAutorizacionTests.test_observacion_reenvio_y_aprobacion_conservan_prescripcion_y_plazo apps.financiadores.test_prescripciones_autorizacion.PrescripcionAutorizacionTests.test_observacion_reenvio_y_rechazo_conservan_prescripcion_y_plazo`: 2 OK, 0,795 s.
- Suite delegada una vez por duración de preparación/migraciones: mismo runner con `apps.financiadores.test_prescripciones_autorizacion apps.financiadores.test_auditoria_medica apps.financiadores.test_autorizaciones apps.financiadores.test_autorizaciones_manuales apps.financiadores.test_uso_autorizaciones`: 82 tests, 8,269 s, OK con 10 omisiones que requieren PostgreSQL dedicado/bloqueos/exclusión concurrente. No acredita esos casos omitidos.
- Runner temporal externo sanea entorno y deshabilita dotenv; usa SQLite en memoria, sin `.env` ni servidor. Dependencias existentes, sin instalación/configuración global. Base efímera destruida. Advertencia de staticfiles ausente conservada; no intervenir en saneamiento.
- Próximo bloqueo técnico: PostgreSQL descartable y recorrido real escritorio/móvil/teclado del candidato requieren autorización acotada de Docker/servicios localhost; no se inicia ese entorno por inferencia. Contratos clínicos continúan pendientes sin reiterar pedido OSTEL. Objetivo completo NO logrado; no cierre #147 ni homologación/aceptación/CI/merge/deploy.
- Risk: none. Sólo pruebas y documentación; no cambia código productivo, permisos, locks, esquema ni dependencias.

### L4 — Unidad local y revisión proporcional

- Commit `e7aeb75`: pruebas, matriz de aceptación y seguimiento juntos (235 líneas autoras). Previsión bajo orientación de 400; no se abre cadena ni PR. El worktree analítico de origen conserva sus cambios anteriores sin modificación.
- Comprobación estructural: AST válido, enlaces/rangos inmutables existentes, contenido íntegro del documento base preservado y diff sin errores. No cambios productivos ni de normalizadores posteriores a las pruebas.
- Evaluación nativa: el inventario canónico identificó sólo el nuevo documento de tareas; selección explícita resuelta. Candidato y commit: medium/executable_change, review_due=false/under_budget. Sin START, consentimiento, revisión aprobada ni cambios del switch global.
- T1/T2 completos; T3 parcial por omisiones PostgreSQL; T4/T5 abiertos. Siguiente intervención solicitada: autorizar PostgreSQL descartable local y servidores loopback con datos ficticios para concurrencia y navegador, sin bases existentes/remotas ni saneamiento. Los contratos normativos siguen pendientes independientemente.

### L5 — Autorización del entorno

autorizo

- S6 levanta únicamente el bloqueo de entorno de L4. Se preparan contenedor, puertos, archivos y escenarios propios, sin reutilizar recursos de otro frente. No levanta la deuda clínica S5 ni concede aceptación humana.
- Relectura actual: rama de cierre en `d662314`, limpia; Docker disponible e imagen PostgreSQL 16 Alpine ya local. El runner real existente no arranca la familia de importación. Se amplía sólo la caracterización combinada de observación/reenvío y se conservan los recorridos anteriores.

### L6 — PostgreSQL y navegador del candidato

- Contenedor propio `salud-autorizaciones-01a1a7cc-20261105`, imagen local PostgreSQL 16 Alpine, tmpfs y puerto 127.0.0.1:61211. No inspeccionar ni reutilizar contenedores/bases ajenos. Migraciones aplicadas sólo a base ficticia dedicada.
- Suite PostgreSQL delegada una vez: 82 tests OK en 37,381 s, sin omisiones. Es el mismo alcance de cinco módulos de L3; antes había 10 omisiones SQLite. Focal API previo y source productiva preservados.
- `npm ci --ignore-scripts --no-audit --no-fund` delegado, exitoso; package/lock sin cambios. Servidores propios: API loopback63952 y Vite loopback63953. Env de proceso saneado/dotenvdisabled, Vite con cwd externo/envFilefalse/cache propia. Sin instalaciones globales ni secretos reales.
- Fixture ampliada de siete a nueve escenarios, conservando los anteriores. Dos casos nuevos reutilizan el recorrido real existente con observación/reenvío antes de aprobar/rechazar. El plazo inicial vacío se detectó al inspeccionar captura y se reforzó con 48 h ficticias sólo en escenarios nuevos y una aserción no nula. No se afirma conservación de plazo por igualdad de dos valores vacíos.
- Chrome del sistema falló antes de abrir la aplicación; se usó Chromium1234 ya instalado correspondiente al lockfile. Focal final padre 2 OK en 23,3 s, visible; suite final delegada 11 OK en 45,7 s, sin omisiones. Una suite previa de 11 OK no acreditaba plazo no nulo; la final sí. No se cambia producto para acomodar el test.
- Capturas de aprobación escritorio/rechazo móvil con plazo visible inspeccionadas. Teclado en descarga, reenvío y resolución; PDF original byte-exacto; revisiones/historia/ID y permisos separados. Negativos con transporte inyectado se distinguen de positivos reales.
- Demo local visible abierta con sesión ficticia en puerto63953. Primer wrapper usó un nombre de botón inexistente, corregido sólo externamente a «Resueltas». Browser/servidores/contenedor propios retenidos para inspección humana; no son aceptación ni despliegue. Temporales externos previos retenidos por limpieza bloqueada, sin bypass ni reintento de borrado.
- T3 completo local; T5 sólo parte técnica. T4 permanece sin fuente/decisiones clínicas aprobadas: PMO, evidencia mínima, vigencias/renovación y conservación/reemplazo. No pedir de nuevo lo ya solicitado a OSTEL ni inventar reglas para declarar cierre integral. Sin autorización de push/PR/merge/deploy.
- Risk: none. Sólo pruebas/fixture ficticia/documentación; sin modificación productiva, permisos, locks, migraciones ni dependencias del proyecto.
