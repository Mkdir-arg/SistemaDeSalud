import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../api/client";
import { useInstitucion } from "../../auth/InstitutionContext";
import { Avatar, Badge, Card, Field, Input, Modal, Mono, Select, Spinner } from "../../components/ui";
import { fechaHora } from "../../lib/format";
import { color } from "../../theme";

// Dashboard del legajo profesional (captura 14).
export default function Legajo() {
  const { institucion } = useInstitucion();
  const navigate = useNavigate();
  const [staff, setStaff] = useState([]);
  const [sel, setSel] = useState("");
  const [legajo, setLegajo] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [editar, setEditar] = useState(false);

  useEffect(() => {
    if (!institucion) return;
    (async () => {
      const [membs, usuarios, areas] = await Promise.all([
        api.get(`/membresias/?institucion=${institucion.id}`),
        api.get("/usuarios/"),
        api.get(`/areas/?institucion=${institucion.id}`),
      ]);
      const usuMap = Object.fromEntries((usuarios.results || usuarios).map((u) => [u.id, u]));
      const areaMap = Object.fromEntries((areas.results || areas).map((a) => [a.id, a.nombre]));
      const por = {};
      for (const m of membs.results || membs) {
        const u = usuMap[m.usuario];
        if (!u) continue;
        if (!por[m.usuario]) por[m.usuario] = { id: u.id, nombre: u.nombre_completo || u.email, areas: new Set() };
        (m.areas || []).forEach((aid) => areaMap[aid] && por[m.usuario].areas.add(areaMap[aid]));
      }
      const lista = Object.values(por).map((x) => ({ ...x, areas: [...x.areas] }));
      setStaff(lista);
      if (lista[0]) setSel(String(lista[0].id));
      setCargando(false);
    })();
  }, [institucion]);

  useEffect(() => {
    if (!sel) return;
    setLegajo(null);
    api.get(`/usuarios/${sel}/legajo/`).then(setLegajo);
  }, [sel]);

  if (cargando) return <Spinner />;
  if (!staff.length) return <div style={{ padding: 30, color: color.slate400 }}>No hay profesionales en esta institución.</div>;

  const prof = staff.find((s) => String(s.id) === String(sel));
  const u = legajo?.usuario;
  const metricas = [
    { n: legajo?.casos_atendidos ?? "—", l: "casos atendidos" },
    { n: legajo?.pacientes_vistos ?? "—", l: "pacientes vistos" },
    { n: legajo?.llamados_fila ?? "—", l: "llamados de fila" },
    { n: legajo?.ultima_actividad ? fechaHora(legajo.ultima_actividad).split(" · ")[0] : "—", l: "última actividad" },
  ];

  return (
    <div style={{ padding: "22px 30px" }}>
      {/* Selector de profesional */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16, maxWidth: 360 }}>
        <span style={{ fontSize: 12.5, color: color.slate500, whiteSpace: "nowrap" }}>Profesional:</span>
        <Select value={sel} onChange={(e) => setSel(e.target.value)}>
          {staff.map((s) => <option key={s.id} value={s.id}>{s.nombre}</option>)}
        </Select>
      </div>

      {/* Header */}
      <Card style={{ padding: "22px 24px", marginBottom: 18, display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
        <Avatar nombre={prof?.nombre} i={prof?.id || 0} size={52} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 19, fontWeight: 800, letterSpacing: "-.3px" }}>{prof?.nombre}</div>
          <div style={{ fontSize: 13, color: color.slate500 }}>
            Profesional{u?.especialidad ? ` · ${u.especialidad}` : ""}{prof?.areas?.length ? ` · ${prof.areas.join(" · ")}` : ""}
          </div>
          {u?.matricula && <div style={{ marginTop: 6 }}><Mono style={{ fontSize: 13, fontWeight: 600 }}>M.N. {u.matricula}</Mono></div>}
        </div>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 8 }}>
          {u?.matricula ? <Badge tone="green">✓ Vigente</Badge> : <Badge tone="gray">Sin matrícula</Badge>}
          <button onClick={() => setEditar(true)} style={{ border: "none", background: "none", color: color.accent, cursor: "pointer", fontSize: 12.5, fontWeight: 600 }}>Editar legajo</button>
        </div>
      </Card>

      {!legajo ? (
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

          {/* Actividad reciente */}
          <Card style={{ padding: 0, overflow: "hidden" }}>
            <div style={{ padding: "16px 20px" }}>
              <div style={{ fontSize: 15, fontWeight: 700 }}>Actividad reciente</div>
              <div style={{ fontSize: 12.5, color: color.slate500 }}>Cada Atención que genera enlaza con una entrada en la Historia clínica del paciente.</div>
            </div>
            {legajo.actividad.length === 0 ? (
              <div style={{ padding: "0 20px 22px", fontSize: 13, color: color.slate400 }}>Sin actividad registrada.</div>
            ) : (
              <>
                <div style={{ display: "grid", gridTemplateColumns: "160px 1fr 1fr 80px", gap: 12, padding: "10px 20px", background: color.subtle, borderTop: `1px solid ${color.divider}`, fontSize: 11, fontWeight: 700, letterSpacing: ".5px", color: color.slate400 }}>
                  <div>FECHA</div><div>PACIENTE</div><div>ACCIÓN</div><div>CASO</div>
                </div>
                {legajo.actividad.map((a, i) => (
                  <div key={i} onClick={() => navigate(`/casos/${a.caso}`)} style={{ display: "grid", gridTemplateColumns: "160px 1fr 1fr 80px", gap: 12, alignItems: "center", padding: "13px 20px", borderTop: `1px solid ${color.divider}`, cursor: "pointer", fontSize: 13.5 }}>
                    <div style={{ color: color.slate500 }}>{fechaHora(a.fecha)}</div>
                    <div style={{ fontWeight: 600 }}>{a.paciente || "—"}</div>
                    <div style={{ color: color.slate600 }}>{a.accion}</div>
                    <Mono>#{String(a.caso).padStart(4, "0")}</Mono>
                  </div>
                ))}
              </>
            )}
          </Card>
        </>
      )}

      {editar && u && <EditarLegajoModal usuario={u} onClose={() => setEditar(false)} onSaved={() => { setEditar(false); api.get(`/usuarios/${sel}/legajo/`).then(setLegajo); }} />}
    </div>
  );
}

