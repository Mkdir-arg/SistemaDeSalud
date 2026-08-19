# Identidad, roles y accesos

## Proposito

Gestionar usuarios, membresias institucionales, roles, legajos profesionales y seleccion de institucion activa. Es la base de seguridad funcional del sistema: ninguna operacion sanitaria, administrativa o estatal deberia ejecutarse sin conocer quien actua, desde que institucion y con que capacidad.

## Actores

- Administrador general.
- Configurador institucional.
- Administrativo.
- Medico y enfermeria.
- Jefe de area.

## Alcance implementado

- Inicio de sesion y seleccion de institucion.
- Usuarios y membresias activas por institucion.
- Roles institucionales con capacidades derivadas.
- Legajo profesional asociado al usuario.
- Rutas protegidas por autenticacion e institucion activa.
- Menu lateral adaptado a capacidades funcionales.

## Reglas de negocio

- El permiso se resuelve por institucion, no por usuario en abstracto.
- Una persona puede tener diferentes roles en diferentes instituciones.
- Las acciones operativas se evalúan contra la institucion dueña del objeto.
- Las acciones clinicas y de casos registran autor cuando generan eventos o movimientos.
- Reasignar un caso exige que el destinatario tenga membresia activa y pueda tomar el paso actual.

## Pantallas y rutas

- `/login`
- `/`
- `/administracion`

## Entidades y endpoints

- `usuarios`
- `membresias`
- `legajos`

## Referencias

- `docs/ROLES-Y-PERMISOS.md`
- `diseno/docs/03-arquitectura-y-roles.md`

## Puntos a validar

- Politicas de bloqueo, caducidad o segundo factor si el despliegue estatal lo requiere.
- Circuito formal de alta/baja de profesionales y auditoria de cambios de membresia.
