# #38 — dinero vinculado para la demo del 15/09

## Estado de activación de la demo — 15/09/2026

Para el cierre posterior, publicación y nueva prioridad de obras sociales, consultar el [estado post-demo](../funcionalidades/finanzas-costos/estado-post-demo-2026-09-15.md). Las cifras y estados de publicación de este plan son checkpoints históricos.

**Decisión posterior a la demo:** el usuario pidió resolver el fallo inicial de captura y aclaró que no existen históricos productivos que deban diferenciarse. El hecho económico existente pasa a ser la fuente recuperable aun sin snapshot de cobro; no se agrega una migración ni se ejecuta reconstrucción masiva. Se conservan los cortes temporales de la política, el bloqueo por hecho, la idempotencia, el alcance sensible y el rollback de recuperación si falla la auditoría. Esto sustituye el límite de «fallo al insertar el ancla requiere investigación» que figura en los checkpoints inferiores. Prueba de reproducción: antes el GET devolvía lista vacía para un hecho cuya captura falló; después aparece y dos POST de recuperación generan un único cargo con el arancel original.

El usuario autorizó y confirmó activar las correcciones y reemplazar los datos de8090 por el escenario ficticio Hospital General Los Aromos. El código corregido está integrado en el worktree de continuidad y activo; la preparación y evidencia de la carga se describen en [el plan del15/09](2026-09-15-demo-los-aromos-design.md). Las secciones inferiores conservan los checkpoints históricos y sus restricciones de ese momento. No hubo commit/push, merge ni cierre de issues.

## Checkpoint anterior — correcciones validadas antes de su activación

El usuario pidió corregir todos los hallazgos técnicos y de UI/UX. La preparación se hace en `sistemadesalud-finanzas-dinero-demo` a partir del código activo sobre `73ad575`: 8090 monta el otro worktree en vivo y no se reinicia ni modifica durante estas pruebas. No hay cambios de esquema, dependencias, concesiones, usuarios ni datos de demo. El usuario aclaró que la elección del perfil y la carga realista se harán cuando lo solicite; su ausencia no es un defecto del módulo.

Correcciones y criterios observables:

- Reintentar una devolución después de perder la respuesta y actualizar la vista previa conserva la identidad de la operación, sin otra devolución ni reducción. Versiones y pendiente esperado son controles de concurrencia, no una nueva intención. La identidad se conserva en memoria mientras sigue abierto el formulario; no se guardan importes ni referencias en almacenamiento persistente del navegador.
- Los POST del lote de dinero/cobros que devuelven información monetaria registran la lectura dentro de la misma transacción: si la auditoría falla, no queda una operación oculta. Repetir una aprobación de dinero ya realizada también audita la lectura. Esto no describe todos los POST históricos de gastos/ajustes: conservan autoría de escritura, pero su cobertura de auditoría de lectura no es uniforme; ver el estado post-demo.
- Se puede suspender expresamente el cobro de una prestación inactiva sin reactivar el catálogo. Desactivar el catálogo y suspender cobros siguen siendo decisiones distintas; no se recalculan cargos ni políticas históricas.
- El gasto permite abrir su cuenta existente sin intentar crearla de nuevo. El enlace sólo se expone con lectura de dinero en la institución, área y sensibilidad de esa cuenta.
- Resumen, Control mensual y Evolución muestran las correcciones de gasto pendientes como cantidad separada. No cambian el confirmado ni se presentan como otro importe por pagar; un mes con correcciones pendientes no figura completo.
- Una devolución ligada a una reducción anterior no dice que ambas se aprueban juntas. Reservas en cero no ocupan un bloque detallado permanente. La ayuda incluye los gastos compartidos efectivamente atribuidos, sin prometer el costo total del hospital.
- El recuperador usa la fecha de última revisión ya existente: nunca revisados primero y luego los menos recientemente revisados. Los errores también registran revisión bajo el bloqueo del hecho, sin borrar faltantes ni modificar importes. Un lote persistente de 100 hechos sin valor no impide recuperar el siguiente; el modo seco no escribe.

### Evidencia del lote corregido

