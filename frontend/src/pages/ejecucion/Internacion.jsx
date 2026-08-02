import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { api } from "@/api/client";
import { useAccion, useLista } from "@/api/queries";
import { useInstitucion } from "@/auth/InstitutionContext";
import { Icon } from "@/components/icons";
import { Button, Input } from "@/components/ui";
import { EstadoError, EstadoVacio, Skeleton } from "@/components/ui/estados";
import { useToast } from "@/components/ui/toast";
import { antiguedad, casoId } from "@/lib/format";
import { cn } from "@/lib/cn";

/*
 * Tablero de camas.
 *
 * Lo que se mira acá es una sola pregunta —¿entra otro paciente?— y la respuesta
 * tiene que verse sin leer: por eso el sector muestra el porcentaje grande y las
 * camas son fichas de un color por estado. La lista detallada es para después.
 *
 * Los cuatro estados son operativamente distintos y ninguno se puede colapsar:
 * una cama en higiene no está libre, y una fuera de servicio no cuenta para
 * nada — ni en el numerador ni en el denominador de la ocupación.
 */
const ESTADOS = {
  libre: { label: "Libre", chip: "bg-badge-green-bg text-badge-green-fg", punto: "bg-badge-green-fg" },
  ocupada: { label: "Ocupada", chip: "bg-accent-50 text-accent", punto: "bg-accent-fuerte" },
  higiene: { label: "En higiene", chip: "bg-badge-amber-bg text-badge-amber-fg", punto: "bg-badge-amber-fg" },
  bloqueada: { label: "Fuera de servicio", chip: "bg-division text-texto-suave", punto: "bg-texto-tenue" },
};

// Umbrales de ocupación. No es decoración: un sector al 90 % es una decisión
// distinta a uno al 60 %, y quien mira el tablero de reojo tiene que verlo.
function tonoOcupacion(pct) {
  if (pct >= 90) return { texto: "text-danger", barra: "bg-danger" };
  if (pct >= 75) return { texto: "text-badge-amber-fg", barra: "bg-badge-amber-fg" };
  return { texto: "text-texto-fuerte", barra: "bg-accent-fuerte" };
}

