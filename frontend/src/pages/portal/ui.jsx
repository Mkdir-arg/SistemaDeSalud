import { Link } from "react-router-dom";

import { Icon } from "@/components/icons";

// Piezas del portal del paciente, tomadas del Figma de HEN («05 · App clínica
// (MVP)», nodo 61-132). Los colores y las sombras son tokens del DS. Lo que el
// DS de la aplicación no tiene —la escala de texto de celular de Figma y sus
// radios— vive acá, en `TAMANO` y `RADIO`, y no se usa fuera del portal.
export const TAMANO = {
  t13: "text-[13px] leading-5",
  t15: "text-[15px] leading-[23px]",
  t15cuerpo: "text-[15px] leading-[22px]",
  t16: "text-[16px] leading-6",
  t17: "text-[17px] leading-[26px]",
  t22: "text-[22px] leading-7",
};
export const RADIO = {
  tarjeta: "rounded-[16px]",
  // Las variantes van escritas enteras: Tailwind lee las clases como texto y
  // no ve un «md:» que se arma en tiempo de ejecución.
  hojaArribaMd: "rounded-t-[24px] md:rounded-[24px]",
  marcoMd: "md:rounded-[28px]",
  selector: "rounded-[10px]",
  pestana: "rounded-[8px]",
  asa: "rounded-[2px]",
};

export const TEXTO = {
  /** Título de pantalla, al lado del «atrás». */
  cabecera: `${TAMANO.t17} font-semibold text-texto`,
  /** Título principal de una pantalla («Hola, Andrea»). */
  titulo: "text-xxl leading-8 font-bold text-texto",
  /** Párrafo debajo del título. */
  cuerpo: `${TAMANO.t15cuerpo} text-texto-suave`,
  filaTitulo: `${TAMANO.t15} font-medium text-texto`,
  // El gris de Figma (#766E94) se reemplaza por el token semántico
  // `texto-tenue`, que cumple AA sobre blanco y sobre el fondo lila
  // (docs/FUNDACION-FRONTEND.md, «Deuda conocida»).
  filaDetalle: `${TAMANO.t13} text-texto-tenue`,
  nota: "text-sm leading-[21px] text-texto-suave",
};

const FOCO = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent";
// Un link a otro sitio (no `tel:` ni `mailto:`) se abre en otra pestaña.
const destinoExterno = (href) => (href.startsWith("http") ? { target: "_blank", rel: "noreferrer" } : {});
const VARIANTES = {
  primario: "hen-cta text-white",
  secundario: "border border-borde bg-superficie text-texto-suave hover:bg-fondo",
  // Sobre la tarjeta degradada: fondo lila claro, como en Figma.
  claro: "border border-borde bg-fondo text-texto-suave hover:bg-superficie",
  peligro: "bg-danger-fuerte text-white",
  texto: "text-texto hover:bg-accent-50",
};

/**
 * Botón de la app. Con `to` es un link interno, con `href` uno externo (mapa,
 * teléfono): así cada acción lleva a donde dice y funciona abrir en otra pestaña.
 * `chico` es el de 14 px que va dentro de una tarjeta.
 */
export function Boton({ children, to, href, onClick, variante = "primario", chico = false, disabled = false, icono, className = "", ...resto }) {
  const tamano = chico ? "min-h-10 px-4 text-sm leading-5" : `min-h-12 px-5 ${TAMANO.t16}`;
  const clase = `flex w-full items-center justify-center gap-1.5 rounded-md font-medium ${tamano} ${FOCO} disabled:cursor-not-allowed disabled:opacity-50 ${VARIANTES[variante]} ${className}`;
  const contenido = <>{icono && <Icon name={icono} size={chico ? 16 : 18} />}{children}</>;
  if (to && !disabled) return <Link to={to} onClick={onClick} className={clase} {...resto}>{contenido}</Link>;
  if (href) return <a href={href} className={clase} {...destinoExterno(href)} {...resto}>{contenido}</a>;
  return <button type="button" onClick={onClick} disabled={disabled} className={clase} {...resto}>{contenido}</button>;
}

