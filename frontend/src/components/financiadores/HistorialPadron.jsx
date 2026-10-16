import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import { errorFinanciador, filasDe } from "@/api/financiadores";
import { POR_PAGINA } from "@/api/queries";
import { Badge, Button, Spinner } from "@/components/ui";
import TarjetaFicha from "./TarjetaFicha";
import { cn } from "@/lib/cn";
import { fechaHora } from "@/lib/format";
import { BLOQUES_PADRON, CAMPOS_COBRANZA, CAMPOS_SALUD, CAMPOS_LEGAJO, CAMPOS_FAMILIA, valorCampoPadron } from "./padronCampos";

const CAMPOS = [...BLOQUES_PADRON.flatMap((bloque) => bloque.campos), ...CAMPOS_FAMILIA, ...CAMPOS_LEGAJO, ...CAMPOS_SALUD, ...CAMPOS_COBRANZA];
const TIPOS = { actualizacion: "Actualización", finalizacion: "Finalización", reactivacion: "Reactivación" };
const ORIGENES = { manual: "Carga manual", importacion: "Importación de padrón" };
const motivoVisible = (evento) => evento.lote && evento.origen === "importacion" && evento.motivo === "Importación v2 de padrón" ? "Importación de padrón" : evento.motivo;
export default function HistorialPadron({ ruta, scope, titulo = "Historia administrativa" }) {
  const [pagina, setPagina] = useState(1);
  const consulta = useQuery({ queryKey: [...scope, "historial", ruta, pagina], queryFn: () => api.get(`${ruta}?${new URLSearchParams({ page: pagina, page_size: POR_PAGINA })}`), gcTime: 0, retry: false });
  return <section aria-label={titulo}><TarjetaFicha titulo={titulo} icono="reloj">
    {consulta.isLoading ? <Spinner label="Consultando historial…" /> : consulta.error ? <p role="alert">{errorFinanciador(consulta.error)} <Button variant="ghost" onClick={() => consulta.refetch()}>Reintentar</Button></p> : <>
      {!filasDe(consulta.data).length ? <p className="text-sm text-texto-debil">No hay cambios registrados.</p> : <ol className="relative space-y-5 border-l border-borde pl-6">{filasDe(consulta.data).map((evento) => <li key={evento.id} className="relative text-sm">
        <span className="absolute -left-[31px] top-1 size-3 rounded-full border-2 border-superficie bg-accent" aria-hidden="true" />
        <div className="flex flex-wrap items-center gap-2"><Badge tone={evento.tipo === "finalizacion" ? "amber" : evento.tipo === "reactivacion" ? "green" : "info"}>{TIPOS[evento.tipo] || evento.tipo || "Corrección"}</Badge><span className="font-semibold tabular-nums">{fechaHora(evento.registrado)}</span></div>
        <div className="mt-1.5 space-y-0.5 text-texto-debil"><p>Registrado por {evento.usuario_nombre || "Usuario no disponible"}</p>
          {evento.motivo && <p className="text-texto-suave">Motivo: {motivoVisible(evento)}</p>}{evento.origen && <p>Origen: {ORIGENES[evento.origen] || evento.origen}{evento.lote ? ` · Lote ${evento.lote}` : ""}</p>}</div>
        {Object.entries(evento.cambios || {}).length > 0 && <dl className="mt-3 grid gap-px overflow-hidden rounded-md border border-division bg-division sm:grid-cols-2">{Object.entries(evento.cambios).map(([name, cambio]) => {
          const campo = CAMPOS.find((item) => item.name === name) || { name, label: name.startsWith("legajo:") ? `Presentación ${name.split(":")[1]}` : name };
          const anterior = valorCampoPadron(campo, cambio.anterior);
          return <div key={name} className="min-w-0 bg-superficie px-3 py-2.5"><dt className="text-xs font-medium uppercase tracking-wide text-texto-debil">{campo.label}</dt><dd className="mt-1 break-words whitespace-pre-wrap"><span className={cn("text-texto-tenue", anterior !== "Sin informar" && "line-through")}>{anterior}</span><span className="px-1.5 text-texto-debil" aria-label="cambió a">→</span><span className="font-medium">{valorCampoPadron(campo, cambio.nuevo)}</span></dd></div>;
        })}</dl>}
      </li>)}</ol>}
      <div className="mt-5 flex flex-wrap items-center justify-between gap-2 border-t border-division pt-4 text-sm text-texto-debil"><span>{consulta.data?.count ?? 0} cambios · Página {pagina}</span><div className="flex gap-2"><Button variant="ghost" size="sm" disabled={pagina === 1 || consulta.isFetching} onClick={() => setPagina((previa) => previa - 1)}>Anterior</Button><Button variant="ghost" size="sm" disabled={!consulta.data?.next || consulta.isFetching} onClick={() => setPagina((previa) => previa + 1)}>Siguiente</Button></div></div>
    </>}
  </TarjetaFicha></section>;
}
