# Fundación del frontend

> Cómo está construido el frontend y las reglas que hay que respetar al tocarlo.
> Documento vivo. Creado: **2026-08-01** · Fase 1 cerrada: **2026-08-02**.

Contexto y hoja de ruta en [`PLAN-DESARROLLO.md`](PLAN-DESARROLLO.md).

## El estado

Todas las pantallas están migradas **menos una**: el editor de flujos
([`FlujoEditor.jsx`](../frontend/src/pages/diseno/FlujoEditor.jsx)), que se rehace
entero en la Fase 2 y por eso no se tocó.

| | Antes | Ahora |
|---|---|---|
| Estilos | `style={{}}` inline leyendo `theme.js` | clases de Tailwind sobre tokens |
| Datos | `fetch` a mano en cada pantalla | TanStack Query (`useLista`, `useAccion`) |
| Paginación | ninguna (mostraba los primeros 25 y descartaba el resto) | `TablaRecurso` |
| Filtros y búsqueda | `.filter()` sobre lo ya traído | parámetros al servidor |
| Tema oscuro | no | sí |
| Responsive | no | sí |
| Contraste AA | sin verificar | medido en 12 pantallas × 2 temas |

`theme.js` **sigue existiendo** y no se borra todavía: es lo que consume el editor
de flujos, y además es la fuente del generador de tokens. Desaparece cuando la
Fase 2 rehaga el editor. Lo que sí se separó es el vocabulario del negocio
(estados, nombres de nodo), que se fue a
[`lib/dominio.js`](../frontend/src/lib/dominio.js): eso sobrevive al sistema de
diseño y no tenía por qué morir con él.

La excepción deliberada sigue siendo la pantalla de llamados (ver más abajo).

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
2. **El preflight de Tailwind está activo desde el cierre de la Fase 1.** Durante
   la migración estuvo apagado a propósito —con ~1.100 estilos inline asumiendo el
   reset propio, encenderlo antes habría cambiado las 30 pantallas de golpe y sin
   red— y lo suplía un *mini-preflight* con las dos reglas que habían causado bugs
   reales: las viñetas de `<ul>` y el fondo nativo `buttonface` de los `<button>`
   (que en tema oscuro pintaba cajas grises). Ese parche ya se borró. Lo único que
   se conserva encima del preflight es `cursor: pointer` en los botones: el
   preflight sigue el default del navegador, y acá hay filas y tarjetas enteras
   que son botones.
3. **El estado de una vista va en la URL; las preferencias en localStorage.**
   Página, orden y filtros en la URL, para que una vista filtrada se pueda
   compartir por link y sobreviva un F5. La densidad y el tema en localStorage:
   son de la persona, no de la vista.
4. **Toda lista pagina, y filtra en el SERVIDOR.** Nunca `api.get()` directo a un
   listado: `useLista` o `TablaRecurso`. Y nunca `.filter()` sobre lo que trajo la
   consulta: con la API paginando de a 25, filtrar en el cliente busca dentro de
   esas 25 y el resto no existe. Ya apareció en cinco pantallas —Casos,
   Supervisión, Bandejas, Directorio y la Fila—, cada una necesitó abrir el filtro
   en el backend. Si falta el parámetro, se agrega a `filter_fields`; no se
   compensa en el cliente.
5. **La paleta de nodos (`nodo-*`) es para bordes y rellenos, nunca para texto.**
   No llega al contraste AA como texto y ya rompió tres veces. Como fondo con su
   `tint` y como ícono con su `sol`, funciona y además tiene variante oscura
   resuelta con `color-mix`.
6. **Antes de dar por buena una clase, correr el auditor.** Las escalas de color,
   tipografía, radio y sombra están reemplazadas (`*: initial`), así que un nombre
   que no exista es un no-op **silencioso**: no rompe el build ni avisa. Pasó con
   `text-2xl` y `text-3xl`, y cinco pantallas mostraron sus cifras al tamaño de una
   etiqueta durante días.

   ```bash
   npm run build && npm run auditar
   ```

