import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useInstitucion } from "../auth/InstitutionContext";
import { PageHeader } from "../components/Shell";
import { Badge, Button, Card, EmptyState, Spinner } from "../components/ui";
import { Icon } from "../components/icons";
import { antiguedad } from "../lib/format";
import { color, estadoCaso, estadoVersion, font, nodeCat } from "../theme";

// Tablero general del hospital (super admin / configuración): números, tiempos por
// área y gráficos. Lee /instituciones/:id/tablero/. Gráficos en SVG/CSS, sin libs.

const REFRESCO_MS = 60000;

const RANGOS = [
  { dias: 7, label: "7 días" },
  { dias: 30, label: "30 días" },
  { dias: 90, label: "90 días" },
];
const isoHoy = () => new Date().toISOString().slice(0, 10);
const isoHace = (dias) => { const x = new Date(); x.setDate(x.getDate() - (dias - 1)); return x.toISOString().slice(0, 10); };

// Color por estado para la dona y la leyenda.
const ESTADO_COLOR = {
  recibido: "#667085",
  en_evaluacion: "#2D3A9E",
  en_espera: "#A96A12",
  derivado: "#0E8893",
  atendido: "#1B7A4E",
  cerrado: "#98A0AE",
};

// Umbrales (min) para colorear la espera promedio. Color + número (no solo color).
function tonoEspera(min) {
  if (min >= 30) return color.danger;
  if (min >= 15) return "#A96A12";
  return "#1B7A4E";
}

export default function Dashboard() {
  const { institucion } = useInstitucion();
  const navigate = useNavigate();
  const [d, setD] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(false);
  const [refrescando, setRefrescando] = useState(false);
  const [desde, setDesde] = useState(isoHace(30));
  const [hasta, setHasta] = useState(isoHoy());
  const [tab, setTab] = useState("general"); // "general" o el id de un área

  const cargar = useCallback(async (silent = false) => {
    if (!institucion) return;
    silent ? setRefrescando(true) : setCargando(true);
    try {
      setD(await api.get(`/instituciones/${institucion.id}/tablero/?desde=${desde}&hasta=${hasta}`));
      setError(false);
    } catch {
      if (!silent) setError(true);
    } finally {
      silent ? setRefrescando(false) : setCargando(false);
    }
  }, [institucion, desde, hasta]);

  useEffect(() => { cargar(); }, [cargar]);
  useEffect(() => {
    const id = setInterval(() => { if (!document.hidden) cargar(true); }, REFRESCO_MS);
    return () => clearInterval(id);
  }, [cargar]);

  if (cargando && !d) return <Spinner label="Cargando tablero…" />;
  if (error && !d) {
    return (
      <div style={{ padding: 48, textAlign: "center" }}>
        <div style={{ fontSize: 15, fontWeight: 700, color: color.slate700 }}>No pudimos cargar el tablero</div>
        <div style={{ fontSize: 13, color: color.slate400, margin: "6px 0 16px" }}>Revisá la conexión y reintentá.</div>
        <Button onClick={() => cargar()}>Reintentar</Button>
      </div>
    );
  }

  return (
    <>
      <PageHeader
        subtitle="Estado general del hospital: carga, tiempos por área y evolución de ingresos."
        right={
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <span style={{ fontSize: 12, color: color.slate400 }}>{refrescando ? "Actualizando…" : "Se actualiza solo cada 60 s"}</span>
            <Button variant="secondary" onClick={() => cargar()}>↻ Actualizar</Button>
          </div>
        }
      />

      <div style={{ padding: "22px 32px", display: "flex", flexDirection: "column", gap: 22 }}>
        <RangoFechas desde={desde} hasta={hasta} setDesde={setDesde} setHasta={setHasta} />
        <Tabs areas={d.por_area} tab={tab} setTab={setTab} />

        {tab === "general"
          ? <TableroGeneral d={d} navigate={navigate} />
          : <AreaTablero key={tab} areaId={tab} desde={desde} hasta={hasta} navigate={navigate} />}
      </div>
    </>
  );
}

// Solapas: General + una por cada área (dinámicas, salen de las áreas existentes).
function Tabs({ areas, tab, setTab }) {
  const items = [{ id: "general", nombre: "General" }, ...(areas || []).map((a) => ({ id: String(a.area_id), nombre: a.nombre }))];
  return (
    <div style={{ display: "flex", gap: 2, flexWrap: "wrap", borderBottom: `1px solid ${color.border}` }}>
      {items.map((it) => {
        const activo = String(tab) === it.id;
        return (
          <button key={it.id} onClick={() => setTab(it.id)}
            style={{ padding: "10px 15px", border: "none", background: "none", cursor: "pointer", fontFamily: font.display,
              fontSize: 13.5, fontWeight: activo ? 700 : 600, color: activo ? color.accent : color.slate500,
              borderBottom: `2px solid ${activo ? color.accent : "transparent"}`, marginBottom: -1, transition: "color .12s" }}>
            {it.nombre}
          </button>
        );
      })}
    </div>
  );
}

