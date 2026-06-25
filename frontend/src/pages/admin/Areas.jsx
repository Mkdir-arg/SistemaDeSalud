import { useEffect, useMemo, useState } from "react";
import { api } from "../../api/client";
import { useInstitucion } from "../../auth/InstitutionContext";
import { Avatar, Badge, Button, Card, Field, Input, Modal, Mono, Select, Spinner, Table, Textarea } from "../../components/ui";
import { Icon } from "../../components/icons";
import { color } from "../../theme";

const ROL_LABEL = { admin: "Admin de institución", configurador: "Configurador", administrativo: "Administrativo", medico: "Médico / profesional" };

// Estructura organizativa: tabla de áreas + ficha en panel lateral (drawer).
export default function Areas() {
  const { institucion } = useInstitucion();
  const [areas, setAreas] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [nuevoArea, setNuevoArea] = useState(false);
  const [sel, setSel] = useState(null);     // área abierta en el panel lateral
  const [editar, setEditar] = useState(false);
  const [borrar, setBorrar] = useState(null);

  async function cargar() {
    if (!institucion) return;
    setCargando(true);
    try {
      const d = await api.get(`/areas/?institucion=${institucion.id}`);
      const lista = d.results || d;
      setAreas(lista);
      setSel((prev) => (prev ? lista.find((a) => a.id === prev.id) || null : null));
    } finally {
      setCargando(false);
    }
  }
  useEffect(() => {
    cargar(); // eslint-disable-next-line
  }, [institucion]);

  return (
    <div style={{ padding: "26px 30px" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 18 }}>
        <div>
          <div style={{ fontSize: 27, fontWeight: 800, letterSpacing: "-.5px" }}>Áreas</div>
          <div style={{ fontSize: 13, color: color.slate500, marginTop: 2 }}>{areas.length} áreas · {institucion?.nombre}</div>
        </div>
        <Button onClick={() => setNuevoArea(true)} style={{ display: "flex", alignItems: "center", gap: 8 }}><Icon name="plus" size={15} /> Nueva área</Button>
      </div>

      <Card style={{ overflow: "hidden", padding: 0 }}>
        {cargando ? (
          <Spinner />
        ) : (
          <Table
            rows={areas}
            onRowClick={(a) => setSel(a)}
            vacio="No hay áreas. Creá la primera."
            columns={[
              {
                key: "nombre", label: "Área",
                render: (a) => (
                  <div style={{ display: "flex", alignItems: "center", gap: 11 }}>
                    <div style={{ width: 34, height: 34, borderRadius: 9, background: color.accent50, color: color.accent, display: "flex", alignItems: "center", justifyContent: "center", flex: "none" }}><Icon name="cube" size={17} /></div>
                    <span style={{ fontWeight: 600 }}>{a.nombre}</span>
                  </div>
                ),
              },
              { key: "responsable", label: "Responsable", render: (a) => <span style={{ color: a.responsable ? color.slate700 : color.slate400 }}>{a.responsable || "—"}</span> },
              { key: "staff", label: "Staff", render: (a) => <Mono>{a.staff}</Mono> },
              { key: "sub", label: "Sub-áreas", render: (a) => <Mono>{a.subareas?.length || 0}</Mono> },
              {
                key: "acc", label: "",
                render: (a) => (
                  <div style={{ textAlign: "right" }}>
                    <button onClick={(e) => { e.stopPropagation(); setBorrar({ tipo: "area", item: a }); }} title="Eliminar" style={{ border: "none", background: "none", color: color.slate400, cursor: "pointer", display: "inline-flex" }}><Icon name="trash" size={15} /></button>
                  </div>
                ),
              },
            ]}
          />
        )}
      </Card>

      {/* Panel lateral con la ficha del área */}
      {sel && (
        <div onMouseDown={() => setSel(null)} style={{ position: "fixed", inset: 0, background: "rgba(16,24,40,.35)", zIndex: 40, display: "flex", justifyContent: "flex-end" }}>
          <div onMouseDown={(e) => e.stopPropagation()} style={{ width: 600, maxWidth: "100%", height: "100%", background: "#fff", boxShadow: "-8px 0 30px rgba(16,24,40,.18)", overflowY: "auto" }}>
            <div style={{ display: "flex", justifyContent: "flex-end", padding: "14px 18px 0" }}>
              <button onClick={() => setSel(null)} style={{ border: "none", background: "none", cursor: "pointer", color: color.slate400, display: "flex" }}><Icon name="x" size={18} /></button>
            </div>
            <div style={{ padding: "0 28px 28px" }}>
              <FichaArea key={sel.id} area={sel} institucionNombre={institucion?.nombre} onEditar={() => setEditar(true)} onChange={cargar} />
            </div>
          </div>
        </div>
      )}

      {nuevoArea && <AreaModal institucionId={institucion?.id} onClose={() => setNuevoArea(false)} onSaved={() => { setNuevoArea(false); cargar(); }} />}
      {editar && sel && <AreaModal area={sel} institucionId={institucion?.id} onClose={() => setEditar(false)} onSaved={() => { setEditar(false); cargar(); }} />}
      {borrar && <EliminarModal {...borrar} onClose={() => setBorrar(null)} onDeleted={() => { setBorrar(null); setSel(null); cargar(); }} />}
    </div>
  );
}

