import { useId } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { Icon } from "@/components/icons";
import { mensajePortal, rutaSegunCuenta, sesionPortal, useCuentaPortal } from "@/api/portal";
import { Boton, Campo, CLASE_CAMPO, RADIO, TAMANO } from "./ui";

// Nombre neutro hasta que se acuerde la marca (#59).
export const NOMBRE_PORTAL = "Mi portal de salud";

export const soloDigitos = (s = "") => s.replace(/\D/g, "");
// Con puntos si es un número; si no (pasaporte, o los documentos ficticios de la demo), tal cual.
export const formatoDni = (dni) => (!dni ? "" : /^\d+$/.test(dni) ? Number(dni).toLocaleString("es-AR") : dni);

export function Pantalla({ children }) {
  return <div className="flex flex-1 flex-col px-5 pb-8 pt-4">{children}</div>;
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

/**
 * Carga, error y vacío de una consulta de la app. El error deja reintentar; un
 * 401 nunca llega acá: el cliente avisa que la sesión venció y el marco lleva a
 * ingresar.
 */
export function Consulta({ consulta, cargando, error, vacio, children }) {
  if (consulta.isPending) return <Cargando texto={cargando} />;
  // Si ya había datos, una consulta que vuelve a fallar no los tapa: el llamado
  // se pide cada 5 segundos y un corte de un instante no puede borrar el aviso.
  if (consulta.isError && consulta.data === undefined) return <ErrorConsulta consulta={consulta} texto={error} />;
  if (vacio && Array.isArray(consulta.data) && consulta.data.length === 0) return vacio;
  return children(consulta.data);
}

export function ErrorConsulta({ consulta, texto }) {
  return <div role="alert" className={`flex flex-col items-center ${RADIO.tarjeta} border border-borde bg-superficie p-6 text-center`}>
    <span className="flex size-12 items-center justify-center rounded-full bg-badge-error-bg text-badge-error-fg"><Icon name="alert" size={22} /></span>
    <p className="mt-3 text-sm font-semibold">{texto}</p>
    <p className="mt-1 text-xs text-texto-suave">{mensajePortal(consulta.error, "Revisá tu conexión e intentá de nuevo.")}</p>
    <div className="mt-4 w-full"><Boton variante="secundario" icono="refresh" onClick={() => consulta.refetch()} disabled={consulta.isFetching}>Reintentar</Boton></div>
  </div>;
}

/** Lo que se ve cuando no hay nada: un ícono, qué pasa y, si hace falta, por qué. */
export function Vacio({ icono, titulo, children }) {
  return <div className={`flex flex-col items-center ${RADIO.tarjeta} border border-dashed border-borde bg-superficie p-6 text-center`}>
    <span className="flex size-12 items-center justify-center rounded-full bg-accent-50 text-accent"><Icon name={icono} size={22} /></span>
    <p className="mt-3 text-sm font-semibold">{titulo}</p>
    {children && <p className="mt-1 text-xs leading-relaxed text-texto-suave">{children}</p>}
  </div>;
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
    <h2 className="mt-5 text-xxl font-bold leading-8">{titulo}</h2>
    <div className={`mt-2 space-y-2 ${TAMANO.t15cuerpo} text-texto-suave`}>{children}</div>
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
      <input {...input} aria-invalid={error ? true : undefined} aria-describedby={error ? id : undefined} className={`${CLASE_CAMPO} ${error ? "border-danger-fuerte" : ""} ${className}`} />
    </Campo>
    {error && <p id={id} className="mt-1.5 text-xs text-badge-error-fg">{error}</p>}
  </div>;
}

/**
 * Puertas de las pantallas con sesión del portal. Las dos mandan a ingresar si
 * no hay sesión; difieren en a quién dejan pasar:
 * - `PasoDeLaCuenta`: mientras le falta validar la identidad, la cuenta tiene
 *   UNA pantalla que le corresponde; si se entra a otra por un link o con
 *   «atrás», se la lleva a la suya. Con la identidad validada, al inicio.
 * - `ConIdentidadValidada`: las pantallas de la app; sin validar, a validar.
 */
export function PasoDeLaCuenta({ children }) {
  const { pathname } = useLocation();
  return <CuentaCargada>{(cuenta) => {
    const destino = rutaSegunCuenta(cuenta);
    return destino === pathname.replace(/\/+$/, "") ? children(cuenta) : <Navigate to={destino} replace />;
  }}</CuentaCargada>;
}

export function ConIdentidadValidada({ children }) {
  return <CuentaCargada>{(cuenta) => (
    cuenta.identidad === "validada" ? children(cuenta) : <Navigate to={rutaSegunCuenta(cuenta)} replace />
  )}</CuentaCargada>;
}

function CuentaCargada({ children }) {
  const cuenta = useCuentaPortal();
  if (!sesionPortal.access) return <Navigate to="/mi/ingresar" replace />;
  if (cuenta.isPending) return <Cargando texto="Cargando tu cuenta…" />;
  if (cuenta.isError) return <Pantalla>
    <Alerta>{mensajePortal(cuenta.error, "No pudimos cargar tu cuenta.")}</Alerta>
    <div className="mt-5"><Boton variante="secundario" onClick={() => cuenta.refetch()}>Reintentar</Boton></div>
  </Pantalla>;
  return children(cuenta.data);
}
