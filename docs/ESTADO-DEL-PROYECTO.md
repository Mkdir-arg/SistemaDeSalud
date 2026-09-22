# Estado del proyecto — I-Core Salud

> Qué está construido, qué falta y qué no está validado.
> Reescrito el **2026-09-22** contra `main` en `fca71e3` (último commit: 18/09/2026).

I-Core Salud es un **constructor y motor de flujos** para procesos asistenciales y su
gestión administrativa. El configurador arma un circuito como diagrama; el mismo
diagrama se ejecuta: el personal completa casos reales que avanzan paso a paso, se
derivan entre áreas y quedan registrados. Sobre esa base se apoyan agenda,
internación, farmacia, red de derivaciones, historia clínica, finanzas y cobertura.

- **Qué hace cada módulo**: [`funcionalidades/`](funcionalidades/README.md).
- **Cómo levantarlo y mostrarlo**: [`entornos/`](entornos/README.md).
- **Toda la documentación, con su vigencia**: [`INDICE-FUNCIONAL.md`](INDICE-FUNCIONAL.md).
- **Por qué se construyó así**: [`historico/`](historico/README.md).

---

## 1. El tamaño de lo construido

Medido sobre el código, no sobre expectativas:

| | |
|---|---|
| Apps de backend | 13 |
| Modelos | 93 |
| Recursos REST registrados | 66 |
| Rutas de frontend | 37 |
| Roles institucionales | 9 |
| Capacidades funcionales | 20 |
| Acciones de permiso financiero | 18 |
| Tipos de nodo del flujo | 13 |
| Servicios en Docker Compose | 7 |

## 2. Qué está construido

### Núcleo: flujos, casos y estructura

| Pieza | Estado |
|---|---|
| Estructura organizativa: instituciones, áreas, subáreas, grupos, boxes, camas | ✅ |
| Formularios configurables y su constructor de campos | ✅ |
| Flujos versionados, editor visual, validación, publicación y ensayo | ✅ |
| Motor de ejecución con eventos, decisiones, derivaciones y subprocesos | ✅ |
| Casos, bandeja, filas por prioridad, boxes y pantalla pública de llamados | ✅ |
| Reactivación de esperas por tiempo | ✅ Servicio `tiempos`, cada 2 minutos |
| Derivar a otro flujo instanciando el caso en destino | ✅ |
| Supervisión de área: reasignar, priorizar, cancelar | ✅ |
| Notificaciones in-app con campana y resumen | ✅ |

### Atención

| Pieza | Estado |
|---|---|
| Padrón de pacientes: alta, búsqueda y ficha administrativa | ✅ |
| Historia clínica, entradas firmadas, estudios, recetas y antecedentes | ✅ |
| Sellado encadenado de integridad de la historia | ✅ |
| Agenda: disponibilidades, cupos, bloqueos, grilla, reprogramación, ausentismo | ✅ |
| Internación: camas por sector, estadías, pases y egresos | ✅ |
| Farmacia: stock por depósito y lote, movimientos, pedidos, alertas, trazabilidad | ✅ |
| Red multicentro: redes, destinos, traslados y tablero | ✅ |

### Dinero

| Pieza | Estado |
|---|---|
| Costos por atención: prestaciones, componentes y valores vigentes | ✅ |
| Gastos: carga, ajustes, reemplazos y aprobación | ✅ |
| Gastos mensuales esperados, con referencia y estado de carga | ✅ |
| Reparto de gastos aprobados entre atenciones, por área o institucional | ✅ |
| Pagos y cobros: cuentas, movimientos parciales, devoluciones y reducciones | ✅ |
| Reportería ejecutiva comparable, con descarga en PDF | ✅ |
| Permisos financieros explícitos por acción, área y sensibilidad | ✅ |
| Contabilidad general, facturación fiscal y conciliación bancaria | ❌ Fuera de alcance |

### Financiadores y cobertura

