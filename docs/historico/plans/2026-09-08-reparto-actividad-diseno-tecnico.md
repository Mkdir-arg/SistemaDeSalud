# Diseño técnico aprobado: primer reparto por actividad

Estado: diseño aprobado; primer checkpoint backend implementado. No autoriza
ejecución sobre datos reales.

Referencia: #37, módulo #33, contratos #10/#12 y fuentes #36. Complementa
`2026-09-08-reparto-primera-base-propuesta.md`: no reemplaza las condiciones
funcionales ya aprobadas.

## Alcance del primer corte

El reparto toma únicamente un gasto aprobado que tenga área. Una regla explícita
del mismo concepto, institución, área y mes distribuye su saldo entre las
atenciones completadas del mismo ámbito. No reparte gastos institucionales sin
área, no crea cargos, deudas, cobros ni pagos, y no altera los costos directos
existentes.

La cobertura es prospectiva: una habilitación por institución y área sólo vale
desde su fecha fiable hacia adelante. Los períodos anteriores nunca se infieren
como completos ni se retrocompletan. El flujo clínico conserva la creación
atómica del `HechoAtencionCosteable`; el reparto no agrega pasos al profesional.

## Contrato persistente mínimo

### Cobertura de actividad

`CoberturaActividadCosteable` representa la habilitación inmutable y versionada
de una fuente de atenciones por institución, área y vigencia. Conserva autor y
fecha de habilitación. No tiene campos para cargar conteos manuales ni para
declarar cobertura histórica.

Una cobertura ausente o una inconsistencia técnica detectada deja el gasto
pendiente; una declaración administrativa posterior no puede convertir ese
pendiente en un reparto sin una nueva evidencia válida. La primera migración no
creará registros ni realizará backfill.

### Regla de reparto

`ReglaRepartoActividad` es una versión inmutable por concepto, institución,
área y vigencia. Sólo expresa la única base inicial: cantidad de
`HechoAtencionCosteable` completados en ese mismo ámbito durante el mes. Las
versiones se encadenan con el patrón de vigencias ya usado por
`ExpectativaGasto`; no se edita ni elimina una regla vigente o histórica.

### Resultado y atribuciones

`RepartoGasto` conserva cada resultado o pendiente de una fuente. Debe guardar:

- gasto, regla aplicada cuando existe, número de versión y huella de insumos;
- importe original, suma de ajustes y saldo resultante, todos en centavos;
- estado y motivo explícito cuando no se puede repartir;
- saldo no atribuido cuando la actividad acreditada es realmente cero; y
- referencia a la versión anterior cuando cambian los insumos.

`AtribucionReparto` conserva una fila por hecho en una versión, con importe en
centavos. La suma de las atribuciones más el saldo no atribuido debe igualar
exactamente el saldo de la fuente. El residual se asigna en orden determinista
por ID estable del hecho.

Los ajustes tardíos, una nueva atención válida o una regla sucesora generan una
versión nueva. El mismo conjunto de insumos devuelve la misma versión. Si el
saldo queda negativo por ajustes, la nueva versión atribuye importes negativos
con la misma base; reduce el costo compartido y nunca se interpreta como cargo,
deuda, pago ni reintegro.

## Estados operativos

- Sin regla aplicable o sin cobertura acreditada: pendiente visible, no costo
  cero.
- Cobertura acreditada y denominador cero: resultado completo sin
  atribuciones; el saldo queda disponible en el mismo ámbito, sin trasladarlo
  a otros pacientes.
- Cobertura acreditada y denominador positivo: resultado distribuido, con
  cierre exacto en centavos.

El resultado vigente reemplaza al anterior para los totales. El historial sigue
consultable y nunca se suma junto con su versión sucesora.

## Permisos, lectura y operación

Se agrega únicamente la acción administrativa explícita
`configurar_repartos` a `ConcesionFinanciera`; habilita coberturas y reglas.
No se concede automáticamente y exige membresía administrativa. La consulta de
resultados de paciente usa el permiso existente `ver_costos` y conserva la
auditoría clínica correspondiente. Configurar no da lectura por sí solo.

