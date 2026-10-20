import { useEffect, useRef, useState } from "react";
import { api } from "@/api/client";
import { errorFinanciador, importarFinanciador, rutaFinanciador } from "@/api/financiadores";
import { Ayuda, Badge, Button, Card, Field, Input, Spinner, Textarea } from "@/components/ui";
import { plural } from "@/lib/format";

const APLICADOS = new Set(["aplicada"]);
const EN_PROCESO = new Set(["procesando", "aplicando", "pendiente", "validando"]);

export default function ImportacionSistema({ organizacion, tipo, formato, onAplicado, onBloqueosChange, lote, setLote, lotes, setPagina }) {
  const [archivo, setArchivo] = useState(null);
  const [error, setError] = useState(null);
  const [ocupado, setOcupado] = useState(false);
  const [descargando, setDescargando] = useState(false);
  const [revisiones, setRevisiones] = useState({});
  const clave = useRef(crypto.randomUUID());
  const activo = useRef(true);
  useEffect(() => { activo.current = true; return () => { activo.current = false; }; }, []);
  useEffect(() => { onBloqueosChange({ selector: ocupado || descargando, cierre: ocupado }); }, [ocupado, descargando, onBloqueosChange]);
  useEffect(() => { setRevisiones({}); setError(null); }, [lote?.id]);
  async function previsualizar(e) {
    e.preventDefault(); if (!archivo) return;
    setOcupado(true); setError(null);
    try {
      const data = await importarFinanciador(organizacion.id, tipo, archivo, clave.current, formato.recursoRevision);
      if (activo.current) { setLote(data); setPagina(1); lotes.refetch(); }
    } catch (err) { if (activo.current) setError(err); }
    finally { if (activo.current) setOcupado(false); }
  }
  async function confirmar() {
    setOcupado(true); setError(null);
    try {
      let pendiente = Number(lote.resumen?.valida || 0);
      do {
        const data = await api.post(rutaFinanciador(organizacion.id, formato.recursoConfirmacion), { importacion: lote.id, revisiones_duplicados: tipo === "consumos" ? Object.fromEntries(Object.entries(revisiones).filter(([, motivo]) => motivo.trim())) : {} });
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
  const hayRevision = tipo === "consumos" && Object.values(revisiones).some((motivo) => motivo.trim());
  return <div className="space-y-5">
      {error && <div role="alert" className="rounded-md bg-badge-error-bg p-3 text-badge-error-fg">{errorFinanciador(error)}</div>}
      <Card className="p-4"><div className="flex flex-wrap items-center justify-between gap-3"><div><div className="flex items-center gap-2"><h3 className="font-semibold">1. Prepará el archivo</h3><Ayuda etiqueta="Ayuda sobre la plantilla">
            {tipo === "padron" ? <>
              <span className="block">La plantilla incluye identidad, contacto, régimen, familia, trámite y credencial registrada externamente. Conservá los identificadores como texto y cargá primero al titular.</span>
              <span className="block">La carga agrega o actualiza afiliados. Las celdas nuevas vacías no borran datos existentes y los afiliados ausentes del archivo no se dan de baja.</span>
              <span className="block">No se importan bajas, reactivaciones, datos de salud, parentesco protegido ni datos de cobranza o bancarios. Esas operaciones se realizan desde los recursos correspondientes de la ficha.</span>
            </> : <span className="block">La plantilla incluye las prestaciones de este financiador. Indicá número de afiliado y documento tal como figuran en el padrón.</span>}
          </Ayuda></div></div><div className="flex flex-wrap gap-2"><Button variant="secondary" disabled={descargando} onClick={() => descargar("plantilla", formato.parametrosPlantilla(tipo), formato.nombrePlantilla(tipo))}>Descargar plantilla</Button></div></div></Card>
      <form onSubmit={previsualizar} className="space-y-3"><h3 className="font-semibold">2. Revisá antes de importar</h3><Field label="Archivo Excel (.xlsx)"><Input type="file" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" disabled={ocupado} onChange={(e) => { setArchivo(e.target.files[0] || null); setLote(null); setRevisiones({}); setError(null); clave.current = crypto.randomUUID(); }} /></Field><Button type="submit" disabled={!archivo || ocupado}>{ocupado && !lote ? "Revisando…" : "Revisar archivo"}</Button></form>
      {lote && <section aria-label="Resumen de importación" className="space-y-4 border-t border-division pt-5">
        <div className="flex flex-wrap items-center justify-between gap-2"><h3 className="font-semibold">3. {terminado ? "Resultado de la importación" : "Confirmá las filas válidas"}</h3><Badge tone={terminado ? "green" : "amber"}>{terminado ? "Procesada" : procesando ? "En proceso" : "Pendiente de confirmación"}</Badge></div>
        <dl className="grid grid-cols-2 gap-3 rounded-lg bg-superficie-2 p-4 sm:grid-cols-4">{[["Filas revisadas", resumen.total], ["Válidas pendientes", resumen.valida], ["Rechazadas", resumen.rechazada], ["Aplicadas", resumen.aplicada ?? 0]].map(([label, value]) => <div key={label}><dt className="text-sm text-texto-debil">{label}</dt><dd className="mt-1 text-xl font-semibold tabular-nums">{value ?? "—"}</dd></div>)}</dl>
        {resumen.revision > 0 && <p className="text-sm text-badge-amber-fg">{tipo === "padron" ? `${resumen.revision} filas con conflictos de identidad requieren corregir el archivo. No se permite forzar una identidad con un motivo.` : `${resumen.revision} posibles duplicados necesitan revisión individual y motivo.`}</p>}
        {resumen.error_tecnico > 0 && <p role="alert" className="text-sm text-badge-error-fg">{resumen.error_tecnico} filas tuvieron un error técnico. Reintentá la confirmación; lo ya aplicado no se duplica.</p>}
        {procesando ? <Spinner label="Procesando el lote. Podés volver a consultarlo desde las importaciones recientes." /> : !terminado && <><div className="flex items-center gap-2"><Button disabled={ocupado || (validas === 0 && !hayRevision && !resumen.error_tecnico)} onClick={confirmar}>{ocupado ? "Importando…" : resumen.error_tecnico ? "Reintentar confirmación" : hayRevision ? "Importar filas válidas y revisadas" : `Importar ${plural(validas, "fila válida", "filas válidas")}`}</Button><Ayuda>Las filas válidas se vuelven a verificar al confirmar. El resultado final indica cuáles se aplicaron; las rechazadas quedan disponibles para corregir.</Ayuda></div></>}
        {terminado && <p role="status" className="text-sm text-texto-debil">{resumen.aplicada === 1 ? "Se aplicó" : "Se aplicaron"} {plural(resumen.aplicada ?? 0, "fila", "filas")}. Las filas rechazadas no modificaron el padrón ni el cupo.</p>}
        {rechazos.length > 0 && <div className="space-y-3"><Button variant="secondary" disabled={descargando} onClick={() => descargar(formato.recursoRechazos, { importacion: lote.id }, `rechazos-${tipo}.xlsx`)}>Descargar filas rechazadas</Button><div className="max-h-72 overflow-auto"><table className="w-full text-left text-sm"><thead><tr className="border-b border-division"><th scope="col" className="p-2">Fila</th><th scope="col" className="p-2">Motivo</th></tr></thead><tbody>{rechazos.map((fila) => <tr key={fila.fila} className="border-b border-division"><td className="p-2">{fila.fila}</td><td className="space-y-2 p-2"><p>{fila.errores?.join(" ") || "Revisá el detalle descargable."}</p>{tipo === "consumos" && fila.estado === "revision" && <Field label={`Motivo de revisión de fila ${fila.fila}`} ayuda="Completá sólo si verificaste que es una prestación distinta."><Textarea maxLength={255} disabled={ocupado} value={revisiones[fila.fila] || ""} onChange={(e) => setRevisiones({ ...revisiones, [fila.fila]: e.target.value })} /></Field>}</td></tr>)}</tbody></table></div></div>}
      </section>}

    </div>;
}
