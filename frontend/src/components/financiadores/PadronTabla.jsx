import { useEffect, useId, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { Icon } from "@/components/icons";
import { Button } from "@/components/ui";
import { FiltroSelect } from "@/components/ui/filtros";
import { DataTable } from "@/components/ui/tabla";
import { cn } from "@/lib/cn";
import ColumnasPadron from "./ColumnasPadron";
import { BuscadorPadron, ChipsFiltrosPadron, PanelFiltrosPadron, useBorradoresPadron } from "./FiltrosPadron";
import "./PadronTabla.css";
import { COLUMNAS_PADRON, cambiarConsultaPadron, cambiarEstadoPadron, estadoDerechoPadron, filtrosActivosPadron, obtenerColumnasPadron, ordenarPadron, tamanoPadron, valorColumnaPadron } from "./padronTablaEstado";

const VACIO = [];
const positivo = (v, defecto) => Number.isSafeInteger(Number(v)) && Number(v) > 0 ? Number(v) : defecto;
const DURACION_PANEL = 200; // = duration-200 de la transición (tokens.css, «Movimiento»)
const ESTADOS = [["vigentes", "Vigentes"], ["administrativas", "Sólo registro administrativo"], ["futuras", "Aún no vigentes"], ["finalizadas", "Finalizadas"], ["todos", "Todos"]];

/** Presentación/control URL. Consulta, permisos, edición y XLSX los aporta Portal. */
export default function PadronTabla(props) {
  // Cambiar de financiador descarta borradores y su timer: no se aplican a otro padrón.
  return <PadronTablaFinanciador key={props.parametros.get("financiador") || ""} {...props} />;
}

function PadronTablaFinanciador({ filas, total, paginas, estado, parametros, onParametrosChange, onFiltrosPendientesChange, planes = VACIO, fichaHref, renderAcciones, barra }) {
  const [densidad, setDensidad] = useState("comoda");
  // Fases del panel: se monta cerrado, se abre al cuadro siguiente (así hay
  // transición) y al cerrar espera a que termine antes de desmontarse.
  const [fase, setFase] = useState("cerrado");
  const panel = fase !== "cerrado";
  const visible = fase === "abierto";
  const abierto = fase === "abriendo" || fase === "abierto";
  useEffect(() => {
    if (fase === "abriendo") {
      let cuadro = requestAnimationFrame(() => { cuadro = requestAnimationFrame(() => setFase("abierto")); });
      return () => cancelAnimationFrame(cuadro);
    }
    if (fase === "cerrando") {
      const espera = setTimeout(() => setFase("cerrado"), window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : DURACION_PANEL);
      return () => clearTimeout(espera);
    }
  }, [fase]);
  const cerrarPanel = () => setFase((f) => (f === "cerrado" ? f : "cerrando"));
  const idPanel = useId();
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
  const { borradores, pendientes, editarTexto, descartar, aplicarYa } = useBorradoresPadron({ parametros, cambiar, cambiarVarios, onFiltrosPendientesChange });
  const activos = filtrosActivosPadron(parametros, planes);
  // «Limpiar todo» vuelve al padrón entero: chips, búsqueda y plan. Estado no:
  // define qué afiliaciones se miran, no un filtro sobre ellas.
  const [reinicioBusqueda, setReinicioBusqueda] = useState(0);
  const hayQueLimpiar = activos.length > 0 || parametros.has("search") || parametros.has("plan");
  const limpiar = () => {
    descartar(Object.keys(borradores));
    setReinicioBusqueda((n) => n + 1);
    onParametrosChange(cambiarConsultaPadron(parametros, Object.fromEntries([...activos.map((f) => f.clave), "search", "plan"].map((clave) => [clave, ""]))));
  };
  const quitar = (clave) => { descartar([clave]); cambiar(clave, ""); };
  const estadoActual = estadoDerechoPadron(parametros);
  const tabla = {
    pagina, orden, tamano, densidad, setDensidad,
    irA: (n) => { const p = new URLSearchParams(parametros); if (n > 1) p.set("page", String(n)); else p.delete("page"); onParametrosChange(p); },
    ordenarPor: (campo) => onParametrosChange(ordenarPadron(parametros, campo)),
    cambiarTamano: (n) => cambiar("page_size", n),
  };
  const herramientas = <>
    <BuscadorPadron key={reinicioBusqueda} parametros={parametros} editarTexto={editarTexto} aplicarYa={aplicarYa} />
    <select aria-label="Estado" value={estadoActual} onChange={(e) => onParametrosChange(cambiarEstadoPadron(parametros, e.target.value))}
      className={cn("h-8 rounded-md border border-campo-borde bg-superficie px-2 text-base text-texto-medio outline-none focus:border-accent", estadoActual !== "vigentes" && "border-accent-100 bg-accent-50 text-accent")}>
      {ESTADOS.map(([id, nombre]) => <option key={id} value={id}>{nombre}</option>)}
    </select>
    <FiltroSelect className="max-w-[10rem]" etiqueta="Plan" todos="Todos los planes" valor={parametros.get("plan") || ""} onChange={(valor) => cambiar("plan", valor)} opciones={planes.map((p) => ({ value: String(p.id), label: p.nombre }))} />
    <button type="button" aria-expanded={abierto} aria-controls={panel ? idPanel : undefined} onClick={() => (abierto ? cerrarPanel() : setFase("abriendo"))}
      className={cn("inline-flex h-8 items-center gap-2 rounded-md px-3 text-sm font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent", abierto || activos.length ? "bg-accent-50 text-accent" : "text-texto-suave hover:bg-superficie-2")}>
      <Icon name="filter" size={15} />Filtros{activos.length > 0 && <span className="rounded-pill bg-accent px-1.5 text-xs font-semibold tabular-nums text-sobre-accent">{activos.length}</span>}
    </button>
    {/* Lo que cambia la vista (no el resultado) va a la derecha, junto a la densidad. */}
    <div className="ml-auto flex items-center gap-md">
      <ColumnasPadron elegidas={elegidas} parametros={parametros} onParametrosChange={onParametrosChange} />
      {barra}
    </div>
  </>;
  const vacio = { titulo: "Sin afiliados para estos filtros", detalle: hayQueLimpiar ? "Probá quitar algún filtro o cambiar la búsqueda." : "No hay afiliaciones en este estado.",
    accion: hayQueLimpiar ? <Button type="button" variant="secondary" size="sm" onClick={limpiar}>Limpiar filtros</Button> : undefined };

  return <section aria-label="Padrón de afiliados" className="padron-tabla flex min-w-0 items-start">
    <div className="min-w-0 flex-1" aria-busy={estado.cargando || estado.refrescando || undefined}>
      <DataTable titulo="Padrón de afiliados" columnas={columnas} filas={filas} total={total} paginas={paginas} estado={estado} tabla={tabla} mantenerEncabezados adaptable vacio={vacio}
        barra={herramientas} subbarra={(activos.length > 0 || pendientes) && <ChipsFiltrosPadron activos={activos} pendientes={pendientes} quitar={quitar} limpiar={limpiar} />} />
    </div>
    {/* El hueco anima su ancho: la tabla se achica y se agranda con el panel.
        overflow-clip (no hidden) para no romper el sticky del panel. El margen
        negativo lo estira dentro del padding inferior de la página (30px en lg,
        40px en xl) hasta 24px del borde: si terminara con la tabla, al final del
        scroll el sticky empujaría el panel hacia arriba. */}
    {panel && <div className={cn("lg:-mb-1.5 lg:flex lg:shrink-0 lg:justify-end lg:self-stretch lg:overflow-clip xl:-mb-4 lg:transition-[width] lg:duration-200 lg:ease-salida motion-reduce:transition-none", visible ? "lg:w-[356px]" : "lg:w-0")}>
      <PanelFiltrosPadron id={idPanel} visible={visible} cerrando={fase === "cerrando"} parametros={parametros} cambiar={cambiar} borradores={borradores} editarTexto={editarTexto} planes={planes} activos={activos} limpiar={limpiar} cerrar={cerrarPanel} />
    </div>}
  </section>;
}
