import { useRef, useState } from "react";
import { Link } from "react-router-dom";

import { Button, Checkbox } from "@/components/ui";
import { DataTable } from "@/components/ui/tabla";
import FiltrosPadron from "./FiltrosPadron";
import "./PadronTabla.css";
import { COLUMNAS_PADRON, COLUMNAS_PREDETERMINADAS, cambiarColumnasPadron, cambiarConsultaPadron, obtenerColumnasPadron, ordenarPadron, tamanoPadron, valorColumnaPadron } from "./padronTablaEstado";

const VACIO = [];
const positivo = (v, defecto) => Number.isSafeInteger(Number(v)) && Number(v) > 0 ? Number(v) : defecto;

/** Presentación/control URL. Consulta, permisos, edición y XLSX los aporta Portal. */
export default function PadronTabla({ filas, total, paginas, estado, parametros, onParametrosChange, onFiltrosPendientesChange, planes = VACIO, fichaHref, renderAcciones, barra }) {
  const [densidad, setDensidad] = useState("comoda");
  const elegidas = obtenerColumnasPadron(parametros);
  const pagina = positivo(parametros.get("page"), 1);
  const tamano = tamanoPadron(parametros);
  const orden = parametros.get("ordering") || "";
  const actuales = useRef();
  actuales.current = { parametros, onParametrosChange };
  const columnas = COLUMNAS_PADRON.filter((c) => elegidas.includes(c.key)).map((col) => ({
    key: col.key, label: col.label, orden: col.key,
    render: (fila) => col.key === "nombre" && fichaHref ? <Link className="font-medium text-accent hover:underline" to={fichaHref(fila)}>{fila.nombre}</Link> : valorColumnaPadron(fila, col, planes),
  }));
  if (renderAcciones) columnas.push({ key: "acciones", label: "Acciones", fija: true, render: renderAcciones });
  const cambiar = (campo, valor) => onParametrosChange(cambiarConsultaPadron(parametros, { [campo]: valor }));
  const cambiarVarios = (cambios, opciones) => actuales.current.onParametrosChange(cambiarConsultaPadron(actuales.current.parametros, cambios), opciones);
  const tabla = {
    pagina, orden, tamano, densidad, setDensidad,
    irA: (n) => { const p = new URLSearchParams(parametros); if (n > 1) p.set("page", String(n)); else p.delete("page"); onParametrosChange(p); },
    ordenarPor: (campo) => onParametrosChange(ordenarPadron(parametros, campo)),
    cambiarTamano: (n) => cambiar("page_size", n),
  };
  return <section aria-label="Padrón de afiliados" className="padron-tabla min-w-0 space-y-3">
    <details className="rounded-md border border-division p-4">
      <summary className="cursor-pointer text-sm font-semibold">Columnas visibles ({elegidas.length})</summary>
      <p className="mt-2 text-sm text-texto-debil">Mostrar u ocultar columnas no cambia los datos del afiliado. Afiliado, número y acciones se conservan.</p>
      <fieldset className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        <legend className="sr-only">Elegir columnas visibles</legend>
        {COLUMNAS_PADRON.map((col) => <Checkbox key={col.key} label={col.label} checked={elegidas.includes(col.key)} disabled={col.required} onChange={(event) => onParametrosChange(cambiarColumnasPadron(parametros, event.target.checked ? [...elegidas, col.key] : elegidas.filter((k) => k !== col.key)))} />)}
      </fieldset>
      <Button type="button" variant="secondary" size="sm" className="mt-3" onClick={() => onParametrosChange(cambiarColumnasPadron(parametros, COLUMNAS_PREDETERMINADAS))}>Restaurar columnas</Button>
    </details>
    <FiltrosPadron key={parametros.get("financiador") || ""} parametros={parametros} cambiar={cambiar} cambiarVarios={cambiarVarios} onFiltrosPendientesChange={onFiltrosPendientesChange} columnas={elegidas} planes={planes} />
    <div aria-busy={estado.cargando || estado.refrescando || undefined}>
      <DataTable titulo="Padrón de afiliados" columnas={columnas} filas={filas} total={total} paginas={paginas} estado={estado} tabla={tabla} barra={barra} mantenerEncabezados adaptable vacio={{ titulo: "Sin afiliados para estos filtros", detalle: "Revisá los filtros administrativos o la búsqueda." }} />
    </div>
  </section>;
}
