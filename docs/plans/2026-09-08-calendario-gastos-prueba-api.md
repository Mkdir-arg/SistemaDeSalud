# Prueba del calendario mensual de gastos

## Estado del corte

La API permite configurar expectativas, consultar el calendario de un mes y
registrar indicaciones conservando su historial. La pantalla `/finanzas` permite
recorrer la carga, revisión y calendario con permisos explícitos. Este recorrido
requiere un entorno de prueba con las
migraciones del PR aplicadas allí, usuarios autenticados y datos sintéticos.
No se aplicaron migraciones ni se prepararon usuarios en bases reales.

Los permisos se conceden por membresía activa, institución, área y sensibilidad:
`ver_gastos` para consulta y `configurar_gastos_esperados` para configuración e
indicaciones. Este último exige rol administrativo. Registrar una factura sigue
requiriendo `registrar_gastos`; aprobar requiere `aprobar_gastos`.

## Recorrido verificable

1. Con un concepto existente del catálogo, crear una expectativa con
   `POST /api/expectativas-gasto/`. Ejemplo de cuerpo (reemplazar identificadores
   por los del entorno):

   ```json
   {
     "concepto": 1,
     "institucion": 1,
     "area": 1,
     "vigente_desde": "2026-08-01"
   }
   ```

2. Consultar
   `GET /api/expectativas-gasto/calendario/?periodo_economico=2026-08-01&institucion=1`.
   Debe aparecer `estado_carga: falta_cargar` con `indicacion_id: null`.
   No se crea un gasto ni se informa un costo de importe cero.
3. Registrar un gasto con la API de gastos desde un usuario delegado. El
   calendario mantiene `falta_cargar` y muestra un gasto pendiente de aprobación.
   Una carga reemplazada ya no se cuenta como pendiente vigente.
4. Con administración autorizada, enviar
   `POST /api/expectativas-gasto/{id}/indicar/`:

   ```json
   {"periodo_economico": "2026-08-01", "estado": "carga_completa"}
   ```

   El calendario cambia la indicación, pero conserva el pendiente de aprobación.
   `gastos_pendientes` y `gastos_aprobados` son cantidades de registros visibles,
   no importes ni una declaración de cobertura completa.
5. Agregar información tardía y volver a indicar `falta_cargar` si corresponde.
   `GET /api/expectativas-gasto/{id}/indicaciones/` debe conservar ambas
   indicaciones, con autor y fecha. No se cierra ni reabre ningún mes.
6. Indicar `no_corresponde` en otro mes: no se crea gasto, pago ni importe cero.
   Las demás expectativas mantienen su propia indicación.
7. Repetir consultas con acceso limitado a otra área o sin autorización sensible:
   no deben aparecer filas, historial ni conteos fuera de ese acceso.

## Vigencias y límites

- Los intervalos son mensuales, con inicio inclusivo y fin exclusivo. Un sucesor
  desde septiembre conserva agosto en la expectativa anterior. Una corrección
  del mismo intervalo se consulta mediante la nueva versión; el historial de la
  anterior sigue disponible por su identificador y sus permisos.
- La API de expectativas acepta altas y versiones nuevas; no permite editar ni
  eliminar filas. Los filtros disponibles son institución, área y concepto;
  `area=null` consulta el ámbito institucional.
- Una consulta sin expectativas devuelve una lista vacía. No significa que la
  institución no tenga gastos; el sistema sólo conoce lo configurado.
- El calendario enumera pendientes y aprobados visibles del mismo concepto,
  mes y ámbito exacto. El detalle y los rechazados siguen en la API de gastos.
