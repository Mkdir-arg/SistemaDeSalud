# Interoperabilidad FHIR

## Proposito

Exponer informacion sanitaria de Cauce en formato FHIR R4 y permitir que un flujo consulte un padron FHIR externo para completar datos del paciente. El objetivo funcional es integrarse con ecosistemas estatales o interinstitucionales sin romper la trazabilidad interna del sistema.

## Actores

- Sistemas externos autorizados.
- Equipo de interoperabilidad.
- Gestion estatal.
- Configurador de flujos que conecta un padron.
- Auditor de accesos clinicos.

## Alcance implementado

- Fachada FHIR R4 de solo lectura fuera de `/api/`, bajo `/fhir/`.
- `GET /fhir/metadata` como CapabilityStatement.
- Recurso `Patient`: lectura por id y busqueda por identificador/apellido.
- Recurso `Encounter`: lectura por id y busqueda por paciente, estado y fecha.
- Recurso `Organization`: lectura y busqueda de instituciones.
- Respuestas con `application/fhir+json`.
- Errores en formato FHIR `OperationOutcome`.
- Auditoria de accesos clinicos realizados por la fachada FHIR.
- Consulta a padron FHIR externo desde nodo de servicio/configuracion de flujo.

## Reglas de negocio

- La fachada FHIR es de solo lectura: no admite escritura directa de pacientes, episodios u observaciones.
- La escritura sanitaria debe seguir pasando por el motor de Cauce para conservar permisos, eventos y reglas.
- La fachada respeta los mismos permisos funcionales que la API interna.
- Las busquedas devuelven `Bundle`, aun cuando no haya resultados.
- Los resultados se limitan para evitar consultas masivas sin control.
- El padron FHIR externo solo completa campos vacios del paciente; no pisa datos cargados por una persona.
- Si el padron externo no responde o responde mal, el flujo no debe caer de forma abrupta.

## Pantallas y rutas

- No tiene pantalla operativa propia.
- Se configura desde el editor de flujos cuando un nodo usa modo `Padron FHIR`.
- Base tecnica: `/fhir/`.

## Recursos y endpoints

- `/fhir/metadata`
- `/fhir/Patient`
- `/fhir/Patient/<id>`
- `/fhir/Encounter`
- `/fhir/Encounter/<id>`
- `/fhir/Organization`
- `/fhir/Organization/<id>`

## Integraciones

- Registros clinicos: `Patient`.
- Casos: `Encounter`.
- Instituciones: `Organization`.
- Auditoria: registro de accesos clinicos por FHIR.
- Flujos: consulta a padron FHIR externo para completar datos del paciente.

## Puntos a validar

- Perfiles FHIR exigidos por la jurisdiccion.
- Autenticacion requerida por clientes externos en produccion.
- Mapeo futuro de recursos adicionales como `Observation`, `MedicationRequest` o `ServiceRequest`.
