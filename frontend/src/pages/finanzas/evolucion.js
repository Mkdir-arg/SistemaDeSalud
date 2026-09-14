// Un estado pertenece a un concepto/mes; nunca filtra el mes de otras series.
export const coincideEstadoMes = (fila, estado) => estado === "ambos" || (estado === "completo"
  ? fila.estado === "completo"
  : ["incompleto", "mes_abierto", "sin_carga"].includes(fila.estado));

// Cero es una referencia válida. No arrastrar valores sobre meses sin referencia.
export const tieneReferencia = (serie) => serie.meses.some((fila) => fila.monto_referencia != null);
