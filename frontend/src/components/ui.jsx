// Componentes base de UI. Estilos calcados del "Sistema de diseño" de Cauce.
import { useEffect, useRef } from "react";
import { avatarColors, badgeTone, color, font, iniciales, radius, shadow, type } from "../theme";
import { Icon } from "./icons";

export function Button({ variant = "primary", size = "md", children, style, disabled, ...props }) {
  const base = {
    height: size === "sm" ? 32 : 40,
    padding: size === "sm" ? "0 12px" : "0 18px",
    borderRadius: radius.md,
    fontSize: size === "sm" ? type.base : type.md,
    fontWeight: 600,
    fontFamily: font.sans,
    cursor: disabled ? "not-allowed" : "pointer",
    border: "none",
    transition: ".12s",
  };
  const variants = {
    primary: { background: color.accent, color: "#fff" },
    // Secundario: misma familia índigo que el primario, pero más claro.
    secondary: { background: color.accent50, color: color.accent, border: `1px solid ${color.accent100}` },
    dashed: { background: "none", border: "1.5px dashed #C7CDF2", color: color.accent },
    danger: { background: color.danger, color: "#fff" },
    disabled: { background: "#EEF0F3", color: color.slate400 },
  };
  const v = disabled ? variants.disabled : variants[variant] || variants.primary;
  return (
    <button style={{ ...base, ...v, ...style }} disabled={disabled} {...props}>
      {children}
    </button>
  );
}

export function Badge({ tone = "neutral", children }) {
  const t = badgeTone[tone] || badgeTone.neutral;
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        padding: "3px 10px",
        borderRadius: radius.pill,
        fontSize: type.sm,
        fontWeight: 600,
        background: t.bg,
        color: t.fg,
        whiteSpace: "nowrap",
      }}
    >
      <span style={{ width: 6, height: 6, borderRadius: "50%", background: t.fg }} />
      {children}
    </span>
  );
}

export function Card({ children, style, ...props }) {
  return (
    <div
      style={{
        background: "#fff",
        border: `1px solid ${color.border}`,
        borderRadius: radius.lg,
        ...style,
      }}
      {...props}
    >
      {children}
    </div>
  );
}

export function Field({ label, children }) {
  return (
    <label style={{ display: "block" }}>
      {label && (
        <div style={{ fontSize: type.base, fontWeight: 600, color: color.slate600, marginBottom: 6 }}>
          {label}
        </div>
      )}
      {children}
    </label>
  );
}

export function Input({ style, size = "md", ...props }) {
  return (
    <input
      style={{
        height: size === "sm" ? 32 : 40,
        width: "100%",
        border: `1px solid ${color.inputBorder}`,
        borderRadius: radius.md,
        padding: "0 12px",
        fontSize: size === "sm" ? type.base : type.md,
        fontFamily: font.sans,
        outline: "none",
        boxSizing: "border-box",
        ...style,
      }}
      onFocus={(e) => (e.target.style.border = `1px solid ${color.accent}`)}
      onBlur={(e) => (e.target.style.border = `1px solid ${color.inputBorder}`)}
      {...props}
    />
  );
}

export function Textarea({ style, ...props }) {
  return (
    <textarea
      style={{
        width: "100%",
        minHeight: 84,
        border: `1px solid ${color.inputBorder}`,
        borderRadius: radius.md,
        padding: "10px 12px",
        fontSize: type.md,
        fontFamily: font.sans,
        outline: "none",
        boxSizing: "border-box",
        resize: "vertical",
        ...style,
      }}
      {...props}
    />
  );
}

export function Select({ style, size = "md", children, ...props }) {
  return (
    <select
      style={{
        height: size === "sm" ? 32 : 40,
        width: "100%",
        border: `1px solid ${color.inputBorder}`,
        borderRadius: radius.md,
        padding: "0 10px",
        fontSize: size === "sm" ? type.base : type.md,
        fontFamily: font.sans,
        outline: "none",
        background: "#fff",
        boxSizing: "border-box",
        ...style,
      }}
      {...props}
    >
      {children}
    </select>
  );
}

// Checkbox con el acento de marca y un label opcional. Reemplaza el control
// nativo azul-sistema que desentonaba en los paneles.
export function Checkbox({ checked, onChange, label, style, ...props }) {
  return (
    <label style={{ display: "flex", alignItems: "center", gap: 9, cursor: "pointer", fontSize: type.md, ...style }}>
      <input
        type="checkbox"
        checked={checked}
        onChange={onChange}
        style={{ width: 16, height: 16, accentColor: color.accent, cursor: "pointer", flex: "none" }}
        {...props}
      />
      {label}
    </label>
  );
}

export function Mono({ children, style }) {
  return <span style={{ fontFamily: font.mono, ...style }}>{children}</span>;
}

export function Avatar({ nombre, i = 0, size = 32 }) {
  return (
    <span
      style={{
        width: size,
        height: size,
        borderRadius: "50%",
        flex: "none",
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        fontSize: size * 0.38,
        fontWeight: 700,
        color: "#fff",
        background: avatarColors[i % avatarColors.length],
      }}
    >
      {iniciales(nombre)}
    </span>
  );
}