function FichaArea({ area, institucionNombre, onEditar, onChange }) {
  const [tab, setTab] = useState("datos");
  const [asignar, setAsignar] = useState(false);
  const [crearSub, setCrearSub] = useState(false);
  const [crearGrupo, setCrearGrupo] = useState(false);
  const [recargaGrupos, setRecargaGrupos] = useState(0);
  const [crearBox, setCrearBox] = useState(false);
  const [recargaBoxes, setRecargaBoxes] = useState(0);
  const tabs = [
    { k: "datos", l: "Datos" },
    { k: "staff", l: "Staff" },
    { k: "grupos", l: "Grupos" },
    { k: "boxes", l: "Boxes" },
    { k: "subareas", l: "Sub-áreas" },
  ];
  // Botón de acción contextual: cambia según la solapa activa.
  const accion = {
    staff: { label: "Asignar profesional", on: () => setAsignar(true) },
    grupos: { label: "Crear grupo", on: () => setCrearGrupo(true) },
    boxes: { label: "Crear box", on: () => setCrearBox(true) },
    subareas: { label: "Crear sub-área", on: () => setCrearSub(true) },
  }[tab];

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
        <span style={{ fontSize: 22, fontWeight: 800, letterSpacing: "-.4px" }}>{area.nombre}</span>
        <Badge tone="info">Área</Badge>
      </div>
      <div style={{ fontSize: 13.5, color: color.slate500, marginBottom: 16 }}>
        Responsable: <strong style={{ color: color.slate700 }}>{area.responsable || "—"}</strong>
      </div>
      <div style={{ display: "flex", gap: 10, marginBottom: 22 }}>
        <Button variant="secondary" onClick={onEditar}>Editar</Button>
        {accion && (
          <Button onClick={accion.on} style={{ display: "flex", alignItems: "center", gap: 7 }}>
            <Icon name="plus" size={15} /> {accion.label}
          </Button>
        )}
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
      {tab === "grupos" && <GruposTab area={area} recarga={recargaGrupos} />}
      {tab === "boxes" && <BoxesTab area={area} recarga={recargaBoxes} />}
      {tab === "subareas" && <SubareasTab area={area} onChange={onChange} />}

      {asignar && <AsignarModal area={area} onClose={() => setAsignar(false)} onSaved={() => { setAsignar(false); onChange(); }} />}
      {crearSub && <NuevaSubareaModal area={area} onClose={() => setCrearSub(false)} onSaved={() => { setCrearSub(false); onChange(); }} />}
      {crearGrupo && <GrupoModal area={area} onClose={() => setCrearGrupo(false)} onSaved={() => { setCrearGrupo(false); setRecargaGrupos((n) => n + 1); }} />}
      {crearBox && <BoxModal area={area} onClose={() => setCrearBox(false)} onSaved={() => { setCrearBox(false); setRecargaBoxes((n) => n + 1); }} />}
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
  const [quitando, setQuitando] = useState(null);
  // usuario_id → nombres de los grupos del área que integra.
  const [gruposPorUsuario, setGruposPorUsuario] = useState({});

  async function cargar() {
    const [membs, usuarios, grupos] = await Promise.all([
      api.get(`/membresias/?institucion=${area.institucion}`),
      api.get("/usuarios/"),
      api.get(`/grupos/?area=${area.id}`),
    ]);
    const usuMap = Object.fromEntries((usuarios.results || usuarios).map((u) => [u.id, u]));
    const porUsuario = {};
    (grupos.results || grupos).forEach((g) => {
      (g.integrantes || []).forEach((p) => {
        (porUsuario[p.id] = porUsuario[p.id] || []).push(g.nombre);
      });
    });
    setGruposPorUsuario(porUsuario);
    const lista = (membs.results || membs)
      .filter((m) => (m.areas || []).includes(area.id))
      .map((m) => ({ id: m.id, u: usuMap[m.usuario], rol: ROL_LABEL[m.rol] || m.rol, areas: m.areas || [] }));
    setFilas(lista);
  }
  useEffect(() => {
    cargar(); // eslint-disable-next-line
  }, [area.id]);

  // Quitar a una persona de esta área: si la membresía cubre otras áreas, solo
  // se le saca esta; si era la única, se elimina la membresía completa.
  async function quitar(f) {
    setQuitando(f.id);
    try {
      const resto = f.areas.filter((a) => a !== area.id);
      if (resto.length) await api.patch(`/membresias/${f.id}/`, { areas: resto });
      else await api.del(`/membresias/${f.id}/`);
      await cargar();
    } finally {
      setQuitando(null);
    }
  }

  if (filas === null) return <Spinner />;
  if (!filas.length) return <Card style={{ padding: 24, fontSize: 13.5, color: color.slate400 }}>Sin profesionales asignados a esta área.</Card>;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {filas.map((f) => {
        const grupos = gruposPorUsuario[f.u?.id] || [];
        return (
        <Card key={f.id} style={{ padding: "12px 16px", display: "flex", alignItems: "center", gap: 12 }}>
          <Avatar nombre={f.u?.nombre_completo || f.u?.email} i={f.id} size={32} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 14, fontWeight: 600 }}>{f.u?.nombre_completo || "—"}</div>
            <div style={{ fontSize: 12, color: color.slate500 }}>{f.u?.email}</div>
          </div>
          {grupos.length > 0 && (
            <Badge tone="info">
              <span title={`En ${grupos.length === 1 ? "el grupo" : "los grupos"}: ${grupos.join(", ")}`} style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
                <Icon name="users" size={12} />
                {grupos.length === 1 ? grupos[0] : `${grupos.length} grupos`}
              </span>
            </Badge>
          )}
          <Badge tone="neutral">{f.rol}</Badge>
          <button
            onClick={() => quitar(f)}
            disabled={quitando === f.id}
            title="Quitar de esta área"
            style={{ border: "none", background: "none", color: color.slate400, cursor: "pointer", fontSize: 12, padding: "4px 6px" }}
          >
            {quitando === f.id ? "…" : "quitar"}
          </button>
        </Card>
        );
      })}
    </div>
  );
}

