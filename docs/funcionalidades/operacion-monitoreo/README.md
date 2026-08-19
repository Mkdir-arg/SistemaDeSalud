# Operacion y monitoreo

## Proposito

Dar senales simples y verificables sobre el estado tecnico del sistema para despliegue, soporte y monitoreo institucional. En un entorno hospitalario, detectar rapido una caida o un proceso detenido evita que el problema tecnico se transforme en demora asistencial.

## Actores

- Equipo tecnico.
- Mesa de ayuda.
- Operaciones de infraestructura.
- Gestion institucional o estatal que necesita evidencia de disponibilidad.

## Alcance implementado

- Endpoint publico de salud de aplicacion y base de datos.
- Endpoint autenticado de estado interno/procesos periodicos.
- Pruebas de respaldo para configuracion segura de produccion.
- Referencias de uso en setup de pruebas end-to-end.

## Reglas de negocio

- `/api/health/` debe contestar si la aplicacion puede atender y si llega a la base.
- Un fallo de base debe responder con estado de error para que el monitor lo detecte.
- `/api/estado/` no debe quedar abierto como `health`, porque expone informacion interna.
- El monitoreo no reemplaza auditoria funcional ni trazabilidad clinica.

## Rutas

- `GET /api/health/`
- `GET /api/estado/`

## Integraciones

- Despliegue y hosting.
- Pruebas end-to-end.
- Alertas externas de infraestructura.

## Puntos a validar

- Herramienta final de monitoreo en produccion.
- Politica de alertas, guardias tecnicas y escalamiento.
- Indicadores de disponibilidad requeridos por contrato o jurisdiccion.
