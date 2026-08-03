import { useNavigate } from "react-router-dom";

import { api } from "@/api/client";
import { useAccion, useLista } from "@/api/queries";
import { Icon } from "@/components/icons";
import { PageHeader } from "@/components/Shell";
import { Button, Card } from "@/components/ui";
import { EstadoError, EstadoVacio, Skeleton } from "@/components/ui/estados";
import { antiguedad } from "@/lib/format";
import { cn } from "@/lib/cn";

/** Historial completo de avisos del usuario. */
export default function Notificaciones() {
  const navigate = useNavigate();
  const q = useLista("notificaciones", { pageSize: 50 });

  // Invalida la lista, que se refresca sola. El contador de la campana no: el
  // Shell todavía la maneja con su propio poll de 30 s, así que tarda hasta ese
  // lapso en bajar. Se arregla cuando la campana pase a TanStack Query.
  const leer = useAccion((ids) => api.post("/notificaciones/leer/", ids ? { ids } : {}));

  const hayNoLeidas = q.filas.some((n) => !n.leida);

  function abrir(n) {
    if (!n.leida) leer.mutate([n.id]);
    if (n.caso) navigate(`/casos/${n.caso}`);
  }

  return (
    <>
      <PageHeader
        subtitle="Tus avisos: estudios que volvieron, reasignaciones, casos urgentes y cancelaciones."
        right={
          hayNoLeidas && (
            <Button variant="secondary" disabled={leer.isPending} onClick={() => leer.mutate(undefined)}>
              Marcar todas leídas
            </Button>
          )
        }
      />
      <div className="px-lg pb-8 pt-[22px] sm:px-8">
        {q.isLoading ? (
          <Card className="overflow-hidden">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="flex gap-3 border-t border-division p-lg first:border-t-0">
                <Skeleton className="size-[30px] shrink-0 rounded-md" />
                <div className="flex-1 space-y-1.5">
                  <Skeleton className="h-3.5 w-52" />
                  <Skeleton className="h-3 w-72" />
                </div>
              </div>
            ))}
          </Card>
        ) : q.error ? (
          <EstadoError error={q.error} onReintentar={q.refetch} />
        ) : q.filas.length === 0 ? (
          <EstadoVacio
            titulo="No tenés notificaciones"
            detalle="Acá van a aparecer tus avisos a medida que sucedan."
            icono="bell"
          />
        ) : (
          <Card className="overflow-hidden">
            <ul>
              {q.filas.map((n) => (
                <li key={n.id}>
                  <button
                    onClick={() => abrir(n)}
                    className={cn(
                      "flex w-full gap-3 border-t border-division p-lg text-left first:border-t-0",
                      n.leida ? "hover:bg-superficie-2" : "bg-accent-50",
                    )}
                  >
                    <span className="flex size-[30px] shrink-0 items-center justify-center rounded-md bg-superficie-2 text-texto-debil">
                      <Icon name="bell" size={15} />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block text-md font-semibold">{n.titulo}</span>
                      {/* `texto-suave` y no `texto-debil`: sobre el tinte de «no leída»
                          (`accent-50`) el débil mide 4,31:1, por debajo de AA.
                          Es la tercera pantalla donde falla ese mismo par. */}
                      {n.detalle && <span className="block text-base text-texto-suave">{n.detalle}</span>}
                      <span className="mt-0.5 block text-xs text-texto-tenue">hace {antiguedad(n.creada)}</span>
                    </span>
                    {!n.leida && (
                      <span className="mt-1.5 size-2 shrink-0 rounded-pill bg-accent" aria-label="Sin leer" />
                    )}
                  </button>
                </li>
              ))}
            </ul>
          </Card>
        )}
      </div>
    </>
  );
}
