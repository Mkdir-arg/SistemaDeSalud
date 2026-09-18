# Prompt — análisis UI/UX y jerarquía de la pantalla del caso

Copiá todo lo que sigue como prompt.

---

## Tarea

Analizá la **jerarquía de información de la pantalla de detalle del caso** y
proponé una mejora. Es la pantalla que más se usa del sistema: es donde el
administrativo y el profesional trabajan el día entero.

**Primero el análisis y la propuesta. No toques código hasta que apruebe.**

## Qué es esta pantalla

`/casos/:id`, componente `frontend/src/pages/ejecucion/CasoDetalle.jsx` (~1.245
líneas). El panel de cobertura es aparte:
`frontend/src/pages/financiadores/CoberturaCaso.jsx` (~298 líneas).

Hoy tiene nueve bloques, en este orden de arriba hacia abajo:

| # | Bloque | Contenido |
|---|---|---|
| 1 | Encabezado | `Flujo · Paciente` |
| 2 | Barra numerada | Recibido → En proceso → Derivado → Atendido → Cerrado |
| 3 | PASO ACTUAL | Tipo de nodo + nombre |
| 4 | Historia clínica · antecedentes | Alergias, condiciones. Solo lectura. **Condicional por partida doble**: hace falta permiso clínico *y* que el paciente tenga antecedentes cargados |
| 5 | Cobertura del caso | Afiliación, prestaciones del paso, autorizaciones |
| 6 | **El bloque de trabajo** | `FORMULARIO` o `ATENCIÓN`, según el nodo. Campos + «Completar y avanzar» |
| 7 | Datos cargados | Respuestas acumuladas de los pasos anteriores |
| 8 | INFORMACIÓN DEL CASO | Caso, estado, paso actual, flujo, área, responsable, asignado a, ingreso, prioridad |
| 9 | Trazabilidad | Registro de eventos: qué pasó, detalle, quién y cuándo |

## Hipótesis a evaluar

No las tomes como verdad: confirmalas o rebatilas con evidencia de la pantalla.

1. **El encabezado es demasiado débil.** Es el único lugar donde aparecen el
   **nombre del paciente** y **a qué vino**, que son los dos datos que orientan
   todo lo demás. Hoy compite en peso visual con bloques mucho menos importantes.
2. **«Información del caso» debería incluir la cobertura.** Hoy el estado de
   cobertura vive en un bloque propio en el medio, lejos del resto de los datos de
   identificación del caso.
3. **La franja del medio es larga y está cargada de información accesoria**, y
   empuja hacia abajo lo único que la persona vino a hacer. **Lo importante ahí es
   el formulario** (bloque 6): debería ser lo más prominente y lo más rápido de
   alcanzar.

## Lo que hay que entender antes de proponer

**Dos ejes independientes deciden qué ve cada persona:**

1. **Si puede ejecutar el paso** → lo definen los **grupos del nodo** actual. El
   campo *Responsable* del bloque 8 los muestra. Quien no integra el grupo ve el
   bloque 6 reemplazado por un texto: *«Este paso lo realiza X. No integrás ese
   grupo, así que no podés ejecutarlo»*, sin botón.
2. **Si puede ver datos clínicos** → lo define la capacidad del rol. Sin ella, el
   bloque 4 no aparece en absoluto.

Los dos se combinan: hay usuarios que ven los antecedentes pero no pueden avanzar
el caso, y al revés.

**Y hay un tercer factor que mueve el layout:** el bloque 4 solo se renderiza si
el paciente tiene antecedentes cargados. El mismo usuario, en dos casos seguidos,
ve la pantalla con y sin ese bloque. Comparalo en `/casos/679` (Julieta Díaz,
tiene «Insuficiencia cardíaca») contra `/casos/670` (María Rodríguez, sin
antecedentes), los dos con `guardia.med@`. Cualquier jerarquía que dependa de que
ese bloque esté presente es frágil.

**El bloque 6 es el único que cambia según quién sos.** Todo el resto se ve igual.
Cualquier propuesta tiene que funcionar en las cuatro combinaciones, incluida la
peor: alguien que no puede ejecutar el paso y no ve datos clínicos, para quien la
pantalla es solo consulta.

## Dónde mirarlo funcionando

La aplicación está corriendo en <http://localhost:8082>.

