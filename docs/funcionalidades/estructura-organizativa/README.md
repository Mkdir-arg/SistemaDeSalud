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
- Vista de estructura en frontend por area, subseccion y subarea.

## Reglas de negocio

- El area es la unidad funcional principal para flujo, supervision, agenda y derivaciones.
- Los grupos restringen quien puede tomar, llamar o avanzar un paso cuando el nodo los declara.
- Un box puede estar libre u ocupado por un caso.
- Una cama ocupada debe tener caso asociado; una cama sin caso no puede figurar como ocupada.
- Al liberar una cama, puede pasar a higiene antes de volver a libre.

## Pantallas y rutas

- `/estructura`
- `/estructura/:areaId`
- `/estructura/:areaId/sub/:subId`
- `/estructura/:areaId/:seccion`

## Entidades y endpoints

- `instituciones`, `areas`, `subareas`, `grupos`, `boxes`, `camas`, `estadias-cama`

## Integraciones

- Flujos: nodos por area, sector, grupos responsables y derivaciones.
- Casos: area actual, llamado por box y asignacion a grupos.
- Internacion: camas y estadias.
- Agenda: agendas asociadas a area.
- Red: destino sugerido por establecimiento y area.

## Referencias

- `docs/FUNCIONALIDADES-ESTRUCTURA-Y-FLUJOS.md`
- `diseno/docs/04-pantallas.md`
- `diseno/docs/captures-manual/`

## Puntos a validar

- Nomenclador estatal unico para tipos de area, sectores y servicios.
- Politica de cierre historico cuando se desactiva un area con casos o camas activas.
