import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import { useInstitucion } from "../../auth/InstitutionContext";
import { PageHeader } from "../../components/Shell";
import { Badge, Button, Card, EmptyState, Field, Modal, Mono, Select, Spinner } from "../../components/ui";
import { antiguedad } from "../../lib/format";
import { color, estadoCaso } from "../../theme";

const TABS = [
  { key: "mios", label: "Mis casos" },
  { key: "sin", label: "Sin asignar" },
];

export default function Bandejas() {
  const { user } = useAuth();
  const { institucion } = useInstitucion();
  const navigate = useNavigate();
  const [casos, setCasos] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [tab, setTab] = useState("mios");
  const [tomando, setTomando] = useState(null);
  const [nuevo, setNuevo] = useState(false);

  async function cargar() {
    if (!institucion) return;
    setCargando(true);
    try {
      const data = await api.get(`/casos/?institucion=${institucion.id}`);
      setCasos(data.results || data);
    } finally {
      setCargando(false);
    }
  }
  useEffect(() => {
    cargar(); // eslint-disable-next-line
  }, [institucion]);

  // "Sin asignar" muestra solo lo que el usuario puede tomar: pasos abiertos o
  // pasos cuyos grupos responsables integra (el backend resuelve `puede_tomar`).
  const filtrados = casos.filter((c) => {
    if (tab === "mios") return c.asignado_a === user?.id;
    if (tab === "sin") return !c.asignado_a && c.puede_tomar;
    return true;
  });

  async function tomar(e, caso) {
    e.stopPropagation();
    setTomando(caso.id);
    try {
      await api.post(`/casos/${caso.id}/tomar/`);
      await cargar();
      setTab("mios");
    } finally {
      setTomando(null);
    }
  }

  const cuenta = (k) =>
    casos.filter((c) => (k === "mios" ? c.asignado_a === user?.id : k === "sin" ? !c.asignado_a && c.puede_tomar : true)).length;

  return (
    <>
      <PageHeader
        title="Bandejas"
        subtitle="Casos en curso. Tomá uno sin asignar o continuá los tuyos."
        right={
          <div style={{ display: "flex", gap: 10 }}>
            <Button variant="secondary" onClick={cargar}>↻ Actualizar</Button>
            <Button onClick={() => setNuevo(true)}>+ Nuevo caso</Button>
          </div>
        }
      />

      <div style={{ padding: 32 }}>
        {/* Tabs */}
        <div style={{ display: "inline-flex", gap: 4, background: "#EFF1F4", padding: 4, borderRadius: 11, marginBottom: 20 }}>
          {TABS.map((t) => {
            const active = tab === t.key;
            return (
              <button
                key={t.key}
                onClick={() => setTab(t.key)}
                style={{
                  padding: "8px 16px",
                  borderRadius: 9,
                  fontSize: 13.5,
                  fontWeight: 600,
                  cursor: "pointer",
                  border: "none",
                  background: active ? "#fff" : "transparent",
                  color: active ? color.accent : color.slate500,
                  boxShadow: active ? "0 1px 2px rgba(16,24,40,.10)" : "none",
                }}
              >
                {t.label}
                <span style={{ marginLeft: 7, fontSize: 11.5, color: color.slate400 }}>{cuenta(t.key)}</span>
              </button>
            );
          })}
        </div>

        <Card style={{ overflow: "hidden" }}>
          {cargando ? (
            <Spinner />
          ) : filtrados.length === 0 ? (
            <EmptyState title="No hay casos en esta bandeja" hint="Probá otra pestaña o creá un caso desde la API/admin." />
          ) : (
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13.5 }}>
              <thead>
                <tr style={{ background: color.subtle, color: color.slate500, textAlign: "left" }}>
                  <Th>Caso</Th>
                  <Th>Paso actual</Th>
                  <Th>Estado</Th>
                  <Th>Área</Th>
                  <Th>Antigüedad</Th>
                  <Th />
                </tr>
              </thead>
              <tbody>
                {filtrados.map((c) => {
                  const est = estadoCaso[c.estado] || { label: c.estado_display, tone: "neutral" };
                  return (
                    <tr
                      key={c.id}
                      onClick={() => navigate(`/casos/${c.id}`)}
                      style={{ borderTop: `1px solid ${color.divider}`, cursor: "pointer" }}
                      onMouseEnter={(e) => (e.currentTarget.style.background = color.subtle)}
                      onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                    >
                      <Td>
                        <Mono style={{ fontWeight: 700 }}>#{String(c.id).padStart(4, "0")}</Mono>
                        <div style={{ fontSize: 12, color: color.slate500, marginTop: 2 }}>{c.flujo_titulo}</div>
                      </Td>
                      <Td style={{ color: color.slate600 }}>
                        {c.paso_actual || "—"}
                        {c.responsables?.length > 0 && (
                          <div style={{ fontSize: 11.5, color: color.slate400, marginTop: 2 }}>
                            👥 {c.responsables.map((g) => g.nombre).join(", ")}
                          </div>
                        )}
                      </Td>
                      <Td>
                        <Badge tone={est.tone}>{est.label}</Badge>
                      </Td>
                      <Td style={{ color: color.slate600 }}>{c.area_nombre || "—"}</Td>
                      <Td style={{ color: color.slate500 }}>{antiguedad(c.creado)}</Td>
                      <Td style={{ textAlign: "right" }}>
                        {c.asignado_a === user?.id ? (
                          <Button style={{ height: 34, padding: "0 15px" }} onClick={(e) => { e.stopPropagation(); navigate(`/casos/${c.id}`); }}>
                            Continuar
                          </Button>
                        ) : !c.asignado_a ? (
                          <Button variant="secondary" style={{ height: 34, padding: "0 15px" }} disabled={tomando === c.id} onClick={(e) => tomar(e, c)}>
                            {tomando === c.id ? "…" : "Tomar"}
                          </Button>
                        ) : null}
                      </Td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </Card>
      </div>

      {nuevo && <NuevoCasoModal institucionId={institucion?.id} onClose={() => setNuevo(false)} onCreated={(id) => navigate(`/casos/${id}`)} />}
    </>
  );
}

function NuevoCasoModal({ institucionId, onClose, onCreated }) {
  const [flujos, setFlujos] = useState([]);
  const [ciudadanos, setCiudadanos] = useState([]);
  const [form, setForm] = useState({ flujoId: "", ciudadano: "", prioridad: "normal" });
  const [creando, setCreando] = useState(false);
  const set = (k, v) => setForm((p) => ({ ...p, [k]: v }));

  useEffect(() => {
    (async () => {
      const f = await api.get(`/flujos/?institucion=${institucionId}`);
      // Solo flujos con una versión publicada.
      const lista = (f.results || f)
        .map((fl) => ({ ...fl, pub: (fl.versiones || []).find((v) => v.estado === "publicada") }))
        .filter((fl) => fl.pub);
      setFlujos(lista);
      if (lista[0]) set("flujoId", String(lista[0].id));
      const c = await api.get(`/ciudadanos/?institucion=${institucionId}`);
      setCiudadanos(c.results || c);
    })();
  }, [institucionId]);

  async function crear() {
    const flujo = flujos.find((f) => String(f.id) === String(form.flujoId));
    if (!flujo) return;
    setCreando(true);
    try {
      const caso = await api.post("/casos/", {
        institucion: flujo.institucion,
        version: flujo.pub.id,
        ciudadano: form.ciudadano || null,
        prioridad: form.prioridad,
      });
      await api.post(`/casos/${caso.id}/iniciar/`); // arranca el flujo
      onCreated(caso.id);
    } finally {
      setCreando(false);
    }
  }

  return (
    <Modal
      title="Nuevo caso"
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancelar</Button>
          <Button disabled={creando || !form.flujoId} onClick={crear}>{creando ? "Creando…" : "Crear e iniciar"}</Button>
        </>
      }
    >
      {flujos.length === 0 ? (
        <div style={{ fontSize: 13.5, color: color.slate500 }}>
          No hay flujos publicados. Publicá un flujo en el mundo Diseño primero.
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <Field label="Flujo *">
            <Select value={form.flujoId} onChange={(e) => set("flujoId", e.target.value)}>
              {flujos.map((f) => <option key={f.id} value={f.id}>{f.titulo} ({f.pub.etiqueta})</option>)}
            </Select>
          </Field>
          <Field label="Paciente">
            <Select value={form.ciudadano} onChange={(e) => set("ciudadano", e.target.value)}>
              <option value="">— Sin asociar —</option>
              {ciudadanos.map((c) => <option key={c.id} value={c.id}>{c.nombre} {c.apellido}</option>)}
            </Select>
          </Field>
          <Field label="Prioridad">
            <Select value={form.prioridad} onChange={(e) => set("prioridad", e.target.value)}>
              <option value="normal">Normal</option>
              <option value="alta">Alta</option>
              <option value="urgente">Urgente</option>
            </Select>
          </Field>
        </div>
      )}
    </Modal>
  );
}

function Th({ children }) {
  return <th style={{ padding: "12px 16px", fontWeight: 600, fontSize: 12.5, whiteSpace: "nowrap" }}>{children}</th>;
}
function Td({ children, style }) {
  return <td style={{ padding: "13px 16px", verticalAlign: "middle", ...style }}>{children}</td>;
}
