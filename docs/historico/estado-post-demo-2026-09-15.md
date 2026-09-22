# Finanzas y costos: cierre de demo y continuidad

Fecha: 15/09/2026. PR de entrega: [#40](https://github.com/Mkdir-arg/SistemaDeSalud/pull/40), base `main`. Este documento reemplaza los estados operativos anteriores; los planes conservan sus decisiones y evidencias históricas, no describen necesariamente el entorno actual.

**Cierre técnico:** código consolidado en `f891079`, con **739 pruebas backend y 118 UI aprobadas**, build, auditor de clases, comprobaciones de Django y consistencia de migraciones sin errores. El commit posterior agrega documentación, no modifica ese código validado. Preparado para revisión/aceptación final en el mismo PR, sin merge automático. La configuración y los datos de 8090 se preservaron.

## Resultado y prioridad confirmada

La demo se realizó con el escenario **Hospital General Los Aromos**, completamente ficticio y con historia simulada de octubre de 2025 a septiembre de 2026. El módulo ya permite explicar configuración, atención, costos, gastos, aprobación, reparto y dinero. No es contabilidad general ni facturación a obras sociales.

Después de la demo el usuario priorizó fuertemente **cobros de pacientes y, especialmente, conexión con obras sociales e ingreso de sus usuarios al sistema**. El feedback adicional de la última interfaz queda para después; no se inventan observaciones ni se mezclan con este cierre. La nueva prioridad no cambia retroactivamente los criterios con que se construyó la demo.

## Qué está entregado

| Parte | Comportamiento disponible | Evidencia principal |
| --- | --- | --- |
| Configuración | Prestaciones, componentes, valores versionados y vigencias; códigos automáticos opcionalmente reemplazables al crear. | `serializers.py`, `test_codigos_catalogo.py`, `CostosAtencion.jsx`, `finanzas-vigencias-demo.spec.js` |
| Atención y costo directo | Hecho económico único al completar la atención; componentes congelados, valores, faltantes y ajustes separados. El worker recupera costos pendientes sin quedar monopolizado por el primer lote fallido. | `services.py`, `procesar_costos.py`, `test_revision_circuito.py`, pruebas del motor clínico |
| Gastos | Registro, aprobación según permiso, ajustes, reemplazos e historial. Los importes pendientes de aprobación no integran el confirmado. | `services.py`, `test_aprobaciones_gastos.py`, `tests.py` |
| Gastos mensuales | Configuración recurrente, referencia opcional y declaración de carga completa/no corresponde. Configurar no crea facturas ni dinero. | `calendario.py`, `test_calendario.py`, `ControlesFinanzas.jsx` |
| Repartos | Primera base por cantidad de atenciones elegibles, verificación de actividad, versiones e importe sin distribuir; actualización en segundo plano. | `procesamiento.py`, `test_procesamiento.py`, `test_reparto_api.py` |
| Cuentas y dinero | Cuenta por pagar explícita desde gasto aprobado; cargos de atención por política explícita; parciales, aprobaciones, reducciones, devoluciones y reintentos idempotentes. | `dinero.py`, `cobros.py`, `test_dinero.py`, `test_cobros.py`, `test_aprobaciones_dinero.py` |
| Reportes | Gastos/aprobaciones/distribución y evolución de referencias; dinero por fecha real, separado del mes económico del origen. | `api_reportes.py`, `api_reportes_dinero.py`, `test_reportes.py`, `test_reportes_dinero.py` |
| Permisos y UX | Acceso desde Inicio; acciones por pestaña y menú a la derecha; edición de permisos por membresía en Editar usuario, bloques plegables y columnas independientes; retiro del modal anterior. | `Inicio.jsx`, `Usuarios.jsx`, `editor_permisos.py`, `EditorPermisosFinancieros.jsx`, `test_editor_permisos.py`, pruebas `finanzas-*-demo.spec.js` |

Los archivos backend de esta tabla están en `backend/apps/finanzas/`, salvo el motor clínico; los componentes de finanzas, en `frontend/src/pages/finanzas/`; las pruebas de interfaz, en `frontend/e2e/`.

## Reglas que deben conservarse al continuar

- **Costo interno ≠ arancel ≠ cargo ≠ cobro.** El costo de atender no indica cuánto debe el paciente. El arancel tampoco crea deuda sin decisión de cobro y responsable explícito.
- Sólo movimientos vinculados, hasta el pendiente disponible. Sin anticipos, sobrepagos ni movimientos libres.
- Lo pendiente de aprobación se ve aparte y reserva capacidad, pero no aumenta pagado/cobrado confirmado. Rechazar libera la reserva; aprobar la convierte en confirmado, sin volver a sumarla.
- «Aprobado» comienza marcado sólo si el actor tiene permiso para aprobar ese alcance; puede desmarcarlo. No se otorga aprobación por ser administración central.
- Devolver dinero y reducir deuda son decisiones distintas. Si una reducción ya existe, se vincula sin duplicarla. No se editan ni borran originales.
- Los repartos vigentes explican parte de los gastos aprobados: **aprobado = distribuido + sin distribuir**. No son otro gasto que se deba sumar.
- Los permisos financieros no dan acceso clínico. La edición de concesiones es atómica, valida áreas/sensibilidad en servidor y rechaza modificaciones sobre una versión desactualizada.
- El cambio de una política o valor no reescribe atenciones ni cargos históricos. No hacer backfill automático de deuda antigua.
- `CoberturaActividadCosteable` significa completitud de actividad para repartir costos; **no es cobertura de obra social**.

## Contraste de issues

Se inspeccionaron descripción, comentarios y checklists de [#33](https://github.com/Mkdir-arg/SistemaDeSalud/issues/33), [#9](https://github.com/Mkdir-arg/SistemaDeSalud/issues/9), [#10](https://github.com/Mkdir-arg/SistemaDeSalud/issues/10), [#11](https://github.com/Mkdir-arg/SistemaDeSalud/issues/11), [#12](https://github.com/Mkdir-arg/SistemaDeSalud/issues/12) y [#34–#39](https://github.com/Mkdir-arg/SistemaDeSalud/issues?q=is%3Aissue+sort%3Acreated-asc). Todos seguían abiertos al revisar; no se cerraron ni se marcaron checklists automáticamente.

| Issues | Estado respaldado por código, no cierre de épica |
| --- | --- |
| #33 | Incremento operativo amplio, pero módulo integral todavía parcial. |
| #9–#10 | Catálogo, componentes, vigencias, permisos y configuración mínima de cobro presentes. Otras fuentes y alcance integral siguen pendientes. |
| #11–#12 | Hecho, costo directo, recuperación de costos y cargo mínimo implementados. Cuenta por episodio, historial integral y otras fuentes no se declaran terminados. |
| #36 | Gastos, aprobaciones, configuración mensual e historial presentes. Deduplicación documental/idempotencia de altas y aceptación integral continúan pendientes. |
| #37 | Primera base por atenciones disponible; no todas las bases de reparto ni costos institucionales/disponibilidad. |
| #38 | Lote vinculado implementado en Los Aromos. Revisión y recuperación inicial se tratan abajo. No equivale a cajas, bancos, facturación o portal externo. |
| #39 | Reportes operativos y dinero disponibles; no reportería integral de fuentes aún inexistentes. |
| #34–#35 | Roadmap; fuera del incremento entregado. |

Hay checkpoints obsoletos en #33/#38 («sin activar», staging) y checklists de #11/#12 que aún no reflejan la corrección del recuperador por lotes. Son diferencias de seguimiento, no evidencia de que el código falte. La descripción anterior del PR también excluía #38/#39 y no reflejaba la edición integrada de permisos; debe leerse su resumen actualizado, no ese alcance histórico.

## Revisión técnica: Standards

Revisión independiente de zonas de riesgo, contra `main` en `f91dbbb` e incluyendo los cambios locales posteriores a `73ad575`. No es una inspección exhaustiva línea por línea de todo el PR.

- Los bloqueos por obligación, claves de reintento, reservas y sumas de reportes son coherentes con el contrato y tienen pruebas PostgreSQL. Las migraciones de aprobación conservan el efecto de históricos sin inventar aprobadores.
- **Auditoría con alcance diferente:** los POST de dinero/cobros incluyen auditoría de respuesta y rollback si ésta falla. Los POST de gastos y ajustes de gasto/costo conservan autoría de escritura, pero no todos generan un `AccesoFinanciero` por su respuesta monetaria; sus GET sí lo hacen. No se detectó por esto acceso fuera de permisos. No prometer auditoría de lectura transversal de todo POST: uniformarla es un pendiente explícito.
- No se detectaron nuevos P0/P1 confirmados en los hotspots inspeccionados. Esto no reemplaza aceptación humana, revisión de infraestructura ni pruebas de producción.

## Revisión funcional: Spec

- Se respeta el lote autorizado de dinero y sus límites. La siembra manual y los retoques de UX tienen autorización previa; no son expansión no solicitada.
- Se corrigió en el README la mezcla entre la antigua demo y Los Aromos, los nombres visibles «Gastos mensuales» y el alcance real de migraciones/aprobación.
- **Recuperación inicial de cobros corregida:** se confirmó que, si fallaba incluso crear `SnapshotCobroAtencion`, quedaba el hecho pero no aparecía como recuperable. El usuario pidió resolverlo y aclaró que no existen históricos productivos que deban preservarse como una categoría distinta. Se reutiliza `HechoAtencionCosteable` como fuente durable: se listan hechos sin captura o con captura incompleta, y se crea/reutiliza el snapshot bajo bloqueo del hecho. No se requiere nueva columna, migración, proceso masivo ni bloqueo de la atención por un fallo de captura. Las políticas siguen sujetas a fecha de vigencia y fecha de registro anteriores a la atención. GET requiere lectura sensible; POST, lectura y registro sensibles en institución y área de origen. Repetir POST después de una respuesta perdida sigue siendo válido aunque la captura ya esté terminada. La auditoría y la recuperación comparten transacción.

El listado `/api/pendientes-cobro/recuperables/` identifica ahora sus filas por hecho: `id == hecho`; antes `id` era el identificador del snapshot. El POST conserva `{ "hecho": id }` y la interfaz ya usa ese campo para recuperar. No se ofrece reconstrucción automática: un hecho anterior sin snapshot puede aparecer en la lista y requiere decisión administrativa explícita. Una política creada después de esa atención no le genera un cargo al recuperarla.

La alternativa de agregar una marca aditiva para separar fuentes históricas se descartó con esa aclaración del usuario. Exigir que el snapshot se guarde para confirmar la atención también se descartó porque ampliaría el bloqueo del trabajo clínico por un problema financiero. La solución elegida conserva la frontera durable que el motor ya tenía; si falla la persistencia del propio hecho, no se confirma una atención sin esa fuente económica.

La revisión independiente del cambio de recuperación no encontró bloqueantes confirmados; verificó bloqueo por hecho, filtros por área original, combinación de permisos, repetición del POST terminado, cortes temporales y rollback de auditoría. No se eliminó la prueba de no aplicar una política posterior: se adaptó la expectativa anterior que impedía toda recuperación sin snapshot a la decisión nueva del usuario.

## Próximo desarrollo: paciente y obra social

### Base existente para reutilizar

`Ciudadano` (`backend/apps/registros/models.py`) ya tiene identidad y documento por institución; `obra_social` es **texto libre** editable desde Padrón. `HechoAtencionCosteable` conserva paciente, caso y atención; `PoliticaCobro` y `PendienteCobro` conservan arancel/pagador de la atención, y `ObligacionFinanciera` permite seguir la deuda y sus movimientos. El pagador de la política es texto fijo por prestación: **no se deriva de la obra social del paciente**.

Usuarios por email/JWT, membresías hospitalarias y concesiones financieras son mecanismos reutilizables, no un portal de financiadores ya resuelto. No hay catálogo de obras sociales, afiliaciones/planes/convenios, copagos estructurados, permisos por financiador, API de una obra social ni login dedicado a sus operadores. No hay vínculo de autenticación Usuario–Ciudadano para un portal de pacientes.

### Prioridad confirmada y definiciones todavía abiertas

El ingreso de usuarios de obra social es una prioridad explícita; no hace falta volver a preguntar si interesa ese actor. Lo que falta definir es **qué puede hacer y ver**, además del alcance de «conexión»:

1. Primera obra social y operación objetivo: consultar cargos, autorizar prestaciones, recibir una presentación, auditarla o informar pagos. Integración por API requiere contrato externo verificable; no se presume que exista.
2. Responsable por cada atención: particular, tercero u obra social; cobertura/copago y quién confirma elegibilidad. Una afiliación por sí sola no prueba que se deba cobrarle todo a ese financiador.
3. Información mínima visible para sus usuarios y vínculo con instituciones/cargos autorizados. No concederles membresía hospitalaria amplia como atajo ni abrirles historias clínicas completas.
4. Arancel aplicable y vigencia: convenio, prestación y cobertura al momento de la atención; qué pasa con faltantes, rechazos y cambios posteriores.

**Recomendación del agente, aún no diseño aprobado:** comenzar por un recorrido vertical pequeño que incluya al actor prioritario: administración identifica financiador/responsable de una atención; el operador de esa obra social inicia sesión y ve únicamente los cargos autorizados a su entidad; el cobro se registra sobre la obligación correcta. Un cambio de cobertura no reasigna el histórico. Definir antes si ese primer recorrido incluye sólo consulta o también autorización/presentación; no implementar un portal vacío de cuentas fiables ni automatizar un intercambio externo sin contrato.

### Backlog separado

- Prioridad alta: identidad de financiador/afiliación, responsable y eventual copago; consulta de cuenta por paciente/obra social; acceso externo aislado; luego el primer intercambio real que se acuerde.
- Posterior: conciliación/presentaciones y convenios avanzados según descubrimiento; cajas/bancos/fiscal fuera de este incremento; otras fuentes de costo y bases de reparto; reportería integral; uniformidad de auditoría de POST financieros.
- Diferido por el usuario: feedback de la última interfaz. No se describen cambios concretos porque ese feedback aún no fue recibido.

## Validación y operación

En esta revisión, antes de la corrección de recuperación, pasaron **336 pruebas de Finanzas y Accounts en PostgreSQL** (167,300 s). Build frontend: **742 módulos**, sin error. El pase UI final dio **118/118** (3,5 min) y la auditoría de clases pasó, con 240 clases revisadas. Tras corregir la recuperación pasaron **30 pruebas de cobros** (52,600 s), incluidas fallo inicial de snapshot, política original, reintento, permisos, rollback de auditoría y concurrencia PostgreSQL. `manage.py check` y `makemigrations --check --dry-run` siguieron sin problemas; no se requiere una migración adicional.

La ampliación inicial a Casos y Auditoría ejecutó 398 pruebas y encontró tres fallos: dos por 12 advertencias del esquema OpenAPI y uno por inventario de rutas anterior a Finanzas. Se declararon los tipos reales y el nombre del enum financiero, sin silenciar advertencias ni modificar payloads/permisos. El inventario ahora exige autenticación y la barrera financiera propia, con pruebas HTTP de rechazo sin concesiones. El subconjunto de esquema, inventario y checklist de despliegue pasó **17/17** (9,050 s). La regresión conjunta final ejecutó **739 pruebas, todas OK, en 252,064 s**, sobre PostgreSQL y código congelado; incluyó Finanzas, Accounts, Casos y Auditoría.

El primer pase UI dio 117/118 porque una medición cruzó la carga tardía de Inter: el cambio de fuente desplazaba 21,96875 px el grupo de controles, exactamente el delta fallido; alternar vistas con la fuente cargada lo desplazaba 0 px. El test ahora espera `document.fonts.ready` sin relajar tolerancias. El auditor confundía la propiedad CSS `fill-opacity` con una clase; se agregó a la excepción documentada de propiedades, como `stroke-width`. No se cambió el diseño para satisfacer esas comprobaciones.

Comandos reproducibles, siempre sobre un entorno de prueba con base separada:

```text
python manage.py test apps.finanzas apps.accounts apps.casos apps.auditoria --noinput --verbosity 1
python manage.py check
python manage.py makemigrations --check --dry-run
cd frontend
npm run build
npm run auditar
npx playwright test --config playwright.finanzas-ui.config.js
git diff --check
```

Las pruebas de interfaz de esa configuración simulan HTTP: verifican comportamiento de pantalla, no la integración real autenticada. `finanzas-feedback.spec.js` corresponde a una demo anterior y no debe ejecutarse sobre Los Aromos como si fuera un recorrido vigente. No se repitió la siembra ni se modificaron datos de 8090 para probar. La prueba de checklist de despliegue usa ajustes de prueba seguros; no certifica ni cambia la configuración de desarrollo de 8090. No se ejecutaron las suites de aplicaciones ajenas al alcance revisado.

Las bases de pruebas se crean y retiran con el runner de Django; no se usa `salud` como base de test. En el proceso de validación se fijaron `DATABASES['default']['NAME'] = 'finanzas_postdemo_validation'` y `DATABASES['default']['TEST']['NAME'] = 'test_finanzas_postdemo_final_20260915'` antes de invocar el runner; no se editaron ajustes persistentes. Los errores y respuestas 403/404/409/503 del log corresponden a pruebas negativas deliberadas. Los artefactos quedaron fuera del repositorio, en la carpeta temporal local.

El repositorio no contiene workflows de GitHub Actions y el PR no reportaba checks. **Ausencia de CI no significa CI aprobada**. La evidencia local no certifica un despliegue productivo ni sustituye el entendimiento del usuario.

### Migraciones, activación y reversión

El PR incorpora el módulo completo desde `main`: migraciones financieras 0001–0024, no sólo las últimas tres. 0022 agrega obligaciones/movimientos; 0023 políticas/captura de cobros; 0024 aprobación de movimientos y ajustes, manteniendo aprobados los históricos que ya tenían efecto. No se conceden automáticamente todas las acciones financieras por ser administrador.

Antes de desplegar a otro entorno: respaldo consistente y restauración probada, revisión de migraciones, aplicación antes de levantar código que dependa del nuevo esquema, frontend compatible y workers de costos/repartos supervisados. El seed de Los Aromos no es parte del arranque y nunca debe ejecutarse para actualizar una base con datos.

Revertir código **no** revierte pagos ni constituye un rollback seguro de esquema. Con actividad nueva, preferir corrección hacia adelante y conciliación explícita. Revertir migraciones que eliminan tablas/campos monetarios puede perder historia; restaurar un respaldo perdería escrituras posteriores. Ambas acciones necesitan decisión del responsable, ventana operativa y tratamiento de esa diferencia, no un comando automático.

8090 sigue siendo desarrollo local, no una publicación segura de producción. El cierre no abre túneles, cambia secretos, reinicia servicios, migra ni altera la base de demo. No se incorporan credenciales, respaldos ni archivos privados al PR.

### Aceptación para incorporar

Publicar el PR no autoriza merge automático. La evidencia técnica está consolidada; queda aceptación humana de alcance/riesgos. Dos escenarios a discutir con el usuario: un cobro repetido por respuesta perdida y un cargo atribuido a la obra social equivocada. El primero tiene protección de reintentos; el segundo requiere el futuro contrato de identidad/cobertura, no inferencias a partir de texto libre. No se da por validado el entendimiento del usuario sobre implementación, detección de fallos o reversión sólo porque haya participado en la demo.

Skills utilizadas: `code-review` separó Standards/Spec y habilitó revisiones independientes; `pr-reviewer-github` fijó base, alcance y comprobación de PR; `systematic-debugging` exigió reproducir los hallazgos antes de corregirlos; `brainstorming` permitió contrastar las alternativas de recuperación y descartar la migración tras la aclaración del usuario. La comprensión y aceptación humanas no se dan por demostradas sólo por pruebas o revisión de agentes.
