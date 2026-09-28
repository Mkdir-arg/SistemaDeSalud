/** Logotipo de texto temporal. El archivo definitivo se podrá conectar aquí. */
export function LogoMark({ size = 40 }) {
  return (
    <span
      role="img"
      aria-label="HEN"
      className="inline-flex flex-none items-center justify-center rounded-md border border-accent-100 bg-accent-50 font-bold tracking-tight text-accent"
      style={{ width: size, height: size, fontSize: size * 0.33 }}
    >
      HEN
    </span>
  );
}

export function LogoFull({ size = 44, light = false }) {
  return (
    <span
      role="img"
      aria-label="HEN"
      className="inline-block whitespace-nowrap font-bold tracking-tight"
      style={{ fontSize: size * 0.8, lineHeight: 1, color: light ? "#fff" : "var(--color-texto-fuerte)" }}
    >
      HEN
    </span>
  );
}

export function Logo(props) {
  return <LogoMark {...props} />;
}
