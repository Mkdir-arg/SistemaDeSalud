import { useMemo } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/api/client";
import { useInstitucion } from "@/auth/InstitutionContext";
import { Icon } from "@/components/icons";
import { Badge, Spinner } from "@/components/ui";
import { EstadoError, EstadoVacio } from "@/components/ui/estados";
import { estadoVersion } from "@/lib/dominio";

const CARD_W = 250;
const CARD_H = 96;
const GAP_X = 132;
const GAP_Y = 26;
const PAD = 16;

// Mapa panorámico: cada bloque es un flujo; las flechas son derivaciones
// (nodos «derivar» con flujo de destino) que encadenan un proceso con otro.
export default function MapaFlujos() {
  const { institucion } = useInstitucion();

  const q = useQuery({
    queryKey: ["mapa-flujos", institucion?.id],
    queryFn: () => api.get(`/flujos/mapa/?institucion=${institucion.id}`),
    enabled: institucion?.id != null,
  });

  const layout = useMemo(() => calcularLayout(q.data), [q.data]);

  return (
    <div className="flex h-full flex-col">
      <div className="px-lg pb-3.5 pt-5 sm:px-[30px]">
        <h2 className="text-lg font-bold">Cómo se encadenan los procesos</h2>
        <div className="mt-0.5 max-w-2xl text-base text-texto-debil">
          Cada bloque es un flujo; las flechas son derivaciones entre flujos. Hacé
          clic en un bloque para abrirlo en el diseñador.
        </div>
      </div>

      {/* La cuadrícula de puntos usa el token de borde, así que en tema oscuro se
          atenúa sola en vez de quedar un enrejado claro sobre fondo negro. */}
      <div
        className="flex-1 overflow-auto bg-fondo p-8"
        style={{
          backgroundImage: "radial-gradient(circle, var(--color-borde) 1.1px, transparent 1.1px)",
          backgroundSize: "20px 20px",
        }}
      >
        {q.error ? (
          <EstadoError error={q.error} onReintentar={q.refetch} />
        ) : q.isLoading ? (
          <Spinner />
        ) : !layout || layout.nodos.length === 0 ? (
          <EstadoVacio
            titulo="No hay flujos en esta institución"
            detalle="Creá un flujo desde Flujos y volvé acá para ver cómo se encadena con el resto."
            icono="workflow"
          />
        ) : (
          <div className="relative min-w-full" style={{ width: layout.width, height: layout.height }}>
            {/* Flechas de derivación */}
            <svg
              width={layout.width}
              height={layout.height}
              role="img"
              aria-label={`Mapa de ${layout.nodos.filter((n) => !n.externo).length} flujos y ${layout.aristas.length} derivaciones`}
              className="pointer-events-none absolute inset-0 overflow-visible text-texto-tenue"
            >
              <title>Mapa de derivaciones entre flujos</title>
              {/* `currentColor` en vez de un gris fijo: así la flecha y su punta
                  toman el color del token y siguen al tema con una sola fuente. */}
              <defs>
                <marker id="flecha" markerWidth="10" markerHeight="10" refX="8" refY="4" orient="auto" markerUnits="userSpaceOnUse">
                  <path d="M0,0 L8,4 L0,8 Z" fill="currentColor" />
                </marker>
              </defs>
              {layout.aristas.map((a, i) => (
                <path key={i} d={a.path} fill="none" stroke="currentColor" strokeWidth={1.7} strokeDasharray={a.externo ? "5 4" : undefined} markerEnd="url(#flecha)" />
              ))}
            </svg>

            {/* Etiquetas de las flechas (HTML, por encima de las tarjetas) */}
            {layout.aristas.map((a, i) => a.etiqueta && (
              <div
                key={`l${i}`}
                className="pointer-events-none absolute max-w-44 -translate-x-1/2 -translate-y-1/2 rounded-sm bg-fondo px-1.5 py-px text-center text-xs font-semibold text-texto-debil"
                style={{ left: a.lx, top: a.ly }}
              >
                {a.etiqueta}
              </div>
            ))}

            {/* Bloques de flujo */}
            {layout.nodos.map((n) => {
              const est = estadoVersion[n.estado] || estadoVersion.borrador;
              const externo = n.externo;
              const Bloque = externo ? "div" : Link;
              return (
                <Bloque
                  key={n.id}
                  to={externo ? undefined : `/flujos/${n.id}`}
                  aria-label={externo ? undefined : `Abrir flujo ${n.titulo}`}
                  className={
                    "absolute box-border flex flex-col justify-between rounded-lg border border-borde px-lg py-3.5 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent " +
                    (externo
                      ? "cursor-default border-dashed bg-superficie-2"
                      : "cursor-pointer bg-superficie shadow-card hover:border-accent-100")
                  }
                  style={{ left: n.x, top: n.y, width: CARD_W, height: CARD_H }}
                >
                  <div className="flex min-w-0 items-center gap-2.5">
                    <span
                      className={
                        "flex size-8 flex-none items-center justify-center rounded-md " +
                        (externo ? "bg-superficie text-texto-tenue" : "bg-accent-50 text-accent")
                      }
                    >
                      <Icon name="workflow" size={16} />
                    </span>
                    <div className="min-w-0 truncate text-md font-semibold" title={n.titulo}>{n.titulo}</div>
                  </div>
                  <div className="flex items-center gap-1.5 text-sm text-texto-debil">
                    {externo ? (
                      "Flujo de otro alcance"
                    ) : (
                      <>
                        <Badge tone={est.tone}>{est.label}</Badge>
                        <Badge tone="info">{n.area_nombre}</Badge>
                      </>
                    )}
                  </div>
                </Bloque>
              );
            })}
          </div>
        )}
      </div>
      {layout?.aristas.length > 0 && (
        <details className="border-t border-division bg-superficie px-lg py-4 sm:px-[30px]">
          <summary className="cursor-pointer font-semibold text-accent">Ver conexiones como lista ({layout.aristas.length})</summary>
          <ul className="mt-3 max-h-64 list-disc space-y-2 overflow-y-auto pl-5 text-sm">
            {layout.aristas.map((a, i) => {
              const origen = layout.nodos.find((n) => n.id === a.from);
              const destino = layout.nodos.find((n) => n.id === a.to);
              return <li key={i}>
                <Link to={`/flujos/${a.from}`} className="font-semibold text-accent underline">{origen?.titulo || `Flujo ${a.from}`}</Link>
                {` → ${a.etiqueta || "Derivación"} → `}
                {a.externo ? <span>{destino?.titulo || "Flujo de otro alcance"}</span> : <Link to={`/flujos/${a.to}`} className="font-semibold text-accent underline">{destino?.titulo || `Flujo ${a.to}`}</Link>}
              </li>;
            })}
          </ul>
        </details>
      )}
    </div>
  );
}

