// Tokens del sistema de diseño de Cauce.
// Fuente: "Sistema de diseno.dc.html". No inventar colores: usar estos.

export const color = {
  // Marca · Indigo
  accent: "#3949C0",
  accentHover: "#2D3A9E",
  accent50: "#ECEEFB",
  accent100: "#C7CDF2",

  // Neutros
  ink: "#14161C",
  slate900: "#1F2430",
  slate700: "#344054",
  slate600: "#475467",
  slate500: "#667085",
  slate400: "#98A0AE",
  border: "#E7E9EE",
  divider: "#EEF0F3",
  canvas: "#F4F5F7",
  subtle: "#FAFBFC",
  white: "#FFFFFF",
  // Borde de controles de formulario (inputs/selects), según el componente del manual.
  inputBorder: "#E2E5EA",
  // Acciones destructivas (rojo del estado "Error").
  danger: "#B42318",
};

// --------------------------------------------------------------------------- //
// Capa semántica
// --------------------------------------------------------------------------- //
// La paleta de arriba es LITERAL: dice cómo se ve un color, no qué papel cumple.
// Eso alcanza mientras haya un solo tema, pero rompe en modo oscuro: `bg-white`
// tendría que valer gris oscuro, y un token llamado «white» que es negro es una
// trampa para el que venga después.
//
// Los componentes migrados usan ESTOS nombres. El tema oscuro sólo redefine esta
// capa; la literal queda intacta para los estilos inline que faltan migrar (que
// no tienen modo oscuro, y está bien: adoptarlo es parte de migrar cada pantalla).
export const semantico = {
  fondo: color.canvas, // lienzo de la página
  superficie: color.white, // tarjetas, paneles, filas
  superficie2: color.subtle, // encabezados de tabla, zonas hundidas
  borde: color.border,
  division: color.divider, // separadores internos, más suaves que el borde
  campoBorde: color.inputBorder,
  // Seis niveles de texto, uno por cada neutro de la paleta literal. El mapeo es
  // 1:1 a propósito: migrar un componente de `text-slate-600` a `text-texto-suave`
  // no debe cambiar un solo píxel en modo claro.
  // El acento tiene DOS papeles y no puede resolverlos un solo color: como texto
  // sobre una superficie necesita ser claro en tema oscuro, y como relleno detrás
  // de texto blanco necesita ser oscuro. Con un único token, en oscuro el «1» de
  // la fila destacada quedaba en 2,7:1.
  accentFuerte: color.accent, // relleno de botones y píldoras
  sobreAccent: color.white, // texto encima de ese relleno
  dangerFuerte: color.danger, // mismo desdoblamiento para el rojo: contador de
  sobreDanger: color.white, // no leídas, botones destructivos
  texto: color.ink, // títulos y cifras
  textoFuerte: color.slate900,
  textoMedio: color.slate700, // contenido principal de una fila
  textoSuave: color.slate600,
  textoDebil: color.slate500, // metadatos, texto de apoyo
  // NO es `slate400`. Medido: #98A0AE sobre blanco da 2,63:1, muy por debajo del
  // 4,5:1 que pide WCAG AA para texto chico — y con ese gris están puestos los
  // rótulos de columna, los subtítulos y los placeholders de todo el sistema.
  // Es deuda del diseño original, no de la migración.
  //
  // Se corrige acá, en el token semántico, y no en `color.slate400`: así las
  // pantallas migradas cumplen AA sin alterar la escala literal de la marca ni
  // las 17 capturas de referencia. A medida que se migren pantallas, el sistema
  // converge solo. Cambiar `slate400` de raíz es una decisión de marca.
  // 4,7:1 sobre blanco pero 4,3:1 sobre el fondo de página (`fondo` es gris, no
  // blanco). Se calibra contra el fondo, que es el peor caso.
  textoTenue: "#626A7B", // rótulos, placeholders, deshabilitado
};

