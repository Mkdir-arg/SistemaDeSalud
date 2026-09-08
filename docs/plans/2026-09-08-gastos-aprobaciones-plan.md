# Plan implementable: gastos y aprobaciones

## Alcance del incremento

Incorporar gastos institucionales aprobables como fuente financiera aislada.
El resultado no distribuye gastos, no recalcula atenciones y no genera cobros,
pagos ni movimientos de dinero.

## Orden de trabajo

### 1. Catálogo y contrato persistente

**Resultado verificable:** se pueden definir conceptos institucionales y
expectativas por área/vigencia, sin crear un importe económico.

- Agregar los modelos de concepto y expectativa con institución y área
  consistentes.
- Congelar la sensibilidad cuando se crea un gasto, no cuando se lo consulta.
- Proteger contra edición o borrado de registros históricos; usar vigencias o
  reemplazos para una corrección.
- Crear una migración reversible y focalizada de `finanzas`.

**Pruebas focalizadas:** ámbito de área perteneciente a otra institución,
vigencias incompatibles, catálogo inmutable y ninguna expectativa que produzca
un gasto o importe cero.

### 2. Concesiones y lectura segura

**Resultado verificable:** cada acción de gastos exige la misma combinación de
concesión, institución, área y sensibilidad que usa el módulo de costos.

- Añadir las cinco acciones aprobadas a `ConcesionFinanciera`.
- Declarar administrativas las acciones de aprobar, corregir y configurar.
- Reutilizar `tiene_concesion_financiera`; no crear roles nuevos ni permisos
  implícitos.

**Pruebas focalizadas:** una persona de área sólo registra dentro de su área;
un administrador sin `permite_sensibles` no lee un gasto sensible; una concesión
de otra institución no habilita ningún acceso.

### 3. Carga, revisión y ajuste inmutables

**Resultado verificable:** una carga central queda aprobada, una carga delegada
queda pendiente, y una aprobación reintentada no duplica su efecto.

- Agregar `Gasto` y `AjusteGasto` con ARS, período económico y fecha de
  registro separados.
- Centralizar creación, aprobación, rechazo y ajuste en servicios transaccionales.
- Usar bloqueo de fila para aprobar y devolver el mismo gasto si ya estaba
  aprobado.
- Permitir reemplazo de pendientes o rechazados, sin edición; permitir ajustes
  sólo sobre aprobados.

**Pruebas focalizadas:** transición inválida, reintento, doble aprobación bajo
concurrencia PostgreSQL, ajuste no nulo y conservación del original.

### 4. Calendario de carga esperada

**Resultado verificable:** para cada expectativa mensual se visualiza el último
estado indicado o el faltante conocido, sin cerrar el mes ni suponer cobertura.

- Agregar eventos inmutables de indicación de carga.
- Proyectar el último evento por expectativa/mes/ámbito en la consulta.
- Mantener carga completa separada de aprobación y distribución.

**Pruebas focalizadas:** primera factura no completa el calendario, información
tardía luego de carga completa, `no_corresponde` sin gasto cero y períodos
anteriores.

### 5. API, auditoría y regresión transversal

**Resultado verificable:** la API respeta permisos y expone estados sin revelar
sensibles; los costos de paciente permanecen iguales hasta #37.

- Incorporar serializers y viewsets restringidos; bloquear `PUT` y `DELETE` en
  entidades inmutables.
- Aplicar auditoría de lectura donde corresponda al acceso financiero.
- Añadir filtros por institución, área, período, concepto y estado.
- Ejecutar pruebas de `finanzas` y las regresiones de casos/auditoría afectadas.

**Pruebas focalizadas:** detalle por ID sensible, lista filtrada, acceso
institucional cruzado, y afirmación de que un gasto aprobado no modifica
`HechoAtencionCosteable`.

## Checkpoints de entrega

Cada bloque se confirma con una migración o prueba focalizada cuando aplique,
un commit convencional y un push a la misma PR en borrador. #36 permanece en
In Progress hasta que sus endpoints y pruebas estén revisables; #33 sigue como
referencia central del módulo.

## Riesgos controlados

- Un gasto compartido no debe parecer asignado a un paciente antes de #37.
- El último estado del calendario no debe esconder la historia de indicaciones.
- Las reintentos y ejecuciones concurrentes no deben producir dos aprobaciones.
- Un cambio posterior de sensibilidad de catálogo no debe ampliar lectura de
  gastos ya registrados.

## Checkpoint: calendario por API

Implementados el alta/versionado de expectativas, la indicación administrativa,
su historial paginado y el calendario mensual con pendientes/aprobados visibles.
La consulta conserva versiones anteriores hasta la vigencia de su sucesora;
permite actualizar indicaciones tardías de esos meses. La indicación y el
versionado usan el bloqueo del mismo concepto para serializar sus escrituras.

Guía y evidencia: `2026-09-08-calendario-gastos-prueba-api.md`.
Faltan la pantalla de gastos/calendario, prueba manual con ambos perfiles y
terminar la revisión de auditoría/regresión transversal del bloque 5 antes de
considerar #36 completo. El issue permanece en In progress.
