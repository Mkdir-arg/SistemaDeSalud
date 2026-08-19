# Documentacion funcional por modulo

Actualizado: 2026-08-18

Este directorio es la fuente de verdad funcional del sistema. Organiza la documentacion por funcionalidad para que analisis, desarrollo, validacion operativa y gestion estatal puedan leer el sistema por procesos reales y no por archivos de codigo.

No reemplaza los documentos de capacitacion, marca, capturas o handoff visual ya existentes en `diseno/docs`. Cuando una pantalla o un material de entrenamiento ya existe, se referencia desde aca y no se duplica.

## Modulos cubiertos

- [Identidad, roles y accesos](identidad-accesos/README.md)
- [Estructura organizativa](estructura-organizativa/README.md)
- [Formularios](formularios/README.md)
- [Flujos y motor de procesos](flujos-motor/README.md)
- [Casos, guardia y filas](casos-guardia-filas/README.md)
- [Agenda y turnos programados](agenda-turnos/README.md)
- [Internacion y camas](internacion-camas/README.md)
- [Farmacia e insumos](farmacia-insumos/README.md)
- [Red estatal y traslados](red-traslados/README.md)
- [Registros clinicos e historia clinica](registros-clinicos/README.md)
- [Auditoria, consentimiento e integridad](auditoria-consentimiento/README.md)
- [Interoperabilidad FHIR](interoperabilidad-fhir/README.md)
- [Operacion y monitoreo](operacion-monitoreo/README.md)
- [Tablero, supervision y notificaciones](tablero-notificaciones/README.md)

## Criterio de actualizacion

Cada carpeta describe: proposito funcional, actores, alcance actual, reglas de negocio, estados relevantes, pantallas/rutas, entidades/endpoints, integraciones y puntos a validar.

## Documentacion relacionada que no se duplica

- `docs/ROLES-Y-PERMISOS.md`: matriz detallada de roles, capacidades y permisos.
- `docs/NOTIFICACIONES.md`: especificacion focalizada de notificaciones.
- `docs/ESCENARIO-GUARDIA.md`: escenario de referencia para guardia.
- `docs/FUNCIONALIDADES-ESTRUCTURA-Y-FLUJOS.md`: detalle historico de estructura, formularios y flujos.
- `diseno/docs/*`: manual de marca, sistema de diseno, arquitectura visual, pantallas, modelo de datos, handoff y capturas.
