# Seguimiento hospitalario de cobertura y cobros

## Problema y alcance

El hospital ya puede generar obligaciones y registrar cobros, ajustes y reintegros. Falta reunir sus fuentes de cobertura para distinguir cuentas por cobrar, importes sin responsable y hechos cuya captura financiera no terminó. El usuario autorizó continuar este bloque, aplicar las recomendaciones y guardar los avances en el PR #41.

Se agrega «Seguimiento de cobros» en Coberturas y copagos. Reutiliza el detalle de cuenta y las operaciones existentes de Finanzas. No crea otro libro de dinero, conciliación bancaria, facturas, lotes de pagos, tablas ni permisos nuevos.

## Resultados observables

1. **Cuentas:** una fila por obligación de cobertura, incluyendo financiador, paciente y acuerdos posteriores. Permite abrir su cuenta y operar según las concesiones existentes. Totales del conjunto filtrado, sin sumar dos veces una prestación por tener varios movimientos o ajustes.
2. **Pendientes administrativos:** prestaciones realizadas con arancel/evaluación incompleta, reparto sin terminar o diferencia que nadie aceptó asumir. Los importes desconocidos permanecen desconocidos; una diferencia sin responsable no se trata como deuda exigible.
3. **Captura pendiente:** hechos asistenciales del circuito de cobertura sin snapshot o con captura incompleta, incluso cuando todavía no existe reserva. Son hechos registrados, sin inventar importes ni responsables. La gestión y recuperación conservan las acciones existentes.

## Contrato de consulta

`GET /api/seguimiento-cobros/` exige institución y `ver_dinero` en el ámbito consultado. Vistas `cuentas`, `pendientes` y `captura`, paginadas en servidor. Fecha inicial/final inclusiva de **la prestación**, área de origen, búsqueda; las cuentas admiten cobertura del caso, responsable y situación financiera. Los pendientes administrativos admiten financiador/estado; captura no filtra financiador, responsable ni estado porque pueden ser desconocidos y rechaza esas combinaciones explícitamente.

El período selecciona prestaciones; sus cobros y ajustes se consideran hasta el momento de la consulta, aunque se hayan registrado en otro mes. Para dinero recibido por fecha efectiva sigue existiendo el reporte de Dinero. Se conserva la fecha de generación y se explica que es una consulta operativa, no un cierre contable.

Las cuentas se relacionan mediante las FK de distribución y resolución, nunca interpretando el texto de contraparte. El listado de pendientes usa hospital/área del hecho original. Cada salida, total y opción de filtro respeta institución, área y sensibilidad. Roles clínicos, de financiador o de resolución administrativa por sí solos no habilitan leer movimientos de dinero. La captura aún incompleta exige lectura sensible porque su sensibilidad puede ser desconocida.

## Importes y estados

- Obligación actual = original + ajustes aprobados.
- Cobrado neto = cobros aprobados − reintegros aprobados.
- Por cobrar = máximo(actual − neto, cero), calculado **por cuenta** antes de sumar.
- A devolver = máximo(neto − actual, cero), por cuenta. No compensa deuda de otra persona ni del otro responsable.
- Cobros, reintegros y reducciones por aprobar se muestran aparte; los rechazados no modifican saldos.
- Una cuenta puede tener deuda y movimientos por aprobar simultáneamente. «Saldada» exige saldo cero y ausencia de operaciones pendientes de aprobación.

Un helper SQL de sólo lectura en `finanzas/saldos.py` consulta subconsultas independientes para ajustes/movimientos; se verifica contra `estado_obligacion`. Las operaciones de escritura y su bloqueo transaccional no cambian. Esto evita traer todo el período al navegador o bloquear todas las cuentas para obtener un total.

## Seguridad y validación

Se reutiliza la auditoría financiera estricta, agrupada por institución/área/sensibilidad/mes del conjunto que sustenta el reporte. Si no puede persistir, no se entrega la respuesta. Sin caché compartida. El detalle de cuenta vuelve a validar su acceso y cualquier operación conserva los permisos propios del dinero.

Pruebas previstas: totales contra cuentas, devoluciones sin compensación, acuerdos posteriores, varias aprobaciones/rechazos sin multiplicar importes, meses diferentes, paginación, origen conservado tras traslado, permisos negativos, sensibilidad desconocida, captura faltante, auditoría fallida y UI con filtros persistidos/invalidados tras registrar dinero. Demo aislada con datos ficticios; no se interviene localhost:8090 ni se migran datos reales.

Estas decisiones son recomendaciones del agente dentro del alcance autorizado. Se eligió consultar las fuentes existentes frente a crear conciliaciones persistidas o consolidar un nuevo libro: el incremento queda acotado y mantiene una única operatoria de dinero. Quedan fuera las autorizaciones previas y la aceptación del piloto.
