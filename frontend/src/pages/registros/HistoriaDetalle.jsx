import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../../api/client";
import { Avatar, Badge, Button, Card, EmptyState, Field, Input, Modal, Mono, Spinner, Textarea } from "../../components/ui";
import { Icon } from "../../components/icons";
import { fechaHora } from "../../lib/format";
import { color } from "../../theme";

export default function HistoriaDetalle() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [ciudadano, setCiudadano] = useState(null);
  const [hc, setHc] = useState(undefined); // undefined=cargando, null=sin HC
  const [tab, setTab] = useState("evolucion");
  const [nuevaAtencion, setNuevaAtencion] = useState(false);

  async function cargarHc() {
    const d = await api.get(`/historias-clinicas/?ciudadano=${id}`);
    setHc((d.results || d)[0] || null);
  }
  useEffect(() => {
    (async () => {
      const c = await api.get(`/ciudadanos/${id}/`);
      setCiudadano(c);
      await cargarHc();
    })(); // eslint-disable-next-line
  }, [id]);

  if (!ciudadano) return <Spinner label="Cargando historia…" />;

  const nombre = `${ciudadano.nombre} ${ciudadano.apellido}`.trim();
  const metricas = [
    { n: hc?.entradas?.length || 0, l: "consultas" },
    { n: hc?.estudios?.length || 0, l: "estudios" },
    { n: (hc?.recetas || []).filter((r) => r.activa).length, l: "recetas activas" },
    { n: hc?.entradas?.length ? new Date(hc.entradas[0].fecha).toLocaleDateString("es-AR", { day: "2-digit", month: "2-digit" }) : "—", l: "última visita" },
  ];
  const tabs = [
    { k: "evolucion", l: "Evolución" },
    { k: "estudios", l: "Estudios" },
    { k: "recetas", l: "Recetas" },
  ];

  return (
    <div style={{ padding: "22px 30px" }}>
      {/* Breadcrumb */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
        <button onClick={() => navigate("/historia")} style={{ width: 30, height: 30, borderRadius: 8, border: `1px solid ${color.border}`, background: "#fff", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", color: color.slate500 }}>
          <Icon name="back" size={15} />
        </button>
        <div style={{ fontSize: 13.5, color: color.slate500 }}>Historias clínicas · <strong style={{ color: color.slate700 }}>{nombre}</strong></div>
      </div>

      {/* Header paciente */}
      <Card style={{ padding: "20px 24px", marginBottom: 18, display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
        <Avatar nombre={nombre} i={ciudadano.id} size={52} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 20, fontWeight: 800, letterSpacing: "-.3px" }}>{nombre}</div>
          <div style={{ fontSize: 13, color: color.slate500 }}>
            {ciudadano.documento ? `DNI ${ciudadano.documento}` : ""}{ciudadano.fecha_nacimiento ? ` · ${new Date(ciudadano.fecha_nacimiento).toLocaleDateString("es-AR")}` : ""}{ciudadano.obra_social ? ` · ${ciudadano.obra_social}` : ""}
          </div>
          {ciudadano.codigo && (
            <div style={{ marginTop: 8, display: "inline-flex", alignItems: "center", gap: 6, fontSize: 11.5, fontWeight: 600, padding: "3px 9px", borderRadius: 6, background: "#E2F6F9", color: "#0C7C8E" }}>
              <Icon name="enter" size={12} /> Identidad del Legajo ciudadano (externo) · <Mono>{ciudadano.codigo}</Mono>
            </div>
          )}
        </div>
        <Button onClick={() => setNuevaAtencion(true)} style={{ display: "flex", alignItems: "center", gap: 8 }}><Icon name="plus" size={15} /> Nueva atención</Button>
      </Card>

      {hc === undefined ? (
        <Spinner />
      ) : (
        <>
          {/* Métricas */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 14, marginBottom: 22 }}>
            {metricas.map((m) => (
              <Card key={m.l} style={{ padding: 18 }}>
                <div style={{ fontSize: 26, fontWeight: 800, lineHeight: 1 }}>{m.n}</div>
                <div style={{ fontSize: 12.5, color: color.slate400, marginTop: 6 }}>{m.l}</div>
              </Card>
            ))}
          </div>

          {/* Tabs */}
          <div style={{ display: "flex", borderBottom: `1px solid ${color.border}`, marginBottom: 20 }}>
            {tabs.map((t) => (
              <button key={t.k} onClick={() => setTab(t.k)} style={{ padding: "11px 2px", marginRight: 26, fontSize: 13.5, fontWeight: 600, border: "none", borderBottom: `2px solid ${tab === t.k ? color.accent : "transparent"}`, color: tab === t.k ? color.accent : color.slate400, background: "none", cursor: "pointer" }}>{t.l}</button>
            ))}
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 280px", gap: 20, alignItems: "start" }}>
            <div>
              {tab === "evolucion" && <Evolucion entradas={hc?.entradas || []} />}
              {tab === "estudios" && <Estudios estudios={hc?.estudios || []} />}
              {tab === "recetas" && <Recetas recetas={hc?.recetas || []} />}
            </div>
            {/* Antecedentes */}
            <Card style={{ padding: 18 }}>
              <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: ".6px", color: color.slate400, marginBottom: 12 }}>ANTECEDENTES</div>
              <Dato k="Alergias" v={<span style={{ color: hc?.alergias ? "#B42318" : color.slate500 }}>{hc?.alergias || "—"}</span>} />
              <div style={{ height: 10 }} />
              <Dato k="Condiciones" v={hc?.condiciones || "—"} />
            </Card>
          </div>
        </>
      )}

      {nuevaAtencion && (
        <NuevaAtencionModal
          ciudadanoId={id}
          hcId={hc?.id}
          onClose={() => setNuevaAtencion(false)}
          onSaved={() => { setNuevaAtencion(false); cargarHc(); }}
        />
      )}
    </div>
  );
}

