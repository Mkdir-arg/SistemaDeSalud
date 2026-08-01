import { useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/api/client";
import { useAccion } from "@/api/queries";
import { PageHeader } from "@/components/Shell";
import { Badge, Button, Card } from "@/components/ui";
import { EstadoError, EstadoVacio, Skeleton } from "@/components/ui/estados";
import { useToast } from "@/components/ui/toast";
import { antiguedad } from "@/lib/format";
import { cn } from "@/lib/cn";
import { estadoCaso, nodeCat } from "@/theme";

const PRIO = { urgente: { label: "Urgente", tone: "error" }, alta: { label: "Alta", tone: "amber" } };

/** Color de la espera: a los 15 min avisa, a los 30 alarma. */
function claseEspera(iso) {
  const min = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 60000));
  return min >= 30 ? "text-danger" : min >= 15 ? "text-badge-amber-fg" : "text-texto-debil";
}

/** Detalle de un paso (nodo): indicadores del momento + los casos parados ahí. */
export default function PuestoDetalle() {
  const { id } = useParams();
  const navigate = useNavigate();
  const toast = useToast();

  const q = useQuery({
    queryKey: ["puesto", id],
    queryFn: () => api.get(`/puestos/${id}/`),
    refetchInterval: 30_000, // el puesto cambia solo: llegan y salen casos
  });

  const tomar = useAccion((caso) => api.post(`/casos/${caso}/tomar/`), {
    onError: (e) => toast.deError(e, "No se pudo tomar el caso."),
  });
  const llamar = useAccion(({ caso, box }) => api.post(`/casos/${caso}/llamar/`, { box_id: box }), {
    onError: (e) => toast.deError(e, "No se pudo llamar al paciente."),
  });

  if (q.isLoading) return <CargandoPuesto />;
  if (q.error) {
    return (
      <div className="p-8">
        <EstadoError
          error={q.error}
          titulo="No pudimos cargar este paso"
          onReintentar={q.refetch}
        />
      </div>
    );
  }

  const { nodo, indicadores: ind, casos, mi_box: miBox } = q.data;
  const cat = nodeCat[nodo.tipo] || nodeCat.form;

  const tiles = [
    { label: nodo.con_fila ? "En cola" : "Ahora", n: ind.ahora },
    { label: "Urgentes", n: ind.urgentes, alerta: ind.urgentes > 0 },
    { label: "Resueltos hoy", n: ind.hoy },
  ];

  return (
    <>
      <PageHeader subtitle={[nodo.flujo_titulo, nodo.area_nombre].filter(Boolean).join(" · ")} />

      <div className="flex flex-col gap-[22px] px-lg pb-8 pt-[22px] sm:px-8">
        {/* Encabezado del paso */}
        <div className="flex items-center gap-3">
          <span
            className="flex size-10 shrink-0 items-center justify-center rounded-md border"
            // Las 10 categorías de nodo son dinámicas: no puede ser una clase.
            style={{ background: `var(--color-nodo-${nodo.tipo}-tint)`, borderColor: `var(--color-nodo-${nodo.tipo}-bd)` }}
          >
            <span className="size-3.5 rounded-sm" style={{ background: `var(--color-nodo-${nodo.tipo}-sol)` }} />
          </span>
          <div>
            <div className="text-micro font-bold tracking-wide text-texto-tenue">{cat.name.toUpperCase()}</div>
            <h2 className="text-xxl font-extrabold tracking-tight">{nodo.titulo}</h2>
          </div>
        </div>

        {/* Indicadores */}
        <div className="grid grid-cols-[repeat(auto-fit,minmax(9.5rem,1fr))] gap-3">
          {tiles.map((t) => (
            <Card key={t.label} className={cn("border-l-[3px] px-lg py-3.5", t.alerta ? "border-l-danger" : "border-l-borde")}>
              <div className={cn("text-cifra-lg font-extrabold leading-none tabular-nums", t.alerta ? "text-danger" : "text-texto")}>
                {t.n}
              </div>
              <div className="mt-1.5 text-sm text-texto-debil">{t.label}</div>
            </Card>
          ))}
          <Card className="px-lg py-3.5">
            <div className={cn("text-xl font-extrabold leading-tight", ind.desde ? "text-texto" : "text-texto-tenue")}>
              {ind.desde ? `hace ${antiguedad(ind.desde)}` : "—"}
            </div>
            <div className="mt-1.5 text-sm text-texto-debil">El más antiguo</div>
          </Card>
        </div>

        {/* Casos parados en este paso */}
        <Card className="overflow-hidden">
          <div className="border-b border-division px-lg py-3 text-md font-bold">
            Casos en este paso <span className="font-medium text-texto-tenue">({casos.length})</span>
          </div>
          {casos.length === 0 ? (
            <EstadoVacio titulo="No hay casos en este paso" detalle="Cuando lleguen, los vas a ver acá." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-md">
                <thead className="bg-superficie-2 text-left">
                  <tr>
                    {["Paciente", "Prioridad", "Estado", "Espera", "Asignado", ""].map((h, i) => (
                      <th key={i} className="whitespace-nowrap px-lg py-2.5 text-sm font-semibold text-texto-debil">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {casos.map((c) => {
                    const est = estadoCaso[c.estado] || { label: c.estado_display, tone: "neutral" };
                    const p = PRIO[c.prioridad];
                    return (
                      <tr
                        key={c.id}
                        onClick={() => navigate(`/casos/${c.id}`)}
                        className="cursor-pointer border-t border-division hover:bg-superficie-2"
                      >
                        <td className="whitespace-nowrap px-lg py-3 font-semibold">{c.ciudadano_nombre || "—"}</td>
                        <td className="px-lg py-3">
                          {p ? <Badge tone={p.tone}>{p.label}</Badge> : <span className="text-texto-tenue">Normal</span>}
                        </td>
                        <td className="px-lg py-3">
                          {c.esperando ? <Badge tone="amber">Esperando</Badge> : <Badge tone={est.tone}>{est.label}</Badge>}
                        </td>
                        <td className={cn("whitespace-nowrap px-lg py-3 font-semibold tabular-nums", claseEspera(c.creado))}>
                          {antiguedad(c.creado)}
                        </td>
                        <td className="whitespace-nowrap px-lg py-3 text-texto-suave">
                          {c.asignado_nombre || <span className="text-texto-tenue">—</span>}
                        </td>
                        <td className="whitespace-nowrap px-lg py-3 text-right" onClick={(e) => e.stopPropagation()}>
                          <AccionCaso
                            c={c}
                            nodo={nodo}
                            miBox={miBox}
                            ocupado={tomar.isPending || llamar.isPending}
                            onAbrir={() => navigate(`/casos/${c.id}`)}
                            onTomar={() => tomar.mutate(c.id, { onSuccess: () => navigate(`/casos/${c.id}`) })}
                            onLlamar={() => llamar.mutate({ caso: c.id, box: miBox }, { onSuccess: () => navigate(`/casos/${c.id}`) })}
                          />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>
    </>
  );
}

/** La acción depende del estado del caso y del tipo de paso. */
function AccionCaso({ c, nodo, miBox, ocupado, onAbrir, onTomar, onLlamar }) {
  if (c.mio) return <Button size="sm" onClick={onAbrir}>Continuar</Button>;
  if (nodo.con_fila && c.en_fila) {
    return miBox ? (
      <Button size="sm" disabled={ocupado} onClick={onLlamar}>{ocupado ? "…" : "Llamar"}</Button>
    ) : (
      <Button size="sm" variant="secondary" disabled title="Ocupá tu box en «Mi trabajo»">Ocupá un box</Button>
    );
  }
  if (!c.asignado) {
    return <Button size="sm" variant="secondary" disabled={ocupado} onClick={onTomar}>{ocupado ? "…" : "Tomar y abrir"}</Button>;
  }
  return <Button size="sm" variant="secondary" onClick={onAbrir}>Abrir</Button>;
}

function CargandoPuesto() {
  return (
    <div className="flex flex-col gap-[22px] px-lg pb-8 pt-[22px] sm:px-8" role="status" aria-label="Cargando el paso…">
      <Skeleton className="h-10 w-64" />
      <div className="grid grid-cols-[repeat(auto-fit,minmax(9.5rem,1fr))] gap-3">
        {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-[72px]" />)}
      </div>
      <Skeleton className="h-80" />
    </div>
  );
}
