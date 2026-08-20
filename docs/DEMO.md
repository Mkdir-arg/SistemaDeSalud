# Guion operativo de la demo

> Cómo dejar la demo impecable, con qué usuario entrar a cada pantalla y qué hay
> cargado para mostrar. Verificado el **2026-08-20** sobre el stack de Docker.

Las credenciales que figuran en [`ESTADO-DEL-PROYECTO.md`](ESTADO-DEL-PROYECTO.md)
§6 y en [`roles/README.md`](roles/README.md) (`operador@cauce.local`,
`a.gomez@`, `m.diaz@`, `j.perez@`) son de `seed_demo` y **no existen** en este
entorno: el override de desarrollo siembra `seed_guardia` + `seed_volumen`. Las
que sirven son las de abajo.

---

## 1. Levantar y resetear

```bash
docker compose up -d
# Aplicación:    http://localhost:8080
# API navegable: http://localhost:8000/api/
# Documentación: http://localhost:8000/api/docs/
# Fachada FHIR:  http://localhost:8000/fhir/metadata
```

**Reset completo, dos comandos (~60 s). Correrlos juntos y en este orden:**

```bash
docker compose exec backend python manage.py seed_volumen --rehacer
docker compose exec backend python manage.py seed_faltantes
```

`seed_volumen --rehacer` refecha todo contra *ahora*: sin él, los pacientes de la
cola aparecen esperando días y el tablero de demoras muestra números absurdos.
**Conviene correrlo el mismo día de la demo.**

`seed_faltantes` completa lo que `seed_volumen` no cubre y sin lo cual cinco
funcionalidades existen pero no se pueden mostrar: los pedidos de farmacia, el
consumo imputado a pacientes (trazabilidad de lote), un bloqueo de agenda con
turnos afectados, el token de la pantalla pública de llamados, y los usuarios de
los roles de gobierno.

**Anotá la URL de la pantalla de TV**: el comando la imprime al final, en la
sección «Pantalla pública de llamados». Es un token nuevo en cada corrida, así
que la URL de la demo anterior deja de servir. La de la sala de espera de guardia
es la que tiene la cola larga.

---

## 2. Con qué usuario entrar

Contraseña **`demo1234`** para todos, salvo el superusuario.

| Para mostrar | Usuario | Rol |
|---|---|---|
| Plataforma completa, editor de flujos, todo | `admin@cauce.local` / `admin1234` | superusuario |
| Gobierno estatal: alta de efectores y redes, directorio | `plataforma@cauce.local` | plataforma |
| Auditoría de accesos con alcance estatal | `auditor@cauce.local` | auditor |
| Administración de la institución, usuarios y estructura | `admin.central@hospital.gob.ar` | admin |
| Diseño de flujos y formularios | `config.central@hospital.gob.ar` | configurador |
| Supervisión de área, reasignar, priorizar, cancelar | `guardia.jefe@hospital.gob.ar` | jefe de área |
| Admisión, filas, turnos | `guardia.adm@hospital.gob.ar` | administrativo |
| Triage de enfermería | `guardia.enf@hospital.gob.ar` | enfermería |
| Atención médica y firma | `guardia.med@hospital.gob.ar` | médico |
| Especialidades | `cardio.med@` · `trauma.med@` · `sm.med@` · `neuro.med@` | médico |
| Estudios (ida y vuelta) | `lab.med@` · `img.med@` | médico |
| Internación y camas | `int.adm@` · `int.med@` | administrativo / médico |
| El efector chico de la red | `villa.med@` · `villa.jefe@` · `villa.adm@` | Villa Real |

Todos los `@hospital.gob.ar` son de **Hospital Central** salvo los `villa.*`.

---

## 3. Qué hay cargado para mostrar

Medido después del reset:

