// Orden visual compartido por las barras y sus referencias impresas.
// Los importes exactos siguen siendo las cadenas recibidas del servidor.
export const gruposComparados = (grupos) => [...grupos]
  .sort((a, b) => Number(b.actual?.aprobados || 0) - Number(a.actual?.aprobados || 0))
  .slice(0, 8);
