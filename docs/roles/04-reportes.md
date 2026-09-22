# Rol: Reportes / solo lectura

> Pensado para consulta pasiva de indicadores agregados no nominales.
> **Hoy casi no tiene dónde usarse.**
> Técnicamente: membresía con rol `reportes`.

**Usuario de demo:** `reportes@salud.local` / `demo1234`

---

## 1. En una frase

Es el rol para que alguien de gestión sanitaria pueda mirar cómo va la red sin
acceder a datos de pacientes ni operar procesos.

## 2. Estado real

**La capacidad existe; las pantallas, no.** Entrar con este usuario muestra una
aplicación prácticamente vacía. No es un defecto de configuración: todavía no se
construyeron las pantallas de indicadores agregados que justifican el rol.

Conviene saberlo antes de mostrarlo en una demo.

## 3. Qué habilita hoy

- La capacidad `reportes`, que los recursos pueden exigir para una lectura agregada.
- Nada más. No ve Estructura, Administración, Flujos, Casos, Padrón, Historia
  clínica, Internación, Farmacia, Red ni el Registro de accesos.

## 4. Permisos

| Acción | Reportes |
|---|---|
| Consultar reportes agregados no nominales, cuando existan | ✅ |
| Operar casos, turnos, filas, internación, farmacia, red | ❌ |
| Ver historia clínica o padrón | ❌ |
| Auditar accesos clínicos | ❌ |
| Administrar instituciones, usuarios o estructura | ❌ |

Capacidad exacta: sólo `reportes`.

## 5. La regla que hay que respetar al construirle pantallas

**Un reporte que muestre pacientes, historia o profesionales identificables necesita
una capacidad más específica.** `reportes` habilita agregados, no datos nominales.
Si una pantalla futura necesita mostrar nombres, no alcanza con este rol.

## 6. Qué falta

- Pantallas de indicadores por establecimiento, región sanitaria y provincia.
- Definir qué indicadores exige el reporte estatal.

Está listado como pendiente en [`ESTADO-DEL-PROYECTO.md`](../ESTADO-DEL-PROYECTO.md) §5.
