# Integrarse con I-Core Salud

> Para el área de sistemas que tiene que conectar otro sistema con éste.
> Verificado contra el código el 22/09/2026.

**La referencia completa es el esquema OpenAPI**, en `/api/docs/` (visor) y
`/api/esquema/` (el documento). Ahí está cada endpoint con sus parámetros y su
respuesta, y se genera desde el código, así que no se desactualiza.

Este documento es lo otro: las seis o siete cosas que el esquema no te dice y que
vas a necesitar igual.

---

## 1. Dos superficies distintas

| | Para qué | Base |
|---|---|---|
| **API REST** | Todo: leer y escribir | `/api/` |
| **Fachada FHIR R4** | Interoperar con un ecosistema sanitario | `/fhir/` |

La fachada FHIR es **de sólo lectura**, a propósito. La escritura sanitaria pasa
siempre por el motor, que es donde viven los permisos, los eventos y las reglas del
circuito. Un `Patient` creado por fuera sería un paciente sin historia y sin
auditoría.

> **`/fhir/` no pasa por el puerto de la aplicación.** El nginx del frontend proxea
> `/api/`, `/admin/` y `/static/`, no `/fhir/`. Hay que apuntar al backend directo.

## 2. Autenticación

JWT. No hay API keys.

```bash
curl -X POST https://HOST/api/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"email":"integracion@hospital.gob.ar","password":"..."}'
```

```json
{ "access": "eyJ...", "refresh": "eyJ..." }
```

```bash
curl https://HOST/api/casos/ -H "Authorization: Bearer eyJ..."
```

| | |
|---|---|
| Vida del `access` | **60 minutos** |
| Vida del `refresh` | **7 días** |
| Renovar | `POST /api/auth/token/refresh/` con `{"refresh": "..."}` |

Todo endpoint exige autenticación. La única excepción es `/api/health/`, que va sin
credenciales porque una sonda de monitoreo no tramita sesiones — y justamente por eso
no cuenta nada del sistema.

### Lo que hay que entender antes de escribir código

**Un usuario de integración es un usuario del sistema, con membresía y rol.** No hay
un modo «servicio» que esquive los permisos. Lo que ese usuario puede leer o escribir
depende de:

1. Su **membresía**: en qué institución, con qué rol, en qué áreas.
2. La **capacidad** que exija el recurso.
3. Para finanzas, además, sus **concesiones financieras** explícitas.

Conviene crearle una membresía con el rol mínimo que necesite, y no reutilizar un
superusuario. Ver [`ROLES-Y-PERMISOS.md`](ROLES-Y-PERMISOS.md).

## 3. Alcance por institución

**Es la regla que más sorprende.** Cada consulta se filtra por las instituciones donde
el usuario tiene membresía activa. No hay un parámetro que lo desactive.

Consecuencias prácticas:

- Un 404 no siempre significa «no existe»: puede significar «no existe **para vos**».
  Es deliberado — un 403 confirmaría que el identificador es válido.
- Si tu integración abarca varios efectores, el usuario necesita una membresía en
  cada uno.
- La escritura se valida contra la institución **dueña del objeto**, no contra la que
  venga en el cuerpo.

## 4. Listados

Paginación por número de página:

```
GET /api/casos/?page=2&page_size=50
```

| | |
|---|---|
| Tamaño por defecto | 25 |
| Máximo | **200**. Un `page_size` mayor se recorta, no da error |

```json
{ "count": 412, "next": "...?page=3", "previous": "...?page=1", "results": [ ... ] }
```

Filtros, búsqueda y orden:

```
GET /api/areas/?institucion=1
GET /api/casos/?estado=recibido&asignado_a=7
GET /api/ciudadanos/?search=gomez
GET /api/gastos/?ordering=-periodo_economico
```

Qué campos admite cada recurso está en el esquema. **No inventes parámetros**: uno
desconocido se ignora en silencio y vas a recibir el listado completo creyendo que
filtraste.

## 5. Acciones, no sólo CRUD

Buena parte del dominio **no se modela como campos editables** sino como acciones,
porque cada una tiene reglas y deja evidencia:

```
POST /api/casos/{id}/tomar/
POST /api/casos/{id}/avanzar/
POST /api/turnos/{id}/llegada/
POST /api/traslados/{id}/aceptar/
POST /api/pedidos-stock/{id}/entregar/
```

