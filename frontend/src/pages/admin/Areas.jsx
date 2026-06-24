import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../api/client";
import { useInstitucion } from "../../auth/InstitutionContext";
import { Avatar, Badge, Button, Card, Field, Input, Modal, Select, Spinner, Textarea } from "../../components/ui";
import { Icon } from "../../components/icons";
import { color } from "../../theme";

const ROL_LABEL = { admin: "Admin de institución", configurador: "Configurador", administrativo: "Administrativo" };

// Estructura organizativa: árbol de áreas (izq) + ficha con pestañas (der).
export default function Areas() {
  const { institucion } = useInstitucion();
  const [areas, setAreas] = useState([]);
  const [sel, setSel] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [nuevoArea, setNuevoArea] = useState(false);
  const [editar, setEditar] = useState(false);

  async function cargar(seleccionar) {
    if (!institucion) return;
    setCargando(true);
    try {
      const d = await api.get(`/areas/?institucion=${institucion.id}`);
      const lista = d.results || d;
      setAreas(lista);
      setSel((prev) => lista.find((a) => a.id === (seleccionar ?? prev?.id)) || lista[0] || null);
    } finally {
      setCargando(false);
    }
  }
  useEffect(() => {
    cargar(); // eslint-disable-next-line
  }, [institucion]);

  return (
    <div style={{ height: "100%", display: "flex", minHeight: 0 }}>
      {/* Árbol de áreas */}
      <div style={{ width: 320, borderRight: `1px solid ${color.border}`, background: "#fff", display: "flex", flexDirection: "column", flex: "none" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "16px 18px 10px" }}>
          <span style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: ".7px", color: color.slate400 }}>ÁRBOL DE ÁREAS</span>
          <button onClick={() => setNuevoArea(true)} title="Nueva área" style={{ width: 28, height: 28, borderRadius: 8, border: `1px solid ${color.inputBorder}`, background: "#fff", color: color.accent, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <Icon name="plus" size={15} />
          </button>
        </div>
        <div style={{ overflow: "auto", flex: 1, padding: "0 10px 10px" }}>
          {cargando ? (
            <Spinner />
          ) : (
            <>
              {/* Raíz: institución */}
              <Nodo icon="building" label={institucion?.nombre} meta={`${areas.length} áreas`} nivel={0} />
              {areas.map((a) => (
                <div key={a.id}>
                  <Nodo
                    icon="building"
                    label={a.nombre}
                    meta={a.subareas?.length ? `${a.subareas.length} sub` : `${a.staff} staff`}
                    nivel={1}
                    activo={sel?.id === a.id}
                    onClick={() => setSel(a)}
                  />
                  {a.subareas?.map((s) => (
                    <Nodo key={s.id} icon="layers" label={s.nombre} meta="" nivel={2} />
                  ))}
                </div>
              ))}
            </>
          )}
        </div>
      </div>

      {/* Ficha del área */}
      <div style={{ flex: 1, overflow: "auto", padding: 30 }}>
        {!sel ? (
          <div style={{ color: color.slate400, fontSize: 14 }}>Elegí un área del árbol.</div>
        ) : (
          <FichaArea
            key={sel.id}
            area={sel}
            institucionNombre={institucion?.nombre}
            onEditar={() => setEditar(true)}
            onChange={() => cargar(sel.id)}
          />
        )}
      </div>

      {nuevoArea && <AreaModal institucionId={institucion?.id} onClose={() => setNuevoArea(false)} onSaved={(id) => { setNuevoArea(false); cargar(id); }} />}
      {editar && sel && <AreaModal area={sel} institucionId={institucion?.id} onClose={() => setEditar(false)} onSaved={() => { setEditar(false); cargar(sel.id); }} />}
    </div>
  );
}

