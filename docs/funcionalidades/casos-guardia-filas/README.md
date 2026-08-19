# Casos, guardia y filas

## Proposito

Gestionar la atencion de pacientes como casos trazables. El caso concentra estado, prioridad, nodo actual, area, asignacion, valores completados, fila, llamados, eventos y relacion con historia clinica.

## Actores

- Administrativo de admision.
- Enfermeria.
- Medico.
- Jefe de area.
- Paciente visible en pantalla publica de llamado.

## Alcance implementado

- Creacion e inicio de caso.
- Toma de caso por usuario habilitado.
- Llamado, rellamado, devolucion a cola y ausente.
- Avance por motor de flujo.
- Reasignacion, priorizacion y cancelacion por supervisor.
- Registro de eventos del caso.
- Filas con orden, urgencia, box, llamados y ausencias.
- Pantalla publica por token.

## Estados principales

- `recibido`
- `en_evaluacion`
- `en_espera`
- `derivado`
- `atendido`
- `cerrado`
- `cancelado`

## Reglas de negocio

- El caso debe asegurar historia clinica al crearse.
- Tomar, llamar, rellamar, devolver, marcar ausente y avanzar respetan grupos responsables del paso.
- Priorizar como urgente tambien impacta la fila si el caso esta esperando.
- Cancelar caso es accion de supervision del area.
- Llamar ocupa box; ausente libera box.
- La linea de tiempo del caso es evidencia funcional y clinica.

## Pantallas y rutas

- `/bandeja`
- `/filas`
- `/puesto/:id`
- `/casos`
- `/casos/:id`
- `/pantalla/:token`

## Entidades y endpoints

- `casos`, `valores-campo`, `items-fila`, `eventos-caso`
- Acciones funcionales: `tomar`, `llamar`, `rellamar`, `devolver`, `ausente`, `asignar`, `priorizar`, `cancelar`, `iniciar`, `avanzar`, `eventos`.

## Integraciones

- Flujos: define el paso actual y acciones.
- Estructura: area, grupos y boxes.
- Registros clinicos: historia, estudios y recetas.
- Internacion: asignacion y egreso de cama.
- Farmacia: consumo imputado a caso.
- Red: solicitud de traslado.

## Referencias

- `docs/ESCENARIO-GUARDIA.md`
- `docs/NOTIFICACIONES.md`
- `diseno/docs/captures-manual/`

## Puntos a validar

- Indicadores minimos para guardia: espera por prioridad, ausentismo, tiempos por nodo y saturacion por area.
- Politica de reapertura de casos cerrados si el circuito asistencial lo requiere.
