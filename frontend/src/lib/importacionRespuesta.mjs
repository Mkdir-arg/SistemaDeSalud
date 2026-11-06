export function combinarLote(actual, respuesta) {
  const invalida = () => { throw new Error("No se pudo sincronizar el lote. Reintentá la confirmación para recuperar su estado."); };
  if (respuesta?.id !== actual.id || respuesta?.version !== actual.version) invalida();
  if (respuesta.modo_respuesta !== "cambios") {
    // Compatible con la respuesta completa del backend anterior y con el
    // fallback completo del nuevo. Nunca interpretar un resumen como lote.
    if (![undefined, "completa"].includes(respuesta.modo_respuesta) || !Array.isArray(respuesta.filas)) invalida();
    return respuesta;
  }
  if (!actual.huella_lote || actual.huella_lote !== respuesta.base_huella
      || !respuesta.huella_lote || "filas" in respuesta
      || !Array.isArray(actual.filas) || !Array.isArray(respuesta.filas_cambiadas)) invalida();
  const posiciones = new Map(actual.filas.map((fila, index) => [fila.fila, index]));
  if (posiciones.size !== actual.filas.length) invalida();
  const filas = [...actual.filas];
  const vistas = new Set();
  for (const fila of respuesta.filas_cambiadas) {
    if (!posiciones.has(fila.fila) || vistas.has(fila.fila)) invalida();
    vistas.add(fila.fila);
    // Reemplazar la fila completa también elimina campos que el servidor
    // retiró; conservar sin cambios las filas y evidencias no afectadas.
    filas[posiciones.get(fila.fila)] = fila;
  }
  if (respuesta.resumen?.total !== filas.length) invalida();
  const conteos = { valida: 0, revision: 0, rechazada: 0, aplicada: 0, error_tecnico: 0, omitida: 0 };
  for (const fila of filas) {
    if (!Object.hasOwn(conteos, fila.estado)) invalida();
    conteos[fila.estado] += 1;
  }
  for (const [estado, total] of Object.entries(conteos)) {
    if (respuesta.resumen[estado] !== total) invalida();
  }
  const { filas_cambiadas, base_huella, ...cabecera } = respuesta;
  return { ...cabecera, filas };
}

export async function confirmarTanda(actual, enviar) {
  const respuesta = await enviar({ importacion: actual.id, modo_respuesta: "cambios",
    ...(actual.huella_lote ? { huella_lote: actual.huella_lote } : {}) });
  return combinarLote(actual, respuesta);
}
