import catalogo from "./padronColumnas.json" with { type: "json" };

export const COLUMNAS_PADRON = catalogo;
export const COLUMNAS_PREDETERMINADAS = catalogo.filter((c) => c.default).map((c) => c.key);
export const FILTROS_LEGACY_PADRON = ["estado_administrativo", "regimen", "alta_desde", "alta_hasta", "baja_desde", "baja_hasta"];
const consultaLegacy = ["plan", "estado", "derecho", "documento", "search", ...FILTROS_LEGACY_PADRON];

// Mismos tamaños de DataTable/useTablaUrl; la consulta y el rango visible coinciden.
export function tamanoPadron(parametros) {
  const pedido = Number(parametros.get("page_size"));
  return [10, 25, 50, 100].includes(pedido) ? pedido : 10;
}

export function obtenerColumnasPadron(parametros) {
  const elegidas = parametros.has("columnas") ? parametros.get("columnas").split(",") : COLUMNAS_PREDETERMINADAS;
  return catalogo.filter((c) => c.required || elegidas.includes(c.key)).map((c) => c.key);
}

export function cambiarColumnasPadron(parametros, claves) {
  const nuevos = new URLSearchParams(parametros);
  const columnas = catalogo.filter((c) => c.required || claves.includes(c.key)).map((c) => c.key);
  if (columnas.join(",") === COLUMNAS_PREDETERMINADAS.join(",")) nuevos.delete("columnas");
  else nuevos.set("columnas", columnas.join(","));
  return nuevos;
}

// Una transición evita pedir la página anterior de la nueva consulta.
export function cambiarConsultaPadron(parametros, cambios) {
  const nuevos = new URLSearchParams(parametros);
  nuevos.delete("page");
  nuevos.delete("padron_page");
  for (const [clave, valor] of Object.entries(cambios)) {
    if (valor === "" || valor == null) nuevos.delete(clave);
    else nuevos.set(clave, String(valor));
  }
  if (Object.hasOwn(cambios, "estado")) nuevos.delete("derecho");
  return nuevos;
}

export function ordenarPadron(parametros, campo) {
  if (!catalogo.some((c) => c.key === campo)) return new URLSearchParams(parametros);
  const actual = parametros.get("ordering") || "";
  return cambiarConsultaPadron(parametros, { ordering: actual === campo ? `-${campo}` : actual === `-${campo}` ? "" : campo });
}

export function parametrosConsultaPadron(parametros) {
  const consulta = new URLSearchParams();
  for (const [clave, valor] of parametros) {
    if (consultaLegacy.includes(clave) || ["ordering", "columnas", "page", "page_size"].includes(clave) || clave.startsWith("flt_")) consulta.append(clave, valor);
  }
  if (!consulta.has("page")) consulta.set("page", "1");
  consulta.set("page_size", String(tamanoPadron(parametros)));
  if (!consulta.has("estado") && !consulta.has("derecho")) consulta.set("estado", "vigentes");
  return consulta;
}

export function valorColumnaPadron(fila, columna, planes = []) {
  let valor = fila[columna.key];
  if (columna.key === "derecho") valor = fila.finalizado_en ? "finalizadas" : fila.vigente === false ? "futuras" : "vigentes";
  if (columna.key === "plan") return fila.plan == null ? "Sin plan" : planes.find((p) => String(p.id) === String(fila.plan))?.nombre || `Plan ${fila.plan}`;
  if (valor == null || valor === "") return "Sin informar";
  if (columna.options) return columna.options[valor] || String(valor);
  if (columna.type === "date") return String(valor).split("-").reverse().join("/");
  if (columna.type === "datetime") return new Date(valor).toLocaleString("es-AR");
  return String(valor);
}