export default function Internacion() {
  const { institucion } = useInstitucion();
  const [sectorSel, setSectorSel] = useState(null);

  const q = useLista(
    "camas",
    { "area__institucion": institucion?.id, pageSize: 500 },
    { enabled: institucion?.id != null },
  );

  const sectores = useMemo(() => {
    const m = new Map();
    for (const c of q.filas) {
      const clave = c.sector || "Sin sector";
      if (!m.has(clave)) {
        m.set(clave, { sector: clave, camas: [], total: 0, ocupadas: 0, libres: 0, higiene: 0, bloqueadas: 0 });
      }
      const s = m.get(clave);
      if (!c.activa) continue; // dada de baja: no existe a los fines del tablero
      s.camas.push(c);
      s.total += 1;
      s[{ ocupada: "ocupadas", libre: "libres", higiene: "higiene", bloqueada: "bloqueadas" }[c.estado]] += 1;
    }
    return [...m.values()]
      .map((s) => {
        // Sobre camas EN SERVICIO: contar las rotas en el denominador haría que
        // un sector con la mitad de las camas fuera de uso parezca desahogado.
        const operativas = s.total - s.bloqueadas;
        return { ...s, operativas, ocupacion: operativas ? Math.round((100 * s.ocupadas) / operativas) : 0 };
      })
      .sort((a, b) => a.sector.localeCompare(b.sector, "es"));
  }, [q.filas]);

  const totales = useMemo(() => {
    const t = sectores.reduce(
      (acc, s) => {
        for (const k of ["total", "operativas", "ocupadas", "libres", "higiene", "bloqueadas"]) acc[k] += s[k];
        return acc;
      },
      { total: 0, operativas: 0, ocupadas: 0, libres: 0, higiene: 0, bloqueadas: 0 },
    );
    return { ...t, ocupacion: t.operativas ? Math.round((100 * t.ocupadas) / t.operativas) : 0 };
  }, [sectores]);

  const visibles = sectorSel ? sectores.filter((s) => s.sector === sectorSel) : sectores;

  if (q.isLoading) return <Cargando />;
  if (q.error) return <div className="p-[30px]"><EstadoError error={q.error} onReintentar={q.refetch} /></div>;

  return (
    <div className="flex flex-col gap-lg p-lg sm:p-[26px] lg:px-[30px]">
      <section className="flex flex-wrap items-center gap-lg rounded-lg border border-borde bg-superficie px-xl py-lg">
        <span className="flex size-11 shrink-0 items-center justify-center rounded-md bg-nodo-atencion-tint text-nodo-atencion-sol">
          <Icon name="bed" size={22} />
        </span>
        <div className="min-w-40 flex-1">
          <h2 className="text-xl font-bold">Internación</h2>
          <p className="text-base text-texto-debil">
            {totales.ocupadas} de {totales.operativas} camas en servicio ocupadas
            {totales.bloqueadas > 0 && ` · ${totales.bloqueadas} fuera de servicio`}
          </p>
        </div>
        {sectores.length > 1 && (
          <select
            aria-label="Sector"
            value={sectorSel ?? ""}
            onChange={(e) => setSectorSel(e.target.value || null)}
            className="h-9 rounded-md border border-campo-borde bg-superficie px-2 text-md outline-none focus:border-accent"
          >
            <option value="">Todos los sectores</option>
            {sectores.map((s) => <option key={s.sector} value={s.sector}>{s.sector}</option>)}
          </select>
        )}
        <div className="text-right">
          <div className={cn("text-cifra font-extrabold leading-none tabular-nums", tonoOcupacion(totales.ocupacion).texto)}>
            {totales.ocupacion}%
          </div>
          <div className="text-xs text-texto-tenue">ocupación</div>
        </div>
      </section>

      {sectores.length === 0 ? (
        <EstadoVacio
          titulo="No hay camas cargadas"
          detalle="Cargalas en Estructura organizativa → área de internación."
          icono="bed"
        />
      ) : (
        visibles.map((s) => <Sector key={s.sector} sector={s} onCambio={q.refetch} />)
      )}
    </div>
  );
}

function Sector({ sector, onCambio }) {
  const tono = tonoOcupacion(sector.ocupacion);
  return (
    <section className="overflow-hidden rounded-lg border border-borde bg-superficie">
      <header className="flex flex-wrap items-center gap-lg border-b border-division px-xl py-lg">
        <div className="min-w-40 flex-1">
          <h3 className="text-lg font-bold">{sector.sector}</h3>
          <p className="text-base text-texto-debil">
            {sector.libres} {sector.libres === 1 ? "cama libre" : "camas libres"}
            {sector.higiene > 0 && ` · ${sector.higiene} en higiene`}
            {sector.bloqueadas > 0 && ` · ${sector.bloqueadas} fuera de servicio`}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {/* La barra dice lo mismo que el número, pero se lee de reojo. */}
          <div className="h-2 w-32 overflow-hidden rounded-pill bg-division" role="presentation">
            <div className={cn("h-full rounded-pill", tono.barra)} style={{ width: `${sector.ocupacion}%` }} />
          </div>
          <div className="text-right tabular-nums">
            <div className={cn("text-lg font-extrabold leading-none", tono.texto)}>{sector.ocupacion}%</div>
            <div className="text-xs text-texto-tenue">{sector.ocupadas}/{sector.operativas}</div>
          </div>
        </div>
      </header>
      <div className="grid grid-cols-[repeat(auto-fill,minmax(13rem,1fr))] gap-2.5 p-xl">
        {sector.camas.map((c) => <FichaCama key={c.id} cama={c} onCambio={onCambio} />)}
      </div>
    </section>
  );
}