7. **Los anchos y altos van con valor explícito: `max-w-[28rem]`, nunca `max-w-md`.**
   Los tokens de espaciado se llaman `xs/sm/md/lg/xl/xxl` y esos mismos nombres
   existen en la escala de contenedores de Tailwind. En `max-w-md` gana el de
   espaciado: la clase significa **12px**, no 448px.

   Es peor que una clase huérfana porque genera CSS perfectamente válido —
   revisar «¿existe la clase?» no lo detecta. Estuvo en el panel del login y en
   **todos** los estados vacíos y de error de la app, con el texto de detalle en
   una columna de 12px, y sobrevivió a varias revisiones visuales. El auditor
   ahora lo marca aparte, como COLISIONES.

   Para espaciado (`p-lg`, `gap-md`, `px-xl`) los nombres se usan igual: ahí no
   hay con qué colisionar.

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

# 2. La suite (66 tests)
cd frontend && npm run e2e        # npm run e2e:ui para verla correr
```

`e2e/setup.js` chequea antes de empezar que los dos servidores respondan, que la
demo tenga volumen y que quede cola para llamar; si no, falla con el comando de
siembra que corresponda. Sin eso, un backend caído se manifiesta como veinte tests
rojos por «timeout esperando un selector».

| Archivo | Cubre |
|---|---|
| `tabla.spec.js` | Paginación real, orden, filtros, búsqueda, densidad, sin desborde |
| `fila.spec.js` | El recorrido operativo de la guardia: la cola ordena urgentes primero y llamar saca al paciente de la fila |
| `shell.spec.js` | Colapso en escritorio, cajón en móvil (abrir, Escape, cierre al navegar) |
| `tema.spec.js` | Conmutador, persistencia sin destello y **contraste AA medido** en ambos temas |
| `sesion.spec.js` | Que un tropiezo del servidor no cierre la sesión, y un solo refresh ante varios 401 a la vez |
| `directorio.spec.js` | Directorio de plataforma: búsqueda contra el servidor, total real, vista en la URL |

**Los tests corren en serie** (`workers: 1`): operan sobre la misma base y llamar a
un paciente cambia la fila que ve otro test.

**La suite no es idempotente.** `fila.spec.js` llama pacientes de verdad contra el
motor real, así que cada corrida completa gasta un lugar de la fila (una siembra
fresca deja 7). Es deliberado —simular el llamado no probaría nada—, y por eso el
chequeo previo mide la cola y avisa cuándo hay que volver a sembrar.

### Esperar por señales, no por reloj

Nada de `waitForTimeout` antes de mirar o medir una pantalla: alcanza en una
máquina descansada y no alcanza bajo carga, y entonces el test falla por algo que
no tiene que ver con lo que prueba. Costó media jornada de diagnóstico: el test de
contraste medía la pantalla de login y reportaba 67 fallos inexistentes, en rutas
distintas cada corrida. Se usa `esperarPantalla(page)` de `apoyo.js`, que espera la
barra lateral y que no quede ningún `role="status"` cargando.

Y si un estado depende de los datos —«no hay nadie llamado», por ejemplo—, se
**fuerza** con `page.route` en vez de esperar a que la siembra caiga de ese lado.
Ese estado de la pantalla de llamados tenía dos textos por debajo del contraste
mínimo y el test sólo los veía cuando la fila quedaba casualmente vacía.

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

Ojo con el escalado en `vw`: un texto de `1.4vw` mide 27px en una TV de 1920 y 19px
en un monitor de 1366. Cruzando los 24px deja de contar como «texto grande» para
WCAG y el mínimo salta de 3:1 a 4.5:1. Los colores de esta pantalla tienen que
cumplir **4.5:1**, no el mínimo del televisor más grande.

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
