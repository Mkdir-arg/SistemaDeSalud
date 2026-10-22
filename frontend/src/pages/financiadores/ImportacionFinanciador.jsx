import { useEffect, useRef, useState } from "react";
import { Ayuda, Button, Field, Modal, Select, Spinner } from "@/components/ui";
import ImportacionSistema from "./ImportacionSistema";
import ImportacionAdministrativa from "./ImportacionAdministrativa";
import RevisionTecnicaExcel from "./RevisionTecnicaExcel";
import { formatosPara, guardarFormatoPreferido, leerFormatoPreferido } from "./formatosImportacion";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import { errorFinanciador, filasDe, rutaFinanciador } from "@/api/financiadores";
import { POR_PAGINA } from "@/api/queries";

const EN_PROCESO = new Set(["procesando", "aplicando", "pendiente", "validando"]);
const FLUJOS = { administrativa: ImportacionAdministrativa, importacion: ImportacionSistema, revision: RevisionTecnicaExcel };

export default function ImportacionFinanciador({ usuarioId, organizacion, tipo, scope, onClose, onAplicado }) {
  const opciones = formatosPara(tipo);
  const [pagina, setPagina] = useState(1);
  const [lote, setLote] = useState(null);
  const [coberturaHabilitada, setCoberturaHabilitada] = useState(true);
  const [historialAbierto, setHistorialAbierto] = useState(false);
  const [loteHistorico, setLoteHistorico] = useState(null);
  const [bloqueosHistorial, setBloqueosHistorial] = useState({ selector: false, cierre: false });
  const tituloHistorial = useRef(null);
  const accesoHistorial = useRef(null);
  useEffect(() => {
    if (historialAbierto) tituloHistorial.current?.focus();
    else accesoHistorial.current?.focus();
  }, [historialAbierto, loteHistorico?.id]);
  const lotes = useQuery({
    queryKey: [...scope, "importaciones", tipo, pagina],
    queryFn: () => api.get(`${rutaFinanciador(organizacion.id, "importaciones")}?${new URLSearchParams({ tipo, page: pagina, page_size: POR_PAGINA })}`),
    gcTime: 0,
    refetchInterval: EN_PROCESO.has(lote?.estado) || EN_PROCESO.has(loteHistorico?.estado) ? 2000 : false,
  });
  const registros = filasDe(lotes.data).filter((item) => item.tipo === tipo);
  useEffect(() => {
    setLote((actual) => {
      if (!actual || !EN_PROCESO.has(actual.estado)) return actual;
      return filasDe(lotes.data).find((item) => item.id === actual.id) || actual;
    });
  }, [lotes.data]);
  useEffect(() => {
    setLoteHistorico((actual) => actual && EN_PROCESO.has(actual.estado)
      ? filasDe(lotes.data).find((item) => item.id === actual.id) || actual : actual);
  }, [lotes.data]);
  useEffect(() => {
    if (loteHistorico) setLote((actual) => actual?.id === loteHistorico.id ? loteHistorico : actual);
  }, [loteHistorico]);
  const [preferencia, setPreferencia] = useState(() => leerFormatoPreferido(usuarioId, tipo, opciones));
  const [bloqueos, setBloqueos] = useState({ selector: false, cierre: false });
  const formato = opciones.find((item) => item.id === preferencia.id) || opciones[0];
  const Flujo = FLUJOS[formato.modo];
  const formatoHistorico = opciones.find((item) => item.id === (loteHistorico?.version === 3 ? "ostel" : "sistema"));
  const DetalleHistorico = formatoHistorico && FLUJOS[formatoHistorico.modo];

  function cerrarHistorial() {
    setHistorialAbierto(false);
    setLoteHistorico(null);
    setBloqueosHistorial({ selector: false, cierre: false });
    lotes.refetch();
  }

  function seleccionar(event) {
    const id = event.target.value;
    if (!opciones.some((item) => item.id === id)) return;
    setLote(null);
    setPreferencia({ id, persistencia: guardarFormatoPreferido(usuarioId, tipo, id) });
  }

  return <Modal title={historialAbierto ? "Importaciones registradas" : `Importar ${tipo === "padron" ? "padrón" : "consumos externos"}`}
    onClose={historialAbierto ? bloqueosHistorial.cierre ? undefined : cerrarHistorial : bloqueos.cierre ? undefined : onClose} width={historialAbierto ? 1120 : 840}>
    <div hidden={historialAbierto} className="space-y-5">
      <Field label="Formato del archivo" ayuda="La selección se recuerda para tu usuario en este navegador. Podés solicitar formatos personalizados contactando a soporte técnico.">
        <Select value={formato.id} onChange={seleccionar} disabled={bloqueos.selector}>
          {opciones.map((item) => <option key={item.id} value={item.id}>{item.nombre}</option>)}
        </Select>
      </Field>
      {tipo === "padron" && <div className="flex items-center gap-2">
        <label className="flex items-center gap-2 font-semibold"><input type="checkbox" checked={coberturaHabilitada} disabled={bloqueos.selector}
          onChange={(event) => { setCoberturaHabilitada(event.target.checked); setLote(null); }} />Habilitar cobertura</label>
        <Ayuda etiqueta="Ayuda sobre cobertura de la importación">Se aplica a las personas nuevas. Desmarcá para registrar sólo datos administrativos. En personas existentes se conserva la habilitación actual; las diferencias quedan como conflictos para revisión. Las prestaciones siguen sujetas al plan, las fechas y las reglas de cobertura.</Ayuda>
      </div>}
      {!preferencia.persistencia && <p role="status" className="text-sm text-texto-debil">Este navegador no permite guardar la preferencia. Podés continuar seleccionando el formato en cada apertura.</p>}
      <Flujo key={formato.id} formato={formato} organizacion={organizacion} tipo={tipo} scope={scope}
        onAplicado={onAplicado} onBloqueosChange={setBloqueos} coberturaHabilitada={coberturaHabilitada}
        lote={lote} setLote={setLote} lotes={lotes} setPagina={setPagina} />
      <button ref={accesoHistorial} type="button" aria-haspopup="dialog" aria-expanded={historialAbierto}
        disabled={bloqueos.selector} onClick={() => setHistorialAbierto(true)}
        className="flex w-full items-center justify-between border-t border-division py-4 text-left font-semibold hover:text-accent disabled:opacity-50">
        Importaciones registradas <span aria-hidden="true">▸</span>
      </button>
    </div>
    {historialAbierto && <div className="space-y-5">
      <div className="flex items-center justify-between gap-3">
        <h3 ref={tituloHistorial} tabIndex={-1} className="font-semibold outline-none">{loteHistorico ? `Importación ${loteHistorico.id}` : "Elegí una importación para consultar sus filas"}</h3>
        <Button variant="ghost" disabled={bloqueosHistorial.cierre} onClick={loteHistorico ? () => setLoteHistorico(null) : cerrarHistorial}>{loteHistorico ? "← Volver al historial" : "← Volver a importar"}</Button>
      </div>
      {loteHistorico && DetalleHistorico ? <DetalleHistorico key={loteHistorico.id} soloDetalle formato={formatoHistorico}
        organizacion={organizacion} tipo={tipo} scope={scope} onAplicado={onAplicado}
        onBloqueosChange={setBloqueosHistorial} lote={loteHistorico} setLote={setLoteHistorico} lotes={lotes} setPagina={setPagina} /> :
      <section aria-label="Importaciones registradas" className="border-t border-division pt-4">
        {lotes.isLoading ? <Spinner label="Consultando importaciones…" /> : lotes.error ?
          <p role="alert" className="mt-2 text-sm text-badge-error-fg">{errorFinanciador(lotes.error)} <button className="underline" onClick={() => lotes.refetch()}>Reintentar</button></p> :
          <div className="mt-2 space-y-2">
            {registros.length === 0 ? <p className="text-sm text-texto-debil">Todavía no hay importaciones de este tipo.</p> : registros.map((item) =>
              <button key={item.id} type="button" onClick={() => setLoteHistorico(item)} className="flex w-full flex-wrap justify-between gap-2 rounded-md border border-division px-3 py-2 text-left text-sm hover:bg-superficie-2">
                <span>{item.nombre_archivo || item.archivo_nombre || `Importación ${item.id}`}</span>
                <span>{item.creado ? new Date(item.creado).toLocaleString("es-AR") : ""}{item.version === 3 ? ` · ${item.resumen?.fuente === "bajas" ? "Evidencia de bajas" : "Padrón base"} · ${item.resumen?.aplicada || 0} aplicadas · ${item.resumen?.revision || 0} pendientes · ` : " "}{item.estado === "aplicada" ? "Procesada" : EN_PROCESO.has(item.estado) ? "En proceso" : "Revisar resumen"}</span>
              </button>)}
          </div>}
        {!lotes.isLoading && !lotes.error && (pagina > 1 || lotes.data?.next) &&
          <div className="mt-3 flex items-center justify-between gap-2 text-sm">
            <span className="text-texto-debil">Página {pagina}</span>
            <div className="flex gap-2">
              <Button size="sm" variant="ghost" disabled={pagina === 1 || lotes.isFetching || bloqueos.selector} onClick={() => setPagina(pagina - 1)}>Anterior</Button>
              <Button size="sm" variant="ghost" disabled={!lotes.data?.next || lotes.isFetching || bloqueos.selector} onClick={() => setPagina(pagina + 1)}>Siguiente</Button>
            </div>
          </div>}
      </section>}
    </div>}
  </Modal>;
}