- PostgreSQL16 temporal, sin puertos publicados ni conexión a la demo: `python manage.py test apps.finanzas --noinput --verbosity 0` → **283 pruebas OK**, 94,056s. Incluye 22 nuevas regresiones: recuperación entre lotes y error persistente, permiso del enlace gasto/cuenta, suspensión y auditoría/rollback, ajustes pendientes y sus límites de acceso. Los mensajes de error durante los tests corresponden a fallas simuladas y respuestas negativas esperadas.
- Rojo antes del arreglo: devolución con respuesta perdida cambiaba clave después de actualizar preview; API no exponía cuenta existente; el hecho101 seguía sin costear tras dos lotes100; fallo persistente monopolizaba el primer lugar; faltaban conteos y auditoría. Los mismos escenarios pasan después del cambio.
- UI aislada con `CAUCE_URL=http://127.0.0.1:18990`, proxy apuntado a puerto sin servicio y HTTP completamente simulado: `node node_modules/@playwright/test/cli.js test finanzas-dinero.spec.js --config=playwright.finanzas-ui.config.js --output=C:/Users/Juanito/AppData/Local/Temp/finanzas-review-ui-dinero-final-20260914` → **29 OK**, 30,5s. Archivo `finanzas-ui.spec.js`, mismo comando/config, salida `finanzas-review-ui-completa-20260914` → **51 OK**, 1,5min. Total **80**. Después, un foco visual del escenario de reservas vacías pasó con capturas de escritorio y móvil390; no fue un cambio funcional.
- Una ejecución intermedia de UI coincidió con HMR y perdió un elemento al cambiar de vista. Se repitió sobre archivos estables y pasó, igual que la suite completa; no se parcheó el producto por ese timeout.
- `node node_modules/vite/bin/vite.js build --outDir C:/Users/Juanito/AppData/Local/Temp/finanzas-review-build-20260914` → **742 módulos OK**, 2,46s. `python manage.py makemigrations --check --dry-run` → **No changes detected**. `git -c core.safecrlf=false diff --check` → sin errores.
- Inspección visual central: aviso separado de ajustes en Resumen, mes provisional con corrección pendiente en móvil, dinero sin bloque vacío y acciones de cuenta visibles a390px. Capturas bajo `finanzas-review-ui-completa-20260914` y `finanzas-review-ui-dinero-visual-20260914` en Temp.
- Revisión cruzada Standards de cambios del integrador y Spec de interfaz: **sin nuevos hallazgos confirmados**. Se añadió cobertura expresa de sensibilidad e institución al enlace gasto/cuenta.
- Issues #33/#35/#38 reconciliados sin cerrar issues ni alterar tablero, responsables o PR. Distinguen lote base activo y correcciones todavía aisladas. El perfil y la carga realista se posponen por pedido explícito del usuario.
- Retirados el contenedor PostgreSQL `finanzas-review-pg-20260914`, su red interna `finanzas-review-test-20260914` y el Vite temporal18990. Sólo contenían pruebas sintéticas; se conservan build y capturas en Temp. No se retiraron servicios ni volúmenes de8090/8092.

Las correcciones abarcan26 archivos respecto de la versión activa: servicios/API y regresiones de dinero/cobros, recuperador de costos, serializers/vistas de gastos, calendario/reportes, páginas financieras y sus tests, guía y este plan. No incluyen modelos, migraciones, permisos ni dependencias nuevos. Staging queda en HEAD separado `73ad575`; rama principal de continuidad y PR40 permanecen en el mismo checkpoint, sin commit/push.

Pendiente operativo: copiar/activar el lote después de autorización, conservando el estado actual y sin semillas ni concesiones; todavía no se hizo. 8090 y health8010 siguen HTTP200 con38 archivos locales previos intactos. La nueva suite se ejecutó en bases temporales, no en la demo. No se repitió navegador→API real para estas correcciones ni CI/otros navegadores/carga de producción. La aceptación y comprensión humana siguen reservadas para el análisis del usuario antes de la demo; las pruebas y el segundo agente no las sustituyen. El cierre/recarga de un formulario incierto sigue requiriendo consultar el historial antes de recrearlo, porque la clave sólo vive durante ese formulario.