// Personas asignadas al área (elegibles para integrar grupos): una entrada por
// usuario, derivada de las membresías cuya lista de áreas incluye esta área.
function useStaffDeArea(area) {
  const [staff, setStaff] = useState(null);
  useEffect(() => {
    (async () => {
      const [membs, usuarios] = await Promise.all([
        api.get(`/membresias/?institucion=${area.institucion}`),
        api.get("/usuarios/"),
      ]);
      const usuMap = Object.fromEntries((usuarios.results || usuarios).map((u) => [u.id, u]));
      const vistos = new Set();
      const lista = [];
      (membs.results || membs)
        .filter((m) => (m.areas || []).includes(area.id))
        .forEach((m) => {
          if (vistos.has(m.usuario)) return;
          vistos.add(m.usuario);
          if (usuMap[m.usuario]) lista.push(usuMap[m.usuario]);
        });
      setStaff(lista);
    })();
  }, [area.id]); // eslint-disable-line
  return staff;
}

function GruposTab({ area, recarga }) {
  const [grupos, setGrupos] = useState(null);
  const [gestion, setGestion] = useState(null); // grupo cuyos miembros se editan
  const [borrar, setBorrar] = useState(null);
  const staff = useStaffDeArea(area);

  async function cargar() {
    const d = await api.get(`/grupos/?area=${area.id}`);
    setGrupos(d.results || d);
  }
  useEffect(() => {
    cargar(); // eslint-disable-next-line
  }, [area.id, recarga]);

  if (grupos === null) return <Spinner />;
  if (!grupos.length)
    return <Card style={{ padding: 24, fontSize: 13.5, color: color.slate400 }}>Sin grupos. Usá «Crear grupo» para armar equipos con personas del área; luego se usan en los flujos.</Card>;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {grupos.map((g) => (
        <Card key={g.id} style={{ padding: "14px 16px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{ width: 34, height: 34, borderRadius: 9, background: color.accent50, color: color.accent, display: "flex", alignItems: "center", justifyContent: "center", flex: "none" }}><Icon name="users" size={17} /></div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 14, fontWeight: 600 }}>{g.nombre}</div>
              {g.descripcion && <div style={{ fontSize: 12, color: color.slate500 }}>{g.descripcion}</div>}
            </div>
            <span style={{ fontSize: 12.5, color: color.slate500 }}>{g.integrantes.length === 1 ? "1 integrante" : `${g.integrantes.length} integrantes`}</span>
            <Button variant="secondary" onClick={() => setGestion(g)}>Gestionar</Button>
            <button onClick={() => setBorrar(g)} title="Eliminar grupo" style={{ border: "none", background: "none", color: color.slate400, cursor: "pointer", display: "inline-flex" }}><Icon name="trash" size={15} /></button>
          </div>
          {g.integrantes.length > 0 && (
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 12 }}>
              {g.integrantes.map((p) => (
                <span key={p.id} style={{ display: "inline-flex", alignItems: "center", gap: 7, fontSize: 12.5, background: color.subtle, border: `1px solid ${color.border}`, borderRadius: 20, padding: "3px 11px 3px 3px" }}>
                  <Avatar nombre={p.nombre || p.email} i={p.id} size={22} /> {p.nombre || p.email}
                </span>
              ))}
            </div>
          )}
        </Card>
      ))}

      {gestion && <MiembrosModal grupo={gestion} staff={staff} grupos={grupos} onClose={() => setGestion(null)} onSaved={() => { setGestion(null); cargar(); }} />}
      {borrar && <EliminarGrupoModal grupo={borrar} onClose={() => setBorrar(null)} onDeleted={() => { setBorrar(null); cargar(); }} />}
    </div>
  );
}

