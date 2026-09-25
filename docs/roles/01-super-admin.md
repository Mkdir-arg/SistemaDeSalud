# Rol: Superusuario de plataforma

> El nivel más alto. No pertenece a una institución: **las atraviesa todas**.
> Técnicamente es el usuario con `is_superuser = True`; el filtro por institución
> no lo limita.
>
> **No es un rol hospitalario.** Es un usuario técnico para administración de
> plataforma, soporte y contingencia. Para el gobierno estatal de la red hay un rol
> funcional aparte: [`02-plataforma.md`](02-plataforma.md).

**Usuario de demo:** `admin@salud.local` / `demo1234`

---

## 1. En una frase

Entra al directorio de todas las instituciones y puede ingresar a cualquiera para
operarla con acceso total: configuración, diseño, ejecución, registros, finanzas y
cobertura.

## 2. Qué ve al entrar

Aterriza en el **Directorio de instituciones**, no en una institución puntual. La
barra muestra el alcance —«todas las instituciones»— y un selector de vista
**Sistema / Configurador / Administrativo**, que sirve para *previsualizar* qué
grupos del menú vería cada perfil. Por defecto está en Sistema, que muestra todo.

## 3. Funcionalidades

### 3.1. Directorio de instituciones

| Puede… | Detalle |
|---|---|
| Ver el listado completo | Institución · tipo · áreas · staff · estado |
| Buscar | Por nombre |
| Crear una institución | Nombre, tipo, CUIT, dirección y coordenadas |
| Ingresar a una institución | Entra a su contexto; vuelve con **Volver al directorio** |

Las instituciones **no se borran**: `AccesoClinico.institucion` y
`Flujo.institucion` son `PROTECT` a propósito, porque la auditoría clínica no se
borra. La única baja posible es la de estado.

### 3.2. Dentro de una institución

Ve el menú completo, con sus tres grupos y las entradas transversales:

#### ⚙️ SISTEMA
- **Estructura organizativa**: áreas → subáreas, grupos de trabajo, boxes y camas.
  Ficha del área con Datos, Staff, Grupos y Sub-áreas.
- **Administración**: usuarios, membresías, roles, áreas y **permisos financieros**.
- **Flujos** y **Mapa de flujos**: crear, abrir el editor visual, validar, publicar
  y versionar.
- **Formularios**: constructor de campos con vista previa.

#### 🗂️ TRABAJO
- **Casos** · **Tablero** · **Turnos programados** · **Internación** ·
  **Farmacia e insumos** · **Red y traslados** · **Supervisión**.
- Bandeja y Filas se operan desde **Mi trabajo**, en Inicio.

#### 🩺 REGISTROS
- **Padrón de pacientes** · **Historia clínica** · **Legajo profesional** ·
  **Registro de accesos**.

#### Transversales
- **Finanzas y costos** y **Coberturas y copagos**.
- **Portal de financiadores**, incluido el catálogo común de prestaciones.

### 3.3. Recorrido guiado

Tocando tres veces sobre su ficha de usuario en la barra lateral se inicia el
**recorrido guiado**: la aplicación se maneja sola y construye «Hospital Escuela
Salud» desde cero. Está pensado para demostrar el sistema sin datos previos.

## 4. Permisos

| Acción | Superusuario |
|---|---|
| Ver y entrar a todas las instituciones | ✅ |
| Crear instituciones y redes | ✅ |
| Diseñar, validar y publicar flujos y formularios | ✅ |
| Operar casos, filas, turnos, internación, farmacia, traslados | ✅ |
| Ver y cargar historia clínica | ✅ |
| Auditar accesos clínicos, en toda la plataforma | ✅ |
| Operar Finanzas y cobertura | ✅ Sin necesidad de concesiones |
| Administrar organizaciones de financiadores y el catálogo común | ✅ |

> **Nota técnica.** El alcance «ve todo» surge de `is_superuser=True`, que saltea el
> filtro por institución. Cualquier otro usuario sólo ve las instituciones donde
> tiene una membresía activa.

## 5. Cómo debería usarse

- Administración de plataforma, soporte y contingencia. **No es un rol hospitalario
  cotidiano.**
- Atraviesa todos los límites institucionales, así que requiere controles fuertes de
  credenciales, trazabilidad y uso excepcional.
- Para las tareas de gobierno estatal que sí son cotidianas —alta de efectores,
  redes, auditoría— existe el rol `plataforma`, que **no** recibe permisos clínicos.
