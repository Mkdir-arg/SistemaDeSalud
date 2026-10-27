import { useEffect, useRef, useState } from "react";
import { api } from "@/api/client";
import { errorFinanciador, importarFinanciador, rutaFinanciador } from "@/api/financiadores";
import { Ayuda, Badge, Button, Field, Spinner, Textarea } from "@/components/ui";
import { BotonArchivoAnotado, PasoPreparar, PasoRevisar, PestanasFilas, TablaFilas, pestanaInicial } from "./ImportacionPasos";
import RevisionFilaSistema from "./RevisionFilaSistema";
import { plural } from "@/lib/format";

const APLICADOS = new Set(["aplicada"]);
const EN_PROCESO = new Set(["procesando", "aplicando", "pendiente", "validando"]);
const ESTADOS = { valida: "Lista para importar", revision: "Requiere revisión", rechazada: "Rechazada", error_tecnico: "Error técnico", aplicada: "Aplicada", omitida: "Excluida" };
// Mismas pestañas que OSTEL; «A revisar» reúne todo lo que necesita una acción.
const PESTANAS = [
  { key: "revision", label: "A revisar", incluye: (f) => ["revision", "rechazada", "error_tecnico"].includes(f.estado) },
  { key: "valida", label: "Listas", incluye: (f) => f.estado === "valida" },
  { key: "aplicada", label: "Aplicadas", incluye: (f) => f.estado === "aplicada" },
  { key: "omitida", label: "Excluidas", incluye: (f) => f.estado === "omitida" },
  { key: "todas", label: "Todas", incluye: () => true },
];

