import { NOMBRE_SISTEMA } from "@/lib/marca";

/**
 * Logotipo de texto temporal. El archivo definitivo se podrá conectar aquí.
 *
 * La marca cuadrada lleva sólo la inicial: el nombre cambia de largo y siempre
 * aparece escrito al lado, así que el nombre entero no entraría en el cuadrado.
 */
export function LogoMark({ size = 40 }) {
  return (
    <span
      role="img"
      aria-label={NOMBRE_SISTEMA}
      className="inline-flex flex-none items-center justify-center rounded-md border border-accent-100 bg-accent-50 font-bold tracking-tight text-accent"
      style={{ width: size, height: size, fontSize: size * 0.5 }}
    >
      {NOMBRE_SISTEMA.charAt(0)}
    </span>
  );
}

export function LogoFull({ size = 44, light = false }) {
  return (
    <span
      role="img"
      aria-label={NOMBRE_SISTEMA}
      className="inline-block whitespace-nowrap font-bold tracking-tight"
      style={{ fontSize: size * 0.8, lineHeight: 1, color: light ? "#fff" : "var(--color-texto-fuerte)" }}
    >
      {NOMBRE_SISTEMA}
    </span>
  );
}

export function Logo(props) {
  return <LogoMark {...props} />;
}
