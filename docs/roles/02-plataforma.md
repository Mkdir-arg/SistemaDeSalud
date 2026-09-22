# Rol: Autoridad estatal / plataforma

> Gobierna la red: da de alta efectores, arma redes sanitarias y habilita
> organizaciones de financiadores. **No atiende pacientes y no ve historia clínica.**
> Técnicamente: membresía con rol `plataforma`. No es `is_superuser`.

**Usuario de demo:** `plataforma@salud.local` / `demo1234`

---

## 1. En una frase

Es el nivel estatal del sistema: existe para que la red tenga quien cree los
establecimientos, los vincule entre sí y responda por la trazabilidad, sin que eso
implique poder entrar a la historia clínica de nadie.

## 2. Qué ve al entrar

Como tiene `gobierno_plataforma`, entra al **Directorio de instituciones**, no a una
institución concreta. Desde ahí elige dónde trabajar.

Su menú es corto: **Registro de accesos** y **Portal de financiadores**. No ve
Estructura, Administración, Flujos, Casos, Padrón ni Historia clínica.

## 3. Funcionalidades

#### Directorio de instituciones
- Alta, edición y baja lógica de efectores, con tipo, CUIT, dirección y coordenadas.
- No se pueden borrar: `AccesoClinico.institucion` y `Flujo.institucion` son
  `PROTECT` a propósito. La auditoría clínica no se borra, así que la única baja es
  la de estado.

#### Redes sanitarias
- Crear redes y definir qué establecimiento puede derivar a cuál.
- Es lo que habilita el módulo de traslados: sin red, el circuito existe y no anda.

#### Directorio estatal de usuarios
- Crear los usuarios y las membresías necesarias para dar de alta una institución.
- Asignar los roles estatales (`plataforma` y `auditor`).

#### Registro de accesos
- Consulta con **alcance estatal**: ve los accesos clínicos de todas las
  instituciones, no sólo de una.

#### Portal de financiadores
- Da de alta organizaciones nuevas y administra el **catálogo común de
  prestaciones**, que es lo que permite reconocer una misma prestación entre
  hospitales y financiadores.

## 4. Permisos

| Acción | Plataforma |
|---|---|
| Crear, editar y desactivar instituciones | ✅ |
| Crear redes sanitarias | ✅ |
| Administrar el catálogo común de prestaciones | ✅ |
| Dar de alta organizaciones de financiadores | ✅ |
| Auditar accesos clínicos, con alcance estatal | ✅ |
| Consultar reportes agregados | ✅ |
| Operar casos, turnos, filas, internación, farmacia | ❌ |
| Ver historia clínica o padrón | ❌ |
| Diseñar flujos o formularios | ❌ |
| Operar Finanzas | ❌ salvo concesiones explícitas |

Capacidades exactas: `gobierno_plataforma`, `reportes` y `auditoria`.

## 5. Notas

- **No equivale al superusuario.** El superusuario es un usuario técnico que
  atraviesa todo por diseño; plataforma es un rol funcional con un alcance definido.
  Ver [`01-super-admin.md`](01-super-admin.md).
- `gobierno_plataforma` es la única capacidad **global**: no se acota a un hospital.
- Resolver autorizaciones de un financiador **no le corresponde por ser plataforma**:
  eso exige una designación expresa dentro de esa organización.
