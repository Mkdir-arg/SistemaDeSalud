# Cauce — Documentación funcional por rol

Esta carpeta describe **qué puede hacer cada rol** en el sistema, pantalla por
pantalla, según lo implementado. Es la referencia funcional (no técnica) del
producto.

## Los roles

Cauce tiene un rol de **plataforma** y cuatro roles **por institución** (un mismo
usuario puede tener varios roles, y distintos roles en distintas instituciones; la
**función es por área**).

| Rol | Nivel | Alcance |
|---|---|---|
| **Super admin** | Plataforma | Ve y opera **todas** las instituciones |
| **Admin de institución** | Institución | Gestiona **su** institución (estructura, usuarios) |
| **Configurador** | Institución | Diseña flujos y formularios |
| **Administrativo** | Institución | Ejecuta casos y registros clínicos |
| **Médico / profesional** | Institución | Como administrativo **+ firma de atenciones** (por área) |

> El rol determina **qué grupos del menú** ve y **qué datos** alcanza. Los datos
> siempre se acotan a la institución del contexto (salvo el super admin, que ve todo).
> Administrativo y médico ven el mismo menú; la diferencia es que **solo el médico
> firma atenciones**.

## Documentos

- [`01-super-admin.md`](01-super-admin.md) — Super admin (plataforma) ✅
- [`02-admin-institucion.md`](02-admin-institucion.md) — Admin de institución ✅
- [`03-configurador.md`](03-configurador.md) — Configurador ✅
- [`04-administrativo.md`](04-administrativo.md) — Administrativo ✅
- [`05-medico.md`](05-medico.md) — Médico / profesional ✅

## Usuarios de demo

| Rol | Usuario | Contraseña |
|---|---|---|
| Super admin | `admin@cauce.local` | `admin1234` |
| Admin de institución | `a.gomez@hospital.gob.ar` | `demo1234` |
| Configurador | `m.diaz@hospital.gob.ar` | `demo1234` |
| Administrativo | `operador@cauce.local` | `demo1234` |
| Médico / profesional | `j.perez@hospital.gob.ar` | `demo1234` |