// Tema oscuro. Valores elegidos a mano, no derivados: invertir la luminosidad de
// una paleta clínica da grises azulados sucios y tintes de badge que vibran.
// Reglas seguidas: superficies levemente más claras que el fondo (no al revés),
// índigo de marca aclarado —#3949C0 sobre fondo oscuro no llega a contraste AA—
// y tintes de badge oscuros con el texto claro, nunca el pastel del tema claro.
export const oscuro = {
  fondo: "#0E1219",
  superficie: "#171C26",
  superficie2: "#1E242F",
  borde: "#2A313F",
  division: "#232A36",
  campoBorde: "#333B4B",
  texto: "#E7EAF1",
  textoFuerte: "#F2F4F8",
  textoMedio: "#C6CDDA",
  textoSuave: "#B4BCCB",
  textoDebil: "#98A1B2",
  // #7B8496 daba 4,14:1 sobre `superficie2` — justo por debajo de AA. Medido, no
  // estimado: los rótulos de columna son texto chico y tienen que pasar.
  textoTenue: "#949DAE",
  // Marca
  accent: "#8B97F0", // como TEXTO sobre superficie oscura
  accentHover: "#A2ACF5",
  accent50: "#1D2440",
  accent100: "#2B3560",
  accentFuerte: "#4A57C8", // como RELLENO, para que el blanco encima llegue a AA
  sobreAccent: "#FFFFFF",
  danger: "#F0958C", // como TEXTO
  dangerFuerte: "#B4453C", // como RELLENO (blanco encima llega a 5,5:1)
  sobreDanger: "#FFFFFF",
};

// Badges en oscuro: fondo apagado + texto claro (el pastel del tema claro
// deslumbra sobre negro).
export const badgeToneOscuro = {
  neutral: { bg: "#252B37", fg: "#B4BCCB" },
  info: { bg: "#1D2745", fg: "#9FB2F2" },
  amber: { bg: "#382C18", fg: "#E3B573" },
  green: { bg: "#14301E", fg: "#6ED79A" },
  gray: { bg: "#222732", fg: "#8B94A5" }, // #828B9C daba 4,36:1
  error: { bg: "#3A1D1B", fg: "#F0958C" },
};

export const font = {
  sans: "Inter, system-ui, sans-serif",
  mono: "'JetBrains Mono', monospace",
  // Tipografía de marca (wordmark I-Core y títulos destacados).
  display: "Manrope, Inter, system-ui, sans-serif",
};

// Escala tipográfica discreta. Reemplaza los ~14 fontSize sueltos (con decimales
// .5 imperceptibles) por 7 pasos nombrados. Un solo lugar para ajustar tamaños.
export const type = {
  micro: 10, // kickers de mayúscula, captions mínimos
  xs: 11, // ayudas, metadatos
  sm: 12, // labels, texto secundario denso
  base: 13, // texto de cuerpo y controles compactos
  md: 14, // texto de controles y títulos de fila
  lg: 16, // títulos de sección / modal
  xl: 17, // título de pantalla
  xxl: 20, // título grande de detalle

  // Cifras: los números que SON el contenido de una tarjeta (KPIs, contadores),
  // no texto. Son un rol aparte, no una continuación de la escala de texto.
  //
  // Faltaban, y como las escalas de Tailwind están reemplazadas por estas,
  // escribir `text-2xl` o `text-3xl` no generaba ninguna clase: el número
  // quedaba del mismo tamaño que su etiqueta, en silencio. Los pasos de abajo
  // son los tamaños que el diseño original tenía en línea.
  cifra: 22,
  cifraLg: 26,
  cifraXl: 30,
};

// Espaciado en múltiplos de 4 (grilla base). Colapsa los enteros sueltos
// (7/9/11…) a la grilla para un ritmo coherente.
export const space = { xs: 4, sm: 8, md: 12, lg: 16, xl: 20, xxl: 24 };

// Radios de borde. Controles → md; superficies-tarjeta → lg; píldoras → pill.
export const radius = { sm: 7, md: 9, lg: 14, pill: 999 };

