# Actividad del financiador: consulta y exportación

## Alcance y aceptación

Incremento del PR [#41](https://github.com/Mkdir-arg/SistemaDeSalud/pull/41), sobre RF6 de [#20](https://github.com/Mkdir-arg/SistemaDeSalud/issues/20) y consumos de [#19](https://github.com/Mkdir-arg/SistemaDeSalud/issues/19). El usuario autorizó continuar con las recomendaciones y guardar avances en commits. Las decisiones locales siguientes son recomendaciones del agente dentro de ese alcance.

- Consultar actividad por fechas inclusivas, hospital de origen, plan fijado en la afiliación del caso, prestación común, estado, discrepancia y búsqueda de afiliado/prestación.
- Mostrar totales de **todo el resultado filtrado**, con paginación en servidor. La interfaz abre el mes calendario actual y conserva filtros en la URL.
- Descargar las mismas filas filtradas en CSV, aunque ocupen varias páginas; máximo 5.000 registros por archivo. Si se supera, pedir un filtro más acotado sin entregar archivos parciales.
- Mantener la visibilidad vigente y el acceso histórico limitado a pendientes propios ya aprobados. Las opciones de filtro también se obtienen de actividad visible.
- Registrar el acceso a cada persona e institución antes de entregar la página o el archivo. El fallo de auditoría impide esa entrega administrativa.

## Significado de los importes

El **importe asignado original** suma el cargo inicial del financiador y sus aceptaciones posteriores de diferencias. Sólo se totalizan prestaciones realizadas con distribución conocida. Reservas y liberaciones no generan este total. Las realizadas sin evaluación o arancel completo aparecen pendientes, sin convertir un importe desconocido en cero.

Estos importes no descuentan pagos ni ajustes posteriores: no representan un saldo de cuenta, una liquidación ni dinero cobrado. El estado administrativo «Resuelta» tampoco acredita un pago. El portal explica esta distinción junto al total y el archivo utiliza encabezados explícitos.

## Implementación acotada

Se extiende `GET /api/financiadores/{id}/actividad/`, reutilizando `actividad_visible` y la auditoría existente. No se crean modelos, permisos, migraciones ni dependencias. JSON mantiene los campos anteriores y agrega nombre del padrón, plan, código común, importe de acuerdos e importe asignado. No se incluyen historia clínica, notas ni evidencia documental.

El CSV usa UTF-8 con BOM, punto y coma y coma decimal. Los identificadores se prefijan con apóstrofo para conservar sus ceros al abrirlos como texto; ese prefijo es una convención del archivo, no modifica el padrón. Se neutralizan textos que puedan interpretarse como fórmulas y se conservan identificadores que parezcan fechas. La exportación se construye con un resultado acotado y se audita antes de responder; no se envían filas durante la generación.

Los filtros usan la fecha prevista de las reservas o la fecha efectiva de las realizadas, y el plan fijado en su afiliación, aunque posteriormente cambie el padrón. La opción «Sin plan» permite encontrar selecciones que no lo tenían. La fecha de generación informa cuándo se consultó: los datos siguen siendo operativos y pueden cambiar entre consultas; no es un cierre contable inmutable.

La auditoría divide las reservas de una misma persona en bloques de diez IDs para conservar evidencia completa dentro del campo existente de 300 caracteres. Si el hecho no tiene paciente vinculado, se registra el hospital y las reservas consultadas sin inventar una identidad clínica. Una revisión de diseño de Claude identificó los riesgos de multiplicar cargos al unir resoluciones, truncar auditorías e interpretar identificadores como fechas; se evitan con subconsultas, bloques y formato textual explícito.

## Verificación prevista

Pruebas HTTP de filtros y límites, totales fuera de la página, acuerdos posteriores, importes pendientes, visibilidad histórica y aislamiento entre financiadores. CSV con ceros, fórmulas, separadores y saltos de línea; auditoría de todas las personas exportadas y fallo sin entrega. Interfaz con filtros persistentes, exportación equivalente, errores y rol de consulta. Recorrido adicional en la demo ficticia.

La autorización previa, la conciliación hospitalaria y la política de conservación continúan como incrementos separados. Este bloque no cierra por sí solo las épicas #19/#20 ni habilita un despliegue con datos reales.
