# Seguimiento hospitalario de cobertura y cobros

## Problema y alcance

El hospital ya puede generar obligaciones y registrar cobros, ajustes y reintegros. Falta reunir sus fuentes de cobertura para distinguir cuentas por cobrar, importes sin responsable y hechos cuya captura financiera no terminó. El usuario autorizó continuar este bloque, aplicar las recomendaciones y guardar los avances en el PR #41.

Se agrega «Seguimiento de cobros» en Coberturas y copagos. Reutiliza el detalle de cuenta y las operaciones existentes de Finanzas. No crea otro libro de dinero, conciliación bancaria, facturas, lotes de pagos, tablas ni permisos nuevos.

## Resultados observables

1. **Cuentas:** una fila por obligación de cobertura, incluyendo financiador, paciente y acuerdos posteriores. Permite abrir su cuenta y operar según las concesiones existentes. Totales del conjunto filtrado, sin sumar dos veces una prestación por tener varios movimientos o ajustes.
2. **Pendientes administrativos:** prestaciones realizadas con arancel/evaluación incompleta, reparto sin terminar o diferencia que nadie aceptó asumir. Los importes desconocidos permanecen desconocidos; una diferencia sin responsable no se trata como deuda exigible.
3. **Captura pendiente:** hechos asistenciales del circuito de cobertura sin snapshot o con captura incompleta, incluso cuando todavía no existe reserva. Son hechos registrados, sin inventar importes ni responsables. La gestión y recuperación conservan las acciones existentes.

## Contrato de consulta

`GET /api/seguimiento-cobros/` exige institución y `ver_dinero` en el ámbito consultado. Vistas `cuentas`, `pendientes` y `captura`, paginadas en servidor. Fecha inicial/final inclusiva de **la prestación**, área de origen, búsqueda; las cuentas admiten cobertura del caso, responsable y situación financiera. Los pendientes administrativos admiten financiador/estado; captura no filtra financiador, responsable ni estado porque pueden ser desconocidos y rechaza esas combinaciones explícitamente.

El período selecciona prestaciones; sus cobros y ajustes se consideran hasta el momento de la consulta, aunque se hayan registrado en otro mes. Para dinero recibido por fecha efectiva sigue existiendo el reporte de Dinero. Se conserva la fecha de generación y se explica que es una consulta operativa, no un cierre contable.

Las cuentas se relacionan mediante las FK de distribución y resolución, nunca interpretando el texto de contraparte. El listado de pendientes usa hospital/área del hecho original. Cada salida, total y opción de filtro respeta institución, área y sensibilidad. Roles clínicos, de financiador o de resolución administrativa por sí solos no habilitan leer movimientos de dinero. La captura aún incompleta exige lectura sensible porque su sensibilidad puede ser desconocida.

## Importes y estados

- Obligación actual = original + ajustes aprobados.
- Cobrado neto = cobros aprobados − reintegros aprobados.
- Por cobrar = máximo(actual − neto, cero), calculado **por cuenta** antes de sumar.
- A devolver = máximo(neto − actual, cero), por cuenta. No compensa deuda de otra persona ni del otro responsable.
- Cobros, reintegros y reducciones por aprobar se muestran aparte; los rechazados no modifican saldos.
- Una cuenta puede tener deuda y movimientos por aprobar simultáneamente. «Saldada» exige saldo cero y ausencia de operaciones pendientes de aprobación.

Un helper SQL de sólo lectura en `finanzas/saldos.py` consulta subconsultas independientes para ajustes/movimientos; se verifica contra `estado_obligacion`. Las operaciones de escritura y su bloqueo transaccional no cambian. Esto evita traer todo el período al navegador o bloquear todas las cuentas para obtener un total.

## Seguridad y validación

Se reutiliza la auditoría financiera estricta, agrupada por institución/área/sensibilidad/mes del conjunto que sustenta el reporte. Si no puede persistir, no se entrega la respuesta. Sin caché compartida. El detalle de cuenta vuelve a validar su acceso y cualquier operación conserva los permisos propios del dinero.

Pruebas previstas: totales contra cuentas, devoluciones sin compensación, acuerdos posteriores, varias aprobaciones/rechazos sin multiplicar importes, meses diferentes, paginación, origen conservado tras traslado, permisos negativos, sensibilidad desconocida, captura faltante, auditoría fallida y UI con filtros persistidos/invalidados tras registrar dinero. Demo aislada con datos ficticios; no se interviene localhost:8090 ni se migran datos reales.

