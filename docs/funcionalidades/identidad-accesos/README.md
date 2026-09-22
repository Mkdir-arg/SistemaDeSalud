# Identidad, roles y accesos

## Proposito

Gestionar usuarios, membresias institucionales, roles, legajos profesionales y seleccion de institucion activa. Es la base de seguridad funcional del sistema: ninguna operacion sanitaria, administrativa o estatal deberia ejecutarse sin conocer quien actua, desde que institucion y con que capacidad.

## Actores

- Administrador general.
- Configurador institucional.
- Administrativo.
- Medico y enfermeria.
- Jefe de area.
- Usuario de un financiador, con membresia propia que no es institucional.

## Alcance implementado

- Inicio de sesion y seleccion de institucion.
- Usuarios y membresias activas por institucion, con nueve roles.
- Roles institucionales con capacidades derivadas.
- Legajo profesional asociado al usuario, con su actividad.
- Rutas protegidas por autenticacion e institucion activa.
- Menu lateral adaptado a capacidades funcionales.
- Permisos financieros explicitos por membresia, area y sensibilidad, administrados aparte del rol.
- Membresia de financiador, separada de la institucional, y activacion de la cuenta por invitacion.

## Reglas de negocio

- El permiso se resuelve por institucion, no por usuario en abstracto.
- Una persona puede tener diferentes roles en diferentes instituciones.
- Las acciones operativas se evaluan contra la institucion duena del objeto.
- Las acciones clinicas y de casos registran autor cuando generan eventos o movimientos.
- Reasignar un caso exige que el destinatario tenga membresia activa y pueda tomar el paso actual.
- El rol no concede permisos financieros: se otorgan de a uno, con su alcance, y no los hereda el administrador de institucion salvo las lecturas declaradas por rol.
- Un usuario de financiador elige una organizacion concreta; conocer un identificador valido no concede acceso a otra.

## Pantallas y rutas

- `/login`
- `/` — directorio de instituciones o entrada directa segun el rol.
- `/administracion` — usuarios, membresias y permisos financieros de la institucion.
- `/legajo` — legajo profesional propio y su actividad.
- `/financiadores/activar` — alta de la cuenta de un usuario invitado por un financiador.

## Entidades y endpoints

- `usuarios`
- `membresias`
- `legajos`
- `financiadores/{id}/usuarios` y `financiadores/activar` para el acceso del financiador.

## Referencias

- [`docs/ROLES-Y-PERMISOS.md`](../../ROLES-Y-PERMISOS.md) — matriz completa de roles, capacidades y permisos.
- [Financiadores, cobertura y copagos](../financiadores-cobertura/README.md)
- `diseño/docs/03-arquitectura-y-roles.md`

## Puntos a validar

- Politicas de bloqueo, caducidad o segundo factor si el despliegue estatal lo requiere.
- Circuito formal de alta/baja de profesionales y auditoria de cambios de membresia.
