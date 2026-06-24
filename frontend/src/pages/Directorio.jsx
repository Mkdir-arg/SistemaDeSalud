import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useInstitucion } from "../auth/InstitutionContext";
import { Logo } from "../components/Logo";
import { Avatar, Badge, Button, Card, Field, Input, Modal, Mono, Select, Spinner, Table } from "../components/ui";
import { Icon } from "../components/icons";
import { color } from "../theme";

const ESTADO_TONE = { activa: "green", en_alta: "amber", inactiva: "gray" };

// Shell de plataforma (super admin): sidebar con Instituciones / Usuarios.
export default function Directorio() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [vista, setVista] = useState("instituciones");

  const NAV = [
    { key: "instituciones", label: "Instituciones", icon: "building" },
    { key: "usuarios", label: "Usuarios", icon: "users" },
  ];

  return (
    <div style={{ display: "flex", minHeight: "100vh", background: color.canvas }}>
      {/* Sidebar de plataforma */}
      <aside style={{ width: 240, background: "#fff", borderRight: `1px solid ${color.border}`, display: "flex", flexDirection: "column", flex: "none", height: "100vh", position: "sticky", top: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 11, padding: "18px 18px 14px" }}>
          <Logo size={34} />
          <div>
            <div style={{ fontSize: 17, fontWeight: 800, letterSpacing: "-.4px" }}>Cauce</div>
            <div style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: ".6px", color: color.slate400 }}>PLATAFORMA</div>
          </div>
        </div>
        <nav style={{ padding: "8px 12px", display: "flex", flexDirection: "column", gap: 2 }}>
          {NAV.map((n) => {
            const activo = vista === n.key;
            return (
              <button key={n.key} onClick={() => setVista(n.key)}
                style={{ display: "flex", alignItems: "center", gap: 11, padding: "9px 12px", borderRadius: 9, fontSize: 13.5, fontWeight: 600, border: "none", cursor: "pointer", textAlign: "left", color: activo ? "#fff" : color.slate600, background: activo ? color.accent : "transparent" }}>
                <Icon name={n.icon} size={17} /> {n.label}
              </button>
            );
          })}
        </nav>
        <div style={{ flex: 1 }} />
        <div style={{ borderTop: `1px solid ${color.divider}`, padding: 14, display: "flex", alignItems: "center", gap: 10 }}>
          <Avatar nombre={user?.nombre_completo || user?.email} size={34} />
          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={{ fontSize: 12.5, fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{user?.nombre_completo || user?.email}</div>
            <div style={{ fontSize: 11, color: color.slate400 }}>Super admin</div>
          </div>
          <button onClick={() => { logout(); navigate("/login"); }} title="Cerrar sesión" style={{ border: "none", background: "none", cursor: "pointer", color: color.slate400, display: "flex" }}><Icon name="power" size={17} /></button>
        </div>
      </aside>

      {/* Main */}
      <main style={{ flex: 1, minWidth: 0, height: "100vh", display: "flex", flexDirection: "column" }}>
        <header style={{ height: 64, flex: "none", background: "#fff", borderBottom: `1px solid ${color.border}`, display: "flex", alignItems: "center", gap: 16, padding: "0 26px" }}>
          <div style={{ fontSize: 17, fontWeight: 700 }}>{vista === "instituciones" ? "Instituciones" : "Usuarios"}</div>
          <div style={{ display: "inline-flex", alignItems: "center", gap: 7, padding: "6px 12px", borderRadius: 999, background: color.accent50, color: color.accent, fontSize: 12.5, fontWeight: 600 }}>
            <Icon name="building" size={14} /> Alcance: todas las instituciones
          </div>
          <div style={{ flex: 1 }} />
          <div style={{ display: "flex", alignItems: "center", background: "#F2F3F6", border: `1px solid ${color.border}`, borderRadius: 9, padding: 3, gap: 2 }}>
            <span style={{ padding: "6px 12px", borderRadius: 7, fontSize: 12.5, fontWeight: 600, background: "#fff", color: color.accent, boxShadow: "0 1px 2px rgba(16,24,40,.12)" }}>Super admin</span>
            <span style={{ padding: "6px 12px", borderRadius: 7, fontSize: 12.5, fontWeight: 600, color: color.slate500 }}>Admin de institución</span>
          </div>
        </header>
        <div style={{ flex: 1, overflow: "auto", padding: 30 }}>
          {vista === "instituciones" ? <InstitucionesView /> : <UsuariosView />}
        </div>
      </main>
    </div>
  );
}

