# Escenario de prueba — Guardia hospitalaria completa

> **Objetivo final** del sistema, usado como caso de referencia. Documento vivo.
> Creado: **2026-06-25**. Reescrito con los flujos realistas: **2026-06-25**.

## 1. Qué simulamos

Una **guardia de hospital** de punta a punta, con triage tipo **Manchester** y
todos los circuitos que nacen de ella: especialidades, estudios (laboratorio /
imágenes) con **ida y vuelta**, interconsultas e **internación**.

El triage **fija la prioridad** del caso (Rojo→urgente, Amarillo→alta, …) y todos
pasan a una **única** sala de espera cuya cola se ordena por esa prioridad: el
médico, desde su **box**, llama siempre al de mayor prioridad primero.

```
 Inicio ─► Admisión ─► Triage ─► Sala de espera ─► Conducta médica ─► ¿Conducta?
 (manual) (administr.) (enferm.) (atención con fila,        │
                       fija prioridad)  cola por prioridad)  ▼
                                                                     │
            ┌────────────────┬───────────────────┬─────────────────┴──────────────┐
            ▼                ▼                   ▼                                  ▼
          Alta          Internación         Observación                    Derivar a especialidad
        (fin)          (→ Internación)    (espera → reevalúa)             ¿Especialidad? ─► Trauma
                                                                                          ├─ Cardiología
                                                                                          ├─ Salud mental
                                                                                          └─ Neurología
```

Cada especialidad recibe la derivación y corre **su propio flujo**:
```
Inicio (derivado) → Atención con fila → Conducta → ¿Disposición? → { Alta | Internación }
```
Durante la **Atención con fila** el médico puede, con las acciones del caso:
- **Solicitar un estudio** a Laboratorio o Imágenes (ida y vuelta: el caso espera
  y retoma cuando vuelve el resultado).
- **Pedir una interconsulta** a otra área (ida y vuelta).
- **Emitir recetas**, que quedan en la historia clínica.

## 2. Estructura organizativa

| Área | Grupos (equipos) | Staff de ejemplo |
|---|---|---|
| **Guardia** | `Admisión de guardia`, `Enfermería de triage`, `Médicos de guardia` | `guardia.adm`, `guardia.enf`, `guardia.med` |
| **Traumatología** | `Admin. trauma`, `Médicos trauma` | `trauma.adm`, `trauma.med` |
| **Cardiología** | `Admin. cardio`, `Médicos cardio` | `cardio.adm`, `cardio.med` |
| **Salud mental** | `Admin. SM`, `Profesionales SM` | `sm.adm`, `sm.med` |
| **Neurología** | `Médicos neuro` | `neuro.med` |
| **Diagnóstico por imágenes** | `Técnicos de imágenes` | `img.med` |
| **Laboratorio** | `Bioquímicos` | `lab.med` |
| **Internación** | `Admisión internación`, `Médicos de planta` | `int.adm`, `int.med` |

- **Boxes:** Guardia tiene `Consultorio 1` y `Consultorio 2`; cada especialidad,
  `Box 1` y `Box 2`. Son los puntos desde donde se **llama** al paciente en una
  atención con fila.
- **Quién hace qué:** cada nodo de trabajo está asignado al grupo responsable, así
  la bandeja y la fila filtran por equipo (sólo ese equipo ve y opera el caso).

## 3. Los flujos (8 publicados)

### 3.1. Ingreso a Guardia (entrada manual) — flujo central
```
Inicio → Admisión administrativa → Triage de enfermería → Sala de espera → Conducta médica → ¿Conducta?
   ├─ Alta ───────────────► Alta de guardia (fin)
   ├─ Internación ────────► Internar (deriva al flujo Internación)
   ├─ Observación ────────► Observación en guardia (espera) → vuelve a Conducta
   └─ Derivar (default) ──► ¿Especialidad? → Trauma / Cardio / Salud mental / Neurología
```
- **Admisión administrativa** (grupo `Admisión de guardia`): motivo, forma de
  llegada, cobertura, acompañante.
