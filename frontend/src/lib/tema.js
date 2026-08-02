import { useCallback, useEffect, useState } from "react";

const CLAVE = "cauce.tema"; // "claro" | "oscuro" | ausente = seguir al sistema

/** Aplica el tema al <html>. Se exporta para poder llamarlo antes de montar React. */
export function aplicarTema(tema) {
  const oscuro =
    tema === "oscuro" ||
    (!tema && window.matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.classList.toggle("dark", oscuro);
  return oscuro;
}

/** Lee la preferencia guardada (null = sin elegir, sigue al sistema). */
export const temaGuardado = () => localStorage.getItem(CLAVE);

/**
 * Tema claro/oscuro.
 *
 * Por defecto sigue al sistema; en cuanto la persona elige uno, esa elección
 * manda y se recuerda. En una guardia el turno noche lo decide quien está en el
 * puesto, no la configuración del sistema operativo de una máquina compartida.
 */
export function useTema() {
  const [oscuro, setOscuro] = useState(() => document.documentElement.classList.contains("dark"));

  // Si no hay preferencia explícita, seguir los cambios del sistema.
  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const alCambiar = () => { if (!temaGuardado()) setOscuro(aplicarTema(null)); };
    mq.addEventListener("change", alCambiar);
    return () => mq.removeEventListener("change", alCambiar);
  }, []);

  const alternar = useCallback(() => {
    const nuevo = document.documentElement.classList.contains("dark") ? "claro" : "oscuro";
    localStorage.setItem(CLAVE, nuevo);
    setOscuro(aplicarTema(nuevo));
  }, []);

  return { oscuro, alternar };
}
