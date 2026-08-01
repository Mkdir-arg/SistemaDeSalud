/**
 * Vocabulario del dominio: cómo se llama y con qué tono se muestra cada estado.
 *
 * Vive acá y no en `theme.js` porque no es estilo. Que un caso «cerrado» se
 * muestre en gris es una decisión visual, pero que exista un estado «cerrado» y
 * se escriba así es del negocio: sobrevive al sistema de diseño.
 *
 * La separación importa para el final de la Fase 1: `theme.js` se borra cuando no
 * queden estilos inline, y sin este archivo se llevaría puestos los mapas de
 * estado que usan hasta las pantallas ya migradas.
 */

/** Estado del caso → etiqueta y tono de `Badge`. */
export const estadoCaso = {
  recibido: { label: "Recibido", tone: "neutral" },
  en_evaluacion: { label: "En evaluación", tone: "info" },
  en_espera: { label: "En espera", tone: "amber" },
  derivado: { label: "Derivado", tone: "amber" },
  atendido: { label: "Atendido", tone: "green" },
  cerrado: { label: "Cerrado", tone: "gray" },
  cancelado: { label: "Cancelado", tone: "error" },
};

/** Estado de la versión de un flujo → etiqueta y tono. */
export const estadoVersion = {
  borrador: { label: "Borrador", tone: "neutral" },
  publicada: { label: "Publicada", tone: "green" },
  reemplazada: { label: "Reemplazada", tone: "gray" },
  archivada: { label: "Archivada", tone: "gray" },
};

/**
 * Nombre de cada tipo de nodo.
 *
 * Sólo el nombre: los colores de la categoría son tokens (`--color-nodo-*-sol`,
 * `-tint`, `-bd`), que además tienen su variante oscura resuelta. Un componente
 * que quiera el color de una categoría usa la clase o la variable, nunca un hex
 * traído desde acá.
 */
const NOMBRE_NODO = {
  inicio: "Inicio",
  form: "Formulario",
  decision: "Decisión",
  accion: "Acción",
  derivar: "Derivar",
  espera: "Espera de fila",
  tiempo: "Espera por tiempo",
  atencion: "Atención",
  estado: "Estado",
  fin: "Fin",
};

/**
 * Función y no el objeto pelado: siempre devuelve algo.
 *
 * El backend puede sumar un tipo de nodo antes que el frontend lo conozca, y el
 * nombre se usa en lugares que asumen texto (`cat.toUpperCase()`). Con acceso
 * directo al mapa eso sería `undefined` y una pantalla en blanco por un tipo
 * nuevo, que es un precio absurdo por una etiqueta.
 */
export const nombreNodo = (tipo) => NOMBRE_NODO[tipo] || "Paso";

/** «María Elena Gómez» → «ME». Para los avatares. */
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
