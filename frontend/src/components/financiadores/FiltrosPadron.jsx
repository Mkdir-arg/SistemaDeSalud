import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigationType } from "react-router-dom";
import { Icon } from "@/components/icons";
import { Input, Select } from "@/components/ui";
import { Buscador } from "@/components/ui/filtros";
import { cn } from "@/lib/cn";
import { GRUPOS_PADRON, controlesFiltroPadron } from "./padronTablaEstado";

/**
 * Borradores de texto con espera: una ráfaga de teclas produce una sola
 * consulta y un `replace` (no ensucia el historial). Back descarta lo que no se
 * aplicó. Vive en PadronTabla para sobrevivir al cierre del panel.
 */
export function useBorradoresPadron({ parametros, cambiar, cambiarVarios, onFiltrosPendientesChange }) {
  const [borradores, setBorradores] = useState({});
  const pendientes = Object.keys(borradores).length > 0;
  const location = useLocation();
  const navegacion = useNavigationType();
  const anterior = useRef(location.key);
  const actual = useRef();
  actual.current = { parametros, cambiar, cambiarVarios, onFiltrosPendientesChange };

  useEffect(() => {
    if (anterior.current !== location.key && navegacion === "POP") setBorradores({});
    anterior.current = location.key;
  }, [location.key, navegacion]);

  useEffect(() => {
    actual.current.onFiltrosPendientesChange?.(pendientes);
  }, [pendientes]);
  useEffect(() => () => actual.current.onFiltrosPendientesChange?.(false), []);

  function aplicar(lote) {
    const cambios = Object.fromEntries(Object.entries(lote).filter(([k, v]) => v !== (actual.current.parametros.get(k) || "")));
    if (Object.keys(cambios).length) {
      if (actual.current.cambiarVarios) actual.current.cambiarVarios(cambios, { replace: true });
      else Object.entries(cambios).forEach(([k, v]) => actual.current.cambiar(k, v, { replace: true }));
    }
    setBorradores({});
  }

  useEffect(() => {
    if (!Object.keys(borradores).length) return;
    const timer = setTimeout(() => aplicar(borradores), 300);
    return () => clearTimeout(timer);
  }, [borradores, location.key]);

  function editarTexto(clave, valor) {
    setBorradores((previos) => {
      const nuevos = { ...previos };
      if (valor === (parametros.get(clave) || "")) delete nuevos[clave];
      else nuevos[clave] = valor;
      return nuevos;
    });
  }
  // Quitar o limpiar un filtro también descarta lo que se estaba tipeando en
  // él: si no, el temporizador lo vuelve a aplicar después del clic.
  function descartar(claves) {
    setBorradores((previos) => {
      const nuevos = { ...previos };
      for (const clave of claves) delete nuevos[clave];
      return nuevos;
    });
  }
  return { borradores, pendientes, editarTexto, descartar, aplicarYa: () => aplicar(borradores) };
}

/** Búsqueda global: se aplica sola al dejar de tipear, o al instante con Enter. */
export function BuscadorPadron({ parametros, editarTexto, aplicarYa }) {
  const aplicado = parametros.get("search") || "";
  const location = useLocation();
  // El texto visible es propio: la consulta va recortada y no debe comerse el
  // espacio que la persona acaba de tipear entre dos palabras.
  const [texto, setTexto] = useState(aplicado);
  useEffect(() => { setTexto((t) => (t.trim() === aplicado ? t : aplicado)); }, [aplicado, location.key]);
  return <Buscador className="w-full sm:w-52" aria-label="Buscar por afiliado, documento o nombre" placeholder="Buscar afiliado…"
    valor={texto} onChange={(valor) => { setTexto(valor); editarTexto("search", valor.trim()); }}
    onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); aplicarYa(); } }} />;
}

/** Chips de lo aplicado: cada uno se quita solo; «Limpiar todo» vuelve al padrón entero. */
export function ChipsFiltrosPadron({ activos, pendientes, quitar, limpiar }) {
  return <div className="flex flex-wrap items-center gap-2">
    {activos.map((f) => <span key={f.clave} className="inline-flex max-w-full animate-aparecer items-center gap-1 rounded-pill border border-accent-100 bg-accent-50 py-0.5 pl-2.5 pr-1 text-sm text-accent">
      <span className="truncate">{f.etiqueta}</span>
      <button type="button" aria-label={`Quitar filtro ${f.etiqueta}`} onClick={() => quitar(f.clave)} className="flex rounded-pill p-0.5 hover:bg-accent-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"><Icon name="x" size={12} /></button>
    </span>)}
    {activos.length > 0 && <button type="button" onClick={limpiar} className="rounded-md px-2 py-0.5 text-sm font-medium text-texto-debil hover:bg-superficie-2 hover:text-texto-medio">Limpiar todo</button>}
    {pendientes && <p role="status" className="text-sm text-texto-debil">Aplicando filtros…</p>}
  </div>;
}