function NuevaAtencionModal({ ciudadanoId, hcId, onClose, onSaved }) {
  const [titulo, setTitulo] = useState("");
  const [contenido, setContenido] = useState("");
  const [firmada, setFirmada] = useState(true);
  const [guardando, setGuardando] = useState(false);
  async function guardar() {
    setGuardando(true);
    try {
      let historia = hcId;
      if (!historia) {
        const hc = await api.post("/historias-clinicas/", { ciudadano: ciudadanoId });
        historia = hc.id;
      }
      await api.post("/entradas-historia/", { historia, titulo, contenido, firmada });
      onSaved();
    } finally {
      setGuardando(false);
    }
  }
  return (
    <Modal title="Nueva atención" onClose={onClose} footer={<>
      <Button variant="secondary" onClick={onClose}>Cancelar</Button>
      <Button disabled={guardando || !titulo} onClick={guardar}>{guardando ? "Registrando…" : "Registrar atención"}</Button>
    </>}>
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <Field label="Título *"><Input value={titulo} onChange={(e) => setTitulo(e.target.value)} autoFocus placeholder="Evaluación inicial, Control…" /></Field>
        <Field label="Evolución / observaciones"><Textarea value={contenido} onChange={(e) => setContenido(e.target.value)} /></Field>
        <label style={{ display: "flex", alignItems: "center", gap: 9, fontSize: 13.5, color: color.slate600, cursor: "pointer" }}>
          <input type="checkbox" checked={firmada} onChange={(e) => setFirmada(e.target.checked)} /> Firmar la entrada
        </label>
      </div>
    </Modal>
  );
}

function Dato({ k, v }) {
  return (
    <div>
      <div style={{ fontSize: 12, color: color.slate400, marginBottom: 2 }}>{k}</div>
      <div style={{ fontSize: 14, fontWeight: 600, color: color.slate900 }}>{v}</div>
    </div>
  );
}

function Evolucion({ entradas }) {
  if (!entradas.length) return <EmptyState title="Sin entradas de evolución" />;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {entradas.map((e) => (
        <Card key={e.id} style={{ padding: 18 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
            <div style={{ fontSize: 14.5, fontWeight: 700 }}>{e.titulo}</div>
            {e.firmada && <Badge tone="green">Firmada</Badge>}
          </div>
          {e.contenido && <div style={{ fontSize: 13.5, color: color.slate700, marginBottom: 8 }}>{e.contenido}</div>}
          <div style={{ fontSize: 11.5, color: color.slate400 }}>{fechaHora(e.fecha)}</div>
        </Card>
      ))}
    </div>
  );
}

function Estudios({ estudios }) {
  if (!estudios.length) return <EmptyState title="Sin estudios" />;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {estudios.map((s) => (
        <Card key={s.id} style={{ padding: "14px 18px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div>
            <div style={{ fontSize: 14, fontWeight: 600 }}>{s.tipo}</div>
            <div style={{ fontSize: 12.5, color: color.slate500 }}>{s.fecha} · {s.autor || "—"} {s.archivo && <Mono style={{ marginLeft: 6 }}>{s.archivo}</Mono>}</div>
          </div>
          {s.resultado && <Badge tone={s.resultado === "normal" ? "green" : "amber"}>{s.resultado_display}</Badge>}
        </Card>
      ))}
    </div>
  );
}

function Recetas({ recetas }) {
  if (!recetas.length) return <EmptyState title="Sin recetas" />;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {recetas.map((r) => (
        <Card key={r.id} style={{ padding: "14px 18px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div>
            <div style={{ fontSize: 13.5, color: color.slate700 }}>{r.detalle}</div>
            <div style={{ fontSize: 12, color: color.slate400 }}>{r.fecha}</div>
          </div>
          <Badge tone={r.activa ? "green" : "gray"}>{r.activa ? "Activa" : "Inactiva"}</Badge>
        </Card>
      ))}
    </div>
  );
}