| Caso | Usuario | Contraseña | Qué muestra |
|---|---|---|---|
| `/casos/679` | `guardia.adm@hospital.gob.ar` | `demo1234` | Paso *Admisión administrativa*, **puede** ejecutarlo, **no** ve antecedentes |
| `/casos/679` | `guardia.med@hospital.gob.ar` | `demo1234` | El mismo caso: **no** puede ejecutarlo, **sí** ve antecedentes |
| `/casos/670` | `guardia.med@hospital.gob.ar` | `demo1234` | Caso mitad de camino: trazabilidad larga, «Datos cargados» con varios pasos previos. Y el bloque 4 **no aparece**, porque esta paciente no tiene antecedentes |
| `/casos/196` | `paula.benitez@losaromos.test` | `LosAromos2026!` | Panel de cobertura activo, con afiliación y evaluación de importes |
| `/casos/753` | `int.adm@hospital.gob.ar` | `demo1234` | Nodo de tipo *Asignar cama* (el bloque 6 no siempre es un formulario) |

Mirá los cinco antes de proponer nada. Varían mucho en densidad, y una jerarquía
que funciona en el más vacío se rompe en el más cargado.

**Ojo con `/casos/196`:** ese flujo lo generó un seed con nodos **sin grupos**, así
que dice *Responsable: Abierto a todos* y no sirve para evaluar la diferencia de
roles. Para eso usá los casos de Hospital Central.

## Restricciones del código — no negociables

Están en `docs/FUNDACION-FRONTEND.md`, sección «Reglas que ya costaron un bug».
Las que más te van a afectar:

- **Anchos y altos con valor explícito: `max-w-[28rem]`, nunca `max-w-md`.** Los
  tokens de espaciado se llaman `xs/sm/md/lg/xl/xxl` y colisionan con la escala de
  contenedores de Tailwind: `max-w-md` significa **12px**, no 448px. Genera CSS
  válido, así que no se detecta revisando si la clase existe. Ya rompió el login y
  todos los estados vacíos de la app, y la semana pasada rompió otra pantalla.
- **No inventes colores ni tamaños.** Las escalas están reemplazadas con
  `*: initial` en `frontend/src/styles/tokens.css`: un nombre que no exista es un
  no-op **silencioso**. Usá solo tokens del sistema.
- **Las variantes usan mapas de clases completas, nunca interpolación.**
  `` `bg-badge-${tono}-bg` `` no genera nada.
- **La paleta `nodo-*` es para bordes y rellenos, nunca para texto** (no llega a
  contraste AA).
- **El estado de la vista va en la URL; las preferencias en `localStorage`.**
- Tiene que funcionar en **tema claro y oscuro** y en **mobile**. La app es
  responsive y se usa en pantallas chicas.
- Reutilizá las piezas existentes (`components/ui/`, `lib/cn.js`,
  `lib/media.js`). No agregues dependencias.

## Lo que quiero de vuelta

**Paso 1 — Análisis.** Para cada uno de los nueve bloques: qué pregunta responde,
quién lo necesita, en qué momento de la tarea, y cuánto peso visual tiene hoy
versus el que merece. Señalá concretamente qué compite con qué. Si alguna de mis
tres hipótesis está mal, decilo y explicá por qué.

**Paso 2 — Propuesta.** Una jerarquía nueva, con el porqué de cada movimiento.
Incluí un boceto de la estructura (ASCII o descripción de layout) para escritorio
y para mobile. Si proponés agrupar, colapsar o mover algo, decí qué se pierde:
todo movimiento tiene un costo y quiero verlo escrito.

**Paso 3 — Riesgos.** Qué se rompe o se degrada con tu propuesta, y en cuál de las
cuatro combinaciones de permisos. Qué caso de los cinco de arriba es el que peor
la pasa.

Recién después de que apruebe, implementás.

## Cómo se valida

- Abrí los cinco casos de la tabla, con los dos temas, en escritorio y en mobile.
- `cd frontend && npm run build && npm run auditar` — el auditor reporta clases
  huérfanas y, aparte, **COLISIONES**. Tiene que quedar limpio.
- No declares nada verificado que no hayas corrido. Si algo no se pudo probar,
  decilo.

## Lo que NO quiero

- Rediseño visual: no toques la paleta, la tipografía ni el estilo de los
  componentes. Esto es **jerarquía y layout**, no maquillaje.
- Refactor de `CasoDetalle.jsx` por prolijidad. Cambiá lo que la jerarquía
  necesite y nada más.
- Cambios en el backend o en los contratos de la API.
- Suposiciones sobre qué hace cada bloque: está todo corriendo, andá a mirarlo.