Skills: `brainstorming` reutilizó el contrato ya aprobado; `systematic-debugging` y `tdd` exigieron reproducción antes del cambio y cobertura pública UI/API/comando; `interface-design` conservó patrones hospitalarios y simplificó sólo bloques vacíos; `playwright` verificó comportamiento y presentación; `code-review` separó estándares y cumplimiento funcional.

Las pruebas/activación del checkpoint inferior pertenecen al lote anterior y se conservan como historia. Sin commit/push ni cierre de issues o merge del PR.

## Checkpoint anterior: activado con aprobación simple

El 14/09 el usuario confirmó la ampliación de aprobación y autorizó la activación. Lote completo en localhost:8090 sobre `73ad575`, sin commit/push. PR40 sigue abierto en borrador. Las secciones inferiores de «preparado/no activado» conservan la evidencia del checkpoint anterior, ya superado por esta activación.

- Backend PostgreSQL16: `python manage.py test apps.finanzas --noinput --verbosity 0` → **261 tests OK**, 82,264s. Tras agregar contexto de permiso a ajustes anidados de costo: `python manage.py test apps.finanzas.test_aprobaciones_gastos apps.finanzas.test_reparto_api apps.finanzas.tests --noinput --verbosity 0` → **131 OK**, 36,091s. Dos fixtures sensibles se actualizaron para conceder aprobación expresamente al creador; los permisos reales no se tocaron.
- UI final: `CAUCE_URL=http://127.0.0.1:18990 node node_modules/@playwright/test/cli.js test --config=playwright.finanzas-ui.config.js --output=C:/Users/Juanito/AppData/Local/Temp/finanzas-aprobaciones-ui-final-20260914` → **75 OK**, 1,9min. Contratos HTTP simulados. Build Vite **742 módulos OK**. `git -c core.safecrlf=false diff --check` y `makemigrations --check --dry-run`: OK.
- Navegador → API real → PostgreSQL temporal: gasto100/cuenta100; pago30 desmarcado conserva confirmado0/pendiente100/reserva30/disponible70; aprobación deja neto30/pendiente70. Devolución10 con reducción conjunta pendiente no cambia confirmados; aprobar ambas deja cuenta90/neto20/pendiente70. Otro pago20 pendiente rechazado libera reserva sin mover neto20. Gasto50 pendiente aprobado; ajuste-10 pendiente conserva50, aprobarlo deja40. Historial y motivos visibles. Móvil390px sin desbordamiento; capturas inspeccionadas.
- Activación: pausa coordinada de frontend/backend/costos/repartos, respaldo completo en `C:/Users/Juanito/AppData/Local/Temp/finanzas-activacion-38-20260914-1928/base.dump`, restauración PostgreSQL aislada y comparación de cantidades/huellas en **78 tablas, 21.024 filas originales**. SHA256 respaldo: `6CC83A4C83CD3958C96341DF1453C121F38198F28078A267A4C71138AD2E786B`. También se conservan `codigo-73ad575.zip` y archivos compose.
- Las migraciones0022/0023/0024 se ensayaron sobre la copia y después se aplicaron a la demo. Las filas originales y columnas preexistentes conservaron su contenido. Django agregó sólo registros técnicos esperados de modelos/permisos y migraciones; **ninguna concesión financiera nueva**, ningún cargo/movimiento histórico. Ajustes anteriores conservan estado aprobado. 38 archivos copiados coinciden con staging normalizando CRLF.
- Verificación posterior: frontend8090 y health8010 HTTP200; backend y repartos saludables, costos activo; rutas nuevas resueltas y módulo Vite nuevo HTTP200; migraciones marcadas aplicadas, sin cambios pendientes de modelo. No se crearon transacciones de prueba en la demo ni se tocó la práctica8092.
- Retirados navegador, API18991, Vite18990, PostgreSQL temporal (incluida copia restaurada) y ambas redes de prueba. El respaldo local y las capturas se conservan. Última comprobación: demo HTTP200, backend/repartos saludables, latido de costos reciente y cero trabajos de reparto pendientes.

