# Rol: Configurador

> El que **diseña los procesos**. Vive en el mundo **Diseño** (el lienzo): arma los
> flujos y formularios que después el motor ejecuta. **No opera casos ni ve la
> historia clínica.**
> Técnicamente: usuario con una **membresía de rol `configurador`**.

**Usuario de demo:** `m.diaz@hospital.gob.ar` / `demo1234` (Martín Díaz, Hospital Central)

---

## 1. En una frase

El configurador **dibuja un proceso como diagrama** (pasos, formularios, decisiones,
derivaciones) y lo **publica**; esa misma definición es la que el motor usa para
generar las pantallas que opera el personal. **Nadie programa una pantalla a mano.**

## 2. Qué ve al entrar

Entra directo a su institución (acceso fijo, sin directorio). Su menú muestra
**Inicio** y el grupo **DISEÑO** únicamente — no ve Trabajo, Registros ni Sistema.

> Es el rol más acotado en cuanto a menú, pero el más profundo en su mundo: el
> diseñador es la pantalla más rica del sistema.

---

## 3. Funcionalidades

#### 🟦 Inicio
- Panel de la institución (métricas + accesos). Su acceso rápido principal es **Flujos**.

#### 🎨 DISEÑO *(su mundo)*

**Flujos** *(listado)*
- Tabla de flujos: estado (Publicado / Borrador / Archivado), versión, casos activos,
  última edición. Filtros por estado y área.
- **Crear flujo**: nombre + área → nace una versión **v1 en borrador** con un nodo
  **Inicio**.
- **Abrir en el diseñador**, **duplicar**.

**Diseñador de flujos** *(el lienzo)* — la pantalla central del rol
- **Lienzo** con grilla de puntos, zoom/scroll (mundo "diagrama", distinto del de ejecución).
- **Paleta de 10 nodos**: Inicio · Formulario · Decisión · Acción · Atención ·
  Derivar · Espera de fila · Espera por tiempo · Estado · Fin.
- **Arrastrar** nodos (la posición se guarda) y **conectarlos** con flechas.
- **Panel de propiedades** por nodo, según su tipo:
  - *Formulario* → elegir qué **formulario** pide.
  - *Derivar* → elegir **área de destino** (y opcionalmente otro flujo).
  - *Estado* → qué **estado** aplica al caso.
  - *Espera por tiempo* → duración.
- **Constructor de reglas** en las Decisiones: condición *campo · operador · valor*
  (=, ≠, >, <, contiene) para bifurcar el camino.
- **Validación viva**: botón **Validar** → lista de problemas (errores/avisos):
  flujo sin Inicio/Fin, derivación sin área, decisión con campo inexistente, nodos sin salida.
- **Publicar**: si no hay errores, publica la versión y marca la anterior como
  *reemplazada*. (Con errores, el botón queda deshabilitado.)
- **Versionado**: selector de versiones (v1, v2, …) del flujo.

**Mapa de flujos**
- Vista panorámica de cómo se encadenan los procesos de la institución.

**Formularios** *(constructor)*
- Lista de formularios + **constructor** con **vista previa en vivo** (así lo verá
  el administrativo).
- **Crear formulario** y **agregar campos**: tipo (texto corto/largo, fecha,
  selección única, archivo), requerido, opciones, y **vinculación** a Historia
  clínica / Legajo ciudadano (precarga el dato).

---

## 4. Permisos (resumen)

| Acción | Configurador |
|---|---|
| Diseñar flujos (lienzo) | ✅ |
| Validar y publicar versiones | ✅ |
| Crear formularios y campos | ✅ |
| Ver mapa de flujos | ✅ |
| Operar casos (bandeja, filas) | ❌ |
| Ver / cargar historia clínica | ❌ |
| Gestionar estructura organizativa / usuarios | ❌ |
| Ver otras instituciones | ❌ |

> El configurador **construye el "qué"** (la plantilla del proceso); el
> administrativo **ejecuta el "cómo"** (los casos reales). Dos mundos visuales
> distintos a propósito: Diseño = lienzo; Ejecución = sistema de gestión.

---

### Modo Probar y Reproducir *(implementado)*

- **Probar**: simula un caso recorriendo el flujo **sin crear datos reales**. Abre
  un panel "Modo prueba" que muestra el nodo actual; en los Formularios deja
  cargar valores, evalúa las Decisiones con esos valores, y avanza paso a paso
  hasta el Fin, mostrando el **recorrido** completo. El nodo actual se resalta en
  el lienzo. (Espeja la lógica del motor del backend, en el cliente.)
- **Reproducir**: anima un **token** que viaja por el lienzo siguiendo el camino
  (el de la última simulación, o el camino por defecto si no se simuló).

## 5. Decisiones y notas

- El menú del configurador sale de su **membresía de rol `configurador`** → solo
  habilita el grupo **DISEÑO** (+ Inicio).
- ✅ **Probar y Reproducir implementados** (ver arriba).