function GrupoModal({ area, onClose, onSaved }) {
  const [f, setF] = useState({ nombre: "", descripcion: "" });
  const [guardando, setGuardando] = useState(false);
  const set = (k, v) => setF((p) => ({ ...p, [k]: v }));
  async function crear() {
    setGuardando(true);
    try {
      await api.post("/grupos/", { area: area.id, nombre: f.nombre.trim(), descripcion: f.descripcion });
      onSaved();
    } finally {
      setGuardando(false);
    }
  }
  return (
    <Modal title={`Nuevo grupo · ${area.nombre}`} onClose={onClose} footer={<><Button variant="secondary" onClick={onClose}>Cancelar</Button><Button disabled={guardando || !f.nombre.trim()} onClick={crear}>{guardando ? "…" : "Crear"}</Button></>}>
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <Field label="Nombre del grupo *"><Input value={f.nombre} onChange={(e) => set("nombre", e.target.value)} autoFocus placeholder="Guardia mañana" /></Field>
        <Field label="Descripción"><Textarea value={f.descripcion} onChange={(e) => set("descripcion", e.target.value)} placeholder="Para qué se usa este grupo…" /></Field>
      </div>
    </Modal>
  );
}

function MiembrosModal({ grupo, staff, grupos = [], onClose, onSaved }) {
  const [sel, setSel] = useState(() => new Set(grupo.integrantes.map((p) => p.id)));
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState(null);
  // usuario_id → nombres de OTROS grupos del área que ya integra.
  const otrosGrupos = useMemo(() => {
    const m = {};
    grupos.filter((g) => g.id !== grupo.id).forEach((g) => {
      (g.integrantes || []).forEach((p) => {
        (m[p.id] = m[p.id] || []).push(g.nombre);
      });
    });
    return m;
  }, [grupos, grupo.id]);
  function toggle(id) {
    setSel((prev) => {
      const n = new Set(prev);
      if (n.has(id)) n.delete(id); else n.add(id);
      return n;
    });
  }
  async function guardar() {
    setGuardando(true);
    setError(null);
    try {
      await api.patch(`/grupos/${grupo.id}/`, { miembros: [...sel] });
      onSaved();
    } catch (e) {
      setError(e?.data?.miembros || "No se pudieron guardar los cambios.");
      setGuardando(false);
    }
  }
  return (
    <Modal title={`Integrantes · ${grupo.nombre}`} onClose={onClose} footer={<><Button variant="secondary" onClick={onClose}>Cancelar</Button><Button disabled={guardando} onClick={guardar}>{guardando ? "…" : "Guardar"}</Button></>}>
      {staff === null ? (
        <Spinner />
      ) : staff.length === 0 ? (
        <div style={{ fontSize: 13.5, color: color.slate500 }}>No hay personas asignadas al área. Primero asigná profesionales en la pestaña «Staff».</div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 4, maxHeight: 360, overflow: "auto" }}>
          {staff.map((u) => {
            const checked = sel.has(u.id);
            const enOtros = otrosGrupos[u.id] || [];
            return (
              <label key={u.id} style={{ display: "flex", alignItems: "center", gap: 11, padding: "8px 10px", borderRadius: 9, cursor: "pointer", background: checked ? color.accent50 : "transparent" }}>
                <input type="checkbox" checked={checked} onChange={() => toggle(u.id)} />
                <Avatar nombre={u.nombre_completo || u.email} i={u.id} size={30} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 14, fontWeight: 600 }}>{u.nombre_completo || "—"}</div>
                  <div style={{ fontSize: 12, color: color.slate500 }}>{u.email}</div>
                </div>
                {enOtros.length > 0 && (
                  <Badge tone="amber">
                    <span title={`Ya está en: ${enOtros.join(", ")}`} style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
                      <Icon name="users" size={12} />
                      {enOtros.length === 1 ? "En otro grupo" : `En ${enOtros.length} grupos`}
                    </span>
                  </Badge>
                )}
              </label>
            );
          })}
        </div>
      )}
      {error && <div style={{ marginTop: 12, fontSize: 13, color: color.danger }}>{String(error)}</div>}
    </Modal>
  );
}

