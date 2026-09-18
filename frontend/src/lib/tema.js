import { useCallback, useEffect, useLayoutEffect, useState } from "react";
import { useLocation } from "react-router-dom";

const CLAVE = "salud.tema"; // "claro" | "oscuro" | ausente = seguir al sistema

/**
 * Rutas que se ven siempre en claro, sin importar la preferencia.
 *
 * El login es la cara institucional del sistema: tiene que verse igual en
 * cualquier puesto, y su panel de marca ya trae su propio degradado. La misma
 * regla está repetida en el script del <head> de index.html, que corre antes de
 * que exista este módulo; si cambia una, cambian las dos.
 */
const RUTAS_CLARAS = ["/login"];

export const esRutaClara = (pathname) => RUTAS_CLARAS.includes(pathname.replace(/\/+$/, ""));

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

/** ¿La preferencia vigente (o la del sistema, si no hay) pide oscuro? */
const prefiereOscuro = () => {
  const t = temaGuardado();
  return t === "oscuro" || (!t && window.matchMedia("(prefers-color-scheme: dark)").matches);
};

/**
 * Mantiene el <html> en el tema que corresponde a la ruta actual.
 *
 * Va en un layout effect para que el cambio ocurra antes de pintar: al salir del
 * login la preferencia vuelve sin que se vea un cuadro en claro, y al entrar al
 * login no se ve uno en oscuro mientras carga su chunk.
 */
export function useTemaDeRuta() {
  const { pathname } = useLocation();
  useLayoutEffect(() => {
    aplicarTema(esRutaClara(pathname) ? "claro" : temaGuardado());
  }, [pathname]);
}

/**
 * Tema claro/oscuro.
 *
 * Por defecto sigue al sistema; en cuanto la persona elige uno, esa elección
 * manda y se recuerda. En una guardia el turno noche lo decide quien está en el
 * puesto, no la configuración del sistema operativo de una máquina compartida.
 */
export function useTema() {
  // El estado sale de la preferencia y no de la clase del <html>: en las rutas
  // claras esa clase está forzada, y el conmutador mostraría el rótulo al revés
  // apenas se vuelve a la aplicación.
  const [oscuro, setOscuro] = useState(prefiereOscuro);

  // Si no hay preferencia explícita, seguir los cambios del sistema.
  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const alCambiar = () => { if (!temaGuardado()) setOscuro(aplicarTema(null)); };
    mq.addEventListener("change", alCambiar);
    return () => mq.removeEventListener("change", alCambiar);
  }, []);

  const alternar = useCallback(() => {
    const nuevo = oscuro ? "claro" : "oscuro";
    localStorage.setItem(CLAVE, nuevo);
    setOscuro(aplicarTema(nuevo));
  }, [oscuro]);

  return { oscuro, alternar };
}
