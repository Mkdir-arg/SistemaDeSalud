# Cierre de Autorizaciones

Objetivo: completar el plan de cierre sin inventar contratos clínicos ni duplicar saneamiento. Rama: `juanikitro/salud-cierre-autorizaciones-20261105`; base: `8a3a1d8b87a25380c85e15519fc0683f09ef6c49`.
Entrega: `ask-on-risk`, local, sin publicación/merge/deploy. Previsión: menos de 400 líneas autoras en el primer corte. Runner: API Django con `config.settings_financiadores_test`, SQLite efímero; no acredita concurrencia PostgreSQL.

## Specs

- S1 — Objetivo exacto: «usa como objetivo el plan que me compartiste para cerrar autorizaciones. avanza hasta que te encuentres un bloqueante o necesites intervencion humana».
- S2 — Solicitud de planificación referida: «analiza lo que queda por hacer para cerrar el modulo y planifica su implementacion». El plan acordado comprende precisión documental y caracterización de prescripción con observación/reenvío; contrato mínimo; implementación de diferencias aprobadas; integración; aceptación y entrega separadas.
- S3 — Restricción vigente: «no toque saneamiento, eso lo hace otro agente». Sin inspeccionar ni modificar su checkout, repetir sus arreglos ni asumir sus resultados.
- S4 — Preservar S17–S21 ya aprobados: adjunto privado PDF/imagen, presentación institucional, consulta designada y resolución de la misma solicitud con capacidades independientes; no dictamen paralelo ni exclusividad médica inferida. Fuente: `odd/tasks/ostel-operacion-integral.md`, S17–S21.
- S5 — Contratos aún no aprobados: criterios PMO, suficiencia/obligatoriedad clínica, vigencias/renovación/excepciones, conservación/reemplazo y aceptación OSTEL. La continuidad autoriza avanzar técnicamente, no decidir estas reglas ni activar cobros/pagos o publicar/desplegar.

## Tasks

| ID | Specs | Corte | Ruta / riesgo | Estado / evidencia |
| --- | --- | --- | --- | --- |
| T1 | S1–S4 | Precisar los efectos de aprobación y recuperar la matriz documental previa sin perder historia | Inline; pasivo | Completo local: matriz recuperada y precisión financiera; commit pendiente |
| T2 | S1,S4 | Caracterizar por API presentación privada → observación → reenvío → resolución; conservar original/ID/plazo, revisión, reintento y permisos | Inline; pruebas de contrato existente, Risk: none; sin cambio de producto | Completo local: dos caracterizaciones API aprobadas; commit pendiente |
| T3 | S1,S4 | Ejecutar focal y suite pertinente en entorno aislado, registrar alcance y límites | Focal inline; suite delegada por duración de preparación/migraciones | Parcial: suite 82 tests OK, 10 omisiones PostgreSQL; falta ese entorno y navegador |
| T4 | S1,S2,S5 | Traducir contrato clínico aprobado a casos y configuración existente, implementar únicamente brechas | No ejecutar sin fuente y decisiones aprobadas; ruta/riesgo por determinar | Bloqueado por contrato |
| T5 | S1,S2,S4,S5 | Integración representativa, escritorio/móvil/teclado y aceptación funcional/clínica; entrega separada | No sustituir por caracterización local; sin deploy ni aceptación implícita | Dependiente de T4 y entorno autorizado |

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