function EliminarGrupoModal({ grupo, onClose, onDeleted }) {
  const [borrando, setBorrando] = useState(false);
  async function eliminar() {
    setBorrando(true);
    try {
      await api.del(`/grupos/${grupo.id}/`);
      onDeleted();
    } finally {
      setBorrando(false);
    }
  }
  return (
    <Modal title="Eliminar grupo" onClose={onClose} footer={<><Button variant="secondary" onClick={onClose}>Cancelar</Button><Button variant="danger" disabled={borrando} onClick={eliminar}>{borrando ? "…" : "Eliminar"}</Button></>}>
      <div style={{ fontSize: 14, color: color.slate700 }}>¿Seguro que querés eliminar el grupo <strong>{grupo.nombre}</strong>? Esta acción no se puede deshacer.</div>
    </Modal>
  );
}

function BoxesTab({ area, recarga }) {
  const [boxes, setBoxes] = useState(null);
  const [borrar, setBorrar] = useState(null);

  async function cargar() {
    const d = await api.get(`/boxes/?area=${area.id}`);
    setBoxes(d.results || d);
  }
  useEffect(() => {
    cargar(); // eslint-disable-next-line
  }, [area.id, recarga]);

  if (boxes === null) return <Spinner />;
  if (!boxes.length)
    return <Card style={{ padding: 24, fontSize: 13.5, color: color.slate400 }}>Sin boxes. Usá «Crear box» para definir los consultorios; desde ellos se llama a la fila de espera.</Card>;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {boxes.map((b) => (
        <Card key={b.id} style={{ padding: "12px 16px", display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ width: 32, height: 32, borderRadius: 8, background: color.accent50, color: color.accent, display: "flex", alignItems: "center", justifyContent: "center", flex: "none" }}><Icon name="enter" size={16} /></div>
          <div style={{ flex: 1, fontSize: 14, fontWeight: 600 }}>{b.nombre}</div>
          {!b.activo && <Badge tone="gray">inactivo</Badge>}
          <button onClick={() => setBorrar(b)} title="Eliminar box" style={{ border: "none", background: "none", color: color.slate400, cursor: "pointer", display: "inline-flex" }}><Icon name="trash" size={15} /></button>
        </Card>
      ))}
      {borrar && <EliminarBoxModal box={borrar} onClose={() => setBorrar(null)} onDeleted={() => { setBorrar(null); cargar(); }} />}
    </div>
  );
}

