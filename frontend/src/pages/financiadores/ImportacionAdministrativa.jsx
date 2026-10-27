import { useEffect, useRef, useState } from "react";
import { api } from "@/api/client";
import { errorFinanciador, rutaFinanciador } from "@/api/financiadores";
import { Ayuda, Button } from "@/components/ui";
import { plural } from "@/lib/format";
import { BotonArchivoAnotado, PasoPreparar, PasoRevisar, PestanasFilas, TablaFilas, pestanaInicial } from "./ImportacionPasos";
import RevisionFilaOstel, { fichaInicial } from "./RevisionFilaOstel";

const ESTADOS = { valida: "Lista para importar", revision: "Requiere revisión", aplicada: "Aplicada", omitida: "Excluida" };
const PESTANAS = [
  { key: "revision", label: "A revisar", incluye: (f) => f.estado === "revision" },
  { key: "valida", label: "Listas", incluye: (f) => f.estado === "valida" },
  { key: "advertencias", label: "Con advertencias", incluye: (f) => f.advertencias?.length > 0 },
  { key: "aplicada", label: "Aplicadas", incluye: (f) => f.estado === "aplicada" },
  { key: "omitida", label: "Excluidas", incluye: (f) => f.estado === "omitida" },
  { key: "todas", label: "Todas", incluye: () => true },
];