| Pieza | Estado |
|---|---|
| Organización del financiador, sus usuarios y su portal | ✅ |
| Planes, reglas de cobertura versionadas, catálogo común y vínculos | ✅ |
| Padrón de afiliados, importación incremental, identidad y vigencias | ✅ |
| Convenios y aranceles acordados | ✅ |
| Evaluación de cobertura, cupo compartido y reserva serializada | ✅ |
| Consumos externos informados por el financiador | ✅ |
| Copago, aceptación del paciente y saldos de resolución administrativa | ✅ |
| Autorizaciones previas: solicitar, observar, resolver, vencer, anular | ✅ |
| Seguimiento hospitalario de cobros y exportación auditada | ✅ |
| Operación con datos productivos | ⚠️ No validada. Lo probado es el piloto integral |

### Normativa, interoperabilidad y operación

| Pieza | Estado |
|---|---|
| Auditoría de accesos clínicos (Ley 26.529) y pantalla `/accesos` | ✅ |
| Retención y consentimiento (Ley 25.326): `purgar_datos` y panel en la HC | ✅ |
| Firma digital con certificado (Ley 25.506) | ❌ No implementada. Está identificado el punto de inserción; elegir certificador y dispositivo es decisión del cliente |
| Fachada FHIR R4 de sólo lectura: `Patient`, `Encounter`, `Organization`, `Coverage` | ✅ |
| Consulta a padrón FHIR externo desde un paso del flujo | ✅ |
| Respaldo verificable que restaura y compara en cada corrida | ✅ |
| `/api/health/` (toca la base) y `/api/estado/` (latido de los procesos) | ✅ |
| Esquema OpenAPI en `/api/esquema/` y visor en `/api/docs/` | ✅ |
| Endurecimiento para producción: `check --deploy` limpio, con test que lo corre | ✅ |
| Despliegue real: hosting, dominio y monitoreo | ⚠️ Falta decidir dónde se hospeda |

## 3. Cómo levantarlo

Todo corre con Docker Compose: base, backend, frontend y cuatro procesos de fondo
(`tiempos`, `repartos`, `costos`, `respaldos`).

```bash
docker compose up -d
# Aplicación:    http://localhost:8080
# API navegable: http://localhost:8000/api/
# Documentación: http://localhost:8000/api/docs/
# Fachada FHIR:  http://localhost:8000/fhir/metadata
```

Eso levanta el **stack de desarrollo**, con recarga en caliente y el escenario de
guardia sembrado. Los usuarios y lo que queda cargado están en [`DEMO.md`](DEMO.md).

Para mostrar el sistema o para configurarlo desde cero hay **dos entornos aparte**,
en 8081 y 8082, con su propia siembra y sus guiones paso a paso:
[`entornos/README.md`](entornos/README.md).

- Django 6 + DRF + SimpleJWT sobre PostgreSQL 16. Dependencias en `backend/requirements.txt`.
- El cliente de Postgres de la imagen está fijado a la versión del servidor: un
  `pg_dump` de otra versión produce respaldos que no se pueden restaurar.
- Comandos dentro del contenedor: `docker compose exec backend python manage.py …`

### Obtener un token

```bash
curl -X POST http://127.0.0.1:8000/api/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@salud.local","password":"admin1234"}'

curl http://127.0.0.1:8000/api/instituciones/ -H "Authorization: Bearer <access>"
```

## 4. Mapa del backend

| App | Responsabilidad |
|---|---|
| `accounts` | Usuario (login por email), membresía institucional con rol, legajo profesional |
| `instituciones` | Institución → área → subárea, grupos de trabajo, boxes, camas, estadías |
| `formularios` | Formulario y campos configurables |
| `flujos` | Flujo, versión, nodo (13 tipos) y conexión |
| `casos` | Caso, valores de campo, ítem de fila, evento y notificación; el motor de ejecución |
| `registros` | Ciudadano, historia clínica, entradas, estudios, recetas, consentimiento, sellado |
| `agenda` | Agenda, disponibilidad, bloqueo, turno |
| `farmacia` | Insumo, depósito, lote, existencia, movimiento, pedido |
| `red` | Red de establecimientos y traslados |
| `auditoria` | Accesos clínicos, latidos de los procesos, respaldo y purga |
| `finanzas` | Costos, gastos, reparto, dinero, reportes y permisos financieros |
| `financiadores` | Organización, padrón, cobertura, cupo, copago, autorizaciones |
| `fhir` | Fachada FHIR R4 de sólo lectura |