| Módulo | Datos disponibles |
|---|---|
| Guardia y casos | ~518 casos en Hospital Central · ~100 activos · 8 flujos publicados · 90 días de historia |
| Filas | ~27 pacientes esperando, urgentes al frente, mediana de espera de minutos |
| Internación | 28 camas (libres, ocupadas, en higiene, bloqueadas) + estadías históricas |
| Agenda | 4 agendas · ~1.100 turnos con los 5 estados · turnos de hoy y a futuro · **1 bloqueo con 6 turnos afectados** |
| Farmacia | Stock, lotes y los **6 estados de pedido**: pendiente, pendiente urgente, preparado, **parcial**, entregado, rechazado |
| Trazabilidad de lote | 2 lotes que llegan a 4 pacientes con nombre cada uno (el caso «se retira el lote, a quién se le aplicó») |
| Red | 1 red · Villa Real deriva a Hospital Central · 14 traslados (7 recibidos, 3 rechazados, 4 esperando respuesta) |
| Historia clínica | ~425 entradas, todas selladas · 38 consentimientos |
| Auditoría | Miles de accesos clínicos registrados; la consulta por paciente devuelve su historial de accesos |
| Recorrido guiado | Tres clics en la ficha del super admin: la app se maneja sola y construye «Hospital Escuela Cauce» desde cero |
| FHIR | `Patient`, `Encounter`, `Organization` y `metadata` respondiendo |
| Pantalla de TV | 3 pantallas con token listo; la de la sala de espera de guardia con ~25 en cola |

---

## 4. Lo que conviene no mostrar

- **El Directorio de plataforma tiene dos efectores dados de baja** («X» y «Hospital
  de Prueba»): quedaron de pruebas manuales y aparecen con badge *Inactiva*. **No se
  pueden borrar**: `AccesoClinico.institucion` y `Flujo.institucion` son `PROTECT`
  a propósito —la auditoría clínica no se borra—, así que la única baja posible es
  la de estado. Si molestan en cámara, entrar directo a Hospital Central en vez de
  pasar por el directorio.
- **«Hospital Escuela Cauce» NO se toca**: no es un resto de pruebas, es el
  escenario que construye el **recorrido guiado** (`src/tutorial/`, tres clics en la
  ficha del super admin). Si se lo da de baja, el tutorial integrado deja de
  funcionar. Queda en estado *En alta* a propósito.
- **Rol `reportes`**: la capacidad existe pero no hay pantallas de indicadores
  agregados no nominales. Entrar con ese usuario muestra una app casi vacía.
- **Firma digital con certificado** (Ley 25.506): el enganche está, el certificador
  no. La firma que se muestra es la funcional por rol, no la criptográfica.
- **Espera por tiempo**: se reactiva sola (servicio `tiempos`, cada 2 min), pero si
  se quiere mostrar en vivo hay que esperar ese ciclo.

---

## 5. Chequeo rápido antes de empezar

```bash
curl -s http://localhost:8000/api/health/                 # {"status": "ok"}
docker compose ps                                         # 5 servicios arriba
```

Y con sesión de superusuario, `GET /api/estado/` dice si el reloj del motor, los
recordatorios, la saturación y el respaldo están al día. Si alguno se quedó
callado, el Tablero lo avisa —y eso también se ve en la demo.

---

## 6. Estado de la verificación automática

| Suite | Resultado |
|---|---|
| Backend (`manage.py test`) | 1010 tests, verde |
| Frontend e2e (`npm run e2e`) | 227 de 229, verde salvo dos specs obsoletos |
| Build + auditor de clases | limpio · chunk principal 302 kB · 235 clases sin huérfanas |
| Contraste AA | sin fallos en claro y en oscuro |

Los dos specs que fallan son `e2e/_tmp_caso7.spec.js` y `e2e/_tmp_turnos.spec.js`:
quedaron de una prueba manual, apuntan a un flujo de UI que ya cambió y cada uno
consume 120 s de *timeout*. No prueban nada que las otras specs no cubran;
conviene borrarlos junto con los `_tmp_A*.png` del mismo directorio.