function Nodo({ icon, label, meta, nivel, activo, onClick }) {
  return (
    <div
      onClick={onClick}
      style={{
        display: "flex", alignItems: "center", gap: 9,
        padding: "9px 10px", marginLeft: nivel * 18, borderRadius: 9,
        cursor: onClick ? "pointer" : "default",
        background: activo ? color.accent50 : "transparent",
        color: activo ? color.accent : color.slate700,
      }}
    >
      <Icon name={icon} size={16} />
      <span style={{ flex: 1, fontSize: 13.5, fontWeight: activo ? 700 : nivel === 0 ? 600 : 500, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{label}</span>
      {meta && <span style={{ fontSize: 11.5, color: color.slate400 }}>{meta}</span>}
    </div>
  );
}

function FichaArea({ area, institucionNombre, onEditar, onChange }) {
  const [tab, setTab] = useState("datos");
  const [asignar, setAsignar] = useState(false);
  const tabs = [
    { k: "datos", l: "Datos" },
    { k: "staff", l: "Staff" },
    { k: "procesos", l: "Procesos" },
    { k: "subareas", l: "Sub-áreas" },
  ];
  return (
    <div style={{ maxWidth: 760 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
        <span style={{ fontSize: 22, fontWeight: 800, letterSpacing: "-.4px" }}>{area.nombre}</span>
        <Badge tone="info">Área</Badge>
      </div>
      <div style={{ fontSize: 13.5, color: color.slate500, marginBottom: 16 }}>
        Responsable: <strong style={{ color: color.slate700 }}>{area.responsable || "—"}</strong>
      </div>
      <div style={{ display: "flex", gap: 10, marginBottom: 22 }}>
        <Button variant="secondary" onClick={onEditar}>Editar</Button>
        <Button onClick={() => setAsignar(true)} style={{ display: "flex", alignItems: "center", gap: 7 }}><Icon name="plus" size={15} /> Asignar profesional</Button>
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", borderBottom: `1px solid ${color.border}`, marginBottom: 20 }}>
        {tabs.map((t) => (
          <button key={t.k} onClick={() => setTab(t.k)} style={{ padding: "11px 2px", marginRight: 26, fontSize: 13.5, fontWeight: 600, border: "none", borderBottom: `2px solid ${tab === t.k ? color.accent : "transparent"}`, color: tab === t.k ? color.accent : color.slate400, background: "none", cursor: "pointer" }}>{t.l}</button>
        ))}
      </div>

      {tab === "datos" && (
        <Card style={{ padding: 22 }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 18 }}>
            <Campo k="Nombre" v={area.nombre} />
            <Campo k="Responsable / jefe" v={area.responsable || "—"} />
            <Campo k="Estado" v={area.activa ? "Activa" : "Inactiva"} />
            <Campo k="Área padre" v={institucionNombre} />
            <div style={{ gridColumn: "1 / -1" }}><Campo k="Descripción" v={area.descripcion || "—"} /></div>
          </div>
        </Card>
      )}
      {tab === "staff" && <StaffTab area={area} />}
      {tab === "procesos" && <ProcesosTab area={area} />}
      {tab === "subareas" && <SubareasTab area={area} onChange={onChange} />}

      {asignar && <AsignarModal area={area} onClose={() => setAsignar(false)} onSaved={() => { setAsignar(false); onChange(); }} />}
    </div>
  );
}

function Campo({ k, v }) {
  return (
    <div>
      <div style={{ fontSize: 12, color: color.slate400, marginBottom: 3 }}>{k}</div>
      <div style={{ fontSize: 14, fontWeight: 600, color: color.slate900 }}>{v}</div>
    </div>
  );
}

function StaffTab({ area }) {
  const [filas, setFilas] = useState(null);
  useEffect(() => {
    (async () => {
      const [membs, usuarios] = await Promise.all([
        api.get(`/membresias/?institucion=${area.institucion}`),
        api.get("/usuarios/"),
      ]);
      const usuMap = Object.fromEntries((usuarios.results || usuarios).map((u) => [u.id, u]));
      const lista = (membs.results || membs)
        .filter((m) => (m.areas || []).includes(area.id))
        .map((m) => ({ id: m.id, u: usuMap[m.usuario], rol: ROL_LABEL[m.rol] || m.rol }));
      setFilas(lista);
    })();
  }, [area.id]);
  if (filas === null) return <Spinner />;
  if (!filas.length) return <Card style={{ padding: 24, fontSize: 13.5, color: color.slate400 }}>Sin profesionales asignados a esta área.</Card>;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {filas.map((f) => (
        <Card key={f.id} style={{ padding: "12px 16px", display: "flex", alignItems: "center", gap: 12 }}>
          <Avatar nombre={f.u?.nombre_completo || f.u?.email} i={f.id} size={32} />
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 14, fontWeight: 600 }}>{f.u?.nombre_completo || "—"}</div>
            <div style={{ fontSize: 12, color: color.slate500 }}>{f.u?.email}</div>
          </div>
          <Badge tone="neutral">{f.rol}</Badge>
        </Card>
      ))}
    </div>
  );
}

function ProcesosTab({ area }) {
  const navigate = useNavigate();
  const [flujos, setFlujos] = useState(null);
  useEffect(() => {
    api.get(`/flujos/?area=${area.id}`).then((d) => setFlujos(d.results || d));
  }, [area.id]);
  if (flujos === null) return <Spinner />;
  if (!flujos.length) return <Card style={{ padding: 24, fontSize: 13.5, color: color.slate400 }}>No hay flujos en esta área.</Card>;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {flujos.map((f) => (
        <Card key={f.id} onClick={() => navigate(`/flujos/${f.id}`)} style={{ padding: "13px 16px", display: "flex", alignItems: "center", gap: 11, cursor: "pointer" }}>
          <div style={{ width: 32, height: 32, borderRadius: 8, background: color.accent50, color: color.accent, display: "flex", alignItems: "center", justifyContent: "center", flex: "none" }}><Icon name="workflow" size={16} /></div>
          <span style={{ fontSize: 14, fontWeight: 600 }}>{f.titulo}</span>
        </Card>
      ))}
    </div>
  );
}

