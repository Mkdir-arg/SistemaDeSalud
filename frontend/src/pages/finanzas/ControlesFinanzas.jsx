import { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useSearchParams } from "react-router-dom";
import { Icon } from "@/components/icons";
import { Button, Field, Input, Select } from "@/components/ui";

// El panel usa los mismos tokens que Popover. El portal evita que el scroll de
// la tabla lo recorte y su posición fija no desplaza filas ni formularios.
export function PanelFlotante({ titulo, icono, children, activo = false, ayuda = false, etiqueta }) {
  const [abierto, setAbierto] = useState(false);
  const [posicion, setPosicion] = useState({ left: 8, top: 8 });
  const boton = useRef(null);
  const panel = useRef(null);
  const fijado = useRef(false);
  const cierrePendiente = useRef(null);
  const omitirFoco = useRef(false);
  const id = useId();
  const cancelarCierre = () => window.clearTimeout(cierrePendiente.current);
  const cerrar = (devolverFoco = false) => {
    cancelarCierre();
    fijado.current = false;
    setAbierto(false);
    if (devolverFoco && document.activeElement !== boton.current) {
      omitirFoco.current = true;
      boton.current?.focus();
    }
  };
  const salir = () => {
    cancelarCierre();
    if (ayuda && !fijado.current) cierrePendiente.current = window.setTimeout(() => {
      if (!panel.current?.contains(document.activeElement) && document.activeElement !== boton.current) cerrar();
    }, 180);
  };
  useEffect(() => () => cancelarCierre(), []);
  useEffect(() => {
    if (!abierto) return;
    const ubicar = () => {
      const r = boton.current.getBoundingClientRect();
      const altura = panel.current?.offsetHeight || 200;
      setPosicion({ left: Math.max(8, Math.min(r.left, window.innerWidth - 336)),
        top: r.bottom + altura + 8 <= window.innerHeight ? r.bottom + 6 : Math.max(8, r.top - altura - 6) });
    };
    const cerrarFuera = (e) => {
      if (!panel.current?.contains(e.target) && !boton.current?.contains(e.target)) cerrar();
    };
    const tecla = (e) => {
      if (e.key === "Escape") { e.stopPropagation(); e.preventDefault(); cerrar(true); }
    };
    ubicar();
    if (!ayuda) (panel.current?.querySelector("input,select") || panel.current?.querySelector("button"))?.focus();
    document.addEventListener("pointerdown", cerrarFuera);
    document.addEventListener("keydown", tecla, true);
    window.addEventListener("resize", ubicar);
    window.addEventListener("scroll", ubicar, true);
    return () => {
      document.removeEventListener("pointerdown", cerrarFuera);
      document.removeEventListener("keydown", tecla, true);
      window.removeEventListener("resize", ubicar);
      window.removeEventListener("scroll", ubicar, true);
    };
  }, [abierto]);
  return <>
    <button ref={boton} type="button" aria-label={titulo} aria-expanded={abierto} aria-controls={abierto ? id : undefined}
      aria-haspopup="dialog" className={`inline-flex ${etiqueta ? "min-h-8 gap-2 px-3 text-sm" : "size-8"} shrink-0 items-center justify-center rounded-md focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent ${activo ? "text-accent bg-accent-50" : "text-texto-debil hover:bg-superficie-2"}`}
      onMouseEnter={() => { cancelarCierre(); if (ayuda) setAbierto(true); }}
      onMouseLeave={salir}
      onFocus={() => { if (omitirFoco.current) { omitirFoco.current = false; return; } if (ayuda) setAbierto(true); }}
      onBlur={(e) => { if (ayuda && !fijado.current && !panel.current?.contains(e.relatedTarget)) setAbierto(false); }}
      onClick={() => { fijado.current = !fijado.current; setAbierto(fijado.current); }}>
      {etiqueta}{icono && <Icon name={icono} size={17} />}
    </button>
    {abierto && createPortal(<div ref={panel} id={id} role="dialog" aria-label={titulo} onMouseEnter={cancelarCierre} onMouseLeave={salir}
      onBlur={(e) => { if (!e.currentTarget.contains(e.relatedTarget) && e.relatedTarget !== boton.current) cerrar(); }}
      style={posicion} className="fixed z-[100] w-[320px] max-w-[calc(100vw-16px)] max-h-[calc(100vh-16px)] overflow-y-auto rounded-lg border border-borde bg-superficie p-4 text-left text-md font-normal text-texto shadow-dropdown">
      <div className="mb-3 flex items-center justify-between gap-2"><strong>{titulo}</strong><button type="button" aria-label={`Cerrar ${titulo}`} onClick={() => cerrar(true)} className="rounded px-2 py-1 hover:bg-superficie-2">×</button></div>
      {children}
    </div>, boton.current?.closest('[aria-modal="true"]') || document.body)}
  </>;
}

