import { Field, Input, Select } from "@/components/ui";
import { ADMINISTRATIVOS, REGIMENES } from "./padronCampos";

export const FILTROS_PADRON = ["estado_administrativo", "regimen", "alta_desde", "alta_hasta", "baja_desde", "baja_hasta"];
export default function FiltrosPadron({ parametros, cambiar }) {
  return <details className="mb-4 rounded-md border border-division p-4" open={FILTROS_PADRON.some((campo) => parametros.has(campo))}>
    <summary className="cursor-pointer text-sm font-semibold">Filtros administrativos</summary>
    <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      <Field label="Estado administrativo"><Select value={parametros.get("estado_administrativo") || ""} onChange={(event) => cambiar("estado_administrativo", event.target.value)}><option value="">Todos</option>{Object.entries(ADMINISTRATIVOS).map(([id, nombre]) => <option key={id} value={id}>{nombre}</option>)}</Select></Field>
      <Field label="Régimen"><Select value={parametros.get("regimen") || ""} onChange={(event) => cambiar("regimen", event.target.value)}><option value="">Todos</option>{Object.entries(REGIMENES).map(([id, nombre]) => <option key={id} value={id}>{nombre}</option>)}</Select></Field>
      {[["alta_desde", "Alta administrativa desde"], ["alta_hasta", "Alta administrativa hasta"], ["baja_desde", "Baja administrativa desde"], ["baja_hasta", "Baja administrativa hasta"]].map(([name, label]) => <Field key={name} label={label}><Input type="date" value={parametros.get(name) || ""} onChange={(event) => cambiar(name, event.target.value)} /></Field>)}
    </div>
  </details>;
}
