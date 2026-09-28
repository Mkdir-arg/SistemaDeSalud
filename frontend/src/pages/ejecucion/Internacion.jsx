import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

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
 *
 * Los NÚMEROS los cuenta el servidor y las FICHAS son otra consulta. No es una
 * separación caprichosa: la lista de camas está paginada con un tope duro de 200
 * filas, así que en cualquier hospital de más de 200 camas —cualquier hospital
 * público mediano— calcular la ocupación con lo que llega significaba dibujar un
 * porcentaje verosímil y falso sobre los sectores que entraron en la página, y
 * distinto del que muestra el Dashboard para el mismo día.
 */
const ESTADOS = {
  libre: { label: "Libre", chip: "bg-badge-green-bg text-badge-green-fg", punto: "bg-badge-green-fg" },
  ocupada: { label: "Ocupada", chip: "bg-accent-50 text-accent", punto: "bg-accent-fuerte" },
  higiene: { label: "En higiene", chip: "bg-badge-amber-bg text-badge-amber-fg", punto: "bg-badge-amber-fg" },
  bloqueada: { label: "Fuera de servicio", chip: "bg-division text-texto-suave", punto: "bg-texto-tenue" },
};

// El tablero queda abierto en un monitor de sala de enfermería toda la guardia.
// Sin esto, la única forma de que se actualizara era que alguien tocara la
// ventana: una cama que alguien acaba de ocupar desde el detalle del caso seguía
// mostrándose verde durante horas, y dos personas mandaban dos pacientes a la
// misma cama. El resto de las pantallas de monitor ya refrescan solas.
const REFRESCO_MS = 30_000;

// Tope real del servidor (`max_page_size`). Pedir más no trae más: DRF recorta
// en silencio y la pantalla se quedaba creyendo que tenía todo.
const MAX_FILAS = 200;

const claveSector = (subareaId, areaId) => (subareaId ? `s${subareaId}` : `a${areaId}`);

// Umbrales de ocupación. No es decoración: un sector al 90 % es una decisión
// distinta a uno al 60 %, y quien mira el tablero de reojo tiene que verlo.
function tonoOcupacion(pct) {
  if (pct >= 90) return { texto: "text-danger", barra: "bg-danger" };
  if (pct >= 75) return { texto: "text-badge-amber-fg", barra: "bg-badge-amber-fg" };
  return { texto: "text-texto-fuerte", barra: "bg-accent-fuerte" };
}

/**
 * Vuelve a dibujar cada tanto.
 *
 * Las antigüedades («internado hace 3 h», «esperando hace 40 min») se calculan
 * con `Date.now()` durante el render: sin un re-render periódico quedan clavadas
 * en el momento en que se abrió la pantalla y cuatro horas después siguen
 * diciendo «3 h». En un monitor que nadie toca en todo el turno, eso es la
 * diferencia entre una cama que se liberó recién y una que espera higiene desde
 * la mañana.
 */
function useReloj(ms) {
  const [, tic] = useState(0);
  useEffect(() => {
    const id = setInterval(() => tic((n) => n + 1), ms);
    return () => clearInterval(id);
  }, [ms]);
}

/** Cuán vieja es la foto que está en pantalla. Importa incluso con refresco
 *  automático: si se cae la red, es lo único que lo delata. */
function frescura(ms) {
  if (!ms) return "sin datos";
  const seg = Math.max(0, Math.round((Date.now() - ms) / 1000));
  return seg < 60 ? "recién" : `hace ${antiguedad(new Date(ms).toISOString())}`;
}

