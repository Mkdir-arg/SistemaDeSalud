# Escenario de prueba — Guardia completa

> **Objetivo final** del sistema, usado como caso de referencia. En base a esto
> generamos los evolutivos. Documento vivo.
> Creado: **2026-06-25**.

## 1. Qué queremos simular

Una **guardia de hospital** de punta a punta:

1. **Ingreso a guardia** — el paciente llega, se lo registra y se hace un triage
   inicial.
2. **Derivación a especialidad** — al final del ingreso, según la evaluación, el
   caso se deriva a **Traumatología**, **Cardiología** o **Salud mental
   (Psiquiatría)**.
3. **Atención en la especialidad** — cada especialidad tiene **su propio flujo**,
   con **su formulario** y la **solicitud de sus estudios**.
4. **Equipos por área** — cada flujo lo operan **los médicos y los
   administrativos de esa área** (vía grupos responsables por nodo).

```
                                   ┌──────────────────────────────┐
                                   │  Flujo: Atención Traumatología│
                          ┌──────► │  form trauma + estudios        │
                          │        └──────────────────────────────┘
┌───────────────────────┐ │       ┌──────────────────────────────┐
│ Flujo: Ingreso a       │ │       │  Flujo: Atención Cardiología  │
│ Guardia                ├─┼─────► │  form cardio + estudios        │
│ (registro + triage +   │ │       └──────────────────────────────┘
│  decisión de destino)  │ │       ┌──────────────────────────────┐
└───────────────────────┘ │       │  Flujo: Atención Salud mental │
                          └──────► │  form psico + estudios         │
                                   └──────────────────────────────┘
```

## 2. Estructura organizativa a configurar

| Área | Sub-áreas | Grupos (equipos) | Staff de ejemplo |
|---|---|---|---|
| **Guardia** | — | `Médicos de guardia`, `Admin. de guardia` | 1-2 médicos, 1 administrativo |
| **Traumatología** | — | `Médicos trauma`, `Admin. trauma` | 1 médico, 1 administrativo |
| **Cardiología** | (Hemodinamia) | `Médicos cardio`, `Admin. cardio` | 1 médico, 1 administrativo |
| **Salud mental** | — | `Profesionales SM`, `Admin. SM` | 1 médico/psic., 1 administrativo |

- Cada persona se carga como **staff del área** (Estructura → área → Staff) con su
  **función** (Médico / Administrativo).
- Los **grupos** se arman dentro de cada área (Estructura → área → Grupos) y son
  los que después se asignan a los nodos de los flujos.

## 3. Flujos a diseñar

### 3.1. Ingreso a Guardia (ámbito: área Guardia)
```
Inicio → Formulario «Datos de ingreso» → Decisión «¿Especialidad?»
   ├─ [Trauma]  → Derivar a Flujo «Atención Traumatología»
   ├─ [Cardio]  → Derivar a Flujo «Atención Cardiología»
   └─ [S. mental] → Derivar a Flujo «Atención Salud mental»
```
- **Formulario de ingreso:** datos del paciente + motivo + un campo de selección
  **Especialidad** (Trauma / Cardio / Salud mental) que alimenta la decisión.
- **Responsable de los nodos:** grupos `Médicos de guardia` / `Admin. de guardia`.

### 3.2. Flujo por especialidad (ámbito: área de la especialidad)
Mismo esqueleto para Trauma / Cardio / Salud mental:
```
Inicio → Formulario propio → Solicitud de estudios → Atención con fila → Fin
```
- **Formulario propio:** cada especialidad tiene su formulario (campos distintos).
- **Solicitud de estudios:** el pedido de los estudios de esa especialidad (hoy placeholder).
- **Atención con fila:** un **único nodo** que une espera + llamado + atención. El
  paciente queda en la **sala de espera** (cola FIFO + urgencia); un médico lo
  **llama desde un Box** (consultorio del área) y recién ahí lo atiende (la
  atención queda en la HC). Config: nodo Atención con «fila de espera» activada.
- **Boxes:** consultorios del área (Estructura → área → Boxes). Se llama desde
  cada box en la pantalla **Filas de espera**; queda registrado en qué box se atendió.
- **Responsable:** el grupo de médicos del área (quién llama y atiende).

