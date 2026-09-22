# I-Core Salud para quien lo diseña

> Qué pantallas existen, dónde vive la marca, qué reglas hay que respetar y qué
> está sin resolver. Verificado contra la aplicación el **22/09/2026**.

---

## 1. La regla que ordena todo el diseño

El sistema tiene **dos modos visuales que no deben parecerse**:

| | Qué es | Cómo se ve |
|---|---|---|
| **Diseño** | Donde se dibuja el circuito | Lienzo tipo diagrama: canvas con grilla de puntos, nodos arrastrables, flechas, zoom y paneo |
| **Ejecución** | Donde se atiende al paciente | Software de gestión serio: formularios prolijos, tablas, badges de estado, pasos de progreso. **Sin lienzo ni grilla** |

> Si la pantalla de ejecución parece un diagrama, está mal. Si el editor parece un
> formulario lineal, está mal.

Es la decisión de diseño más vieja del producto y sigue vigente.

## 2. Dónde vive la marca

| Qué | Dónde | Se edita |
|---|---|---|
| Manual de marca: identidad, voz y tono, logo, color, tipografía | [`diseño/docs/01-manual-de-marca.md`](../diseño/docs/01-manual-de-marca.md) | Sí |
| Sistema de diseño: tokens y componentes | [`diseño/docs/02-sistema-de-diseno.md`](../diseño/docs/02-sistema-de-diseno.md) | Sí |
| **Los tokens que usa la aplicación** | `frontend/src/styles/tokens.css` | **Sí, es la fuente única** |
| Escalas derivadas | `frontend/src/styles/escalas.js` | No, se genera con `npm run escalas` |
| Tokens en CSS y JSON del entregable | `diseño/docs/tokens.css` · `tokens.json` | Sí |
| Página visual del sistema de diseño | `diseño/Sistema de diseno.dc.html` | Sí |

**Cuidado con una instrucción vieja:** hubo un `theme.js` del que se generaba
`tokens.css`. Ese archivo se borró y ahora es al revés: `tokens.css` es el original
y se edita a mano. Si encontrás un `npm run tokens`, ya no existe.

### Los dos niveles de token, y cuál usar

- **Literales** (`slate-600`, `canvas`, `white`): la escala de la marca. **No cambian
  con el tema.**
- **Semánticos** (`superficie`, `fondo`, `borde`, `texto-suave`…): dicen **qué papel
  cumple** el color, no cómo se ve. **Son los únicos que cambian con el tema**, y son
  los que usa todo lo nuevo.

Tres tokens se desdoblan a propósito, porque cumplen papeles contradictorios: como
**texto** sobre fondo oscuro tienen que ser claros, y como **relleno** detrás de texto
blanco tienen que ser oscuros.

| Para | Token |
|---|---|
| Texto, íconos, bordes | `text-accent`, `text-danger` |
| Relleno de un botón o píldora | `bg-accent-fuerte` + `text-sobre-accent` |

Con un token solo, el número de la fila destacada quedaba en 2,7:1 en tema oscuro.

## 3. Las capturas: cuál es cuál

Hay tres carpetas y sirven para cosas distintas. Es la confusión más común.

| Carpeta | Qué es | Vigencia |
|---|---|---|
| [`captures-app/`](../diseño/docs/captures-app/) | **29 capturas de la aplicación real**, generadas automáticamente | La referencia de cómo se ve hoy. Última corrida: 20/08/2026 |
| [`captures/`](../diseño/docs/captures/) | 17 capturas del **prototipo** original | Junio 2026. Sirve como intención de diseño, no como estado |
| [`captures-manual/`](../diseño/docs/captures-manual/) | 24 capturas tomadas a mano, para material de capacitación | Agosto 2026 |

**Las de `captures-app/` se regeneran solas.** Están definidas en
`frontend/e2e/capturas.spec.js` y salen de recorrer la aplicación con el navegador.
Si cambiás algo visual, se actualizan corriendo esa suite: no hay que volver a
sacarlas a mano.

### Seis pantallas no tienen captura

El recorrido de capturas se escribió antes de que existieran, y **no las incluye**:

- Padrón de pacientes y su ficha
- Finanzas y costos
- Coberturas y copagos
- Portal de financiadores
- Activación de cuenta de un financiador

Agregarlas a `capturas.spec.js` es la forma de que entren al circuito automático.

## 4. Las pantallas que existen hoy

Son 37 rutas. Agrupadas por dónde aparecen en el menú:

### Fuera de la sesión
- **Login** · **Pantalla pública de llamados** (la TV de la sala de espera, entra por token, sin login) · **Activación de cuenta de financiador**

### Entrada
- **Directorio de instituciones** (sólo para plataforma; el resto entra directo a la suya) · **Inicio / Mi trabajo** · **Notificaciones**

### Trabajo
- **Casos** y **Detalle del caso** — la pantalla central del producto · **Bandeja** · **Filas** · **Puesto de atención** · **Tablero** · **Supervisión** · **Turnos programados** · **Internación** · **Farmacia e insumos** · **Red y traslados**

