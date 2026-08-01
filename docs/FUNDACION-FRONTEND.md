# Fundación del frontend

> Cómo está construido el frontend después de la Fase 0, y las reglas que hay que
> respetar al migrar las pantallas que faltan. Documento vivo.
> Creado: **2026-08-01**.

Contexto y hoja de ruta en [`PLAN-DESARROLLO.md`](PLAN-DESARROLLO.md).

## El estado: dos capas conviviendo

La migración va por pantalla, así que durante la Fase 1 conviven:

| | Capa vieja | Capa nueva |
|---|---|---|
| Estilos | `style={{}}` inline leyendo `theme.js` | clases de Tailwind sobre tokens |
| Datos | `fetch` a mano en cada pantalla | TanStack Query (`useLista`, `useAccion`) |
| Paginación | ninguna (mostraba los primeros 25 y descartaba el resto) | `TablaRecurso` |
| Tema oscuro | no | sí |
| Responsive | no | sí |

**Pantallas ya migradas:** Fila de espera (piloto), Casos, y el Shell.
Las otras ~27 siguen en la capa vieja y funcionan igual que antes.

---

## Tokens

`src/styles/tokens.css` **se genera** desde `src/theme.js` con `npm run tokens`.
No se edita a mano. Mientras convivan las dos capas, dos listas de colores
mantenidas por separado divergen sin que nadie se entere.

Hay dos niveles y hay que usar el correcto:

- **Literales** (`slate-600`, `canvas`, `white`): la escala de la marca. **No
  cambian con el tema.** Los usan los estilos inline que faltan migrar.
- **Semánticos** (`superficie`, `fondo`, `borde`, `texto-suave`…): dicen qué papel
  cumple el color, no cómo se ve. **Son los únicos que cambian con el tema.**
  Todo código nuevo usa estos.

```jsx
<div className="bg-superficie border-borde text-texto-suave">  {/* sí */}
<div className="bg-white border-border text-slate-600">        {/* no */}
```

### Los tres tokens que se desdoblan

`accent`, `danger` y el texto encima de ellos cumplen papeles contradictorios: como
**texto** sobre una superficie oscura tienen que ser claros, y como **relleno**
detrás de texto blanco tienen que ser oscuros. Por eso:

| Para | Token |
|---|---|
| Texto, iconos, bordes | `text-accent`, `text-danger` |
| Relleno de un botón o píldora | `bg-accent-fuerte` + `text-sobre-accent` |

Con un solo token, el número de la fila destacada quedaba en 2,7:1 en oscuro.

---

## Reglas que ya costaron un bug

1. **Las variantes usan mapas de clases completas, nunca interpolación.** Tailwind
   escanea el código como texto: `` `bg-badge-${tono}-bg` `` no genera nada. Ver
   `BADGE_TONO` en [`ui.jsx`](../frontend/src/components/ui.jsx).
2. **No está el preflight de Tailwind.** Su reset cambiaría de golpe las pantallas
   que todavía dependen del reset propio. En su lugar hay un *mini-preflight* en
   [`index.css`](../frontend/src/index.css) con el motivo de cada regla escrito al
   lado. Se agregó por dos bugs reales: las viñetas de `<ul>` y el fondo nativo
   `buttonface` de los `<button>` (que en tema oscuro pintaba cajas grises).
3. **El estado de una vista va en la URL; las preferencias en localStorage.**
   Página, orden y filtros en la URL, para que una vista filtrada se pueda
   compartir por link y sobreviva un F5. La densidad y el tema en localStorage:
   son de la persona, no de la vista.
4. **Toda lista pagina.** Nunca `api.get()` directo a un listado: `useLista` o
   `TablaRecurso`. El fallo original era exactamente ese.

---

## Piezas disponibles

| Pieza | Para qué |
|---|---|
| `api/queries.js` | `useLista` (listas paginadas), `useDetalle`, `useAccion` (mutación que invalida las listas) |
| `components/ui/tabla.jsx` | `TablaRecurso` (tabla conectada a un recurso) y `DataTable` (presentacional) |
| `components/ui/filtros.jsx` | `Buscador` (con retardo), `FiltroSelect`, `LimpiarFiltros`, `useFiltroUrl` |
| `components/ui/estados.jsx` | `Skeleton`, `SkeletonTabla`, `EstadoVacio`, `EstadoError` |
| `components/ui/toast.jsx` | `useToast()` → `.ok()`, `.error()`, `.deError(e)` |
| `lib/cn.js` | Combina clases resolviendo conflictos de Tailwind |
| `lib/media.js` | `useEsEscritorio()` para cuando el ancho cambia la *estructura*, no el estilo |
| `lib/tema.js` | `useTema()` |

