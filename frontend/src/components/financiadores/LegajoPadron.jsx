import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import { errorFinanciador, filasDe } from "@/api/financiadores";
import { POR_PAGINA } from "@/api/queries";
import { Badge, Button, Card, Spinner } from "@/components/ui";
import FormularioPadron from "./FormularioPadron";
import { CAMPOS_LEGAJO, TIPOS_LEGAJO, ESTADOS_LEGAJO } from "./padronCampos";
import { estadoVencimiento } from "@/lib/padronEdicion";
export default function LegajoPadron({ ruta, persona, scope, puedeEditar, actualizado }) {
  const [pagina, setPagina] = useState(1);
  const [edicion, setEdicion] = useState(null);
  const consulta = useQuery({ queryKey: [...scope, "legajo", persona.id, pagina], queryFn: () => api.get(`${ruta}legajo/?${new URLSearchParams({ page: pagina, page_size: POR_PAGINA })}`), gcTime: 0, retry: false });
  return <section aria-label="Legajo administrativo" className="space-y-3"><div className="flex flex-wrap items-center justify-between gap-2"><h2 className="text-lg font-semibold">Legajo administrativo</h2>{puedeEditar && <Button variant="secondary" onClick={() => setEdicion({ estado: "pendiente" })}>Registrar presentación</Button>}</div>
    <p className="text-sm text-texto-debil">Presentación registrada; sin archivo adjunto. Las referencias remiten al original externo. Los vencimientos generan avisos; no cortan cobertura automáticamente. El CUD se registra en el recurso de salud protegido.</p>
    {persona.estado_tramite === "completo" && <p role="note" className="text-sm text-texto-debil">El trámite está completo. Para agregar una presentación pendiente u observar un documento, primero cambiá el trámite a «En revisión» desde «Trámite y credencial».</p>}
    <Card className="p-4">{consulta.isLoading ? <Spinner label="Consultando legajo…" /> : consulta.error ? <p role="alert">{errorFinanciador(consulta.error)} <Button variant="ghost" onClick={() => consulta.refetch()}>Reintentar</Button></p> : <>
      {!filasDe(consulta.data).length ? <p className="text-sm text-texto-debil">No hay presentaciones registradas.</p> : <ul className="space-y-3">{filasDe(consulta.data).map((documento) => <li key={documento.id} className="flex flex-wrap justify-between gap-3 border-b border-division pb-3"><div className="min-w-0 text-sm"><p className="font-medium">{TIPOS_LEGAJO[documento.tipo] || documento.tipo} · {ESTADOS_LEGAJO[documento.estado] || documento.estado}</p><p>Presentado: {documento.presentado_en || "Sin informar"} · Verificado: {documento.verificado_en || "Sin informar"}</p><p>Vencimiento: {documento.vence_en || "Sin informar"} · <Badge tone={estadoVencimiento(documento.vence_en) === "Vencido" ? "amber" : "gray"}>{estadoVencimiento(documento.vence_en)}</Badge></p><p className="break-words">Referencia: {documento.referencia || "Sin informar"}</p><p className="text-texto-debil">Presentación registrada; sin archivo adjunto.</p></div>{puedeEditar && <Button size="sm" variant="ghost" onClick={() => setEdicion(documento)}>Editar presentación</Button>}</li>)}</ul>}
      <div className="mt-4 flex items-center justify-between gap-2 text-sm"><span>{consulta.data?.count ?? 0} presentaciones · Página {pagina}</span><div className="flex gap-2"><Button size="sm" variant="ghost" disabled={pagina === 1 || consulta.isFetching} onClick={() => setPagina(pagina - 1)}>Anterior</Button><Button size="sm" variant="ghost" disabled={!consulta.data?.next || consulta.isFetching} onClick={() => setPagina(pagina + 1)}>Siguiente</Button></div></div>
    </>}</Card>
    {edicion && <FormularioPadron titulo={edicion.id ? "Editar presentación" : "Registrar presentación"} campos={CAMPOS_LEGAJO.map((campo) => ({ ...campo, required: ["tipo", "estado"].includes(campo.name) }))} inicial={edicion} requiereCambio={Boolean(edicion.id)} guardar={(cambios, motivo) => {
      const body = { ...(edicion.id ? { id: edicion.id } : { ...edicion }), ...cambios, revision: persona.revision, motivo };
      return edicion.id ? api.patch(`${ruta}legajo/`, body) : api.post(`${ruta}legajo/`, body);
    }} recargar={async () => { setEdicion(null); await actualizado(); }} onClose={() => setEdicion(null)} onGuardado={async () => { setEdicion(null); await actualizado(); }} />}
  </section>;
}
