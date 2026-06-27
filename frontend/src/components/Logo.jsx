import { color, font } from "../theme";

// Marca de I-Core (empresa del sistema de salud).
// Isotipo: una "C" (Core) abierta a la derecha con un núcleo central —
// el punto central es la "i" / el núcleo. Construido en SVG: nítido a cualquier escala.
//
// Exporta:
//   <LogoMark size light />        → solo isotipo (logo chico, p. ej. el menú)
//   <LogoFull size light descriptor> → imagotipo: isotipo + "I-Core" (logo grande)
//   <Logo size />                  → alias de LogoMark (compatibilidad)
//
// `light`: para fondos oscuros (índigo) → cuadro blanco con la marca en índigo.

export function LogoMark({ size = 40, light = false }) {
  const fg = light ? color.accent : "#fff";
  const sw = 24 * 0.115; // grosor del trazo relativo al viewBox 24
  return (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: size * 0.27,
        flex: "none",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: light ? "#fff" : `linear-gradient(150deg, ${color.accent} 0%, ${color.accentHover} 100%)`,
        boxShadow: light ? "none" : "0 4px 12px rgba(57,73,192,.26)",
      }}
    >
      <svg width={size * 0.62} height={size * 0.62} viewBox="0 0 24 24" fill="none">
        {/* "C" de Core: arco abierto hacia la derecha */}
        <path d="M17.6 6.4 A8 8 0 1 0 17.6 17.6" stroke={fg} strokeWidth={sw} strokeLinecap="round" />
        {/* núcleo central (la "i" / el core) */}
        <circle cx="12" cy="12" r="2.7" fill={fg} />
      </svg>
    </div>
  );
}

export function LogoFull({ size = 44, light = false, descriptor = "Salud" }) {
  const ink = light ? "#fff" : color.ink;
  const sep = light ? "rgba(255,255,255,.55)" : color.accent;
  const sub = light ? "rgba(255,255,255,.66)" : color.slate500;
  return (
    <div style={{ display: "inline-flex", alignItems: "center", gap: size * 0.32 }}>
      <LogoMark size={size} light={light} />
      <div style={{ lineHeight: 1.05, fontFamily: font.display }}>
        <div style={{ fontSize: size * 0.5, fontWeight: 800, letterSpacing: "-.4px", color: ink, whiteSpace: "nowrap" }}>
          I<span style={{ color: sep, fontWeight: 600, margin: "0 .5px" }}>-</span>Core
        </div>
        {descriptor && (
          <div style={{ fontSize: size * 0.24, fontWeight: 700, letterSpacing: "1.6px", textTransform: "uppercase", color: sub, marginTop: size * 0.07 }}>
            {descriptor}
          </div>
        )}
      </div>
    </div>
  );
}

// Compatibilidad: el isotipo sigue disponible como `Logo`.
export function Logo(props) {
  return <LogoMark {...props} />;
}