Riesgos/límites: elegir permisos del perfil de demo sigue a cargo del usuario; hoy no existen nuevas concesiones de dinero. Control mensual no enumera ajustes pendientes (el historial sí); no confundir un mes con carga completa con ausencia de correcciones por revisar. No se verificaron CI, Firefox/Safari, alto volumen ni todo el circuito clínico desde navegador. La aceptación y comprensión humana del usuario siguen pendientes para mañana. Si ocurre un incidente, detener operaciones preservando la base; no revertir borrando tablas de dinero. El respaldo es previo a nuevas operaciones y restaurarlo luego podría perderlas: requiere decisión y conciliación, nunca restauración automática.

Skills: brainstorming conservó el contrato confirmado y su alcance; systematic-debugging identificó las dos fixtures dependientes de aprobación implícita; Playwright comprobó interacción real, confirmados/reservas y presentación móvil. Trabajo paralelo separado en dinero, gastos/ajustes e interfaz, con integración y verificación central.

Diseño aprobado por el usuario el 14/09/2026; prioridad explícita: mantenerlo simple para el personal hospitalario. Continúa el circuito aprobado en #10/#12/#38. No sustituye los costos ni los reportes existentes.

## Contrato aprobado

- Una obligación por pagar nace explícitamente desde un gasto aprobado y vigente, con contraparte identificada. No convertir gastos históricos automáticamente en deuda.
- Un cargo por cobrar requiere atención completada y política administrativa de cobro explícita. Arancel separado del costo, paciente separado del pagador. Datos faltantes quedan para administración, sin preguntas clínicas nuevas ni deuda inventada.
- Sólo registrar dinero vinculado y hasta el pendiente. Sin anticipos, excedentes, movimientos libres, cajas, bancos ni facturación fiscal.
- Pagos/cobros/reintegros conservan originales, autoría, fecha efectiva y referencias. Fecha del dinero y mes económico son distintos.
- Devolver dinero puede mantener la obligación o acompañar una reducción. Una reducción previa se vincula sin aplicarla nuevamente. No modificar gastos, costos, stock ni repartos por esa devolución.
- Confirmar una devolución muestra el pendiente resultante; un cambio concurrente exige recalcular. Reintentos identificados no duplican movimientos.
- Permisos explícitos para consultar, registrar, corregir dinero y configurar cobros. Reutilizar institución, área, sensibilidad y auditoría; no conceder nuevos permisos automáticamente.

## Implementación por áreas exclusivas

### Ampliación confirmada: aprobación simple

- Gastos, ajustes manuales de gasto/costo, pagos, cobros, reintegros y reducciones muestran «Aprobado». Marcado inicialmente sólo si el usuario tiene el permiso de aprobación en el mismo contexto; en otro caso se guarda pendiente. El rol administrativo por sí solo no aprueba.
- Un pendiente no modifica gasto/costo confirmado, reparto, obligación vigente ni totales de dinero. Pagos/cobros pendientes reservan capacidad de registro; reintegros y reducciones reservan sus respectivos límites para evitar duplicaciones.
- Ejemplo: cuenta100, pago30 pendiente: confirmado0, pendiente100, por aprobar30, disponible para registrar70. Aprobar: confirmado30/pendiente70. Rechazar: confirmado0/pendiente100/disponible100.
- Aprobar/rechazar desde el mismo detalle, conservando originales, autoría y fecha de decisión. Rechazo con motivo. Reintegro con reducción conjunta tiene una sola decisión atómica. Se vuelven a verificar permisos, límites y estado bajo bloqueo.
- Ajustes históricos conservan efecto aprobado sin inventar autor de aprobación. Configuración de cobro y hechos clínicos automáticos no agregan una aprobación manual.
- Migración aditiva0024; sin otorgar permisos automáticamente. El usuario autorizó activar el lote completo en8090 con respaldo restaurado y verificado, migraciones y recarga mínima; nunca semillas. La revisión humana sigue reservada para mañana.

Implementación paralela: servicios de dinero/reservas, gastos/ajustes/consumidores e interfaz. Integración central: modelos, migración, reportes, pruebas PostgreSQL y activación protegida. La evidencia del lote anterior de abajo no valida por sí sola esta ampliación.

