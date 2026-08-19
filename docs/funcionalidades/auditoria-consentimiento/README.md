# Auditoria, consentimiento e integridad

## Proposito

Proteger datos clinicos y dejar evidencia de acceso, consentimiento y firma. En un sistema hospitalario estatal, este modulo sostiene rendicion de cuentas, cumplimiento normativo y confianza institucional.

## Actores

- Paciente o representante.
- Profesional que registra o consulta.
- Auditor institucional.
- Gestion estatal.
- Administrador de seguridad.

## Alcance implementado

- Registro de accesos clinicos.
- Consulta de accesos por paciente.
- Consentimientos y revocaciones.
- Entradas clinicas firmadas con sello.
- Auditoria de lectura clinica mediante mixin en recursos sensibles.

## Reglas de negocio

- La urgencia asistencial no debe bloquearse por ausencia de consentimiento, pero debe quedar evidencia.
- El consentimiento identifica modo, alcance, institucion y quien lo toma.
- Las lecturas de informacion clinica sensible deben registrarse.
- La firma de entradas preserva autoria y matricula.
- La integridad de la historia se apoya en hash/sello encadenado.

## Pantallas y rutas

- `/accesos`
- Secciones de consentimiento y firma dentro de historia clinica.

## Entidades y endpoints

- `accesos-clinicos`
- `consentimientos`
- `entradas-historia`

## Integraciones

- Registros clinicos: historia, entradas, estudios y recetas.
- Identidad: usuario, rol, membresia e institucion.
- Casos: contexto asistencial que justifica accesos.

## Referencias

- `docs/ROLES-Y-PERMISOS.md`

## Puntos a validar

- Adecuacion juridica final segun jurisdiccion, ley aplicable y politica de privacidad.
- Retencion, exportacion y respuesta ante solicitudes de acceso del paciente.
