# Tablero, supervision y notificaciones

## Proposito

Dar visibilidad operativa a equipos y jefaturas: trabajo pendiente, casos asignados, esperas, saturacion, notificaciones y alertas. Es la capa que permite gestionar el hospital en tiempo real.

## Actores

- Usuario operativo.
- Jefe de area.
- Administrativo.
- Gestion institucional.
- Gestion estatal cuando se agregan indicadores.

## Alcance implementado

- Inicio operativo y mi trabajo.
- Dashboard con metricas.
- Bandeja de tareas pendientes.
- Supervision de area.
- Notificaciones con resumen, lectura individual o masiva.
- Alertas generadas por asignaciones y eventos relevantes.
- Navegacion directa desde notificacion o busqueda.

## Reglas de negocio

- La bandeja debe separar asignados, tomables por grupo y esperas vencidas.
- El supervisor puede operar sobre casos de su area segun reglas de caso.
- Las notificaciones no reemplazan el estado real del caso; son disparadores de atencion.
- Marcar como leida no altera el evento funcional que la origino.
- Los tableros deben respetar institucion activa y capacidades del usuario.

## Pantallas y rutas

- `/inicio`
- `/dashboard`
- `/notificaciones`
- `/supervision`
- `/bandeja`

## Entidades y endpoints

- `notificaciones`
- `casos`
- Endpoints agregados de bandeja/supervision/resumen.
- Acciones funcionales: resumen de notificaciones, marcar leidas, tareas pendientes.

## Integraciones

- Casos y flujos.
- Identidad y permisos.
- Agenda, internacion, farmacia y red para indicadores operativos.

## Referencias

- `docs/NOTIFICACIONES.md`
- `diseno/docs/04-pantallas.md`

## Puntos a validar

- Indicadores oficiales para reporte estatal.
- Tableros por nivel: establecimiento, region sanitaria, provincia/municipio.