Estas decisiones son recomendaciones del agente dentro del alcance autorizado. Se eligió consultar las fuentes existentes frente a crear conciliaciones persistidas o consolidar un nuevo libro: el incremento queda acotado y mantiene una única operatoria de dinero. Quedan fuera las autorizaciones previas y la aceptación del piloto.

## Resultado y evidencia — 16/09/2026

Implementación en `financiadores/seguimiento.py`, `finanzas/saldos.py` y `finanzas/api_seguimiento_cobertura.py`; interfaz en `SeguimientoCobros.jsx`, integrada a `CoberturasHospital.jsx`. La API permanece en Finanzas para cumplir su barrera común de autenticación y permisos. La auditoría admite identificar explícitamente el recurso y la vista, conservando el comportamiento de sus usuarios anteriores.

Se conservan tres vistas paginadas porque las bandejas administrativas previas no ofrecen el contrato financiero de permisos, totales y faltantes de captura. Sus operaciones de revisión y recuperación sí se reutilizan. El detalle de cuenta sigue siendo `DetalleCuenta`, sin otra implementación de cobros.

| Criterio | Evidencia |
| --- | --- |
| Saldos por responsable, agregados sin duplicación, devoluciones sin compensar deuda ajena | `test_sumatorias_sin_producto_cartesiano_y_paridad_con_dinero`, `test_saldo_a_devolver_no_compensa_deuda_del_otro_responsable` y acuerdos vinculados por FK |
| Período de prestación y origen conservado tras traslado | `test_fecha_filtra_prestacion_y_no_fecha_de_movimiento`, `test_traslado_del_caso_no_reescribe_origen_ni_alcance` |
| Alcance financiero aplicado a filas, opciones y totales | Pruebas de permisos clínicos/financiador/resolución insuficientes, hospital ajeno, concesión por área, sensibilidad y registros sin área |
| Importe desconocido sin deuda inventada | Pruebas de evaluación/arancel, captura con y sin snapshot, política inexistente y sensibilidad no verificable |
| Auditoría de todo el conjunto antes de entregar | Pruebas de páginas, vistas y rollback al fallar el segundo grupo; respuesta 503 sin importes |
| Cobrar desde el detalle actualiza el seguimiento | E2E del modal y recorrido real con $3.000 cobrados, $5.000 pendientes al financiador y $2.000 al paciente |
| Una página vacía tras saldar su última cuenta se puede recuperar | E2E de 26 a 25 cuentas y error 404 ajeno a paginación; se vuelve a la primera página conservando filtros |

Validación final del incremento:

- **347/347 pruebas en PostgreSQL 16**, sin omisiones, 108,517 s: financiadores, dinero, aprobaciones, cobros, reportes de dinero y barreras de permisos/esquema de Casos.
- **30/30 focales en SQLite**, 2,730 s, antes del traslado mecánico del ViewSet a Finanzas. PostgreSQL y OpenAPI se repitieron después del traslado. La diferencia de tratamiento de JSON `null` entre motores quedó corregida y cubierta: una evaluación sin política no presume sensibilidad pública.
- **69/69 pruebas Playwright**, API simulada, 1,1 minutos; incluyen 13 del nuevo seguimiento y las regresiones del portal y circuito clínico. Build Vite correcto: 751 módulos, 3,88 s.
- `check`, OpenAPI con `--validate --fail-on-warn` y `git diff --check`: correctos. Este incremento no agrega modelos, migraciones, dependencias ni concesiones financieras.
- Demo con navegador/API/base reales: un cobro parcial aprobado desde el modal, actualización automática del saldo, pendiente con importe desconocido, auditoría y un solo movimiento persistido. Escritorio y móvil inspeccionados; tabla con desplazamiento horizontal contenido, sin desborde del documento ni errores JavaScript. La preparación agrega sólo una atención ficticia con los servicios existentes y conserva los datos previos mediante respaldo.

```text
python manage.py test apps.financiadores apps.finanzas.test_dinero apps.finanzas.test_aprobaciones_dinero apps.finanzas.test_cobros apps.finanzas.test_reportes_dinero apps.casos.test_permisos_barrida apps.casos.test_esquema --settings=config.settings_financiadores_postgres_test --noinput
python manage.py test apps.financiadores.test_seguimiento --settings=config.settings_financiadores_test --noinput
python manage.py spectacular --settings=config.settings_financiadores_test --validate --fail-on-warn --file <archivo-temporal.yaml>
npx playwright test --config playwright.financiadores-ui.config.js
npm run build
```

Claude revisó el diseño; su revisión final no se completó porque agotó el límite de sesión. Una revisión independiente de Codex encontró el problema de página inválida tras cobrar y verificó su corrección y el traslado de la API. Es evidencia estática adicional, no otra ejecución de pruebas ni aceptación humana.

