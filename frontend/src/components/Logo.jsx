import logoUrl from "../assets/logo.png";

/**
 * Marca del sistema. Isotipo = imagen (`src/assets/logo.png`, fondo transparente).
 *
 *   <LogoMark size />                → solo isotipo (p. ej. el menú)
 *   <LogoFull size light descriptor> → imagotipo: isotipo + «I-Core»
 *   <Logo size />                    → alias de LogoMark (compatibilidad)
 *
 * Los tamaños se calculan desde `size` y por eso van inline: son proporciones del
 * logo, no pasos de la escala tipográfica. Los colores sí salen de tokens, así el
 * logo sigue al tema sin una copia de la paleta.
 */

export function LogoMark({ size = 40 }) {
  return (
    <img
      src={logoUrl}
      alt="I-Core"
      width={size}
      height={size}
      className="block flex-none object-contain"
    />
  );
}

export function LogoFull({ size = 44, light = false, descriptor = "Salud" }) {
  // `light` es para superficies de marca oscuras (el panel del login), donde el
  // color no viene del tema sino del degradado. El descriptor estaba al 66% de
  // blanco: sobre el índigo eso queda en 4.1:1 y no llega al mínimo de AA. A 80%
  // pasa, y la jerarquía con el nombre se conserva igual.
  const tinta = light ? "#fff" : "var(--color-texto)";
  const separador = light ? "rgba(255,255,255,.7)" : "var(--color-accent)";
  const sub = light ? "rgba(255,255,255,.8)" : "var(--color-texto-debil)";

  return (
    <div className="inline-flex items-center" style={{ gap: size * 0.32 }}>
      <LogoMark size={size} />
      <div style={{ lineHeight: 1.05, fontFamily: "var(--font-display)" }}>
        <div
          className="whitespace-nowrap font-extrabold tracking-tight"
          style={{ fontSize: size * 0.5, color: tinta }}
        >
          I<span style={{ color: separador, fontWeight: 600, margin: "0 .5px" }}>-</span>Core
        </div>
        {descriptor && (
          <div
            className="font-bold uppercase"
            style={{ fontSize: size * 0.24, letterSpacing: "1.6px", color: sub, marginTop: size * 0.07 }}
          >
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