1. Backend dinero: obligaciones, movimientos, reducciones, claves de reintento, bloqueos, previsualización, API y pruebas.
2. Cobros: política versionada, captura del contexto al completar atención, pendientes administrativos y generación única de cargo; API y pruebas.
3. Interfaz: acciones desde gasto/cargo, pendiente visible, formularios breves y explicación del resultado; configuración separada de operación.
4. Integración: rutas, reporte de dinero real (brutos, devoluciones, netos), pruebas cruzadas y guía.

## Aceptación observable

- Obligación 100, pago 30: pendiente 70. Cargo 100, cobros 40 y 60: pendiente 0.
- Cargo cobrado 100, reintegro 30 manteniendo obligación: pendiente 30. Reduciendo a 70: pendiente 0.
- Una reducción ya registrada no vuelve a reducir el cargo. Deuda ajena a la reducción se conserva.
- Dos reintentos iguales producen un movimiento; dos operaciones reales con identidades distintas se conservan. Misma identidad y contenido diferente se rechaza.
- Operaciones concurrentes no superan pendiente ni reintegrable. No hay filtración entre áreas/instituciones ni de importes sensibles.
- Un movimiento de septiembre sobre gasto de agosto figura como dinero de septiembre; no altera el gasto de agosto.
- Configuración posterior no factura retrospectivamente atenciones anteriores ni cambia sus aranceles.

## Validación y activación

Base: `73ad575`, rama de continuidad `codex/finanzas-costos-incremento-1`. La demo monta ese worktree en vivo. Implementación preparada en el worktree separado `sistemadesalud-finanzas-dinero-demo` para conservar 8090 mientras se modifica esquema/código. Sin commits ni cambios de historia.

Validar con bases de prueba aisladas, incluidos PostgreSQL para bloqueos, pruebas UI y recorrido integrado. SQLite no demuestra concurrencia. Registrar comandos y límites al finalizar. Activación real exige autorización separada para copia de cambios, respaldo, migraciones aditivas, reinicios estrictamente necesarios y concesiones elegidas por el usuario. Sin semillas, reinicios, permisos ni migraciones automáticas sobre la demo.

La revisión y comprensión del usuario será antes de la demo, según su pedido. Ni pruebas ni revisión de otro agente sustituyen esa aceptación.

Skills: brainstorming para conservar el diseño confirmado; writing-plans no está disponible, se usa este plan del repositorio; interface-design para reutilizar el lenguaje y los componentes existentes sin rediseño.

## Resultado del lote — 14/09, validado en aislamiento

Implementados modelos y migraciones aditivas `0022_dinero`/`0023_cobros`, servicios monetarios, políticas de cobro, captura de nuevas atenciones, recuperación administrativa, API, reporte por fecha real e interfaz. Ningún commit/push ni activación real. El worktree original permanece limpio en `73ad575`.

### Evidencia reproducible

La red `finanzas-dinero-test-20260914` y PostgreSQL16 `finanzas-dinero-pg-20260914` fueron temporales. Base `finanzas_pruebas`, datos en tmpfs, sin volúmenes ni conexión a bases demo. Backend usó la imagen ya instalada `sistemadesalud-finanzas-demo-backend`, montando sólo el backend del staging. El puerto de navegador fue exclusivamente `127.0.0.1:18991`; frontend de prueba `127.0.0.1:18990`.

- `python manage.py test apps.finanzas --noinput`: **228 tests OK**, 64,512s, PostgreSQL. Incluye cobros simultáneos/recuperación concurrente, pagos simultáneos, reintegros simultáneos, colisión de clave entre reducción y devolución, controles de ámbito y sensibilidad, auditoría no disponible y regresiones existentes.
- `python manage.py makemigrations --check --dry-run`: **No changes detected**. Migraciones completas aplicadas satisfactoriamente en la base temporal.
- `CAUCE_URL=http://127.0.0.1:18990 node node_modules/@playwright/test/cli.js test --config=playwright.finanzas-ui.config.js --output=C:/Users/Juanito/AppData/Local/Temp/finanzas-dinero-final-ui-20260914`: **57 tests OK**, 1,5min (45 existentes + 12 dinero). Contratos HTTP simulados; no prueba integración por sí sola.
- `node node_modules/vite/bin/vite.js build`: **OK**, 741 módulos, después del último ajuste de permiso visible.
- `git diff --check`: **OK** con la configuración Git vigente. Una comprobación intermedia forzando `core.autocrlf=false` interpretó CRLF existentes como whitespace; no se alteró la codificación ni se hizo una reescritura cosmética para ese falso positivo.