Skills: `brainstorming` acotó el bloque sobre decisiones aprobadas; `interface-design` conservó I-Core Salud y el detalle financiero; `systematic-debugging` guio el diagnóstico del JSON nulo; `playwright` verificó el recorrido real; `pr-reviewer-github` estructuró la revisión independiente, sin publicar comentarios de revisión.

## Límites y siguiente bloque

No se ejecutó la suite global completa ni una prueba de carga con volúmenes hospitalarios. Las consultas SQL y la cantidad de grupos de auditoría requieren medición antes del piloto. El reporte es operativo: las cuentas pueden cambiar durante consultas concurrentes; no se ofrece como cierre contable ni instantánea inmutable. El detalle vuelve a validar el saldo y los permisos antes de cualquier operación.

Dos riesgos concretos quedaron cubiertos: contar varias veces una obligación con varios movimientos, y exponer una evaluación incompleta sin conocer su sensibilidad. Un tercero, perder la navegación al saldar la última fila, motivó la corrección de interfaz. La reversión de este bloque retira su lectura y pantalla; debe conservar cuentas, movimientos y auditorías generados con las operaciones existentes. No se eliminan datos para revertirlo.

La **exportación hospitalaria de cuentas y pendientes con los mismos filtros, permisos y auditoría**, recomendada después del seguimiento, se implementó en el incremento siguiente documentado abajo. Facilita el intercambio y la conciliación con financiadores. No implica conciliación bancaria automática, emisión fiscal ni pagos masivos. La revisión del piloto y la comprensión/aceptación por parte del usuario siguen pendientes; la instrucción de continuar automáticamente no se presenta como aceptación de incorporación.

## Exportación hospitalaria — alcance autorizado el 16/09/2026

El usuario pidió continuar el bloque recomendado. Se incorpora `formato=csv` al mismo endpoint, conservando la selección y autorización de sus tres vistas. La descarga incluye todas las páginas del conjunto filtrado, hasta 5.000 filas; si lo supera, se rechaza sin archivo parcial. El JSON informa ese límite para mostrarlo en la interfaz.

Se recomienda CSV UTF-8 con BOM, punto y coma y coma decimal, como la exportación de actividad existente. Reutiliza su protección de texto frente a fórmulas, sin transformar identificadores en números de precisión limitada ni interpretar nombres como fechas. No se agrega un generador de hojas XLSX ni un trabajo asíncrono: el volumen se acota y no requiere infraestructura ni dependencias nuevas.

Cada vista tiene encabezados propios. Cuentas exporta importes originales, ajustes aprobados, obligación actual, cobrado neto, deuda, devoluciones y registros por aprobar en ARS. Pendientes conserva importe desconocido vacío y estado/motivo legibles. Captura no inventa responsables ni importes. Sólo se incluyen los campos financieros ya consultables, el hospital y la fecha de generación; no se agregan documentos, historia clínica ni evidencia de aceptación. IDs y textos libres (nombres, prestaciones y motivos) llevan un apóstrofo inicial para conservarlos como texto, incluso si parecen números o fechas. Ese prefijo es una convención del CSV y puede verse en otros lectores; no modifica los datos del sistema. Las etiquetas fijas, fechas y cantidades monetarias conservan su formato propio.

El archivo se construye con un único conjunto materializado y acotado; los grupos auditados se calculan desde esas mismas filas. No se transmite contenido antes de persistir toda la auditoría. Cada registro identifica `seguimiento-cobros` y `exportar_<vista>`. Si falla un grupo, se revierte la auditoría parcial y se devuelve 503 sin archivo. Se mantienen `private, no-store` y `nosniff`.

El botón «Exportar CSV» usa los filtros aplicados, excluye la página y se deshabilita ante cambios sin aplicar, carga, error, falta de permiso o exceso del límite. Comunica que el archivo reúne todas las páginas y que su estado corresponde al momento de la descarga. La exportación vuelve a validar en servidor permisos y datos; no fija el saldo de una consulta anterior.

Aceptación técnica: comparar JSON/CSV de las tres vistas y de múltiples páginas; rechazar filtros incompatibles y límites excedidos; verificar permisos por hospital/área/sensibilidad, texto peligroso, decimales negativos y desconocidos; simular fallos de auditoría; comprobar descargas y errores desde la interfaz y contrastar un archivo de la demo con su base. Se validan regresiones del exportador de actividad al extraer exclusivamente la función compartida de texto seguro.

### Resultado de la exportación y validación

