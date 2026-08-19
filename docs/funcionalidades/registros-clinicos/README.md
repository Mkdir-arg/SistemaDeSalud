# Registros clinicos e historia clinica

## Proposito

Mantener el registro clinico longitudinal del ciudadano dentro de la institucion: datos del paciente, historia clinica, entradas firmadas, estudios, recetas y antecedentes relevantes.

## Actores

- Medico.
- Enfermeria.
- Administrativo con alcance limitado.
- Auditor clinico.
- Paciente como titular de los datos.

## Alcance implementado

- Ciudadanos por institucion con documento normalizado.
- Historia clinica por ciudadano.
- Antecedentes, alergias y condiciones.
- Entradas de historia con firma, matricula y sello encadenado.
- Estudios.
- Recetas.
- Busqueda/listado de historias.
- Detalle de historia.

## Reglas de negocio

- El ingreso de un caso asegura la existencia de historia clinica.
- El documento no vacio debe ser unico por institucion.
- La firma de una entrada preserva autor, matricula y sello.
- La cadena de sellos aporta integridad y evidencia de no alteracion.
- Estudios y recetas pueden originarse desde el caso.
- La lectura clinica debe auditarse cuando aplica.

## Pantallas y rutas

- `/historia`
- `/historia/:id`
- Acciones clinicas dentro de `/casos/:id`.

## Entidades y endpoints

- `ciudadanos`, `historias-clinicas`, `entradas-historia`, `estudios`, `recetas`
- Acciones funcionales: verificacion de historia, firma de entrada, recetas y estudios desde caso.

## Integraciones

- Casos: origen de registros durante atencion.
- Auditoria: acceso a datos clinicos.
- Consentimiento: base legal de tratamiento de datos.
- Farmacia: trazabilidad de consumo por caso/paciente.

## Puntos a validar

- Politica de intercambio interinstitucional de historia clinica.
- Estandares FHIR requeridos por jurisdiccion y alcance del consentimiento.
