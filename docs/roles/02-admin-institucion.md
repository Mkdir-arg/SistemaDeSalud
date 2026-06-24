# Rol: Admin de institución

> El responsable de **una** institución. Gestiona su estructura, su gente y sus
> procesos — pero **no sale** de su institución ni ve las demás.
> Técnicamente es un usuario con una **membresía de rol `admin`** en esa institución.

**Usuario de demo:** `a.gomez@hospital.gob.ar` / `demo1234` (Ana Gómez, Hospital Central)

---

## 1. En una frase

El admin de institución entra **directo a su institución** (no ve el directorio) y
tiene **acceso completo dentro de ella**: trabajo, registros, diseño y sistema —
todo acotado a esa única institución.

## 2. Qué ve al entrar

A diferencia del super admin, **no pasa por el directorio**: al iniciar sesión
entra automáticamente al **contexto de su institución**. En la barra lateral, en
lugar de "Volver al directorio", ve la leyenda **"Admin de institución · acceso
fijo"** (no puede cambiar de institución).

> Si tuviera membresía en más de una institución, entraría a la primera; el cambio
> entre instituciones propias es una mejora futura (hoy el acceso es fijo a una).

---

## 3. Funcionalidades

Dentro de su institución ve **los cuatro grupos** del menú. Su foco natural es
**SISTEMA** (estructura y usuarios), pero también puede diseñar y operar.

#### 🟦 Inicio — Panel de la institución
- Métricas de **su** institución: Áreas · Sub-áreas · Staff · Casos activos.
- Accesos rápidos a las secciones.

#### ⚙️ SISTEMA *(su responsabilidad principal)*
- **Estructura organizativa**: árbol de Áreas → Sub-áreas. Ficha del área (Datos /
  Staff / Procesos / Sub-áreas). Puede **crear áreas y sub-áreas**, **editar** la
  ficha (responsable, descripción) y **asignar profesionales** a las áreas.
- **Administración**: usuarios con acceso a **su** institución. Puede **crear
  usuarios**, asignarles **rol(es)** (admin / configurador / administrativo) y
  **área(s)**, y activarlos/desactivarlos.

#### 🎨 DISEÑO
- **Flujos** / **Mapa de flujos** / **Formularios**: puede diseñar, validar y
  publicar los procesos de su institución (mismas capacidades que el configurador).

#### 🗂️ TRABAJO  ·  🩺 REGISTROS
- **Bandeja, Filas, Casos** y **Historia clínica, Legajo**: puede operar y
  supervisar la ejecución de su institución (mismas capacidades que el administrativo).

---

## 4. Permisos (resumen)

| Acción | Admin de institución |
|---|---|
| Ver el directorio / otras instituciones | ❌ (solo la suya) |
| Crear / eliminar instituciones | ❌ (solo super admin) |
| **Editar la ficha de su propia institución** (nombre, tipo, datos) | ✅ *(acordado; ver nota)* |
| Gestionar estructura organizativa (áreas/sub-áreas) | ✅ (en su institución) |
| Crear/editar usuarios y asignar roles | ✅ (en su institución) |
| Diseñar / publicar flujos y formularios | ✅ |
| Operar casos y cargar historia clínica | ✅ |

> **Diferencia clave con el super admin:** mismo acceso a las funciones, pero
> **acotado a su institución** y **sin** el nivel de plataforma (directorio, crear
> instituciones, moverse entre instituciones).

---

## 5. Decisiones y notas

- ✅ **Acceso completo confirmado:** ve y opera los 4 grupos dentro de su institución
  (diseña, opera y administra), siempre acotado a ella.
- ✅ **Edita la ficha de su propia institución** (nombre, tipo, datos). Crear o
  eliminar instituciones queda **solo** para el super admin.
  - ⚠️ *Estado:* el backend ya lo permite (un admin solo alcanza su institución), pero
    falta una **acción de UI** "Editar institución" (p. ej. en el panel de Inicio).
    Pendiente menor de implementación.
- 💡 *Idea a futuro:* si un admin pertenece a **varias** instituciones, poder alternar
  entre ellas (hoy entra a una, "acceso fijo").
