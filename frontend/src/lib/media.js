import { useEffect, useState } from "react";

/**
 * Sigue una media query desde JS.
 *
 * Casi todo lo responsive se resuelve con clases (`md:…`), que es lo preferible.
 * Esto es para lo que NO se puede: cuando el ancho cambia la *estructura* del
 * JSX y no solo su estilo — por ejemplo, el menú colapsado muestra iconos sin
 * texto, y ese texto directamente no debe renderizarse en el cajón móvil.
 */
export function useMedia(query) {
  const [coincide, setCoincide] = useState(
    () => typeof window !== "undefined" && window.matchMedia(query).matches,
  );

  useEffect(() => {
    const mq = window.matchMedia(query);
    const alCambiar = (e) => setCoincide(e.matches);
    setCoincide(mq.matches);
    mq.addEventListener("change", alCambiar);
    return () => mq.removeEventListener("change", alCambiar);
  }, [query]);

  return coincide;
}

/** `md` de Tailwind: de acá para arriba el menú es barra lateral, no cajón. */
export const useEsEscritorio = () => useMedia("(min-width: 768px)");
