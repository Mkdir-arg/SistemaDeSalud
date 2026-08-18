# Estado del proyecto — Cauce

> Documento vivo. Resume **qué está hecho**, **cómo levantarlo** y **qué falta**.
> Última actualización: **2026-08-14** (Fase 8: normativa, interoperabilidad FHIR
> y preparación para producción).

Cauce = constructor y motor de flujos para procesos de salud / Estado. Ver
`README.md` para la visión y los `.dc.html` de la raíz (prototipo de alta
fidelidad — fuente del modelo de datos).

Catálogo completo de funcionalidades (todos los módulos) en
[`FUNCIONALIDADES.md`](FUNCIONALIDADES.md). Funcionalidades incrementales de
estructura organizativa y flujos en
[`FUNCIONALIDADES-ESTRUCTURA-Y-FLUJOS.md`](FUNCIONALIDADES-ESTRUCTURA-Y-FLUJOS.md)
(eliminar áreas/sub-áreas, ámbito de flujos, grupos de staff).

**Escenario objetivo (norte):** simular una **guardia completa** (ingreso →
derivación a Trauma/Cardio/Salud mental → atención por especialidad). Spec y
evolutivos pendientes en [`ESCENARIO-GUARDIA.md`](ESCENARIO-GUARDIA.md).

---

## 1. Resumen rápido

| Capa | Estado |
|---|---|
| Backend — modelo de datos (6 apps) | ✅ Completo |
| Backend — admin de Django | ✅ Completo |
| Backend — migraciones aplicadas | ✅ (SQLite local) |
| Backend — auth JWT | ✅ |
| Backend — API REST (CRUD de todas las entidades) | ✅ Verificada end-to-end |
| Backend — motor de ejecución (avance de casos + derivar a otro flujo) | ✅ Completo + tests |
| Backend — permisos por institución (scope de querysets) | ✅ Completo + tests |
| Backend — subida de archivos | ✅ Completo + tests |
| Frontend — base (Vite+React, auth JWT, design system, shell multi-mundo) | ✅ Completo |
| Frontend — mundo Ejecución (bandejas, nuevo caso, detalle, fila) | ✅ Completo + verificado |
| Frontend — mundo Diseño (lienzo, paleta, propiedades, reglas, validar/publicar) | ✅ Completo + verificado |
| Frontend — administración (instituciones, áreas, usuarios) | ✅ Completo + verificado |
| Frontend — registros (historia clínica) | ✅ Completo + verificado |
| Camas e internación (modelo, motor, tablero, pases) | ✅ Completo + 41 tests |
| Turnos y agenda (editor gráfico de horarios, cupos por franja, bloqueos, vista semanal, reprogramar, sobreturnos, ausentismo, presencial/virtual) | ✅ Completo + 135 tests |
| Farmacia e insumos (stock, lotes, trazabilidad, pedidos) | ✅ Completo + 48 tests |
| Red multicentro (traslados, panorama, saturación) | ✅ Completo + 55 tests |
| Auditoría de accesos clínicos (Ley 26.529) | ✅ Backend + pantalla `/accesos` |
| Sellado de integridad de la historia clínica | ✅ Backend + verificación en pantalla |
| Retención y consentimiento (Ley 25.326) | ✅ `purgar_datos` (en seco por defecto) + panel en la HC |
| Firma digital con certificado (Ley 25.506) | ⏳ Enganche listo; falta que el cliente elija certificador |
| Fachada FHIR R4 de sólo lectura (`/fhir/`) | ✅ Patient · Encounter · Organization · metadata |
| Consulta a padrón FHIR desde un paso del flujo | ✅ Completa los campos vacíos del paciente |
| Respaldo verificable (`respaldar`) | ✅ Restaura y compara en cada corrida; servicio diario |
| Endurecimiento para producción | ✅ `check --deploy` limpio, con test que lo corre |
| Monitoreo | ✅ `/api/health/` toca la base · `/api/estado/` delata el proceso periódico que murió |
| Aviso en el Tablero | ✅ Aparece sólo si algo se detuvo, y dice qué se rompe |
| Datos de demo (seed) | ✅ `seed_volumen --rehacer` (escenario + ~530 casos con 90 días de historia) |
| Tests automatizados | ✅ 545 de backend · 143 end-to-end (Playwright, dos temas) |
| Guardas de calidad | ✅ Esquema OpenAPI, clases Tailwind huérfanas, contraste WCAG AA, N+1 por volumen |
| Despliegue real (hosting, dominio, monitoreo) | ⚠️ Falta decidir dónde se hospeda |

---

## 2. Cómo levantar el backend

Todo el stack corre con Docker Compose: base, backend, frontend, el reloj del
motor y el respaldo diario.

```bash
docker compose up -d
# Aplicación:    http://localhost:8080
# API navegable: http://localhost:8000/api/
# Documentación: http://localhost:8000/api/docs/
# Fachada FHIR:  http://localhost:8000/fhir/metadata
```

- Django 6 + DRF + SimpleJWT sobre PostgreSQL 16.
- Dependencias declaradas en `backend/requirements.txt`.
- **Superusuario de desarrollo:** `admin@cauce.local` / `admin1234`.
  El staff del escenario entra con `demo1234`.
