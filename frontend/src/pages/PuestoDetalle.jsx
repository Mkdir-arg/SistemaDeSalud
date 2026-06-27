import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import { PageHeader } from "../components/Shell";
import { Badge, Button, Card, EmptyState, Spinner } from "../components/ui";
import { antiguedad } from "../lib/format";
import { color, estadoCaso, nodeCat } from "../theme";

const PRIO = { urgente: { label: "Urgente", tone: "error" }, alta: { label: "Alta", tone: "amber" } };
const tonoEspera = (iso) => {
  const m = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 60000));
  return m >= 30 ? color.danger : m >= 15 ? "#A96A12" : color.slate500;
};

// Detalle de un paso (nodo): indicadores del momento + tabla de casos parados ahí.
export default function PuestoDetalle() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [d, setD] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(false);
  const [accion, setAccion] = useState(null); // id de caso en acción

  const cargar = useCallback(async () => {
    setCargando(true);
    try { setD(await api.get(`/puestos/${id}/`)); setError(false); }
    catch { setError(true); }
    finally { setCargando(false); }
  }, [id]);
  useEffect(() => { cargar(); }, [cargar]);

  if (cargando && !d) return <Spinner label="Cargando el paso…" />;
  if (error) {
    return (
      <div style={{ padding: 48, textAlign: "center" }}>
        <div style={{ fontSize: 15, fontWeight: 700, color: color.slate700 }}>No pudimos cargar este paso</div>
        <div style={{ fontSize: 13, color: color.slate400, margin: "6px 0 16px" }}>Puede que no seas responsable de él.</div>
        <Button onClick={() => navigate("/inicio")}>Volver a Mi trabajo</Button>
      </div>
    );
  }

  const { nodo, indicadores: ind, casos } = d;
  const cat = nodeCat[nodo.tipo] || nodeCat.form;

  async function tomarYAbrir(c) {
    setAccion(c.id);
    try {
      if (!c.mio) await api.post(`/casos/${c.id}/tomar/`);
      navigate(`/casos/${c.id}`);
    } finally { setAccion(null); }
  }
  async function llamar(c) {
    if (!d.mi_box) return;
    setAccion(c.id);
    try {
      await api.post(`/casos/${c.id}/llamar/`, { box_id: d.mi_box });
      navigate(`/casos/${c.id}`);
    } finally { setAccion(null); }
  }
  const tiles = [
    { label: nodo.con_fila ? "En cola" : "Ahora", n: ind.ahora },
    { label: "Urgentes", n: ind.urgentes, alerta: ind.urgentes > 0 },
    { label: "Resueltos hoy", n: ind.hoy },
  ];

  return (
    <>
      <PageHeader
        subtitle={[nodo.flujo_titulo, nodo.area_nombre].filter(Boolean).join(" · ")}
        right={<Button variant="secondary" onClick={cargar}>↻ Actualizar</Button>}
      />

      <div style={{ padding: "22px 32px", display: "flex", flexDirection: "column", gap: 22 }}>
        {/* Encabezado del paso */}
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span style={{ width: 38, height: 38, borderRadius: 10, background: cat.tint, border: `1px solid ${cat.bd}`, display: "flex", alignItems: "center", justifyContent: "center", flex: "none" }}>
            <span style={{ width: 13, height: 13, borderRadius: 4, background: cat.sol }} />
          </span>
          <div>
            <div style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: ".6px", color: color.slate400 }}>{cat.name.toUpperCase()}</div>
            <div style={{ fontSize: 20, fontWeight: 800, letterSpacing: "-.3px" }}>{nodo.titulo}</div>
          </div>
        </div>

        {/* Indicadores */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 12 }}>
          {tiles.map((t) => (
            <Card key={t.label} style={{ padding: "14px 16px", borderLeft: `3px solid ${t.alerta ? color.danger : color.border}` }}>
              <div style={{ fontSize: 26, fontWeight: 800, lineHeight: 1, color: t.alerta ? color.danger : color.ink }}>{t.n}</div>
              <div style={{ fontSize: 12, color: color.slate500, marginTop: 6 }}>{t.label}</div>
            </Card>
          ))}
          <Card style={{ padding: "14px 16px" }}>
            <div style={{ fontSize: 18, fontWeight: 800, lineHeight: 1.2, color: ind.desde ? color.ink : color.slate400 }}>
              {ind.desde ? `hace ${antiguedad(ind.desde)}` : "—"}
            </div>
            <div style={{ fontSize: 12, color: color.slate500, marginTop: 6 }}>El más antiguo</div>
          </Card>
        </div>

        {/* Tabla de casos en este paso */}
        <Card style={{ overflow: "hidden" }}>
          <div style={{ padding: "13px 16px", borderBottom: `1px solid ${color.divider}`, fontSize: 13, fontWeight: 700 }}>
            Casos en este paso <span style={{ color: color.slate400, fontWeight: 500 }}>({casos.length})</span>
          </div>
          {casos.length === 0 ? (
            <EmptyState title="No hay casos en este paso" hint="Cuando lleguen, los vas a ver acá." />
          ) : (
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13.5 }}>
              <thead>
                <tr style={{ background: color.subtle, color: color.slate500, textAlign: "left" }}>
                  <Th>Paciente</Th><Th>Prioridad</Th><Th>Estado</Th><Th>Espera</Th><Th>Asignado</Th><Th />
                </tr>
              </thead>
              <tbody>
                {casos.map((c) => {
                  const est = estadoCaso[c.estado] || { label: c.estado_display, tone: "neutral" };
                  const p = PRIO[c.prioridad];
                  return (
                    <tr key={c.id} onClick={() => navigate(`/casos/${c.id}`)}
                      style={{ borderTop: `1px solid ${color.divider}`, cursor: "pointer" }}
                      onMouseEnter={(e) => (e.currentTarget.style.background = color.subtle)}
                      onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}>
                      <Td style={{ fontWeight: 600 }}>{c.ciudadano_nombre || "—"}</Td>
                      <Td>{p ? <Badge tone={p.tone}>{p.label}</Badge> : <span style={{ color: color.slate400 }}>Normal</span>}</Td>
                      <Td>{c.esperando ? <Badge tone="amber">Esperando</Badge> : <Badge tone={est.tone}>{est.label}</Badge>}</Td>
                      <Td style={{ color: tonoEspera(c.creado), fontWeight: 600 }}>{antiguedad(c.creado)}</Td>
                      <Td style={{ color: color.slate600 }}>{c.asignado_nombre || <span style={{ color: color.slate400 }}>—</span>}</Td>
                      <Td style={{ textAlign: "right", whiteSpace: "nowrap" }} onClick={(e) => e.stopPropagation()}>
                        <AccionCaso c={c} nodo={nodo} miBox={d.mi_box} cargando={accion === c.id}
                          onAbrir={() => navigate(`/casos/${c.id}`)} onTomar={() => tomarYAbrir(c)} onLlamar={() => llamar(c)} />
                      </Td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </Card>
      </div>
    </>
  );
}

// Acción por caso según su estado y el tipo de paso.
function AccionCaso({ c, nodo, miBox, cargando, onAbrir, onTomar, onLlamar }) {
  const btn = { height: 32, padding: "0 14px" };
  if (c.mio) return <Button style={btn} onClick={onAbrir}>Continuar</Button>;
  if (nodo.con_fila && c.en_fila) {
    return miBox
      ? <Button style={btn} disabled={cargando} onClick={onLlamar}>{cargando ? "…" : "Llamar"}</Button>
      : <Button variant="secondary" style={btn} disabled title="Ocupá tu box en «Mi trabajo»">Ocupá un box</Button>;
  }
  if (!c.asignado) {
    return <Button variant="secondary" style={btn} disabled={cargando} onClick={onTomar}>{cargando ? "…" : "Tomar y abrir"}</Button>;
  }
  return <Button variant="secondary" style={btn} onClick={onAbrir}>Abrir</Button>;
}

function Th({ children }) {
  return <th style={{ padding: "11px 16px", fontWeight: 600, fontSize: 12.5, whiteSpace: "nowrap" }}>{children}</th>;
}
function Td({ children, style }) {
  return <td style={{ padding: "12px 16px", verticalAlign: "middle", ...style }}>{children}</td>;
}
