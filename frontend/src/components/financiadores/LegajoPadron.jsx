import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import { errorFinanciador, filasDe } from "@/api/financiadores";
import { POR_PAGINA } from "@/api/queries";
import { Badge, Button, Spinner } from "@/components/ui";
import TarjetaFicha from "./TarjetaFicha";
import FormularioPadron from "./FormularioPadron";
import { CAMPOS_LEGAJO, TIPOS_LEGAJO, ESTADOS_LEGAJO } from "./padronCampos";
import { estadoVencimiento } from "@/lib/padronEdicion";
export default function LegajoPadron({ ruta, persona, scope, puedeEditar, actualizado, integrado = false, onEdicion, onOcupado }) {
  const [pagina, setPagina] = useState(1);
  const [edicion, setEdicion] = useState(null);
  useEffect(() => { onEdicion?.(edicion ? "legajo" : null); }, [edicion, onEdicion]);
  const consulta = useQuery({ queryKey: [...scope, "legajo", persona.id, pagina], queryFn: () => api.get(`${ruta}legajo/?${new URLSearchParams({ page: pagina, page_size: POR_PAGINA })}`), gcTime: 0, retry: false });
  return <section aria-label="Legajo administrativo" className="space-y-3"><div hidden={integrado && Boolean(edicion)}><TarjetaFicha titulo="Legajo administrativo" icono="fileText" descripcion="Presentación registrada; sin archivo adjunto. Las referencias remiten al original externo. Los vencimientos generan avisos; no cortan cobertura automáticamente. El CUD se registra en el recurso de salud protegido." accion={puedeEditar && <Button size="sm" variant="secondary" onClick={() => setEdicion({ estado: "pendiente" })}>Registrar presentación</Button>}>
    {persona.estado_tramite === "completo" && <p role="note" className="mb-4 rounded-md bg-superficie-2 p-3 text-sm text-texto-debil">El trámite está completo. Para agregar una presentación pendiente u observar un documento, primero cambiá el trámite a «En revisión» desde «Trámite y credencial».</p>}
    {consulta.isLoading ? <Spinner label="Consultando legajo…" /> : consulta.error ? <p role="alert">{errorFinanciador(consulta.error)} <Button variant="ghost" onClick={() => consulta.refetch()}>Reintentar</Button></p> : <>
      {!filasDe(consulta.data).length ? <p className="text-sm text-texto-debil">No hay presentaciones registradas.</p> : <ul className="space-y-3">{filasDe(consulta.data).map((documento) => <li key={documento.id} className="flex flex-wrap justify-between gap-3 rounded-md border border-division p-4"><div className="min-w-0 space-y-1 text-sm"><p className="flex flex-wrap items-center gap-2"><span className="font-semibold">{TIPOS_LEGAJO[documento.tipo] || documento.tipo}</span><Badge tone={documento.estado === "verificado" ? "green" : documento.estado === "observado" ? "amber" : "neutral"}>{ESTADOS_LEGAJO[documento.estado] || documento.estado}</Badge><Badge tone={estadoVencimiento(documento.vence_en) === "Vencido" ? "amber" : "gray"}>{estadoVencimiento(documento.vence_en)}</Badge></p><p className="text-texto-debil">Presentado: {documento.presentado_en || "Sin informar"} · Verificado: {documento.verificado_en || "Sin informar"} · Vencimiento: {documento.vence_en || "Sin informar"}</p><p className="break-words">Referencia: {documento.referencia || "Sin informar"}</p></div>{puedeEditar && <Button size="sm" variant="ghost" onClick={() => setEdicion(documento)}>Editar presentación</Button>}</li>)}</ul>}
      <div className="mt-4 flex items-center justify-between gap-2 text-sm text-texto-debil"><span>{consulta.data?.count ?? 0} presentaciones · Página {pagina}</span><div className="flex gap-2"><Button size="sm" variant="ghost" disabled={pagina === 1 || consulta.isFetching} onClick={() => setPagina(pagina - 1)}>Anterior</Button><Button size="sm" variant="ghost" disabled={!consulta.data?.next || consulta.isFetching} onClick={() => setPagina(pagina + 1)}>Siguiente</Button></div></div>
    </>}</TarjetaFicha>
    </div>
    {edicion && <FormularioPadron integrado={integrado} onOcupado={onOcupado} titulo={edicion.id ? "Editar presentación" : "Registrar presentación"} campos={CAMPOS_LEGAJO.map((campo) => ({ ...campo, required: ["tipo", "estado"].includes(campo.name) }))} inicial={edicion} requiereCambio={Boolean(edicion.id)} guardar={(cambios, motivo) => {
      const body = { ...(edicion.id ? { id: edicion.id } : { ...edicion }), ...cambios, revision: persona.revision, motivo };
      return edicion.id ? api.patch(`${ruta}legajo/`, body) : api.post(`${ruta}legajo/`, body);
    }} recargar={async () => { setEdicion(null); await actualizado(); }} onClose={() => setEdicion(null)} onGuardado={async () => { setEdicion(null); await actualizado(); }} />}
  </section>;
}