## 4. Recorrido de la prueba (cuando esté configurado)

1. Crear un **caso nuevo** sobre el flujo *Ingreso a Guardia* (Bandejas → Nuevo caso).
2. El **administrativo de guardia** lo toma, completa los datos y elige la
   especialidad → el caso se **deriva** y aparece como un caso del flujo de esa
   especialidad.
3. El caso cae en la **bandeja del equipo de la especialidad** (solo ellos lo ven).
4. El **médico de la especialidad** completa su formulario, **solicita estudios** y
   **registra la atención** (queda en la historia clínica).
5. Cierre del caso.

## 5. Qué tenemos hoy vs. qué falta (evolutivos)

Estado de las piezas que requiere el escenario:

| Pieza | Estado | Nota |
|---|---|---|
| Áreas / sub-áreas / staff | ✅ Listo | Estructura organizativa completa |
| Grupos por área + integrantes | ✅ Listo | `Grupo` + pestaña Grupos |
| Asignar grupos a nodos («quién hace qué») | ✅ Listo | `Nodo.grupos` + editor |
| Bandeja filtrada por grupo + restringir tomar/avanzar | ✅ Listo | Motor `usuario_puede_tomar` |
| Flujo con ámbito por área | ✅ Listo | `Flujo.area` / `subarea` |
| Decisión con ramas por valor de campo | ✅ Listo | `Conexion.condicion` |
| Atención → entrada en historia clínica | ✅ Listo | Nodo `atencion` |
| **Derivar a OTRO flujo (instanciar caso en el destino)** | ✅ **Listo** | El nodo `derivar` con `flujo_destino_id` **instancia y arranca** un caso en el flujo destino, **vinculado al origen** (`Caso.origen`) y con el **área del destino**. Trazable en ambos sentidos. |
| **Solicitud de estudios como paso del flujo** | ⚠️ **Falta** | Hoy `Estudio` se carga a mano en la HC. Falta un **tipo de nodo** (o acción) «Solicitar estudios» que genere el pedido durante la ejecución. |
| Cambiar el ámbito de un flujo desde la UI | ⚠️ Falta | Backend ya lo soporta (`PATCH /flujos/{id}/`). |

### Evolutivos priorizados (derivados de esta prueba)
1. ~~Derivar a otro flujo (real)~~ — ✅ **Hecho.** `Nodo.derivar` con
   `flujo_destino_id` crea y arranca el caso destino, con `Caso.origen` y el área
   del flujo destino. Trazabilidad: `origen` / `derivados` en la API y en el
   detalle del caso (tarjeta «Derivaciones» con enlaces). Test:
   `DerivacionEntreFlujosTests`.
2. **Nodo «Solicitud de estudios»:** nuevo tipo de nodo que, al ejecutarse, crea
   el/los `Estudio` pedidos en la HC del paciente (con estado pendiente/resultado).
   **← próximo evolutivo.**
3. **Formularios por especialidad:** sin desarrollo nuevo — se arman con el
   constructor de formularios existente; queda como tarea de **configuración**.

## 6. Cómo cargar el escenario

El escenario completo se carga con un comando (idempotente):

```bash
docker compose exec backend python manage.py seed_guardia
# o, en local:  python manage.py seed_guardia
```

Crea: super admin, **Hospital Central**, las 4 áreas con su **staff** (médico +
administrativo) y sus **grupos**, los **3 flujos de especialidad publicados** y el
**flujo de ingreso** con la decisión y las 3 derivaciones ya enganchadas. No crea
casos (se arranca de cero).

**Accesos** (contraseña `demo1234`, salvo el admin):
- `admin@cauce.local` / `admin1234` — super admin (ve todo, configura).
- `guardia.adm@hospital.gob.ar` — administrativo de guardia (arranca el ingreso).
- `trauma.med@…` · `cardio.med@…` · `sm.med@…` — médicos de cada especialidad.

> `seed_demo` (escenario viejo) y `reset_datos` (limpieza total) siguen existiendo.
> Verificado de punta a punta: un ingreso con *Especialidad = Cardiología* deriva y
> genera el caso en «Atención cardiológica», en el área correcta y con el grupo
> «Admin. cardio» como responsable del primer paso.