---

## Cómo migrar una pantalla

1. Cambiar el `fetch` a mano por `useLista` / `useDetalle`; las acciones por `useAccion`.
2. Si lista datos, usar `TablaRecurso`. Sin excepciones: la paginación no es opcional.
3. Reemplazar los `style={{}}` por clases con tokens **semánticos**.
4. Estados de carga, vacío y error con los componentes de `estados.jsx` (nunca un
   spinner que borra la pantalla, nunca un error sin reintento).
5. Que funcione a 1440, 1024 y 390 sin desborde horizontal.
6. Feedback de las acciones con `useToast`.
7. **Agregar la ruta a `PANTALLAS` en [`e2e/tema.spec.js`](../frontend/e2e/tema.spec.js)**
   — es lo que la pone bajo control de contraste. Sin ese paso la pantalla no está
   terminada.

---

## La suite end-to-end

Es la red que hace que migrar 27 pantallas no sea a ciegas.

```bash
# 1. Datos y servidores
cd backend  && python manage.py seed_volumen --rehacer && python manage.py runserver
cd frontend && npm run dev

# 2. La suite (23 tests)
cd frontend && npm run e2e        # npm run e2e:ui para verla correr
```

`e2e/setup.js` chequea antes de empezar que los dos servidores respondan y que la
demo tenga volumen, y si no falla con instrucciones. Sin eso, un backend caído se
manifiesta como veinte tests rojos por «timeout esperando un selector».

| Archivo | Cubre |
|---|---|
| `tabla.spec.js` | Paginación real, orden, filtros, búsqueda, densidad, sin desborde |
| `fila.spec.js` | El recorrido operativo de la guardia: la cola ordena urgentes primero y llamar saca al paciente de la fila |
| `shell.spec.js` | Colapso en escritorio, cajón en móvil (abrir, Escape, cierre al navegar) |
| `tema.spec.js` | Conmutador, persistencia sin destello y **contraste AA medido** en ambos temas |

**Los tests corren en serie** (`workers: 1`): operan sobre la misma base y llamar a
un paciente cambia la fila que ve otro test.

El contraste se **mide** —se recorre todo el texto visible y se calcula la razón
real contra su fondo efectivo— en vez de revisarse en capturas. Es requisito de
pliego en licitación pública: conviene que sea un test que falla y no algo que
alguien tiene que acordarse de mirar.

---

## La única excepción: la pantalla de llamados

[`PantallaLlamados.jsx`](../frontend/src/pages/PantallaLlamados.jsx) **no** usa
Tailwind ni los tokens, y es deliberado:

- **No participa del tema.** Es un cartel público en una sala de espera, con
  identidad propia de turnero. Que cambie a oscuro porque un administrativo tocó
  un botón en otra pantalla sería un error.
- **Su tipografía se mide en `vw`/`vh`**, para leerse igual en un monitor de 24"
  y en una TV de 55". Eso no son breakpoints: es escalado continuo, y escribirlo
  con clases arbitrarias (`text-[4.4vw]`) sería el mismo estilo inline con más
  ruido.
- **No comparte un solo componente** con el resto de la app.

Lo que sí sigue las reglas: la capa de datos, la accesibilidad y **el contraste**,
que se mide igual —es la pantalla que más lejos se lee, así que es donde menos se
puede fallar.

## Deuda conocida

- **`slate400` de la marca no llega a AA** (2,63:1 sobre blanco) y con ese gris
  están los rótulos y subtítulos de las pantallas sin migrar. Se corrigió en el
  token semántico `texto-tenue`, así que las migradas cumplen; el resto converge a
  medida que se migran. Cambiar la escala literal es una decisión de marca.
- **Las categorías de nodo no tienen paleta oscura.** Ese lienzo se rehace entero
  en la Fase 2 y elegir ahora 30 colores que van a cambiar es trabajo tirado.
- **El buscador de pacientes se esconde en pantalla angosta.** Compite con el
  título y la campana. Queda accesible desde Historia clínica, pero la solución
  buena es que se expanda desde un icono.