const coincide = (texto, busca) => texto.toLocaleLowerCase("es").normalize("NFD").replace(/\p{Diacritic}/gu, "").includes(busca);

/**
 * Todos los filtros del padrón, agrupados como la ficha. No dependen de las
 * columnas visibles: se puede filtrar por un dato sin mostrarlo.
 */
export function PanelFiltrosPadron({ id, visible, cerrando, parametros, cambiar, borradores, editarTexto, planes, activos, limpiar, cerrar }) {
  const [busca, setBusca] = useState("");
  const ref = useRef(null);
  const claveBusca = busca.trim().toLocaleLowerCase("es").normalize("NFD").replace(/\p{Diacritic}/gu, "");
  const activosPorGrupo = (g) => g.columnas.filter((c) => controlesFiltroPadron(c).some((k) => parametros.has(k.clave))).length;
  const [abiertos, setAbiertos] = useState(() => new Set(GRUPOS_PADRON.filter((g, i) => i < 2 || activosPorGrupo(g)).map((g) => g.titulo)));
  useEffect(() => {
    const previo = document.activeElement;
    ref.current?.querySelector("input")?.focus();
    // Al desmontarse (tras la transición) devuelve el foco sólo si quedó perdido:
    // si la persona ya hizo clic en otra cosa, no se lo saca.
    return () => {
      const actual = document.activeElement;
      if (previo?.isConnected && (!actual || actual === document.body)) previo.focus();
    };
  }, []);
  const grupos = GRUPOS_PADRON.map((g) => ({ ...g, columnas: g.columnas.filter((c) => controlesFiltroPadron(c).length && (!claveBusca || coincide(c.label, claveBusca) || coincide(g.titulo, claveBusca))) })).filter((g) => g.columnas.length);
  const alternar = (titulo) => setAbiertos((previos) => { const nuevos = new Set(previos); if (nuevos.has(titulo)) nuevos.delete(titulo); else nuevos.add(titulo); return nuevos; });

  useAltoHastaElBorde(ref);

  return <aside ref={ref} id={id} role="dialog" aria-label="Filtros del padrón" inert={cerrando ? "" : undefined}
    onKeyDown={(e) => { if (e.key === "Escape") { e.stopPropagation(); cerrar(); } }}
    className={cn("fixed inset-y-0 right-0 z-50 flex w-full max-w-[24rem] flex-col border-l border-borde bg-superficie shadow-modal transition-[opacity,translate] duration-200 ease-salida motion-reduce:transition-none lg:sticky lg:ml-4 lg:bottom-auto lg:right-auto lg:top-6 lg:z-auto lg:h-[var(--alto-panel,calc(100dvh-10rem))] lg:w-[340px] lg:shrink-0 lg:rounded-lg lg:border lg:shadow-none", visible ? "translate-x-0 opacity-100" : "translate-x-6 opacity-0")}>
    <div className="flex items-center justify-between gap-2 border-b border-division px-4 py-3">
      <strong className="text-md">Filtros{activos.length > 0 && <span className="ml-1.5 font-normal text-texto-debil">({activos.length})</span>}</strong>
      <button type="button" aria-label="Cerrar filtros" onClick={cerrar} className="flex rounded-md p-1 text-texto-debil hover:bg-superficie-2 hover:text-texto"><Icon name="x" size={16} /></button>
    </div>
    <div className="border-b border-division px-4 py-2.5">
      <Buscador aria-label="Buscar filtro" placeholder="Buscar un dato…" valor={busca} onChange={setBusca} />
    </div>
    <div className="min-h-0 flex-1 overflow-y-auto">
      {grupos.map((g) => {
        const abierto = Boolean(claveBusca) || abiertos.has(g.titulo);
        const cuenta = activosPorGrupo(g);
        return <section key={g.titulo} className="border-b border-division last:border-b-0">
          <h3><button type="button" aria-expanded={abierto} onClick={() => alternar(g.titulo)} className="flex w-full items-center justify-between gap-2 px-4 py-2.5 text-left text-sm font-semibold text-texto-medio hover:bg-superficie-2">
            <span>{g.titulo}{cuenta > 0 && <span className="ml-2 rounded-pill bg-accent-50 px-1.5 text-xs font-semibold text-accent tabular-nums">{cuenta}</span>}</span>
            <Icon name="chevronRight" size={14} className={cn("text-texto-tenue transition-transform motion-reduce:transition-none", abierto && "rotate-90")} />
          </button></h3>
          {abierto && <div className="animate-aparecer space-y-3 px-4 pb-4 pt-1">
            {g.columnas.map((col) => <FiltroColumna key={col.key} columna={col} parametros={parametros} cambiar={cambiar} planes={planes} borradores={borradores} editarTexto={editarTexto} />)}
          </div>}
        </section>;
      })}
      {!grupos.length && <p className="px-4 py-6 text-center text-sm text-texto-debil">Ningún dato coincide con «{busca.trim()}».</p>}
    </div>
    {activos.length > 0 && <div className="border-t border-division px-4 py-2.5"><button type="button" onClick={limpiar} className="text-sm font-medium text-accent hover:underline">Limpiar todos los filtros</button></div>}
  </aside>;
}

