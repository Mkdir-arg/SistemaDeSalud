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

## Resultado y evidencia — 16/09/2026

Implementado en `actividad.py` y `ActividadFinanciador.jsx`, con delegación mínima desde las vistas y el portal existentes. `acceso.py` conserva el alcance previo y divide únicamente el detalle de auditoría. Cambios guardados en los commits `528ad54` (backend) y `b64ffc0` (interfaz).

| Criterio | Evidencia |
| --- | --- |
| Los totales abarcan todas las páginas; los acuerdos no duplican cargos | `test_totales_incluyen_todas_las_paginas_y_separan_reservas_de_cargos`, `test_importe_incluye_acuerdo_del_pagador_sin_sumar_rechazos_o_asuncion_hospital` |
| Se distinguen importes pendientes, cero conocido y cargos sin descontar pagos | Pruebas de importe desconocido, prestación sin cobro y cargos originales tras cobro/ajuste |
| Filtrado por origen y plan capturado, incluidos filtros booleanos omitidos | Pruebas de hospital original, cambio de plan, sin plan, discrepancias, fecha inclusiva y filtros inválidos |
| No se amplían permisos mediante totales, opciones o CSV | Pruebas de organización ajena, ausencia de membresía y acceso histórico exclusivamente pendiente |
| Archivo completo con valores íntegros y auditoría previa | Pruebas de límite, páginas, fórmulas, ceros, identificador parecido a fecha, 25 IDs largos y rollback ante fallos de auditoría |
| La pantalla conserva filtros y descarga el mismo conjunto | Ocho pruebas de interfaz nuevas, incluidas URL/recarga, organización, rol auditor, errores y exportación |

Validación final del incremento:

- PostgreSQL 16 dedicado y descartable: **230/230 pruebas**, sin omisiones, 58,063 s. Abarca todo `apps.financiadores` y los contratos de permisos/esquema de Casos.
- Después de aclarar las etiquetas del CSV por la revisión final: **26/26 pruebas del reporte en PostgreSQL**, 7,873 s. Esta comprobación incluye un nuevo escenario que distingue reserva sin cargo emitido de prestación realizada que no se cobra; no se repitieron las 230 para ese cambio de etiquetas.
- Focales SQLite: **39/39**, 5,257 s (25 nuevas y 14 históricas). Los primeros pases detectaron interpretación incorrecta de booleanos omitidos y colisión del alias de agregación; ambos se corrigieron en producción y quedaron cubiertos. La regresión también exigió actualizar otra lista exacta de campos administrativos autorizados, conservando la prohibición de contexto clínico.
- Playwright con API simulada: **44/44 del portal**, 44,1 s, y **12/12 clínicas**, 17,1 s. Compilación Vite: 750 módulos, 4,32 s.
- `check`, OpenAPI con `--validate --fail-on-warn` y `git diff --check`: correctos. No hay cambios de modelo ni migraciones en este incremento.
- Demo real, navegador → API → archivo → base: Obra Social Demo, **3 realizadas y $24.000**; Mutual Demo, **2 realizadas y $17.500**, incluida actividad histórica pendiente del segundo hospital. Se verificaron filtros persistentes, CSV equivalente, auditoría por persona/hospital y capturas en escritorio/móvil sin desborde del documento ni errores JS/HTTP. No se registró dinero ni se alteraron prestaciones en este recorrido.

```text
python manage.py test apps.financiadores apps.casos.test_permisos_barrida apps.casos.test_esquema --settings=config.settings_financiadores_postgres_test --noinput
python manage.py test apps.financiadores.test_actividad apps.financiadores.test_vigencias.ActividadHistoricaTests --settings=config.settings_financiadores_test
npx --no-install playwright test --config=playwright.financiadores-ui.config.js financiadores-ui.spec.js
npx --no-install playwright test --config=playwright.financiadores-ui.config.js cobertura-clinica-ui.spec.js
npm run build
```

Claude completó una revisión estática independiente sin bloqueantes. Su observación sobre códigos ambiguos motivó exportar etiquetas legibles: «Cargo todavía no emitido», «Prestación sin cargo» y «Responsable definido», entre otras. No se presenta esa revisión como una ejecución adicional de pruebas.

No se ejecutó toda la suite global del repositorio, una prueba de carga con 5.000 filas ni una apertura en Microsoft Excel real. En particular, el costo de auditar miles de personas distintas y las consultas de opciones requieren medición antes de aumentar el límite de descarga. La integridad del CSV se verificó con un parser y con archivos descargados de la demo. Las consultas son operativas: sus totales pueden cambiar por nueva actividad o por cambios de acceso entre consultas. Para revisar las decisiones, leer `con_importes`, `resumen_actividad`, `exportar_actividad` y las condiciones de `actividad_visible`; no se agregó una segunda cuenta corriente.

Skills: `brainstorming` acotó RF6 sobre las decisiones aprobadas; `interface-design` preservó Shell y componentes; `systematic-debugging` separó los fallos reales de consultas de expectativas antiguas; las comprobaciones de navegador siguieron el flujo de `playwright` ya usado en la demo. La autorización para continuar no se presenta como aceptación del piloto ni como verificación de comprensión por parte del usuario.
