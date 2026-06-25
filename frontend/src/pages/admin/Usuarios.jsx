import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { useInstitucion } from "../../auth/InstitutionContext";
import { Avatar, Badge, Button, Card, Field, Input, Modal, Select, Spinner } from "../../components/ui";
import { Icon } from "../../components/icons";
import { color } from "../../theme";

const ROLES = [
  { value: "admin", label: "Admin de institución" },
  { value: "configurador", label: "Configurador" },
  { value: "jefe_area", label: "Jefe / Supervisor de área" },
  { value: "administrativo", label: "Administrativo" },
  { value: "enfermeria", label: "Enfermería" },
  { value: "medico", label: "Médico / profesional" },
];
const ROL_LABEL = { admin: "Admin del sistema", configurador: "Configurador", jefe_area: "Jefe / Supervisor de área", administrativo: "Administrativo", enfermeria: "Enfermería", medico: "Médico / profesional" };
const COLS = "minmax(180px,1.6fr) 160px 150px 110px 44px";

export default function Usuarios() {
  const { institucion } = useInstitucion();
  const [filas, setFilas] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [editando, setEditando] = useState(null);

  async function cargar() {
    if (!institucion) return;
    setCargando(true);
    try {
      const [membs, usuarios, areas] = await Promise.all([
        api.get(`/membresias/?institucion=${institucion.id}`),
        api.get("/usuarios/"),
        api.get(`/areas/?institucion=${institucion.id}`),
      ]);
      const usuMap = Object.fromEntries((usuarios.results || usuarios).map((u) => [u.id, u]));
      const areaMap = Object.fromEntries((areas.results || areas).map((a) => [a.id, a.nombre]));
      const porUsuario = {};
      for (const m of membs.results || membs) {
        const u = usuMap[m.usuario];
        if (!u) continue;
        if (!porUsuario[m.usuario]) porUsuario[m.usuario] = { usuario: u, roles: new Set(), areas: new Set() };
        porUsuario[m.usuario].roles.add(ROL_LABEL[m.rol] || m.rol);
        (m.areas || []).forEach((aid) => areaMap[aid] && porUsuario[m.usuario].areas.add(areaMap[aid]));
      }
      setFilas(Object.values(porUsuario).map((x) => ({ ...x, roles: [...x.roles], areas: [...x.areas] })));
    } finally {
      setCargando(false);
    }
  }
  useEffect(() => {
    cargar(); // eslint-disable-next-line
  }, [institucion]);

  return (
    <div style={{ padding: "26px 30px" }}>
      <Card style={{ overflow: "hidden", padding: 0 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "18px 22px" }}>
          <div>
            <div style={{ fontSize: 17, fontWeight: 700 }}>Usuarios</div>
            <div style={{ fontSize: 12.5, color: color.slate500 }}>{filas.length} personas con acceso al sistema</div>
          </div>
          <Button onClick={() => setEditando({})} style={{ display: "flex", alignItems: "center", gap: 8 }}><Icon name="plus" size={15} /> Crear usuario</Button>
        </div>

        {cargando ? (
          <Spinner />
        ) : filas.length === 0 ? (
          <div style={{ padding: 40, textAlign: "center", color: color.slate400, fontSize: 13.5 }}>No hay usuarios con acceso a esta institución.</div>
        ) : (
          <>
            <div style={{ display: "grid", gridTemplateColumns: COLS, gap: 13, padding: "11px 22px", background: color.subtle, borderTop: `1px solid ${color.divider}`, fontSize: 11, fontWeight: 700, letterSpacing: ".5px", color: color.slate400 }}>
              <div>USUARIO</div><div>ROL(ES)</div><div>ÁREA(S)</div><div>ESTADO</div><div />
            </div>
            {filas.map((f) => (
              <div key={f.usuario.id} onClick={() => setEditando(f.usuario)} style={{ display: "grid", gridTemplateColumns: COLS, gap: 13, alignItems: "center", padding: "13px 22px", borderTop: `1px solid ${color.divider}`, cursor: "pointer" }}
                onMouseEnter={(e) => (e.currentTarget.style.background = color.subtle)} onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}>
                <div style={{ display: "flex", alignItems: "center", gap: 11, minWidth: 0 }}>
                  <Avatar nombre={f.usuario.nombre_completo || f.usuario.email} i={f.usuario.id} size={32} />
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{f.usuario.nombre_completo || "—"}</div>
                    <div style={{ fontSize: 12, color: color.slate500, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{f.usuario.email}</div>
                  </div>
                </div>
                <div style={{ fontSize: 13.5, color: color.slate700 }}>{f.roles.join(" · ") || "—"}</div>
                <div style={{ fontSize: 13.5, color: color.slate600 }}>{f.areas.join(", ") || "—"}</div>
                <div><Badge tone={f.usuario.is_active ? "green" : "gray"}>{f.usuario.is_active ? "Activo" : "Inactivo"}</Badge></div>
                <div style={{ textAlign: "right", color: color.slate400 }}><Icon name="edit" size={15} /></div>
              </div>
            ))}
          </>
        )}
      </Card>

      {editando && <UsuarioModal usuario={editando} onClose={() => setEditando(null)} onSaved={() => { setEditando(null); cargar(); }} />}
    </div>
  );
}

function UsuarioModal({ usuario, onClose, onSaved }) {
  const esNuevo = !usuario.id;
  const [form, setForm] = useState({
    email: usuario.email || "",
    nombre: usuario.nombre || "",
    apellido: usuario.apellido || "",
    password: "",
    is_active: usuario.is_active ?? true,
  });
  const [guardando, setGuardando] = useState(false);
  const [instituciones, setInstituciones] = useState([]);
  const [membresias, setMembresias] = useState([]);
  const [nuevaMemb, setNuevaMemb] = useState({ institucion: "", rol: "administrativo" });
  const set = (k, v) => setForm((p) => ({ ...p, [k]: v }));

  useEffect(() => {
    (async () => {
      const d = await api.get("/instituciones/");
      const lista = d.results || d;
      setInstituciones(lista);
      setNuevaMemb((p) => ({ ...p, institucion: lista[0] ? String(lista[0].id) : "" }));
      if (usuario.id) {
        const m = await api.get(`/membresias/?usuario=${usuario.id}`);
        setMembresias(m.results || m);
      }
    })();
  }, [usuario.id]);

  async function guardar() {
    setGuardando(true);
    try {
      const payload = { email: form.email, nombre: form.nombre, apellido: form.apellido, is_active: form.is_active };
      if (form.password) payload.password = form.password;
      if (esNuevo) await api.post("/usuarios/", payload);
      else await api.patch(`/usuarios/${usuario.id}/`, payload);
      onSaved();
    } finally {
      setGuardando(false);
    }
  }

  async function agregarMembresia() {
    if (!usuario.id || !nuevaMemb.institucion) return;
    const m = await api.post("/membresias/", { usuario: usuario.id, institucion: nuevaMemb.institucion, rol: nuevaMemb.rol });
    setMembresias((p) => [...p, m]);
  }
  async function quitarMembresia(id) {
    await api.del(`/membresias/${id}/`);
    setMembresias((p) => p.filter((m) => m.id !== id));
  }

  const instNombre = (id) => instituciones.find((i) => i.id === id)?.nombre || `#${id}`;

  return (
    <Modal
      title={esNuevo ? "Nuevo usuario" : "Editar usuario"}
      width={520}
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancelar</Button>
          <Button disabled={guardando || !form.email || !form.nombre} onClick={guardar}>{guardando ? "Guardando…" : "Guardar"}</Button>
        </>
      }
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <Field label="Email *"><Input type="email" value={form.email} onChange={(e) => set("email", e.target.value)} autoFocus /></Field>
        <div style={{ display: "flex", gap: 12 }}>
          <Field label="Nombre *"><Input value={form.nombre} onChange={(e) => set("nombre", e.target.value)} /></Field>
          <Field label="Apellido"><Input value={form.apellido} onChange={(e) => set("apellido", e.target.value)} /></Field>
        </div>
        <Field label={esNuevo ? "Contraseña" : "Nueva contraseña (dejar vacío para no cambiar)"}>
          <Input type="password" value={form.password} onChange={(e) => set("password", e.target.value)} />
        </Field>
        <label style={{ display: "flex", alignItems: "center", gap: 9, fontSize: 13.5 }}>
          <input type="checkbox" checked={form.is_active} onChange={(e) => set("is_active", e.target.checked)} /> Activo
        </label>

        {!esNuevo && (
          <div style={{ borderTop: `1px solid ${color.divider}`, paddingTop: 14 }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: color.slate700, marginBottom: 10 }}>Membresías</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 12 }}>
              {membresias.length === 0 && <div style={{ fontSize: 13, color: color.slate400 }}>Sin membresías.</div>}
              {membresias.map((m) => (
                <div key={m.id} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", fontSize: 13 }}>
                  <span>{instNombre(m.institucion)} · <strong>{m.rol_display}</strong></span>
                  <button onClick={() => quitarMembresia(m.id)} style={{ border: "none", background: "none", color: "#B42318", cursor: "pointer", fontSize: 12 }}>Quitar</button>
                </div>
              ))}
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <Select value={nuevaMemb.institucion} onChange={(e) => setNuevaMemb((p) => ({ ...p, institucion: e.target.value }))}>
                {instituciones.map((i) => <option key={i.id} value={i.id}>{i.nombre}</option>)}
              </Select>
              <Select value={nuevaMemb.rol} onChange={(e) => setNuevaMemb((p) => ({ ...p, rol: e.target.value }))}>
                {ROLES.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
              </Select>
              <Button variant="secondary" onClick={agregarMembresia} style={{ whiteSpace: "nowrap" }}>+ Add</Button>
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
}
