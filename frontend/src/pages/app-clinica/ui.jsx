import { useId } from "react";
import { Link } from "react-router-dom";

import { Icon } from "@/components/icons";

export const BASE = "/demo/app-clinica";
export const ruta = (sub = "") => (sub ? `${BASE}/${sub}` : BASE);

const FOCO = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent";
const VARIANTES = {
  primario: "hen-cta text-white",
  secundario: "border border-borde bg-superficie text-texto-medio hover:bg-accent-50",
  claro: "bg-white text-accent hover:bg-accent-50",
  peligro: "bg-danger-fuerte text-white",
  texto: "text-accent hover:bg-accent-50",
};

/**
 * Botón de la app. Con `to` es un link interno, con `href` uno externo (mapa,
 * teléfono): así cada acción lleva a donde dice y funciona abrir en otra pestaña.
 */
export function Boton({ children, to, href, onClick, variante = "primario", disabled = false, icono, className = "", ...resto }) {
  const clase = `flex min-h-11 w-full items-center justify-center gap-2 rounded-md px-4 text-sm font-semibold ${FOCO} disabled:cursor-not-allowed disabled:opacity-50 ${VARIANTES[variante]} ${className}`;
  const contenido = <>{icono && <Icon name={icono} size={17} />}{children}</>;
  if (to && !disabled) return <Link to={to} onClick={onClick} className={clase} {...resto}>{contenido}</Link>;
  if (href) return <a href={href} className={clase} {...(href.startsWith("http") ? { target: "_blank", rel: "noreferrer" } : {})} {...resto}>{contenido}</a>;
  return <button type="button" onClick={onClick} disabled={disabled} className={clase} {...resto}>{contenido}</button>;
}

/** Título de pantalla con "atrás". El destino es explícito para que un link directo no deje a nadie sin salida. */
export function Cabecera({ titulo, atras, children }) {
  return <div className="mb-6 flex items-center gap-2">
    {atras && <Link to={atras} aria-label="Volver" className={`-ml-2 flex size-10 items-center justify-center rounded-md text-texto-medio hover:bg-accent-50 ${FOCO}`}><Icon name="chevronLeft" size={22} /></Link>}
    <h1 className="min-w-0 flex-1 truncate text-lg font-bold">{titulo}</h1>
    {children}
  </div>;
}

export function Tarjeta({ children, className = "" }) {
  return <div className={`rounded-lg border border-borde bg-superficie ${className}`}>{children}</div>;
}

const INSIGNIAS = { verde: "bg-badge-green-bg text-badge-green-fg", ambar: "bg-badge-amber-bg text-badge-amber-fg", gris: "bg-badge-gray-bg text-badge-gray-fg", acento: "bg-accent-50 text-accent", rojo: "bg-badge-error-bg text-badge-error-fg" };
export function Insignia({ tono = "acento", children }) {
  return <span className={`inline-flex items-center rounded-sm px-1.5 py-0.5 text-xs font-medium ${INSIGNIAS[tono]}`}>{children}</span>;
}

/** Fila de lista. Navega con `to`, abre afuera con `href` o ejecuta `onClick`; sin nada es informativa. */
export function Fila({ titulo, detalle, to, href, onClick, insignia, icono, extremo, ultimo = false }) {
  const clase = `flex w-full items-center gap-3 px-4 py-3.5 text-left ${ultimo ? "" : "border-b border-borde"}`;
  const accionable = to || href || onClick;
  const contenido = <>
    {icono && <span className="flex size-9 flex-none items-center justify-center rounded-md bg-accent-50 text-accent"><Icon name={icono} size={18} /></span>}
    <span className="min-w-0 flex-1"><strong className="block text-sm font-medium">{titulo}</strong>{detalle && <span className="mt-0.5 block text-xs text-texto-suave">{detalle}</span>}</span>
    {insignia}
    {extremo}
    {accionable && <Icon name="chevronRight" size={16} className="flex-none text-texto-suave" />}
  </>;
  const interactiva = `${clase} hover:bg-accent-50 ${FOCO}`;
  if (to) return <Link to={to} onClick={onClick} className={interactiva}>{contenido}</Link>;
  if (href) return <a href={href} className={interactiva} {...(href.startsWith("http") ? { target: "_blank", rel: "noreferrer" } : {})}>{contenido}</a>;
  if (onClick) return <button type="button" onClick={onClick} className={interactiva}>{contenido}</button>;
  return <div className={clase}>{contenido}</div>;
}

export function Pie({ children }) { return <div className="mt-auto space-y-3 pt-8">{children}</div>; }

export function Paso({ numero, total = 3 }) {
  return <div><p className="text-xs font-semibold text-accent">Paso {numero} de {total}</p><div className="mt-2 flex gap-1">{Array.from({ length: total }, (_, i) => <span key={i} className={`h-1 flex-1 rounded-pill ${i < numero ? "bg-accent-fuerte" : "bg-accent-100"}`} />)}</div></div>;
}

export function Campo({ etiqueta, ayuda, children }) {
  return <label className="mt-5 block text-xs font-medium text-texto-medio">{etiqueta}{children}{ayuda && <span className="mt-1.5 block font-normal text-texto-suave">{ayuda}</span>}</label>;
}
export const CLASE_CAMPO = "mt-2 h-11 w-full rounded-md border border-campo-borde bg-superficie px-3 text-sm text-texto focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent-100";

/** Isotipo de la clínica: la misma cruz de la fachada de la ilustración. */
export function MarcaClinica({ size = 36 }) {
  // Un id por instancia: si todas comparten uno y la primera está oculta
  // (display: none), Chrome no pinta el degradado en las demás.
  const degradado = useId();
  return <svg width={size} height={size} viewBox="0 0 36 36" role="img" aria-label="Clínica Modelo" className="flex-none">
    <defs><linearGradient id={degradado} x1="0" y1="1" x2="1" y2="0"><stop offset="0" stopColor="#7031C7" /><stop offset="1" stopColor="#007A70" /></linearGradient></defs>
    <rect width="36" height="36" rx="10" fill={`url(#${degradado})`} />
    <path d="M15 9h6v6h6v6h-6v6h-6v-6H9v-6h6z" fill="#fff" />
  </svg>;
}

export const iniciales = (nombre = "") => nombre.trim().split(/\s+/).slice(0, 2).map((p) => p[0]?.toUpperCase()).join("") || "?";
export const primerNombre = (nombre = "") => nombre.trim().split(/\s+/)[0] || "";

export function Avatar({ nombre, size = 36 }) {
  return <span aria-hidden="true" className="flex flex-none items-center justify-center rounded-full bg-accent-100 font-bold text-accent" style={{ width: size, height: size, fontSize: size * 0.36 }}>{iniciales(nombre)}</span>;
}
