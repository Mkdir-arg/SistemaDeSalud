# Rol: Enfermería

> Triage, cuidados, internación e insumos. Ve la historia clínica y solicita
> estudios, pero **no prescribe**.
> Técnicamente: membresía con rol `enfermeria`.

**Usuario de demo:** `guardia.enf@hospital.gob.ar` / `demo1234`

---

## 1. En una frase

Clasifica al paciente al entrar —lo que fija la prioridad con la que va a esperar—,
lo cuida mientras está internado y consume los insumos que hagan falta, dejando cada
cosa registrada.

## 2. Qué ve al entrar

Entra directo a su institución. Ve **Casos**, **Turnos programados**,
**Internación**, **Farmacia e insumos**, **Red y traslados**, **Padrón de
pacientes**, **Historia clínica**, **Legajo profesional** y **Coberturas y copagos**.

No ve Estructura, Administración, Flujos, Formularios, Tablero ni Supervisión.

## 3. Funcionalidades

#### 🟦 Inicio — Mi trabajo
- Sus tareas asignadas y lo tomable por sus grupos.

#### Triage y ejecución del caso
- Completa los formularios de enfermería del paso actual.
- **El triage fija la prioridad del caso** —Rojo → urgente, Amarillo → alta, …— y
  con esa prioridad se ordena la única sala de espera: el profesional llama siempre
  al de mayor prioridad primero.
- Llama, rellama, devuelve a la cola y marca ausente, si integra el grupo del nodo.
- Registra intervenciones asistenciales y **solicita estudios**.

#### 🛏️ Internación
- Tablero de camas por sector con sus cuatro estados: libre, ocupada, en higiene,
  bloqueada.
- Asigna cama desde el caso, registra pases de sector o cama, y egresos con motivo.
- Una cama ocupada siempre tiene un caso asociado; al liberarla puede pasar a higiene
  antes de volver a libre.

#### 💊 Farmacia e insumos
- Consume insumos **imputándolos al caso**, que es lo que después permite responder
  «se retira este lote, a quién se le aplicó».
- Opera lotes, existencias, movimientos y pedidos entre depósitos.
- No mantiene el catálogo de insumos ni crea depósitos: eso es configuración.

#### 🩺 REGISTROS
- **Historia clínica** completa: antecedentes, alergias, condiciones, evolución,
  estudios y recetas, en lectura.
- **Padrón de pacientes** y **Legajo profesional** propio.

## 4. Permisos

| Acción | Enfermería |
|---|---|
| Operar casos, filas, turnos y traslados | ✅ |
| Ver historia clínica y registrar intervenciones | ✅ |
| **Solicitar estudios** | ✅ |
| Operar internación y camas | ✅ |
| **Operar el stock de farmacia** | ✅ |
| Gestionar el padrón y el consentimiento | ✅ |
| **Emitir recetas** | ❌ Es `prescripcion`, que tiene el médico |
| Firmar una atención que el nodo reserva a médico | ❌ |
| Ver el tablero o supervisar | ❌ |
| Auditar accesos clínicos | ❌ |
| Diseñar flujos o formularios | ❌ |
| Administrar usuarios o estructura | ❌ |

Capacidades: `trabajo`, `registros`, `padron_admision`, `historia_clinica`,
`solicitud_estudios`, `turnos`, `casos_operar`, `filas`, `internacion`,
`farmacia_stock`, `traslados_red`.

## 5. Dos asimetrías con el médico

- **Enfermería opera el stock de farmacia y el médico no.** Quien consume el insumo
  en la sala es enfermería, así que la capacidad `farmacia_stock` está de este lado.
- **El médico prescribe y enfermería no.** Las dos pueden solicitar estudios.

Si un nodo declara grupos responsables, además hay que integrar uno de ellos para
poder tomar ese paso.
