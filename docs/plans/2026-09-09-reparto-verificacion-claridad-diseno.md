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
- importe total aprobado que se distribuirá o quedará pendiente;
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

