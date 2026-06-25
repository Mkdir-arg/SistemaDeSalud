# Notificaciones

> Avisos personales in-app. Documento vivo. Creado: **2026-06-25**.

## Modelo
`apps.casos.models.Notificacion`: `usuario` (destinatario), `titulo`, `detalle`,
`caso` (opcional, para enlazar), `leida`, `creada`. Personal: cada usuario ve solo
las suyas (no se scopea por institución).

## Cuándo se dispara (en `apps/casos/motor.py`)
| Evento | A quién | Dónde |
|---|---|---|
| Vuelve un **estudio/interconsulta** | al médico que lo pidió (`asignado_a` del caso de origen) | `_retornar_al_origen` |
| **Reasignación** de un caso | al nuevo responsable | endpoint `casos/{id}/asignar/` |
| **Caso urgente** llega a un paso de trabajo | a los integrantes de los grupos responsables del nodo | `_correr_automaticos` |
| **Cancelación** de un caso | al responsable asignado (si no es quien cancela) | `cancelar_caso` |

Helpers: `_notificar(usuario, …)` (individual) y `_notificar_grupo(nodo, …)` (a todo
el equipo responsable, con `bulk_create`).

## API (`/api/notificaciones/`, viewset personal)
- `GET /notificaciones/` — historial del usuario (paginado).
- `GET /notificaciones/resumen/` — `{no_leidas, items}` (para la campana; poll liviano).
- `POST /notificaciones/leer/` — marca leídas todas, o las de `{"ids": [...]}`.

## UI
- **Campana** en la barra superior (`components/Shell.jsx`, `Campana`): badge de no
  leídas, dropdown con los avisos, clic → navega al caso y marca leído, «Marcar
  todas», «Ver todas». Poll a `/resumen/` cada 30 s (pausa con pestaña oculta / al
  volver el foco).
- **Historial** (`pages/Notificaciones.jsx`, ruta `/notificaciones`): lista completa
  con marcar leídas.

## Tests
`apps/casos/test_supervision.py`: reasignación genera notificación, cancelación
avisa al responsable, privacidad entre usuarios, marcar leídas. Verificado además
end-to-end por HTTP (reasignación y urgente→equipo).

## Posibles mejoras
- Tiempo real (WebSocket/SSE) en vez de poll.
- Preferencias por usuario (qué eventos avisar).
- Aviso al equipo destino cuando llega una derivación no urgente (hoy solo urgentes,
  para no hacer ruido).