function FiltroColumna({ columna: col, parametros, cambiar, borradores, editarTexto }) {
  const controles = controlesFiltroPadron(col);
  const valores = controles.filter((c) => c.tipo !== "vacio");
  const vacio = controles.find((c) => c.tipo === "vacio");
  const label = valores[0]?.label || col.label;
  // Filtra por si el dato está cargado, sin importar su valor (fichas incompletas).
  const selectVacio = vacio && <Select size="sm" className="w-[8.5rem] shrink-0" aria-label={`${col.label}: ¿cargado?`} title="Filtrar por si el dato está cargado o vacío" value={parametros.get(vacio.clave) || ""} onChange={(e) => cambiar(vacio.clave, e.target.value)}>
    <option value="">¿Cargado?</option><option value="true">Vacío</option><option value="false">Cargado</option>
  </Select>;
  return <div>
    <div className="mb-1 text-sm font-medium text-texto-suave">{label}</div>
    {valores[0]?.tipo === "date" ? <>
      <div className="grid grid-cols-2 gap-2">{valores.map((c) => <Input key={c.clave} size="sm" type="date" aria-label={`${label} ${c.extremo}`} title={c.extremo === "desde" ? "Desde" : "Hasta"} value={parametros.get(c.clave) || ""} onChange={(e) => cambiar(c.clave, e.target.value)} />)}</div>
      {selectVacio && <div className="mt-2">{selectVacio}</div>}
    </> : <div className="flex gap-2">
      {valores.map((c) => c.tipo === "choice"
        ? <Select key={c.clave} size="sm" className="min-w-0 flex-1" aria-label={c.clave.startsWith("flt_") ? `Filtrar ${label}` : label} value={parametros.get(c.clave) || ""} onChange={(e) => cambiar(c.clave, e.target.value)}><option value="">Todos</option>{Object.entries(c.options).map(([id, nombre]) => <option key={id} value={id}>{nombre}</option>)}</Select>
        : <Input key={c.clave} size="sm" className="min-w-0 flex-1" aria-label={`Filtrar ${label}`} type={c.tipo === "relation" ? "number" : "text"} min={c.tipo === "relation" ? 1 : undefined} step={c.tipo === "relation" ? 1 : undefined} placeholder={c.tipo === "relation" ? "ID exacto" : "Contiene…"} value={borradores[c.clave] ?? parametros.get(c.clave) ?? ""} onChange={(e) => editarTexto(c.clave, e.target.value)} />)}
      {selectVacio}
    </div>}
  </div>;
}

/**
 * En escritorio el panel llega siempre hasta 24px del borde inferior: al inicio
 * arranca debajo del título y es más bajo; al scrollear queda pegado arriba
 * (sticky top-6) y crece. Escribe `--alto-panel` sin re-renderizar.
 *
 * El borde superior sale de dónde DEBERÍA estar (su hueco o el tope del sticky),
 * no de su rect actual: al final de la tabla el sticky lo empuja hacia arriba y
 * medir ese rect agrandaría el panel cada vez más.
 */
const MARGEN = 24; // = lg:top-6
function useAltoHastaElBorde(ref) {
  useEffect(() => {
    const panel = ref.current;
    if (!panel) return;
    const scroll = document.getElementById("contenido-principal");
    let cuadro = 0;
    const medir = () => {
      cuadro = 0;
      const area = scroll ? scroll.getBoundingClientRect() : { top: 0, bottom: window.innerHeight };
      const arriba = Math.max(panel.parentElement.getBoundingClientRect().top, area.top + MARGEN);
      panel.style.setProperty("--alto-panel", `${Math.max(240, Math.round(area.bottom - arriba - MARGEN))}px`);
    };
    const pedir = () => { if (!cuadro) cuadro = requestAnimationFrame(medir); };
    medir();
    scroll?.addEventListener("scroll", pedir, { passive: true });
    window.addEventListener("resize", pedir);
    return () => {
      cancelAnimationFrame(cuadro);
      scroll?.removeEventListener("scroll", pedir);
      window.removeEventListener("resize", pedir);
    };
  }, [ref]);
}