- Aprobar o indicar carga completa todavía no reparte gastos a pacientes (#37).

## Evidencia del checkpoint de API (anterior)

- `manage.py test apps.finanzas`: 72 pruebas, 70 correctas y 2 omitidas por
  requerir PostgreSQL en el entorno local SQLite.
- PostgreSQL aislado, código actual montado en sólo lectura: 10 pruebas de
  calendario e indicaciones correctas, incluidas vigencias, reemplazos,
  pendientes, ámbito institucional/área y sensibilidad.
- `makemigrations finanzas --check --dry-run`: sin cambios pendientes.
- Falta validación manual de interfaz y medición con volumen representativo.
  Los tests PostgreSQL de este corte no son una nueva prueba de concurrencia.

## Checkpoint de interfaz

La entrada **Finanzas y costos** aparece sólo para quien tiene una concesión de
gastos efectiva en la institución seleccionada. El frontend consulta
`GET /api/concesiones-financieras/mias/`; este endpoint describe permisos propios,
no administra concesiones ni reemplaza los controles de autorización de cada API.

La pantalla permite registrar, aprobar, rechazar, reemplazar cargas no aprobadas
y ajustar aprobadas, consultar el original y los ajustes, crear conceptos y
expectativas iniciales e indicar la carga mensual. Cada formulario identifica la
institución y el mes; el ámbito debe elegirse expresamente. No agrega campos
clínicos, pacientes, repartos, cargos ni pagos.

### Validación ejecutada el 8 de septiembre de 2026

- `manage.py test apps.finanzas`: 74 pruebas, 72 correctas y 2 omitidas por
  requerir PostgreSQL. SQLite en memoria y entorno virtual de Finanzas. Un primer
  intento con Python global no pudo iniciar por faltar `rest_framework_simplejwt`;
  no se modificaron dependencias para resolverlo.
- `manage.py makemigrations finanzas --check --dry-run`: sin cambios pendientes.
- `npm run build`: correcto, pantalla separada mediante carga diferida.
- `npm run auditar`: 235 clases, sin clases huérfanas ni colisiones.
- Navegador real con Playwright, Vite y Django del worktree aislado, SQLite
  temporal recién migrado y usuarios/datos exclusivamente sintéticos:
  - administración indica carga completa y aprueba una carga delegada;
  - ajuste de ARS -25,50 conserva el importe original de ARS 300;
  - operador de Guardia registra ARS 140,25 como pendiente; no ve Remuneraciones
    sensibles, otras áreas ni acciones de aprobación/configuración;
  - carga completa conserva por separado el nuevo pendiente de aprobación;
  - alta de concepto y expectativa inicial aparece como faltante en calendario;
  - selector recupera opciones posteriores a los primeros 25 registros;
  - otra institución sin concesión financiera deniega la pantalla;
  - escritorio y móvil de 390 px inspeccionados; sin desborde horizontal de la
    página, con desplazamiento contenido en la tabla.

### Límites pendientes

La prueba de navegador fue ejecutada por el agente: no equivale a aceptación
funcional del usuario. No se volvió a ejecutar PostgreSQL en este checkpoint, no
se midió volumen representativo ni se desplegó. Rechazo, reemplazo y permisos de
registro sin lectura tienen cobertura backend y comprobación estática de UI, no
un nuevo recorrido completo de navegador en este corte.

La interfaz no ofrece todavía nuevas versiones de expectativas ni administración
de concesiones. Queda la revisión de auditoría/regresión transversal de #36.
Ante una respuesta de escritura incierta, el formulario impide reenviar desde
ese diálogo y pide comprobar los registros antes de repetir; no es una garantía
de idempotencia global de altas entre pestañas. La pérdida de respuesta de red
no fue simulada en navegador en este checkpoint.

El flujo de gastos ya puede probarse en un entorno aislado sin esperar a reparto,
pagos y reportería. No requiere preparar cuentas ni datos reales.

## Checkpoint posterior: versiones y escenarios de error en navegador

La UI ya ofrece `Nueva versión` y `Ver versiones` en cada concepto del calendario.
El detalle técnico y las ocho pruebas API focalizadas están en el plan de gastos.
Reutiliza exclusivamente endpoints y permisos existentes.

Recorrido real ejecutado con Playwright CLI, Vite y Django sobre una base SQLite
temporal nueva, sin datos reales:

- Versión de Electricidad/Guardia desde octubre hasta noviembre exclusivo:
  septiembre mantiene versión e indicación `Carga completa`; octubre usa la
  sucesora y `Falta cargar`; noviembre ya no muestra esa expectativa.
- El historial de la versión anterior continúa accesible desde `Ver versiones`.
  El formulario rechaza un intervalo vacío y el servidor un segundo sucesor
  de la misma versión; no se duplican registros.
- Administración rechaza el gasto delegado de ARS 300 con motivo. Luego crea
  un reemplazo central de ARS 275,50: queda aprobado según la regla existente.
  El original mantiene importe, motivo de rechazo y vínculo a la carga nueva.
- Se interceptó exclusivamente ese POST local: `route.fetch()` lo envió al
  servidor y `route.abort()` descartó la respuesta antes de entregarla a la UI.
  El formulario mostró resultado incierto y deshabilitó `Confirmar`. Tras cerrar
  y actualizar, apareció una sola carga nueva. Esto verifica el bloqueo del
  mismo diálogo; no demuestra idempotencia global entre pestañas.
- Ingreso como operador de Guardia: sólo Electricidad/Guardia, sin Remuneraciones
  sensibles ni acciones de configuración/versionado/aprobación. Puede consultar
  versiones por su permiso de lectura. La carga completa sigue separada de las
  cantidades aprobadas y no incorpora el gasto reemplazado como otro aprobado.
- Capturas de versiones en escritorio y del formulario a 390 px inspeccionadas;
  sin desborde horizontal global. No se cambió el sistema visual existente.

Build correcto y auditoría de 235 clases sin incidencias. No hubo cambios
productivos durante la verificación de rechazo/reemplazo/red. El navegador
registró el 400 y fallo de red deliberados, además de un favicon ausente y los
avisos de desarrollo ya existentes de React Router. Una reapertura de sesión
del CLI descartó la autenticación: se repitió el ingreso; no se contó esa
interrupción del instrumento como fallo del producto ni como prueba aprobada.

Persisten: administración de concesiones por UI, volumen representativo y
aceptación funcional del responsable. No se aplicaron migraciones reales ni
se realizó despliegue. Las pruebas del agente no sustituyen aceptación humana.
