# Cierre de Familias

Objetivo: completar el plan aprobado de Familias, sin confundir cierre técnico y homologación OSTEL.
Rama: `juanikitro/salud-familias-cierre-20261105`; base: `8a3a1d8b87a25380c85e15519fc0683f09ef6c49`. Estrategia: ask-on-risk; previsión menor de 400 líneas propias. Runner: Django/PostgreSQL descartable y Playwright existente.

## Specs

- S1 — «usa como objetivo el plan que me compartiste para cerrar el modulo de familias. avanza hasta que te encuentres un bloqueante o necesites intervencion humana». Referencia: plan compartido del 05/11, etapas consolidación, privacidad, evidencia técnica, homologación y aceptación.
- S2 — Del traspaso vigente: «no toque saneamiento, eso lo hace otro agente». No escribir en su checkout ni duplicar sus correcciones. Sin publicación, cierre de issues, merge ni deploy.
- S3 — Del contrato familiar: «Never deduce family from a shared NROAFI.» Conservar vínculo explícito, clasificación pendiente y derechos separados; no renumerar, fusionar ni reactivar por inferencia.
- S4 — Del plan aprobado: revisar la presentación administrativa de CODPAR y corregir sólo exposición reproducible. Conservar originales persistidos, historial y copia de salud protegida. No extender minimización a otros campos ni modificar permisos por inferencia.
- S5 — Del plan aprobado: reutilizar regresiones familiares/CODPAR y recorrido real sobre el mismo candidato; negativos sin mutación, aislamiento, revisiones, fuentes y derechos intactos; escritorio, móvil y teclado. No repetir G2a.
- S6 — Del plan aprobado: homologación sólo con equivalencias aprobadas; aceptación humana separada. La falta de esos insumos no se reemplaza por ejemplos sintéticos ni cierra #181/#142.
- S7 — «autorizo», en respuesta a usar `gpt-6-luna` con esfuerzo alto para el explorador, sustituyendo el modelo no disponible. No cambia la asignación de otros actores.
- S8 — «acepto», en respuesta a «¿Aceptás el circuito mostrado en la demo?». Aceptación técnica local del circuito mostrado, sin inferir homologación, casos no detallados ni autorización de publicación/merge/deploy.
- S9 — «retira el entorno local y publica la entrega». Autoriza retirar sólo recursos propios y publicar esta rama/PR mediante la sesión GitHub ya autorizada; sin merge, deploy ni cierre de issues.

## Tasks

| ID | Specs | Resultado | Ruta / motivo | Estado / evidencia / commit |
| --- | --- | --- | --- | --- |
| T1 | S1,S2 | Candidato aislado correcto y reconciliación documental | Inline; cambio documental conocido | Completo local: base exacta y reconciliación trasladada; documento previo preservado; commit `8d54b5f` |
| T2 | S3,S4 | Suprimir exposición administrativa de CODPAR sin modificar el original | Inline tras mapa delegado de superficies desconocidas; Risk: items 2/3 | Completo local: RED por CODPAR expuesto; GREEN focal; sin mutar fuente/huella; commit `8d54b5f` |
| T3 | S3–S5 | Verificación integrada y demostración técnica | Pruebas focales inline; suite larga y verificador ítems 2/3 delegados | Completo técnico local: independiente152tests, diferencialv1/v2/v3, build y6recorridos reales; aceptación técnica local S8; commit `8d54b5f` |
| T4 | S6 | Equivalencias homologadas y diferencias necesarias | Condicionada a fuente aprobada | Pendiente de información externa ya identificada; no inventar catálogo |
| T5 | S1,S2,S6,S8 | Aceptación humana y entrega | Humana; publicación aparte | Aceptación técnica local confirmada S8; publicación autorizada S9, en curso; no cerrar issues |

## Log

### L1 — Solicitud original, 05/11/2026

usa como objetivo el plan que me compartiste para cerrar el modulo de familias. avanza hasta que te encuentres un bloqueante o necesites intervencion humana

### L2 — Reanudación y candidato

