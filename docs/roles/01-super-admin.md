# Rol: Super admin (plataforma)

> El nivel más alto. No pertenece a una institución: **las administra todas**.
> Técnicamente es el usuario con `is_superuser = True`. El scope por institución
> no lo limita: ve y opera todo.

**Usuario de demo:** `admin@cauce.local` / `admin1234`

---

## 1. En una frase

El super admin entra a la plataforma, ve el **directorio de todas las
instituciones**, y puede **ingresar a cualquiera** para operarla con acceso
total (diseño, ejecución, registros y administración).

## 2. Qué ve al entrar

Al iniciar sesión aterriza en el **Directorio de instituciones** (no en una
institución puntual). La barra superior muestra:
- El pill **"Alcance: todas las instituciones"**.
- El selector de vista **Super admin / Admin de institución**.

---

## 3. Funcionalidades

### 3.1. Directorio de instituciones *(pantalla raíz)*

Es la "home" del super admin. Tabla con **todas** las instituciones de la plataforma.

| Puede… | Detalle |
|---|---|
| **Ver el listado** | Tabla: Institución · Tipo · Áreas · Staff · Estado (Activa / En alta / Inactiva) |
| **Buscar** | Filtro por nombre de institución |
| **Crear institución** | Botón "+ Nueva institución" → nombre, tipo, CUIT. Nace en estado **En alta** |
| **Ingresar a una institución** | Botón "Ingresar" → entra al **contexto** de esa institución |

### 3.2. Contexto de institución

Al ingresar a una institución, el super admin la opera como si estuviera adentro,
con **acceso a todos los mundos**. La barra lateral muestra la institución actual
y el botón **"Volver al directorio"**.

- **Vista por rol** (barra superior: Configurador / Administrativo / Sistema):
  permite *previsualizar* el sistema como lo vería cada rol (cambia qué grupos del
  menú se muestran). Por defecto está en **Sistema** (ve todo).
- **Volver al directorio**: sale del contexto y vuelve al listado de instituciones.

Dentro de la institución, accede a estos grupos del menú:

#### 🟦 Inicio — Panel de la institución
- Cabecera con nombre, tipo y estado de la institución.
- Métricas: **Áreas · Sub-áreas · Staff · Casos activos**.
- Accesos rápidos a las secciones.

#### 🗂️ TRABAJO (ejecución)
- **Bandeja de tareas**: casos asignados ("Mis casos") y "Sin asignar". Puede
  **tomar** un caso, **continuarlo** y **crear un caso nuevo** (elige flujo
  publicado + paciente).
- **Filas de espera**: casos encolados (orden FIFO + urgencias). Puede **llamar al
  siguiente**.
- **Casos**: auditoría de **todos** los casos de la institución (estado, área,
  asignación). Clic → detalle con trazabilidad.

#### 🩺 REGISTROS
- **Historia clínica**: lista de pacientes (condiciones/alergias, entradas, última
  visita). Puede **crear un registro** (paciente) y abrir el **detalle** (métricas
  + evolución / estudios / recetas) y **registrar una nueva atención**.
- **Legajo profesional**: dashboard por profesional (casos atendidos, pacientes
  vistos, llamados de fila, actividad reciente). Puede **editar** especialidad/matrícula.

#### 🎨 DISEÑO
- **Flujos**: lista de flujos (estado, versión, casos). Puede **crear** un flujo,
  **abrirlo en el diseñador** (lienzo: paleta de nodos, arrastrar, conectar,
  propiedades, reglas de decisión), **validar** y **publicar** versiones.
- **Mapa de flujos**: vista panorámica de los procesos.
- **Formularios**: constructor de formularios con **vista previa en vivo**; puede
  crear formularios y agregar campos (tipos + campos vinculados a HC/legajo).

#### ⚙️ SISTEMA
- **Estructura organizativa**: árbol de Áreas → Sub-áreas. Ficha del área (Datos /
  Staff / Procesos / Sub-áreas). Puede **crear áreas/sub-áreas**, **editar** la
  ficha y **asignar profesionales** a un área.
- **Administración**: usuarios con acceso a la institución (rol(es), área(s),
  estado). Puede **crear usuarios**, asignar **roles** y **membresías**.

---

## 4. Permisos (resumen)

| Acción | Super admin |
|---|---|
| Ver todas las instituciones | ✅ |
| Crear instituciones | ✅ |
| Entrar a cualquier institución | ✅ |
| Diseñar / publicar flujos | ✅ |
| Operar casos (tomar, avanzar, derivar) | ✅ |
| Ver / editar historia clínica | ✅ |
| Gestionar estructura y usuarios | ✅ |

> **Nota técnica:** el alcance "ve todo" surge de `is_superuser=True`, que saltea
> el filtro por institución (`InstitucionScopedMixin`). Cualquier otro usuario solo
> ve las instituciones donde tiene una membresía.

---

## 5. Decisiones y notas

- ✅ **Acceso total confirmado:** el super admin puede operar casos, cargar
  historia clínica, diseñar flujos y administrar — sin restricciones — en cualquier
  institución.
- 💡 *Ideas a futuro (no bloqueantes):*
  - Estados de institución (Activa / En alta / Inactiva): podría sumarse un flujo de
    alta con pasos para activar una institución recién creada.
  - El selector "Admin de institución" de la barra del directorio podría permitir al
    super admin actuar *como* admin de una institución puntual.
