# Rol: Auditor estatal

> Lee **quién consultó la historia clínica de quién**, con alcance estatal. No opera
> nada, no modifica nada y no puede borrar el registro que audita.
> Técnicamente: membresía con rol `auditor`.

**Usuario de demo:** `auditor@salud.local` / `demo1234`

---

## 1. En una frase

Existe porque la Ley 26.529 exige poder responder «quién vio esta historia clínica y
cuándo», y porque esa respuesta no se la puede dar el mismo equipo que atiende.

## 2. Qué ve al entrar

Su menú tiene **una sola entrada**: Registro de accesos. La aplicación se ve
deliberadamente vacía: no tiene casos, ni pacientes, ni configuración.

## 3. Funcionalidades

#### Registro de accesos (`/accesos`)
- Cada lectura de información clínica sensible queda registrada: quién, qué
  paciente, qué recurso, desde qué institución, cuántos resultados, con qué IP y
  cuándo.
- Se puede consultar **por paciente**, para responder un reclamo concreto.
- El alcance es **estatal**: ve los accesos de todas las instituciones, no de una.
- Incluye los accesos originados por la fachada FHIR.

## 4. Permisos

| Acción | Auditor |
|---|---|
| Leer el registro de accesos clínicos, en todas las instituciones | ✅ |
| Crear, editar o borrar registros de auditoría | ❌ Por diseño |
| Ver la historia clínica en sí | ❌ Ve el registro de accesos, no el contenido |
| Operar casos, turnos, filas, internación, farmacia, red | ❌ |
| Administrar instituciones, usuarios o redes | ❌ |
| Diseñar flujos o formularios | ❌ |

Capacidad exacta: sólo `auditoria`. Es el rol con menos capacidades del sistema, y
está bien así.

## 5. Notas

- El registro de accesos **es tan sensible como lo que audita**: dice quién se
  atendió dónde, con nombre y documento. Por eso no lo ve cualquier rol asistencial;
  lo ven el auditor, plataforma, el admin de institución y el jefe de área, y los dos
  primeros con alcance estatal.
- Auditar es una función de control, no de conducción asistencial: un médico no
  audita a sus colegas.
- La auditoría **financiera** es otra cosa y tiene su propio permiso
  (`auditar_finanzas`). Este rol no la incluye.
