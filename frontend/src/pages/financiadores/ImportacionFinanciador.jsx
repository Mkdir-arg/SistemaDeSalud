import { useEffect, useState } from "react";
import { Button, Field, Modal, Select, Spinner } from "@/components/ui";
import ImportacionSistema from "./ImportacionSistema";
import RevisionTecnicaExcel from "./RevisionTecnicaExcel";
import { formatosPara, guardarFormatoPreferido, leerFormatoPreferido } from "./formatosImportacion";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import { errorFinanciador, filasDe, rutaFinanciador } from "@/api/financiadores";
import { POR_PAGINA } from "@/api/queries";

const EN_PROCESO = new Set(["procesando", "aplicando", "pendiente", "validando"]);
const FLUJOS = { importacion: ImportacionSistema, revision: RevisionTecnicaExcel };

export default function ImportacionFinanciador({ usuarioId, organizacion, tipo, scope, onClose, onAplicado }) {
  const opciones = formatosPara(tipo);
  const [pagina, setPagina] = useState(1);
  const [lote, setLote] = useState(null);
  const lotes = useQuery({
    queryKey: [...scope, "importaciones", tipo, pagina],
    queryFn: () => api.get(`${rutaFinanciador(organizacion.id, "importaciones")}?${new URLSearchParams({ tipo, page: pagina, page_size: POR_PAGINA })}`),
    gcTime: 0,
    refetchInterval: lote && EN_PROCESO.has(lote.estado) ? 2000 : false,
  });
  const registros = filasDe(lotes.data).filter((item) => item.tipo === tipo);
  useEffect(() => {
    setLote((actual) => {
      if (!actual || !EN_PROCESO.has(actual.estado)) return actual;
      return filasDe(lotes.data).find((item) => item.id === actual.id) || actual;
    });
  }, [lotes.data]);
  const [preferencia, setPreferencia] = useState(() => leerFormatoPreferido(usuarioId, tipo, opciones));
  const [bloqueos, setBloqueos] = useState({ selector: false, cierre: false });
  const formato = opciones.find((item) => item.id === preferencia.id) || opciones[0];
  const Flujo = FLUJOS[formato.modo];

  function seleccionar(event) {
    const id = event.target.value;
    if (!opciones.some((item) => item.id === id)) return;
    setLote(null);
    setPreferencia({ id, persistencia: guardarFormatoPreferido(usuarioId, tipo, id) });
  }

  return <Modal title={`Importar ${tipo === "padron" ? "padrón" : "consumos externos"}`}
    onClose={bloqueos.cierre ? undefined : onClose} width={840}>
    <div className="space-y-5">
      <Field label="Formato del archivo" ayuda="La selección se recuerda para tu usuario en este navegador.">
        <Select value={formato.id} onChange={seleccionar} disabled={bloqueos.selector}>
          {opciones.map((item) => <option key={item.id} value={item.id}>{item.nombre}</option>)}
        </Select>
      </Field>
      {!preferencia.persistencia && <p role="status" className="text-sm text-texto-debil">Este navegador no permite guardar la preferencia. Podés continuar seleccionando el formato en cada apertura.</p>}
      <Flujo key={formato.id} formato={formato} organizacion={organizacion} tipo={tipo} scope={scope}
        onAplicado={onAplicado} onBloqueosChange={setBloqueos}
        lote={lote} setLote={setLote} lotes={lotes} setPagina={setPagina} />
      <section aria-label="Importaciones registradas" className="border-t border-division pt-4">
        <h3 className="font-semibold">Importaciones registradas</h3>
        {lotes.isLoading ? <Spinner label="Consultando importaciones…" /> : lotes.error ?
          <p role="alert" className="mt-2 text-sm text-badge-error-fg">{errorFinanciador(lotes.error)} <button className="underline" onClick={() => lotes.refetch()}>Reintentar</button></p> :
          <div className="mt-2 space-y-2">
            {registros.length === 0 ? <p className="text-sm text-texto-debil">Todavía no hay importaciones de este tipo.</p> : registros.map((item) =>
              <button key={item.id} type="button" disabled={bloqueos.selector} onClick={() => {
                // Los lotes existentes pertenecen al importador del sistema.
                // Consultarlos no cambia la preferencia para archivos nuevos.
                setPreferencia((actual) => ({ ...actual, id: "sistema" }));
                setLote(item);
              }} className="flex w-full flex-wrap justify-between gap-2 rounded-md border border-division px-3 py-2 text-left text-sm hover:bg-superficie-2">
                <span>{item.nombre_archivo || item.archivo_nombre || `Importación ${item.id}`}</span>
                <span>{item.estado === "aplicada" ? "Procesada" : EN_PROCESO.has(item.estado) ? "En proceso" : "Revisar resumen"}</span>
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
      </section>
    </div>
  </Modal>;
}