Principio que ordena todo: **plantilla** (flujo + versión + grafo) frente a **caso**
(instancia en ejecución). El motor usa la misma definición para diseñar y para
ejecutar; nadie programa una pantalla a mano.

## 5. Qué falta

### Decisiones pendientes

- **Dónde se hospeda.** Es el bloqueo real para pasar a producción.
- **Certificador para la firma digital** con certificado (Ley 25.506). Lo que hoy se
  muestra es la firma funcional por rol, no la criptográfica.
- **Perfiles FHIR** exigidos por la jurisdicción y autenticación de clientes externos.

### Alcance no construido

- Contabilidad general, facturación fiscal y conciliación bancaria.
- Otras bases de reparto distintas de la actividad.
- Pantallas de indicadores agregados no nominales: el rol `reportes` existe y casi no
  tiene dónde usarse.
- Tableros por nivel: establecimiento, región sanitaria, provincia.

### Deuda conocida

- Dos specs de Playwright quedaron de una prueba manual y apuntan a una UI que ya
  cambió: `e2e/_tmp_caso7.spec.js` y `e2e/_tmp_turnos.spec.js`, junto con los
  `_tmp_A*.png` del mismo directorio. Conviene borrarlos.
- `e2e/finanzas-feedback.spec.js` conserva expectativas de una versión anterior de la
  interfaz de Finanzas.
- El admin de Django no funciona por http en los entornos con `DEBUG=false`: las
  cookies van marcadas `Secure`. La aplicación no lo necesita, usa JWT.
- `/fhir/` no pasa por el puerto de la aplicación; el nginx del frontend no lo proxea.

## 6. Qué está validado y qué no

Hay **1767 pruebas de backend** y **35 suites end-to-end** de Playwright.

### Lo medido el 22/09/2026

`apps.finanzas` + `apps.financiadores`: **726 pruebas, 49 fallos y 3 errores.**

Casi todos tienen una sola causa. El commit `c4eefbb` del 18/09 amplió la herencia
financiera del administrador de institución de dos acciones a las dieciocho, y
dejó atrás las pruebas que usaban una membresía con rol `admin` como portador
neutro para verificar que un permiso viene de la concesión y no del rol. Al
heredar todo, cada afirmación negativa de ese tipo pasa sola y el test falla.

Está comprobado: con esa línea revertida, las mismas 724 pruebas bajan a **4
fallos y 2 errores**. El resto de la suite no está tocado.

**La regla de producción es la correcta** —es una decisión aprobada el 18/09—; lo
que quedó viejo son los fixtures de prueba, en unos 16 módulos. No están
reparados. Es una tarea acotada pero propia, no un efecto secundario de otra.

Las demás apps no se ejecutaron en esta medición:

```bash
docker compose exec backend python manage.py test
cd frontend && npm run e2e
```

Lo que sí está verificado contra la aplicación corriendo, y con fecha:

| Qué | Cuándo |
|---|---|
| Los dos entornos locales, levantados y recorridos botón por botón | 17–18/09/2026 |
| Circuito de financiadores en el entorno demo | 18/09/2026 |
| Guion de demo comercial completo | 17/09/2026 |
| Escenario de finanzas Los Aromos y sus cifras | 15/09/2026 |
| Stack de desarrollo y escenario de guardia | 20/08/2026 |

Lo que **no** está validado: la operación real con datos productivos, el
comportamiento con volumen de producción, y el despliegue fuera de una máquina local.
Una activación local no equivale a aprobación de producción ni a aceptación funcional.
