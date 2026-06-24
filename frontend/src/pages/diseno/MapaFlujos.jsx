import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../api/client";
import { useInstitucion } from "../../auth/InstitutionContext";
import { Badge, Spinner } from "../../components/ui";
import { Icon } from "../../components/icons";
import { color, estadoVersion } from "../../theme";

const CARD_W = 250;
const CARD_H = 96;
const GAP_X = 132;
const GAP_Y = 26;
const PAD = 16;

// Mapa panorámico: cada bloque es un flujo; las flechas son derivaciones
// (nodos «derivar» con flujo de destino) que encadenan un proceso con otro.
export default function MapaFlujos() {
  const { institucion } = useInstitucion();
  const navigate = useNavigate();
  const [data, setData] = useState(null); // { nodos, aristas }
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    if (!institucion) return;
    setCargando(true);
    api
      .get(`/flujos/mapa/?institucion=${institucion.id}`)
      .then(setData)
      .finally(() => setCargando(false));
  }, [institucion]);

  const layout = useMemo(() => calcularLayout(data), [data]);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div style={{ padding: "20px 30px 14px" }}>
        <div style={{ fontSize: 16, fontWeight: 700 }}>Cómo se encadenan los procesos</div>
        <div style={{ fontSize: 13, color: color.slate500, marginTop: 3, maxWidth: 640 }}>
          Cada bloque es un flujo; las flechas son derivaciones entre flujos. Hacé clic en un bloque para abrirlo en el diseñador.
        </div>
      </div>
      <div style={{ flex: 1, overflow: "auto", background: "#FBFBFD", backgroundImage: "radial-gradient(circle, #D9DDE5 1.1px, transparent 1.1px)", backgroundSize: "20px 20px", padding: 32 }}>
        {cargando ? (
          <Spinner />
        ) : !layout || layout.nodos.length === 0 ? (
          <div style={{ fontSize: 14, color: color.slate400 }}>No hay flujos en esta institución.</div>
        ) : (
          <div style={{ position: "relative", width: layout.width, height: layout.height, minWidth: "100%" }}>
            {/* Flechas de derivación */}
            <svg width={layout.width} height={layout.height} style={{ position: "absolute", inset: 0, overflow: "visible", pointerEvents: "none" }}>
              <defs>
                <marker id="flecha" markerWidth="10" markerHeight="10" refX="8" refY="4" orient="auto" markerUnits="userSpaceOnUse">
                  <path d="M0,0 L8,4 L0,8 Z" fill={color.slate400} />
                </marker>
              </defs>
              {layout.aristas.map((a, i) => (
                <path key={i} d={a.path} fill="none" stroke={color.slate400} strokeWidth={1.7} strokeDasharray={a.externo ? "5 4" : undefined} markerEnd="url(#flecha)" />
              ))}
            </svg>

            {/* Etiquetas de las flechas (HTML, por encima de las tarjetas) */}
            {layout.aristas.map((a, i) => a.etiqueta && (
              <div key={`l${i}`} style={{ position: "absolute", left: a.lx, top: a.ly, transform: "translate(-50%,-50%)", fontSize: 11, fontWeight: 600, color: color.slate500, background: "#FBFBFD", padding: "1px 6px", borderRadius: 6, whiteSpace: "nowrap", pointerEvents: "none" }}>
                {a.etiqueta}
              </div>
            ))}

            {/* Bloques de flujo */}
            {layout.nodos.map((n) => {
              const est = estadoVersion[n.estado] || { label: "Borrador", tone: "neutral" };
              const externo = n.externo;
              return (
                <div
                  key={n.id}
                  onClick={() => !externo && navigate(`/flujos/${n.id}`)}
                  style={{
                    position: "absolute", left: n.x, top: n.y, width: CARD_W, height: CARD_H,
                    background: externo ? "#F7F8FA" : "#fff",
                    border: `1px ${externo ? "dashed" : "solid"} ${color.border}`,
                    borderRadius: 14, padding: "14px 16px", cursor: externo ? "default" : "pointer",
                    boxShadow: externo ? "none" : "0 1px 3px rgba(16,24,40,.07)",
                    display: "flex", flexDirection: "column", justifyContent: "space-between", boxSizing: "border-box",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 9, minWidth: 0 }}>
                    <div style={{ width: 28, height: 28, borderRadius: 8, background: externo ? color.subtle : color.accent50, color: externo ? color.slate400 : color.accent, display: "flex", alignItems: "center", justifyContent: "center", flex: "none" }}>
                      <Icon name="workflow" size={15} />
                    </div>
                    <div style={{ fontSize: 14.5, fontWeight: 700, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", minWidth: 0 }} title={n.titulo}>{n.titulo}</div>
                  </div>
                  <div style={{ fontSize: 12, color: color.slate500, display: "flex", alignItems: "center", gap: 7 }}>
                    {externo ? (
                      "Flujo de otro alcance"
                    ) : (
                      <>
                        <Badge tone={est.tone}>{est.label}</Badge>
                        <Badge tone="info">{n.area_nombre}</Badge>
                      </>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
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

  // Profundidad por relajación (grafos chicos; tope de iteraciones = #nodos).
  const adj = new Map(items.map((n) => [n.id, []]));
  const indeg = new Map(items.map((n) => [n.id, 0]));
  edges.forEach((e) => {
    adj.get(e.from)?.push(e.to);
    indeg.set(e.to, (indeg.get(e.to) || 0) + 1);
  });
  const depth = new Map(items.map((n) => [n.id, 0]));
  for (let it = 0; it < items.length; it++) {
    let cambio = false;
    for (const e of edges) {
      const nd = depth.get(e.from) + 1;
      if (nd > depth.get(e.to)) { depth.set(e.to, nd); cambio = true; }
    }
    if (!cambio) break;
  }

  // Agrupar por columna y asignar fila.
  const columnas = new Map();
  for (const n of items) {
    const d = depth.get(n.id);
    if (!columnas.has(d)) columnas.set(d, []);
    columnas.get(d).push(n);
  }
  const pos = new Map();
  let maxFilas = 0;
  for (const [d, lista] of columnas) {
    maxFilas = Math.max(maxFilas, lista.length);
    lista.forEach((n, fila) => {
      pos.set(n.id, { x: PAD + d * (CARD_W + GAP_X), y: PAD + fila * (CARD_H + GAP_Y) });
    });
  }
  const maxDepth = Math.max(0, ...items.map((n) => depth.get(n.id)));
  const width = PAD * 2 + (maxDepth + 1) * CARD_W + maxDepth * GAP_X;
  const height = PAD * 2 + maxFilas * CARD_H + Math.max(0, maxFilas - 1) * GAP_Y;

  const nodosUbicados = items.map((n) => ({ ...n, ...pos.get(n.id) }));

  // Curvas: del borde derecho del origen al borde izquierdo del destino.
  const aristasUbicadas = edges.map((e) => {
    const o = pos.get(e.from), d = pos.get(e.to);
    const sx = o.x + CARD_W, sy = o.y + CARD_H / 2;
    const tx = d.x, ty = d.y + CARD_H / 2;
    const dx = Math.max(36, (tx - sx) / 2);
    return {
      ...e,
      path: `M ${sx} ${sy} C ${sx + dx} ${sy}, ${tx - dx} ${ty}, ${tx} ${ty}`,
      lx: (sx + tx) / 2,
      ly: (sy + ty) / 2 - 8,
    };
  });

  return { nodos: nodosUbicados, aristas: aristasUbicadas, width, height };
}
