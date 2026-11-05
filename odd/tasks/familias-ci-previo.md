# Prerrequisito CI de Familias

Objetivo: recuperar el runner publicado que necesita #214 antes de integrar Familias.
Rama: `juanikitro/salud-familias-ci-previo-20261105`; base `8a3a1d8b87a25380c85e15519fc0683f09ef6c49`; dos PRs secuenciales a continuidad, nunca main. Runner: unittest sin DB y CI remoto. Presupuesto previsto menor de 400 líneas por PR.

## Specs

- S1 — «monitorea y arregla, cuando el ci este verde mergea. si el error no es de este pr, intenta pullear el arreglo de otras ramas».
- S2 — «autorizo», en respuesta a «¿Autorizás esa secuencia de dos PRs y sus merges condicionados a CI verde?». Primero PR previo de CI hacia continuidad; después #214 sobre esa base, cada merge sólo con todos los checks verdes del HEAD exacto. No retarget a main ni deploy.
- S3 — Recuperar el arreglo existente completo de manifiesto/preparación/limpieza y sus pruebas, sin omitir suites, debilitar guards o importar documentación ajena. Procedencia: commit `dbffea304b189fbeeb688a6b7ec0155799f58093`, PR #211 ya integrado en main.
- S4 — Del frente vigente: «no toque saneamiento, eso lo hace otro agente». Sólo consultar su entrega publicada; no leer/editar su checkout ni dirigir a ese agente. Otros arreglos heredados se reutilizarán sólo ante su fallo correspondiente demostrado. Backend de #214 confirmó staticfiles y creado_por: recuperar fuentes/pruebas completas de 3a7bf96 y 467c935, sin sus documentos ajenos.
- S5 — Homologación OSTEL, aceptación local ya registrada y publicación/merge son estados separados. No cerrar #181/#142 ni inferir equivalencias o derechos como efecto de CI verde.

## Tasks

| ID | Specs | Resultado | Ruta / riesgo | Estado / evidencia |
| --- | --- | --- | --- | --- |
| T1 | S1,S3,S4 | Recuperar runner/workflow y pruebas publicadas | Inline, patch conocido de tres archivos; ítems 2/5 | Completo local: RED tests publicados y GREEN al recuperar fuente; tres archivos idénticos por Git a dbffea3, sin documentos ajenos |
| T1b | S1,S3,S4 | Recuperar fixtures estáticos y clasificación de autoría ante fallos confirmados | Inline, patches publicados conocidos de 87 líneas; ítems 2/5 | Completo local: fuentes publicadas recuperadas; clasificación RED local, 64 regresiones y verificador independiente aprobados |
| T2 | S1–S4 | Comprobar guards y publicar PR previo acotado | Suite focal inline; verificador independiente ítems 2/5 | Verificación local e independiente aprobadas; publicación pendiente |
| T3 | S1,S2,S5 | CI verde y merge previo a continuidad | Remoto explícitamente autorizado | Pendiente; no omitir checks ni usar admin/bypass |
| T4 | S1,S2,S5 | Sincronizar #214, verificar CI y merge a continuidad | Tras T3, sin main/deploy | Pendiente |

## Log

### L1 — Solicitud y estrategia aprobada

monitorea y arregla, cuando el ci este verde mergea. si el error no es de este pr, intenta pullear el arreglo de otras ramas

autorizo

- issue43 run42080692128: suite familiar intenta leer SALUD_FAMILIA_MANIFEST ausente. La dependencia ya está en base8a3a1d8; #214 sólo añade aserciones, no introdujo el fallo del runner. Fuente publicada dbffea3 está en origin/main y ausente de la base de continuidad.
- PR214 tiene361líneas; recuperar los tres archivos fuente/pruebas suma128 y supera400. Se aprobó PR previo acotado y merge secuencial con CI verde, no excepción de tamaño ni modificación de main.
- Worktree propio limpio antes de crear esta rama desde la base exacta; la rama de Familias y sus commits publicados quedan preservados. Sin nuevos entornos, DB, servidores o secretos. El runner puro usa conexiones/procesos simulados.
- Antes de importar fuentes, observar RED de las pruebas publicadas; luego recuperar runner y workflow sin modificaciones. Riesgo de permisos/rutas de limpieza y CI exige verificador independiente y evaluación nativa del nuevo candidato; la omisión anterior de #214 no concede consentimiento aquí.

### L2 — Recuperación y verificación locales

