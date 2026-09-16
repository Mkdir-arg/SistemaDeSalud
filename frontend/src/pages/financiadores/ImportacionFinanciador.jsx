import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import { errorFinanciador, filasDe, importarFinanciador, rutaFinanciador } from "@/api/financiadores";
import { Badge, Button, Card, Field, Input, Modal, Spinner, Textarea } from "@/components/ui";
import { plural } from "@/lib/format";

const APLICADOS = new Set(["aplicada"]);
const EN_PROCESO = new Set(["procesando", "aplicando", "pendiente", "validando"]);

export default function ImportacionFinanciador({ organizacion, tipo, scope, onClose, onAplicado }) {
  const [archivo, setArchivo] = useState(null);
  const [lote, setLote] = useState(null);
  const [error, setError] = useState(null);
  const [ocupado, setOcupado] = useState(false);
  const [descargando, setDescargando] = useState(false);
  const [revisiones, setRevisiones] = useState({});
  const [pagina, setPagina] = useState(1);
  const clave = useRef(crypto.randomUUID());
  const activo = useRef(true);
  useEffect(() => { activo.current = true; return () => { activo.current = false; }; }, []);
  const lotes = useQuery({ queryKey: [...scope, "importaciones", tipo, pagina], queryFn: () => api.get(`${rutaFinanciador(organizacion.id, "importaciones")}?${new URLSearchParams({ tipo, page: pagina })}`), gcTime: 0, refetchInterval: lote && EN_PROCESO.has(lote.estado) ? 2000 : false });
  useEffect(() => {
    if (!lote || !EN_PROCESO.has(lote.estado)) return;
    const actualizado = filasDe(lotes.data).find((item) => item.id === lote.id);
    if (actualizado) setLote(actualizado);
  }, [lotes.data]);
  async function previsualizar(e) {
    e.preventDefault(); if (!archivo) return;
    setOcupado(true); setError(null);
    try {
      const data = await importarFinanciador(organizacion.id, tipo, archivo, clave.current);
      if (activo.current) { setLote(data); setPagina(1); lotes.refetch(); }
    } catch (err) { if (activo.current) setError(err); }
    finally { if (activo.current) setOcupado(false); }
  }
  async function confirmar() {
    setOcupado(true); setError(null);
    try {
      let pendiente = Number(lote.resumen?.valida || 0);
      do {
        const data = await api.post(rutaFinanciador(organizacion.id, "confirmar-importacion"), { importacion: lote.id, revisiones_duplicados: Object.fromEntries(Object.entries(revisiones).filter(([, motivo]) => motivo.trim())) });
        if (!activo.current) break;
        setLote(data);
        const restantes = Number(data.resumen?.valida || 0);
        // Cada confirmación es recuperable. Un error técnico o falta de
        // progreso exige reintento explícito, nunca un bucle de pedidos.
        if (APLICADOS.has(data.estado) || !restantes || data.resumen?.error_tecnico > 0 || restantes >= pendiente) break;
        pendiente = restantes;
      } while (activo.current);
      if (activo.current) { lotes.refetch(); await onAplicado(); }
    } catch (err) { if (activo.current) setError(err); }
    finally { if (activo.current) setOcupado(false); }
  }
  async function descargar(recurso, params, nombre) {
    setDescargando(true); setError(null);
    try { await api.download(`${rutaFinanciador(organizacion.id, recurso)}?${new URLSearchParams(params)}`, nombre); }
    catch (err) { if (activo.current) setError(err); }
    finally { if (activo.current) setDescargando(false); }
  }
  const resumen = lote?.resumen || {};
  const terminado = APLICADOS.has(lote?.estado);
  const procesando = EN_PROCESO.has(lote?.estado);
  const validas = Number(resumen.valida ?? 0);
  const rechazos = (lote?.filas || []).filter((fila) => ["rechazada", "revision", "error_tecnico"].includes(fila.estado));
  const hayRevision = Object.values(revisiones).some((motivo) => motivo.trim());
  return <Modal title={`Importar ${tipo === "padron" ? "padrón" : "consumos externos"}`} onClose={ocupado ? undefined : onClose} width={840}>
    <div className="space-y-5">
      <p className="text-sm text-texto-debil">{organizacion.nombre} · {tipo === "padron" ? "La carga agrega o actualiza afiliados. No da de baja a nadie por omisión." : "La plantilla incluye las prestaciones de este financiador. Indicá número de afiliado y documento tal como figuran en el padrón."}</p>
      {error && <div role="alert" className="rounded-md bg-badge-error-bg p-3 text-badge-error-fg">{errorFinanciador(error)}</div>}
      <Card className="p-4"><div className="flex flex-wrap items-center justify-between gap-3"><div><h3 className="font-semibold">1. Prepará el archivo</h3><p className="mt-1 text-sm text-texto-debil">Descargá la plantilla vigente y completá la hoja de carga. Conservá los identificadores como texto.</p></div><Button variant="secondary" disabled={descargando} onClick={() => descargar("plantilla", { tipo }, `plantilla-${tipo}.xlsx`)}>Descargar plantilla</Button></div></Card>
      <form onSubmit={previsualizar} className="space-y-3"><h3 className="font-semibold">2. Revisá antes de importar</h3><Field label="Archivo Excel (.xlsx)"><Input type="file" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" disabled={ocupado} onChange={(e) => { setArchivo(e.target.files[0] || null); setLote(null); setRevisiones({}); setError(null); clave.current = crypto.randomUUID(); }} /></Field><Button type="submit" disabled={!archivo || ocupado}>{ocupado && !lote ? "Revisando…" : "Revisar archivo"}</Button></form>
      {lote && <section aria-label="Resumen de importación" className="space-y-4 border-t border-division pt-5">
        <div className="flex flex-wrap items-center justify-between gap-2"><h3 className="font-semibold">3. {terminado ? "Resultado de la importación" : "Confirmá las filas válidas"}</h3><Badge tone={terminado ? "green" : "amber"}>{terminado ? "Procesada" : procesando ? "En proceso" : "Pendiente de confirmación"}</Badge></div>
        <dl className="grid grid-cols-2 gap-3 rounded-lg bg-superficie-2 p-4 sm:grid-cols-4">{[["Filas revisadas", resumen.total], ["Válidas pendientes", resumen.valida], ["Rechazadas", resumen.rechazada], ["Aplicadas", resumen.aplicada ?? 0]].map(([label, value]) => <div key={label}><dt className="text-sm text-texto-debil">{label}</dt><dd className="mt-1 text-xl font-semibold tabular-nums">{value ?? "—"}</dd></div>)}</dl>
        {resumen.revision > 0 && <p className="text-sm text-badge-amber-fg">{resumen.revision} posibles duplicados necesitan revisión individual y motivo.</p>}
        {resumen.error_tecnico > 0 && <p role="alert" className="text-sm text-badge-error-fg">{resumen.error_tecnico} filas tuvieron un error técnico. Reintentá la confirmación; lo ya aplicado no se duplica.</p>}
        {procesando ? <Spinner label="Procesando el lote. Podés volver a consultarlo desde las importaciones recientes." /> : !terminado && <><p className="text-sm text-texto-debil">Las filas válidas se vuelven a verificar al confirmar. El resultado final indica cuáles se aplicaron; las rechazadas quedan disponibles para corregir.</p><Button disabled={ocupado || (validas === 0 && !hayRevision && !resumen.error_tecnico)} onClick={confirmar}>{ocupado ? "Importando…" : resumen.error_tecnico ? "Reintentar confirmación" : hayRevision ? "Importar filas válidas y revisadas" : `Importar ${plural(validas, "fila válida", "filas válidas")}`}</Button></>}
        {terminado && <p role="status" className="text-sm text-texto-debil">{resumen.aplicada === 1 ? "Se aplicó" : "Se aplicaron"} {plural(resumen.aplicada ?? 0, "fila", "filas")}. Las filas rechazadas no modificaron el padrón ni el cupo.</p>}
        {rechazos.length > 0 && <div className="space-y-3"><Button variant="secondary" disabled={descargando} onClick={() => descargar("rechazos", { importacion: lote.id }, `rechazos-${tipo}.xlsx`)}>Descargar filas rechazadas</Button><div className="max-h-72 overflow-auto"><table className="w-full text-left text-sm"><thead><tr className="border-b border-division"><th scope="col" className="p-2">Fila</th><th scope="col" className="p-2">Motivo</th></tr></thead><tbody>{rechazos.map((fila) => <tr key={fila.fila} className="border-b border-division"><td className="p-2">{fila.fila}</td><td className="space-y-2 p-2"><p>{fila.errores?.join(" ") || "Revisá el detalle descargable."}</p>{fila.estado === "revision" && <Field label={`Motivo de revisión de fila ${fila.fila}`} hint="Completá sólo si verificaste que es una prestación distinta."><Textarea maxLength={255} disabled={ocupado} value={revisiones[fila.fila] || ""} onChange={(e) => setRevisiones({ ...revisiones, [fila.fila]: e.target.value })} /></Field>}</td></tr>)}</tbody></table></div></div>}
      </section>}
      <section className="border-t border-division pt-4"><h3 className="font-semibold">Importaciones registradas</h3>{lotes.isLoading ? <Spinner label="Consultando importaciones…" /> : lotes.error ? <p role="alert" className="mt-2 text-sm text-badge-error-fg">{errorFinanciador(lotes.error)} <button className="underline" onClick={() => lotes.refetch()}>Reintentar</button></p> : <div className="mt-2 space-y-2">{filasDe(lotes.data).filter((item) => item.tipo === tipo).length === 0 ? <p className="text-sm text-texto-debil">Todavía no hay importaciones de este tipo.</p> : filasDe(lotes.data).filter((item) => item.tipo === tipo).map((item) => <button key={item.id} type="button" disabled={ocupado} onClick={() => { setLote(item); setRevisiones({}); setError(null); }} className="flex w-full flex-wrap justify-between gap-2 rounded-md border border-division px-3 py-2 text-left text-sm hover:bg-superficie-2"><span>{item.nombre_archivo || item.archivo_nombre || `Importación ${item.id}`}</span><span>{APLICADOS.has(item.estado) ? "Procesada" : EN_PROCESO.has(item.estado) ? "En proceso" : "Revisar resumen"}</span></button>)}</div>}<div className="mt-3 flex items-center justify-between gap-2 text-sm"><span className="text-texto-debil">Página {pagina}</span><div className="flex gap-2"><Button size="sm" variant="ghost" disabled={pagina === 1 || lotes.isFetching || ocupado} onClick={() => setPagina(pagina - 1)}>Anterior</Button><Button size="sm" variant="ghost" disabled={!lotes.data?.next || lotes.isFetching || ocupado} onClick={() => setPagina(pagina + 1)}>Siguiente</Button></div></div></section>
    </div>
  </Modal>;
}