function SubareasTab({ area, onChange }) {
  const [nueva, setNueva] = useState("");
  const [guardando, setGuardando] = useState(false);
  async function agregar() {
    if (!nueva.trim()) return;
    setGuardando(true);
    try {
      await api.post("/subareas/", { area: area.id, nombre: nueva.trim() });
      setNueva("");
      onChange();
    } finally {
      setGuardando(false);
    }
  }
  return (
    <div>
      {area.subareas?.length ? (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 16 }}>
          {area.subareas.map((s) => (
            <span key={s.id} style={{ fontSize: 13, background: color.subtle, border: `1px solid ${color.border}`, borderRadius: 8, padding: "6px 12px" }}>{s.nombre}</span>
          ))}
        </div>
      ) : (
        <div style={{ fontSize: 13.5, color: color.slate400, marginBottom: 16 }}>Sin sub-áreas. (Una sub-área no contiene sub-áreas.)</div>
      )}
      <div style={{ display: "flex", gap: 10, maxWidth: 420 }}>
        <Input placeholder="Nueva sub-área…" value={nueva} onChange={(e) => setNueva(e.target.value)} onKeyDown={(e) => e.key === "Enter" && agregar()} />
        <Button variant="secondary" disabled={guardando || !nueva.trim()} onClick={agregar}>Agregar</Button>
      </div>
    </div>
  );
}

function AreaModal({ area, institucionId, onClose, onSaved }) {
  const esNuevo = !area;
  const [f, setF] = useState({ nombre: area?.nombre || "", responsable: area?.responsable || "", descripcion: area?.descripcion || "" });
  const [guardando, setGuardando] = useState(false);
  const set = (k, v) => setF((p) => ({ ...p, [k]: v }));
  async function guardar() {
    setGuardando(true);
    try {
      if (esNuevo) {
        const a = await api.post("/areas/", { institucion: institucionId, ...f });
        onSaved(a.id);
      } else {
        await api.patch(`/areas/${area.id}/`, f);
        onSaved(area.id);
      }
    } finally {
      setGuardando(false);
    }
  }
  return (
    <Modal title={esNuevo ? "Nueva área" : "Editar área"} onClose={onClose} footer={<><Button variant="secondary" onClick={onClose}>Cancelar</Button><Button disabled={guardando || !f.nombre} onClick={guardar}>{guardando ? "…" : "Guardar"}</Button></>}>
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <Field label="Nombre *"><Input value={f.nombre} onChange={(e) => set("nombre", e.target.value)} autoFocus /></Field>
        <Field label="Responsable / jefe"><Input value={f.responsable} onChange={(e) => set("responsable", e.target.value)} placeholder="Dra. Laura Méndez" /></Field>
        <Field label="Descripción"><Textarea value={f.descripcion} onChange={(e) => set("descripcion", e.target.value)} /></Field>
      </div>
    </Modal>
  );
}

function AsignarModal({ area, onClose, onSaved }) {
  const [membs, setMembs] = useState([]);
  const [sel, setSel] = useState("");
  const [guardando, setGuardando] = useState(false);
  useEffect(() => {
    (async () => {
      const [m, usuarios] = await Promise.all([
        api.get(`/membresias/?institucion=${area.institucion}`),
        api.get("/usuarios/"),
      ]);
      const usuMap = Object.fromEntries((usuarios.results || usuarios).map((u) => [u.id, u]));
      const lista = (m.results || m)
        .filter((x) => !(x.areas || []).includes(area.id))
        .map((x) => ({ id: x.id, areas: x.areas || [], nombre: usuMap[x.usuario]?.nombre_completo || usuMap[x.usuario]?.email, rol: ROL_LABEL[x.rol] || x.rol }));
      setMembs(lista);
      if (lista[0]) setSel(String(lista[0].id));
    })();
  }, [area.id]);
  async function asignar() {
    const m = membs.find((x) => String(x.id) === String(sel));
    if (!m) return;
    setGuardando(true);
    try {
      await api.patch(`/membresias/${m.id}/`, { areas: [...m.areas, area.id] });
      onSaved();
    } finally {
      setGuardando(false);
    }
  }
  return (
    <Modal title={`Asignar profesional a ${area.nombre}`} onClose={onClose} footer={<><Button variant="secondary" onClick={onClose}>Cancelar</Button><Button disabled={guardando || !sel} onClick={asignar}>{guardando ? "…" : "Asignar"}</Button></>}>
      {membs.length === 0 ? (
        <div style={{ fontSize: 13.5, color: color.slate500 }}>No hay profesionales disponibles para asignar.</div>
      ) : (
        <Field label="Profesional">
          <Select value={sel} onChange={(e) => setSel(e.target.value)}>
            {membs.map((m) => <option key={m.id} value={m.id}>{m.nombre} · {m.rol}</option>)}
          </Select>
        </Field>
      )}
    </Modal>
  );
}
