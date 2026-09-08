# Gastos, aprobaciones y conceptos esperados

## Contexto

El costo directo por atención ya conserva su fuente, sus componentes y sus
ajustes sin mezclarlo con aranceles, cargos ni dinero efectivamente pagado.
Falta incorporar el origen institucional de gastos reales para que el reparto
posterior pueda usar fuentes aprobadas sin alterar la atención clínica ni
presentar un dato desconocido como cero.

Esta decisión implementa el alcance de la épica #36. El reparto a atenciones
(#37), pagos (#38), comprobantes y detección automática de duplicados quedan
fuera de este incremento.

## Decisión

Se modelará una fuente de gastos inmutable, con aprobación explícita y
correcciones aditivas.

### Catálogo y expectativa de carga

- `ConceptoGasto` será un catálogo institucional con código, nombre, estado y
  sensibilidad.
- `ExpectativaGasto` indicará que un concepto aplica a una institución o a un
  área durante una vigencia mensual. No contiene importe ni crea gastos.
- `IndicacionCargaGasto` será un registro inmutable de una indicación para una
  expectativa, mes y ámbito. Sus únicos estados son `falta_cargar`,
  `carga_completa` y `no_corresponde`.
- El estado que se muestra en el calendario será la última indicación. Si aún
  no hay una, se mostrará el faltante conocido de la expectativa sin crear una
  fila de gasto, un importe cero ni una obligación de cierre.

Las expectativas y sus vigencias no se borran. Una corrección conserva el
histórico mediante una nueva versión o vigencia, según el patrón ya usado para
valores de componentes.

### Gasto y aprobación

`Gasto` conservará el concepto, la institución, el área opcional, el importe
en ARS, el período económico normalizado al mes, la fecha real de registro,
autor, origen y sensibilidad congelada del concepto.

- Una carga de administración central con concesión explícita nace aprobada.
- Una carga delegada de área nace pendiente de aprobación central.
- Un gasto rechazado es terminal y no se modifica.
- Un error previo a la aprobación o un gasto rechazado se reemplaza mediante
  una nueva carga enlazada al registro original; no se sobrescribe el registro
  revisado.
- Un gasto aprobado no se edita. `AjusteGasto` agrega un importe no nulo con
  motivo, autor y fecha, igual que `AjusteCosto` preserva su imputación.

La transición de pendiente a aprobado se ejecutará bajo bloqueo de fila. Un
reintento de la misma aprobación devuelve el gasto ya aprobado y no genera un
segundo efecto. Rechazar un aprobado o aprobar un rechazado será inválido.

En este incremento, *impactar* significa que la fuente queda aprobada y
disponible para un repartidor futuro. No actualiza todavía un costo de paciente,
no crea aranceles, cargos, cobros ni movimientos de dinero.

### Permisos y sensibilidad

Se amplía el mecanismo existente `ConcesionFinanciera`, ligado a membresía,
institución, área y `permite_sensibles`, con estas acciones:

- `ver_gastos`
- `registrar_gastos`
- `aprobar_gastos`
- `corregir_gastos`
- `configurar_gastos_esperados`

Aprobar, corregir y configurar requieren membresía administrativa. Registrar
admite una concesión delegada por área; sólo una membresía administrativa con
esa acción puede originar una carga directamente aprobada. La lectura de un
gasto sensible, incluso por identificador o futuras exportaciones, exige una
concesión administrativa explícita que permita sensibles. La sensibilidad queda
congelada en la carga para que un cambio posterior de catálogo no revele su
histórico.

## Alternativas descartadas

- Editar una única fila de gasto: impide saber qué importe fue aprobado o
  rechazado y hace frágil la recuperación ante reintentos.
- Hacer que el primer gasto cambie automáticamente el calendario a completo:
  confunde una carga parcial con la confirmación administrativa de completitud.
- Event sourcing de todos los campos financieros: aporta una generalidad que
  V1 no necesita; las entidades inmutables y los ajustes ya dan la trazabilidad
  necesaria.

## Invariantes

- Desconocido, pendiente de aprobación y aprobado son estados distintos; ninguno
  se representa con importe cero.
- El período económico puede ser anterior a la fecha de registro; no requiere
  cerrar ni reabrir meses.
- Una fuente aprobada se incorpora una sola vez, aun si una solicitud se
  reintenta concurrentemente.
- Los gastos no se asignan a pacientes ni se convierten en deuda o pago dentro
  de este incremento.
- La atención clínica no agrega pasos, campos ni validaciones.

## Validación prevista

- Permisos por institución, área y sensibilidad en listado, detalle y alta.
- Carga central aprobada y carga de área pendiente.
- Aprobación concurrente e idempotente sin doble incorporación.
- Rechazo y reemplazo conservando ambos registros.
- Ajuste de gasto aprobado sin modificación del original.
- Gasto de un período anterior y calendario de expectativas sin importes
  inventados.
- Regresión de que ningún gasto cambia aún el detalle de costos del paciente.
