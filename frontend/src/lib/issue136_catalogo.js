// Una carga completa por nivel y contexto; la búsqueda no dispara peticiones.
export async function cargarCatalogoGeografico(cargarPagina, signal) {
  const filas = [];
  let pagina = 1;
  let total;
  while (pagina !== null) {
    signal?.throwIfAborted();
    const respuesta = await cargarPagina(pagina);
    signal?.throwIfAborted();
    if (!Array.isArray(respuesta.results)) throw new Error("Respuesta de catálogo inválida.");
    if (total === undefined) total = respuesta.count;
    if (respuesta.count !== total) throw new Error("El catálogo cambió durante la carga.");
    filas.push(...respuesta.results);
    const siguiente = respuesta.next ?? null;
    if (siguiente !== null && (!Number.isInteger(siguiente) || siguiente <= pagina || siguiente > 10000)) {
      throw new Error("Paginación de catálogo inválida.");
    }
    pagina = siguiente;
  }
  if (total !== undefined && filas.length !== total) throw new Error("Catálogo incompleto.");
  return filas;
}

export function filtrarCatalogoGeografico(filas, texto) {
  const busqueda = texto.trim().toLocaleLowerCase("es-AR");
  return busqueda ? filas.filter((fila) => fila.nombre.toLocaleLowerCase("es-AR").includes(busqueda)) : filas;
}
