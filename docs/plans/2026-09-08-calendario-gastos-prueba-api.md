# Prueba del calendario mensual de gastos

## Estado del corte

La API permite configurar expectativas, consultar el calendario de un mes y
registrar indicaciones conservando su historial. Todavía no hay pantalla de
Finanzas en el frontend. Este recorrido requiere un entorno de prueba con las
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

## Evidencia de este corte

- `manage.py test apps.finanzas`: 72 pruebas, 70 correctas y 2 omitidas por
  requerir PostgreSQL en el entorno local SQLite.
- PostgreSQL aislado, código actual montado en sólo lectura: 10 pruebas de
  calendario e indicaciones correctas, incluidas vigencias, reemplazos,
  pendientes, ámbito institucional/área y sensibilidad.
- `makemigrations finanzas --check --dry-run`: sin cambios pendientes.
- Falta validación manual de interfaz y medición con volumen representativo.
  Los tests PostgreSQL de este corte no son una nueva prueba de concurrencia.

Para una prueba funcional por parte del usuario conviene completar la pantalla
de gastos y calendario y preparar un entorno demostrable con usuarios de ambos
perfiles. No hace falta esperar a reparto, pagos y reportería para probar este
recorrido completo.
