// Componentes base de UI.
//
// Migrados a Tailwind sobre tokens SEMÁNTICOS, así que responden al tema. Todos
// siguen aceptando `style` además de `className`: las pantallas que faltan migrar
// les pasan estilos inline y no se pueden romper hasta que les toque el turno.
import { useEffect, useRef } from "react";

import { cn } from "@/lib/cn";
import { iniciales } from "../theme";
import { Icon } from "./icons";

// --------------------------------------------------------------------------- //
// Acciones
// --------------------------------------------------------------------------- //
const BOTON_VARIANTE = {
  // El primario usa el relleno de marca con su color de texto: `accent` a secas
  // es claro en tema oscuro y el blanco encima no llegaría a contraste.
  primary: "bg-accent-fuerte text-sobre-accent hover:bg-accent-hover",
  secondary: "bg-accent-50 text-accent border border-accent-100 hover:bg-accent-100",
  dashed: "border-[1.5px] border-dashed border-accent-100 text-accent hover:bg-accent-50",
  danger: "bg-danger-fuerte text-sobre-danger hover:brightness-110",
  ghost: "text-texto-suave hover:bg-superficie-2 hover:text-texto",
};

export function Button({ variant = "primary", size = "md", className, children, disabled, ...props }) {
  return (
    <button
      disabled={disabled}
      className={cn(
        "inline-flex items-center justify-center gap-1.5 rounded-md font-semibold transition-colors",
        size === "sm" ? "h-8 px-3 text-base" : "h-10 px-4.5 text-md",
        disabled
          ? "cursor-not-allowed bg-division text-texto-tenue"
          : BOTON_VARIANTE[variant] || BOTON_VARIANTE.primary,
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
}

// --------------------------------------------------------------------------- //
// Indicadores
// --------------------------------------------------------------------------- //
// Mapa tono → clases. Tiene que ser un mapa de strings COMPLETOS y estáticos:
// Tailwind escanea el código fuente como texto, así que `bg-badge-${tono}-bg` no
// genera nada (no existe esa clase en el archivo). Es la convención para todo
// componente con variantes.
const BADGE_TONO = {
  neutral: "bg-badge-neutral-bg text-badge-neutral-fg",
  info: "bg-badge-info-bg text-badge-info-fg",
  amber: "bg-badge-amber-bg text-badge-amber-fg",
  green: "bg-badge-green-bg text-badge-green-fg",
  gray: "bg-badge-gray-bg text-badge-gray-fg",
  error: "bg-badge-error-bg text-badge-error-fg",
};

export function Badge({ tone = "neutral", className, children }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 whitespace-nowrap rounded-pill px-2.5 py-[3px]",
        "text-sm font-semibold",
        BADGE_TONO[tone] || BADGE_TONO.neutral,
        className,
      )}
    >
      {/* El punto toma el color del texto: una variante menos que mantener. */}
      <span className="size-1.5 rounded-full bg-current" />
      {children}
    </span>
  );
}

export function Card({ className, children, ...props }) {
  return (
    <div className={cn("rounded-lg border border-borde bg-superficie", className)} {...props}>
      {children}
    </div>
  );
}

export function Mono({ className, children, ...props }) {
  return <span className={cn("font-mono", className)} {...props}>{children}</span>;
}

export function Avatar({ nombre, i = 0, size = 32 }) {
  return (
    <span
      className="inline-flex shrink-0 items-center justify-center rounded-pill font-bold text-white"
      style={{
        width: size,
        height: size,
        fontSize: size * 0.38,
        // Paleta rotativa: el índice es dinámico, así que no puede ser una clase
        // (Tailwind no vería `bg-avatar-${i}`). La variable sí sigue al tema.
        background: `var(--color-avatar-${(i % 6) + 1})`,
      }}
    >
      {iniciales(nombre)}
    </span>
  );
}

// --------------------------------------------------------------------------- //
// Formulario
// --------------------------------------------------------------------------- //
export function Field({ label, hint, children }) {
  return (
    <label className="block">
      {label && <div className="mb-1.5 text-base font-semibold text-texto-suave">{label}</div>}
      {children}
      {hint && <div className="mt-1 text-sm text-texto-tenue">{hint}</div>}
    </label>
  );
}

const CONTROL =
  "w-full rounded-md border border-campo-borde bg-superficie text-texto outline-none " +
  "placeholder:text-texto-tenue focus:border-accent disabled:bg-superficie-2 disabled:text-texto-tenue";

export function Input({ className, size = "md", ...props }) {
  return (
    <input
      className={cn(CONTROL, size === "sm" ? "h-8 px-3 text-base" : "h-10 px-3 text-md", className)}
      {...props}
    />
  );
}

export function Textarea({ className, ...props }) {
  return <textarea className={cn(CONTROL, "min-h-21 resize-y px-3 py-2.5 text-md", className)} {...props} />;
}

export function Select({ className, size = "md", children, ...props }) {
  return (
    <select
      className={cn(CONTROL, size === "sm" ? "h-8 px-2 text-base" : "h-10 px-2.5 text-md", className)}
      {...props}
    >
      {children}
    </select>
  );
}

export function Checkbox({ checked, onChange, label, className, ...props }) {
  return (
    <label className={cn("flex cursor-pointer items-center gap-2.5 text-md", className)}>
      <input
        type="checkbox"
        checked={checked}
        onChange={onChange}
        className="size-4 shrink-0 cursor-pointer accent-accent"
        {...props}
      />
      {label}
    </label>
  );
}

