# Verificación y claridad del reparto por actividad

Fecha: 2026-09-09  
Alcance: correcciones de revisión del primer incremento de #37.

## Objetivo

Evitar que un gasto se reparta sobre actividad incompleta y explicar el impacto
con palabras y totales comprensibles para la administración de un hospital.

## Decisión aprobada

La actividad de un área sólo se considera **verificada** cuando coinciden dos
condiciones distintas:

1. **Integridad técnica:** todas las atenciones completadas que el sistema puede
   contrastar tienen su hecho financiero y no presentan diferencias de
   institución, área o fecha.
2. **Cobertura operativa:** una persona autorizada confirma que, desde el mes
   elegido, el área registra toda su actividad en el sistema.

Una confirmación operativa no puede ocultar una inconsistencia técnica. Si la
integridad deja de verificarse, el gasto queda pendiente y conserva todo su
importe sin atribuir.

La verificación técnica usa el evento de atención únicamente como control de
conciliación. El origen financiero durable continúa siendo
`HechoAtencionCosteable`.

## Presentación para el usuario

Antes de confirmar se mostrará:

- área, concepto y mes;
- estado `Actividad verificada` o `Actividad incompleta`;
- diferencia encontrada, si existe;
- importe aprobado visible para sus permisos, que se distribuirá o quedará
  pendiente;
- cantidad total de atenciones incluidas;
- importe estimado por atención cuando el divisor sea mayor que cero.

El botón describirá la acción y permanecerá deshabilitado ante una
inconsistencia técnica. La misma explicación quedará visible en la pantalla de
Finanzas. La tabla principal mostrará sólo resultados vigentes; las versiones
anteriores quedarán en un historial separado para evitar sumas aparentes.

## Otras correcciones del mismo bloque

- El procesamiento por lotes alcanzará también los gastos posteriores al primer
  lote y registrará como pendientes los gastos institucionales sin área.
- `configurar_repartos` permitirá consultar el catálogo necesario sin conceder
  permisos para modificarlo.
- Las correcciones de cobertura y reglas conservarán ámbito y vigencia, exigirán
  un motivo y seguirán siendo inmutables.
- Las altas concurrentes de cobertura se serializarán por área.

## Validación esperada

- Más de cien gastos no dejan elementos sin procesar.
- Un gasto institucional aparece como pendiente y no se redistribuye.
- El permiso exclusivo de reparto permite completar el formulario.
- Una inconsistencia técnica impide habilitar y procesar el reparto.
- Dos coberturas concurrentes no quedan activas para el mismo intervalo.
- Atenciones de otra institución, área o mes nunca reciben atribuciones.
- La suma de centavos vigentes coincide exactamente con el importe del gasto y
  sus ajustes.

## Resultado implementado

La explicación quedó visible en Finanzas y en el formulario de configuración.
La pantalla distingue expresamente el control técnico de la confirmación
operativa, muestra la diferencia, el importe aprobado visible, la cantidad de
atenciones y el estimado por atención. También separa los resultados vigentes
del historial para que no parezcan acumulables.

La conciliación bloquea la habilitación y el reparto si falta un hecho
financiero o si una atención aparece asociada a otra institución, área o mes.
Los gastos institucionales sin área quedan pendientes y el procesamiento por
lotes recorre todos los gastos, no sólo los primeros cien.

Validación del 2026-09-09: 109 pruebas de `apps.finanzas` correctas sobre
PostgreSQL 16 aislado, incluidas concurrencia, diferencias técnicas, separación
por ámbito, cierre exacto en centavos y lote de 102 gastos; migraciones sin
cambios pendientes; build Vite y auditoría de 235 clases correctos.
