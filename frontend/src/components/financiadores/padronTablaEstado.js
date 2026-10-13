import catalogo from "./padronColumnas.json" with { type: "json" };
import { ADMINISTRATIVOS, REGIMENES } from "./padronCampos.js";

export const COLUMNAS_PADRON = catalogo;
export const COLUMNAS_PREDETERMINADAS = catalogo.filter((c) => c.default).map((c) => c.key);
export const FILTROS_LEGACY_PADRON = ["estado_administrativo", "regimen", "alta_desde", "alta_hasta", "baja_desde", "baja_hasta"];
const consultaLegacy = ["plan", "estado", "derecho", "documento", "search", ...FILTROS_LEGACY_PADRON];

// Mismos tamaños de DataTable/useTablaUrl; la consulta y el rango visible coinciden.
export function tamanoPadron(parametros) {
  const pedido = Number(parametros.get("page_size"));
  return [10, 25, 50, 100].includes(pedido) ? pedido : 10;
}

export function estadoDerechoPadron(parametros) {
  return parametros.get("derecho") || parametros.get("estado") || parametros.get("flt_derecho") || "vigentes";
}

export function cambiarEstadoPadron(parametros, valor) {
  return cambiarConsultaPadron(parametros, { estado: valor || "vigentes" });
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
  if (Object.hasOwn(cambios, "estado")) {
    nuevos.delete("derecho");
    nuevos.delete("flt_derecho");
  }
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
  if (!consulta.get("estado") && !consulta.get("derecho") && !consulta.get("flt_derecho")) consulta.set("estado", "vigentes");
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

// Agrupación solo de presentación, con los mismos bloques de la ficha. El
// catálogo es contrato con backend (debe coincidir exacto), por eso no la lleva.
export const GRUPOS_PADRON = [
  ["Afiliación", ["nombre", "numero", "documento", "plan", "plan_tipo", "derecho", "desde", "finalizado_en", "motivo_finalizacion"]],
  ["Trámite y credencial", ["estado_administrativo", "estado_tramite", "alta_administrativa", "delegacion", "credencial_tipo", "credencial_fecha"]],
  ["Identidad", ["tipo_documento", "cuil", "nombres", "apellidos", "sexo", "fecha_nacimiento", "nacionalidad", "estado_civil"]],
  ["Contacto", ["telefono", "celular", "email"]],
  ["Domicilio", ["calle", "altura", "piso", "departamento", "codigo_postal", "localidad", "partido", "provincia"]],
  ["Régimen y trabajo", ["regimen", "empleador", "cuit_empleador", "actividad_laboral", "domicilio_laboral", "telefono_laboral", "email_laboral", "subsidio_desde", "subsidio_hasta"]],
  ["Baja administrativa", ["causa_baja", "solicitud_baja", "baja_efectiva", "fin_prestacional_informado", "motivo_baja"]],
  ["Grupo familiar", ["titular", "parentesco"]],
].map(([titulo, claves]) => ({ titulo, columnas: claves.map((key) => catalogo.find((c) => c.key === key)) }));

const fechaAR = (valor) => String(valor).split("-").reverse().join("/");
// Cuatro columnas conservan sus parámetros históricos (URLs guardadas, export),
// con el rótulo que ya tenían en pantalla.
const LEGACY = {
  estado_administrativo: [{ clave: "estado_administrativo", tipo: "choice", options: ADMINISTRATIVOS, label: "Estado administrativo" }],
  regimen: [{ clave: "regimen", tipo: "choice", options: REGIMENES }],
  alta_administrativa: ["desde", "hasta"].map((extremo) => ({ clave: `alta_${extremo}`, tipo: "date", extremo })),
  baja_efectiva: ["desde", "hasta"].map((extremo) => ({ clave: `baja_${extremo}`, tipo: "date", extremo, label: "Baja administrativa" })),
};

function controlesGenericos(col) {
  const vacio = col.nullable ? [{ clave: `flt_${col.key}_vacio`, tipo: "vacio" }] : [];
  if (col.type === "date" || col.type === "datetime") return [...["desde", "hasta"].map((extremo) => ({ clave: `flt_${col.key}_${extremo}`, tipo: "date", extremo })), ...vacio];
  if (col.key === "plan") return [{ clave: "flt_plan", tipo: "plan" }, ...vacio];
  if (col.type === "choice") return [{ clave: `flt_${col.key}`, tipo: "choice", options: col.options }, ...vacio];
  return [{ clave: `flt_${col.key}`, tipo: col.type === "relation" ? "relation" : "text" }, ...vacio];
}

/**
 * Controles que ofrece el panel para una columna. Estado y Plan viven en la
 * barra y no se repiten (de Plan queda «sin informar»).
 */
export function controlesFiltroPadron(col) {
  if (col.key === "derecho") return [];
  const genericos = controlesGenericos(col);
  if (col.key === "plan") return genericos.filter((c) => c.tipo === "vacio");
  if (LEGACY[col.key]) return [...LEGACY[col.key], ...genericos.filter((c) => c.tipo === "vacio")];
  return genericos;
}

/**
 * Filtros aplicados (no borradores) como chips, uno por parámetro. Incluye los
 * flt_ de columnas con parámetro histórico: siguen siendo válidos en la URL.
 */
export function filtrosActivosPadron(parametros, planes = []) {
  const activos = [];
  for (const col of catalogo) {
    if (col.key === "derecho") continue;
    const controles = [...(LEGACY[col.key] || []), ...controlesGenericos(col)];
    for (const control of controles) {
      const valor = parametros.get(control.clave);
      if (!valor) continue;
      const label = control.label || col.label;
      let texto;
      if (control.tipo === "vacio") texto = `: ${valor === "true" ? "sin cargar" : "cargado"}`;
      else if (control.tipo === "date") texto = ` ${control.extremo} ${fechaAR(valor)}`;
      else if (control.tipo === "choice") texto = `: ${control.options?.[valor] || valor}`;
      else if (control.tipo === "plan") texto = `: ${planes.find((p) => String(p.id) === valor)?.nombre || `Plan ${valor}`}`;
      else if (control.tipo === "relation") texto = ` ${valor}`;
      else texto = `: «${valor}»`;
      activos.push({ clave: control.clave, etiqueta: label + texto });
    }
  }
  return activos;
}