// --------------------------------------------------------------------------- //
// Estados
// --------------------------------------------------------------------------- //
export function Spinner({ label = "Cargando…" }) {
  return (
    <div className="flex flex-col items-center gap-3 p-10 text-center text-md text-texto-debil" role="status">
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" className="animate-spin" aria-hidden="true">
        <circle cx="12" cy="12" r="9" stroke="var(--color-division)" strokeWidth="3" />
        <path d="M21 12a9 9 0 0 0-9-9" stroke="var(--color-accent)" strokeWidth="3" strokeLinecap="round" />
      </svg>
      {label}
    </div>
  );
}

/** Alias histórico de `EstadoVacio`. Se conserva porque lo usan las pantallas
 *  que faltan migrar; al terminar la Fase 1 se borra. */
export function EmptyState({ title, hint }) {
  return (
    <div className="px-xxl py-12 text-center">
      <div className="text-lg font-bold text-texto-suave">{title}</div>
      {hint && <div className="mt-1.5 text-base text-texto-debil">{hint}</div>}
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Diálogo
// --------------------------------------------------------------------------- //
export function Modal({ title, onClose, children, footer, width = 460 }) {
  const ref = useRef(null);

  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") onClose?.(); };
    window.addEventListener("keydown", onKey);
    ref.current?.focus();
    // Bloquea el scroll del fondo: si no, la rueda mueve la página de atrás y el
    // diálogo parece flotar sobre contenido que se desliza.
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = overflow;
    };
  }, [onClose]);

  return (
    <div
      onMouseDown={onClose}
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink/45 p-lg animate-[fadeIn_.12s_ease]"
    >
      <div
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-label={typeof title === "string" ? title : undefined}
        tabIndex={-1}
        onMouseDown={(e) => e.stopPropagation()}
        style={{ width }}
        className="max-h-[90vh] max-w-full overflow-auto rounded-lg bg-superficie shadow-modal outline-none animate-[fadeUp_.16s_ease]"
      >
        <div className="flex items-center justify-between border-b border-division px-xl py-lg">
          <div className="text-lg font-bold">{title}</div>
          <button onClick={onClose} aria-label="Cerrar" className="flex rounded-sm p-1 text-texto-debil hover:text-texto">
            <Icon name="x" size={18} />
          </button>
        </div>
        <div className="p-xl">{children}</div>
        {footer && (
          <div className="flex justify-end gap-2.5 border-t border-division px-xl py-lg">{footer}</div>
        )}
      </div>
    </div>
  );
}

/**
 * Confirmación de una acción que no se puede deshacer.
 *
 * Existe para que cada pantalla no vuelva a inventar su propio modal de «¿seguro?»
 * con textos y botones distintos. El botón de confirmar dice QUÉ hace («Cancelar
 * caso»), no «Aceptar»: en un diálogo de cancelación, un botón que dice
 * «Cancelar» es ambiguo hasta el absurdo.
 */
export function ConfirmDialog({
  title, children, confirmar = "Confirmar", volver = "Volver",
  peligroso = false, cargando = false, onConfirmar, onClose,
}) {
  return (
    <Modal
      title={title}
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={cargando}>{volver}</Button>
          <Button variant={peligroso ? "danger" : "primary"} onClick={onConfirmar} disabled={cargando}>
            {cargando ? "…" : confirmar}
          </Button>
        </>
      }
    >
      <div className="text-md text-texto-suave">{children}</div>
    </Modal>
  );
}

// --------------------------------------------------------------------------- //
// Tabla simple
// --------------------------------------------------------------------------- //
/**
 * Tabla sin paginación. Solo para listas cortas y acotadas por naturaleza (los
 * boxes de un área, las opciones de un formulario).
 *
 * Para cualquier listado de un recurso va `TablaRecurso` de `ui/tabla.jsx`: esta
 * no pagina, y mostrar los primeros 25 de una lista larga descartando el resto
 * en silencio fue exactamente el bug que motivó la fundación nueva.
 */
export function Table({ columns, rows, onRowClick, vacio = "Sin registros" }) {
  if (!rows.length) return <EmptyState title={vacio} />;
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-md">
        <thead>
          <tr className="bg-superficie-2 text-left">
            {columns.map((c) => (
              <th key={c.key} className="whitespace-nowrap px-lg py-3 text-sm font-semibold text-texto-debil">
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr
              key={r.id}
              onClick={onRowClick ? () => onRowClick(r) : undefined}
              className={cn(
                "border-t border-division",
                onRowClick && "cursor-pointer hover:bg-superficie-2",
              )}
            >
              {columns.map((c) => (
                <td key={c.key} className="px-lg py-3.5 align-middle">
                  {c.render ? c.render(r) : r[c.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Stepper
// --------------------------------------------------------------------------- //
export function Stepper({ steps, current }) {
  return (
    <div className="flex items-center">
      {steps.map((s, i) => {
        const hecho = i < current;
        const actual = i === current;
        return (
          <div key={i} className={cn("flex items-center", i < steps.length - 1 && "flex-1")}>
            <div className="flex flex-col items-center gap-1.5">
              <div
                className={cn(
                  "flex size-7 shrink-0 items-center justify-center rounded-pill text-sm font-bold",
                  hecho && "bg-accent-fuerte text-sobre-accent",
                  actual && "border-2 border-accent bg-superficie text-accent ring-4 ring-accent/15",
                  !hecho && !actual && "border-2 border-borde bg-superficie text-texto-tenue",
                )}
              >
                {hecho ? "✓" : i + 1}
              </div>
              <div
                className={cn(
                  "whitespace-nowrap text-sm",
                  actual ? "font-bold text-accent" : hecho ? "font-medium text-texto-suave" : "font-medium text-texto-tenue",
                )}
              >
                {s.label}
              </div>
            </div>
            {i < steps.length - 1 && (
              <div className={cn("mb-[22px] h-0.5 min-w-6 flex-1 mx-3", hecho ? "bg-accent" : "bg-borde")} />
            )}
          </div>
        );
      })}
    </div>
  );
}