export default function Internacion() {
  const { institucion } = useInstitucion();
  const [sectorSel, setSectorSel] = useState(null);
  useReloj(REFRESCO_MS);

  // Conteos y porcentajes: los cuenta el servidor sobre TODAS las camas activas
  // de la institución, que es lo mismo que hace el Dashboard. Que las dos
  // pantallas del mismo hospital dieran distinto el mismo día es lo que hacía
  // que no se pudiera creer ninguna de las dos.
  const tab = useQuery({
    queryKey: ["camas-tablero", institucion?.id],
    queryFn: () => api.get(`/camas/tablero/?area__institucion=${institucion.id}`),
    enabled: institucion?.id != null,
    refetchInterval: REFRESCO_MS,
    refetchIntervalInBackground: false,
  });

  const sectores = useMemo(() => {
    const lista = tab.data?.sectores || [];
    // `Subarea` es única por área, no por institución: «Sala general» de Clínica
    // médica y «Sala general» de Cirugía es una configuración normal. El
    // servidor las agrupa bien (por id), pero rotuladas igual el jefe de Cirugía
    // lee la ocupación del otro servicio como si fuera la suya.
    const vistos = new Set();
    const repetidos = new Set();
    for (const s of lista) {
      if (vistos.has(s.sector)) repetidos.add(s.sector);
      vistos.add(s.sector);
    }
    return lista.map((s) => ({
      ...s,
      clave: claveSector(s.sector_id, s.area_id),
      rotulo: repetidos.has(s.sector) && s.area !== s.sector ? `${s.sector} · ${s.area}` : s.sector,
    }));
  }, [tab.data]);

  const sel = sectores.find((s) => s.clave === sectorSel) || null;

  // Las fichas. Con el sector elegido se piden sólo las de ese sector: es la
  // forma de ver el detalle completo de un servicio grande sin chocar con el
  // tope de filas del servidor.
  const q = useLista(
    "camas",
    {
      "area__institucion": institucion?.id,
      // Una cama dada de baja no existe a los fines del tablero. Sin este filtro
      // igual ocupaba un lugar del tope y desplazaba a una cama real.
      activa: true,
      subarea: sel?.sector_id ?? undefined,
      area: sel && !sel.sector_id ? sel.area_id : undefined,
      pageSize: MAX_FILAS,
    },
    {
      enabled: institucion?.id != null,
      refetchInterval: REFRESCO_MS,
      refetchIntervalInBackground: false,
    },
  );

  const porSector = useMemo(() => {
    const m = new Map();
    for (const c of q.filas) {
      const k = claveSector(c.subarea, c.area);
      if (!m.has(k)) m.set(k, []);
      m.get(k).push(c);
    }
    return m;
  }, [q.filas]);

  const visibles = sel ? [sel] : sectores;
  // Cuántas fichas no entraron. Los porcentajes siguen siendo correctos —los
  // cuenta el servidor—, pero las camas que faltan no se pueden mirar, y eso hay
  // que decirlo: una lista incompleta que se ve completa es peor que un aviso.
  // Con `keepPreviousData` en pantalla hay filas de la consulta anterior, así
  // que ahí el conteo todavía no significa nada.
  const estable = !q.isPlaceholderData;
  const mostradas = visibles.reduce((n, s) => n + (porSector.get(s.clave)?.length || 0), 0);
  const enSectores = visibles.reduce((n, s) => n + s.total, 0);
  const faltan = estable ? Math.max(0, enSectores - mostradas) : 0;
  const vacios = { total: 0, operativas: 0, ocupadas: 0, libres: 0, higiene: 0, bloqueadas: 0, ocupacion: 0 };
  // El número grande sigue al filtro. Antes era siempre el del hospital entero:
  // alguien filtraba UTI —un acto deliberado, quiere saber cómo está UTI— y
  // arriba seguía leyendo 33 % con UTI al 100 %.
  const foco = sel ?? tab.data?.totales ?? vacios;
  const rotuloFoco = sel ? sel.rotulo : "todo el hospital";
  const actualizado = Math.min(tab.dataUpdatedAt || Infinity, q.dataUpdatedAt || Infinity);
  const refrescar = () => { tab.refetch(); q.refetch(); };

  if (tab.isLoading) return <Cargando />;
  if (tab.error || q.error) {
    return <div className="p-[30px]"><EstadoError error={tab.error || q.error} onReintentar={refrescar} /></div>;
  }

  return (
    <div className="flex flex-col gap-lg p-lg sm:p-[26px] lg:px-[30px] xl:px-10">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold">Internación</h2>
          <p className="text-base text-texto-debil">
            {foco.ocupadas} de {foco.operativas} camas en servicio ocupadas
            {foco.bloqueadas > 0 && ` · ${foco.bloqueadas} fuera de servicio`}
            {` · ${tab.isFetching ? "actualizando…" : `actualizado ${frescura(actualizado === Infinity ? 0 : actualizado)}`}`}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {sectores.length > 1 && (
            <div className="flex max-w-full items-center gap-0.5 overflow-x-auto rounded-md border border-borde bg-superficie-2 p-1" role="group" aria-label="Sector">
              <button type="button" onClick={() => setSectorSel(null)} aria-pressed={!sel}
                className={cn("whitespace-nowrap rounded px-3 py-1.5 text-sm", !sel ? "bg-superficie font-semibold text-texto-fuerte shadow-card" : "text-texto-suave hover:text-texto-fuerte")}>
                Todos
              </button>
              {sectores.map((s) => (
                <button key={s.clave} type="button" onClick={() => setSectorSel(s.clave)} aria-pressed={sel?.clave === s.clave}
                  className={cn("whitespace-nowrap rounded px-3 py-1.5 text-sm", sel?.clave === s.clave ? "bg-superficie font-semibold text-texto-fuerte shadow-card" : "text-texto-suave hover:text-texto-fuerte")}>
                  {s.rotulo}
                </button>
              ))}
            </div>
          )}
          <Button size="sm" variant="secondary" onClick={refrescar} disabled={tab.isFetching} aria-label="Actualizar camas">
            <Icon name="refresh" size={14} /> Actualizar
          </Button>
        </div>
      </header>

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4" aria-label={`Estado de las camas de ${rotuloFoco}`}>
        {[
          { label: "Ocupación", value: `${foco.ocupacion}%`, detail: `${foco.ocupadas} de ${foco.operativas} camas en servicio`, tone: tonoOcupacion(foco.ocupacion).texto },
          { label: "Libres", value: foco.libres, detail: "Listas para ingresar" },
          { label: "En higiene", value: foco.higiene, detail: "Pendientes de limpieza", tone: "text-badge-amber-fg" },
          { label: "Fuera de servicio", value: foco.bloqueadas, detail: "No cuentan como operativas" },
        ].map((k) => (
          <div key={k.label} className="rounded-lg border border-borde bg-superficie px-4 py-4">
            <p className="text-sm text-texto-suave">{k.label}</p>
            <p className={cn("mt-1 text-cifra font-bold leading-none tabular-nums", k.tone)}>{k.value}</p>
            <p className="mt-2 text-xs text-texto-tenue">{k.detail}</p>
          </div>
        ))}
      </section>

      {faltan > 0 && (
        <div className="flex items-start gap-2 rounded-md bg-badge-amber-bg px-3.5 py-3 text-md text-badge-amber-fg">
          <Icon name="alert" size={16} className="mt-0.5 flex-none" />
          <span>
            Se están mostrando {mostradas} de {enSectores} camas: faltan {faltan} fichas por
            dibujar. Los porcentajes son correctos —los calcula el servidor sobre todas las
            camas—, pero para ver las camas que faltan elegí un sector arriba.
          </span>
        </div>
      )}

      {sectores.length === 0 ? (
        <EstadoVacio
          titulo="No hay camas cargadas"
          detalle="Cargalas en Estructura organizativa → área de internación."
          icono="bed"
        />
      ) : (
        visibles.map((s) => {
          const camas = porSector.get(s.clave) || [];
          return (
            <Sector
              key={s.clave}
              sector={s}
              camas={camas}
              faltan={estable ? Math.max(0, s.total - camas.length) : 0}
              conflictos={tab.data?.conflictos || {}}
              onCambio={refrescar}
            />
          );
        })
      )}
    </div>
  );
}

