# Plan implementable: gastos y aprobaciones

Estado actual: #36 In review; gastos, calendario, versiones y operación de
concesiones disponibles para revisión. Evidencia final: 154/154 en PostgreSQL
aislado y recorridos de navegador. Reparto #37 pendiente de decisiones en
`2026-09-08-reparto-primera-base-propuesta.md`; no hay aceptación ni despliegue.

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

La auditoría financiera y la regresión transversal ya tienen evidencia en
PostgreSQL (ver checkpoints posteriores). El siguiente paso es completar la
operación de expectativas versionadas desde UI, antes del reparto por actividad.
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

### Decisión material aprobada: auditoría financiera separada

El responsable aprobó la propuesta y pidió mantenerla simple. La implementación
se limita a una tabla, una acción de concesión, un adaptador compartido de lectura
y un endpoint de consulta; sin infraestructura, tareas de fondo ni nuevos roles.

**Recomendación:** registro `AccesoFinanciero` separado para las consultas de
gastos, catálogo de gastos, expectativas, calendario e historial. Reutilizar
`ConcesionFinanciera` con una acción administrativa explícita de auditoría,
manteniendo institución, área y sensibilidad en la misma concesión. No conceder
esa acción automáticamente a administradores ni auditores clínicos.

- Registrar actor, fecha, recurso/acción, institución, área, sensibilidad,
  identificador cuando corresponda y cantidad de registros; sin importes,
  motivos libres ni narrativa clínica. Se toman identificadores/períodos de la
  respuesta autorizada, no se copia la URL ni los filtros arbitrarios del pedido.
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
rastro durable. El responsable aprobó bloquear sólo estas consultas financieras.

La validación cubre acceso cruzado, sensibles, paginación, acciones personalizadas,
fallo de persistencia e independencia clínica. Reconsiderar la separación sólo
si el sistema adopta una auditoría general con permisos equivalentes verificados.

### Implementación y evidencia

- `AccesoFinanciero` guarda actor, fecha, institución, área, sensibilidad,
  recurso/acción, ID cuando aplica, período disponible y cantidad. Los listados
  registran la página devuelta, agrupada por ámbito/sensibilidad/período; no el
  total de filas existentes. El historial identifica su expectativa, aun vacío.
- Sin resultados se registra cantidad cero (no un importe), sin inventar área
  ni sensibilidad. La institución se obtiene del contexto validado existente;
  si no puede atribuirse, queda nula y sólo plataforma puede consultar ese acceso.
- `GET /api/accesos-financieros/` y detalle requieren `auditar_finanzas`:
  membresía administrativa activa y el alcance de la misma concesión. Crear
  gastos, administrar la institución o auditar clínicamente no otorga esta acción.
  El superusuario conserva el tratamiento existente del módulo.
- Se auditan lecturas de gastos, catálogo, expectativas, calendario e historial.
  No se agrega auditoría recursiva al propio registro ni se cambian las respuestas
  de escritura, los hechos de costo o los recorridos clínicos.
- Un fallo de escritura revierte todos los registros de esa consulta y responde
  503 sin entregar sus datos. El log contiene sólo el tipo de error, no su texto
  ni el payload. Los rechazos 400/403/404 no se anotan como lecturas exitosas.
- La migración `0017_acceso_financiero` agrega la tabla y la opción de permiso;
  no concede accesos automáticamente ni modifica gastos existentes. Sólo se
  aplicó mediante las bases temporales de tests, nunca en una base real.

**Pruebas ejecutadas:** ocho casos nuevos en `apps.finanzas.test_auditoria`,
incluidos fallo en varios endpoints, reversión de escritura parcial, aislamiento
de ámbitos, democión/suspensión de membresía, consulta vacía e inmutabilidad por
API/modelo. Regresión conjunta: 140 casos, 138 correctos y 2 omitidos por requerir
PostgreSQL. `makemigrations finanzas --check --dry-run`: sin cambios pendientes.

**Chequeo adicional con fallo:** el test de generación OpenAPI falla con 12
advertencias de tipos en los serializers existentes de costos/gastos; ninguno
de esos serializers fue modificado en este checkpoint. No hay errores de
generación ni advertencias del nuevo serializer de accesos. Se conserva como
siguiente corrección focalizada, sin declarar toda la validación verde.

No se repitieron navegador/build ni PostgreSQL ni mediciones de volumen. La
consulta de accesos está disponible por API, sin nueva pantalla. La aceptación
funcional del usuario continúa pendiente.

**Conservación y reversión:** API sin alta/edición/borrado, modelo sin edición ni
borrado por instancia y referencias `PROTECT`; no se registra en Django admin.
Esto no pretende impedir SQL ni operaciones ORM masivas de mantenimiento
privilegiado. No deshacer la migración sobre registros reales: eliminaría la
tabla de auditoría. Un rollback debe conservar esa tabla y su evidencia.

