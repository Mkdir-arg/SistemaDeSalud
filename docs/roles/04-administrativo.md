# Rol: Administrativo / profesional

> El que **opera el día a día**. Vive en el mundo **Ejecución** (software de gestión,
> no lienzo): toma casos, completa formularios, atiende, deriva y deja todo
> registrado. Es quien hace correr los flujos que diseñó el configurador.
> Técnicamente: usuario con una **membresía de rol `administrativo`**.

**Usuario de demo:** `operador@cauce.local` / `demo1234` (Carla Ibáñez, Hospital Central · Admisión)

---

## 1. En una frase

El administrativo recibe **casos reales** (instancias de un flujo publicado), los
**hace avanzar paso a paso** (cargar datos, atender, llamar de la fila, derivar) y
consulta/realiza los **registros clínicos** de los pacientes.

## 2. Qué ve al entrar

Entra directo a su institución (acceso fijo, sin directorio). Su menú muestra
**Inicio**, **TRABAJO** y **REGISTROS** — no ve Diseño ni Sistema.

> Su experiencia es la opuesta al configurador: nada de lienzo ni grilla. Tablas,
> formularios, badges de estado y un **stepper** de progreso — "estoy operando un
> sistema institucional".

---

## 3. Funcionalidades

#### 🟦 Inicio
- Panel de la institución (métricas + accesos rápidos a Bandeja e Historia clínica).

#### 🗂️ TRABAJO *(su mundo)*

**Bandeja de tareas**
- Pestañas **Mis casos** / **Sin asignar** (con contador).
- Columnas: Caso (id + flujo) · Paso actual · Estado · Área · Antigüedad.
- **Tomar** un caso sin asignar → pasa a "Mis casos".
- **Continuar** un caso propio → abre la ejecución.
- **+ Nuevo caso**: elige un flujo **publicado** y un paciente → crea e **inicia** el caso.

**Ejecución de caso** *(la pantalla central del rol)*
- **Stepper** de progreso (Recibido → En proceso → Derivado → Atendido → Cerrado).
- **Historia clínica · antecedentes** del paciente (solo lectura: alergias, condiciones).
- **Panel del paso actual** — según el tipo de nodo:
  - *Formulario* → completar los campos y **avanzar**.
  - *Atención* → registrar la atención (queda como entrada en la **historia clínica**).
  - *Espera de fila* → "Llamar y continuar".
  - *Espera por tiempo* → "Reactivar".
- **Información del caso** (flujo, área, asignado, ingreso, prioridad).
- **Trazabilidad**: línea de tiempo de todo lo que pasó (quién, qué, cuándo).
- El motor resuelve solo las **Decisiones** y **Derivaciones** según las reglas del flujo.

**Filas de espera**
- Casos encolados en un nodo de espera (orden **FIFO + urgencias**).
- Columnas: Turno · Persona · Ingreso · Espera. **Llamar al siguiente**.

**Casos**
- Tabla de **todos** los casos de la institución (auditoría): Caso · Flujo · Paso ·
  Estado · Área · Asignación. Clic → ejecución/trazabilidad.

#### 🩺 REGISTROS

**Historia clínica**
- **Lista** de pacientes (obra social, condiciones/alergias, entradas, última visita)
  con buscador. **+ Crear registro** (alta de paciente).
- **Detalle** (pantalla separada): header del paciente + métricas (consultas,
  estudios, recetas, última visita) + pestañas **Evolución / Estudios / Recetas** +
  **+ Nueva atención**.

**Legajo profesional**
- Su propio legajo: dashboard con casos atendidos, pacientes vistos, llamados de
  fila, actividad reciente (cada atención enlaza a la HC del paciente).

---

## 4. Permisos (resumen)

| Acción | Administrativo / profesional |
|---|---|
| Operar casos (tomar, iniciar, avanzar, llamar de fila) | ✅ |
| Crear casos a partir de flujos publicados | ✅ |
| Crear pacientes y cargar historia clínica | ✅ |
| Ver su legajo profesional | ✅ |
| Diseñar / publicar flujos o formularios | ❌ |
| Gestionar estructura organizativa / usuarios | ❌ |
| Ver otras instituciones | ❌ |

> **Configurador vs. Administrativo:** el configurador define el **proceso** (la
> plantilla); el administrativo ejecuta los **casos** reales sobre esa plantilla.
> Dos mundos visuales distintos a propósito.

---

## 5. Decisiones y notas

- "Administrativo" y "profesional" son **el mismo rol** en el modelo (`administrativo`).
  La diferencia (p. ej. quién puede firmar una atención) podría refinarse a futuro
  con permisos más finos o usando el **Legajo profesional** (matrícula) como llave.
- El menú sale de su **membresía de rol `administrativo`** → habilita **TRABAJO** y
  **REGISTROS** (+ Inicio).
- 💡 *Idea a futuro:* el acceso a Historia clínica podría gatillarse por el legajo
  (rol/área), como dice el prototipo ("el acceso lo habilita el Legajo profesional").
