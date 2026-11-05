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

## Tasks

| ID | Specs | Resultado | Ruta / motivo | Estado / evidencia / commit |
| --- | --- | --- | --- | --- |
| T1 | S1,S2 | Candidato aislado correcto y reconciliación documental | Inline; cambio documental conocido | Completo local: base exacta y reconciliación trasladada; documento previo preservado; commit pendiente |
| T2 | S3,S4 | Suprimir exposición administrativa de CODPAR sin modificar el original | Inline tras mapa delegado de superficies desconocidas; Risk: items 2/3 | Completo local: RED por CODPAR expuesto; GREEN focal; sin mutar fuente/huella; commit pendiente |
| T3 | S3–S5 | Verificación integrada y demostración técnica | Pruebas focales inline; suite larga y verificador ítems 2/3 delegados | Completo técnico local: independiente152tests, diferencialv1/v2/v3, build y6recorridos reales; aceptación pendiente; commit pendiente |
| T4 | S6 | Equivalencias homologadas y diferencias necesarias | Condicionada a fuente aprobada | Pendiente de información externa ya identificada; no inventar catálogo |
| T5 | S1,S2,S6 | Aceptación humana y entrega | Humana; publicación aparte | Pendiente; no cerrar issues ni atribuir aceptación |

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
