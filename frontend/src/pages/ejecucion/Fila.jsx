import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { api } from "@/api/client";
import { useAccion, useLista } from "@/api/queries";
import { Icon } from "@/components/icons";
import { Badge } from "@/components/ui";
import { EstadoError, EstadoVacio, Skeleton } from "@/components/ui/estados";
import { useToast } from "@/components/ui/toast";
import { antiguedad, casoId } from "@/lib/format";
import { cn } from "@/lib/cn";

const hora = (iso) =>
  new Date(iso).toLocaleTimeString("es-AR", { hour: "2-digit", minute: "2-digit" });

/**
 * Fila de espera de un área. Pantalla piloto de la migración: es la primera
 * hecha entera con la fundación nueva (tokens, componentes, TanStack Query,
 * responsive, estados y toasts) y sirve de patrón para las otras.
 */
export default function Fila() {
  const navigate = useNavigate();
  const toast = useToast();
  const [areaSel, setAreaSel] = useState(null);

  const q = useLista("items-fila", { atendido: false, pageSize: 200 });

  // Los urgentes van al frente; dentro de cada grupo manda el orden de llegada.
  const items = useMemo(
    () => [...q.filas].sort((a, b) => (b.urgente ? 1 : 0) - (a.urgente ? 1 : 0) || a.orden - b.orden),
    [q.filas],
  );

  const areas = useMemo(() => {
    const m = new Map();
    for (const it of items) if (it.area) m.set(it.area, it.area_nombre || `Área ${it.area}`);
    return [...m].map(([id, nombre]) => ({ id, nombre }));
  }, [items]);

  useEffect(() => {
    if (areas.length && !areas.some((a) => a.id === areaSel)) setAreaSel(areas[0].id);
  }, [areas, areaSel]);

  const boxes = useLista("boxes", { area: areaSel, activo: true, pageSize: 50 }, { enabled: areaSel != null });

  // En la fila quedan solo los que todavía no fueron llamados a un box.
  const fila = items.filter((it) => it.area === areaSel && !it.box);
  const areaNombre = areas.find((a) => a.id === areaSel)?.nombre || "Sala de espera";
  const siguiente = fila[0];

  const llamar = useAccion(({ caso, box }) => api.post(`/casos/${caso}/llamar/`, box ? { box_id: box.id } : {}), {
    onError: (e) => toast.deError(e, "No se pudo llamar al paciente."),
  });

  function alLlamar(box) {
    if (!siguiente) return;
    const caso = siguiente.caso;
    const quien = siguiente.persona || casoId(caso);
    llamar.mutate(
      { caso, box },
      {
        onSuccess: () => {
          toast.ok(`Llamaste a ${quien}`, { detalle: box ? `Pasá a ${box.nombre}` : undefined });
          // El profesional pasa directo a atender al paciente que llamó.
          navigate(`/casos/${caso}`);
        },
      },
    );
  }

  if (q.isLoading) return <CargandoFila />;
  if (q.error) return <div className="p-[30px]"><EstadoError error={q.error} onReintentar={q.refetch} /></div>;

  return (
    <div className="flex flex-col gap-lg p-lg sm:p-[26px] lg:px-[30px]">
      {/* Cabecera */}
      <section className="flex flex-wrap items-center gap-lg rounded-lg border border-borde bg-superficie px-xl py-lg">
        <span className="flex size-11 shrink-0 items-center justify-center rounded-md bg-nodo-espera-tint text-nodo-espera-sol">
          <Icon name="list" size={22} />
        </span>
        <div className="min-w-40 flex-1">
          <h2 className="text-xl font-bold">Fila de espera</h2>
          <p className="text-base text-texto-debil">FIFO + urgencia · se llama desde cada box</p>
        </div>
        {areas.length > 1 && (
          <select
            aria-label="Área de la fila"
            value={areaSel ?? ""}
            onChange={(e) => setAreaSel(Number(e.target.value))}
            className="h-9 rounded-md border border-campo-borde bg-superficie px-2 text-md outline-none focus:border-accent"
          >
            {areas.map((a) => <option key={a.id} value={a.id}>{a.nombre}</option>)}
          </select>
        )}
        <div className="text-right">
          <div className="text-2xl font-extrabold leading-none tabular-nums">{fila.length}</div>
          <div className="text-xs text-texto-tenue">en {areaNombre}</div>
        </div>
      </section>

      {/* Boxes: cada uno llama al siguiente de la cola */}
      <section className="rounded-lg border border-borde bg-superficie px-xl py-lg">
        <h3 className="mb-md text-sm font-bold text-texto-suave">Consultorios</h3>
        {boxes.isLoading ? (
          <div className="grid grid-cols-[repeat(auto-fill,minmax(11rem,1fr))] gap-2.5">
            {[0, 1].map((i) => <Skeleton key={i} className="h-[86px]" />)}
          </div>
        ) : boxes.filas.length === 0 ? (
          <div className="flex flex-wrap items-center justify-between gap-md">
            <span className="text-base text-texto-tenue">
              Esta área no tiene boxes configurados. Cargalos en Estructura → área → Boxes.
            </span>
            <BotonLlamar
              label="Llamar al siguiente"
              disabled={!siguiente || llamar.isPending}
              cargando={llamar.isPending}
              onClick={() => alLlamar(null)}
            />
          </div>
        ) : (
          <div className="grid grid-cols-[repeat(auto-fill,minmax(11rem,1fr))] gap-2.5">
            {boxes.filas.map((b) => (
              <div key={b.id} className="flex flex-col gap-2.5 rounded-md border border-borde p-3">
                <div className="flex items-center gap-2 text-md font-bold">
                  <Icon name="enter" size={15} className="text-nodo-espera-sol" /> {b.nombre}
                </div>
                <BotonLlamar
                  label="Llamar siguiente"
                  disabled={!siguiente || llamar.isPending}
                  cargando={llamar.isPending && llamar.variables?.box?.id === b.id}
                  onClick={() => alLlamar(b)}
                />
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Cola */}
      <section className="overflow-hidden rounded-lg border border-borde bg-superficie">
        <h3 className="px-xl py-lg text-lg font-bold">En espera</h3>
        {fila.length === 0 ? (
          <EstadoVacio
            titulo="La fila está vacía"
            detalle={`No hay pacientes esperando en ${areaNombre}.`}
            icono="list"
          />
        ) : (
          <ul className="border-t border-division">
            {/* Encabezado solo en pantallas anchas: en angosto cada fila se lee
                como una ficha y los rótulos de columna sobran. */}
            <li className="hidden bg-superficie-2 px-xl py-2.5 text-micro font-bold tracking-wide text-texto-tenue sm:grid sm:grid-cols-[2.75rem_5.5rem_1fr_5.5rem_5.5rem] sm:gap-md">
              <span /><span>TURNO</span><span>PERSONA</span><span>INGRESO</span><span>ESPERA</span>
            </li>
            {fila.map((it, i) => (
              <li key={it.id}>
                <button
                  onClick={() => navigate(`/casos/${it.caso}`)}
                  className={cn(
                    "flex w-full flex-wrap items-center gap-x-md gap-y-1 border-t border-division px-xl py-3.5 text-left first:border-t-0",
                    "sm:grid sm:grid-cols-[2.75rem_5.5rem_1fr_5.5rem_5.5rem]",
                    i === 0 ? "bg-accent-50 shadow-[inset_3px_0_0_var(--color-accent)]" : "hover:bg-superficie-2",
                  )}
                >
                  <span
                    className={cn(
                      "flex size-6.5 shrink-0 items-center justify-center rounded-pill text-sm font-bold",
                      // Relleno + su color de texto: `accent` a secas es claro en
                      // tema oscuro (para usarse como texto) y el blanco encima
                      // caía a 2,7:1.
                      // `texto-suave` y no `texto-debil`: medido, sobre el gris de
                      // `division` el débil daba 4,36:1, justo por debajo de AA.
                      i === 0 ? "bg-accent-fuerte text-sobre-accent" : "bg-division text-texto-suave",
                    )}
                  >
                    {i + 1}
                  </span>
                  <span className="font-mono font-bold">{it.turno || casoId(it.caso)}</span>
                  <span className="flex min-w-0 items-center gap-2">
                    <span className="truncate text-md text-texto-medio">{it.persona || casoId(it.caso)}</span>
                    {it.urgente && <Badge tone="error">urgente</Badge>}
                  </span>
                  {/* Sobre la fila destacada (tinte índigo) el `texto-debil`
                      quedaba en 4,31:1. Un paso más oscuro y pasa en ambos fondos. */}
                  <span className="text-base text-texto-suave">{hora(it.ingreso)}</span>
                  <span className="text-base tabular-nums text-texto-suave">{antiguedad(it.ingreso)}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function CargandoFila() {
  return (
    <div className="flex flex-col gap-lg p-lg sm:p-[26px] lg:px-[30px]" role="status" aria-label="Cargando fila…">
      <Skeleton className="h-[78px]" />
      <Skeleton className="h-[130px]" />
      <Skeleton className="h-80" />
    </div>
  );
}

function BotonLlamar({ label, disabled, cargando, onClick }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={cn(
        "flex h-9 items-center justify-center gap-1.5 rounded-md px-3.5 text-base font-semibold transition-colors",
        disabled
          ? "cursor-not-allowed bg-division text-texto-tenue"
          // Antes era el teal de la categoría con texto blanco: medido, daba 2,57:1
        // en los dos temas (defecto que ya venía del diseño original). Llamar al
        // siguiente paciente es LA acción primaria de la pantalla, así que usa el
        // relleno de marca; el teal queda como color de categoría en el icono.
        : "bg-accent-fuerte text-sobre-accent hover:bg-accent-hover",
      )}
    >
      <Icon name="enter" size={14} /> {cargando ? "Llamando…" : label}
    </button>
  );
}
