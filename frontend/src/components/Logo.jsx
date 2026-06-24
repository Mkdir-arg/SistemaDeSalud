import { color } from "../theme";

// Isotipo de Cauce: cuadrado indigo con tres nodos conectados.
export function Logo({ size = 46 }) {
  return (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: size * 0.28,
        background: color.accent,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        flex: "none",
      }}
    >
      <svg width={size * 0.52} height={size * 0.52} viewBox="0 0 16 16" fill="none">
        <circle cx="3.5" cy="8" r="2.2" fill="#fff" />
        <circle cx="12.5" cy="3.5" r="2.2" fill="#fff" opacity=".85" />
        <circle cx="12.5" cy="12.5" r="2.2" fill="#fff" opacity=".85" />
        <path d="M5.4 7.1 10.8 4.2M5.4 8.9 10.8 11.8" stroke="#fff" strokeWidth="1.3" />
      </svg>
    </div>
  );
}