// --------------------------------------------------------------------------- //
function InstitucionesView() {
  const { setInstitucion } = useInstitucion();
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [busca, setBusca] = useState("");
  const [nueva, setNueva] = useState(false);

  async function cargar() {
    try {
      const d = await api.get("/instituciones/");
      setItems(d.results || d);
    } finally {
      setCargando(false);
    }
  }
  useEffect(() => { cargar(); }, []);

  function entrar(inst) {
    setInstitucion(inst);
    navigate("/inicio");
  }
  const filtrados = items.filter((i) => i.nombre.toLowerCase().includes(busca.toLowerCase()));

  return (
    <>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16, marginBottom: 18, flexWrap: "wrap" }}>
        <div>
          <div style={{ fontSize: 27, fontWeight: 800, letterSpacing: "-.5px" }}>Instituciones</div>
          <div style={{ fontSize: 13, color: color.slate500, marginTop: 2 }}>{items.length} instituciones en la plataforma · super admin</div>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <div style={{ width: 280 }}><Input placeholder="Buscar institución…" value={busca} onChange={(e) => setBusca(e.target.value)} /></div>
          <Button onClick={() => setNueva(true)} style={{ whiteSpace: "nowrap", display: "flex", alignItems: "center", gap: 8 }}><Icon name="plus" size={15} /> Nueva institución</Button>
        </div>
      </div>

      <Card style={{ overflow: "hidden", padding: 0 }}>
        {cargando ? <Spinner /> : (
          <Table
            rows={filtrados}
            vacio="No hay instituciones"
            columns={[
              { key: "institucion", label: "Institución", render: (i) => (
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  <div style={{ width: 36, height: 36, borderRadius: 10, background: color.accent50, color: color.accent, display: "flex", alignItems: "center", justifyContent: "center", flex: "none" }}><Icon name="building" size={18} /></div>
                  <span style={{ fontWeight: 600 }}>{i.nombre}</span>
                </div>
              ) },
              { key: "tipo", label: "Tipo", render: (i) => <span style={{ color: color.slate500 }}>{i.tipo || "—"}</span> },
              { key: "areas_count", label: "Áreas", render: (i) => <Mono>{i.areas_count}</Mono> },
              { key: "staff", label: "Staff", render: (i) => <Mono>{i.staff}</Mono> },
              { key: "estado", label: "Estado", render: (i) => <Badge tone={ESTADO_TONE[i.estado] || "green"}>{i.estado_display || "Activa"}</Badge> },
              { key: "accion", label: "", render: (i) => (
                <div style={{ textAlign: "right" }}>
                  <Button onClick={() => entrar(i)} style={{ height: 36, padding: "0 16px", display: "inline-flex", alignItems: "center", gap: 7 }}>Ingresar <Icon name="enter" size={15} /></Button>
                </div>
              ) },
            ]}
          />
        )}
      </Card>

      {nueva && <NuevaInstitucionModal onClose={() => setNueva(false)} onSaved={() => { setNueva(false); cargar(); }} />}
    </>
  );
}

function NuevaInstitucionModal({ onClose, onSaved }) {
  const [f, setF] = useState({ nombre: "", tipo: "", cuit: "", admin: "" });
  const [usuarios, setUsuarios] = useState([]);
  const [guardando, setGuardando] = useState(false);
  const set = (k, v) => setF((p) => ({ ...p, [k]: v }));

  useEffect(() => {
    api.get("/usuarios/").then((d) => setUsuarios((d.results || d).filter((u) => !u.is_superuser)));
  }, []);

  async function crear() {
    setGuardando(true);
    try {
      const inst = await api.post("/instituciones/", { nombre: f.nombre, tipo: f.tipo, cuit: f.cuit, estado: "en_alta" });
      // Asignar el usuario elegido como admin de la institución.
      if (f.admin) {
        await api.post("/membresias/", { usuario: Number(f.admin), institucion: inst.id, rol: "admin" });
      }
      onSaved();
    } finally {
      setGuardando(false);
    }
  }

  return (
    <Modal title="Nueva institución" onClose={onClose} footer={<><Button variant="secondary" onClick={onClose}>Cancelar</Button><Button disabled={guardando || !f.nombre} onClick={crear}>{guardando ? "…" : "Crear"}</Button></>}>
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <Field label="Nombre *"><Input value={f.nombre} onChange={(e) => set("nombre", e.target.value)} autoFocus placeholder="Hospital Central" /></Field>
        <Field label="Tipo"><Input value={f.tipo} onChange={(e) => set("tipo", e.target.value)} placeholder="Hospital general" /></Field>
        <Field label="CUIT"><Input value={f.cuit} onChange={(e) => set("cuit", e.target.value)} placeholder="30-12345678-9" /></Field>
        <Field label="Admin de la institución">
          <Select value={f.admin} onChange={(e) => set("admin", e.target.value)}>
            <option value="">— Asignar luego —</option>
            {usuarios.map((u) => <option key={u.id} value={u.id}>{u.nombre_completo || u.email} · {u.email}</option>)}
          </Select>
        </Field>
        <div style={{ fontSize: 12, color: color.slate400 }}>El admin se gestiona desde <strong>Usuarios</strong>. Será el responsable de esta institución.</div>
      </div>
    </Modal>
  );
}

