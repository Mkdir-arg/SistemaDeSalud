// Componentes base de UI. Estilos calcados del "Sistema de diseño" de Cauce.
import { avatarColors, badgeTone, color, font, iniciales } from "../theme";
import { Icon } from "./icons";

export function Button({ variant = "primary", children, style, disabled, ...props }) {
  const base = {
    height: 40,
    padding: "0 18px",
    borderRadius: 9,
    fontSize: 13.5,
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
        borderRadius: 999,
        fontSize: 12,
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
        borderRadius: 14,
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
        <div style={{ fontSize: 13, fontWeight: 600, color: color.slate600, marginBottom: 6 }}>
          {label}
        </div>
      )}
      {children}
    </label>
  );
}

export function Input({ style, ...props }) {
  return (
    <input
      style={{
        height: 40,
        width: "100%",
        border: `1px solid ${color.inputBorder}`,
        borderRadius: 9,
        padding: "0 12px",
        fontSize: 13.5,
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
        borderRadius: 9,
        padding: "10px 12px",
        fontSize: 13.5,
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

export function Select({ style, children, ...props }) {
  return (
    <select
      style={{
        height: 40,
        width: "100%",
        border: `1px solid ${color.inputBorder}`,
        borderRadius: 9,
        padding: "0 10px",
        fontSize: 13.5,
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
    <div style={{ padding: 40, textAlign: "center", color: color.slate400, fontSize: 13.5 }}>
      {label}
    </div>
  );
}

export function EmptyState({ title, hint }) {
  return (
    <div style={{ padding: "48px 24px", textAlign: "center" }}>
      <div style={{ fontSize: 15, fontWeight: 700, color: color.slate600 }}>{title}</div>
      {hint && <div style={{ fontSize: 13, color: color.slate400, marginTop: 6 }}>{hint}</div>}
    </div>
  );
}

export function Modal({ title, onClose, children, footer, width = 460 }) {
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
      }}
    >
      <div
        onMouseDown={(e) => e.stopPropagation()}
        style={{ background: "#fff", borderRadius: 16, width, maxWidth: "100%", maxHeight: "90vh", overflow: "auto", boxShadow: "0 18px 50px rgba(16,24,40,.28)" }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "18px 22px", borderBottom: `1px solid ${color.divider}` }}>
          <div style={{ fontSize: 16, fontWeight: 700 }}>{title}</div>
          <button onClick={onClose} style={{ border: "none", background: "none", cursor: "pointer", color: color.slate400, display: "flex" }}>
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
    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13.5 }}>
      <thead>
        <tr style={{ background: color.subtle, color: color.slate500, textAlign: "left" }}>
          {columns.map((c) => (
            <th key={c.key} style={{ padding: "12px 16px", fontWeight: 600, fontSize: 12.5, whiteSpace: "nowrap" }}>
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