export default function ImportacionSistema({ organizacion, tipo, formato, onAplicado, onBloqueosChange, lote, setLote, lotes, setPagina, soloDetalle = false, coberturaHabilitada = true }) {
  const [archivo, setArchivo] = useState(null);
  const [error, setError] = useState(null);
  const [ocupado, setOcupado] = useState(false);
  const [descargando, setDescargando] = useState(false);
  const [revisiones, setRevisiones] = useState({});
  const [revisionesCobertura, setRevisionesCobertura] = useState({});
  const [edicion, setEdicion] = useState(null);
  const [filtro, setFiltro] = useState(() => pestanaInicial(PESTANAS, lote?.filas || []));
  const clave = useRef(crypto.randomUUID());
  useEffect(() => { clave.current = crypto.randomUUID(); }, [coberturaHabilitada]);
  const activo = useRef(true);
  useEffect(() => { activo.current = true; return () => { activo.current = false; }; }, []);
  useEffect(() => { onBloqueosChange({ selector: ocupado || descargando || !!edicion, cierre: ocupado || !!edicion }); }, [ocupado, descargando, edicion, onBloqueosChange]);
  useEffect(() => { setRevisiones({}); setRevisionesCobertura({}); setError(null); setEdicion(null); setFiltro(pestanaInicial(PESTANAS, lote?.filas || [])); }, [lote?.id]); // eslint-disable-line react-hooks/exhaustive-deps
  async function previsualizar(e) {
    e.preventDefault(); if (!archivo) return;
    setOcupado(true); setError(null);
    try {
      const data = await importarFinanciador(organizacion.id, tipo, archivo, clave.current, formato.recursoRevision, coberturaHabilitada);
      if (activo.current) { setLote(data); setPagina(1); lotes.refetch(); }
    } catch (err) { if (activo.current) setError(err); }
    finally { if (activo.current) setOcupado(false); }
  }
  async function confirmar() {
    setOcupado(true); setError(null);
    try {
      const motivosCobertura = Object.fromEntries(Object.entries(revisionesCobertura).filter(([, motivo]) => motivo.trim()));
      const pendientes = (actual) => Number(actual.resumen?.valida || 0) + (actual.filas || []).filter((f) => f.estado === "revision" && f.conflicto_cobertura && motivosCobertura[f.fila]).length;
      let pendiente = pendientes(lote);
      do {
        const data = await api.post(rutaFinanciador(organizacion.id, formato.recursoConfirmacion), { importacion: lote.id, revisiones_duplicados: tipo === "consumos" ? Object.fromEntries(Object.entries(revisiones).filter(([, motivo]) => motivo.trim())) : {}, ...(tipo === "padron" ? { revisiones_cobertura: motivosCobertura } : {}) });
        if (!activo.current) break;
        setLote(data);
        const restantes = pendientes(data);
        // Cada confirmación es recuperable. Un error técnico o falta de
        // progreso exige reintento explícito, nunca un bucle de pedidos.
        if (APLICADOS.has(data.estado) || !restantes || data.resumen?.error_tecnico > 0 || restantes >= pendiente) break;
        pendiente = restantes;
      } while (activo.current);
      if (activo.current) { lotes.refetch(); await onAplicado(); }
    } catch (err) { if (activo.current) setError(err); }
    finally { if (activo.current) setOcupado(false); }
  }
  async function guardar(accion) {
    setOcupado(true); setError(null);
    try {
      const data = await api.post(rutaFinanciador(organizacion.id, "subsanar-importacion"), {
        importacion: lote.id, fila: edicion.fila, revision: edicion.revision ?? 1, motivo: edicion.motivo, accion,
        ...(accion === "corregir" ? { valores: edicion.valores } : {}),
      });
      if (activo.current) { setLote(data); setEdicion(null); lotes.refetch(); }
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
  const columnas = lote?.columnas || [];
  const valor = (f, columna) => f.original?.[columnas.indexOf(columna)] || "";
  const filas = (lote?.filas || []).filter(PESTANAS.find((p) => p.key === filtro).incluye);
  const hayRevision = tipo === "consumos" ? Object.values(revisiones).some((motivo) => motivo.trim()) : (lote?.filas || []).some((f) => f.estado === "revision" && f.conflicto_cobertura && revisionesCobertura[f.fila]?.trim());
  return <div className="space-y-5">
      {error && !edicion && <div role="alert" className="rounded-md bg-badge-error-bg p-3 text-badge-error-fg">{errorFinanciador(error)}</div>}
      {!soloDetalle && <>
        <PasoPreparar deshabilitado={descargando} onDescargar={() => descargar("plantilla", formato.parametrosPlantilla(tipo), formato.nombrePlantilla(tipo))} ayuda={tipo === "padron" ? <>
              <span className="block">La plantilla incluye identidad, contacto, régimen, familia, trámite y credencial registrada externamente. Conservá los identificadores como texto y cargá primero al titular.</span>
              <span className="block">La carga agrega o actualiza afiliados. Las celdas nuevas vacías no borran datos existentes y los afiliados ausentes del archivo no se dan de baja.</span>
              <span className="block">No se importan bajas, reactivaciones, datos de salud, parentesco protegido ni datos de cobranza o bancarios. Esas operaciones se realizan desde los recursos correspondientes de la ficha.</span>
            </> : <span className="block">La plantilla incluye las prestaciones de este financiador. Indicá número de afiliado y documento tal como figuran en el padrón.</span>} />
        <PasoRevisar onSubmit={previsualizar} enviable={!!archivo} ocupado={ocupado && !lote} deshabilitado={ocupado}
          ayuda="Hasta 5 MiB. Conservá identificadores y ceros tal como fueron informados."
          onArchivo={(nuevo) => { setArchivo(nuevo); setLote(null); setRevisiones({}); setError(null); clave.current = crypto.randomUUID(); }} />
      </>}
      {lote && <section aria-label="Resumen de importación" className="space-y-4 border-t border-division pt-5">
        {tipo === "padron" && <p role="status">{resumen.cobertura_habilitada === false ? "Personas nuevas: sólo registro administrativo, sin habilitar cobertura." : "Personas nuevas: cobertura habilitada, sujeta a plan, fechas y reglas."} En personas existentes se conserva la habilitación actual.</p>}
        <div className="flex flex-wrap items-center justify-between gap-2"><h3 className="font-semibold">3. {terminado ? "Resultado de la importación" : "Confirmá las filas válidas"}</h3><Badge tone={terminado ? "green" : "amber"}>{terminado ? "Procesada" : procesando ? "En proceso" : "Pendiente de confirmación"}</Badge></div>
        {resumen.revision > 0 && <p className="text-sm text-badge-amber-fg">{tipo === "padron" ? `${resumen.revision} filas requieren revisión. En los conflictos de cobertura podés confirmar que se conserva la habilitación actual; el resto se corrige con «Revisar fila».` : `${resumen.revision} posibles duplicados necesitan revisión individual y motivo.`}</p>}
        {resumen.error_tecnico > 0 && <p role="alert" className="text-sm text-badge-error-fg">{resumen.error_tecnico} filas tuvieron un error técnico. Reintentá la confirmación; lo ya aplicado no se duplica.</p>}
        {procesando ? <Spinner label="Procesando el lote. Podés volver a consultarlo desde las importaciones recientes." /> : !terminado && <><div className="flex items-center gap-2"><Button disabled={ocupado || !!edicion || (validas === 0 && !hayRevision && !resumen.error_tecnico)} onClick={confirmar}>{ocupado ? "Importando…" : resumen.error_tecnico ? "Reintentar confirmación" : hayRevision ? "Importar filas válidas y revisadas" : `Importar ${plural(validas, "fila válida", "filas válidas")}`}</Button><Ayuda>Las filas válidas se vuelven a verificar al confirmar. El resultado final indica cuáles se aplicaron; las rechazadas quedan disponibles para corregir.</Ayuda></div></>}
        {terminado && <p role="status" className="text-sm text-texto-debil">{resumen.aplicada === 1 ? "Se aplicó" : "Se aplicaron"} {plural(resumen.aplicada ?? 0, "fila", "filas")}. Las filas rechazadas no modificaron el padrón ni el cupo.</p>}
        {rechazos.length > 0 && (archivo && !soloDetalle ? <BotonArchivoAnotado organizacion={organizacion} archivo={archivo} importacion={lote.id} deshabilitado={ocupado || !!edicion} onError={setError} /> : <Button variant="secondary" disabled={descargando} onClick={() => descargar(formato.recursoRechazos, { importacion: lote.id }, `rechazos-${tipo}.xlsx`)}>Descargar filas rechazadas</Button>)}
        <PestanasFilas pestanas={PESTANAS} filas={lote.filas || []} valor={filtro} onChange={setFiltro} />
        <TablaFilas key={`${lote.id}:${filtro}`} filas={filas}
          persona={(f) => tipo === "padron"
            ? <>{f.datos?.nombre || valor(f, "Nombre y apellido") || "Sin nombre"}<br /><span className="text-texto-debil">Documento {f.datos?.documento || valor(f, "Documento") || "sin informar"} · afiliado {f.datos?.numero || valor(f, "N.º de afiliado") || "sin informar"}</span></>
            : <>Afiliado {valor(f, "N.º de afiliado") || "sin informar"}<br /><span className="text-texto-debil">Documento {valor(f, "Documento") || "sin informar"} · {valor(f, "Prestación") || "sin prestación"}</span></>}
          detalle={(f) => <div className="space-y-2">{ESTADOS[f.estado] || f.estado}<p>{f.errores?.join(" ")}</p>
            {tipo === "padron" && f.estado === "revision" && f.conflicto_cobertura && <Field label={`Motivo para conservar cobertura actual de fila ${f.fila}`} ayuda={`Actualmente ${f.conflicto_cobertura.actual ? "habilitada" : "sin habilitar"}; el lote solicita ${f.conflicto_cobertura.solicitada ? "habilitarla" : "sólo registro administrativo"}. La revisión conservará el valor actual.`}><Textarea maxLength={255} disabled={ocupado} value={revisionesCobertura[f.fila] || ""} onChange={(e) => setRevisionesCobertura({ ...revisionesCobertura, [f.fila]: e.target.value })} /></Field>}
            {tipo === "consumos" && f.estado === "revision" && <Field label={`Motivo de revisión de fila ${f.fila}`} ayuda="Completá sólo si verificaste que es una prestación distinta."><Textarea maxLength={255} disabled={ocupado} value={revisiones[f.fila] || ""} onChange={(e) => setRevisiones({ ...revisiones, [f.fila]: e.target.value })} /></Field>}
          </div>}
          accion={(f) => columnas.length > 0 && <Button variant="secondary" size="sm" className="whitespace-nowrap" disabled={ocupado || !!edicion}
            onClick={() => { setError(null); setEdicion({ ...f, valores: columnas.map((_, i) => f.original?.[i] ?? ""), motivo: "", lectura: ["aplicada", "omitida"].includes(f.estado) }); }}>
            {["aplicada", "omitida"].includes(f.estado) ? "Ver detalle" : "Revisar fila"}</Button>} />
        {edicion && <RevisionFilaSistema edicion={edicion} setEdicion={setEdicion} columnas={columnas} ocupado={ocupado} error={error && errorFinanciador(error)}
          onGuardar={guardar} onCerrar={() => { setEdicion(null); setError(null); }} />}
      </section>}

    </div>;
}