- Se aplicaron primero sólo las pruebas publicadas: RED observado (cinco fallos y un error de preparación faltante/guard/limpieza; conexiones simuladas, sin DB real). Luego se recuperaron runner/workflow; 12 pruebas focales aprobadas.
- Suite ampliada inicial necesitó settings para SimpleTestCase; no era fallo de producto. Se configuró Django mínimo en memoria, sin cargar .env ni DB. Comando correcto desde backend: `python -B -c "from django.conf import settings; settings.configure(DATABASES={}, INSTALLED_APPS=[], SECRET_KEY='ficticio-sin-db'); import django; django.setup(); import unittest; unittest.main(module=None,argv=['unittest','tests.test_importacion_real','config.test_postgres_test_guard','apps.financiadores.tests_ostel_scenarios','-q'])"`: 37 pruebas aprobadas.
- Verificador independiente gpt-6.1-sol/medium, ítems 2/5: mismo comando en scratch aislado, 37 pruebas sin omisiones; probes públicos de rechazo previo a DB/subprocesos/borrados y hash de manifiestos intacto. Cinco guards anteriores conservan excepción/mensaje; rutas workflow/runner coinciden y ambas suites siguen presentes. Ningún bloqueante nuevo.
- Los tres archivos fuente coinciden con dbffea3 por Git; CRLF local frente a LF del blob impide afirmar igualdad literal de bytes. No se reinventa el arreglo ni se importan cambios de negocio o documentación de otro seguimiento. Las regresiones publicadas ya fijan los probes de rutas/manifiestos y symlink.
- Scratch del verificador propio retenido: familias-ci-independent-4sa8rkm9, salud-importacion182-verificacion-5kyb7xeb y ostel-familia-ui-salud-importacion182-verificacion-5kyb7xeb, bajo temporal del sistema. Ningún servicio local nuevo. La retirada recursiva fue denegada anteriormente por el entorno; no se elude con otra herramienta.
- Pendientes: CI del nuevo PR sobre su HEAD exacto, revisión nativa propia y merge condicional. No se reabre la omisión anterior de #214 ni se cambia el switch global. Risk: items 2/5.

### L3 — Diagnóstico del backend y recuperación del checkout

- El backend de #214 terminó: run42080692061, 2936 pruebas, dos fallos y 22 errores. Los errores son STORAGES sin staticfiles en prescripciones; la clasificación omite (financiadores.BorradorReglaDerechos, creado_por). Son fallos de fuentes que no cambió Familias; recuperar 3a7bf96 y 467c935 completos en código/pruebas.
- El fallo restante de bajas sí corresponde a una expectativa vieja del contrato de #214: espera40campos publicados donde ahora se omite CODPAR. Corregir ese test EN LA RAMA DE #214, comprobando por separado39publicados/40persistidos. No introducir esa expectativa en este prerrequisito, que no contiene el filtro de privacidad.
- El worktree de ejecución y su rama CI local desaparecieron durante la espera, sin causa atribuida. PR221/709ef8f y PR214/5292cda permanecen intactos en GitHub; el checkout original y sus cambios se preservaron. Se recuperó desde el HEAD publicado un nuevo worktree propio salud-familias-ci-recuperacion-20261105, branch juanikitro/salud-familias-ci-recuperacion-20261105. Sin reset, prune ni recuperación de autoridad desde otra raíz.
- Revisión nativa del candidato709ef8f: consentimiento1, tres lentes sin hallazgos, acknowledgement exacto confirmado con authority burned. No reabrir ese linaje desde esta raíz. #221 issue43/Frontend/OpenAPI/paciente verdes; backend aún ejecutándose. Los nuevos cambios requerirán su propia evaluación.

### L4 — Arreglos heredados confirmados

- Se recuperaron sólo las fuentes/pruebas de 3a7bf96 (alias staticfiles en fixtures clínicas) y 467c935 (clasificación de creado_por y regresión de autoría/aislamiento): tres archivos/87líneas, sin notas de otros seguimientos. Se comprobó diff vacío por Git contra cada fuente publicada.
- RED local de ClasificacionDeCamposTests por el mismo campo observado en CI; la prueba clínica focal aislada no reprodujo los errores de estáticos. Para ese segundo arreglo, la evidencia RED son los22errores remotos y la igualdad de sus fuentes con el baseline; no se atribuye a Familias ni se inventa reproducción local.
- Tras recuperación, foco26pruebas y suite conjunta64pruebas (prescripciones/simulación) aprobados con PostgreSQL propio descartable. Launcher externo sanea entorno, bloquea dotenv y usa estáticos ficticios externos; no secretos o DB reales. Contenedor propio salud-familias-ci-01a1a7cc, loopback53335, tmpfs; retirar sólo recursos propios al terminar.
- El candidato anterior709ef8f tiene revisión nativa cerrada/authority burned; esta unidad adicional requiere evaluación y verificación propias. No copiar ni recuperar autoridad de la raíz desaparecida. Verificación independiente de la nueva unidad pendiente.

### L5 — Verificación de la unidad heredada adicional

- Verificador independiente en scratch desde709ef8f:64pruebas aprobadas, sin omisiones; controles de autor real/contexto limpio/ajeno404/huellas y clínica503/archivos privados404 preservados. AST confirma que el único cambio productivo es clasificar BorradorReglaDerechos.creado_por; no cambia funciones de atribución/contexto.
- Las regresiones publicadas cubren los probes funcionales; no se agregaron pruebas contra git history. Spot check del padre: mismo comando de64pruebas aprobado, sin cambios productivos posteriores.
- Prerrequisito171líneas más esta unidad sigue bajo400. CI y revisión del HEAD nuevo pendientes; no heredar autoridad quemada del candidato709ef8f ni omitir consentimiento propio.