- El cliente de Postgres de la imagen está pinchado a la versión del servidor
  (`PG_MAJOR`): un `pg_dump` de otra versión produce respaldos que no se pueden
  restaurar.
- Comandos dentro del contenedor: `docker compose exec backend python manage.py …`

### Obtener un token y llamar la API

```bash
# 1) token
curl -X POST http://127.0.0.1:8000/api/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@cauce.local","password":"admin1234"}'
# 2) usar el "access" devuelto:
curl http://127.0.0.1:8000/api/instituciones/ \
  -H "Authorization: Bearer <access>"
```

---

## 3. Lo que está hecho (detalle)

### Modelo de datos — `backend/apps/`

| App | Modelos |
|---|---|
| `accounts` | `Usuario` (login por email, `AUTH_USER_MODEL`), `Membresia` (rol por institución: admin / configurador / administrativo), `LegajoProfesional` |
| `instituciones` | `Institucion` → `Area` → `Subarea` (instituciones autocontenidas) |
| `formularios` | `Formulario`, `Campo` (tipos: texto_corto/largo, número con unidad y rango, fecha, selección única, archivo; `origen` HC/legajo declarado pero sin precarga implementada) |
| `flujos` | `Flujo`, `VersionFlujo` (v1/v2/v3; estados borrador/publicada/reemplazada/archivada), `Nodo` (10 tipos: inicio, form, decision, accion, atencion, derivar, espera, tiempo, estado, fin), `Conexion` |
| `casos` | `Caso` (instancia de `VersionFlujo`), `ValorCampo`, `ItemFila` (cola FIFO + urgentes), `EventoCaso` (trazabilidad) |
| `registros` | `Ciudadano`, `HistoriaClinica`, `EntradaHistoria`, `Estudio`, `Receta` |

Principio clave: **plantilla** (flujo/versión + grafo) vs **caso** (instancia en
ejecución). El motor usa la misma definición para diseñar y para ejecutar.

### API REST

- Router central: `backend/cauce/api.py`, montado en `/api/` (21 endpoints, un
  ViewSet CRUD por entidad).
- Cada app tiene `serializers.py` + viewsets en `views.py`.
- Filtrado por query params: mixin `BaseModelViewSet` en `backend/apps/common.py`
  (atributo `filter_fields`). Ej.: `/api/areas/?institucion=1`,
  `/api/casos/?estado=recibido&asignado_a=1`.
- Búsqueda y orden (`?search=`, `?ordering=`) en los listados principales.
- Auth: JWT obligatorio (`IsAuthenticated` por defecto). API navegable de DRF
  activa con sesión.

**Endpoints / acciones especiales:**
- `GET  /api/health/` — ¿puede atender? Consulta la base; 503 si no llega. Sin auth
  (una sonda no tramita credenciales) y por eso no cuenta qué falló.
- `GET  /api/estado/` — latido de los procesos periódicos (reloj del motor,
  recordatorios, saturación, respaldo). 503 si alguno se quedó callado. Con sesión.
- `POST /api/auth/token/` y `/api/auth/token/refresh/` — JWT.
- `GET  /api/usuarios/me/` — usuario autenticado.
- `POST /api/casos/{id}/tomar/` — asigna el caso al usuario + registra `EventoCaso`.
- `GET  /api/casos/{id}/eventos/` — línea de tiempo del caso.

Lecturas anidadas: `Flujo`→versiones · `VersionFlujo`→nodos+conexiones ·
`HistoriaClinica`→entradas/estudios/recetas · `Caso` (detalle)→valores+eventos.

---

## 4. Lo que falta (pendiente)

### 4.1. Motor de ejecución — ✅ HECHO

Implementado en `backend/apps/casos/motor.py` (cubierto por 8 tests en
`apps/casos/tests.py`). Expuesto en la API:
- `POST /api/casos/{id}/iniciar/` — posiciona el caso en el Inicio y corre la
  cadena de nodos automáticos hasta la primera parada.
- `POST /api/casos/{id}/avanzar/` — completa el nodo de detención actual con los
  datos enviados y avanza. Cuerpo según el tipo de nodo:
  - form → `{"valores": {"<campo_id>": "<valor>"}}`
  - atencion → `{"titulo", "contenido", "firmada"}`
  - espera (fila) / tiempo → `{}`
- `GET  /api/versiones-flujo/{id}/validar/` — problemas (errores/avisos) y si
  se puede publicar.
- `POST /api/versiones-flujo/{id}/publicar/` — publica si no hay errores y marca
  las versiones anteriores como reemplazadas.

Comportamiento por tipo de nodo: inicio/decisión/acción/derivar/estado se
atraviesan solos; form/atención/espera-fila/espera-tiempo/fin detienen el avance.
Las **decisiones** evalúan `Conexion.condicion` (campo/operador/valor: `=`, `!=`,
`>`, `<`, `contiene`) sobre los `ValorCampo` cargados; conexión sin condición =
rama por defecto. **Atención** crea `EntradaHistoria` en la HC del ciudadano.
**Espera** encola `ItemFila` (urgentes primero). Cada transición queda en
`EventoCaso`. Ver convenciones de `Nodo.config` en el docstring de `motor.py`.

