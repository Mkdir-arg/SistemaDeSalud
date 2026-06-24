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
};

export const font = {
  sans: "Inter, system-ui, sans-serif",
  mono: "'JetBrains Mono', monospace",
};

// Tono → estilos de badge de estado (bg / fg). Mapea los estados semánticos.
export const badgeTone = {
  neutral: { bg: "#EEF0F3", fg: "#475467" }, // Recibido / Borrador
  info: { bg: "#E8EEFB", fg: "#2D3A9E" }, // En evaluación
  amber: { bg: "#FBF0DD", fg: "#A96A12" }, // Derivado / En espera
  green: { bg: "#E6F5EC", fg: "#1B7A4E" }, // Publicado / Atendido
  gray: { bg: "#F0F1F3", fg: "#9098A6" }, // Cerrado / Archivado
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
