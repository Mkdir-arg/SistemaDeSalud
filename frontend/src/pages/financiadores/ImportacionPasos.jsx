// Pasos comunes del modal de importación. Todos los formatos los usan para que
// elegir otro formato no cambie la forma de trabajar: mismos títulos, mismo
// orden y mismas pestañas de filas.
import { useState } from "react";
import { api } from "@/api/client";
import { rutaFinanciador } from "@/api/financiadores";
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
  return <div className="max-w-full overflow-x-auto"><Tabs valor={valor} onChange={onChange} className="w-max" tabs={pestanas.map((p) => ({
    key: p.key,
    label: <span className="inline-flex items-center gap-2">{p.label}<span className="min-w-5 rounded-full border border-borde bg-superficie px-1.5 text-xs tabular-nums">{filas.filter(p.incluye).length}</span></span>,
  }))} /></div>;
}

// Primera pestaña con filas, para no abrir el lote en una pestaña vacía.
export function pestanaInicial(pestanas, filas) {
  return (pestanas.find((p) => p.key !== "todas" && filas.some(p.incluye)) || pestanas[0]).key;
}

// Reenvía el archivo elegido y descarga una copia con comentarios de Excel en
// las celdas con error. El servidor no guarda el archivo; por eso sólo se
// ofrece mientras el modal lo tiene (no desde «Importaciones registradas»).
// `onError` recibe el error crudo (o null al reintentar); cada flujo lo muestra.
export function BotonArchivoAnotado({ organizacion, archivo, importacion, deshabilitado, onError }) {
  const [descargando, setDescargando] = useState(false);
  async function descargar() {
    setDescargando(true); onError(null);
    try {
      const datos = new FormData();
      datos.append("archivo", archivo);
      if (importacion) datos.append("importacion", String(importacion));
      const nombre = archivo.name.replace(/\.xlsx$/i, "") + "-con-comentarios.xlsx";
      await api.downloadPost(rutaFinanciador(organizacion.id, "anotar-importacion"), datos, nombre);
    } catch (e) { onError(e); }
    finally { setDescargando(false); }
  }
  return <Button type="button" variant="secondary" disabled={deshabilitado || descargando} onClick={descargar}
    title="Descarga tu mismo archivo con un comentario en cada celda con error (en amarillo, las advertencias).">
    {descargando ? "Preparando…" : "Ver errores en el archivo"}</Button>;
}

// Tabla paginada de filas del lote, igual en todos los formatos. Quien la usa
// le pasa un `key` que cambia con el lote y la pestaña para volver a la página 1.
export function TablaFilas({ filas, persona, detalle, accion, porPagina = 20 }) {
  const [pagina, setPagina] = useState(0);
  const ultima = Math.max(0, Math.ceil(filas.length / porPagina) - 1);
  const visible = Math.min(pagina, ultima);
  if (filas.length === 0) return <p role="status">No hay filas en esta categoría.</p>;
  return <>
    <div><table className="w-full text-left text-sm"><caption className="sr-only">Registros del lote</caption>
      <thead><tr>{["Origen", "Persona", "Estado y observaciones", "Acción"].map((t) => <th key={t} scope="col" className="p-2">{t}</th>)}</tr></thead>
      <tbody>{filas.slice(visible * porPagina, (visible + 1) * porPagina).map((f) => <tr key={f.fila} className="border-t border-division align-top">
        <td className="whitespace-nowrap p-2">{f.hoja || "Carga"} · fila {f.fila_excel ?? f.fila}</td>
        <td className="p-2">{persona(f)}</td>
        <td className="p-2">{detalle(f)}</td>
        <td className="p-2">{accion(f)}</td>
      </tr>)}</tbody>
    </table></div>
    {filas.length > porPagina && <div className="flex items-center justify-between"><Button variant="ghost" disabled={visible === 0} onClick={() => setPagina(visible - 1)}>Anterior</Button><span>Página {visible + 1} de {ultima + 1}</span><Button variant="ghost" disabled={visible === ultima} onClick={() => setPagina(visible + 1)}>Siguiente</Button></div>}
  </>;
}
