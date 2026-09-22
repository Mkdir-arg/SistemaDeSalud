# Rol: Médico / profesional

> Atiende, **firma**, prescribe, solicita estudios y deriva. Su función se acota
> **por área**.
> Técnicamente: membresía con rol `medico`, con sus áreas asignadas.

**Usuario de demo:** `guardia.med@hospital.gob.ar` / `demo1234`
(especialidades: `cardio.med@` · `trauma.med@` · `sm.med@` · `neuro.med@`)

---

## 1. En una frase

Es quien resuelve clínicamente el caso: llama al paciente desde su box, registra la
atención firmada, pide estudios, prescribe y decide la conducta —alta, observación,
internación o derivación a especialidad—.

## 2. Qué ve al entrar

Entra directo a su institución. Ve **Casos**, **Turnos programados**,
**Internación**, **Red y traslados**, **Padrón de pacientes**, **Historia clínica**,
**Legajo profesional** y **Coberturas y copagos**.

No ve Estructura, Administración, Flujos, Formularios, Tablero, Supervisión ni
**Farmacia**.

## 3. Funcionalidades

#### 🟦 Inicio — Mi trabajo
- Sus casos asignados, lo tomable por sus grupos y las esperas vencidas.

#### Puesto de atención (`/puesto/:id`)
- Ocupa un **box** y llama al siguiente de la fila, siempre el de mayor prioridad.
  Llamar ocupa el box; marcar ausente lo libera.

#### Ejecución del caso (`/casos/:id`)
- **Registrar la atención**: título, contenido y **firma**. Queda como entrada en la
  historia clínica del paciente y el caso avanza.
- **Conducta**: alta, observación, internación o derivación a una especialidad; el
  motor resuelve la decisión según las reglas del flujo.
- **Solicitar estudios** e interconsultas, con ida y vuelta: el caso queda en espera
  y vuelve con el resultado. Recibe una notificación cuando el estudio regresa.
- **Emitir recetas**, y suspenderlas.
- **Asignar cama** y registrar pases y egresos, cuando el flujo lo vincula.
- **Solicitar un traslado** a otro establecimiento de la red.
- **Cobertura**: consultar cuánto cubre el financiador antes de la prestación, y
  confirmar la que se va a realizar.

#### 🩺 REGISTROS
- Historia clínica completa: antecedentes, alergias, condiciones, evolución,
  estudios y recetas.
- Legajo profesional propio: su actividad, con enlace a la historia de cada paciente
  atendido.

## 4. Permisos

| Acción | Médico |
|---|---|
| Operar casos, filas, turnos y traslados | ✅ |
| Ver y cargar historia clínica | ✅ |
| **Firmar una atención** | ✅ Si el nodo lo habilita y el área es suya |
| **Emitir y suspender recetas** | ✅ |
| Solicitar estudios e interconsultas | ✅ |
| Operar internación y camas | ✅ |
| Gestionar el padrón y el consentimiento | ✅ |
| **Operar el stock de farmacia** | ❌ Es `farmacia_stock`, que tiene enfermería |
| Ver el tablero o supervisar | ❌ |
| Auditar accesos clínicos | ❌ No audita a sus colegas |
| Diseñar flujos o formularios | ❌ |
| Administrar usuarios o estructura | ❌ |

Capacidades: `trabajo`, `registros`, `padron_admision`, `historia_clinica`,
`prescripcion`, `solicitud_estudios`, `turnos`, `casos_operar`, `filas`,
`internacion`, `traslados_red`.

## 5. Quién firma: lo decide el nodo, no el rol

La firma **no está fijada al rol médico**. Cada nodo de atención declara qué roles
pueden firmarlo —médico, enfermería, administrativo o jefe de área— y si la firma
exige matrícula. Si el nodo no lo declara, rige el **default seguro: médico con
matrícula**.

Además, si el caso está en un área, hay que **tener esa área asignada** en la
membresía. Un médico de Cardiología no firma la atención de un caso que está en
Traumatología.

Publicar un flujo avisa si un nodo declara un rol de firma que el sistema no
reconoce, para que el problema no aparezca con el paciente esperando.

## 6. Médico vs. administrativo vs. enfermería

| | Administrativo | Enfermería | Médico |
|---|:-:|:-:|:-:|
| Ve la historia clínica | ❌ | ✅ | ✅ |
| Solicita estudios | ❌ | ✅ | ✅ |
| Emite recetas | ❌ | ❌ | ✅ |
| Opera el stock de farmacia | ❌ | ✅ | ❌ |
| Opera internación | ❌ | ✅ | ✅ |

Una misma persona puede tener **membresías distintas en áreas distintas**. Se
asignan desde **Estructura → ficha del área → Staff**.
