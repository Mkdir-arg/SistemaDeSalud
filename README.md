# I-Core Salud

**Un sistema donde el hospital dibuja su propio circuito de atención como un
diagrama, y ese mismo diagrama pasa a ser el sistema que usa el personal.**

El configurador arma el proceso —admisión, triage, sala de espera, atención,
derivación, internación— en un editor visual. El motor lee esa definición para dos
cosas: dibujar el lienzo y **renderizar las pantallas que opera el personal**. Nadie
programa una pantalla a mano.

Sobre esa base se apoyan agenda, internación, farmacia, red de derivaciones entre
establecimientos, historia clínica con sello de integridad, costos y gastos, y el
circuito de cobertura con obras sociales.

---

## Levantarlo

```bash
cp .env.example .env     # ajustá lo que necesites
docker compose up -d
```

| | |
|---|---|
| Aplicación | <http://localhost:8080> |
| API navegable | <http://localhost:8000/api/> |
| Documentación de la API | <http://localhost:8000/api/docs/> |
| Fachada FHIR | <http://localhost:8000/fhir/metadata> |

Eso levanta el **stack de desarrollo**, con recarga en caliente y el escenario de
guardia sembrado. Superusuario: `admin@salud.local` / `demo1234`; el staff del
escenario entra con `demo1234`. Qué queda cargado y con qué usuario ver cada cosa:
[`docs/DEMO.md`](docs/DEMO.md).

Para **mostrarlo** o para **configurarlo desde cero** hay dos entornos preparados
aparte, con sus guiones paso a paso: [`docs/entornos/`](docs/entornos/README.md).

Son siete servicios: la base, el backend, el frontend y **cuatro procesos de fondo**
—`tiempos`, `repartos`, `costos` y `respaldos`—. Si uno muere el sistema sigue
respondiendo, pero deja de pasar algo que nadie ve: un paciente en «observación 6
horas» no vuelve nunca. Su latido se consulta en `/api/estado/`.

## Documentación

**Empezá por [`docs/INDICE-FUNCIONAL.md`](docs/INDICE-FUNCIONAL.md)**, que ordena
todo y arranca preguntando qué rol cumplís.

| Si… | Leé |
|---|---|
| Vendés el sistema | [`docs/PARA-VENTAS.md`](docs/PARA-VENTAS.md) |
| Lo diseñás | [`docs/PARA-DISENO.md`](docs/PARA-DISENO.md) |
| Querés saber qué hace | [`docs/funcionalidades/`](docs/funcionalidades/README.md), una ficha por módulo |
| Vas a **usarlo** para atender | [`docs/MANUAL-DE-USO.md`](docs/MANUAL-DE-USO.md) |
| Querés saber quién puede qué | [`docs/ROLES-Y-PERMISOS.md`](docs/ROLES-Y-PERMISOS.md) |
| Vas a desplegarlo | [`docs/DESPLIEGUE.md`](docs/DESPLIEGUE.md) |
| Vas a integrarte por API | [`docs/INTEGRACION-API.md`](docs/INTEGRACION-API.md) |
| Vas a tocar el código | [`docs/MODELO-DE-DATOS.md`](docs/MODELO-DE-DATOS.md), [`docs/FUNDACION-FRONTEND.md`](docs/FUNDACION-FRONTEND.md) y [`docs/PRUEBAS.md`](docs/PRUEBAS.md) |
| Te piden cumplimiento normativo | [`docs/CUMPLIMIENTO-NORMATIVO.md`](docs/CUMPLIMIENTO-NORMATIVO.md) |
| Querés el estado real del proyecto | [`docs/ESTADO-DEL-PROYECTO.md`](docs/ESTADO-DEL-PROYECTO.md) |

El vocabulario de finanzas y cobertura está fijado en [`CONTEXT.md`](CONTEXT.md):
arancel, cargo, cobro, cupo y copago tienen ahí una definición exacta.

## Cómo está armado

```
backend/          Django 6 + DRF + SimpleJWT sobre PostgreSQL 16
  apps/           13 apps · 93 modelos · 66 recursos REST
  config/         settings, router central de la API, urls
frontend/         Vite + React + TanStack Query + Tailwind sobre tokens propios
  src/pages/      37 rutas
  e2e/            Playwright
docs/             La documentación. Empezá por INDICE-FUNCIONAL.md
diseño/           Marca, sistema de diseño, capturas y el prototipo original
```

El principio que ordena todo el dominio: **plantilla** (flujo + versión + grafo)
frente a **caso** (instancia en ejecución). El motor usa la misma definición para
diseñar y para ejecutar.

Y una regla de interfaz que conviene conocer antes de tocar nada: **Diseño** es un
lienzo tipo diagrama y **Ejecución** es un sistema de gestión. No deben parecerse.
Si la pantalla de ejecución parece un diagrama, está mal.

## Pruebas

```bash
docker compose exec backend python manage.py test     # ver docs/PRUEBAS.md antes
cd frontend && npm run e2e
```

**Leé [`docs/PRUEBAS.md`](docs/PRUEBAS.md) antes de la primera corrida.** Hay dos
trampas del entorno que producen cientos de fallas falsas.

## Estado

El núcleo está construido y es demostrable de punta a punta. **Todavía no opera en
ningún hospital real**: falta decidir el hosting, y hay una lista honesta de qué está
hecho, qué falta y qué no está validado en
[`docs/ESTADO-DEL-PROYECTO.md`](docs/ESTADO-DEL-PROYECTO.md).
