# Red estatal y traslados

## Proposito

Coordinar derivaciones entre establecimientos de una red sanitaria estatal. El modulo permite solicitar, aceptar, rechazar, cancelar, marcar en camino, recibir o registrar que el paciente no llego, manteniendo casos separados por institucion.

## Actores

- Establecimiento de origen.
- Establecimiento de destino.
- Central de derivaciones o regulacion.
- Equipo de traslado.
- Gestion estatal que monitorea saturacion y disponibilidad.

## Alcance implementado

- Redes de instituciones.
- Destinos posibles desde una institucion.
- Tablero de red.
- Solicitud de traslado desde un caso.
- Aceptacion con apertura de caso en destino.
- Rechazo con motivo.
- Cancelacion por origen antes de apertura efectiva.
- Marca de ambulancia/en camino.
- Recepcion en destino.
- Registro de no llegada.

## Estados de traslado

- `solicitado`
- `aceptado`
- `rechazado`
- `en_camino`
- `recibido`
- `cancelado`
- `fallido`

## Reglas de negocio

- El traslado vincula dos instituciones, pero los casos siguen perteneciendo a cada una.
- Solo el origen puede solicitar, cancelar y marcar en camino.
- Solo el destino puede aceptar, rechazar y recibir.
- Cualquiera de las dos partes puede registrar no llegada si corresponde.
- Aceptar abre caso del lado destino.
- Recibir cierra la espera del origen segun motor de traslado.
- La seleccion de destino debe considerar red, ocupacion y distancia cuando los datos existen.

## Pantallas y rutas

- `/red`
- Acciones de traslado desde `/casos/:id`.

## Entidades y endpoints

- `redes`
- `traslados`
- Acciones funcionales: `solicitar`, `aceptar`, `rechazar`, `cancelar`, `en-camino`, `recibido`, `no-llego`, `destinos`, `tablero`.

## Integraciones

- Casos: caso origen y caso destino.
- Estructura: instituciones, areas y camas.
- Internacion: disponibilidad de camas.
- Tablero: saturacion de red.

## Puntos a validar

- Roles especificos de central reguladora si opera por encima de establecimientos.
- Criterios normativos para rechazo, prioridad, ambulancia y trazabilidad interjurisdiccional.
