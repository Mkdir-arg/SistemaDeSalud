# Agenda y turnos programados

## Proposito

Gestionar turnos programados para profesionales o recursos, evitando conflictos de horario, permitiendo sobreturnos controlados y conectando la llegada del paciente con la apertura de un caso.

## Actores

- Administrativo de mostrador o telefono.
- Profesional o servicio con agenda.
- Configurador que define disponibilidad.
- Paciente citado.

## Alcance implementado

- Agendas por institucion y area, de tipo profesional o recurso.
- Modalidad presencial, virtual o mixta.
- Disponibilidades semanales con vigencia, cupos y duracion.
- Bloqueos por rango, con listado de turnos afectados.
- Grilla diaria y semanal.
- Proximos horarios libres.
- Reserva, confirmacion, cancelacion, ausente, llegada, cambio de modalidad y reprogramacion.

## Estados de turno

- `reservado`
- `confirmado`
- `presente`
- `ausente`
- `cancelado`

## Reglas de negocio

- Reservar y reprogramar pasan por el motor para evitar doble asignacion concurrente.
- Cancelar libera el horario.
- Ausente no libera el horario: la oportunidad de atencion se perdio.
- La llegada abre un caso si la agenda tiene flujo asociado.
- Bloquear agenda no cancela automaticamente: informa turnos afectados para gestionarlos.
- Un turno virtual requiere enlace valido, propio del turno o heredado de la agenda.

## Pantallas y rutas

- `/agenda`
- Componentes administrativos de horarios dentro de estructura/areas.

## Entidades y endpoints

- `agendas`, `disponibilidades`, `bloqueos-agenda`, `turnos`
- Acciones funcionales: `dia`, `semana`, `proximos-libres`, `cancelar`, `confirmar`, `ausente`, `llegada`, `modalidad`, `reprogramar`.

## Integraciones

- Ciudadanos e historia clinica.
- Flujos/casos al registrar llegada.
- Estructura organizativa por area.

## Puntos a validar

- Politica institucional para recordatorios y confirmacion automatica.
- Reportes de ausentismo por servicio, profesional, origen y franja horaria.