function EditarLegajoModal({ usuario, onClose, onSaved }) {
  const [especialidad, setEspecialidad] = useState(usuario.especialidad || "");
  const [matricula, setMatricula] = useState(usuario.matricula || "");
  const [guardando, setGuardando] = useState(false);
  async function guardar() {
    setGuardando(true);
    try {
      // Buscar legajo existente del usuario.
      const d = await api.get(`/legajos/?usuario=${usuario.id}`);
      const existente = (d.results || d)[0];
      if (existente) await api.patch(`/legajos/${existente.id}/`, { especialidad, matricula });
      else await api.post("/legajos/", { usuario: usuario.id, especialidad, matricula });
      onSaved();
    } finally {
      setGuardando(false);
    }
  }
  return (
    <Modal title={`Legajo · ${usuario.nombre}`} onClose={onClose} footer={<>
      <button onClick={onClose} style={{ height: 40, padding: "0 18px", borderRadius: 9, background: "#fff", border: "1px solid #D8DBE2", color: color.slate700, fontSize: 13.5, fontWeight: 600, cursor: "pointer" }}>Cancelar</button>
      <button onClick={guardar} disabled={guardando} style={{ height: 40, padding: "0 18px", borderRadius: 9, background: color.accent, color: "#fff", border: "none", fontSize: 13.5, fontWeight: 600, cursor: "pointer" }}>{guardando ? "…" : "Guardar"}</button>
    </>}>
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <Field label="Especialidad"><Input value={especialidad} onChange={(e) => setEspecialidad(e.target.value)} autoFocus /></Field>
        <Field label="Matrícula"><Input value={matricula} onChange={(e) => setMatricula(e.target.value)} placeholder="98.214" /></Field>
      </div>
    </Modal>
  );
}
