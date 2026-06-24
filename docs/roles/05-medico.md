# Rol: Médico / profesional

> El profesional que **atiende y firma**. Comparte el mundo de **Ejecución** y
> **Registros** con el administrativo, pero tiene una capacidad **exclusiva**:
> registrar (firmar) **Atenciones** en la historia clínica. Su función es **por
> área**. Técnicamente: usuario con una **membresía de rol `medico`**.

**Usuario de demo:** `j.perez@hospital.gob.ar` / `demo1234` (Juan Pérez, Hospital Central · médico en Cardiología y Admisión)

---

## 1. En una frase

El médico hace correr los casos igual que el administrativo, pero es el **único**
(además del super admin) que puede **registrar una Atención** —el acto médico que
queda asentado y firmado en la **historia clínica** del paciente—, y solo en las
**áreas a las que está asignado**.

## 2. Qué ve al entrar

Entra directo a su institución. Su menú es el mismo que el del administrativo:
**Inicio**, **TRABAJO** (Bandeja, Filas, Casos) y **REGISTROS** (Historia clínica,
Legajo profesional). No ve Diseño ni Sistema.

> A nivel de **menú/capacidades** es idéntico al administrativo (`trabajo` +
> `registros`). La diferencia no está en qué pantallas ve, sino en **qué puede
> firmar**.

---

## 3. Funcionalidades

Todas las del [administrativo](04-administrativo.md) (bandeja, ejecución de casos,
filas, casos, historia clínica, legajo), **más**:

#### 🖊️ Registro de Atención (exclusivo)
- En la **ejecución de un caso**, cuando el paso actual es un nodo **Atención**, el
  panel permite registrar la atención (título + contenido + **firmar**). Queda como
  una **entrada en la historia clínica** del paciente (`EntradaHistoria`, con
  `firmada`), y el caso pasa a estado **Atendido**.
- Un administrativo **no** puede completar ese paso: el motor lo rechaza
  (`_exigir_medico`).

#### 🧭 Función por área
- El médico solo puede firmar atenciones en las **áreas a las que está asignado**
  (la lista `areas` de su membresía `medico`). Si el caso está en un área donde no
  está asignado, el motor rechaza la atención.
- Una misma persona puede ser **administrativa en un área y médica en otra**: son
  membresías distintas. Se asignan desde **Estructura → Staff → Asignar profesional**,
  eligiendo la **función** (Administrativo / Médico).

---

## 4. Permisos (resumen)

| Acción | Administrativo | Médico |
|---|:---:|:---:|
| Operar casos (tomar, iniciar, avanzar, llamar de fila) | ✅ | ✅ |
| Crear casos / pacientes / cargar historia clínica | ✅ | ✅ |
| **Registrar / firmar una Atención** | ❌ | ✅ *(en sus áreas)* |
| Diseñar / publicar flujos o formularios | ❌ | ❌ |
| Gestionar estructura organizativa / usuarios | ❌ | ❌ |
| Ver otras instituciones | ❌ | ❌ |

---

## 5. Decisiones y notas

- **Médico ≠ administrativo** en el modelo: son roles separados (`medico` /
  `administrativo`). El menú y las capacidades coinciden; lo que cambia es la **firma
  de atenciones**, que el motor restringe al rol `medico` (o super admin).
- La regla vive en `_exigir_medico()` de
  [`apps/casos/motor.py`](../../backend/apps/casos/motor.py): exige autor con
  membresía `medico` en la institución del caso y, si el caso tiene `area_actual`,
  que esa área esté entre las del médico.
- La **función por área** se modela con la M2M `Membresia.areas`; el alta se hace
  en la solapa **Staff** de la ficha de área.