- `autorizo`: sustitución explícita del explorador por gpt-6-luna/high después del rechazo de gpt-6.1-luna. Mapa delegado read-only completado y corregido: diferenciar v1/v2 de OSTEL v3; no atribuir CODPAR al XLSX de rechazos que ya lo excluye.
- Creado worktree relacionado `salud-familias-cierre-20261105` desde el snapshot exacto, sin hooks, agente nuevo, publicación ni cambios en el checkout de análisis/saneamiento. El documento previo del análisis y .atl permanecen intactos.
- Evidencia: ImportacionSerializer devuelve filas crudas; RevisionFilaOstel muestra CODPAR. Respuesta completa/incremental comparten el lote; fuente persistida y copia protegida deben conservarse. Archivo anotado requiere verificar que no incorpore datos sensibles desde el servidor al archivo aportado por quien solicita.
- Autorización de ejecución local del plan: sólo dependencias prescritas existentes y entorno ficticio propio. Nunca leer .env, reutilizar credenciales ni conectar DB real. Settings base cargan dotenv: el launcher de prueba debe impedirlo y limpiar el entorno heredado.
- RED/GREEN aplica a T2 por regla observable y pruebas públicas existentes. No corresponde RED/GREEN documental para T1. No reintentar revisión nativa histórica ni cambiar su switch.

### L3 — Implementación y verificación, 05/11/2026

- T2: filtrado de `original.CODPAR` en ImportacionSerializer para v3 y sus respuestas completas/incrementales; sin mutar el modelo. UI administrativa oculta su fila y aclara que la fuente completa sigue conservada. V1/v2 y descriptor de archivo de40columnas no cambian. Risk: items 2/3.
- RED: `python -B <scratch>/run.py test apps.financiadores.test_privacidad_importacion --noinput --keepdb --verbosity 1` falló por CODPAR visible. GREEN focal aprobado; una expectativa de lectura sin eventos se ajustó al evento legítimo consultar_importaciones, preservando eventos previos y el lote.
- Suite propia inicial:152tests con3failures/1error por expectativas anteriores de CODPAR público. Una corrección adaptó esas expectativas con controles de persistencia; recheck sólo dejó una aserción nueva de orden JSONB. Se corrigió con comparación de conjuntos y pasó su recheck focal; un primer comando focal tenía nombre de clase incorrecto, corregido sin cambios productivos.
- Verificador independiente gpt-6.1-sol/medium por ítems2/3: archivo base más overlay en scratch externo, once módulos152tests/90.117s OK. Diferencial contra base: v1/v2 idénticos, v3 sólo omisión intencional, datos y huella intactos. No acceso DB para probes. La primera forma del probe comparaba identidad ModelState y fallaba también en base; el verificador corrigió sólo ese probe externo.
- Probes incorporados en test_privacidad_importacion: tres serializers, v1/v2/v3, fuente/filas incrementales/huella inmutables. Spot check del padre: módulo focal final2tests OK. Sin nuevos cambios productivos después de la verificación.
- Comando de suite: `python -B <scratch>/run.py test apps.financiadores.test_privacidad_importacion apps.financiadores.test_codpar_importacion apps.financiadores.test_codpar_ostel apps.financiadores.test_familia_pendiente apps.financiadores.test_familia_ostel apps.financiadores.test_concurrencia_familia_ostel apps.financiadores.test_importacion_respuesta apps.financiadores.test_ostel_importacion apps.financiadores.test_anotaciones apps.financiadores.test_padron130 apps.financiadores.test_importaciones --noinput --keepdb --verbosity 0`.
- Npm ci con lockfile e ignore-scripts y npm run build OK, manifiestos intactos. Runner real: `python -B <scratch>/node.py node_modules/@playwright/test/cli.js test --config <scratch>/playwright.config.mjs`:6casos OK, config importa el runner existente y usa puertos propios; desktop estándar y móvil390×844/teclado. Demo visible adicional1366×900; capturas propias revisadas. No repetir G2a.
- Scratch padre `salud-familias-cierre-eui91_sa` y fixture `ostel-familia-ui-01a1a7cc-cierre`, bajo temporal del sistema. PostgreSQL propio `salud-familias-01a1a7cc`, loopback58366/tmpfs; API8347 y Vite5351 para demo. Launcher limpia entorno y bloquea dotenv antes de settings; no lectura de secretos ni conexiones reales. No publicar manifiesto ficticio.
- Revisión nativa: switch global on; evaluación preliminar ítem2 quedó no evaluable por archivos nuevos. No se infiere riesgo bajo ni aprobación. Tras normalización, candidato final aún debe evaluarse y seguir continuación nativa exacta. Sin reabrir linajes históricos.
- T4/T5 pendientes de equivalencias aprobadas y aceptación humana, respectivamente; no pedir nuevamente la información ya solicitada a OSTEL. No cerrar #181/#142 ni atribuir integración main, CI o deploy. Publicación fuera de autorización.

