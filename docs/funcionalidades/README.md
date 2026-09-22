# Documentacion funcional por modulo

Actualizado: 2026-09-22 (verificado contra `main` en `fca71e3`)

Este directorio es la fuente de verdad funcional del sistema. Organiza la documentacion por funcionalidad para que analisis, desarrollo, validacion operativa y gestion estatal puedan leer el sistema por procesos reales y no por archivos de codigo.

Cada ficha describe: proposito funcional, actores, alcance actual, reglas de negocio, estados relevantes, pantallas/rutas, entidades/endpoints, integraciones y puntos a validar. Lo que describe un trabajo terminado y no el estado actual no vive aca: se archiva en [`docs/historico/`](../historico/README.md).

## Modulos cubiertos

### Identidad y configuracion

- [Identidad, roles y accesos](identidad-accesos/README.md)
- [Estructura organizativa](estructura-organizativa/README.md)
- [Formularios](formularios/README.md)
- [Flujos y motor de procesos](flujos-motor/README.md)

### Atencion

- [Casos, guardia y filas](casos-guardia-filas/README.md)
- [Agenda y turnos programados](agenda-turnos/README.md)
- [Internacion y camas](internacion-camas/README.md)
- [Registros clinicos, padron e historia clinica](registros-clinicos/README.md)
- [Red estatal y traslados](red-traslados/README.md)

### Recursos y dinero

- [Farmacia e insumos](farmacia-insumos/README.md)
- [Finanzas, costos y cobros](finanzas-costos/README.md)
- [Financiadores, cobertura y copagos](financiadores-cobertura/README.md)

### Control y plataforma

- [Auditoria, consentimiento e integridad](auditoria-consentimiento/README.md)
- [Interoperabilidad FHIR](interoperabilidad-fhir/README.md)
- [Operacion y monitoreo](operacion-monitoreo/README.md)
- [Tablero, supervision y notificaciones](tablero-notificaciones/README.md)

## Documentacion relacionada que no se duplica

- [`docs/INDICE-FUNCIONAL.md`](../INDICE-FUNCIONAL.md): indice de toda la documentacion del repositorio, con su estado de vigencia.
- [`CONTEXT.md`](../../CONTEXT.md): glosario de finanzas y cobertura. Fija el vocabulario; no describe pantallas.
- [`docs/ROLES-Y-PERMISOS.md`](../ROLES-Y-PERMISOS.md): matriz detallada de roles, capacidades y permisos.
- [`docs/roles/`](../roles/README.md): el mismo modelo de autoridad contado rol por rol, pantalla por pantalla.
- [`docs/entornos/`](../entornos/README.md): los dos entornos locales y los recorridos verificados contra la aplicacion.
- [`docs/NOTIFICACIONES.md`](../NOTIFICACIONES.md): especificacion focalizada de notificaciones.
- [`docs/ESCENARIO-GUARDIA.md`](../ESCENARIO-GUARDIA.md): escenario de referencia para guardia.
- [`docs/historico/`](../historico/README.md): planes, auditorias y documentos cerrados. Explican por que el sistema es como es; no describen su estado actual.
- `diseño/docs/*`: manual de marca, sistema de diseño, arquitectura visual, pantallas, modelo de datos, handoff y capturas.