### Registros
- **Padrón de pacientes** y su **ficha administrativa** · **Historia clínica** y su **detalle** · **Legajo profesional** · **Registro de accesos**

### Dinero
- **Finanzas y costos** (siete pestañas: resumen, gastos, gastos mensuales, repartos, costos por atención, pagos y cobros, reportes) · **Coberturas y copagos** (cuatro pestañas)

### Diseño de procesos
- **Flujos** · **Editor de flujos** (la pantalla estrella) · **Mapa de flujos** · **Formularios** y su **constructor**

### Configuración
- **Estructura organizativa** — el área tiene seis secciones, y cada una es una página propia: datos, staff, grupos, boxes, agendas, sub-áreas · **Administración de usuarios**

### Portal del financiador
- Diez secciones: planes, cobertura, aranceles, padrón, consumos externos, autorizaciones, actividad, convenios, usuarios, catálogo común

> **Ojo con `diseño/docs/04-pantallas.md`.** Describe estas pantallas, pero según el
> prototipo de junio: habla de 10 tipos de nodo (hoy son 13), de Bandeja en el menú
> (hoy se opera desde Mi trabajo) y de un panel lateral para la ficha del área (hoy
> cada sección es una página). Úsalo como intención original, no como especificación.

## 5. Quién ve qué

El menú cambia según el rol, y eso afecta cualquier diseño de navegación. La tabla
completa —diez roles contra cada ítem del menú— está en
[`docs/roles/README.md`](roles/README.md), y cada rol tiene su ficha con qué ve al
entrar y qué hace.

Lo mínimo que conviene tener presente:

- **Bandeja y Filas están fuera del menú a propósito.** Son la cola de lo que te toca
  ahora y se operan desde **Mi trabajo**, en Inicio. «Casos» sí está en el menú,
  porque responde otra pregunta: buscar un caso que no es tu tarea pendiente.
- El **administrativo no ve Historia clínica**. Ve el Padrón, que es la ficha
  administrativa. Son dos permisos distintos y la diferencia es deliberada.
- **Finanzas no aparece por rol**, sino por permisos que se otorgan de a uno.

## 6. Reglas que no son negociables

- **Responsive.** Las listas financieras no deben requerir desplazamiento
  horizontal: el texto se acomoda en varias líneas y, cuando falta ancho, cada
  registro se presenta verticalmente conservando toda la información.
- **Tema oscuro.** Todo lo nuevo usa tokens semánticos, que son los que cambian.
- **Contraste AA**, medido en claro y en oscuro. Hay una verificación automática.
- **Movimiento reducido.** Las animaciones se omiten si el dispositivo lo pide.
- **El color nunca es el único portador de información.** En los gráficos
  financieros, la leyenda y los importes acompañan siempre. Rojo no significa error.
- **No inventar colores.** Las escalas de Tailwind están reemplazadas por las de la
  marca: `bg-red-500` directamente no existe. La regla vive en la herramienta.
- **Las variantes usan mapas de clases completas, nunca interpolación.** Tailwind
  escanea el código como texto, así que `` `bg-badge-${tono}` `` no genera nada.
- **Todo listado nuevo pagina de a 10**, no de a 25. La fila de estas pantallas es
  alta —importes, estados, badges, botones— y con veinticinco hay que barrer la
  pantalla entera para encontrar una. Con diez entra sin scrollear y el paginador se
  usa de verdad. Quien necesite más lo elige en «filas por página», y la elección
  viaja en la URL. Hoy lo cumplen finanzas y financiadores; las pantallas anteriores
  siguen en 25 hasta que les toque.

## 7. Qué está sin resolver

Deuda visual conocida, por si aparece en una revisión:

- **`slate400` de la marca no llega a AA** (2,63:1 sobre blanco). Se corrigió en el
  token semántico `texto-tenue`, así que lo migrado cumple. **Cambiar la escala
  literal es una decisión de marca**, y está pendiente.
- **Las categorías de nodo no tienen paleta oscura.** Son unos 30 colores del lienzo
  del editor.
- **El buscador de pacientes se esconde en pantalla angosta**, porque compite con el
  título y la campana. Queda accesible desde Historia clínica, pero la solución buena
  es que se expanda desde un ícono.
- **`04-pantallas.md` y el resto del entregable de diseño describen el prototipo**, no
  la aplicación actual. La marca, los tokens y las capturas sí están vigentes.

## 8. Si querés ver el sistema funcionando

Hay dos entornos locales preparados, con datos ficticios:
[`docs/entornos/README.md`](entornos/README.md). El de demo (puerto 8082) tiene tres
instituciones y 757 casos cargados, así que las pantallas se ven con contenido real
y no vacías.

Para recorrerlo con sentido, el [guion de demo](entornos/guia-demo-comercial.md) pasa
por las pantallas principales en orden.
