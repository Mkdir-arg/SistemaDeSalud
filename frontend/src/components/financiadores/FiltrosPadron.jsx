import { Field, Input, Select } from "@/components/ui";
import { ADMINISTRATIVOS, REGIMENES } from "./padronCampos";
import { COLUMNAS_PADRON, FILTROS_LEGACY_PADRON } from "./padronTablaEstado";

export const FILTROS_PADRON = FILTROS_LEGACY_PADRON;
const VACIO = [];
const legacy = new Set(["estado_administrativo", "regimen", "alta_administrativa", "baja_efectiva"]);

export default function FiltrosPadron({ parametros, cambiar, columnas = VACIO, planes = VACIO }) {
  const conFiltro = (col) => [...parametros.keys()].some((k) => k === `flt_${col.key}` || k.startsWith(`flt_${col.key}_`));
  // Derecho tiene un único control global Estado, incluidos sus aliases de URL.
  const adicionales = COLUMNAS_PADRON.filter((col) => col.key !== "derecho" && ((!legacy.has(col.key) && columnas.includes(col.key)) || conFiltro(col)));
  const activos = FILTROS_PADRON.some((campo) => parametros.has(campo)) || [...parametros.keys()].some((k) => k.startsWith("flt_"));
  return <details className="mb-4 rounded-md border border-division p-4" open={activos}>
    <summary className="cursor-pointer text-sm font-semibold">Filtros administrativos</summary>
    <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      <Field label="Estado administrativo"><Select value={parametros.get("estado_administrativo") || ""} onChange={(event) => cambiar("estado_administrativo", event.target.value)}><option value="">Todos</option>{Object.entries(ADMINISTRATIVOS).map(([id, nombre]) => <option key={id} value={id}>{nombre}</option>)}</Select></Field>
      <Field label="Régimen"><Select value={parametros.get("regimen") || ""} onChange={(event) => cambiar("regimen", event.target.value)}><option value="">Todos</option>{Object.entries(REGIMENES).map(([id, nombre]) => <option key={id} value={id}>{nombre}</option>)}</Select></Field>
      {[["alta_desde", "Alta administrativa desde"], ["alta_hasta", "Alta administrativa hasta"], ["baja_desde", "Baja administrativa desde"], ["baja_hasta", "Baja administrativa hasta"]].map(([name, label]) => <Field key={name} label={label}><Input type="date" value={parametros.get(name) || ""} onChange={(event) => cambiar(name, event.target.value)} /></Field>)}
      {adicionales.map((col) => <FiltroColumna key={col.key} columna={col} parametros={parametros} cambiar={cambiar} planes={planes} />)}
      {COLUMNAS_PADRON.filter((col) => legacy.has(col.key) && col.nullable && columnas.includes(col.key) && !adicionales.includes(col)).map((col) => <FiltroVacio key={col.key} columna={col} parametros={parametros} cambiar={cambiar} />)}
    </div>
  </details>;
}

function FiltroVacio({ columna, parametros, cambiar }) {
  const clave = `flt_${columna.key}_vacio`;
  return <Field label={`${columna.label}: información`}><Select value={parametros.get(clave) || ""} onChange={(e) => cambiar(clave, e.target.value)}><option value="">Con o sin información</option><option value="true">Sin informar</option><option value="false">Informado</option></Select></Field>;
}

function FiltroColumna({ columna: col, parametros, cambiar, planes }) {
  const clave = `flt_${col.key}`;
  return <fieldset className="min-w-0 space-y-2 rounded-md border border-division p-3">
    <legend className="px-1 text-sm font-semibold">{col.label}</legend>
    {col.type === "date" || col.type === "datetime" ? ["desde", "hasta"].map((extremo) => <Field key={extremo} label={`${col.label} ${extremo}`}><Input type="date" value={parametros.get(`${clave}_${extremo}`) || ""} onChange={(e) => cambiar(`${clave}_${extremo}`, e.target.value)} /></Field>)
      : col.type === "choice" || col.key === "plan" ? <Field label={`Filtrar ${col.label}`}><Select value={parametros.get(clave) || ""} onChange={(e) => cambiar(clave, e.target.value)}><option value="">Todos</option>{(col.key === "plan" ? planes.map((p) => [String(p.id), p.nombre]) : Object.entries(col.options)).map(([id, nombre]) => <option key={id} value={id}>{nombre}</option>)}</Select></Field>
        : <Field label={`Filtrar ${col.label}`}><Input type={col.type === "relation" ? "number" : "text"} min={col.type === "relation" ? 1 : undefined} step={col.type === "relation" ? 1 : undefined} placeholder={col.type === "relation" ? "ID exacto" : "Contiene…"} value={parametros.get(clave) || ""} onChange={(e) => cambiar(clave, e.target.value)} /></Field>}
    {col.nullable && <FiltroVacio columna={col} parametros={parametros} cambiar={cambiar} />}
  </fieldset>;
}