function FichaCama({ cama, onCambio }) {
  const navigate = useNavigate();
  const toast = useToast();
  const [bloqueando, setBloqueando] = useState(false);
  const [motivo, setMotivo] = useState("");
  const est = ESTADOS[cama.estado] || ESTADOS.libre;

  const cambiar = useAccion(
    ({ estado, motivo }) => api.post(`/camas/${cama.id}/estado/`, { estado, motivo }),
    {
      onSuccess: () => { toast.ok(`Cama ${cama.nombre} actualizada`); onCambio?.(); },
      onError: (e) => toast.deError(e, "No se pudo cambiar el estado de la cama."),
    },
  );

  return (
    <div className={cn(
      "flex flex-col gap-2 rounded-md border p-3",
      cama.estado === "ocupada" ? "border-accent-100 bg-accent-50/40" : "border-borde",
    )}>
      <div className="flex items-center justify-between gap-2">
        <span className="flex items-center gap-2 font-mono text-md font-bold">
          <span className={cn("size-2.5 shrink-0 rounded-pill", est.punto)} aria-hidden="true" />
          {cama.nombre}
        </span>
        <span className={cn("rounded-pill px-2 py-px text-xs font-semibold", est.chip)}>{est.label}</span>
      </div>

      {cama.estado === "ocupada" ? (
        <button
          onClick={() => navigate(`/casos/${cama.caso_id}`)}
          className="min-w-0 text-left"
        >
          <span className="block truncate text-base font-semibold text-accent">
            {cama.paciente || casoId(cama.caso_id)}
          </span>
          <span className="block text-sm text-texto-tenue">internado hace {antiguedad(cama.desde)}</span>
        </button>
      ) : cama.estado === "higiene" ? (
        <div className="flex items-center justify-between gap-2">
          <span className="text-sm text-texto-tenue">esperando hace {antiguedad(cama.desde)}</span>
          <Button size="sm" variant="secondary" disabled={cambiar.isPending}
                  onClick={() => cambiar.mutate({ estado: "libre" })}>
            Higienizada
          </Button>
        </div>
      ) : cama.estado === "bloqueada" ? (
        <div className="flex items-center justify-between gap-2">
          <span className="min-w-0 flex-1 truncate text-sm text-texto-tenue" title={cama.motivo}>
            {cama.motivo || "Fuera de servicio"}
          </span>
          <Button size="sm" variant="secondary" disabled={cambiar.isPending}
                  onClick={() => cambiar.mutate({ estado: "libre" })}>
            Reactivar
          </Button>
        </div>
      ) : (
        /* Sacar una cama de servicio es raro; que ocupe lo mismo que la cama
           hacía que el tablero se leyera como una grilla de botones. Queda como
           acción secundaria, sin peso visual. */
        <div className="flex items-center justify-between gap-2">
          <span className="text-sm text-texto-tenue">disponible</span>
          <button
            disabled={cambiar.isPending}
            title="Marcar fuera de servicio"
            aria-label={`Marcar la cama ${cama.nombre} fuera de servicio`}
            onClick={() => setBloqueando(true)}
            className="flex size-7 flex-none items-center justify-center rounded-md text-texto-tenue transition-colors hover:bg-division hover:text-texto-medio"
          >
            <Icon name="alert" size={14} />
          </button>
        </div>
      )}

      {bloqueando && (
        <form
          className="flex flex-col gap-2 border-t border-division pt-2"
          onSubmit={(e) => {
            e.preventDefault();
            cambiar.mutate({ estado: "bloqueada", motivo }, { onSuccess: () => setBloqueando(false) });
          }}
        >
          <Input
            autoFocus
            value={motivo}
            onChange={(e) => setMotivo(e.target.value)}
            placeholder="Motivo (mantenimiento, obra…)"
            aria-label="Motivo por el que queda fuera de servicio"
          />
          <div className="flex gap-2">
            <Button size="sm" type="submit" disabled={cambiar.isPending}>Confirmar</Button>
            <Button size="sm" variant="secondary" type="button" onClick={() => setBloqueando(false)}>
              Cancelar
            </Button>
          </div>
        </form>
      )}
    </div>
  );
}

function Cargando() {
  return (
    <div className="flex flex-col gap-lg p-lg sm:p-[26px] lg:px-[30px]" role="status" aria-label="Cargando camas…">
      <Skeleton className="h-[78px]" />
      <Skeleton className="h-64" />
      <Skeleton className="h-64" />
    </div>
  );
}
