// Pasos comunes del modal de importación. Todos los formatos los usan para que
// elegir otro formato no cambie la forma de trabajar: mismos títulos, mismo
// orden y mismas pestañas de filas.
import { Ayuda, Button, Field, Input, Tabs } from "@/components/ui";

export function PasoPreparar({ ayuda, deshabilitado, onDescargar }) {
  return <div className="flex flex-wrap items-center justify-between gap-3">
    <div className="flex items-center gap-2"><h3 className="font-semibold">1. Prepará el archivo</h3><Ayuda etiqueta="Ayuda sobre la plantilla">{ayuda}</Ayuda></div>
    <Button type="button" variant="secondary" disabled={deshabilitado} onClick={onDescargar}>Descargar plantilla</Button>
  </div>;
}

export function PasoRevisar({ onSubmit, onArchivo, deshabilitado, enviable, ocupado, ayuda }) {
  return <form onSubmit={onSubmit} className="space-y-3 border-t border-division pt-5">
    <h3 className="font-semibold">2. Revisá antes de importar</h3>
    <Field label="Archivo Excel (.xlsx)" ayuda={ayuda}>
      <Input type="file" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" disabled={deshabilitado} onChange={(e) => onArchivo(e.target.files[0] || null)} />
    </Field>
    <Button type="submit" disabled={!enviable || deshabilitado}>{ocupado ? "Revisando…" : "Revisar archivo"}</Button>
  </form>;
}

// `pestanas` = [{ key, label, incluye(fila) }]. La cantidad de cada pestaña se
// calcula sobre las filas del lote, no sobre la página visible.
export function PestanasFilas({ pestanas, filas, valor, onChange }) {
  return <Tabs valor={valor} onChange={onChange} className="flex-wrap" tabs={pestanas.map((p) => ({
    key: p.key,
    label: <span className="inline-flex items-center gap-2">{p.label}<span className="min-w-5 rounded-full border border-borde bg-superficie px-1.5 text-xs tabular-nums">{filas.filter(p.incluye).length}</span></span>,
  }))} />;
}

// Primera pestaña con filas, para no abrir el lote en una pestaña vacía.
export function pestanaInicial(pestanas, filas) {
  return (pestanas.find((p) => p.key !== "todas" && filas.some(p.incluye)) || pestanas[0]).key;
}