Implementado en `seguimiento_csv.py` y en el mismo `SeguimientoCobrosViewSet`, sin una segunda API de consulta ni otro cálculo de saldos. `csv.py` extrae sólo el tratamiento de texto reutilizado por `actividad.py`. `AuditaLecturaFinanciera` admite respuestas de archivo únicamente cuando se aportan grupos explícitos. No hay cambios de modelo, migraciones ni nuevas dependencias. Commits de implementación: `26e592e` (backend) y `f64fd2c` (interfaz).

| Criterio | Evidencia |
| --- | --- |
| CSV contiene todas las filas filtradas en el orden del JSON | `test_exporta_todas_las_filas_filtradas_en_el_mismo_orden_que_json`, incluso con `page=999&page_size=1` |
| Conserva saldos exactos, negativos y desconocidos; no modifica dinero | Pruebas de nueve columnas monetarias, controles de cantidades financieras, pendientes y captura sin importes inventados |
| Ningún campo amplía el ámbito financiero o clínico | Pruebas de institución, área, sensibilidad, roles insuficientes y columnas excluidas |
| Identificadores íntegros y texto seguro en CSV | Pruebas de IDs largos, nombres parecidos a fechas, fórmulas/Unicode, separadores y saltos de línea; regresión de actividad |
| Límite sin archivo parcial y auditoría de las mismas filas | Pruebas de límite exacto/excedido, exportación vacía y llegada de nuevos cargos después de materializar la lista |
| Fallo de auditoría impide entregar el archivo | 503 en las tres vistas y rollback al fallar el segundo grupo |
| Descarga con filtros aplicados y contexto conservado | Nueve E2E nuevos: tres vistas, filtros sin paginación, límites, borradores, errores 400/503, doble clic y cambio de hospital |

- **366/366 pruebas PostgreSQL 16**, sin omisiones, 99,122 s, con el mismo comando de regresión documentado arriba. Incluye las 19 nuevas pruebas del CSV y las regresiones de financiadores, dinero, aprobaciones, cobros, reportes, permisos y esquema.
- **19/19 focales SQLite**, 1,575 s. Primer pase adicional de regresión de seguimiento/actividad: **56/56**, 6,538 s. Comando focal: `python manage.py test apps.financiadores.test_exportacion_seguimiento --settings=config.settings_financiadores_test --noinput`.
- **78/78 pruebas Playwright** de la configuración `playwright.financiadores-ui.config.js`, incluidas 22 del seguimiento; build Vite correcto, 751 módulos, 2,81 s. `check`, OpenAPI con `--validate --fail-on-warn` y `git diff --check` correctos.
- Demo real: CSV de dos cuentas y un pendiente descargados desde la interfaz, comparados con JSON y con los saldos persistidos; una única fecha de generación por archivo, BOM y encabezados HTTP verificados. Exportación de captura vacía verificada por API. Auditoría de las tres vistas y ausencia de nuevos movimientos confirmadas. Capturas de escritorio/móvil sin desborde del documento ni errores JavaScript.

El revisor Codex independiente informó que terminó la inspección de backend y UI sin hallazgos adicionales. La entrega de su respuesta final se interrumpió por cuota; se conservan sus observaciones intermedias. La regresión PostgreSQL y el contraste de la demo los completó el agente principal. Claude no participó de este incremento por el límite informado en la sesión anterior; no se atribuye una revisión final a Claude.

Se aplicaron `brainstorming` para limitar el alcance aprobado, `interface-design` para reutilizar el patrón de descarga de Salud, el flujo de verificación de `playwright` con las herramientas instaladas y `pr-reviewer-github` para revisar permisos, formato y auditoría. Se consultó `xlsx`, pero no se aplicó su flujo de modelos y fórmulas: este cambio implementa una exportación CSV del servidor y conserva sus valores registrados.

Límites: no se abrió el archivo en Microsoft Excel real ni se midió una exportación de 5.000 filas; el CSV se validó con parser y navegador. No se repitió toda la suite global del repositorio. El límite de filas se comprobó con un umbral reducido en las pruebas. El apóstrofo es parte de la convención de texto del archivo, visible en algunos lectores. Una descarga ya iniciada conserva hospital/vista/filtros si se navega a otra pantalla; el cliente existente no permite cancelarla.

Continuidad: el [ensayo integral del piloto con dos hospitales y dos financiadores](piloto-integral.md) ya comprobó permisos, carga masiva, cupos compartidos, atención, cobros y ambos reportes, y midió archivos reales de 5.000 filas. Esa evidencia posterior completa la medición que faltaba en este incremento. La aceptación del equipo hospitalario continúa pendiente; L7 de autorizaciones previas permanece fuera de esta entrega.
