import { color, font } from "../theme";
import logoUrl from "../assets/logo.png";

// Marca del sistema. Isotipo = imagen (frontend/src/assets/logo.png), fondo transparente.
//
// Exporta:
//   <LogoMark size />              → solo isotipo (logo chico, p. ej. el menú)
//   <LogoFull size light descriptor> → imagotipo: isotipo + "I-Core" (logo grande)
//   <Logo size />                  → alias de LogoMark (compatibilidad)

export function LogoMark({ size = 40 }) {
  return (
    <img
      src={logoUrl}
      alt="I-Core"
      width={size}
      height={size}
      style={{ objectFit: "contain", flex: "none", display: "block" }}
    />
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
