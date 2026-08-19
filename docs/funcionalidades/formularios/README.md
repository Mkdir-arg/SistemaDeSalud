# Formularios

## Proposito

Permitir que la institucion modele datos clinicos, administrativos y operativos sin cambiar codigo. Los formularios definen los campos que se completan en pasos de flujo y alimentan la historia del caso.

## Actores

- Configurador institucional.
- Analista funcional.
- Equipos clinicos que definen contenido minimo de registros.
- Usuarios operativos que completan formularios durante la atencion.

## Alcance implementado

- Biblioteca de formularios por institucion y area.
- Constructor de campos.
- Duplicacion de formularios.
- Reordenamiento de campos.
- Consulta de usos del formulario en flujos.
- Eliminacion controlada desde pantalla.

## Reglas de negocio

- Un formulario puede ser reutilizado por diferentes pasos.
- La pantalla de detalle muestra donde se usa antes de modificarlo.
- Los campos obligatorios deben poder detectarse antes de publicar o usar el flujo.
- La configuracion de formularios define estructura de dato; no duplica documentos de capacitacion.

## Pantallas y rutas

- `/formularios`
- `/formularios/:id`

## Entidades y endpoints

- `formularios`
- `campos`
- Acciones funcionales: `duplicar`, `reordenar`, `usos`.

## Integraciones

- Flujos: nodos de tipo formulario.
- Casos: valores completados por campo.
- Historia clinica: registros derivados del caso cuando el motor lo indica.

## Referencias

- `docs/FUNCIONALIDADES-ESTRUCTURA-Y-FLUJOS.md`
- `diseno/docs/04-pantallas.md`

## Puntos a validar

- Versionado funcional de formularios publicados.
- Catalogo minimo estatal para campos sensibles o reportables.
