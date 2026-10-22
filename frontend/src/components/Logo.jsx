import { NOMBRE_SISTEMA } from "@/lib/marca";
import logoColor from "@/assets/marca/plexo-color.svg";
import logoBlanco from "@/assets/marca/plexo-blanco.svg";

// Verde oscuro del paquete de marca de Plexo.
const VERDE_PLEXO = "#079B9D";

/**
 * Marca cuadrada para espacios chicos (menú colapsado). El paquete de marca no
 * trae isotipo: se usa la inicial sobre el verde del logotipo.
 */
export function LogoMark({ size = 40 }) {
  return (
    <span
      role="img"
      aria-label={NOMBRE_SISTEMA}
      className="inline-flex flex-none items-center justify-center rounded-md font-bold tracking-tight text-white"
      style={{ width: size, height: size, fontSize: size * 0.5, background: VERDE_PLEXO }}
    >
      {NOMBRE_SISTEMA.charAt(0)}
    </span>
  );
}

/**
 * Logotipo de Plexo. Es fijo: no sigue a `VITE_NOMBRE_SISTEMA`. `size` es la
 * altura en píxeles; `light` fuerza la versión blanca para fondos oscuros. Sin
 * `light`, la versión blanca aparece sola en tema oscuro.
 */
export function LogoFull({ size = 44, light = false }) {
  const estilo = { height: size, width: "auto" };
  if (light) return <img src={logoBlanco} alt="PLEXO" className="inline-block flex-none" style={estilo} />;
  return (
    <span role="img" aria-label="PLEXO" className="inline-flex flex-none">
      <img src={logoColor} alt="" className="dark:hidden" style={estilo} />
      <img src={logoBlanco} alt="" className="hidden dark:block" style={estilo} />
    </span>
  );
}

export function Logo(props) {
  return <LogoMark {...props} />;
}