function BoxModal({ area, onClose, onSaved }) {
  const [nombre, setNombre] = useState("");
  const [guardando, setGuardando] = useState(false);
  async function crear() {
    setGuardando(true);
    try {
      await api.post("/boxes/", { area: area.id, nombre: nombre.trim() });
      onSaved();
    } finally {
      setGuardando(false);
    }
  }
  return (
    <Modal title={`Nuevo box · ${area.nombre}`} onClose={onClose} footer={<><Button variant="secondary" onClick={onClose}>Cancelar</Button><Button disabled={guardando || !nombre.trim()} onClick={crear}>{guardando ? "…" : "Crear"}</Button></>}>
      <Field label="Nombre del box *"><Input value={nombre} onChange={(e) => setNombre(e.target.value)} autoFocus placeholder="Box 1" /></Field>
    </Modal>
  );
}

function EliminarBoxModal({ box, onClose, onDeleted }) {
  const [borrando, setBorrando] = useState(false);
  async function eliminar() {
    setBorrando(true);
    try {
      await api.del(`/boxes/${box.id}/`);
      onDeleted();
    } finally {
      setBorrando(false);
    }
  }
  return (
    <Modal title="Eliminar box" onClose={onClose} footer={<><Button variant="secondary" onClick={onClose}>Cancelar</Button><Button variant="danger" disabled={borrando} onClick={eliminar}>{borrando ? "…" : "Eliminar"}</Button></>}>
      <div style={{ fontSize: 14, color: color.slate700 }}>¿Seguro que querés eliminar <strong>{box.nombre}</strong>?</div>
    </Modal>
  );
}

function SubareasTab({ area, onChange }) {
  const [sel, setSel] = useState(null);
  const [flujos, setFlujos] = useState([]);
  useEffect(() => {
    api.get(`/flujos/?institucion=${area.institucion}`).then((d) => setFlujos(d.results || d));
  }, [area.institucion]);

  // Ficha de una sub-área seleccionada.
  if (sel) {
    const sub = (area.subareas || []).find((s) => s.id === sel.id) || sel;
    const vinculados = flujos.filter((f) => f.subarea === sub.id);
    return <SubareaFicha sub={sub} flujos={vinculados} onBack={() => setSel(null)} onChange={onChange} />;
  }

  if (!area.subareas?.length)
    return <div style={{ fontSize: 13.5, color: color.slate400 }}>Sin sub-áreas. Usá «Crear sub-área». (Una sub-área no contiene sub-áreas.)</div>;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {area.subareas.map((s) => {
        const n = flujos.filter((f) => f.subarea === s.id).length;
        return (
          <Card
            key={s.id}
            onClick={() => setSel(s)}
            style={{ padding: "12px 16px", display: "flex", alignItems: "center", gap: 12, cursor: "pointer" }}
          >
            <div style={{ width: 30, height: 30, borderRadius: 8, background: color.subtle, color: color.slate500, display: "flex", alignItems: "center", justifyContent: "center", flex: "none" }}><Icon name="cube" size={15} /></div>
            <div style={{ flex: 1, fontSize: 14, fontWeight: 600 }}>{s.nombre}</div>
            <span style={{ fontSize: 12.5, color: color.slate500 }}>{n === 1 ? "1 flujo" : `${n} flujos`}</span>
            <Icon name="back" size={14} style={{ transform: "rotate(180deg)", color: color.slate400 }} />
          </Card>
        );
      })}
    </div>
  );
}

