# Flujos y motor de procesos

## Proposito

Modelar y ejecutar circuitos de atencion. Un flujo define el recorrido de un caso: recepcion, filas, formularios, decisiones, derivaciones, esperas, estudios, interconsultas, internacion, egresos y cierres.

## Actores

- Configurador o analista de procesos.
- Jefe de area.
- Equipos operativos que ejecutan cada paso.
- Auditor o gestion estatal que necesita trazabilidad del proceso.

## Alcance implementado

- Flujos con versiones.
- Editor visual de nodos y conexiones.
- Publicacion, ensayo y nueva version.
- Mapa de flujos.
- Nodos con area, grupos responsables, formularios y configuracion.
- Motor de avance de casos con eventos.

## Reglas de negocio

- Los flujos publicados no deberian editarse directamente; se trabaja con versiones.
- Un caso corre sobre una version del flujo.
- El nodo actual determina que acciones estan disponibles.
- Si un nodo declara grupos responsables, solo integrantes de esos grupos pueden tomar, llamar, avanzar o resolver ese paso.
- El motor registra eventos para trazabilidad.
- Los subprocesos como estudios o interconsultas pueden dejar el caso en espera hasta su retorno.

## Pantallas y rutas

- `/flujos`
- `/flujos/:id`
- `/mapa`

## Entidades y endpoints

- `flujos`, `versiones-flujo`, `nodos`, `conexiones`
- Acciones funcionales: `duplicar`, `publicar`, `ensayo`, `nueva-version`, `mapa`.

## Integraciones

- Formularios: captura de datos.
- Estructura: areas y grupos.
- Casos: ejecucion del flujo.
- Agenda: agenda puede abrir caso en un flujo al registrar llegada.
- Internacion: nodo cama.
- Red: derivacion interinstitucional desde un caso.

## Referencias

- `docs/FUNCIONALIDADES-ESTRUCTURA-Y-FLUJOS.md`
- `docs/ESCENARIO-GUARDIA.md`
- `diseno/docs/06-handoff-desarrollo.md`

## Puntos a validar

- Matriz formal de tipos de nodo y datos esperados por cada uno.
- Controles previos a publicacion para detectar pasos sin area, formulario, grupo o salida.