// Elevación. Un solo set de sombras en vez de rgba(16,24,40,…) escritas a mano.
export const shadow = {
  card: "0 1px 3px rgba(16,24,40,.07)",
  float: "0 8px 20px rgba(16,24,40,.14)",
  dropdown: "0 12px 32px rgba(16,24,40,.16)",
  modal: "0 18px 50px rgba(16,24,40,.28)",
};

// Tono → estilos de badge de estado (bg / fg). Mapea los estados semánticos.
// Tono → estilos de badge de estado (bg / fg). Mapea los estados semánticos.
//
// Dos textos se oscurecieron respecto del diseño original porque no llegaban al
// contraste AA sobre su propio fondo, medido: el ámbar daba 3,91:1 y el gris
// 2,57:1, con 4,5:1 requerido para texto chico. Son los estados «En espera» y
// «Cerrado», que aparecen en casi toda tabla del sistema.
export const badgeTone = {
  neutral: { bg: "#EEF0F3", fg: "#475467" }, // Recibido / Borrador — 6,7:1
  info: { bg: "#E8EEFB", fg: "#2D3A9E" }, // En evaluación
  amber: { bg: "#FBF0DD", fg: "#90590D" }, // Derivado / En espera — era #A96A12 (3,91:1)
  green: { bg: "#E6F5EC", fg: "#1B7A4E" }, // Publicado / Atendido — 4,7:1
  gray: { bg: "#F0F1F3", fg: "#5F6879" }, // Cerrado / Archivado — era #9098A6 (2,57:1)
  error: { bg: "#FCEBEB", fg: "#B42318" }, // Error
};

// Estado del Caso (valor de la API) → etiqueta + tono de badge.
export const estadoCaso = {
  recibido: { label: "Recibido", tone: "neutral" },
  en_evaluacion: { label: "En evaluación", tone: "info" },
  en_espera: { label: "En espera", tone: "amber" },
  derivado: { label: "Derivado", tone: "amber" },
  atendido: { label: "Atendido", tone: "green" },
  cerrado: { label: "Cerrado", tone: "gray" },
  cancelado: { label: "Cancelado", tone: "error" },
};

// Estado de la VersiónFlujo → tono.
export const estadoVersion = {
  borrador: { label: "Borrador", tone: "neutral" },
  publicada: { label: "Publicada", tone: "green" },
  reemplazada: { label: "Reemplazada", tone: "gray" },
  archivada: { label: "Archivada", tone: "gray" },
};

// Categorías de nodo (color sólido, tinte de fondo, borde).
export const nodeCat = {
  inicio: { name: "Inicio", sol: "#1F8A5B", tint: "#E9F6EF", bd: "#BBE3CD" },
  form: { name: "Formulario", sol: "#3949C0", tint: "#ECEEFB", bd: "#C7CDF2" },
  decision: { name: "Decisión", sol: "#C98A2B", tint: "#FBF2E0", bd: "#EBD7AC" },
  accion: { name: "Acción", sol: "#2B8FD6", tint: "#E6F1FB", bd: "#BBD9F2" },
  derivar: { name: "Derivar", sol: "#0E8893", tint: "#E3F4F4", bd: "#B2DFE0" },
  espera: { name: "Espera de fila", sol: "#16B1C9", tint: "#E2F6F9", bd: "#B6E4EC" },
  tiempo: { name: "Espera por tiempo", sol: "#0E9E8E", tint: "#E2F5F1", bd: "#B3E2D9" },
  atencion: { name: "Atención", sol: "#D14B8F", tint: "#FCEAF2", bd: "#F2C4DA" },
  estado: { name: "Estado", sol: "#5B7A99", tint: "#EEF2F6", bd: "#CDD8E2" },
  fin: { name: "Fin", sol: "#475467", tint: "#EFF1F4", bd: "#D0D5DD" },
};

// Avatares: paleta rotativa.
export const avatarColors = ["#3949C0", "#0E8893", "#9A3DB8", "#A96A12", "#1F8A5B", "#2B8FD6"];

export function iniciales(nombre = "") {
  return nombre
    .replace(/\./g, " ")
    .split(/\s+/)
    .filter(Boolean)
    .map((w) => w[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
}