function SubareaFicha({ sub, flujos, onBack, onChange }) {
  const [editando, setEditando] = useState(false);
  const [nombre, setNombre] = useState(sub.nombre);
  const [confirmar, setConfirmar] = useState(false);
  const [trabajando, setTrabajando] = useState(false);

  async function renombrar() {
    if (!nombre.trim() || nombre.trim() === sub.nombre) { setEditando(false); return; }
    setTrabajando(true);
    try {
      await api.patch(`/subareas/${sub.id}/`, { nombre: nombre.trim() });
      setEditando(false);
      onChange();
    } finally {
      setTrabajando(false);
    }
  }
  async function eliminar() {
    setTrabajando(true);
    try {
      await api.del(`/subareas/${sub.id}/`);
      onBack();
      onChange();
    } finally {
      setTrabajando(false);
    }
  }

  return (
    <div>
      <button onClick={onBack} style={{ border: "none", background: "none", color: color.slate500, cursor: "pointer", fontSize: 13, display: "flex", alignItems: "center", gap: 6, marginBottom: 14, padding: 0 }}>
        <Icon name="back" size={14} /> Sub-áreas
      </button>

      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
        {editando ? (
          <>
            <Input value={nombre} onChange={(e) => setNombre(e.target.value)} autoFocus style={{ maxWidth: 280 }} />
            <Button disabled={trabajando} onClick={renombrar}>Guardar</Button>
            <Button variant="secondary" onClick={() => { setNombre(sub.nombre); setEditando(false); }}>Cancelar</Button>
          </>
        ) : (
          <>
            <span style={{ fontSize: 19, fontWeight: 800, letterSpacing: "-.3px" }}>{sub.nombre}</span>
            <Badge tone="neutral">Sub-área</Badge>
            <button onClick={() => setEditando(true)} style={{ border: "none", background: "none", color: color.accent, cursor: "pointer", fontSize: 13 }}>Renombrar</button>
          </>
        )}
      </div>

      <div style={{ fontSize: 13, fontWeight: 700, color: color.slate600, marginBottom: 10 }}>Flujos vinculados <span style={{ color: color.slate400, fontWeight: 500 }}>· {flujos.length}</span></div>
      {flujos.length === 0 ? (
        <Card style={{ padding: 18, fontSize: 13, color: color.slate400 }}>Ningún flujo usa esta sub-área todavía.</Card>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {flujos.map((f) => (
            <Card key={f.id} style={{ padding: "11px 14px", display: "flex", alignItems: "center", gap: 10 }}>
              <Icon name="workflow" size={15} style={{ color: color.accent }} />
              <span style={{ fontSize: 13.5, fontWeight: 600 }}>{f.titulo}</span>
            </Card>
          ))}
        </div>
      )}

      <div style={{ marginTop: 22, borderTop: `1px solid ${color.border}`, paddingTop: 16 }}>
        {confirmar ? (
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span style={{ fontSize: 13, color: color.slate700 }}>¿Eliminar «{sub.nombre}»?</span>
            <Button variant="danger" disabled={trabajando} onClick={eliminar}>{trabajando ? "…" : "Sí, eliminar"}</Button>
            <Button variant="secondary" onClick={() => setConfirmar(false)}>No</Button>
          </div>
        ) : (
          <button onClick={() => setConfirmar(true)} style={{ border: "none", background: "none", color: color.danger, cursor: "pointer", fontSize: 13, padding: 0 }}>Eliminar sub-área</button>
        )}
      </div>
    </div>
  );
}