El cálculo se ejecuta fuera de la atención clínica, mediante un comando de
recuperación separado que reutiliza el patrón de `procesar_costos`. No se
agregan colas, workers, dependencias ni infraestructura. La ejecución bloquea
la fuente de gasto, calcula una huella de los insumos y evita versiones dobles
ante reintentos o concurrencia.

Para el usuario hospitalario quedan dos configuraciones administrativas:
habilitar cobertura prospectiva y definir una regla por concepto. El personal
clínico no registra datos económicos ni ejecuta repartos.

## Conservación y límites

Coberturas, reglas, resultados y atribuciones son inmutables en API y modelo;
sus referencias financieras y clínicas usan retención que impida borrar la
trazabilidad. Un rollback de migración sobre registros reales no debe eliminar
esas evidencias. La primera entrega no agrega UI compleja, cierres mensuales,
reparto inter-área, bases de consumo/ocupación, pagos, cobros ni reportería.

## Validación requerida antes de incorporar código

- alcance por institución, área, sensibilidad y nueva concesión;
- períodos previos a la cobertura, falta de regla y falta de cobertura;
- denominador cero acreditado, residual positivo y reversión negativa;
- ajustes y atenciones tardías, sin sumar versiones históricas;
- reintento y concurrencia sobre una misma fuente;
- separación de `ImputacionCosto` y de cualquier cargo o pago; y
- recuperación por comando sobre datos sintéticos, sin afectar la atención.

## Estado de implementación

Implementado: modelos inmutables, migración `0018`, servicios de
cobertura/regla/cálculo idempotente, `procesar_repartos` y API mínima. Las rutas
de cobertura y reglas sólo admiten consulta/alta bajo `configurar_repartos`;
los resultados financieros explican versiones y pendientes sin exponer
pacientes. El detalle de costo clínico muestra por separado la atribución
vigente y exige lectura sensible cuando el gasto de origen lo es. No se altera
el total directo ni se concede lectura por configurar.

La operación administrativa ya está integrada en Finanzas con dos acciones:
`Habilitar actividad` y `Agregar regla`. La pestaña `Repartos` diferencia
resultados distribuidos y pendientes, muestra concepto, área, importe y cantidad
de atenciones, y mantiene el identificador técnico como trazabilidad secundaria.
Los textos aclaran que carga, aprobación y reparto son estados separados y que
el flujo no crea cargos, pagos ni tareas para personal clínico.

Validación local sobre SQLite efímero:

- 108 pruebas correctas (`apps.finanzas` y regresión de
  `apps.casos.test_esquema`), con tres pruebas PostgreSQL omitidas por motor;
- 99 pruebas financieras correctas sobre PostgreSQL 16 aislado, incluidas las
  tres pruebas de concurrencia para costeo directo, aprobación de gastos y
  reparto; la prueba detectó y permitió limitar el bloqueo del reparto a la fila
  fuente, sin intentar bloquear el área opcional;
- `manage.py check` correcto y
  `makemigrations finanzas --check --dry-run` sin cambios;
- build Vite correcto y auditoría de 235 clases sin huérfanas ni colisiones;
- prueba real de navegador en escritorio y 390 px, sin errores de consola:
  alta de cobertura y regla, ejecución de `procesar_repartos`, un gasto
  distribuido entre tres atenciones y otro pendiente por falta de regla; y
- la tabla y los formularios usan datos administrativos y no solicitan carga al
  personal clínico.

No se ejecutó despliegue, migración sobre una base real ni medición de volumen.

### Actualización de seguridad y claridad del 2026-09-09

La cobertura ahora exige dos evidencias separadas: conciliación técnica de las
atenciones completadas contra `HechoAtencionCosteable` y confirmación operativa
de que el área registra toda su actividad desde el mes indicado. Una diferencia
técnica bloquea la habilitación y conserva el importe completo como pendiente.

La interfaz explica esta diferencia en lenguaje administrativo y muestra, antes
de confirmar, el importe aprobado visible, el total de atenciones y el estimado
por atención. La tabla principal contiene sólo repartos vigentes y el historial
se consulta por separado. Las correcciones requieren motivo y conservan ámbito
y vigencia.

La validación complementaria sobre PostgreSQL 16 ejecutó correctamente las 109
pruebas de `apps.finanzas`; el build Vite y la auditoría de 235 clases también
fueron correctos. No se ejecutó despliegue ni migración sobre datos reales.