**Sub-pendientes del motor (mejoras, no bloqueantes):**
- [ ] Reactivación real de **Espera por tiempo** (cron / tarea diferida); hoy se
      destraba llamando `avanzar` manualmente.
- [ ] **Derivar a otro flujo** (`flujo_destino_id`): hoy solo cambia el área; no
      instancia un nuevo caso en el flujo destino.
- [ ] Operación de fila más rica (devolver a la cola / marcar ausente). El
      llamado básico ya funciona vía `avanzar`.

### 4.2. Frontend (`frontend/` — Vite + React)

Stack: Vite + React + react-router. Dev: `cd frontend && npm install && npm run dev`
(proxy `/api` → `:8000`, ver `vite.config.js`). Base lista: cliente HTTP con JWT
y refresh automático (`src/api/client.js`), `AuthProvider`, design tokens calcados
del sistema de diseño (`src/theme.js`), componentes base (`src/components/ui.jsx`:
Button, Badge, Card, Input, Select, Textarea, Stepper, Avatar, Spinner), shell con
sidebar/header (`src/components/Shell.jsx`) y login (`src/pages/Login.jsx`).

- [x] **Ejecución** (administrativo): bandejas con tabs míos/sin asignar/todos
      (`pages/ejecucion/Bandejas.jsx`), detalle de caso con stepper + trazabilidad
      + panel del paso actual que renderiza el formulario/atención/espera desde la
      definición y llama a `iniciar`/`avanzar` (`pages/ejecucion/CasoDetalle.jsx`),
      fila de espera del operador (`pages/ejecucion/Fila.jsx`). **Verificado con
      Playwright** contra el backend con datos de `seed_demo`.
- [ ] **Diseño** (configurador): lienzo tipo diagrama (nodos arrastrables, flechas,
      zoom/paneo), panel de propiedades por nodo, constructor de reglas. NO debe
      parecerse al mundo de ejecución (README §3).
- [ ] **Administración**: instituciones, áreas/sub-áreas, usuarios y membresías.
- [ ] **Registros**: historia clínica (evolución, estudios, recetas) y legajo.
- [ ] Selector de rol / contexto de institución (hoy el shell asume Ejecución).

### 4.3. Otros pendientes

- [ ] **Tests** automatizados (los `tests.py` de cada app están vacíos).
- [x] **Permisos auditados por rol**: barrida automática de los 24 recursos
      registrados contra los 6 roles, comparando lo que el servidor hace
      con lo que el rol declara poder hacer. Falla si alguien agrega un
      recurso sin declarar su capacidad.
- [ ] **Seed de datos** de demo (script que cargue las instituciones, flujos y
      casos del prototipo) para no empezar de cero cada vez.
- [ ] **Subida de archivos** real para campos tipo Archivo y estudios (hoy solo
      se guarda el nombre como texto).
- [x] **Documentación de API**: esquema OpenAPI 3 en `/api/esquema/` y visor
      Swagger en `/api/docs/` (drf-spectacular). 83 endpoints, sin avisos ni
      errores de generación. En producción pide sesión: no expone datos pero
      sí el mapa completo de la API.
- [ ] Probar de verdad contra **Supabase/Postgres** y preparar despliegue
      (gunicorn/uvicorn, `collectstatic`, variables de entorno de producción).

---

## 5. Mapa de archivos clave del backend

```
backend/
  manage.py
  requirements.txt
  .env.example            # copiar a .env
  cauce/
    settings.py           # DRF + JWT + CORS + DB (Supabase/SQLite)
    urls.py               # admin, health, token, include(api)
    api.py                # router central de la API (21 ViewSets)
  apps/
    common.py             # BaseModelViewSet + filtrado por query params
    accounts/   models.py serializers.py views.py admin.py
    instituciones/ ...
    formularios/   ...
    flujos/        ...
    casos/         ...
    registros/     ...
```

---

## 6. Cómo levantar todo (backend + frontend)

```bash
# Terminal 1 — backend
cd backend
.venv/Scripts/python.exe manage.py seed_demo      # datos de demo (una vez)
.venv/Scripts/python.exe manage.py runserver       # :8000

# Terminal 2 — frontend
cd frontend
npm install                                         # la primera vez
npm run dev                                          # http://localhost:5173
```

Login de demo (administrativo): **operador@cauce.local / demo1234**.
Super admin: **admin@cauce.local / admin1234**.

## 7. Próximo paso sugerido

El mundo **Ejecución** ya está completo y verificado. Próximos candidatos:
- **Mundo Diseño** (lienzo de flujos): el más vistoso; usa `nodos`, `conexiones`
  y las acciones `validar`/`publicar` que ya existen en la API.
- **Administración** (instituciones/áreas/usuarios): el más simple; CRUD directo.
- **Permisos por rol/institución** (§4.3): hoy todo usuario autenticado ve y edita
  todo; conviene cerrarlo antes de exponer el sistema.
