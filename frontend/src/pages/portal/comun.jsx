import { useId } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { Icon } from "@/components/icons";
import { mensajePortal, rutaSegunCuenta, sesionPortal, useCuentaPortal } from "@/api/portal";
import { Boton, Campo, CLASE_CAMPO } from "@/pages/app-clinica/ui";

// Nombre neutro hasta que se acuerde la marca (#59).
export const NOMBRE_PORTAL = "Mi portal de salud";

export const soloDigitos = (s = "") => s.replace(/\D/g, "");
export const formatoDni = (dni) => (dni ? Number(dni).toLocaleString("es-AR") : "");

export function Pantalla({ children }) {
  return <div className="flex flex-1 flex-col px-5 pb-6 pt-4">{children}</div>;
}

export function Alerta({ children }) {
  if (!children) return null;
  return <p role="alert" className="mt-5 rounded-md bg-badge-error-bg p-3 text-sm text-badge-error-fg">{children}</p>;
}

export function Exito({ children }) {
  return <p role="status" className="mt-5 rounded-md bg-badge-green-bg p-3 text-sm text-badge-green-fg">{children}</p>;
}

export function Aviso({ children }) {
  return <p role="status" className="mt-5 rounded-md bg-badge-amber-bg p-3 text-sm text-badge-amber-fg">{children}</p>;
}

export function Cargando({ texto }) {
  return <div role="status" className="flex flex-1 flex-col items-center justify-center gap-4 py-16 text-center">
    <span aria-hidden="true" className="size-9 rounded-full border-4 border-accent-100 border-t-accent motion-safe:animate-spin" />
    <p className="text-sm font-medium text-texto-medio">{texto}</p>
  </div>;
}

/** Pantalla de resultado: un ícono, un título y qué hacer ahora. */
export function Resultado({ icono = "alert", tono = "error", titulo, children, acciones }) {
  const color = tono === "ok" ? "bg-badge-green-bg text-badge-green-fg" : tono === "aviso" ? "bg-badge-amber-bg text-badge-amber-fg" : "bg-badge-error-bg text-badge-error-fg";
  return <div className="flex flex-1 flex-col">
    <span className={`mt-4 flex size-14 items-center justify-center rounded-full ${color}`}><Icon name={icono} size={28} /></span>
    <h2 className="mt-5 text-xl font-bold">{titulo}</h2>
    <div className="mt-2 space-y-2 text-sm leading-relaxed text-texto-suave">{children}</div>
    {acciones && <div className="mt-auto space-y-3 pt-8">{acciones}</div>}
  </div>;
}

/**
 * Campo de formulario con su error debajo. El error va FUERA del <label> (si
 * no, pasa a ser parte del nombre del campo) y se asocia al input con
 * `aria-describedby`, para que el lector de pantalla lo lea al enfocarlo.
 */
export function CampoTexto({ etiqueta, ayuda, error, className = "", ...input }) {
  const id = useId();
  return <div>
    <Campo etiqueta={etiqueta} ayuda={ayuda}>
      <input {...input} aria-invalid={error ? true : undefined} aria-describedby={error ? id : undefined} className={`${CLASE_CAMPO} text-base ${error ? "border-danger-fuerte" : ""} ${className}`} />
    </Campo>
    {error && <p id={id} className="mt-1.5 text-xs text-badge-error-fg">{error}</p>}
  </div>;
}

/**
 * Puerta de las pantallas con sesión del portal.
 *
 * Sin sesión, a ingresar. Con sesión, cada cuenta tiene UNA pantalla que le
 * corresponde según lo que completó (email, identidad, lista): si se entra a
 * otra por un link o con «atrás», se la lleva a la suya.
 */
export function ConCuenta({ children }) {
  const { pathname } = useLocation();
  const cuenta = useCuentaPortal();
  if (!sesionPortal.access) return <Navigate to="/mi/ingresar" replace />;
  if (cuenta.isPending) return <Cargando texto="Cargando tu cuenta…" />;
  if (cuenta.isError) return <Pantalla>
    <Alerta>{mensajePortal(cuenta.error, "No pudimos cargar tu cuenta.")}</Alerta>
    <div className="mt-5"><Boton variante="secundario" onClick={() => cuenta.refetch()}>Reintentar</Boton></div>
  </Pantalla>;
  const destino = rutaSegunCuenta(cuenta.data);
  if (destino !== pathname.replace(/\/+$/, "")) return <Navigate to={destino} replace />;
  return children(cuenta.data);
}
