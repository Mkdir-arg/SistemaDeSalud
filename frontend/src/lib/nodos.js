import { nombreNodo } from "./dominio";

/**
 * Categorías de nodo para el diseñador, en variables CSS.
 *
 * Los colores salen de los tokens `--color-nodo-*`, que tienen su variante
 * oscura resuelta con `color-mix`. Antes el editor leía los hex directamente de
 * `theme.js`, y por eso era la única pantalla sin tema oscuro: los nodos
 * quedaban con tintes claros sobre fondo negro.
 *
 * Devolver las variables en vez de los hex hace que el mismo código de siempre
 * (`cat.sol`, `cat.tint`, `cat.bd`) pase a seguir el tema sin tocar cada uso.
 */
export const TIPOS_NODO = [
  "inicio", "form", "decision", "accion", "derivar",
  "espera", "tiempo", "atencion", "cama", "estado", "notificar", "integracion", "fin",
];

const CONOCIDO = new Set(TIPOS_NODO);

/*
 * Icono de cada tipo, del set de `components/icons`.
 *
 * El color solo no alcanza para decir qué hace un nodo: son trece tipos y varios
 * comparten familia cromática, así que a golpe de vista «Derivar» y «Estado» se
 * veían iguales. El icono lo dice sin leer, y sobre todo lo dice al 60 % de zoom,
 * que es como se ve un flujo entero.
 */
const ICONOS = {
  inicio: "play",
  form: "form",
  decision: "rama",
  accion: "activity",
  derivar: "flecha",
  espera: "users",
  tiempo: "reloj",
  atencion: "clipboard",
  cama: "bed",
  estado: "layers",
  notificar: "bell",
  integracion: "enchufe",
  fin: "power",
};

/**
 * `catDe(tipo)` → `{ name, icono, sol, tint, bd }`.
 *
 * Un tipo desconocido cae en «form»: el backend puede sumar un tipo de nodo
 * antes que el frontend, y componer un `var(--color-nodo-loquesea-sol)` que no
 * existe deja el nodo sin color y sin borde, o sea invisible.
 */
export function catDe(tipo) {
  const t = CONOCIDO.has(tipo) ? tipo : "form";
  return {
    name: nombreNodo(tipo),
    icono: ICONOS[t],
    sol: `var(--color-nodo-${t}-sol)`,
    tint: `var(--color-nodo-${t}-tint)`,
    bd: `var(--color-nodo-${t}-bd)`,
  };
}