/** Título de pantalla con "atrás". El destino es explícito para que un link directo no deje a nadie sin salida. */
export function Cabecera({ titulo, atras, children }) {
  return <div className="-mx-3 mb-3 flex items-center gap-1">
    {atras && <Link to={atras} aria-label="Volver" className={`flex size-10 flex-none items-center justify-center rounded-md text-texto hover:bg-accent-50 ${FOCO}`}><Icon name="chevronLeft" size={20} /></Link>}
    <h1 className={`min-w-0 flex-1 truncate ${atras ? "" : "pl-3"} ${TEXTO.cabecera}`}>{titulo}</h1>
    {children}
  </div>;
}

export function Tarjeta({ children, className = "" }) {
  return <div className={`${RADIO.tarjeta} border border-borde bg-superficie ${className}`}>{children}</div>;
}

const INSIGNIAS = {
  verde: "border-badge-green-bg bg-badge-green-bg text-badge-green-fg",
  ambar: "border-badge-amber-bg bg-badge-amber-bg text-badge-amber-fg",
  gris: "border-borde bg-badge-gray-bg text-badge-gray-fg",
  acento: "border-accent-100 bg-accent-50 text-accent",
  rojo: "border-badge-error-bg bg-badge-error-bg text-badge-error-fg",
};
export function Insignia({ tono = "acento", children }) {
  return <span className={`inline-flex flex-none items-center rounded-sm border px-1 py-0.5 text-xs font-medium leading-4 ${INSIGNIAS[tono]}`}>{children}</span>;
}

/**
 * Fila de lista. Navega con `to`, abre afuera con `href` o ejecuta `onClick`; sin nada es informativa.
 * `extremo` va a la derecha, antes de la flecha (una `Insignia`, el estado de un turno).
 */
export function Fila({ titulo, detalle, to, href, onClick, extremo, ultimo = false }) {
  const clase = `flex w-full items-center gap-3 px-4 py-3.5 text-left ${ultimo ? "" : "border-b border-borde"}`;
  const accionable = to || href || onClick;
  const contenido = <>
    <span className="min-w-0 flex-1"><strong className={`block ${TEXTO.filaTitulo}`}>{titulo}</strong>{detalle && <span className={`mt-0.5 block ${TEXTO.filaDetalle}`}>{detalle}</span>}</span>
    {extremo}
    {accionable && <Icon name="chevronRight" size={16} className="flex-none text-texto-suave" />}
  </>;
  const interactiva = `${clase} hover:bg-fondo ${FOCO}`;
  if (to) return <Link to={to} onClick={onClick} className={interactiva}>{contenido}</Link>;
  if (href) return <a href={href} className={interactiva} {...destinoExterno(href)}>{contenido}</a>;
  if (onClick) return <button type="button" onClick={onClick} className={interactiva}>{contenido}</button>;
  return <div className={clase}>{contenido}</div>;
}

export function Pie({ children }) { return <div className="mt-auto space-y-3 pt-8">{children}</div>; }

export function Paso({ numero, total = 3 }) {
  return <div><p className="text-xs font-semibold text-accent">Paso {numero} de {total}</p><div className="mt-2 flex gap-1">{Array.from({ length: total }, (_, i) => <span key={i} className={`h-1 flex-1 rounded-pill ${i < numero ? "bg-accent-fuerte" : "bg-accent-100"}`} />)}</div></div>;
}

export function Campo({ etiqueta, ayuda, children }) {
  return <label className="mt-4 block text-sm font-medium leading-[21px] text-texto">{etiqueta}{children}{ayuda && <span className={`mt-1.5 block font-normal text-texto-suave ${TAMANO.t13}`}>{ayuda}</span>}</label>;
}
export const CLASE_CAMPO = "mt-1.5 h-12 w-full rounded-md border border-borde bg-fondo px-3.5 text-[16px] leading-6 font-normal text-texto focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent-100";