// Ubica los flujos en columnas por "profundidad" (cuántas derivaciones los
// preceden) y calcula las curvas de las flechas entre bloques.
function calcularLayout(data) {
  if (!data) return null;
  const { nodos = [], aristas = [] } = data;

  // Nodos fantasma para destinos externos (flujos fuera del conjunto visible).
  const ids = new Set(nodos.map((n) => n.id));
  const externos = [];
  const externoId = new Map();
  for (const a of aristas) {
    if (a.externo && !externoId.has(a.destino)) {
      const gid = `ext-${a.destino}`;
      externoId.set(a.destino, gid);
      externos.push({ id: gid, titulo: "Otro flujo", externo: true });
    }
  }
  const items = [...nodos, ...externos];
  const idDe = (origDestino, externo) => (externo ? externoId.get(origDestino) : origDestino);

  // Aristas normalizadas a ids de layout.
  const edges = aristas
    .map((a) => ({ ...a, from: a.origen, to: idDe(a.destino, a.externo) }))
    .filter((a) => ids.has(a.from) && (ids.has(a.to) || String(a.to).startsWith("ext-")));

  /*
   * Profundidad por NIVELES desde las raíces (recorrido en anchura).
   *
   * No por «camino más largo»: las derivaciones entre flujos pueden ciclar
   * —Guardia deriva a Cardiología y Cardiología devuelve a Guardia— y ahí la
   * relajación no converge: sigue sumando una vuelta por pasada hasta el tope
   * de iteraciones. El mismo bug estiraba el diagrama del editor a cuatro mil
   * píxeles. Por niveles, cada flujo se fija la primera vez que se lo alcanza.
   */
  const adj = new Map(items.map((n) => [n.id, []]));
  const indeg = new Map(items.map((n) => [n.id, 0]));
  edges.forEach((e) => {
    adj.get(e.from)?.push(e.to);
    indeg.set(e.to, (indeg.get(e.to) || 0) + 1);
  });
  const depth = new Map();
  // Raíces: los que nadie deriva. Si TODO cicla no hay ninguna, y ahí se arranca
  // por el primero para no dejar el mapa vacío.
  let frontera = items.filter((n) => !indeg.get(n.id)).map((n) => n.id);
  if (!frontera.length && items.length) frontera = [items[0].id];
  frontera.forEach((id) => depth.set(id, 0));
  let nivel = 0;
  while (frontera.length) {
    nivel += 1;
    const siguiente = [];
    for (const id of frontera) {
      for (const d of adj.get(id) || []) {
        if (depth.has(d)) continue;
        depth.set(d, nivel);
        siguiente.push(d);
      }
    }
    frontera = siguiente;
  }
  items.forEach((n) => { if (!depth.has(n.id)) depth.set(n.id, nivel); });

  // Agrupar por columna y asignar fila.
  const columnas = new Map();
  for (const n of items) {
    const d = depth.get(n.id);
    if (!columnas.has(d)) columnas.set(d, []);
    columnas.get(d).push(n);
  }
  const desvios = edges.filter((e) => depth.get(e.to) !== depth.get(e.from) + 1).length;
  const margenSuperior = desvios ? desvios * 30 + 24 : 0;
  const margenLateral = desvios ? 40 : PAD;
  const pos = new Map();
  let maxFilas = 0;
  for (const [d, lista] of columnas) {
    maxFilas = Math.max(maxFilas, lista.length);
    lista.forEach((n, fila) => {
      pos.set(n.id, { x: margenLateral + d * (CARD_W + GAP_X), y: PAD + margenSuperior + fila * (CARD_H + GAP_Y) });
    });
  }
  const maxDepth = Math.max(0, ...items.map((n) => depth.get(n.id)));
  const width = margenLateral * 2 + (maxDepth + 1) * CARD_W + maxDepth * GAP_X;
  const height = PAD * 2 + margenSuperior + maxFilas * CARD_H + Math.max(0, maxFilas - 1) * GAP_Y;

  const nodosUbicados = items.map((n) => ({ ...n, ...pos.get(n.id) }));

  // Curvas: del borde derecho del origen al borde izquierdo del destino.
  let carrilSuperior = 0;
  const aristasUbicadas = edges.map((e) => {
    const o = pos.get(e.from), d = pos.get(e.to);
    const sx = o.x + CARD_W, sy = o.y + CARD_H / 2;
    const tx = d.x, ty = d.y + CARD_H / 2;
    const adyacente = depth.get(e.to) === depth.get(e.from) + 1;
    const corredor = (sx + tx) / 2;
    const superior = PAD + carrilSuperior * 30 + 8;
    if (!adyacente) carrilSuperior += 1;
    return {
      ...e,
      // Entre columnas vecinas se usa el hueco; retornos y saltos largos
      // pasan por un carril sobre todas las tarjetas.
      path: adyacente
        ? `M ${sx} ${sy} H ${corredor} V ${ty} H ${tx}`
        : `M ${sx} ${sy} H ${sx + 24} V ${superior} H ${tx - 24} V ${ty} H ${tx}`,
      lx: adyacente ? corredor : (sx + tx) / 2,
      ly: adyacente ? (sy + ty) / 2 - 12 : superior,
    };
  });

  return { nodos: nodosUbicados, aristas: aristasUbicadas, width, height };
}