// Stepper horizontal de ejecución. `steps` = [{label}], `current` = índice.
export function Stepper({ steps, current }) {
  return (
    <div style={{ display: "flex", alignItems: "center" }}>
      {steps.map((s, i) => {
        const st = i < current ? "done" : i === current ? "current" : "todo";
        const dot =
          st === "done"
            ? { background: color.accent, color: "#fff", border: "none" }
            : st === "current"
            ? {
                background: "#fff",
                border: `2px solid ${color.accent}`,
                color: color.accent,
                boxShadow: "0 0 0 4px rgba(57,73,192,.13)",
              }
            : { background: "#fff", border: "2px solid #DDE0E6", color: "#A4ABB8" };
        return (
          <div key={i} style={{ display: "flex", alignItems: "center", flex: i < steps.length - 1 ? 1 : "none" }}>
            <div style={{ display: "flex", alignItems: "center", flexDirection: "column", gap: 6 }}>
              <div
                style={{
                  width: 28,
                  height: 28,
                  borderRadius: "50%",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 12.5,
                  fontWeight: 700,
                  flex: "none",
                  ...dot,
                }}
              >
                {st === "done" ? "✓" : i + 1}
              </div>
              <div
                style={{
                  fontSize: 12,
                  fontWeight: st === "current" ? 700 : 500,
                  color: st === "current" ? color.accent : st === "done" ? color.slate600 : "#A4ABB8",
                  whiteSpace: "nowrap",
                }}
              >
                {s.label}
              </div>
            </div>
            {i < steps.length - 1 && (
              <div
                style={{
                  flex: 1,
                  height: 2,
                  minWidth: 24,
                  margin: "0 12px",
                  marginBottom: 22,
                  background: i < current ? color.accent : "#E2E5EA",
                }}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

export function Spinner({ label = "Cargando…" }) {
  return (
    <div style={{ padding: 40, textAlign: "center", color: color.slate500, fontSize: type.md, display: "flex", flexDirection: "column", alignItems: "center", gap: 12 }}>
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" style={{ animation: "spin 0.7s linear infinite" }} aria-hidden="true">
        <circle cx="12" cy="12" r="9" stroke={color.divider} strokeWidth="3" />
        <path d="M21 12a9 9 0 0 0-9-9" stroke={color.accent} strokeWidth="3" strokeLinecap="round" />
      </svg>
      {label}
    </div>
  );
}

export function EmptyState({ title, hint }) {
  return (
    <div style={{ padding: "48px 24px", textAlign: "center" }}>
      <div style={{ fontSize: type.lg, fontWeight: 700, color: color.slate600 }}>{title}</div>
      {hint && <div style={{ fontSize: type.base, color: color.slate500, marginTop: 6 }}>{hint}</div>}
    </div>
  );
}

export function Modal({ title, onClose, children, footer, width = 460 }) {
  const ref = useRef(null);
  // Cerrar con Escape y trasladar el foco al diálogo al abrir.
  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") onClose?.(); };
    window.addEventListener("keydown", onKey);
    ref.current?.focus();
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div
      onMouseDown={onClose}
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(16,24,40,.45)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 50,
        padding: 24,
        animation: "fadeIn .12s ease",
      }}
    >
      <div
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-label={typeof title === "string" ? title : undefined}
        tabIndex={-1}
        onMouseDown={(e) => e.stopPropagation()}
        style={{ background: "#fff", borderRadius: radius.lg, width, maxWidth: "100%", maxHeight: "90vh", overflow: "auto", boxShadow: shadow.modal, outline: "none", animation: "fadeUp .16s ease" }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "18px 22px", borderBottom: `1px solid ${color.divider}` }}>
          <div style={{ fontSize: type.lg, fontWeight: 700 }}>{title}</div>
          <button onClick={onClose} aria-label="Cerrar" style={{ border: "none", background: "none", cursor: "pointer", color: color.slate500, display: "flex", padding: 4, borderRadius: radius.sm }}>
            <Icon name="x" size={18} />
          </button>
        </div>
        <div style={{ padding: 22 }}>{children}</div>
        {footer && (
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, padding: "16px 22px", borderTop: `1px solid ${color.divider}` }}>
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}

// Tabla simple estilo ERP. columns = [{key, label, render?}].
export function Table({ columns, rows, onRowClick, vacio = "Sin registros" }) {
  if (!rows.length) return <EmptyState title={vacio} />;
  return (
    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: type.md }}>
      <thead>
        <tr style={{ background: color.subtle, color: color.slate500, textAlign: "left" }}>
          {columns.map((c) => (
            <th key={c.key} style={{ padding: "12px 16px", fontWeight: 600, fontSize: type.sm, whiteSpace: "nowrap" }}>
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
            style={{ borderTop: `1px solid ${color.divider}`, cursor: onRowClick ? "pointer" : "default" }}
            onMouseEnter={(e) => onRowClick && (e.currentTarget.style.background = color.subtle)}
            onMouseLeave={(e) => onRowClick && (e.currentTarget.style.background = "transparent")}
          >
            {columns.map((c) => (
              <td key={c.key} style={{ padding: "13px 16px", verticalAlign: "middle" }}>
                {c.render ? c.render(r) : r[c.key]}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
