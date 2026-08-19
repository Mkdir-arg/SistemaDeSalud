# Internacion y camas

## Proposito

Administrar camas y estadias de internacion como parte del proceso asistencial. El modulo permite conocer disponibilidad real, asignar cama desde un caso, registrar pases y egresos sin perder trazabilidad.

## Actores

- Admision o gestion de camas.
- Enfermeria de sala.
- Medico tratante.
- Jefe de area o supervisor.

## Alcance implementado

- Camas por area, subarea y sector.
- Estados: libre, ocupada, higiene y bloqueada.
- Asignacion de cama desde nodo de flujo.
- Pase de sector o cama.
- Egreso de cama sin necesariamente cerrar el caso.
- Estadias historicas con motivo de egreso.
- Vista operativa de internacion.

## Reglas de negocio

- Una cama ocupada siempre tiene un caso asociado.
- Al internar, se registra estadia.
- El pase cierra la estadia anterior y abre una nueva.
- El egreso libera la cama y registra motivo.
- Si un caso se elimina, la cama asociada pasa a higiene para evitar falsa disponibilidad.
- La cama ofrecida depende del sector/area declarado por el nodo de flujo.

## Pantallas y rutas

- `/internacion`
- Acciones de cama dentro de `/casos/:id`.

## Entidades y endpoints

- `camas`
- `estadias-cama`
- Acciones funcionales de caso: `cama`, `pase`, `egreso-cama`.

## Integraciones

- Flujos: nodo cama.
- Casos: paciente internado, eventos y continuidad de proceso.
- Red: disponibilidad de camas para traslados.
- Tablero: ocupacion y saturacion.

## Puntos a validar

- Criterios estatales para bloqueo, aislamiento, higiene y disponibilidad operativa.
- Reportes de ocupacion por sector, giro cama y demoras de egreso.
