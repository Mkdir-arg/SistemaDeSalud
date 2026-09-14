# Finanzas: usabilidad y trazabilidad aprobadas

El usuario aprobó el 11 de septiembre la propuesta completa formulada el turno anterior. La prioridad es una interfaz simple para administración hospitalaria, consistente con las pantallas existentes.

## Cambios observables

- Mes y área actualizan automáticamente, sin botón Actualizar. Consultas y filtros persisten en URL y reinician paginación cuando corresponde.
- Encabezado sin rótulo superior redundante, componentes y espaciado existentes. Investigar destello por habilitación de botones tras consultas y estabilizarlo sin anticipar permisos.
- Ayudas generales en (?) mediante hover, foco y toque; superpuestas sin desplazar la tabla. Errores, totales y causas de bloqueo permanecen visibles.
- Reemplazar ámbito por área en texto de Finanzas, diferenciando Institucional — sin área asignada. Usar Configurar carga esperada, Modificar vigencia e Historial de configuración. No mostrar identificador interno como número ordinal de versión.
- Orden y filtros por columnas de datos de las tres tablas, globales antes de paginar; selecciones para categorías y rangos para fechas, cantidades e importes. Controles compactos, filtros activos visibles y removibles.
- Conteos del calendario navegan a gastos filtrados exactamente por mes, institución, área (incluido nulo), concepto y estado efectivo, excluyendo reemplazados de los conteos.
- Desplegar asignaciones por atención: referencia, fecha, área e importe; detalle paginado al abrir. Totales claros y permisos actuales, sin narrativa clínica ni nueva concesión automática.
- Mostrar original, ajustes e importe resultante de gastos y enlaces de reemplazo. Cálculo exacto sin multiplicación por joins; mantener historial.

## Implementación y verificación

Reutilizar DataTable, filtros URL, componentes base y consultas existentes. Las extensiones compartidas son optativas y compatibles con los otros módulos. Backend y frontend se implementan paralelamente en el worktree del PR #40; no se agregan dependencias ni migraciones.

Pruebas: ordenamiento y filtros con más de una página; equivalencia de conteos y gastos; nulos institucionales; importes y centavos; permisos y sensibilidad de registros financieros; detalle paginado; navegación, ayudas por teclado/táctil y entrada estable en navegador. Revisar la implementación respecto de estos criterios y de los patrones existentes.

## Práctica simultánea

Otro proyecto Docker y otra base sintética, sobre una copia fija del commit 6cd2c1d, permiten al usuario crear atenciones sin recibir cambios del desarrollo durante el ejercicio. El recorrido explica caso abierto, atención completada, hecho financiero y costo directo. Una vista auxiliar de capacitación puede consultar evidencia mediante la API; no se presenta como una pantalla nueva del producto.

## Hallazgos de revisión atendidos en este cambio

- El detalle de atribuciones obtiene el total distribuido de las asignaciones reales. En un reparto pendiente no confunde el importe fuente con dinero ya distribuido; el resto se calcula sin modificar el registro histórico.
- El detalle consulta permisos efectivos de datos sensibles, incluyendo el rol actual. Una concesión sensible antigua no conserva acceso después de perder la capacidad administrativa.
- Las ayudas permanecen abiertas al mover el puntero hacia el panel y Escape devuelve el foco sin volver a abrirlo. Dentro de un formulario respetan su contención de foco.
- Los encabezados permanecen disponibles durante consultas, errores y resultados vacíos, permitiendo corregir el filtro. Los importes inválidos no se descartan silenciosamente.

## Corrección adicional de permisos autorizada

La acción `coberturas-actividad/verificacion` ya comprobaba solamente `CONFIGURAR_REPARTOS` en 6cd2c1d y devolvía un resumen con gasto aprobado y cantidad de atenciones. Su respuesta personalizada tampoco pasaba por la auditoría explícita de lecturas financieras. Después de la entrega del feedback, el usuario autorizó exigir lectura y registrar la consulta.