function Sector({ sector, camas, faltan = 0, conflictos, onCambio }) {
  return (
    <section className="overflow-hidden rounded-lg border border-borde bg-superficie">
      <header className="flex flex-wrap items-center gap-lg px-xl pt-lg">
        <div className="min-w-40 flex-1">
          <h3 className="text-lg font-bold">{sector.rotulo}</h3>
          <p className="text-base text-texto-debil">
            {sector.libres} {sector.libres === 1 ? "cama libre" : "camas libres"}
            {sector.higiene > 0 && ` · ${sector.higiene} en higiene`}
            {sector.bloqueadas > 0 && ` · ${sector.bloqueadas} fuera de servicio`}
          </p>
        </div>
      </header>
      <div className="grid grid-cols-[repeat(auto-fill,minmax(13rem,1fr))] gap-2.5 p-xl">
        {camas.map((c) => <FichaCama key={c.id} cama={c} conflicto={conflictos[c.id]} onCambio={onCambio} />)}
      </div>
      {faltan > 0 && (
        <p className="border-t border-division px-xl py-3 text-base text-badge-amber-fg">
          Faltan {faltan} de las {sector.total} camas de este sector: elegilo en el selector de
          arriba para verlas todas.
        </p>
      )}
    </section>
  );
}

function FichaCama({ cama, conflicto, onCambio }) {
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
      conflicto?.length ? "border-danger bg-badge-error-bg" : cama.estado === "ocupada" ? "border-accent-100 bg-accent-50/40" : "border-borde",
    )}>
      <div className="flex items-center justify-between gap-2">
        <span className="flex items-center gap-2 font-mono text-md font-bold">
          <span className={cn("size-2.5 shrink-0 rounded-pill", est.punto)} aria-hidden="true" />
          {cama.nombre}
        </span>
        <span className={cn("rounded-pill px-2 py-px text-xs font-semibold", conflicto?.length ? "bg-danger-fuerte text-sobre-danger" : est.chip)}>{conflicto?.length ? "Conflicto" : est.label}</span>
      </div>

      {conflicto?.length > 0 && (
          <p className="text-sm text-badge-error-fg">El paciente también ocupa {conflicto.join(", ")}. Revisá la asignación.</p>
      )}

      {cama.estado === "ocupada" ? (
        <button
          onClick={() => navigate(`/casos/${cama.caso_id}`)}
          className="min-w-0 text-left"
        >
          <span className="block text-base font-semibold text-accent">
            {cama.paciente || casoId(cama.caso_id)}
          </span>
          <span className="block text-sm text-texto-tenue">internado hace {antiguedad(cama.desde)}</span>
        </button>
      ) : cama.estado === "higiene" ? (
        <div className="flex items-center justify-between gap-2">
          <span className="text-sm text-texto-tenue">esperando hace {antiguedad(cama.desde)}</span>
          <Button size="sm" variant="secondary" disabled={cambiar.isPending}
                  onClick={() => cambiar.mutate({ estado: "libre" })}>
            Marcar higienizada
          </Button>
        </div>
      ) : cama.estado === "bloqueada" ? (
        /* Desde cuándo, arriba, y el motivo en su propia línea.
           Cada cama fuera de servicio sale del denominador de la ocupación, así
           que una bloqueada hace cuatro meses por un arreglo que ya se hizo
           empuja el porcentaje del sector para arriba de forma permanente: seis
           olvidadas en un sector de veinte lo dejan al 95 % y se derivan
           pacientes por camas vacías y sanas. Sin fecha, nadie tiene motivo para
           mirarla. Y el motivo va en dos líneas y no truncado: «Pérdida de agua
           — …» no alcanza para decidir si la cama vuelve hoy o es obra hasta fin
           de mes, y el tooltip no existe con teclado ni en tablet. */
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between gap-2">
            <span className="text-sm text-texto-tenue">
              {cama.desde ? `fuera de servicio hace ${antiguedad(cama.desde)}` : "fuera de servicio"}
            </span>
            <Button size="sm" variant="secondary" disabled={cambiar.isPending}
                    onClick={() => cambiar.mutate({ estado: "libre" })}>
              Reactivar
            </Button>
          </div>
          <span className="line-clamp-2 text-sm text-texto-debil" title={cama.motivo}>
            {cama.motivo || "Sin motivo cargado"}
          </span>
        </div>
      ) : (
        /* Sacar una cama de servicio es raro; que ocupe lo mismo que la cama
           hacía que el tablero se leyera como una grilla de botones. Queda como
           acción secundaria, sin peso visual — pero NO con el triángulo de
           advertencia: aparece en toda cama disponible, así que la grilla se
           llenaba de alertas sobre las camas sanas y el sector con la mitad de
           las camas rotas era el que se veía más limpio. El blanco de toque es
           de 44 px porque esto se opera en tablet y con guantes. */
        <div className="flex items-center justify-between gap-2">
          <span className="text-sm text-texto-tenue">disponible</span>
          <button
            disabled={cambiar.isPending}
            title="Marcar fuera de servicio"
            aria-label={`Marcar la cama ${cama.nombre} fuera de servicio`}
            onClick={() => setBloqueando(true)}
            className="flex size-11 flex-none items-center justify-center rounded-md text-texto-tenue transition-colors hover:bg-division hover:text-texto-medio"
          >
            <Icon name="power" size={16} />
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
            required
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