- **Triage de enfermería** (grupo `Enfermería de triage`): signos vitales, dolor y
  el **Nivel de triage** (Rojo / Naranja / Amarillo / Verde / Azul). El nivel **fija
  la prioridad** del caso (Rojo/Naranja→urgente, Amarillo→alta, Verde/Azul→normal),
  que es lo que ordena la fila.
- **Sala de espera** (grupo `Médicos de guardia`, atención con fila): una **única**
  cola ordenada por prioridad. El médico **ocupa un box** y llama al de mayor
  prioridad primero (los urgentes encabezan). No hay vía Shock Room separada: el
  urgente simplemente va al frente de la fila.
- **Conducta médica** (grupo `Médicos de guardia`): diagnóstico presuntivo + la
  **Conducta** (Alta / Derivar / Internación / Observación) y, si deriva, la
  **Especialidad**.

### 3.2. Especialidades (Trauma / Cardio / Salud mental / Neurología)
```
Inicio (derivado) → Atención con fila → Conducta → ¿Disposición? → { Alta | Internar }
```
Cada una tiene su **formulario de conducta** con un dato clínico propio (¿requiere
cirugía?, riesgo cardiovascular, nivel de riesgo, déficit focal). Los estudios,
interconsultas y recetas se piden **dentro de la atención** (acciones del caso).

### 3.3. Laboratorio e Imágenes (ida y vuelta de estudios)
```
Laboratorio: Inicio → Toma de muestra → Procesamiento e informe → Informe disponible
Imágenes:    Inicio → Recepción y preparación → Realización e informe → Estudio informado
```
Reciben el sub-caso que genera *Solicitar estudio → derivar a esta área*. En el
nodo de **informe** (atención) el profesional carga el **resultado estructurado**
(Normal / Alterado) y un archivo opcional; al cerrar, el resultado **vuelve** al
médico que lo pidió y el caso retoma su atención.

### 3.4. Internación (destino de internaciones)
```
Inicio (derivado) → Asignar cama → Evolución médica → Conducta → ¿Continúa?
   ├─ Alta médica ──────────► (fin)
   └─ Continúa internado ───► vuelve a Evolución médica (loop)
```

## 4. Recorrido de la prueba

1. **`guardia.adm`** crea un caso nuevo sobre *Ingreso a Guardia* (Bandejas → Nuevo
   caso, eligiendo o creando el paciente) y completa la **admisión**.
2. **`guardia.enf`** hace el **triage** y fija el nivel → eso fija la **prioridad**;
   el caso pasa a la **sala de espera** (los urgentes encabezan la cola).
3. **`guardia.med`** **ocupa un box** y llama al de mayor prioridad; lo atiende y carga la
   **conducta**. Según ella el caso se da de **alta**, se **interna**, queda en
   **observación** o se **deriva** a una especialidad.
4. En la **especialidad**, su médico (p. ej. `cardio.med`) llama desde un box,
   atiende y puede **solicitar un estudio** (a `Laboratorio` / `Imágenes`) o una
   **interconsulta** (a `Neurología`): el caso queda **esperando**.
5. **`lab.med` / `img.med`** procesan el estudio y cargan el **resultado**; el caso
   **vuelve** al médico de la especialidad, que cierra la conducta (alta o
   internación).
6. Si interna, se crea el caso en **Internación**, donde `int.adm` asigna la cama y
   `int.med` evoluciona hasta el alta.

## 5. Estado de las piezas