## Checkpoint: contrato OpenAPI y regresión PostgreSQL

Se corrigieron las 12 advertencias mediante anotaciones de retorno en los
serializers de gastos/costos y `TypedDict` de la biblioteca estándar para sus
estructuras anidadas. No cambian cuerpos de métodos, respuestas, cálculos,
permisos, modelos ni migraciones; no se agregan dependencias.

Una nueva prueba de contrato falló antes de corregirlo: `total_conocido` no
publicaba su posibilidad de ser nulo. Ahora comprueba importes como texto
decimal, desconocidos nulos, booleanos reales, listas/objetos anidados y fechas
de ajustes. Las nueve pruebas de esquema/documentación pasan en SQLite sin
errores ni advertencias de generación OpenAPI.

Validación conjunta ejecutada sobre PostgreSQL 16.15 aislado: **149 pruebas
correctas, sin omisiones**. Comando desde `backend`:

```text
python manage.py test apps.finanzas apps.auditoria.tests apps.casos.tests.MotorTestCase apps.casos.tests.FirmaConfigurableTests apps.casos.test_esquema --verbosity 0
```

Incluye los ocho casos de auditoría financiera y las dos pruebas de concurrencia
de recuperación/aprobación omitidas en SQLite. El resultado demuestra esos
escenarios, no rendimiento con volumen representativo ni aceptación funcional.
`makemigrations finanzas --check --dry-run`: sin cambios pendientes.

El entorno usó la imagen de backend existente, el checkout montado en sólo
lectura, red interna sin puertos publicados y PostgreSQL en almacenamiento
temporal de memoria. Las migraciones se aplicaron únicamente a la base de tests;
sin tocar bases reales. No se repitió navegador/build al no cambiar la UI.
La ausencia de `staticfiles` produjo un aviso del entorno de tests, distinto de
OpenAPI; los 4xx/503 y errores de fuentes simulados corresponden a pruebas
negativas. No se ocultaron fallos del runner.

Próximo resultado de aquel checkpoint: versionar expectativas desde la pantalla existente, usando
la API ya implementada y conservando consultas/indicaciones de meses anteriores.
#36 sigue en curso; auditoría por API sin pantalla nueva, aceptación del usuario
y medición de volumen pendientes. No se recomienda merge ni despliegue aquí.

## Checkpoint: versiones de expectativas desde la pantalla

Implementación del siguiente resultado aprobado: dos acciones en el calendario,
`Nueva versión` y `Ver versiones`, reutilizando el alta y listado existentes de
expectativas. No se agregan endpoints, permisos, modelos ni migraciones.

- El formulario conserva concepto/ámbito, exige elegir inicio y motivo, permite
  fin mensual exclusivo y explica que no copia indicaciones ni crea gastos.
  El alta inicial también permite un fin opcional; vacío conserva el contrato
  de vigencia abierta. Las validaciones de intervalo, sucesora única y permisos
  permanecen en el servidor; se anticipan intervalo vacío y motivo blanco en UI.
- La consulta de versiones está paginada y filtra el concepto, institución y
  ámbito exactos. Expone intervalos registrados, no afirma una vigencia efectiva
  que podría estar limitada por sucesoras. Desde cada fila se abre su historial.
- Se mantienen los componentes/tokens visuales, invalidación de caché financiera,
  aislamiento por usuario/institución y bloqueo de reenvío ante respuesta incierta.

Validación: build y auditoría de clases (235, sin incidencias) correctos. Ocho
pruebas de calendario por API correctas, incluidas dos nuevas de sucesión,
reenvío, conservación del historial, ámbito y permiso sensible histórico.
Antes de agregarlas pasaron también las 14 pruebas de calendario/auditoría.

Navegador real sobre Vite/Django local y una base SQLite temporal nueva:
septiembre conserva versión/indicación, octubre usa la sucesora sin copiar el
estado, noviembre respeta el fin exclusivo, historial anterior accesible y
reenvío rechazado sin duplicación. Intervalo vacío rechazado por el formulario.
Escritorio y formulario móvil de 390 px inspeccionados, sin desborde horizontal.
No se repitió PostgreSQL en este cambio de interfaz; su evidencia anterior es
149/149. Los datos reales y el checkout original permanecen intactos.

Siguiente verificación del flujo ya implementado: rechazo/reemplazo y pérdida
de respuesta de red en navegador. Administración de concesiones y medición de
volumen siguen pendientes; #36 no se considera aceptado ni cerrado.

## Checkpoint: aislamiento de la administración de concesiones

