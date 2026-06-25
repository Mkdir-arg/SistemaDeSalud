# Escenario de prueba — Guardia hospitalaria completa

> **Objetivo final** del sistema, usado como caso de referencia. Documento vivo.
> Creado: **2026-06-25**. Reescrito con los flujos realistas: **2026-06-25**.

## 1. Qué simulamos

Una **guardia de hospital** de punta a punta, con triage tipo **Manchester** y
todos los circuitos que nacen de ella: especialidades, estudios (laboratorio /
imágenes) con **ida y vuelta**, interconsultas e **internación**.

```
                                          ┌─ Rojo ──────────► Shock Room (atención inmediata)
 Inicio ─► Admisión ─► Triage ─► ¿Nivel? ─┤
 (manual) (administr.) (enferm.)          └─ resto ────────► Sala de espera (atención con fila)
                                                                     │
                                                                     ▼
                                                              Conducta médica ─► ¿Conducta?
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
Inicio → Admisión administrativa → Triage de enfermería → ¿Nivel de triage?
   ├─ Rojo - Emergencia ───────► Shock Room (atención inmediata, sin fila)
   └─ resto (default) ─────────► Sala de espera (atención con fila)
→ Conducta médica → ¿Conducta?
   ├─ Alta ───────────────► Alta de guardia (fin)
   ├─ Internación ────────► Internar (deriva al flujo Internación)
   ├─ Observación ────────► Observación en guardia (espera) → vuelve a Conducta
   └─ Derivar (default) ──► ¿Especialidad? → Trauma / Cardio / Salud mental / Neurología
```
- **Admisión administrativa** (grupo `Admisión de guardia`): motivo, forma de
  llegada, cobertura, acompañante.
- **Triage de enfermería** (grupo `Enfermería de triage`): signos vitales, dolor y
  el **Nivel de triage** (Rojo / Naranja / Amarillo / Verde / Azul) que decide la rama.
- **Shock Room / Sala de espera** (grupo `Médicos de guardia`): la atención. Sólo el
  rojo va directo al Shock Room; el resto espera en la sala y se llama desde un box.
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
2. **`guardia.enf`** hace el **triage** y fija el nivel. Rojo → Shock Room; resto →
   sala de espera.
3. **`guardia.med`** llama al paciente (si está en la sala) y lo atiende; carga la
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
| Triage con decisión por nivel; ramas por valor de campo | ✅ |
| Atención con fila (espera + llamado desde box + atención) | ✅ |
| Derivar a otro flujo (instanciar caso en destino) | ✅ |
| Solicitar estudio con ida y vuelta + **resultado estructurado** | ✅ |
| Interconsulta a otra área (ida y vuelta) | ✅ |
| Recetas en la historia clínica | ✅ |
| Internación con loop de evolución | ✅ |
| Observación: espera y reevaluación | ⚠️ La reactivación de la espera es manual (no hay cron) |
| Cancelar / cerrar un caso a mano | ⚠️ Falta |
| Notificaciones (cuando vuelve un estudio/interconsulta) | ⚠️ Falta |

## 6. Cómo cargar el escenario

Idempotente: borra los flujos/formularios/casos de la institución y los recrea.

```bash
docker compose exec backend python manage.py seed_guardia
# o, en local:  python manage.py seed_guardia
```

**Accesos** (contraseña `demo1234`, salvo el admin):
- `admin@cauce.local` / `admin1234` — super admin (ve todo, configura).
- `guardia.adm@hospital.gob.ar` — admisión (arranca el ingreso).
- `guardia.enf@hospital.gob.ar` — enfermería (triage).
- `guardia.med@hospital.gob.ar` — médico de guardia (atención y conducta).
- `trauma.med` · `cardio.med` · `sm.med` · `neuro.med` — médicos de especialidad.
- `lab.med` · `img.med` — laboratorio / imágenes (estudios).
- `int.adm` · `int.med` — internación.

> Verificado de punta a punta (smoke test del motor): ingreso urgente → triage Rojo
> → Shock Room → conducta «Derivar a Cardiología» → atención cardiológica → estudio
> «Troponinas» derivado a Laboratorio → resultado *alterado* devuelto → conducta
> «Internación» → caso abierto en Internación. La HC del paciente queda con el
> estudio (resultado + realizado) y las entradas de atención.