No intentes conseguir el mismo efecto con un `PATCH` sobre el campo de estado: el
motor no se entera, no se registra el evento y el caso queda inconsistente.

`GET /api/casos/{id}/eventos/` devuelve la línea de tiempo completa, que es la
trazabilidad que después se audita.

## 6. Operaciones monetarias: clave de reintento

Toda operación que mueve dinero lleva una **clave de idempotencia**. Ante una
respuesta incierta —timeout, corte— **reintentá con la misma clave**: el sistema
reconoce el intento y no duplica.

Cambiar el contenido económico con la misma clave es un conflicto, no una
modificación: se rechaza. Y la misma clave con otro contenido nunca se interpreta
como una corrección encubierta.

**No cierres y recrees una operación incierta sin consultar antes su historial.**

## 7. Errores

Formato estándar de DRF:

```json
{ "detail": "..." }
{ "campo": ["Mensaje de validación."] }
```

| Código | Qué significa acá |
|---|---|
| 400 | Validación, o una regla de negocio que no se cumple |
| 401 | Token ausente, vencido o inválido |
| 403 | Autenticado pero sin la capacidad o concesión necesaria |
| 404 | No existe **o no está en tu alcance** |
| 409 | Conflicto de versión: alguien cambió el registro mientras editabas |
| 503 | Un servicio del que depende la operación no está disponible |

La fachada FHIR usa su propio formato: **`OperationOutcome`**, como manda el
estándar, y siempre con `Content-Type: application/fhir+json`.

## 8. FHIR

```
GET /fhir/metadata                          CapabilityStatement
GET /fhir/Patient?identifier=...            búsqueda
GET /fhir/Patient/{id}
GET /fhir/Encounter?patient=...&status=...&date=...
GET /fhir/Organization
GET /fhir/Coverage?beneficiary=Patient/{id}
```

- Las búsquedas devuelven un `Bundle`, **también cuando no hay resultados**.
- Los resultados se limitan: no hay descarga masiva del padrón.
- `Coverage` se busca **por la referencia local del paciente, nunca por documento**, y
  exige `padron_admision` en la institución de la ficha.
- Respeta los mismos permisos que la API interna y **deja registro de acceso clínico**,
  igual que si la consulta viniera por pantalla.

Los perfiles FHIR exigidos por cada jurisdicción **todavía no están definidos**, y la
autenticación que se le va a pedir a un cliente externo en producción tampoco. Son
dos decisiones abiertas.

## 9. Integraciones salientes

Un nodo de flujo puede consultar un **padrón FHIR externo** para completar los datos
del paciente.

- Sólo completa **campos vacíos**: no pisa lo que cargó una persona.
- Si el padrón no responde o responde mal, **el flujo no se cae**.
- Los hosts se habilitan con una lista blanca (`SALUD_INTEGRACIONES_PERMITIDAS`) que
  **viene vacía**: la función está apagada hasta que infraestructura autorice cada
  host. Es una decisión de infraestructura, no del diseñador del flujo.
- Hay un tope de espera (6 s por defecto). El motor llama en línea, así que un
  servicio lento colgaría el avance del caso.

## 10. Antes de pedir una integración

Cosas que no existen y conviene no asumir:

- **No hay webhooks ni eventos salientes.** Si tu sistema necesita enterarse de algo,
  hoy es por consulta.
- **No hay versionado de la API.** No hay `/api/v1/`. Un cambio incompatible se
  coordina, no se descubre.
- **No hay límite de tasa** configurado. Eso no es una licencia para hacer polling
  agresivo contra un sistema hospitalario.
- **No hay conector a ningún sistema concreto.** La API está construida; el conector
  se define en el relevamiento.

## Referencias

- `/api/docs/` — el esquema, que es la referencia real.
- [`ROLES-Y-PERMISOS.md`](ROLES-Y-PERMISOS.md) — qué habilita cada capacidad.
- [`funcionalidades/interoperabilidad-fhir/`](funcionalidades/interoperabilidad-fhir/README.md) — el detalle funcional de la fachada.
- [`MODELO-DE-DATOS.md`](MODELO-DE-DATOS.md) — qué entidades hay y de qué cuelgan.
