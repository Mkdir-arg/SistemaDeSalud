import { clsx } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

import { escalas } from "@/styles/escalas";

// tailwind-merge sabe deduplicar las clases de Tailwind, pero no las escalas
// propias: para él `rounded-pill` o `text-danger` son clases desconocidas y las
// deja pasar junto con la que deberían pisar. Le pasamos las escalas generadas
// desde theme.js para que las agrupe bien.
const merge = extendTailwindMerge({ extend: { theme: escalas } });

/**
 * Combina clases condicionales y resuelve los conflictos de Tailwind quedándose
 * con la última. Es lo que hace que un componente acepte `className` desde afuera
 * y el override realmente gane:
 *
 *     cn("px-4 text-slate-500", className)   // className="text-danger" gana
 */
export function cn(...clases) {
  return merge(clsx(clases));
}
