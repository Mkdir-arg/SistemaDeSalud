import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { Icon } from "@/components/icons";
import { cn } from "@/lib/cn";

/**
 * Un filtro guardado en la URL. Igual que el estado de la tabla: una vista
 * filtrada tiene que poder compartirse y sobrevivir a un F5.
 */
export function useFiltroUrl(nombre, inicial = "") {
  const [params, setParams] = useSearchParams();
  const valor = params.get(nombre) ?? inicial;
  const setValor = (v) => {
    const p = new URLSearchParams(params);
    if (v === "" || v === null || v === undefined) p.delete(nombre);
    else p.set(nombre, v);
    setParams(p, { replace: true });
  };
  return [valor, setValor];
}

/**
 * Igual que `useFiltroUrl` pero con retardo: devuelve el valor que se escribe al
 * instante (para el input) y otro que se estabiliza. Sin esto, cada tecla dispara
 * una consulta al servidor.
 */
export function useBusquedaUrl(nombre = "q", ms = 350) {
  const [valor, setValor] = useFiltroUrl(nombre);
  const [texto, setTexto] = useState(valor);

  // Si la URL cambia por fuera (atrás/adelante del navegador), seguirla.
  useEffect(() => { setTexto(valor); }, [valor]);

  useEffect(() => {
    if (texto === valor) return;
    const id = setTimeout(() => setValor(texto), ms);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [texto, ms]);

  return [texto, setTexto, valor];
}

export function Buscador({ valor, onChange, placeholder = "Buscar…", className }) {
  return (
    <div className={cn("relative", className)}>
      <Icon name="search" size={15} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
      <input
        type="search"
        value={valor}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="h-8 w-full rounded-md border border-input-border bg-white pl-8 pr-2 text-base outline-none placeholder:text-slate-400 focus:border-accent"
      />
    </div>
  );
}

/**
 * Select compacto cuya etiqueta visible es la opción «todos» («Todos los
 * estados»). Como no hay <label>, `etiqueta` da el nombre accesible: sin eso un
 * lector de pantalla anuncia solo «cuadro combinado» y no se sabe qué filtra.
 */
export function FiltroSelect({ valor, onChange, opciones, todos = "Todos", etiqueta, className }) {
  return (
    <select
      value={valor}
      onChange={(e) => onChange(e.target.value)}
      aria-label={etiqueta || todos}
      className={cn(
        "h-8 rounded-md border border-input-border bg-white px-2 text-base text-slate-700 outline-none focus:border-accent",
        valor && "border-accent-100 bg-accent-50 text-accent",
        className,
      )}
    >
      <option value="">{todos}</option>
      {opciones.map((o) => (
        <option key={o.value} value={o.value}>{o.label}</option>
      ))}
    </select>
  );
}

/** Botón para limpiar todos los filtros activos; se oculta si no hay ninguno. */
export function LimpiarFiltros({ activos, onLimpiar }) {
  if (!activos) return null;
  return (
    <button
      type="button"
      onClick={onLimpiar}
      className="flex items-center gap-1 rounded-md px-2 py-1 text-sm font-semibold text-slate-500 hover:bg-subtle hover:text-slate-700"
    >
      <Icon name="x" size={13} /> Limpiar {activos > 1 ? `(${activos})` : ""}
    </button>
  );
}