Ahora se requieren `CONFIGURAR_REPARTOS` y `VER_GASTOS` en la misma institución y área. Para seleccionar un concepto sensible ambos permisos deben habilitar datos sensibles; en la consulta general se excluyen esos importes si falta cualquiera de las dos capacidades sensibles. No se agregan concesiones ni se cambia la autorización para guardar configuraciones.

La respuesta añade `institucion`, `area`, `sensible` y `periodo_economico` con el contexto autorizado. Se utiliza la auditoría existente antes de entregar el resumen; el evento identifica usuario, institución, área, mes y acción `verificacion`, sin inventar un identificador de cobertura. La marca sensible es conservadora: señala que el resumen puede incluir importes sensibles. Si falla la persistencia de auditoría se devuelve 503, sin totales ni conteos.

Archivos de esta corrección adicional: `backend/apps/finanzas/api_repartos.py`, `backend/apps/finanzas/test_reparto_api.py` y estas dos guías de Finanzas. No cambia el motor clínico, los importes guardados ni el entorno de práctica.

No se afirma incorporación, despliegue ni aceptación humana a partir de las pruebas locales. La práctica permite que el usuario contraste su comprensión con resultados reales de datos sintéticos.

## Evidencia local del 11 de septiembre

- `docker exec sistemadesalud-finanzas-demo-backend-1 python manage.py test apps.finanzas --noinput`: 122 pruebas correctas después de corregir los dos hallazgos de revisión. Incluye empate entre páginas, 201 atribuciones, límites de área e institución, sensibilidad, cambios de rol, centavos, ajustes, reemplazos y saldos negativos.
- `docker exec sistemadesalud-finanzas-demo-backend-1 python manage.py makemigrations --check --dry-run`: sin cambios pendientes.
- `npx playwright test --config=playwright.finanzas.config.js` desde `frontend`: 11/11 correctas en la pasada final (29,8 segundos), contra la API real de la demo. Cubre actualización automática, persistencia, encabezados ordenables, conteos, filtros inválidos/vacíos, ayudas y foco, atribuciones, reemplazos, permisos e interfaz móvil.
- `npm run build`: compilación final correcta. `npm run auditar`: 236 clases revisadas, ninguna huérfana ni en colisión. `git diff --check`: sin errores.
- Revisión visual de calendario a 1440, 1036 y 390 px, gastos con reemplazos y reparto con detalle abierto. Las tablas conservan desplazamiento horizontal dentro de su contenedor cuando el ancho no alcanza.
- En la práctica aislada se completó únicamente el caso de control #1 desde el navegador, sin firma: un registro financiero, material ARS 1.500 + tiempo profesional ARS 8.500 = ARS 10.000. Recargar conserva ese mismo registro. Los casos #2–#4 se reservaron al usuario.
- Aplicación de práctica, guía y API de salud respondieron HTTP 200 al cierre. No se ejecutó la suite global de otros módulos ni un despliegue.

La suite de navegador de esta demo se ejecuta desde `frontend` con `npx playwright test --config=playwright.finanzas.config.js`; no siembra ni modifica gastos. Usa las cuentas sintéticas `finanzas.admin@demo.local` y `finanzas.area@demo.local` del entorno 8090, nunca el entorno de práctica del usuario en 8092.

Después de la autorización adicional: se reprodujeron por separado el acceso indebido (200 sin `VER_GASTOS`) y la ausencia de auditoría (cero registros), y ambas pruebas pasaron tras corregir cada causa. La pasada final de `apps.finanzas` pasó **128/128** pruebas (38,555 segundos), incluyendo seis regresiones nuevas de esta corrección. `makemigrations --check --dry-run` y `git diff --check` sin cambios pendientes ni errores. No se repitió navegador ni compilación porque esta corrección no modifica la interfaz; se comprobó el contrato del resumen por API. Aplicación y guía de práctica siguen respondiendo HTTP 200.