export default function ImportacionAdministrativa({ organizacion, formato, lote, setLote, lotes, onAplicado, onBloqueosChange, soloDetalle = false, coberturaHabilitada = true }) {
  const [archivo, setArchivo] = useState(null);
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState(null);
  const [edicion, setEdicion] = useState(null);
  const [filtro, setFiltro] = useState(() => pestanaInicial(PESTANAS, lote?.filas || []));
  const clave = useRef(crypto.randomUUID());
  useEffect(() => { clave.current = crypto.randomUUID(); }, [coberturaHabilitada]);
  const activo = useRef(true);
  useEffect(() => { activo.current = true; return () => { activo.current = false; }; }, []);
  useEffect(() => { onBloqueosChange({ selector: ocupado || !!edicion, cierre: ocupado || !!edicion }); }, [ocupado, edicion, onBloqueosChange]);
  useEffect(() => { setEdicion(null); setError(null); setFiltro(pestanaInicial(PESTANAS, lote?.filas || [])); }, [lote?.id]); // eslint-disable-line react-hooks/exhaustive-deps
  const ruta = (recurso) => rutaFinanciador(organizacion.id, recurso);

  async function ejecutar(accion) {
    setOcupado(true); setError(null);
    try { await accion(); }
    catch (e) { if (activo.current) setError(errorFinanciador(e)); }
    finally { if (activo.current) setOcupado(false); }
  }
  async function revisar(event) {
    event.preventDefault();
    if (!archivo || ocupado) return;
    await ejecutar(async () => {
      const datos = new FormData();
      datos.append("archivo", archivo); datos.append("clave", clave.current); datos.append("cobertura_habilitada", String(coberturaHabilitada));
      const nuevo = await api.multipart(ruta(formato.recursoRevision), datos);
      if (activo.current) { setLote(nuevo); lotes.refetch(); }
    });
  }
  async function confirmar() {
    await ejecutar(async () => {
      let actual = lote;
      while (activo.current && actual.resumen.valida > 0) {
        const nuevo = await api.post(ruta("confirmar-importacion"), { importacion: actual.id });
        if (!activo.current) return;
        setLote(nuevo);
        if (nuevo.resumen.valida >= actual.resumen.valida) break;
        actual = nuevo;
      }
      lotes.refetch(); await onAplicado();
    });
  }
  async function guardar(accion) {
    await ejecutar(async () => {
      const nuevo = await api.post(ruta("subsanar-ostel"), {
        importacion: lote.id, fila: edicion.fila, revision: edicion.revision,
        datos: edicion.datos, motivo: edicion.motivo, accion,
        ...(accion === "corregir" && !edicion.bloqueo_fuente ? { ficha: edicion.ficha } : {}),
      });
      if (activo.current) {
        setLote(nuevo);
        const fila = nuevo.filas.find((f) => f.fila === edicion.fila);
        if (fila?.errores.some((e) => e.includes("no se guardó la corrección"))) {
          setEdicion({ ...fila, datos: edicion.datos, ficha: edicion.ficha, motivo: edicion.motivo });
          setError(fila.errores.join(" "));
        } else setEdicion(null);
        lotes.refetch();
      }
    });
  }
  const filas = (lote?.filas || []).filter(PESTANAS.find((p) => p.key === filtro).incluye);
  return <div className="space-y-5">
    {!soloDetalle && <>
      <PasoPreparar deshabilitado={ocupado} ayuda={<>{formato.descripcion} Las ausencias no generan bajas. Los archivos de bajas sólo se conservan como evidencia para revisión.</>}
        onDescargar={() => ejecutar(() => api.download(`${ruta("plantilla")}?${new URLSearchParams(formato.parametrosPlantilla("padron"))}`, formato.nombrePlantilla("padron")))} />
      <PasoRevisar onSubmit={revisar} enviable={!!archivo} ocupado={ocupado && !lote} deshabilitado={ocupado || !!edicion}
        ayuda="Hasta 5 MiB. Conservá identificadores y ceros tal como fueron informados."
        onArchivo={(nuevo) => { setArchivo(nuevo); setLote(null); setError(null); clave.current = crypto.randomUUID(); }} />
    </>}
    {error && !edicion && <p role="alert" className="rounded-md bg-badge-error-bg p-3 text-badge-error-fg">{error}</p>}
    {/* Archivo rechazado entero: la copia marca las celdas que lo impidieron. */}
    {!soloDetalle && archivo && !lote && error && <BotonArchivoAnotado organizacion={organizacion} archivo={archivo} deshabilitado={ocupado} onError={(e) => e && setError(errorFinanciador(e))} />}
    {lote && <section className="space-y-4 border-t border-division pt-5" aria-label="Revisión administrativa">
      <p role="status">{lote.resumen.cobertura_habilitada === true ? "Personas nuevas: cobertura habilitada, sujeta a plan, fechas y reglas." : "Personas nuevas: sólo registro administrativo, sin habilitar cobertura."} En personas existentes se conserva la habilitación actual.</p>
      <h3 className="font-semibold">3. Confirmá las filas válidas</h3>
      <div className="flex items-center gap-2"><Button disabled={ocupado || !lote.resumen.valida || !!edicion} onClick={confirmar}>{ocupado ? "Importando…" : `Importar ${plural(lote.resumen.valida || 0, "fila válida", "filas válidas")}`}</Button><Ayuda>Las pendientes no bloquean las válidas. Cada fila se revalida al importar; las ya aplicadas no se repiten.</Ayuda></div>
      {!soloDetalle && archivo && (lote.resumen.revision > 0 || lote.resumen.advertencias > 0) && <BotonArchivoAnotado organizacion={organizacion} archivo={archivo} importacion={lote.id} deshabilitado={ocupado || !!edicion} onError={(e) => setError(e && errorFinanciador(e))} />}
      <PestanasFilas pestanas={PESTANAS} filas={lote.filas} valor={filtro} onChange={setFiltro} />
      <TablaFilas key={`${lote.id}:${filtro}`} filas={filas}
        persona={(f) => <>{f.datos.nombre || "Sin nombre"}<br /><span className="text-texto-debil">CUIL {f.datos.cuil || "sin informar"} · interno {f.datos.numero_interno || "sin informar"}</span></>}
        detalle={(f) => <>{ESTADOS[f.estado]}<p>{f.errores.join(" ")}</p>{f.advertencias?.length ? <p className="text-texto-debil">Advertencias: {f.advertencias.join(" ")}</p> : null}</>}
        accion={(f) => <Button variant="secondary" size="sm" className="whitespace-nowrap" disabled={ocupado || !!edicion} onClick={() => { setError(null); setEdicion({ ...f, datos: { ...f.datos }, ficha: fichaInicial(f), motivo: "", lectura: ["aplicada", "omitida"].includes(f.estado) }); }}>{["aplicada", "omitida"].includes(f.estado) ? "Ver detalle" : "Revisar fila"}</Button>} />
      {edicion && <RevisionFilaOstel edicion={edicion} setEdicion={setEdicion} ocupado={ocupado} error={error}
        onGuardar={guardar} onCerrar={() => { setEdicion(null); setError(null); }} />}
    </section>}
  </div>;
}
