# Roles y permisos en Cauce

> Análisis del modelo de autoridad y plan de mejora. Documento vivo.
> Creado: **2026-06-25**.

## 1. Dos ejes de autoridad

Cauce separa **quién sos** de **qué paso concreto operás**:

1. **Rol** — vive en `Membresia` (por institución, con un set de `areas`). Define el
   *tipo* de trabajo y los poderes de plataforma. Cuatro roles:
   `admin`, `configurador`, `administrativo`, `medico`.
2. **Grupo** — equipo por área (`instituciones.Grupo`). Rutea *qué nodos* puede
   tomar/operar una persona (lo usa el motor en `usuario_puede_tomar` y la pantalla
   «Mi trabajo»). Un nodo declara sus grupos responsables.

Regla mental: **el Rol abre la puerta del edificio; el Grupo abre la puerta de la
oficina.** Podés tener el rol `medico` pero solo operás los nodos de los grupos a
los que pertenecés.

## 2. Capacidades por rol (frontend)

`frontend/src/auth/InstitutionContext.jsx` mapea rol → capacidades, y el menú se
gatea por capacidad:

| Rol | config | diseño | trabajo | registros |
|---|:--:|:--:|:--:|:--:|
| **admin** | ✅ | ✅ | ✅ | ✅ |
| **configurador** | — | ✅ | — | — |
| **administrativo** | — | — | ✅ | ✅ |
| **medico** | — | — | ✅ | ✅ |

- `config` → Estructura organizativa, Administración (usuarios/accesos).
- `diseño` → Flujos, Mapa de flujos, Formularios.
- `trabajo` → Mi trabajo / Bandeja, Filas, Casos.
- `registros` → Historia clínica, Legajo.

## 3. Lo que se enforce HOY en el backend

- **Autenticación**: `IsAuthenticated` global (DRF).
- **Scope por institución**: `InstitucionScopedMixin` filtra el *queryset* a las
  instituciones donde el usuario tiene membresía activa (el superusuario ve todo).
- **Regla de atención**: `motor._exigir_medico` exige rol `medico` + área asignada
  para registrar una atención (el superusuario firma siempre).
- **Ruteo por grupo**: `motor.usuario_puede_tomar` — si el nodo declara grupos, hay
  que integrar alguno.

### ⚠️ El hueco: no hay autorización por rol en la API

`DEFAULT_PERMISSION_CLASSES = (IsAuthenticated,)` y el scope solo filtra *lectura*
(y el lookup de detalle). **No** restringe la escritura por rol, y `create` ni
siquiera pasa por el scope. Consecuencia: cualquier miembro de la institución
puede, vía API directa:

- crear / editar / **publicar** flujos, versiones, nodos y conexiones (diseño),
- crear / borrar áreas, sub-áreas, grupos y boxes (estructura),
- operar casos de su institución.

El menú del frontend lo esconde, pero la API no lo impide. Es una brecha real.

## 4. Plan de mejora (en capas)

### Capa 1 — Enforcement por rol en el backend  ✅ **HECHO** (2026-06-25)
Implementado en `apps/common.py`: `ROL_CAPACIDADES` (fuente de verdad),
`capacidades_de(user, institucion_id)` y `CapacidadPermission`, aplicada por
`BaseModelViewSet`. Cada viewset declara `capacidad_requerida`. Lectura abierta a
miembros; escritura gateada por capacidad en la institución del objeto; el
superusuario pasa siempre. Tests: `apps/casos/test_permisos.py` (10). Verificado
por HTTP (médico no puede crear flujos: 403; sí puede leer: 200).

> **Limitación conocida (a endurecer):** en el *create* de objetos hijos cuya
> institución no viene explícita en el cuerpo (p. ej. crear un Nodo, que cuelga de
> `version`), la verificación cae a «tener la capacidad en *alguna* membresía
> activa». Para usuarios de una sola institución (el caso normal) es correcto; para
> usuarios multi-institución con roles mixtos hay que resolver la institución del
> padre. Pendiente: un `institucion_de_payload()` por viewset.

Una permission class `CapacidadPermission` que **espeja** el mapa de capacidades del
frontend y gatea cada viewset por la capacidad que requiere:

| Viewsets | Capacidad requerida para escribir |
|---|---|
| Flujo, VersionFlujo (incl. `publicar`), Nodo, Conexion, Formulario, Campo | `diseño` |
| Area, Subarea, Grupo, Box, Membresia, Usuario | `config` |
| Caso (acciones de trabajo: tomar/llamar/avanzar/…), ValorCampo, ItemFila | `trabajo` |
| HistoriaClinica, Estudio, Receta, EntradaHistoria | `registros` |

- **Lectura** (`GET`): cualquier miembro de la institución (ya scopeado).
- **Escritura** (`POST/PUT/PATCH/DELETE` y acciones sensibles): requiere la capacidad.
- El **superusuario** pasa siempre. El mapa rol→capacidad vive en un solo lugar del
  backend (fuente de verdad) y el frontend lo refleja.

Cierra el hueco sin cambiar el modelo de roles ni romper el frontend.

### Capa 2 — Claridad del modelo  *(documentación + UI)*
Dejar explícito en la UI el doble eje (este documento + tooltips). El front ya está
casi alineado.

### Capa 3 — Nuevos roles  *(decidido: agregar los dos)*
- **Enfermería** — ✅ **agregado** (2026-06-25). Rol `enfermeria`, capacidades
  `{trabajo, registros}`; opera por grupo pero **no firma atención** (la regla
  `_exigir_medico` solo deja firmar al rol `medico`). En el seed, `guardia.enf` ya
  es enfermería.
- **Jefe / Supervisor de área** — ⏳ **rol agregado, poderes pendientes**. Rol
  `jefe_area`, hoy con `{trabajo, registros}`. Falta su poder distintivo:
  - ver **todos** los casos de su área (no solo los de su grupo),
  - **reasignar**, **repriorizar** y **cancelar** casos del área,
  - una vista de **supervisión** (capacidad `supervision` + sección de menú).
  Conecta con el pendiente «cancelar caso». **← próxima iteración.**

### Capa 4 — Regla de atención configurable por nodo
Generalizar `_exigir_medico`: que el nodo declare qué rol/grupo puede *firmar*
(hoy está fijo a `medico`).

## 5. Recomendación de orden
1. **Capa 1** primero — es el hueco real, no es controversial (formaliza la intención
   que ya tiene el frontend) y es de seguridad.
2. **Capa 3** (nuevos roles) — requiere tu decisión de producto antes de codear.
3. Capa 4 — cuando haya flujos donde firme alguien que no es «médico».
