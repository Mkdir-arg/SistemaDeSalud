import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useInstitucion } from "../auth/InstitutionContext";
import { PageHeader } from "../components/Shell";
import { Badge, Button, Card, EmptyState, Field, Modal, Select, Spinner, Textarea } from "../components/ui";
import { antiguedad } from "../lib/format";
import { color, estadoCaso } from "../theme";

const ACTIVOS = (c) => !["cerrado", "cancelado"].includes(c.estado);
const PRIORIDADES = [
  { value: "normal", label: "Normal" },
  { value: "alta", label: "Alta" },
  { value: "urgente", label: "Urgente" },
];

// Vista del jefe/supervisor de área: todos los casos activos de su área, con las
// acciones de supervisión (reasignar, repriorizar, cancelar). Gateada por la
// capacidad "supervision"; el backend marca `puede_supervisar` por caso.
export default function Supervision() {
  const { institucion } = useInstitucion();
  const navigate = useNavigate();
  const [casos, setCasos] = useState([]);
  const [staff, setStaff] = useState([]);
  const [membresias, setMembresias] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(false);
  const [reasignar, setReasignar] = useState(null); // caso en modal de reasignación
  const [cancelar, setCancelar] = useState(null); // caso en modal de cancelación

  const cargar = useCallback(async () => {
    if (!institucion) return;
    setCargando(true);
    try {
      const [c, u, m] = await Promise.all([
        api.get(`/casos/?institucion=${institucion.id}`),
        api.get(`/usuarios/`),
        api.get(`/membresias/?institucion=${institucion.id}`),
      ]);
      setCasos((c.results || c).filter((x) => x.puede_supervisar && ACTIVOS(x)));
      setStaff(u.results || u);
      setMembresias(m.results || m);
      setError(false);
    } catch {
      setError(true);
    } finally {
      setCargando(false);
    }
  }, [institucion]);
  useEffect(() => { cargar(); }, [cargar]);

  async function priorizar(caso, prioridad) {
    await api.post(`/casos/${caso.id}/priorizar/`, { prioridad });
    cargar();
  }

  // Staff candidato para reasignar: quien tenga el área del caso (si no hay área, todos).
  function staffDelArea(areaId) {
    if (!areaId) return staff;
    const ids = new Set(membresias.filter((m) => (m.areas || []).includes(areaId)).map((m) => m.usuario));
    const f = staff.filter((u) => ids.has(u.id));
    return f.length ? f : staff;
  }

  if (cargando && !casos.length) return <Spinner label="Cargando supervisión…" />;
  if (error && !casos.length) {
    return (
      <div style={{ padding: 48, textAlign: "center" }}>
        <div style={{ fontSize: 15, fontWeight: 700, color: color.slate700 }}>No pudimos cargar la supervisión</div>
        <div style={{ fontSize: 13, color: color.slate400, margin: "6px 0 16px" }}>Revisá la conexión y reintentá.</div>
        <Button onClick={cargar}>Reintentar</Button>
      </div>
    );
  }

  return (
    <>
      <PageHeader
        subtitle="Todos los casos activos de tu área. Reasigná, cambiá la prioridad o cancelá."
        right={<Button variant="secondary" onClick={cargar}>↻ Actualizar</Button>}
      />
      <div style={{ padding: "22px 32px" }}>
        {casos.length === 0 ? (
          <EmptyState title="No hay casos activos en tu área" hint="Cuando ingresen casos a tu área, vas a poder supervisarlos desde acá." />
        ) : (
          <Card style={{ overflow: "hidden" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13.5 }}>
              <thead>
                <tr style={{ background: color.subtle, color: color.slate500, textAlign: "left" }}>
                  <Th>Paciente</Th><Th>Paso / flujo</Th><Th>Estado</Th><Th>Prioridad</Th>
                  <Th>Asignado</Th><Th>Espera</Th><Th />
                </tr>
              </thead>
              <tbody>
                {casos.map((c) => {
                  const est = estadoCaso[c.estado] || { label: c.estado_display, tone: "neutral" };
                  return (
                    <tr key={c.id} style={{ borderTop: `1px solid ${color.divider}` }}>
                      <Td>
                        <div style={{ fontWeight: 600, cursor: "pointer" }} onClick={() => navigate(`/casos/${c.id}`)}>
                          {c.ciudadano_nombre || "Sin paciente"}
                        </div>
                        <div style={{ fontSize: 11.5, color: color.slate400 }}>{c.area_nombre || "—"}</div>
                      </Td>
                      <Td style={{ color: color.slate600 }}>
                        {c.paso_actual || "—"}
                        <div style={{ fontSize: 11.5, color: color.slate400 }}>{c.flujo_titulo}</div>
                      </Td>
                      <Td><Badge tone={est.tone}>{est.label}</Badge></Td>
                      <Td>
                        <Select value={c.prioridad} onChange={(e) => priorizar(c, e.target.value)} style={{ height: 32, width: 110 }}>
                          {PRIORIDADES.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
                        </Select>
                      </Td>
                      <Td style={{ color: color.slate600 }}>{c.asignado_nombre || <span style={{ color: color.slate400 }}>—</span>}</Td>
                      <Td style={{ color: color.slate500 }}>{antiguedad(c.creado)}</Td>
                      <Td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                        <Button variant="secondary" style={{ height: 32, padding: "0 12px", marginRight: 8 }} onClick={() => setReasignar(c)}>Reasignar</Button>
                        <Button variant="danger" style={{ height: 32, padding: "0 12px" }} onClick={() => setCancelar(c)}>Cancelar</Button>
                      </Td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </Card>
        )}
      </div>

      {reasignar && (
        <ReasignarModal caso={reasignar} candidatos={staffDelArea(reasignar.area_actual)}
          onClose={() => setReasignar(null)} onDone={() => { setReasignar(null); cargar(); }} />
      )}
      {cancelar && (
        <CancelarModal caso={cancelar} onClose={() => setCancelar(null)} onDone={() => { setCancelar(null); cargar(); }} />
      )}
    </>
  );
}

export function ReasignarModal({ caso, candidatos, onClose, onDone }) {
  const [usuarioId, setUsuarioId] = useState(candidatos[0] ? String(candidatos[0].id) : "");
  const [guardando, setGuardando] = useState(false);
  async function guardar() {
    if (!usuarioId) return;
    setGuardando(true);
    try { await api.post(`/casos/${caso.id}/asignar/`, { usuario_id: Number(usuarioId) }); onDone(); }
    finally { setGuardando(false); }
  }
  return (
    <Modal title={`Reasignar caso de ${caso.ciudadano_nombre || "—"}`} onClose={onClose}
      footer={<><Button variant="secondary" onClick={onClose}>Cancelar</Button>
        <Button disabled={!usuarioId || guardando} onClick={guardar}>{guardando ? "Reasignando…" : "Reasignar"}</Button></>}>
      {candidatos.length === 0 ? (
        <div style={{ fontSize: 13.5, color: color.slate400 }}>No hay staff disponible para esta área.</div>
      ) : (
        <Field label="Asignar a">
          <Select value={usuarioId} onChange={(e) => setUsuarioId(e.target.value)}>
            {candidatos.map((u) => <option key={u.id} value={u.id}>{u.nombre_completo || u.email}</option>)}
          </Select>
        </Field>
      )}
    </Modal>
  );
}

export function CancelarModal({ caso, onClose, onDone }) {
  const [motivo, setMotivo] = useState("");
  const [guardando, setGuardando] = useState(false);
  async function confirmar() {
    setGuardando(true);
    try { await api.post(`/casos/${caso.id}/cancelar/`, { motivo: motivo.trim() }); onDone(); }
    finally { setGuardando(false); }
  }
  return (
    <Modal title={`Cancelar caso de ${caso.ciudadano_nombre || "—"}`} onClose={onClose}
      footer={<><Button variant="secondary" onClick={onClose}>Volver</Button>
        <Button variant="danger" disabled={guardando} onClick={confirmar}>{guardando ? "Cancelando…" : "Cancelar caso"}</Button></>}>
      <div style={{ fontSize: 13.5, color: color.slate600, marginBottom: 12 }}>
        El caso saldrá de las colas y quedará cerrado como <strong>cancelado</strong>. Esta acción no se revierte.
      </div>
      <Field label="Motivo (opcional)">
        <Textarea value={motivo} onChange={(e) => setMotivo(e.target.value)} placeholder="Ej.: duplicado, paciente se retiró…" />
      </Field>
    </Modal>
  );
}

function Th({ children }) {
  return <th style={{ padding: "12px 16px", fontWeight: 600, fontSize: 12.5, whiteSpace: "nowrap" }}>{children}</th>;
}
function Td({ children, style }) {
  return <td style={{ padding: "12px 16px", verticalAlign: "middle", ...style }}>{children}</td>;
}
