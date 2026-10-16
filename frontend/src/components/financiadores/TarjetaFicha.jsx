import { Ayuda, Card } from "@/components/ui";
import { Icon } from "@/components/icons";
import { cn } from "@/lib/cn";
import { valorCampoPadron } from "./padronCampos";

// Título y acción viven dentro de la tarjeta: el bloque se lee como una unidad y
// el botón «Editar» queda pegado a lo que edita. La aclaración va en el «(?)»
// del título; sin `overflow-hidden` en la tarjeta para que el popover no se corte.
export default function TarjetaFicha({ titulo, descripcion, accion, icono, className, cuerpoClassName, children }) {
  return <Card className={className}>
    <div className="flex flex-wrap items-start justify-between gap-3 rounded-t-lg border-b border-division bg-superficie-2 px-5 py-3.5 sm:flex-nowrap">
      {/* El «(?)» va al lado del <h2> y no adentro: adentro sumaría su etiqueta al nombre accesible del título. */}
      <div className="flex min-w-0 flex-1 items-center gap-2 self-center"><h2 className="flex items-center gap-2 text-md font-semibold">{icono && <Icon name={icono} size={16} className="text-texto-debil" />}{titulo}</h2>{descripcion && <Ayuda etiqueta={`Ayuda: ${titulo}`}>{descripcion}</Ayuda>}</div>
      {accion}
    </div>
    <div className={cn("p-5", cuerpoClassName)}>{children}</div>
  </Card>;
}

// «Sin informar» se atenúa: en una ficha a medio cargar es la mayoría de los
// valores y, en negrita, compite con los datos que sí existen.
export function DatosFicha({ campos, valores, className }) {
  return <dl className={cn("grid grid-cols-2 gap-x-6 gap-y-4 text-sm lg:grid-cols-3", className)}>{campos.map((campo) => {
    const valor = valorCampoPadron(campo, valores?.[campo.name]);
    return <div key={campo.name} className="min-w-0"><dt className="text-xs font-medium uppercase tracking-wide text-texto-debil">{campo.label}</dt><dd className={cn("mt-1 break-words whitespace-pre-wrap", valor === "Sin informar" ? "text-texto-tenue" : "font-medium")}>{valor}</dd></div>;
  })}</dl>;
}