// Grilla de KPIs (compartida por la vista general y la de área).
function KpiGrid({ kpis }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", gap: 14 }}>
      {kpis.map((k) => (
        <Card key={k.l} style={{ padding: 18, display: "flex", flexDirection: "column", gap: 12 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span style={{ fontSize: 12.5, color: color.slate500, fontWeight: 600 }}>{k.l}</span>
            <span style={{ width: 30, height: 30, borderRadius: 8, background: k.c + "1A", color: k.c, display: "flex", alignItems: "center", justifyContent: "center", flex: "none" }}>
              <Icon name={k.icon} size={16} />
            </span>
          </div>
          <div style={{ fontFamily: font.display, fontSize: 30, fontWeight: 800, letterSpacing: "-.5px", lineHeight: 1, color: k.c }}>
            {k.v}{k.u && <span style={{ fontSize: 14, fontWeight: 700, color: color.slate400, marginLeft: 4 }}>{k.u}</span>}
          </div>
        </Card>
      ))}
    </div>
  );
}

// ── Solapa GENERAL: el tablero del hospital (contenido original, intacto) ──
function TableroGeneral({ d, navigate }) {
  const r = d.resumen;
  const kpis = [
    { l: "Casos activos", v: r.casos_activos, icon: "fileText", c: color.accent },
    { l: "En cola ahora", v: r.en_cola, icon: "list", c: "#16B1C9" },
    { l: "Urgentes", v: r.urgentes, icon: "activity", c: r.urgentes > 0 ? color.danger : color.slate400 },
    { l: "Ingresos", v: r.ingresos, icon: "enter", c: "#0E8893" },
    { l: "Cerrados", v: r.cerrados, icon: "clipboard", c: "#1B7A4E" },
    { l: "Espera prom.", v: r.espera_prom_min, u: "min", icon: "refresh", c: tonoEspera(r.espera_prom_min) },
    { l: "Atención prom.", v: r.atencion_prom_min ?? 0, u: "min", icon: "users", c: "#D14B8F" },
    { l: "Resolución prom.", v: r.resolucion_prom_h, u: "h", icon: "map", c: color.slate600 },
  ];
  return (
    <>
      <KpiGrid kpis={kpis} />

      <div style={{ display: "grid", gridTemplateColumns: "1.6fr 1fr", gap: 16, alignItems: "stretch" }}>
        <Card style={{ padding: 20, minWidth: 0 }}>
          <ChartHead titulo="Ingresos de casos" sub={d.periodo?.agrupacion === "semana" ? "por semana" : "por día"} />
          <LineaIngresos serie={d.serie_ingresos} />
        </Card>
        <Card style={{ padding: 20, minWidth: 0 }}>
          <ChartHead titulo="Distribución por estado" sub="casos no cancelados" />
          <DonutEstados data={d.por_estado} />
        </Card>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1.5fr 1fr", gap: 16, alignItems: "start" }}>
        <Card style={{ padding: 20, minWidth: 0 }}>
          <Comparativa areas={d.por_area} />
        </Card>
        <Card style={{ padding: 0, overflow: "hidden", minWidth: 0 }}>
          <div style={{ padding: "18px 20px 4px" }}>
            <ChartHead titulo="Top de demoras" sub="quién espera más ahora" />
          </div>
          <TopDemoras items={d.top_demoras} onAbrir={(id) => navigate(`/casos/${id}`)} />
        </Card>
      </div>

      <Card style={{ padding: 0, overflow: "hidden" }}>
        <div style={{ padding: "18px 20px 14px" }}>
          <ChartHead titulo="Carga y tiempos por área" sub="ordenado por casos activos" />
        </div>
        <TablaAreas areas={d.por_area} />
      </Card>
    </>
  );
}

// ── Solapa de ÁREA: detalle de un área, basado en su flujo ──
function AreaTablero({ areaId, desde, hasta, navigate }) {
  const { institucion } = useInstitucion();
  const [a, setA] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let activo = true;
    setCargando(true);
    api.get(`/areas/${areaId}/tablero/?desde=${desde}&hasta=${hasta}`)
      .then((res) => { if (activo) { setA(res); setError(false); } })
      .catch(() => { if (activo) setError(true); })
      .finally(() => { if (activo) setCargando(false); });
    return () => { activo = false; };
  }, [areaId, desde, hasta, institucion]);

  if (cargando && !a) return <Spinner label="Cargando área…" />;
  if (error && !a) return <EmptyState title="No se pudo cargar el área" hint="Reintentá en unos segundos." />;
  if (!a) return null;

  const r = a.resumen;
  const kpis = [
    { l: "Casos activos", v: r.activos, icon: "fileText", c: color.accent },
    { l: "En cola ahora", v: r.en_cola, icon: "list", c: "#16B1C9" },
    { l: "Atendidos", v: r.atendidos, icon: "clipboard", c: "#1B7A4E" },
    { l: "Ingresos", v: r.ingresos, icon: "enter", c: "#0E8893" },
    { l: "Espera prom.", v: r.espera_prom_min, u: "min", icon: "refresh", c: tonoEspera(r.espera_prom_min) },
    { l: "Atención prom.", v: r.atencion_prom_min ?? 0, u: "min", icon: "users", c: "#D14B8F" },
    { l: "Resolución prom.", v: r.resolucion_prom_h, u: "h", icon: "map", c: color.slate600 },
  ];
  return (
    <>
      <KpiGrid kpis={kpis} />

      {a.flujos?.length > 0 ? (
        <Card style={{ padding: 20, minWidth: 0 }}>
          <MapaFlujo key={a.area?.id} flujos={a.flujos} />
        </Card>
      ) : (
        <Card style={{ padding: 0 }}>
          <EmptyState
            title="Esta área todavía no tiene un flujo"
            hint="Asigná un flujo a esta área (Flujos → abrir el flujo → área) para ver su mapa y la carga por paso."
          />
        </Card>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "1.6fr 1fr", gap: 16, alignItems: "stretch" }}>
        <Card style={{ padding: 20, minWidth: 0 }}>
          <ChartHead titulo="Ingresos del área" sub={a.periodo?.agrupacion === "semana" ? "por semana" : "por día"} />
          <LineaIngresos serie={a.serie_ingresos} />
        </Card>
        <Card style={{ padding: 20, minWidth: 0 }}>
          <ChartHead titulo="Distribución por estado" sub="casos del área" />
          <DonutEstados data={a.por_estado} />
        </Card>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1.5fr 1fr", gap: 16, alignItems: "start" }}>
        <Card style={{ padding: 20, minWidth: 0 }}>
          <ChartHead titulo="Casos por paso del flujo" sub="dónde están los casos ahora" />
          <PorPaso pasos={a.por_paso} />
        </Card>
        <Card style={{ padding: 0, overflow: "hidden", minWidth: 0 }}>
          <div style={{ padding: "18px 20px 4px" }}>
            <ChartHead titulo="Top de demoras" sub="del área, en vivo" />
          </div>
          <TopDemoras items={a.top_demoras} onAbrir={(id) => navigate(`/casos/${id}`)} />
        </Card>
      </div>

      <Card style={{ padding: 0, overflow: "hidden" }}>
        <div style={{ padding: "18px 20px 14px" }}>
          <ChartHead titulo="Casos activos del área" sub="urgentes primero · clic para abrir" />
        </div>
        <CasosArea casos={a.casos} onAbrir={(id) => navigate(`/casos/${id}`)} />
      </Card>
    </>
  );
}

