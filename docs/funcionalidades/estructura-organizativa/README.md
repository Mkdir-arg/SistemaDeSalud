# Estructura organizativa

## Proposito

Representar el establecimiento de salud como una organizacion operable: instituciones, areas, subareas, grupos de trabajo, boxes y camas. Esta estructura alimenta permisos, derivaciones, filas, internacion, agendas y supervision.

## Actores

- Configurador institucional.
- Jefe de area.
- Administrativo de admision o gestion operativa.
- Equipos asistenciales que trabajan por grupo, box o sector.

## Alcance implementado

- Instituciones con tipo, CUIT, direccion, estado y coordenadas.
- Areas y subareas.
- Grupos de trabajo por area con miembros.
- Boxes para llamado y atencion.
- Camas vinculadas a area/subarea, con sector y estado operativo.
- Agendas asociadas al area.

## Reglas de negocio

- El area es la unidad funcional principal para flujo, supervision, agenda y derivaciones.
- Los grupos restringen quien puede tomar, llamar o avanzar un paso cuando el nodo los declara.
- Un grupo pertenece a un area y **solo admite personas de esa area**: con membresia en la institucion y esa area asignada. El grupo es nombre mas integrantes; no tiene rol ni funcion propia.
- Un box puede estar libre u ocupado por un caso.
- Una cama ocupada debe tener caso asociado; una cama sin caso no puede figurar como ocupada.
- Al liberar una cama, puede pasar a higiene antes de volver a libre.
- Las instituciones no se eliminan: la auditoria clinica y los flujos las protegen. La unica baja posible es la de estado.

## El ambito de un flujo

Un flujo puede pertenecer a la institucion completa, a un area o a una subarea:

| Ambito | `area` | `subarea` | Significado |
|---|---|---|---|
| `institucion` | nula | nula | Proceso de toda la institucion |
| `area` | seteada | nula | Proceso general del area |
| `subarea` | derivada | seteada | Proceso especifico de la subarea |

- Fijar una subarea **deriva el area** automaticamente, para que los filtros y listados por area sigan funcionando.
- El selector de subarea aparece al crear el flujo solo si el area elegida tiene subareas, con una leyenda del alcance resultante. El listado muestra el ambito como `Area > Subarea`, y duplicar un flujo conserva su subarea.
- El ambito se define al crear. Moverlo despues es posible por API (`PATCH /flujos/{id}/`) pero no tiene pantalla.

## Pantallas y rutas

- `/estructura` — listado de areas.
- `/estructura/:areaId` — ficha del area.
- `/estructura/:areaId/:seccion` — cada seccion es una pagina propia: `datos`, `staff`, `grupos`, `boxes`, `agendas`, `subareas`.
- `/estructura/:areaId/sub/:subId` — ficha de la subarea, que cuelga aparte porque lleva su propio id y no es una seccion.

Cada seccion tiene su accion principal: asignar profesional, crear grupo, crear box, crear agenda, crear subarea.

## Entidades y endpoints

- `instituciones`, `areas`, `subareas`, `grupos`, `boxes`, `camas`, `estadias-cama`
- Escritura con `config_institucional`, salvo `instituciones` (`gobierno_plataforma`), la accion `camas/{id}/estado` y `estadias-cama` (`internacion`).

## Integraciones

- Flujos: nodos por area, sector, grupos responsables y derivaciones.
- Casos: area actual, llamado por box y asignacion a grupos.
- Internacion: camas y estadias.
- Agenda: agendas asociadas a area.
- Red: destino sugerido por establecimiento y area.

## Referencias

- `diseño/docs/04-pantallas.md`
- `diseño/docs/captures-manual/`

## Puntos a validar

- Nomenclador estatal unico para tipos de area, sectores y servicios.
- Politica de cierre historico cuando se desactiva un area con casos o camas activas.
