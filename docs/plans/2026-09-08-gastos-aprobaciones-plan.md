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
La pantalla de gastos/calendario se incorporó en el checkpoint siguiente, con
prueba de navegador ejecutada por el agente sobre usuarios administrativos y
delegados sintéticos. Incluye alta, revisión, ajustes, configuración inicial e
historial; no administración de concesiones ni versionado de expectativas desde
UI. La guía anterior distingue cobertura backend, navegador y límites.

El siguiente paso es terminar la revisión de auditoría de lectura financiera y
regresión transversal del bloque 5, antes de ampliar el reparto por actividad.
Después queda completar la operación de expectativas versionadas desde UI.
#36 permanece en In progress; no se considera completo ni aceptado por el usuario.

## Checkpoint: regresión transversal y límite de auditoría

Se agregaron dos regresiones por API en `HechoCostoApiTests`, sin modificar
comportamiento productivo:

- Una carga delegada, su aprobación, un ajuste y la indicación de carga completa
  conservan exactamente el listado económico previo del paciente: un hecho con
  ARS 1250,50 y otro con importe desconocido y faltantes. Tampoco convierten el
  costo parcial en completo. Se compara después de cada operación.
- Consultar detalle/listado de costos conserva usuario, paciente e institución
  en auditoría. Un jefe de área sin concesión financiera puede auditar quién
  consultó, pero no abrir el costo; la lectura denegada no se anota como exitosa
  ni se copian importes a ese registro en el recorrido probado.

**Validación ejecutada:**

```powershell
$env:DATABASE_URL='sqlite:///:memory:'
$env:DATABASE_SSL='false'
& C:\Users\Juanito\AppData\Local\Temp\sistemadesalud-finanzas-venv\Scripts\python.exe manage.py test apps.finanzas apps.auditoria.tests apps.casos.tests.MotorTestCase apps.casos.tests.FirmaConfigurableTests --verbosity 0
```

Desde `backend` del worktree aislado: 132 pruebas, 130 correctas y 2 omitidas
por requerir PostgreSQL; resultado final tras corregir la clasificación del
test indicada abajo. Las dos pruebas nuevas también pasaron individualmente.
No se repitieron navegador/build ni PostgreSQL: sólo cambiaron tests y este
plan. No hubo migraciones, nuevas dependencias ni cambios de datos reales.
`git diff --check` sin errores. Esto no cierra la auditoría pendiente ni acredita
aceptación funcional por parte del usuario.

### Evidencia estática

La primera ejecución conjunta detectó un fallo del test de cobertura clínica:
interpretaba toda `protege_lectura=True` como dato clínico, incluyendo las
concesiones financieras. Se corrigió sólo el test con una excepción explícita
para configuración de concesiones y la inclusión explícita del recurso de
costos de pacientes. No se quitó protección de lectura ni se excluyó toda la
app financiera. El reensayo focalizado de cobertura y concesiones pasó 6 pruebas.

`HechoAtencionCosteableViewSet` usa `AuditaLecturaClinica`. En cambio,
`GastoViewSet` y `ExpectativaGastoViewSet` no registran sus consultas, incluidas
las acciones de calendario e historial. Autor/fecha de una carga o de su ajuste
prueban la escritura, no quién leyó esos datos posteriormente.

El registro existente `AccesoClinico` fue diseñado para pacientes. Su lectura
admite roles de auditoría clínica sin concesiones financieras, y un fallo al
registrar se informa en log pero no bloquea la consulta clínica. Agregar el mixin
a gastos no resuelve las acciones personalizadas ni define quién debe poder
auditar esos accesos; además copiaría filtros de consulta sin una selección
específica de metadatos financieros. No se aplicó ese cambio mecánicamente.

### Decisión material pendiente, propuesta del agente (no aprobada)

**Recomendación:** registro `AccesoFinanciero` separado para las consultas de
gastos, catálogo de gastos, expectativas, calendario e historial. Reutilizar
`ConcesionFinanciera` con una acción administrativa explícita de auditoría,
manteniendo institución, área y sensibilidad en la misma concesión. No conceder
esa acción automáticamente a administradores ni auditores clínicos.

- Registrar actor, fecha, recurso/acción, institución, área, sensibilidad,
  identificador cuando corresponda y cantidad de registros; sin importes,
  motivos libres ni narrativa clínica. Los filtros admitidos serán una lista
  cerrada de identificadores/períodos, no la URL arbitraria.
- Registros inmutables y sin borrado en API/admin, con referencias protegidas.
  No implementar purgas ni fijar un nuevo plazo de retención en este corte.
- Para estas consultas financieras, si no se logra persistir su auditoría,
  responder un error recuperable sin entregar los datos. No aplicar esa regla
  al motor de atención ni cambiar la auditoría clínica existente.
- Mantener las escrituras financieras y los costos de pacientes bajo sus
  contratos actuales; no cambiar cómo se aprueba, costea o atiende.

**Alternativa:** extender el registro clínico con alcance financiero y separar
sus permisos. Evita una tabla, pero obliga a cambiar esquema, consultas y
políticas de fallo de una pieza transversal clínica. El registro separado
agrega una tabla/migración y una acción de permiso, a cambio de aislar ese riesgo.

**Costo operativo de la recomendación:** durante una falla del registro no se
podrán consultar estos datos financieros. La alternativa de seguir mostrando
datos y avisar sólo en logs preserva disponibilidad, pero deja accesos sin
rastro durable. Esta elección requiere confirmación antes de programar.

Tras aprobar la decisión: implementar registro/permiso, integrar las lecturas
incluidas y cubrir acceso cruzado, sensibles, paginación, acciones personalizadas,
fallo de persistencia e independencia clínica. Reconsiderar la separación sólo
si el sistema adopta una auditoría general con permisos equivalentes verificados.