function NuevaSubareaModal({ area, onClose, onSaved }) {
  const [nombre, setNombre] = useState("");
  const [guardando, setGuardando] = useState(false);
  async function crear() {
    setGuardando(true);
    try {
      await api.post("/subareas/", { area: area.id, nombre: nombre.trim() });
      onSaved();
    } finally {
      setGuardando(false);
    }
  }
  return (
    <Modal title={`Nueva sub-área · ${area.nombre}`} onClose={onClose} footer={<><Button variant="secondary" onClick={onClose}>Cancelar</Button><Button disabled={guardando || !nombre.trim()} onClick={crear}>{guardando ? "…" : "Crear"}</Button></>}>
      <Field label="Nombre de la sub-área *"><Input value={nombre} onChange={(e) => setNombre(e.target.value)} autoFocus placeholder="Hemodinamia" /></Field>
    </Modal>
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

function EliminarModal({ tipo, item, onClose, onDeleted }) {
  const [borrando, setBorrando] = useState(false);
  const [error, setError] = useState(null);
  const esArea = tipo === "area";
  async function eliminar() {
    setBorrando(true);
    setError(null);
    try {
      await api.del(`/${esArea ? "areas" : "subareas"}/${item.id}/`);
      onDeleted();
    } catch (e) {
      setError(e?.data?.detail || "No se pudo eliminar. Puede tener elementos asociados.");
      setBorrando(false);
    }
  }
  return (
    <Modal
      title={esArea ? "Eliminar área" : "Eliminar sub-área"}
      onClose={onClose}
      footer={<><Button variant="secondary" onClick={onClose}>Cancelar</Button><Button variant="danger" disabled={borrando} onClick={eliminar}>{borrando ? "…" : "Eliminar"}</Button></>}
    >
      <div style={{ fontSize: 14, color: color.slate700 }}>
        ¿Seguro que querés eliminar <strong>{item.nombre}</strong>?
        {esArea && <> Se eliminarán también sus sub-áreas.</>} Esta acción no se puede deshacer.
      </div>
      {error && <div style={{ marginTop: 12, fontSize: 13, color: color.danger }}>{error}</div>}
    </Modal>
  );
}

// Funciones operativas que se pueden asignar a un área.
const FUNCIONES = [
  { value: "administrativo", label: "Administrativo" },
  { value: "medico", label: "Médico / profesional" },
];

function AsignarModal({ area, onClose, onSaved }) {
  const [usuarios, setUsuarios] = useState([]);
  const [usuarioId, setUsuarioId] = useState("");
  const [funcion, setFuncion] = useState("administrativo");
  const [guardando, setGuardando] = useState(false);

  useEffect(() => {
    api.get("/usuarios/").then((d) => {
      const lista = (d.results || d).filter((u) => !u.is_superuser);
      setUsuarios(lista);
      if (lista[0]) setUsuarioId(String(lista[0].id));
    });
  }, []);

  async function asignar() {
    if (!usuarioId) return;
    setGuardando(true);
    try {
      // ¿Ya tiene una membresía con esa función en la institución?
      const ms = await api.get(`/membresias/?usuario=${usuarioId}&institucion=${area.institucion}&rol=${funcion}`);
      const existente = (ms.results || ms)[0];
      if (existente) {
        if (!(existente.areas || []).includes(area.id)) {
          await api.patch(`/membresias/${existente.id}/`, { areas: [...(existente.areas || []), area.id] });
        }
      } else {
        await api.post("/membresias/", { usuario: Number(usuarioId), institucion: area.institucion, rol: funcion, areas: [area.id] });
      }
      onSaved();
    } finally {
      setGuardando(false);
    }
  }

  return (
    <Modal title={`Asignar profesional a ${area.nombre}`} onClose={onClose} footer={<><Button variant="secondary" onClick={onClose}>Cancelar</Button><Button disabled={guardando || !usuarioId} onClick={asignar}>{guardando ? "…" : "Asignar"}</Button></>}>
      {usuarios.length === 0 ? (
        <div style={{ fontSize: 13.5, color: color.slate500 }}>No hay usuarios para asignar. Creá usuarios desde el directorio (Usuarios).</div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <Field label="Persona">
            <Select value={usuarioId} onChange={(e) => setUsuarioId(e.target.value)}>
              {usuarios.map((u) => <option key={u.id} value={u.id}>{u.nombre_completo || u.email}</option>)}
            </Select>
          </Field>
          <Field label="Función en esta área">
            <Select value={funcion} onChange={(e) => setFuncion(e.target.value)}>
              {FUNCIONES.map((f) => <option key={f.value} value={f.value}>{f.label}</option>)}
            </Select>
          </Field>
          <div style={{ fontSize: 12, color: color.slate400 }}>
            El médico podrá registrar atenciones (firmar en la historia clínica); el administrativo opera el resto del proceso.
          </div>
        </div>
      )}
    </Modal>
  );
}