| Pieza | Estado |
|---|---|
| Áreas / staff / grupos / boxes | ✅ |
| Asignar grupos a nodos («quién hace qué») | ✅ |
| Bandeja y fila filtradas por grupo; restringir tomar/llamar/avanzar | ✅ |
| Triage que **fija la prioridad** del caso (Rojo→urgente, …) | ✅ |
| Atención con fila por prioridad (cola urgente>alta>normal) + **box obligatorio** | ✅ |
| Ocupación de box (check-in del médico: ocupar/liberar) | ✅ |
| Derivar a otro flujo (instanciar caso en destino) | ✅ |
| Solicitar estudio con ida y vuelta + **resultado estructurado** | ✅ |
| Interconsulta a otra área (ida y vuelta) | ✅ |
| Recetas en la historia clínica | ✅ |
| Internación con loop de evolución | ✅ |
| Observación: espera y reevaluación | ⚠️ La reactivación de la espera es manual (no hay cron) |
| Cancelar / reasignar / repriorizar (jefe de área) | ✅ |
| Notificaciones (estudio vuelve · reasignación · urgente · cancelación) | ✅ |

## 6. Cómo cargar el escenario

`seed_guardia` arma la **estructura**: áreas, staff, grupos, boxes, formularios y los
8 flujos publicados. Es idempotente (borra flujos/formularios/casos y los recrea),
pero **no crea ningún caso**: con solo esto, las bandejas, las filas, la pantalla de
llamados y el tablero se ven vacíos.

`seed_volumen` carga el **volumen**: el padrón de pacientes y los casos, recorridos
con el motor real y fechados hacia atrás. Es lo que hace que el sistema se pueda
mostrar y medir.

```bash
# Reset completo de la demo, un solo comando (~40 s):
docker compose exec backend python manage.py seed_volumen --rehacer
# o, en local:  python manage.py seed_volumen --rehacer
```

Con los valores por defecto deja **~530 casos** sobre **90 días** de historia: ~300
ingresos cerrados que alimentan el tablero, más ~42 casos en curso repartidos por
todos los pasos para que ninguna bandeja ni fila quede vacía.

| Opción | Para qué |
|---|---|
| `--rehacer` | Corre `seed_guardia` primero y limpia los registros clínicos previos |
| `--casos N` | Ingresos históricos, ya cerrados (300) |
| `--activos N` | Casos en curso, de las últimas horas (42) |
| `--pacientes N` · `--dias N` | Tamaño del padrón (40) y ventana histórica (90) |
| `--semilla N` | Misma semilla = mismos datos. La demo se resetea idéntica |

**Dos detalles que importan** (y que costaron encontrar):

- Los casos **en curso** solo pueden ser recientes. Un paciente esperando en una sala
  desde hace 60 días es un dato absurdo que además rompe el panel de demoras del
  tablero. Cada punto de detención tiene su propia ventana de antigüedad (`PARADAS`).
- Al limpiar hay que borrar los **registros clínicos** a mano: `EntradaHistoria.caso`
  es `SET_NULL`, así que las entradas sobreviven al borrado de los casos y se acumulan
  en cada corrida.

**Accesos** (contraseña `demo1234`, salvo el admin):
- `admin@cauce.local` / `admin1234` — super admin (ve todo, configura).
- `guardia.adm@hospital.gob.ar` — admisión (arranca el ingreso).
- `guardia.enf@hospital.gob.ar` — enfermería (triage).
- `guardia.med@hospital.gob.ar` — médico de guardia (atención y conducta).
- `trauma.med` · `cardio.med` · `sm.med` · `neuro.med` — médicos de especialidad.
- `lab.med` · `img.med` — laboratorio / imágenes (estudios).
- `int.adm` · `int.med` — internación.

> Verificado de punta a punta (smoke test del motor): ingreso urgente → triage Rojo
> (→ prioridad urgente, encabeza la fila) → el médico ocupa un box y lo llama →
> atención → conducta «Derivar a Cardiología» → atención cardiológica → estudio
> «Troponinas» derivado a Laboratorio → resultado *alterado* devuelto → conducta
> «Internación» → caso abierto en Internación. La HC del paciente queda con el
> estudio (resultado + realizado) y las entradas de atención.