export function AyudaFinanzas({ titulo = "Ayuda sobre Finanzas", children }) {
  return <PanelFlotante titulo={titulo} icono="help" ayuda><div className="space-y-3 text-texto-suave">{children}</div></PanelFlotante>;
}

export function useFiltrosFinanzas(clave, campos) {
  const [params, setParams] = useSearchParams();
  const valores = Object.fromEntries(campos.map((campo) => [campo, params.get(`${clave}_f_${campo}`) || ""]));
  const cambiar = (cambios) => setParams((previos) => {
    const nuevos = new URLSearchParams(previos);
    Object.entries(cambios).forEach(([campo, valor]) => {
      if (valor == null || valor === "") nuevos.delete(`${clave}_f_${campo}`);
      else nuevos.set(`${clave}_f_${campo}`, valor);
    });
    nuevos.delete(`${clave}_pag`);
    return nuevos;
  }, { replace: true });
  return { valores, cambiar };
}

export function FiltroColumna({ label, controles, filtros }) {
  const activo = controles.some((c) => filtros.valores[c.key]);
  return <PanelFlotante titulo={`Filtrar ${label}`} icono="filter" activo={activo}>
    <div className="space-y-3">{controles.map((c) => <Field key={c.key} label={c.label || label}>
      {c.opciones ? <Select aria-label={c.label || label} value={filtros.valores[c.key]} onChange={(e) => filtros.cambiar({ [c.key]: e.target.value })}>
        <option value="">Todos</option>{c.opciones.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </Select> : <><Input aria-label={c.label || label} type={c.type || "text"} step={c.step} min={c.min} value={filtros.valores[c.key]} onChange={(e) => filtros.cambiar({ [c.key]: e.target.value })} />
        {c.step === "0.01" && filtros.valores[c.key] && !/^-?\d+(\.\d{0,2})?$/.test(filtros.valores[c.key]) && <span role="alert" className="mt-1 block text-sm text-danger">Ingresá un importe con hasta dos decimales, sin notación exponencial.</span>}
      </>}
    </Field>)}
      {activo && <Button size="sm" variant="ghost" onClick={() => filtros.cambiar(Object.fromEntries(controles.map((c) => [c.key, ""])))}>Quitar filtro</Button>}
    </div>
  </PanelFlotante>;
}

export function FiltrosActivos({ filtros, definiciones }) {
  const activos = definiciones.filter((c) => filtros.valores[c.key]);
  if (!activos.length) return null;
  return <div className="flex flex-wrap items-center gap-2" aria-label="Filtros activos">{activos.map((c) => <button key={c.key} type="button"
    className="inline-flex items-center gap-2 rounded-pill border border-accent-100 bg-accent-50 px-3 py-1 text-sm text-accent"
    onClick={() => filtros.cambiar({ [c.key]: "" })} aria-label={`Quitar filtro ${c.label}`}>
    {c.label}: {c.opciones?.find((o) => String(o.value) === filtros.valores[c.key])?.label || filtros.valores[c.key]} <span aria-hidden="true">×</span>
  </button>)}<Button size="sm" variant="ghost" onClick={() => filtros.cambiar(Object.fromEntries(activos.map((c) => [c.key, ""])))}>Limpiar filtros</Button></div>;
}