Al verificar la UI pendiente de concesiones (#10), dos pruebas nuevas revelaron
brechas del endpoint existente. No se observaron accesos reales: toda la
reproducción se hizo en bases sintéticas.

1. `PATCH` validaba capacidad en la institución de la concesión original, pero
   aceptaba cambiar `membresia` a otra institución no administrable (200).
2. El listado exigía capacidad administrativa en alguna institución y filtraba
   por cualquier membresía activa. Un admin en A/operador en B podía enumerar
   concesiones de B. La prueba devolvió dos IDs cuando sólo correspondía uno.

La causa está en la combinación de controles comunes: autorización sobre el
objeto original y scope por membresías no comprueban por sí mismos el destino
de una FK modificable ni el ámbito administrativo de cada fila del listado.

Corrección acotada a `ConcesionFinancieraViewSet`: reutiliza `tiene_capacidad`
con `config_institucional` para limitar el queryset y validar la membresía de
destino antes de guardar. No se toca `apps.common`, no se agregan permisos ni
roles, ni se restringe la consulta propia `/mias/` por ser operador. El objeto
original sigue sujeto a autorización. Un recurso no administrable se oculta
con 404; un destino no autorizado se deniega con 403.

Las dos reproducciones fallaron antes del arreglo. Verificación posterior:
32 pruebas correctas de concesiones/calendario/auditoría/OpenAPI. Las pruebas
nuevas incluyen editar/revocar sin borrar otras concesiones ni la membresía,
rechazar sensibles/acciones administrativas en un operador, impedir traslado
institucional y no mezclar capacidades de instituciones distintas.
Se ajustó el caso de prueba de destino para no chocar antes con unicidad y
ejercitar realmente la autorización; no se relajaron rechazos como aceptación.

No se declara una auditoría general de todos los viewsets: el control común
podría requerir una revisión separada en otros recursos modificables. No hubo
migraciones ni cambios de datos reales. Revertir este arreglo reabriría las dos
brechas; ante un problema de UI, retirar sólo la UI y conservar estos controles.

## Checkpoint: operación de concesiones y validación final del corte

`Administración → Usuarios → Permisos financieros` permite consultar, otorgar,
editar el alcance y revocar concesiones usando la API existente. La entrada
requiere `config_institucional`; no depende de que el administrador se haya
otorgado lectura de gastos. Persona y acción se eligen explícitamente; editar
alcance no cambia su membresía ni acción. No hay permisos por defecto.

Los selectores recorren todas las páginas y se limitan a la institución actual.
Consultas y formularios se aíslan por usuario/institución; las mutaciones
invalidan permisos propios y datos financieros. Se bloquea doble envío y una
respuesta incierta exige volver a consultar. La revocación tiene confirmación
de persona/acción/ámbito, sin borrar gastos, costos ni auditorías. Una membresía
inactiva no recibe ampliaciones por UI; concesiones incompatibles con su rol
actual advierten que la parte administrativa/sensible no aplica y permiten
revocación. El servidor vuelve a validar cada acción.

Pruebas de navegador sobre base sintética: alta por área, rechazo de alcance
vacío, edición Guardia→Cirugía, revocación sólo de `ver_gastos` y nuevo ingreso
del operador. Conserva registrar gastos, pero no puede consultar el listado;
no se muestran acciones administrativas ni la opción sensible para su rol.
Modal móvil de 390 px inspeccionado sin desborde. El comportamiento de una
concesión incompatible tras cambiar el rol tiene pruebas backend y verificación
estática de UI; no otro recorrido específico de navegador en este corte.

Validación conjunta final: **154 pruebas correctas, sin omisiones**, sobre
PostgreSQL 16.15 en contenedores aislados, código actual en bind mount sólo
lectura, red interna sin puertos y base efímera. Comando de regresión: el mismo
del checkpoint OpenAPI anterior. Incluye Finanzas (89), auditoría, motor/firma,
OpenAPI y concurrencia de recuperación/aprobación. Las 32 pruebas focalizadas
también pasaron en SQLite. Build y auditoría de 235 clases correctos;
`makemigrations finanzas --check --dry-run`: sin cambios.

Se retiraron únicamente el contenedor y la red PostgreSQL de esta validación.
No hubo despliegues ni bases reales. No se midió rendimiento con volumen
representativo ni se realizó una revisión técnica integral del PR acumulativo.
La validación automatizada/navegador del agente no demuestra aceptación o
comprensión del responsable. La revisión del arreglo de permisos debe incluir
el destino de la membresía y la combinación admin A/operador B, no sólo la UI.

#36 pasa a **In review**, no Done. #10 sigue In progress por el alcance mayor
de catálogo/valores. #37 entra en preparación técnica; no tiene implementación
de reparto autorizada: ver `2026-09-08-reparto-primera-base-propuesta.md`.
