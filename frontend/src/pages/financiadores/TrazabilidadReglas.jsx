import { createPortal } from "react-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import { errorFinanciador, rutaFinanciador } from "@/api/financiadores";
import { Button, Modal, Spinner } from "@/components/ui";

export default function TrazabilidadReglas({ organizacion, usuarioId, onClose }) {
  const consulta = useQuery({
    queryKey: ["financiadores", usuarioId, organizacion.id, "historial-borradores"],
    queryFn: () => api.get(rutaFinanciador(organizacion.id, "borradores-derechos/historial")),
    gcTime: 0, retry: false, staleTime: Infinity, refetchOnWindowFocus: false,
  });
  const filas = consulta.data?.historial || [];
  return createPortal(<Modal title="Trazabilidad de reglas" onClose={onClose} width={760}>
    <div className="space-y-4">
      <p className="text-sm">Registro de configuración: quién incorporó cada versión, cuándo y con qué motivo. No es una aprobación ni una decisión de derechos.</p>
      <Button variant="secondary" disabled={consulta.isFetching} onClick={() => consulta.refetch()}>Volver a consultar</Button>
      {consulta.isFetching ? <Spinner label="Consultando trazabilidad…" /> : consulta.isError ?
        <p role="alert" className="text-sm text-badge-error-fg">{errorFinanciador(consulta.error)}</p> : filas.length ?
        <ol className="space-y-4" aria-label="Registros de versiones">
          {filas.map((fila) => <li className="space-y-2 break-words rounded-md border border-borde p-3 text-sm" key={`${fila.regla.regimen}:${fila.regla.plan_id}:${fila.regla.codigo}:${fila.regla.version}`}>
            <h3 className="font-semibold">{fila.regla.codigo} · v{fila.regla.version}</h3>
            <p>Autor del registro: Usuario #{fila.creado_por_id}</p>
            <p>Fecha y hora local: <time dateTime={fila.creado}>{new Date(fila.creado).toLocaleString("es-AR")}</time></p>
            <p>Motivo del registro: {fila.motivo}</p>
            <p>Fuente informada: {fila.regla.fuente}</p>
            <p>Ámbito: {fila.regla.regimen} · {fila.regla.plan_id == null ? "Todos los planes" : `Plan #${fila.regla.plan_id}`}</p>
            <p>{fila.regla.plazo_dias_corridos == null ? "Sin plazo configurado" : `Plazo configurado: ${fila.regla.plazo_dias_corridos} días corridos`}</p>
          </li>)}
        </ol> : <p className="text-sm">Todavía no hay versiones registradas.</p>}
    </div>
  </Modal>, document.body);
}
