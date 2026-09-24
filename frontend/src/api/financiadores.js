import { api, mensajeError } from "./client";

export const rutaFinanciador = (id, recurso = "") => `/financiadores/${id}/${recurso ? `${recurso}/` : ""}`;
export const filasDe = (data) => Array.isArray(data) ? data : data?.results || [];

// Las opciones chicas (planes y catálogo) incluyen todas las páginas. Las
// pantallas de padrón y consumos conservan paginación en el servidor.
export async function opcionesFinanciador(id, recurso) {
  const filas = [];
  for (let page = 1; ; page += 1) {
    const data = await api.get(`${rutaFinanciador(id, recurso)}?page=${page}`);
    filas.push(...filasDe(data));
    if (!data.next) return filas;
  }
}

export async function importarFinanciador(id, tipo, archivo, clave) {
  const body = new FormData();
  body.append("tipo", tipo);
  body.append("archivo", archivo);
  body.append("clave", clave);
  return api.multipart(rutaFinanciador(id, "importaciones"), body);
}

export function errorFinanciador(error) {
  return mensajeError(error, "No se pudo completar la operación. Podés volver a intentarlo.");
}
