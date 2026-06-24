# Funcionalidades de Cauce — Catálogo completo

> Inventario de **todas las funcionalidades desarrolladas**, módulo por módulo.
> Para cada una: **qué hace**, **dónde vive** en el código y **qué reglas** la gobiernan.
> Última actualización: **2026-06-24**.

Complementa:
- [`ESTADO-DEL-PROYECTO.md`](ESTADO-DEL-PROYECTO.md) — estado, cómo levantar, qué falta.
- [`FUNCIONALIDADES-ESTRUCTURA-Y-FLUJOS.md`](FUNCIONALIDADES-ESTRUCTURA-Y-FLUJOS.md) — detalle de estructura organizativa y ámbito de flujos.
- [`roles/`](roles/) — capacidades por rol.

**Cauce** es un constructor y motor de flujos para procesos de salud / Estado:
se **diseña** un proceso como diagrama y **la misma definición se ejecuta** sobre
casos reales, con trazabilidad e historia clínica.

---

## Mapa de funcionalidades

| # | Área | Qué resuelve |
|---|---|---|
| 1 | [Autenticación, roles y capacidades](#1-autenticación-roles-y-capacidades) | Login JWT, multi-institución, permisos por rol |
| 2 | [Plataforma y Directorio](#2-plataforma-y-directorio-super-admin) | Alta y gestión de instituciones (super admin) |
| 3 | [Estructura organizativa](#3-estructura-organizativa) | Áreas, sub-áreas y grupos de staff |
| 4 | [Usuarios y membresías](#4-usuarios-y-membresías) | Alta de usuarios y asignación de rol/área |
| 5 | [Formularios dinámicos](#5-formularios-dinámicos) | Constructor de formularios reutilizables |
| 6 | [Diseño de flujos](#6-diseño-de-flujos-el-constructor) | Lienzo drag&drop, nodos, reglas, validación, publicación |
| 7 | [Motor de ejecución](#7-motor-de-ejecución) | Avance automático de casos por el grafo |
| 8 | [Ejecución / Casos](#8-ejecución--casos) | Bandeja, filas de espera, detalle y trazabilidad |
| 9 | [Registros clínicos](#9-registros-clínicos) | Ciudadanos, historia clínica, legajo profesional |
| 10 | [API REST](#10-api-rest-referencia) | Referencia de endpoints |
| 11 | [Infraestructura](#11-infraestructura-y-despliegue) | Docker, configuración, despliegue |

**Stack:** Django 5 + DRF + SimpleJWT + PostgreSQL (backend) · React 18 + Vite +
React Router (frontend) · Docker Compose (orquestación).

---

## 1. Autenticación, roles y capacidades

### 1.1 Login y sesión JWT
- **Qué hace:** login por **email + contraseña**; devuelve `access` (60 min) y
  `refresh` (7 días, con rotación). El cliente refresca el `access` de forma
  transparente ante un `401` y reintenta la llamada.
- **Dónde:**
  - Backend: `POST /api/auth/token/` y `/api/auth/token/refresh/` (SimpleJWT, configurado en [`backend/cauce/settings.py`](../backend/cauce/settings.py)).
  - Frontend: [`api/client.js`](../frontend/src/api/client.js) (manejo de tokens en `localStorage`, refresh automático) y [`pages/Login.jsx`](../frontend/src/pages/Login.jsx).
  - Sesión: [`auth/AuthContext.jsx`](../frontend/src/auth/AuthContext.jsx) carga el usuario desde `GET /usuarios/me/`.

### 1.2 Modelo de pertenencia (multi-institución)
- **Qué hace:** un usuario puede pertenecer a varias instituciones; el **rol no
  es global** sino por institución (`Membresia`), y opcionalmente acotado a
  ciertas **áreas**. La **función es por área**: una persona puede ser
  administrativa en un área y médica en otra (dos membresías distintas).
- **Selector de institución:** un usuario no-super con **más de una membresía**
  cambia de institución desde el encabezado del menú lateral (dropdown "Cambiar de
  institución"); el super admin usa "Volver al directorio". Implementado en
  [`components/Shell.jsx`](../frontend/src/components/Shell.jsx).
- **Dónde:** [`apps/accounts/models.py`](../backend/apps/accounts/models.py) — `Usuario`, `Membresia` (con `unique_together` usuario+institución+rol), `LegajoProfesional`.

### 1.3 Roles y capacidades
- **Roles:** `admin` (de institución), `configurador`, `administrativo`, `medico`.
  Más el **super admin de plataforma** (`is_superuser`).
- **Capacidades** que gobiernan el menú y las rutas en el frontend
  ([`auth/InstitutionContext.jsx`](../frontend/src/auth/InstitutionContext.jsx), `puedeVer(cap)`):

  | Rol | Capacidades |
  |---|---|
  | admin | config + diseño + trabajo + registros |
  | configurador | diseño |
  | administrativo | trabajo + registros |
  | medico | trabajo + registros |
  | super admin | todas (puede simular vista) |

### 1.4 Scope de datos por institución
- **Qué hace:** cada usuario sólo ve datos de sus instituciones activas; el super
  admin ve todo. Se aplica de forma transversal a **todos** los endpoints.
- **Dónde:** `InstitucionScopedMixin` en [`apps/common.py`](../backend/apps/common.py) (cada ViewSet declara su `institucion_path`).

---

## 2. Plataforma y Directorio (super admin)

Pantalla previa a entrar a una institución: [`pages/Directorio.jsx`](../frontend/src/pages/Directorio.jsx).

- **Listado de instituciones** con búsqueda; columnas nombre, tipo, áreas, staff, estado. Botón **Ingresar** entra a la institución.
- **Alta de institución** (`NuevaInstitucionModal`): crea la institución y, en el mismo paso, su **administrador** (`POST /instituciones/` + `POST /membresias/`).
- **Gestión de usuarios** de plataforma (alta/edición).
- **Métricas de institución:** `GET /instituciones/{id}/metricas/` → áreas, sub-áreas, staff, casos activos ([`apps/instituciones/views.py`](../backend/apps/instituciones/views.py)).

---

## 3. Estructura organizativa

Pantalla: [`pages/admin/Areas.jsx`](../frontend/src/pages/admin/Areas.jsx) (ruta `/estructura`).
Jerarquía: **Institución → Área → Sub-área**, más **Grupos** de staff.

- **Áreas:** alta, edición, baja (con confirmación), responsable y estado activo. `unique_together (institucion, nombre)`.
- **Sub-áreas:** subdivisión de un área (`unique_together (area, nombre)`). Eliminar un área **borra en cascada** sus sub-áreas (lo advierte el modal).
- **Grupos de staff:** equipos de trabajo dentro de un área; los integrantes deben tener membresía en esa área (validado en el serializer).
- **Ficha de área** (drawer lateral) con pestañas **Datos / Staff / Grupos / Sub-áreas**.
- **Dónde (backend):** modelos en [`apps/instituciones/models.py`](../backend/apps/instituciones/models.py); endpoints `/api/areas/`, `/api/subareas/`, `/api/grupos/`.

> Detalle ampliado en [`FUNCIONALIDADES-ESTRUCTURA-Y-FLUJOS.md`](FUNCIONALIDADES-ESTRUCTURA-Y-FLUJOS.md).

---

## 4. Usuarios y membresías

Pantalla: [`pages/admin/Usuarios.jsx`](../frontend/src/pages/admin/Usuarios.jsx) (ruta `/administracion`).

- **Listado** de usuarios de la institución (vía membresías), con rol(es) y área(s).
- **Alta / edición** de usuario: email, nombre, apellido, contraseña, activo.
- **Membresías:** asignar/quitar al usuario en instituciones con un **rol**; el rol puede acotarse a **áreas** (scope).
- **Legajo profesional:** especialidad y matrícula (modelo `LegajoProfesional`), visible en el dashboard de [`pages/registros/Legajo.jsx`](../frontend/src/pages/registros/Legajo.jsx).
- **Dónde (backend):** [`apps/accounts/views.py`](../backend/apps/accounts/views.py) — `/api/usuarios/`, `/api/membresias/`, `/api/legajos/`; acciones `usuarios/me/` y `usuarios/{id}/legajo/` (dashboard: casos atendidos, pacientes vistos, llamados de fila, actividad reciente).

---

## 5. Formularios dinámicos

Pantallas: [`pages/diseno/Formularios.jsx`](../frontend/src/pages/diseno/Formularios.jsx) (lista) y [`pages/diseno/FormularioDetalle.jsx`](../frontend/src/pages/diseno/FormularioDetalle.jsx) (constructor).

- **Qué hace:** define formularios **reutilizables** que un nodo de flujo de tipo
  *Formulario* puede usar para pedir datos.
- **Tipos de campo:** `texto_corto`, `texto_largo`, `fecha`, `seleccion_unica` (con opciones), `archivo`.
- **Campos requeridos**, texto de ayuda y **orden**.
- **Campos vinculados:** un campo puede precargarse desde un origen (`historia_clinica` o `legajo_ciudadano`).
- **Previsualización en vivo** del formulario mientras se editan los campos.
- **Dónde (backend):** [`apps/formularios/models.py`](../backend/apps/formularios/models.py) — `Formulario`, `Campo`; endpoints `/api/formularios/`, `/api/campos/`.

---

## 6. Diseño de flujos (el constructor)

El componente central: [`pages/diseno/FlujoEditor.jsx`](../frontend/src/pages/diseno/FlujoEditor.jsx).
Lista y alta de flujos en [`pages/diseno/Flujos.jsx`](../frontend/src/pages/diseno/Flujos.jsx).

### 6.1 Lista de flujos
- Filtros por **estado** (Todos / Publicado / Borrador / Archivado) y por **área**.
- Muestra versión vigente, casos activos y última edición.
- **Nuevo flujo** (crea flujo + versión v1 + nodo Inicio) y **Duplicar**.
- **Ámbito** del flujo: institución, área o sub-área (`Flujo.subarea` sincroniza `area`).

### 6.2 El lienzo (drag & drop)
- **Paleta** con los 10 tipos de nodo; clic agrega el nodo al lienzo.
- **Arrastrar** nodos (posición `x,y` persistida con `PATCH /nodos/{id}/`).
- **Conexiones** dirigidas (curvas Bézier con flecha): botón **+ conectar** → clic en el nodo destino.
- **Panel de propiedades** contextual según el tipo de nodo seleccionado.

### 6.3 Tipos de nodo

| Nodo | Comportamiento | Configuración en el panel |
|---|---|---|
| **Inicio** | Punto de entrada del caso | — |
| **Formulario** | Pide datos (detiene el caso) | Elegir formulario |
| **Decisión** | Bifurca según una condición | *En las conexiones de salida* (etiqueta + regla) |
| **Acción** | Hito automático: registra un evento en la línea de tiempo | Solo el título |
| **Atención** | Registra una atención médica (detiene) | Título |
| **Derivar** | Cambia el área del caso y/o **dispara un subproceso** | Área de destino (y/o flujo destino) |
| **Espera de fila** | Encola el caso (FIFO + urgencia) | Título de la fila |
| **Espera por tiempo** | Pausa el caso hasta reactivación | Duración (informativa) |
| **Estado** | Cambia el estado del caso | Estado a aplicar |
| **Fin** | Cierra el caso | — |

### 6.4 Reglas de decisión (RuleBuilder)
- **Qué hace:** cada conexión de salida de un nodo *Decisión* define una **rama**
  con etiqueta y una condición `SI campo [operador] valor`.
- **Operadores:** `=`, `!=`, `>`, `<`, `contiene`. Los campos provienen de los
  formularios de la institución. Una conexión **sin condición** es la **rama por
  defecto** (else).
- **Dónde:** `RuleBuilder` en [`FlujoEditor.jsx`](../frontend/src/pages/diseno/FlujoEditor.jsx); evaluación cliente en [`lib/simular.js`](../frontend/src/lib/simular.js).

### 6.5 Probar, Reproducir, Validar, Publicar
- **Probar:** simulación interactiva sin tocar la base — recorre el flujo cargando
  datos en los formularios y resolviendo las decisiones ([`lib/simular.js`](../frontend/src/lib/simular.js) espeja el motor del backend).
- **Reproducir:** anima el recorrido por defecto sobre el lienzo.
- **Validar:** `GET /versiones-flujo/{id}/validar/` lista errores/avisos del grafo (ver [§7.5](#75-validación-de-una-versión)).
- **Publicar:** `POST /versiones-flujo/{id}/publicar/` — sólo si no hay errores; marca la versión como **publicada** y **reemplaza** la anterior.

### 6.6 Versionado
- Cada flujo tiene **versiones** (`v1`, `v2`, …) con estados `borrador`,
  `publicada`, `reemplazada`, `archivada` (`unique_together (flujo, numero)`).
- Sólo se ejecuta la **versión publicada**.

### 6.7 Mapa de flujos
- **Qué hace:** vista panorámica de cómo los flujos se **encadenan** entre sí. Cada
  flujo es un bloque (con su estado vigente y área); cada nodo *Derivar* con
  `flujo_destino_id` se dibuja como una **flecha** origen → destino, con la etiqueta
  del nodo. Clic en un bloque abre el diseñador.
- **Endpoint:** `GET /flujos/mapa/` devuelve `{ nodos, aristas }` —
  `nodos` (id, título, área, estado, versiones) y `aristas`
  (`origen`, `destino`, `etiqueta`, `externo`). `externo=true` marca una derivación
  hacia un flujo fuera del conjunto visible (se dibuja punteada).
- **Render:** layout automático **por niveles** (columnas según la profundidad de
  derivación) y flechas en **SVG** (curvas Bézier con punta), con las etiquetas en
  HTML por encima de los bloques.
- **Dónde:** [`pages/diseno/MapaFlujos.jsx`](../frontend/src/pages/diseno/MapaFlujos.jsx) y la acción `mapa` en [`apps/flujos/views.py`](../backend/apps/flujos/views.py).

---

## 7. Motor de ejecución

El corazón del sistema: [`apps/casos/motor.py`](../backend/apps/casos/motor.py). Un
**Caso** es una instancia de una `VersionFlujo` que avanza por el grafo.

### 7.1 Nodos automáticos vs. de detención
- **Automáticos** (el motor los atraviesa solo): `inicio`, `decision`, `accion`, `derivar`, `estado`.
- **De detención** (esperan un disparador externo): `form`, `atencion`, `espera`, `tiempo`, `fin`.

### 7.2 Efectos al entrar a un nodo
| Nodo | Efecto |
|---|---|
| **Estado** | Cambia `caso.estado` según `config.estado` |
| **Derivar** | Cambia `area_actual` al área destino, marca `derivado`; si hay `flujo_destino_id`, **instancia e inicia un caso nuevo** en ese flujo (subproceso) |
| **Acción** | Registra un `EventoCaso` (hito) y continúa |
| **Espera de fila** | Crea un `ItemFila` (FIFO, urgentes primero), estado `en_espera` |
| **Espera por tiempo** | Estado `en_espera`; la reactivación es externa |
| **Fin** | Estado `cerrado` |

### 7.3 Decisión (resolución de rama)
- Evalúa las conexiones **con** condición en orden y toma la **primera que se
  cumple**; si ninguna aplica, usa la rama **por defecto**. Lógica en `_cumple()` y
  `_siguiente_nodo()` de [`motor.py`](../backend/apps/casos/motor.py).

### 7.4 Iniciar y avanzar (transaccional)
- **`iniciar(caso)`** posiciona en el nodo Inicio y corre la cadena automática
  hasta la primera parada.
- **`avanzar(caso, datos)`** completa el nodo de detención actual y vuelve a correr:
  - *form* → guarda valores; *atencion* → registra atención en historia clínica;
    *espera* → llamado desde la fila; *tiempo* → reactivación.
- Ambas en `@transaction.atomic`. Detecta **ciclos** automáticos y callejones sin salida.

### 7.5 Validación de una versión
Antes de publicar (`validar_version`):
- **Error:** debe haber exactamente un nodo *Inicio*; *Derivar* sin área de destino; *Decisión* con regla sobre un campo que no se carga en ningún formulario del flujo.
- **Aviso:** sin nodo *Fin*; nodo (no Fin) sin salida; *Formulario* sin formulario asignado.

### 7.6 Seguridad de la atención médica
- Sólo un usuario con rol **médico** (o super admin) puede registrar una atención;
  si el caso está en un área, el médico debe tener esa área asignada
  (`_exigir_medico` en [`motor.py`](../backend/apps/casos/motor.py)).

---

## 8. Ejecución / Casos

Mundo **Trabajo**. Pantallas en [`pages/ejecucion/`](../frontend/src/pages/ejecucion/).

- **Bandeja de tareas** ([`Bandejas.jsx`](../frontend/src/pages/ejecucion/Bandejas.jsx)): pestañas *Mis casos* / *Sin asignar*; **Tomar** un caso (`POST /casos/{id}/tomar/`); alta de **nuevo caso** sobre un flujo publicado.
- **Casos** ([`Casos.jsx`](../frontend/src/pages/ejecucion/Casos.jsx)): listado/auditoría de todos los casos con su paso actual, estado, área y asignación.
- **Detalle del caso** ([`CasoDetalle.jsx`](../frontend/src/pages/ejecucion/CasoDetalle.jsx)): stepper de estados, panel del **paso actual** (completar formulario, registrar atención, etc.), datos cargados, antecedentes clínicos y **trazabilidad** (línea de tiempo de `EventoCaso`). Acciones `iniciar`/`avanzar`/`eventos`.
- **Filas de espera** ([`Fila.jsx`](../frontend/src/pages/ejecucion/Fila.jsx)): cola FIFO con urgentes al frente; botón **Llamar al siguiente** avanza el primer caso.
- **Estados del caso:** `recibido → en_evaluacion / en_espera / derivado / atendido → cerrado`. **Prioridad:** normal / alta / urgente.
- **Dónde (backend):** [`apps/casos/`](../backend/apps/casos/) — modelos `Caso`, `ValorCampo`, `ItemFila`, `EventoCaso`; endpoints `/api/casos/` (+ acciones `eventos`, `tomar`, `iniciar`, `avanzar`), `/api/items-fila/`, `/api/valores-campo/`, `/api/eventos-caso/`.

---

## 9. Registros clínicos

Mundo **Registros**. Pantallas en [`pages/registros/`](../frontend/src/pages/registros/).

- **Ciudadanos / pacientes** ([`Registros.jsx`](../frontend/src/pages/registros/Registros.jsx)): listado con búsqueda y alta (nombre, documento, fecha de nacimiento, obra social).
- **Historia clínica** ([`HistoriaDetalle.jsx`](../frontend/src/pages/registros/HistoriaDetalle.jsx)): ficha del paciente con pestañas **Evolución / Estudios / Recetas**, antecedentes (alergias, condiciones) y alta de **atención** (se crea automáticamente desde el nodo *Atención* del motor; puede **firmarse**).
- **Legajo profesional** ([`Legajo.jsx`](../frontend/src/pages/registros/Legajo.jsx)): dashboard del profesional (casos atendidos, pacientes vistos, llamados de fila, última actividad) + especialidad y matrícula.
- **Dónde (backend):** [`apps/registros/models.py`](../backend/apps/registros/models.py) — `Ciudadano`, `HistoriaClinica`, `EntradaHistoria`, `Estudio`, `Receta`; endpoints `/api/ciudadanos/`, `/api/historias-clinicas/`, `/api/entradas-historia/`, `/api/estudios/`, `/api/recetas/`.
- **Adjuntos:** subida de archivos vía `POST /api/archivos/` (multipart; usado por campos *archivo* y estudios).

---

## 10. API REST (referencia)

Base `/api/`. Router en [`backend/cauce/api.py`](../backend/cauce/api.py). Todos los
recursos son CRUD (`GET/POST/PUT/PATCH/DELETE`) salvo aclaración, con filtrado por
query params y scope por institución.

| Recurso | Ruta base | Acciones especiales |
|---|---|---|
| Auth | `/api/auth/token/`, `/api/auth/token/refresh/` | login / refresh (POST) |
| Usuarios | `/api/usuarios/` | `me/` (GET), `{id}/legajo/` (GET) |
| Membresías | `/api/membresias/` | — |
| Legajos | `/api/legajos/` | — |
| Instituciones | `/api/instituciones/` | `{id}/metricas/` (GET) |
| Áreas | `/api/areas/` | — |
| Sub-áreas | `/api/subareas/` | — |
| Grupos | `/api/grupos/` | — |
| Formularios | `/api/formularios/` | — |
| Campos | `/api/campos/` | — |
| Flujos | `/api/flujos/` | `mapa/` (GET) |
| Versiones de flujo | `/api/versiones-flujo/` | `{id}/validar/` (GET), `{id}/publicar/` (POST) |
| Nodos | `/api/nodos/` | — |
| Conexiones | `/api/conexiones/` | — |
| Casos | `/api/casos/` | `{id}/eventos/` (GET), `{id}/tomar/` `{id}/iniciar/` `{id}/avanzar/` (POST) |
| Valores de campo | `/api/valores-campo/` | — |
| Ítems de fila | `/api/items-fila/` | — |
| Eventos de caso | `/api/eventos-caso/` | — |
| Ciudadanos | `/api/ciudadanos/` | — |
| Historias clínicas | `/api/historias-clinicas/` | — |
| Entradas de historia | `/api/entradas-historia/` | — |
| Estudios | `/api/estudios/` | — |
| Recetas | `/api/recetas/` | — |
| Archivos | `/api/archivos/` | subir (POST multipart) |

---

## 11. Infraestructura y despliegue

- **Orquestación:** Docker Compose con tres servicios — `db` (PostgreSQL 16),
  `backend` (Django) y `frontend`. Volúmenes `pgdata` y `media`.
- **Desarrollo** (`docker compose up`, carga `docker-compose.override.yml`):
  - Backend con `runserver` (autoreload) expuesto en `:8000`.
  - Frontend con **Vite dev server (HMR) dentro de Docker**, publicado en **`:8080`** (proxy interno de `/api` → `backend:8000`).
- **Producción** (`docker compose -f docker-compose.yml up`):
  - Backend con **gunicorn**; frontend compilado y servido por **nginx** ([`frontend/nginx.conf`](../frontend/nginx.conf): SPA + proxy `/api`, `/media`, `/admin`, `/static`).
- **Base de datos:** PostgreSQL vía `DATABASE_URL` (Supabase recomendado); fallback a SQLite local si no se define.
- **Migraciones y seed:** automáticos en el arranque del backend; seed manual con `python manage.py seed_demo` (ver credenciales y datos demo en [`ESTADO-DEL-PROYECTO.md`](ESTADO-DEL-PROYECTO.md)).

> El detalle completo de configuración (settings, JWT, CORS, Dockerfiles) está en
> [`ESTADO-DEL-PROYECTO.md`](ESTADO-DEL-PROYECTO.md) y los archivos `docker-compose*.yml`.

---

### Convención de nodos (referencia rápida del `config`)
```
estado    : {"estado": "<valor de Caso.Estado>"}      ej. "en_espera"
derivar   : {"area_destino_id": <id>, "flujo_destino_id": <id>}
tiempo    : {"duracion": "1 mes"}                       (informativo)
atencion  : {"plantilla": "evaluación inicial"}
```
### Convención de condición de rama (Decisión)
```
{"campo": <id de Campo>, "operador": "=|!=|>|<|contiene", "valor": "<valor>"}
# Una conexión sin condición es la rama por defecto (else).
```