// --------------------------------------------------------------------------- //
function UsuariosView() {
  const [items, setItems] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [busca, setBusca] = useState("");
  const [editando, setEditando] = useState(null);

  async function cargar() {
    setCargando(true);
    try {
      const d = await api.get("/usuarios/");
      setItems((d.results || d).filter((u) => !u.is_superuser));
    } finally {
      setCargando(false);
    }
  }
  useEffect(() => { cargar(); }, []);

  const filtrados = items.filter((u) => `${u.nombre_completo} ${u.email}`.toLowerCase().includes(busca.toLowerCase()));

  return (
    <>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16, marginBottom: 18, flexWrap: "wrap" }}>
        <div>
          <div style={{ fontSize: 27, fontWeight: 800, letterSpacing: "-.5px" }}>Usuarios</div>
          <div style={{ fontSize: 13, color: color.slate500, marginTop: 2 }}>{items.length} usuarios · candidatos a admin de institución</div>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <div style={{ width: 280 }}><Input placeholder="Buscar usuario…" value={busca} onChange={(e) => setBusca(e.target.value)} /></div>
          <Button onClick={() => setEditando({})} style={{ whiteSpace: "nowrap", display: "flex", alignItems: "center", gap: 8 }}><Icon name="plus" size={15} /> Nuevo usuario</Button>
        </div>
      </div>

      <Card style={{ overflow: "hidden", padding: 0 }}>
        {cargando ? <Spinner /> : (
          <Table
            rows={filtrados}
            onRowClick={(u) => setEditando(u)}
            vacio="No hay usuarios. Creá el primero para asignarlo como admin de una institución."
            columns={[
              { key: "usuario", label: "Usuario", render: (u) => (
                <div style={{ display: "flex", alignItems: "center", gap: 11 }}>
                  <Avatar nombre={u.nombre_completo || u.email} i={u.id} size={32} />
                  <div>
                    <div style={{ fontWeight: 600 }}>{u.nombre_completo || "—"}</div>
                    <div style={{ fontSize: 12, color: color.slate500 }}>{u.email}</div>
                  </div>
                </div>
              ) },
              { key: "is_active", label: "Estado", render: (u) => <Badge tone={u.is_active ? "green" : "gray"}>{u.is_active ? "Activo" : "Inactivo"}</Badge> },
              { key: "accion", label: "", render: () => <div style={{ textAlign: "right", color: color.slate400 }}><Icon name="edit" size={15} /></div> },
            ]}
          />
        )}
      </Card>

      {editando && <UsuarioModal usuario={editando} onClose={() => setEditando(null)} onSaved={() => { setEditando(null); cargar(); }} />}
    </>
  );
}

function UsuarioModal({ usuario, onClose, onSaved }) {
  const esNuevo = !usuario.id;
  const [f, setF] = useState({ email: usuario.email || "", nombre: usuario.nombre || "", apellido: usuario.apellido || "", password: "", is_active: usuario.is_active ?? true });
  const [guardando, setGuardando] = useState(false);
  const set = (k, v) => setF((p) => ({ ...p, [k]: v }));

  async function guardar() {
    setGuardando(true);
    try {
      const payload = { email: f.email, nombre: f.nombre, apellido: f.apellido, is_active: f.is_active };
      if (f.password) payload.password = f.password;
      if (esNuevo) await api.post("/usuarios/", payload);
      else await api.patch(`/usuarios/${usuario.id}/`, payload);
      onSaved();
    } finally {
      setGuardando(false);
    }
  }

  return (
    <Modal title={esNuevo ? "Nuevo usuario" : "Editar usuario"} onClose={onClose} footer={<><Button variant="secondary" onClick={onClose}>Cancelar</Button><Button disabled={guardando || !f.email || !f.nombre} onClick={guardar}>{guardando ? "…" : "Guardar"}</Button></>}>
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <Field label="Email *"><Input type="email" value={f.email} onChange={(e) => set("email", e.target.value)} autoFocus placeholder="admin@institucion.gob.ar" /></Field>
        <div style={{ display: "flex", gap: 12 }}>
          <Field label="Nombre *"><Input value={f.nombre} onChange={(e) => set("nombre", e.target.value)} /></Field>
          <Field label="Apellido"><Input value={f.apellido} onChange={(e) => set("apellido", e.target.value)} /></Field>
        </div>
        <Field label={esNuevo ? "Contraseña" : "Nueva contraseña (vacío = no cambiar)"}><Input type="password" value={f.password} onChange={(e) => set("password", e.target.value)} /></Field>
        <label style={{ display: "flex", alignItems: "center", gap: 9, fontSize: 13.5 }}>
          <input type="checkbox" checked={f.is_active} onChange={(e) => set("is_active", e.target.checked)} /> Activo
        </label>
      </div>
    </Modal>
  );
}
