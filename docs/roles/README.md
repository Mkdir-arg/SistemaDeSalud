# Documentación funcional por rol

Qué puede hacer cada rol, pantalla por pantalla, en lenguaje de producto.
Actualizado el **22/09/2026** contra `main` en `fca71e3`.

Esta carpeta cuenta el modelo de autoridad **rol por rol**. La especificación
completa —capacidades, matrices, endpoints y reglas de seguridad— está en
[`docs/ROLES-Y-PERMISOS.md`](../ROLES-Y-PERMISOS.md). Si las dos difieren, manda esa.

## Los roles

Hay un **superusuario técnico** y **nueve roles de membresía**, cuatro de gobierno
y cinco institucionales. Una persona puede tener varios roles, y distintos roles en
distintas instituciones; la función se acota por **área**.

| # | Rol | Nivel | En una frase |
|---|---|---|---|
| [01](01-super-admin.md) | **Superusuario** | Técnico | Atraviesa todo. Soporte y contingencia, no operación diaria |
| [02](02-plataforma.md) | **Autoridad estatal / plataforma** | Estatal | Da de alta efectores, redes y organizaciones. Sin permisos clínicos |
| [03](03-auditor.md) | **Auditor estatal** | Estatal | Lee quién consultó qué historia. No opera nada |
| [04](04-reportes.md) | **Reportes / solo lectura** | Estatal | Consulta agregada no nominal. Hoy casi sin pantallas |
| [05](05-admin-institucion.md) | **Admin de institución** | Institución | Gobierna su hospital: estructura, gente, procesos y finanzas |
| [06](06-configurador.md) | **Configurador** | Institución | Diseña flujos y formularios. No ve pacientes |
| [07](07-jefe-area.md) | **Jefe / supervisor de área** | Institución | Ordena y supervisa su área. Audita accesos |
| [08](08-administrativo.md) | **Administrativo** | Institución | Admisión, turnos, filas. **No ve historia clínica** |
| [09](09-enfermeria.md) | **Enfermería** | Institución | Triage, cuidados, internación e insumos |
| [10](10-medico.md) | **Médico / profesional** | Institución | Atiende, firma, prescribe y deriva |

Dos cosas que conviene saber antes de leer las fichas:

- **El rol no da permisos financieros.** Finanzas y cobertura se gobiernan con
  concesiones explícitas que se otorgan de a una, con su área y su alcance sensible.
  La única excepción es el admin de institución, que las hereda todas dentro de su
  institución.
- **Los usuarios de obras sociales no tienen ninguno de estos roles.** Tienen una
  membresía de financiador aparte. Ver
  [Financiadores, cobertura y copagos](../funcionalidades/financiadores-cobertura/README.md).

## Qué ve cada rol en el menú

El menú lateral se arma con las capacidades de la institución activa. Bandeja y
Filas no están en el menú a propósito: se operan desde **Mi trabajo**, en Inicio.

| Ítem del menú | Super | Plataforma | Auditor | Reportes | Admin | Config. | Jefe | Admin.vo | Enf. | Médico |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| Estructura organizativa | ✅ | — | — | — | ✅ | — | — | — | — | — |
| Administración | ✅ | — | — | — | ✅ | — | — | — | — | — |
| Flujos · Mapa · Formularios | ✅ | — | — | — | ✅ | ✅ | — | — | — | — |
| Casos | ✅ | — | — | — | ✅ | — | ✅ | ✅ | ✅ | ✅ |
| Tablero · Supervisión | ✅ | — | — | — | ✅ | — | ✅ | — | — | — |
| Turnos programados | ✅ | — | — | — | ✅ | — | ✅ | ✅ | ✅ | ✅ |
| Internación | ✅ | — | — | — | ✅ | — | ✅ | — | ✅ | ✅ |
| Farmacia e insumos | ✅ | — | — | — | ✅ | — | ✅ | — | ✅ | — |
| Red y traslados | ✅ | — | — | — | ✅ | — | ✅ | ✅ | ✅ | ✅ |
| Padrón de pacientes | ✅ | — | — | — | ✅ | — | ✅ | ✅ | ✅ | ✅ |
| Historia clínica | ✅ | — | — | — | ✅ | — | ✅ | — | ✅ | ✅ |
| Legajo profesional | ✅ | — | — | — | ✅ | — | ✅ | ✅ | ✅ | ✅ |
| Registro de accesos | ✅ | ✅ | ✅ | — | ✅ | — | ✅ | — | — | — |
| Finanzas y costos | ✅ | — | — | — | ✅ | — | ◻ | ◻ | ◻ | ◻ |
| Coberturas y copagos | ✅ | — | — | — | ✅ | — | ✅ | ✅ | ✅ | ✅ |
| Portal de financiadores | ✅ | ✅ | — | — | ◻ | — | ◻ | ◻ | ◻ | ◻ |

✅ lo ve por su rol · ◻ sólo con una condición extra (concesiones financieras, o una membresía de financiador en el caso del portal) · — no lo ve.

**Coberturas y copagos** aparece para quien puede operar casos, aunque no tenga
permisos financieros: ahí adentro cada pestaña sí depende de sus concesiones.

## Usuarios de demo

Del escenario de guardia (`seed_guardia` + `seed_roles`), en el stack de
desarrollo. Contraseña `demo1234` para todos, salvo que el entorno defina `DEMO_PASSWORD`.

| Rol | Usuario |
|---|---|
| Superusuario | `admin@salud.local` / `demo1234` |
| Plataforma | `plataforma@salud.local` |
| Auditor | `auditor@salud.local` |
| Reportes | `reportes@salud.local` |
| Admin de institución | `admin.central@hospital.gob.ar` |
| Configurador | `config.central@hospital.gob.ar` |
| Jefe de área | `guardia.jefe@hospital.gob.ar` |
| Administrativo | `guardia.adm@hospital.gob.ar` |
| Enfermería | `guardia.enf@hospital.gob.ar` |
| Médico | `guardia.med@hospital.gob.ar` |

Los entornos de demo y de configuración desde cero tienen **otros usuarios**:
ver [`docs/entornos/`](../entornos/README.md).