// Lista de casos activos del área.
const PRIORIDAD_TONO = { urgente: "error", alta: "amber" };
function CasosArea({ casos, onAbrir }) {
  if (!casos?.length) return <EmptyState title="Sin casos activos" hint="No hay casos en curso en esta área ahora mismo." />;
  const cols = "minmax(150px, 1.5fr) 130px 96px minmax(130px, 1.3fr) minmax(120px, 1fr) 90px";
  return (
    <div style={{ overflowX: "auto" }}>
      <div style={{ minWidth: 780 }}>
        <div style={{ display: "grid", gridTemplateColumns: cols, gap: 12, padding: "10px 20px", background: color.subtle, borderTop: `1px solid ${color.divider}`, fontSize: 11, fontWeight: 700, letterSpacing: ".5px", color: color.slate400 }}>
          <div>PACIENTE</div><div>ESTADO</div><div>PRIORIDAD</div><div>PASO</div><div>ASIGNADO</div><div>ESPERA</div>
        </div>
        {casos.map((c) => {
          const est = estadoCaso[c.estado] || { label: c.estado, tone: "neutral" };
          return (
            <div key={c.id} onClick={() => onAbrir(c.id)}
              style={{ display: "grid", gridTemplateColumns: cols, gap: 12, alignItems: "center", padding: "12px 20px", cursor: "pointer", borderTop: `1px solid ${color.divider}` }}
              onMouseEnter={(e) => (e.currentTarget.style.background = color.subtle)}
              onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}>
              <div style={{ fontSize: 13.5, fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{c.paciente || "Sin paciente"}</div>
              <div><Badge tone={est.tone}>{est.label}</Badge></div>
              <div>{PRIORIDAD_TONO[c.prioridad] ? <Badge tone={PRIORIDAD_TONO[c.prioridad]}>{c.prioridad}</Badge> : <span style={{ fontSize: 12.5, color: color.slate400 }}>normal</span>}</div>
              <div style={{ fontSize: 13, color: color.slate600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{c.paso || "—"}</div>
              <div style={{ fontSize: 13, color: c.asignado ? color.slate600 : color.slate400, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{c.asignado || "—"}</div>
              <div style={{ fontSize: 12.5, color: color.slate500, whiteSpace: "nowrap" }}>{antiguedad(c.creado)}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Mapa del flujo del área ──
// Con varios flujos: primero un índice (mapa de flujos del área); al tocar uno,
// entra a su mini-mapa con "volver". Con uno solo, muestra el mapa directo.
function MapaFlujo({ flujos }) {
  const [sel, setSel] = useState(flujos.length === 1 ? 0 : null);

  // Índice de flujos del área.
  if (sel === null) {
    return (
      <>
        <ChartHead titulo="Flujos del área" sub={`${flujos.length} flujos · tocá uno para ver su mapa`} />
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(244px, 1fr))", gap: 12 }}>
          {flujos.map((f, i) => {
            const casos = (f.nodos || []).reduce((s, n) => s + (n.casos || 0), 0);
            const est = estadoVersion[f.estado] || { label: "Borrador", tone: "neutral" };
            return (
              <div key={f.flujo_id} onClick={() => setSel(i)}
                style={{ border: `1px solid ${color.border}`, borderRadius: 12, padding: 16, cursor: "pointer", background: "#fff", transition: "border-color .12s, box-shadow .12s", display: "flex", flexDirection: "column", gap: 12 }}
                onMouseEnter={(e) => { e.currentTarget.style.borderColor = color.accent100; e.currentTarget.style.boxShadow = "0 6px 18px rgba(16,24,40,.08)"; }}
                onMouseLeave={(e) => { e.currentTarget.style.borderColor = color.border; e.currentTarget.style.boxShadow = "none"; }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
                  <span style={{ width: 32, height: 32, borderRadius: 9, background: color.accent50, color: color.accent, display: "flex", alignItems: "center", justifyContent: "center", flex: "none" }}>
                    <Icon name="workflow" size={16} />
                  </span>
                  <span style={{ fontSize: 14.5, fontWeight: 700, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", minWidth: 0 }} title={f.titulo}>{f.titulo}</span>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 7, flexWrap: "wrap" }}>
                  <Badge tone={f.relacion === "deriva" ? "amber" : "info"}>{f.relacion === "deriva" ? "Deriva aquí" : "Propio"}</Badge>
                  <Badge tone={est.tone}>{est.label}</Badge>
                  <span style={{ fontSize: 11.5, color: color.slate400 }}>v{f.version} · {(f.nodos || []).length} pasos</span>
                </div>
                <div style={{ fontSize: 12.5, color: casos > 0 ? color.slate600 : color.slate400 }}>
                  {casos > 0 ? `${casos} caso${casos === 1 ? "" : "s"} en curso` : "Sin casos en curso"}
                </div>
              </div>
            );
          })}
        </div>
      </>
    );
  }

  // Mapa de un flujo concreto.
  const flujo = flujos[sel];
  return (
    <>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 14, flexWrap: "wrap" }}>
        {flujos.length > 1 && (
          <button onClick={() => setSel(null)}
            style={{ display: "flex", alignItems: "center", gap: 6, height: 30, padding: "0 11px", borderRadius: 8, border: `1px solid ${color.border}`, background: "#fff", cursor: "pointer", fontSize: 12.5, fontWeight: 600, color: color.slate600 }}>
            <Icon name="back" size={14} /> Flujos
          </button>
        )}
        <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}>
          <span style={{ fontFamily: font.display, fontSize: 15, fontWeight: 700, letterSpacing: "-.2px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{flujo.titulo}</span>
          <Badge tone={flujo.relacion === "deriva" ? "amber" : "info"}>{flujo.relacion === "deriva" ? "Deriva aquí" : "Propio"}</Badge>
          <span style={{ fontSize: 12, color: color.slate400, whiteSpace: "nowrap" }}>
            v{flujo.version} · {flujo.relacion === "deriva" ? "el paso resaltado deriva a esta área" : "casos parados en cada paso"}
          </span>
        </div>
      </div>
      <MiniMapaFlujo flujo={flujo} />
    </>
  );
}

function MiniMapaFlujo({ flujo }) {
  const nodos = flujo.nodos || [];
  const conexiones = flujo.conexiones || [];
  if (!nodos.length) return <div style={{ padding: "24px 0", textAlign: "center", fontSize: 13, color: color.slate400 }}>El flujo no tiene nodos para dibujar.</div>;

  const W = 168, H = 60, pad = 36; // tamaño de nodo (coords del diseñador) + margen
  const xs = nodos.map((n) => n.x), ys = nodos.map((n) => n.y);
  const minX = Math.min(...xs), minY = Math.min(...ys);
  const maxX = Math.max(...xs) + W, maxY = Math.max(...ys) + H;
  const vbW = maxX - minX + 2 * pad, vbH = maxY - minY + 2 * pad;
  const tx = (x) => x - minX + pad;
  const ty = (y) => y - minY + pad;
  const cx = (n) => tx(n.x) + W / 2;
  const cy = (n) => ty(n.y) + H / 2;
  const byId = Object.fromEntries(nodos.map((n) => [n.id, n]));
  const corta = (s, n = 22) => (s && s.length > n ? s.slice(0, n - 1) + "…" : s || "");

  return (
    <div style={{ overflow: "auto", maxHeight: 540, border: `1px solid ${color.divider}`, borderRadius: 12, background: color.subtle }}>
      <svg viewBox={`0 0 ${vbW} ${vbH}`} width="100%" height="auto" style={{ display: "block", minWidth: Math.min(vbW, 520) }} role="img" aria-label={`Mapa del flujo ${flujo.titulo}`}>
        <defs>
          <marker id="flecha" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M0 0 L10 5 L0 10 z" fill="#B6BDC9" />
          </marker>
        </defs>
        {/* Conexiones */}
        {conexiones.map((c, i) => {
          const o = byId[c.origen], dn = byId[c.destino];
          if (!o || !dn) return null;
          return <line key={i} x1={cx(o)} y1={cy(o)} x2={cx(dn)} y2={cy(dn)} stroke="#C7CDD6" strokeWidth="1.6" markerEnd="url(#flecha)" />;
        })}
        {/* Nodos */}
        {nodos.map((n) => {
          const cat = nodeCat[n.tipo] || nodeCat.estado;
          const activo = n.casos > 0;
          const destino = n.destino;
          return (
            <g key={n.id} transform={`translate(${tx(n.x)} ${ty(n.y)})`}>
              {destino && <rect x={-5} y={-5} width={W + 10} height={H + 10} rx="15" fill="none" stroke={color.accent} strokeWidth="1.6" strokeDasharray="5 4" opacity=".7" />}
              <rect width={W} height={H} rx="12" fill={activo ? cat.tint : "#fff"} stroke={destino ? color.accent : cat.sol} strokeWidth={destino ? 2.6 : activo ? 2 : 1.3} />
              <rect width="5" height={H} rx="2.5" fill={cat.sol} />
              <text x="16" y="24" fontSize="13" fontWeight="700" fontFamily={font.sans} fill={color.ink}>{corta(n.titulo)}</text>
              <text x="16" y="42" fontSize="11.5" fontFamily={font.sans} fill={cat.sol}>{cat.name}</text>
              {activo && (
                <g transform={`translate(${W - 18} 18)`}>
                  <circle r="14" fill={color.accent} />
                  <text textAnchor="middle" y="4.5" fontSize="13" fontWeight="800" fontFamily={font.display} fill="#fff">{n.casos}</text>
                </g>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}

// Distribución de casos activos por paso del flujo (barras).
const TIPO_PASO = {
  inicio: "Inicio", formulario: "Formulario", decision: "Decisión", atencion: "Atención",
  espera_fila: "Espera de fila", espera_tiempo: "Espera por tiempo", derivar: "Derivar", estado: "Estado", fin: "Fin",
};
function PorPaso({ pasos }) {
  if (!pasos?.length) return <div style={{ padding: "24px 0", textAlign: "center", fontSize: 13, color: color.slate400 }}>No hay casos activos en el flujo de esta área.</div>;
  const max = Math.max(1, ...pasos.map((p) => p.casos));
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {pasos.map((p) => (
        <div key={p.nodo_id} style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ width: 150, flex: "none", minWidth: 0 }}>
            <div style={{ fontSize: 12.5, fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={p.titulo}>{p.titulo}</div>
            <div style={{ fontSize: 11, color: color.slate400 }}>{TIPO_PASO[p.tipo] || p.tipo}{p.en_cola ? ` · ${p.en_cola} en cola` : ""}</div>
          </div>
          <div style={{ flex: 1, height: 18, borderRadius: 5, background: color.divider, overflow: "hidden", minWidth: 30 }}>
            <div style={{ width: `${(p.casos / max) * 100}%`, height: "100%", borderRadius: 5, background: color.accent }} />
          </div>
          <span style={{ width: 30, flex: "none", textAlign: "right", fontSize: 13, fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>{p.casos}</span>
        </div>
      ))}
    </div>
  );
}

// Selector de rango: presets (7/30/90 días) + fechas personalizadas.
function RangoFechas({ desde, hasta, setDesde, setHasta }) {
  const hoy = isoHoy();
  const dateInput = {
    height: 36, border: `1px solid ${color.inputBorder}`, borderRadius: 9, padding: "0 10px",
    fontSize: 13, fontFamily: font.sans, color: color.ink, background: "#fff", outline: "none",
  };
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
      <div style={{ display: "flex", gap: 2, background: "#F2F3F6", border: `1px solid ${color.border}`, borderRadius: 9, padding: 3 }}>
        {RANGOS.map((rg) => {
          const activo = desde === isoHace(rg.dias) && hasta === hoy;
          return (
            <button key={rg.dias} onClick={() => { setDesde(isoHace(rg.dias)); setHasta(hoy); }}
              style={{ padding: "6px 13px", borderRadius: 7, fontSize: 12.5, fontWeight: 600, border: "none", cursor: "pointer", background: activo ? "#fff" : "transparent", color: activo ? color.accent : color.slate500, boxShadow: activo ? "0 1px 2px rgba(16,24,40,.12)" : "none" }}>
              {rg.label}
            </button>
          );
        })}
      </div>
      <span style={{ fontSize: 12.5, color: color.slate400 }}>o</span>
      <input type="date" value={desde} max={hasta} onChange={(e) => e.target.value && setDesde(e.target.value)} style={dateInput} aria-label="Desde" />
      <span style={{ color: color.slate400 }}>→</span>
      <input type="date" value={hasta} min={desde} max={hoy} onChange={(e) => e.target.value && setHasta(e.target.value)} style={dateInput} aria-label="Hasta" />
    </div>
  );
}

function ChartHead({ titulo, sub }) {
  return (
    <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 14 }}>
      <span style={{ fontFamily: font.display, fontSize: 15, fontWeight: 700, letterSpacing: "-.2px" }}>{titulo}</span>
      {sub && <span style={{ fontSize: 12, color: color.slate400 }}>{sub}</span>}
    </div>
  );
}

// ── Comparativa por área: barras horizontales con métrica seleccionable ──
const METRICAS = [
  { k: "activos", label: "Activos", get: (a) => a.activos, unit: "" },
  { k: "espera", label: "Espera", get: (a) => a.espera_prom_min, unit: "min", severidad: true },
  { k: "atencion", label: "Atención", get: (a) => a.atencion_prom_min, unit: "min" },
  { k: "resolucion", label: "Resolución", get: (a) => a.resolucion_prom_h, unit: "h" },
];

function Comparativa({ areas }) {
  const [m, setM] = useState("activos");
  const met = METRICAS.find((x) => x.k === m);
  const datos = (areas || []).map((a) => ({ nombre: a.nombre, v: met.get(a) || 0 })).sort((x, y) => y.v - x.v);
  const max = Math.max(1, ...datos.map((dd) => dd.v));

  return (
    <>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, marginBottom: 16, flexWrap: "wrap" }}>
        <span style={{ fontFamily: font.display, fontSize: 15, fontWeight: 700, letterSpacing: "-.2px" }}>Comparativa por área</span>
        <div style={{ display: "flex", gap: 2, background: "#F2F3F6", border: `1px solid ${color.border}`, borderRadius: 8, padding: 3 }}>
          {METRICAS.map((x) => (
            <button key={x.k} onClick={() => setM(x.k)}
              style={{ padding: "5px 10px", borderRadius: 6, fontSize: 12, fontWeight: 600, border: "none", cursor: "pointer", background: m === x.k ? "#fff" : "transparent", color: m === x.k ? color.accent : color.slate500, boxShadow: m === x.k ? "0 1px 2px rgba(16,24,40,.12)" : "none" }}>
              {x.label}
            </button>
          ))}
        </div>
      </div>
      {datos.length === 0 ? (
        <div style={{ padding: "20px 0", textAlign: "center", fontSize: 13, color: color.slate400 }}>Sin áreas con datos.</div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {datos.map((dd) => {
            const c = met.severidad ? tonoEspera(dd.v) : color.accent;
            return (
              <div key={dd.nombre} style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <span style={{ width: 120, flex: "none", fontSize: 12.5, color: color.slate600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={dd.nombre}>{dd.nombre}</span>
                <div style={{ flex: 1, height: 18, borderRadius: 5, background: color.divider, overflow: "hidden", minWidth: 30 }}>
                  <div style={{ width: `${(dd.v / max) * 100}%`, height: "100%", borderRadius: 5, background: c, transition: "width .25s" }} />
                </div>
                <span style={{ width: 58, flex: "none", textAlign: "right", fontSize: 12.5, fontWeight: 700, fontVariantNumeric: "tabular-nums", color: met.severidad ? c : color.slate700 }}>
                  {dd.v}{met.unit && <span style={{ fontWeight: 500, color: color.slate400 }}> {met.unit}</span>}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </>
  );
}

// ── Top de demoras: casos esperando más en cola ahora (en vivo) ──
function TopDemoras({ items, onAbrir }) {
  if (!items?.length) {
    return <EmptyState title="Sin demoras" hint="No hay nadie esperando en cola ahora mismo." />;
  }
  return (
    <div>
      {items.map((it, i) => (
        <div key={`${it.caso_id}-${i}`} onClick={() => onAbrir(it.caso_id)}
          style={{ display: "flex", alignItems: "center", gap: 11, padding: "11px 20px", cursor: "pointer", borderTop: `1px solid ${color.divider}` }}
          onMouseEnter={(e) => (e.currentTarget.style.background = color.subtle)}
          onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}>
          <span style={{ width: 22, height: 22, borderRadius: "50%", flex: "none", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 700, background: i === 0 ? "#FCEBEB" : "#EEF0F3", color: i === 0 ? color.danger : color.slate500 }}>{i + 1}</span>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 13, fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", display: "flex", alignItems: "center", gap: 7 }}>
              {it.paciente || "Sin paciente"}
              {it.urgente && <Badge tone="error">urgente</Badge>}
            </div>
            <div style={{ fontSize: 11.5, color: color.slate400, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {[it.area, it.nodo].filter(Boolean).join(" · ") || "—"}
            </div>
          </div>
          <span style={{ flex: "none", fontSize: 13, fontWeight: 700, fontVariantNumeric: "tabular-nums", color: tonoEspera(it.espera_min) }}>
            {it.espera_min} <span style={{ fontWeight: 500, color: color.slate400 }}>min</span>
          </span>
        </div>
      ))}
    </div>
  );
}

// ── Línea/área de ingresos (SVG, escala con el ancho) ──
function LineaIngresos({ serie }) {
  const W = 1000, H = 230, padX = 20, padT = 16, padB = 30;
  const n = serie.length;
  const max = Math.max(1, ...serie.map((s) => s.casos));
  const x = (i) => padX + (i * (W - 2 * padX)) / Math.max(1, n - 1);
  const y = (v) => padT + (1 - v / max) * (H - padT - padB);
  const pts = serie.map((s, i) => [x(i), y(s.casos)]);
  const linea = pts.map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(" ");
  const area = `${linea} L${x(n - 1).toFixed(1)},${H - padB} L${padX},${H - padB} Z`;
  const ticks = [3, 2, 1, 0].map((g) => padT + (g / 3) * (H - padT - padB)); // 4 líneas guía
  const etiqueta = (f) => `${f.slice(8, 10)}/${f.slice(5, 7)}`;
  const idxLabels = [0, Math.floor((n - 1) / 2), n - 1];

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" height="auto" style={{ display: "block" }} role="img" aria-label="Ingresos de casos por día, últimos 14 días">
      <defs>
        <linearGradient id="grad-ing" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color.accent} stopOpacity="0.20" />
          <stop offset="100%" stopColor={color.accent} stopOpacity="0" />
        </linearGradient>
      </defs>
      {ticks.map((ty, i) => (
        <line key={i} x1={padX} y1={ty} x2={W - padX} y2={ty} stroke={color.divider} strokeWidth="1" />
      ))}
      <path d={area} fill="url(#grad-ing)" />
      <path d={linea} fill="none" stroke={color.accent} strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
      {pts.map((p, i) => (
        <circle key={i} cx={p[0]} cy={p[1]} r={i === n - 1 ? 4.5 : 2.5} fill={i === n - 1 ? color.accent : "#fff"} stroke={color.accent} strokeWidth="1.6" />
      ))}
      {idxLabels.map((i) => (
        <text key={i} x={x(i)} y={H - 8} textAnchor={i === 0 ? "start" : i === n - 1 ? "end" : "middle"} fontSize="13" fill={color.slate400} fontFamily={font.sans}>
          {etiqueta(serie[i].fecha)}
        </text>
      ))}
    </svg>
  );
}

// ── Dona de estados (SVG) ──
function DonutEstados({ data }) {
  const entries = Object.entries(data || {}).filter(([, n]) => n > 0)
    .sort((a, b) => b[1] - a[1]);
  const total = entries.reduce((s, [, n]) => s + n, 0);
  if (!total) return <div style={{ padding: "30px 0", textAlign: "center", fontSize: 13, color: color.slate400 }}>Sin casos para mostrar.</div>;

  const r = 56, sw = 18, C = 2 * Math.PI * r;
  let acc = 0;
  const segs = entries.map(([estado, n]) => {
    const frac = n / total;
    const seg = { estado, n, dash: frac * C, offset: -acc * C, c: ESTADO_COLOR[estado] || color.slate400 };
    acc += frac;
    return seg;
  });

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 18, flexWrap: "wrap" }}>
      <svg width="150" height="150" viewBox="0 0 150 150" role="img" aria-label="Distribución de casos por estado">
        <g transform="rotate(-90 75 75)">
          <circle cx="75" cy="75" r={r} fill="none" stroke={color.divider} strokeWidth={sw} />
          {segs.map((s) => (
            <circle key={s.estado} cx="75" cy="75" r={r} fill="none" stroke={s.c} strokeWidth={sw}
              strokeDasharray={`${s.dash} ${C - s.dash}`} strokeDashoffset={s.offset} />
          ))}
        </g>
        <text x="75" y="71" textAnchor="middle" fontSize="26" fontWeight="800" fontFamily={font.display} fill={color.ink}>{total}</text>
        <text x="75" y="90" textAnchor="middle" fontSize="11" fill={color.slate400} fontFamily={font.sans}>casos</text>
      </svg>
      <div style={{ display: "flex", flexDirection: "column", gap: 8, flex: 1, minWidth: 130 }}>
        {segs.map((s) => (
          <div key={s.estado} style={{ display: "flex", alignItems: "center", gap: 9, fontSize: 12.5 }}>
            <span style={{ width: 10, height: 10, borderRadius: 3, background: s.c, flex: "none" }} />
            <span style={{ color: color.slate600, flex: 1 }}>{estadoCaso[s.estado]?.label || s.estado}</span>
            <span style={{ fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>{s.n}</span>
            <span style={{ color: color.slate400, fontVariantNumeric: "tabular-nums", width: 38, textAlign: "right" }}>{Math.round((s.n / total) * 100)}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Tabla de tiempos por área (con barra inline de activos) ──
function TablaAreas({ areas }) {
  if (!areas?.length) return <EmptyState title="Sin áreas con datos" hint="Cuando haya casos en las áreas, vas a ver su carga y tiempos acá." />;
  const maxAct = Math.max(1, ...areas.map((a) => a.activos));
  const cols = "minmax(150px, 1.5fr) 1.3fr 70px 105px 105px 110px";

  return (
    <div style={{ overflowX: "auto" }}>
      <div style={{ minWidth: 740 }}>
        <div style={{ display: "grid", gridTemplateColumns: cols, gap: 12, padding: "10px 20px", background: color.subtle, borderTop: `1px solid ${color.divider}`, fontSize: 11, fontWeight: 700, letterSpacing: ".5px", color: color.slate400 }}>
          <div>ÁREA</div><div>CASOS ACTIVOS</div><div>EN COLA</div><div>ESPERA PROM.</div><div>ATENCIÓN</div><div>RESOLUCIÓN</div>
        </div>
        {areas.map((a) => (
          <div key={a.area_id} style={{ display: "grid", gridTemplateColumns: cols, gap: 12, alignItems: "center", padding: "13px 20px", borderTop: `1px solid ${color.divider}` }}>
            <div style={{ fontSize: 13.5, fontWeight: 600, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{a.nombre}</div>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <div style={{ flex: 1, height: 8, borderRadius: 4, background: color.divider, overflow: "hidden", minWidth: 40 }}>
                <div style={{ width: `${(a.activos / maxAct) * 100}%`, height: "100%", borderRadius: 4, background: color.accent }} />
              </div>
              <span style={{ fontSize: 13, fontWeight: 700, fontVariantNumeric: "tabular-nums", width: 26, textAlign: "right" }}>{a.activos}</span>
            </div>
            <div style={{ fontSize: 13, fontVariantNumeric: "tabular-nums", color: a.en_cola > 0 ? color.slate700 : color.slate400 }}>{a.en_cola}</div>
            <div style={{ fontSize: 13, fontWeight: 700, fontVariantNumeric: "tabular-nums", color: tonoEspera(a.espera_prom_min) }}>
              {a.espera_prom_min} <span style={{ fontWeight: 500, color: color.slate400 }}>min</span>
            </div>
            <div style={{ fontSize: 13, fontVariantNumeric: "tabular-nums", color: color.slate600 }}>
              {a.atencion_prom_min ? <>{a.atencion_prom_min} <span style={{ color: color.slate400 }}>min</span></> : <span style={{ color: color.slate400 }}>—</span>}
            </div>
            <div style={{ fontSize: 13, fontVariantNumeric: "tabular-nums", color: color.slate600 }}>
              {a.resolucion_prom_h ? <>{a.resolucion_prom_h} <span style={{ color: color.slate400 }}>h</span></> : <span style={{ color: color.slate400 }}>—</span>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
