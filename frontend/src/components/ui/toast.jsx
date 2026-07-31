import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";

import { Icon } from "@/components/icons";
import { cn } from "@/lib/cn";

const ToastCtx = createContext(null);

const TONO = {
  ok: { clase: "border-badge-green-fg/25 bg-badge-green-bg text-badge-green-fg", icono: "enter" },
  error: { clase: "border-badge-error-fg/25 bg-badge-error-bg text-badge-error-fg", icono: "alert" },
  info: { clase: "border-accent-100 bg-accent-50 text-accent", icono: "bell" },
};

const DURACION = { ok: 3500, info: 4000, error: 6000 };

/**
 * Avisos efímeros de resultado de una acción.
 *
 * Reemplaza el patrón actual de `useState` con un div de error dentro de cada
 * pantalla: eso obliga a reservarle lugar en el layout, se pierde si el aviso
 * queda fuera del scroll, y cada pantalla lo resuelve distinto.
 *
 * Los errores duran más que los éxitos y **no se van solos si hay una acción**:
 * un fallo que desaparece antes de que lo leas es igual a no avisar.
 */
export function ToastProvider({ children }) {
  const [avisos, setAvisos] = useState([]);
  const contador = useRef(0);

  const cerrar = useCallback((id) => {
    setAvisos((xs) => xs.filter((a) => a.id !== id));
  }, []);

  const mostrar = useCallback((aviso) => {
    const id = ++contador.current;
    setAvisos((xs) => [...xs, { id, tono: "info", ...aviso }]);
    return id;
  }, []);

  const toast = useRef({
    ok: (texto, extra) => mostrar({ tono: "ok", texto, ...extra }),
    error: (texto, extra) => mostrar({ tono: "error", texto, ...extra }),
    info: (texto, extra) => mostrar({ tono: "info", texto, ...extra }),
    // Atajo para errores de la API: usa el `detail` de DRF si viene.
    deError: (e, porDefecto = "No se pudo completar la acción.") =>
      mostrar({ tono: "error", texto: e?.data?.detail || e?.message || porDefecto }),
  }).current;

  return (
    <ToastCtx.Provider value={toast}>
      {children}
      <div
        className="pointer-events-none fixed bottom-4 right-4 z-[100] flex w-[min(24rem,calc(100vw-2rem))] flex-col gap-2"
        // `polite` y no `assertive`: el aviso no debe interrumpir a quien está
        // dictando una atención.
        aria-live="polite"
        aria-atomic="false"
      >
        {avisos.map((a) => (
          <Aviso key={a.id} aviso={a} onCerrar={() => cerrar(a.id)} />
        ))}
      </div>
    </ToastCtx.Provider>
  );
}

function Aviso({ aviso, onCerrar }) {
  const t = TONO[aviso.tono] || TONO.info;
  const permanente = Boolean(aviso.accion);

  useEffect(() => {
    if (permanente) return;
    const id = setTimeout(onCerrar, DURACION[aviso.tono] ?? 4000);
    return () => clearTimeout(id);
  }, [aviso.tono, permanente, onCerrar]);

  return (
    <div
      role={aviso.tono === "error" ? "alert" : "status"}
      className={cn(
        "pointer-events-auto flex items-start gap-2.5 rounded-md border px-3 py-2.5 shadow-float",
        "animate-[fadeUp_.16s_ease]",
        t.clase,
      )}
    >
      <Icon name={t.icono} size={16} className="mt-px shrink-0" />
      <div className="min-w-0 flex-1">
        <div className="text-md font-semibold">{aviso.texto}</div>
        {aviso.detalle && <div className="mt-0.5 text-base opacity-80">{aviso.detalle}</div>}
        {aviso.accion && (
          <button
            onClick={() => { aviso.accion.onClick(); onCerrar(); }}
            className="mt-1.5 text-base font-bold underline underline-offset-2"
          >
            {aviso.accion.label}
          </button>
        )}
      </div>
      <button onClick={onCerrar} aria-label="Cerrar aviso" className="shrink-0 opacity-60 hover:opacity-100">
        <Icon name="x" size={15} />
      </button>
    </div>
  );
}

export function useToast() {
  const ctx = useContext(ToastCtx);
  if (!ctx) throw new Error("useToast necesita estar dentro de <ToastProvider>");
  return ctx;
}
