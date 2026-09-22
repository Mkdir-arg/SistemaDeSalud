# Rol: Admin de institución

> El responsable de **una** institución. Gestiona su estructura, su gente, sus
> procesos y sus finanzas — pero **no sale** de su institución ni ve las demás.
> Técnicamente: membresía con rol `admin` en esa institución.

**Usuario de demo:** `admin.central@hospital.gob.ar` / `demo1234`

---

## 1. En una frase

Entra **directo a su institución** (no ve el directorio) y tiene acceso completo
dentro de ella: configura, opera, registra, audita y gobierna Finanzas.

## 2. Qué ve al entrar

A diferencia del superusuario, no pasa por el directorio: entra al contexto de su
institución. En la barra lateral, en lugar de «Volver al directorio», ve la leyenda
de su rol.

> Si tuviera membresía en más de una institución entraría a la primera; alternar
> entre instituciones propias sigue siendo una mejora pendiente.

Ve **todo el menú**: los tres grupos completos más Finanzas y Coberturas.

## 3. Funcionalidades

#### ⚙️ SISTEMA *(su responsabilidad principal)*
- **Estructura organizativa**: áreas → subáreas, con su ficha (Datos, Staff, Grupos,
  Sub-áreas). Crea y edita áreas, define **grupos de trabajo** y asigna
  profesionales. Configura **boxes** y **camas**.
- **Administración**: usuarios con acceso a su institución. Crea usuarios, les
  asigna **rol(es)** —cualquiera de los nueve— y **área(s)**, y los activa o
  desactiva. Acá también viven los **permisos financieros**.
- **Flujos**, **Mapa de flujos** y **Formularios**: diseña, valida y publica los
  procesos de su institución, con las mismas capacidades que el configurador.

#### 🗂️ TRABAJO
- Casos, Tablero, Turnos, Internación, Farmacia, Red y Supervisión: puede operar y
  supervisar todo lo de su institución.

#### 🩺 REGISTROS
- Padrón, Historia clínica, Legajo y **Registro de accesos** de su institución.

#### 💲 Finanzas y cobertura
- **Hereda las dieciocho acciones financieras** dentro de su institución, para todas
  las áreas e información sensible: cargar y aprobar gastos, configurar repartos,
  registrar y aprobar dinero, configurar cobros, registrar aceptaciones de copago y
  resolver saldos de cobertura.
- Es **quien otorga** esos permisos a las demás personas, con su área y su alcance
  sensible, desde **Administración → Usuarios → Editar usuario → Permisos
  financieros**.

## 4. Permisos

| Acción | Admin de institución |
|---|---|
| Ver el directorio u otras instituciones | ❌ Sólo la suya |
| Crear o eliminar instituciones | ❌ Sólo el superusuario |
| Editar la ficha de su propia institución | ✅ *(ver nota)* |
| Gestionar estructura, grupos, boxes y camas | ✅ |
| Crear usuarios, asignar roles y áreas | ✅ |
| Otorgar permisos financieros | ✅ |
| Diseñar y publicar flujos y formularios | ✅ |
| Operar casos, filas, turnos, internación, farmacia, traslados | ✅ |
| Ver y cargar historia clínica | ✅ |
| Auditar accesos clínicos de su institución | ✅ |
| Operar Finanzas y cobertura | ✅ Por herencia, sin concesiones explícitas |
| Crear redes sanitarias | ❌ Es `gobierno_plataforma` |

Capacidades: todas menos `gobierno_plataforma`.

## 5. Lo que cambió el 18/09/2026

Antes el admin de institución **sólo heredaba las dos lecturas financieras**
(`ver_costos` y `ver_gastos`); cargar, aprobar y configurar se le otorgaban a mano
como a cualquier otra persona. Desde esa fecha **hereda las dieciocho acciones**.

Si alguien recuerda que «el administrador no aprueba gastos por sí solo», eso dejó de
ser cierto. La decisión está registrada en
[`docs/historico/plans/2026-09-18-finanzas-coberturas-usabilidad-diseno.md`](../historico/plans/2026-09-18-finanzas-coberturas-usabilidad-diseno.md).

## 6. Notas

- **Diferencia con el superusuario:** mismo acceso a las funciones, pero acotado a
  su institución y sin el nivel de plataforma.
- Funcionalmente debería **delegar la operación diaria**: puede operar casos y
  cargar historia clínica, pero su rol es de conducción y configuración.
- Editar la ficha de la propia institución está permitido en el backend; falta la
  acción de interfaz correspondiente. Crear o eliminar instituciones queda sólo para
  el superusuario.