### Recorrido financiero real adicional

Navegador Chromium → frontend → API real → PostgreSQL temporal, con usuario administrativo y datos sintéticos exclusivos de prueba:

1. Crear cuenta desde gasto aprobado100; registrar pago30; cuenta100/neto30/pendiente70 persistidos.
2. Devolución recibida10 manteniendo cuenta: previsualización y persistencia cuenta100/neto20/pendiente80.
3. Configurar desde pantalla arancel100 y responsable independiente del paciente. Una atención anterior sin política no generó cargo; la siguiente sí.
4. Registrar cobros40+60 desde pantalla; único cargo100, pendiente0. Devolver30 reduciendo cuenta: original100 conservado, cuenta70/neto70/pendiente0, reducción y devolución trazables.
5. Reporte real: cobros brutos100, pagos30, reintegros de cobros30 y de pagos10, cobros netos70/pagos netos20/diferencia50, cinco movimientos.
6. Nueva política con responsable faltante: nueva atención pendiente, completada desde pantalla administrativa sin asignarla al paciente ni repetir cargos anteriores.
7. Capturas reales de detalle, previsualización, resumen y móvil inspeccionadas; 390px de viewport y 390px de documento, sin desbordamiento horizontal. Sin errores de página en el recorrido.

Las atenciones de esa prueba se generaron mediante `registrar_atencion_completada`, el servicio invocado por el flujo clínico, no operando la pantalla clínica completa. Su gancho existente en motor sólo corre tras atención completada. No se verificaron CI, Firefox/Safari, carga a gran escala, flujo clínico íntegro desde navegador ni aceptación humana. Las nuevas claves de reintento de UI duran mientras se conserva el formulario: ante una respuesta incierta no cerrar/recrear sin consultar historia.

Capturas: `C:/Users/Juanito/AppData/Local/Temp/finanzas-dinero-preview-real-20260914.png`, `finanzas-dinero-cargo-real-20260914.png`, `finanzas-dinero-desktop-real-20260914.png`, `finanzas-dinero-mobile-resumen-20260914.png`. Las pruebas fueron retiradas al terminar; se conserva código y evidencia, no la base sintética.

### Lectura sugerida antes de activar

- `dinero.py`: `estado_obligacion`, `registrar_movimiento`, `previsualizar_reintegro`, `reintegrar_movimiento`. Revisar límites, clave de reintento y versión confirmada.
- `cobros.py`: `capturar_cobros_atencion` y `resolver_pendiente_cobro`; política por fecha original y ausencia de cargos retrospectivos.
- `api_reportes_dinero.py`: agrupación sólo de movimientos por fecha efectiva, sin unirlos de forma multiplicativa a ajustes.
- `DineroFinanzas.jsx` y `ConfiguracionCobros.jsx`: tres importes, responsable y resultado antes de confirmar; lectura y escritura del mismo ámbito.

Riesgos residuales: fallo incluso al insertar el ancla de captura necesita investigación técnica (no reconstrucción histórica automática); listas con historiales muy grandes requieren medición/paginación adicional; cuentas y gasto se corrigen explícitamente, nunca se sincronizan solos. No se implementó ampliación positiva de obligación, anticipos, responsables múltiples, cobertura ni cajas.

La activación requiere autorización explícita para respaldo verificable, sincronización al worktree de la rama, migraciones0022/0023 y recarga coordinada mínima. Sin semillas ni nuevas concesiones automáticas. No revertir eliminando tablas con dinero registrado; ante incidente conservar datos y deshabilitar la operación mientras se investiga. El usuario reservó su comprensión y aceptación para mañana: siguen pendientes, no se deducen de estas pruebas.

Skills adicionales: systematic-debugging separó fallos de entorno/harness de fallos de producto; Playwright permitió inspección visual y recorrido real; vercel-react-best-practices ayudó a acotar consultas y estado en la implementación de interfaz.
