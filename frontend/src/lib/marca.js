// Nombre visible del producto. Cambia seguido mientras se define la marca, por eso
// sale de `VITE_NOMBRE_SISTEMA` y no está escrito en las pantallas. Vite lo
// incrusta en el build: cambiarlo exige volver a construir el frontend.
// Ver docs/NOMBRE-DEL-SISTEMA.md.
export const NOMBRE_SISTEMA = import.meta.env.VITE_NOMBRE_SISTEMA?.trim() || "PLEXO";