### L4 — Revisión omitida por elección humana

2

- Selección única de «Omitir esta vez» del consentimiento v3 del candidato de ocho archivos/312líneas. Ejecutada una vez la invocación exacta entregada por el proveedor; resultado `action=declined`, `consent=declined_this_candidate`, target `sha256:06d0ab8a07ea6420dbb72e5949cdaca2f9a79d33259cb5ef76aa811aa2a92017` coincidente.
- T1–T3 se conservan en el commit local `8d54b5fd3a2c3af22ad7cc23d8596b7710620495`. No revisión aprobada, receipt, publicación ni autorización para integrar main. Modo global sin cambios; no reabrir este candidato por la omisión.
- T4 continúa pendiente de equivalencias aprobadas; T5 de aceptación humana. No se repite la solicitud ya realizada a OSTEL. La prueba ficticia de vínculo conocido no acredita una equivalencia normativa ni derechos. Familias no cierra legajo/credenciales y restantes criterios de #142.
- Sin código de negocio adicional justificado por los insumos disponibles. La limpieza del scratch del verificador fue rechazada por política del entorno; no se intentó otro mecanismo de borrado. Recursos de demo propios retenidos para inspección humana, no confundirlos con saneamiento.
- Esta actualización es sólo seguimiento pasivo: lectura estructural y diff --check; no nueva ejecución de tests/DB/build ni nuevo candidato funcional. Risk: none.

### L5 — Aceptación técnica local, 05/11/2026

acepto

- Responde a «¿Aceptás el circuito mostrado en la demo?». Se registra la aceptación humana del circuito técnico local mostrado, sin atribuirle casos, dispositivos o verificaciones adicionales que no detalló.
- La aceptación elimina ese pendiente local de T3/T5, no aporta equivalencias de parentesco/identidad/catálogos ni homologa OSTEL. T4 continúa pendiente de la fuente aprobada ya solicitada; no inferir normativa ni pedir nuevamente el mismo insumo.
- Publicación, integración/merge y despliegue no autorizados. Revisión nativa omitida sólo para el candidato anterior, no aprobada. No cerrar #181/#142 ni afirmar que todo el módulo está homologado.
- Actualización documental pasiva del registro y aceptación temática; lectura estructural y diff --check. Sin cambios de producto, pruebas nuevas o conexiones a DB. Risk: none.

### L6 — Retiro de entorno y publicación autorizados, 05/11/2026

retira el entorno local y publica la entrega

- Identidad del contenedor comprobada por ID completo y etiqueta de propiedad; PostgreSQL propio detenido y retirado. Sesiones de demo terminadas y procesos descendientes propios verificados y detenidos; comprobar listeners antes de cierre.
- Tres carpetas externas propias verificadas como hijas directas del temporal, sin enlaces de redirección. El entorno rechazó el borrado nativo aun con autorización nueva; no se usó otra herramienta para eludirlo. Temporales retenidos: salud-familias-cierre-eui91_sa, ostel-familia-ui-01a1a7cc-cierre y familias-independent-b7zpmd1e. El worktree y sus dependencias locales se conservan.
- Publicación prevista: un PR borrador contra juanikitro/salud-continuidad-generica-20261103, cuya punta remota coincide con base8a3a1d8, para mostrar sólo este corte; no integrar la entrega acumulada ni saneamiento. Usar GitHub autorizado por HTTPS, sin SSH ni extracción de credenciales. Refs #181/#142, no cierre automático. Sin merge/deploy.
- La aceptación técnica local sigue vigente; homologación permanece pendiente. Revisión nativa del candidato funcional omitida por elección2 y seguimientos pasivos; no se reclama aprobación. Registrar URL/CI observado después de confirmar creación; no inferir éxito de una operación ambigua.
