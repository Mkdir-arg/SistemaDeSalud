# Prerrequisito CI de Familias

Objetivo: recuperar el runner publicado que necesita #214 antes de integrar Familias.
Rama: `juanikitro/salud-familias-ci-previo-20261105`; base `8a3a1d8b87a25380c85e15519fc0683f09ef6c49`; dos PRs secuenciales a continuidad, nunca main. Runner: unittest sin DB y CI remoto. Presupuesto previsto menor de 400 líneas por PR.

## Specs

- S1 — «monitorea y arregla, cuando el ci este verde mergea. si el error no es de este pr, intenta pullear el arreglo de otras ramas».
- S2 — «autorizo», en respuesta a «¿Autorizás esa secuencia de dos PRs y sus merges condicionados a CI verde?». Primero PR previo de CI hacia continuidad; después #214 sobre esa base, cada merge sólo con todos los checks verdes del HEAD exacto. No retarget a main ni deploy.
- S3 — Recuperar el arreglo existente completo de manifiesto/preparación/limpieza y sus pruebas, sin omitir suites, debilitar guards o importar documentación ajena. Procedencia: commit `dbffea304b189fbeeb688a6b7ec0155799f58093`, PR #211 ya integrado en main.
- S4 — Del frente vigente: «no toque saneamiento, eso lo hace otro agente». Sólo consultar su entrega publicada; no leer/editar su checkout ni dirigir a ese agente. Otros arreglos heredados se reutilizarán sólo ante su fallo correspondiente demostrado.
- S5 — Homologación OSTEL, aceptación local ya registrada y publicación/merge son estados separados. No cerrar #181/#142 ni inferir equivalencias o derechos como efecto de CI verde.

## Tasks

| ID | Specs | Resultado | Ruta / riesgo | Estado / evidencia |
| --- | --- | --- | --- | --- |
| T1 | S1,S3,S4 | Recuperar runner/workflow y pruebas publicadas | Inline, patch conocido de tres archivos; ítems 2/5 | Completo local: RED tests publicados y GREEN al recuperar fuente; tres archivos idénticos por Git a dbffea3, sin documentos ajenos |
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
