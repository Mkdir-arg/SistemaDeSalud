# Registros clinicos, padron e historia clinica

## Proposito

Mantener el registro longitudinal del ciudadano dentro de la institucion. El modulo separa dos accesos con permisos distintos sobre la misma persona: la **ficha administrativa** del padron (identificacion, domicilio, cobertura, consentimiento) y la **historia clinica** (antecedentes, evolucion, estudios, recetas).

## Actores

- Administrativo de admision, sobre el padron.
- Medico.
- Enfermeria.
- Auditor clinico.
- Paciente como titular de los datos.

## Alcance implementado

- Ciudadanos por institucion con documento normalizado.
- Padron de pacientes: listado, busqueda por nombre o documento, alta y ficha administrativa.
- Afiliaciones vigentes del ciudadano, separadas de la cobertura declarada como texto libre.
- Consentimiento de tratamiento de datos: otorgar y revocar desde la ficha.
- Historia clinica por ciudadano.
- Antecedentes, alergias y condiciones.
- Entradas de historia con firma, matricula y sello encadenado.
- Estudios.
- Recetas.
- Busqueda/listado de historias y detalle de historia.

## Reglas de negocio

- El ingreso de un caso asegura la existencia de historia clinica.
- El documento no vacio debe ser unico por institucion.
- Ver el padron no habilita leer la historia clinica: son dos capacidades distintas (`padron_admision` y `historia_clinica`). El rol administrativo tiene la primera y no la segunda.
- La firma de una entrada preserva autor, matricula y sello.
- La cadena de sellos aporta integridad y evidencia de no alteracion.
- Estudios y recetas pueden originarse desde el caso.
- La lectura clinica debe auditarse cuando aplica.
- La afiliacion verificada de un financiador no reemplaza la obra social declarada como texto: conviven y se muestran separadas.

## Pantallas y rutas

- `/padron` — padron de pacientes: paciente, cobertura, domicilio y estado del consentimiento.
- `/padron/:id` — ficha administrativa: documento, codigo, fecha de nacimiento, domicilio, alta en padron, cobertura y consentimiento.
- `/historia` — listado de historias clinicas.
- `/historia/:id` — detalle de historia clinica.
- Acciones clinicas dentro de `/casos/:id`.

## Entidades y endpoints

- `ciudadanos`, `historias-clinicas`, `entradas-historia`, `estudios`, `recetas`, `consentimientos`
- Acciones funcionales: verificacion de historia, firma de entrada, recetas y estudios desde caso.

## Integraciones

- Casos: origen de registros durante atencion.
- Auditoria: acceso a datos clinicos.
- Consentimiento: base legal de tratamiento de datos.
- Farmacia: trazabilidad de consumo por caso/paciente.
- Financiadores: afiliaciones vigentes y cobertura del paciente sobre la ficha administrativa.

## Referencias

- [Financiadores, cobertura y copagos](../financiadores-cobertura/README.md)
- `docs/ROLES-Y-PERMISOS.md`

## Puntos a validar

- Politica de intercambio interinstitucional de historia clinica.
- Estandares FHIR requeridos por jurisdiccion y alcance del consentimiento.
