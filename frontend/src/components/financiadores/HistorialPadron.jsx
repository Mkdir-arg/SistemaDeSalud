import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import { errorFinanciador, filasDe } from "@/api/financiadores";
import { POR_PAGINA } from "@/api/queries";
import { Button, Card, Spinner } from "@/components/ui";
import { fechaHora } from "@/lib/format";
import { BLOQUES_PADRON, CAMPOS_COBRANZA, CAMPOS_SALUD, CAMPOS_LEGAJO, CAMPOS_FAMILIA, valorCampoPadron } from "./padronCampos";

const CAMPOS = [...BLOQUES_PADRON.flatMap((bloque) => bloque.campos), ...CAMPOS_FAMILIA, ...CAMPOS_LEGAJO, ...CAMPOS_SALUD, ...CAMPOS_COBRANZA];
const ORIGENES = { manual: "Carga manual", importacion: "Importación de padrón" };
const motivoVisible = (evento) => evento.lote && evento.origen === "importacion" && evento.motivo === "Importación v2 de padrón" ? "Importación de padrón" : evento.motivo;
export default function HistorialPadron({ ruta, scope, titulo = "Historia administrativa" }) {
  const [pagina, setPagina] = useState(1);
  const consulta = useQuery({ queryKey: [...scope, "historial", ruta, pagina], queryFn: () => api.get(`${ruta}?${new URLSearchParams({ page: pagina, page_size: POR_PAGINA })}`), gcTime: 0, retry: false });
  return <section aria-label={titulo} className="space-y-3"><h2 className="text-lg font-semibold">{titulo}</h2><Card className="p-4">
    {consulta.isLoading ? <Spinner label="Consultando historial…" /> : consulta.error ? <p role="alert">{errorFinanciador(consulta.error)} <Button variant="ghost" onClick={() => consulta.refetch()}>Reintentar</Button></p> : <>
      {!filasDe(consulta.data).length ? <p className="text-sm text-texto-debil">No hay cambios registrados.</p> : <ol className="space-y-4">{filasDe(consulta.data).map((evento) => <li key={evento.id} className="border-b border-division pb-3 text-sm">
        <p className="font-semibold">{evento.tipo || "Corrección"} · {fechaHora(evento.registrado)}</p><p>Registrado por {evento.usuario_nombre || "Usuario no disponible"}</p>
        {evento.motivo && <p>Motivo: {motivoVisible(evento)}</p>}{evento.origen && <p className="text-texto-debil">Origen: {ORIGENES[evento.origen] || evento.origen}{evento.lote ? ` · Lote ${evento.lote}` : ""}</p>}
        {Object.entries(evento.cambios || {}).length > 0 && <dl className="mt-2 grid gap-2 sm:grid-cols-2">{Object.entries(evento.cambios).map(([name, cambio]) => {
          const campo = CAMPOS.find((item) => item.name === name) || { name, label: name.startsWith("legajo:") ? `Presentación ${name.split(":")[1]}` : name };
          return <div key={name}><dt className="font-medium">{campo.label}</dt><dd className="break-words whitespace-pre-wrap">{valorCampoPadron(campo, cambio.anterior)} → {valorCampoPadron(campo, cambio.nuevo)}</dd></div>;
        })}</dl>}
      </li>)}</ol>}
      <div className="mt-4 flex flex-wrap items-center justify-between gap-2 text-sm"><span>{consulta.data?.count ?? 0} cambios · Página {pagina}</span><div className="flex gap-2"><Button variant="ghost" size="sm" disabled={pagina === 1 || consulta.isFetching} onClick={() => setPagina((previa) => previa - 1)}>Anterior</Button><Button variant="ghost" size="sm" disabled={!consulta.data?.next || consulta.isFetching} onClick={() => setPagina((previa) => previa + 1)}>Siguiente</Button></div></div>
    </>}
  </Card></section>;
}
