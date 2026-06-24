import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { PageHeader } from "../../components/Shell";
import { Badge, Button, Card, Field, Input, Modal, Spinner, Table } from "../../components/ui";

export default function Instituciones() {
  const [items, setItems] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [editando, setEditando] = useState(null); // objeto o {} para nuevo

  async function cargar() {
    setCargando(true);
    try {
      const d = await api.get("/instituciones/");
      setItems(d.results || d);
    } finally {
      setCargando(false);
    }
  }
  useEffect(() => {
    cargar();
  }, []);

  return (
    <>
      <PageHeader
        title="Instituciones"
        subtitle="Organizaciones autocontenidas del sistema."
        right={<Button onClick={() => setEditando({})}>+ Nueva institución</Button>}
      />
      <div style={{ padding: 32 }}>
        <Card style={{ overflow: "hidden" }}>
          {cargando ? (
            <Spinner />
          ) : (
            <Table
              rows={items}
              onRowClick={(r) => setEditando(r)}
              vacio="No hay instituciones"
              columns={[
                { key: "nombre", label: "Nombre", render: (r) => <span style={{ fontWeight: 600 }}>{r.nombre}</span> },
                { key: "cuit", label: "CUIT", render: (r) => r.cuit || "—" },
                { key: "areas_count", label: "Áreas" },
                { key: "activa", label: "Estado", render: (r) => <Badge tone={r.activa ? "green" : "gray"}>{r.activa ? "Activa" : "Inactiva"}</Badge> },
              ]}
            />
          )}
        </Card>
      </div>

      {editando && <InstitucionModal inst={editando} onClose={() => setEditando(null)} onSaved={() => { setEditando(null); cargar(); }} />}
    </>
  );
}

function InstitucionModal({ inst, onClose, onSaved }) {
  const esNuevo = !inst.id;
  const [form, setForm] = useState({ nombre: inst.nombre || "", cuit: inst.cuit || "", direccion: inst.direccion || "", activa: inst.activa ?? true });
  const [guardando, setGuardando] = useState(false);
  const set = (k, v) => setForm((p) => ({ ...p, [k]: v }));

  async function guardar() {
    setGuardando(true);
    try {
      if (esNuevo) await api.post("/instituciones/", form);
      else await api.patch(`/instituciones/${inst.id}/`, form);
      onSaved();
    } finally {
      setGuardando(false);
    }
  }

  return (
    <Modal
      title={esNuevo ? "Nueva institución" : "Editar institución"}
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancelar</Button>
          <Button disabled={guardando || !form.nombre} onClick={guardar}>{guardando ? "Guardando…" : "Guardar"}</Button>
        </>
      }
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <Field label="Nombre *"><Input value={form.nombre} onChange={(e) => set("nombre", e.target.value)} autoFocus /></Field>
        <Field label="CUIT"><Input value={form.cuit} onChange={(e) => set("cuit", e.target.value)} placeholder="30-12345678-9" /></Field>
        <Field label="Dirección"><Input value={form.direccion} onChange={(e) => set("direccion", e.target.value)} /></Field>
        <label style={{ display: "flex", alignItems: "center", gap: 9, fontSize: 13.5 }}>
          <input type="checkbox" checked={form.activa} onChange={(e) => set("activa", e.target.checked)} /> Activa
        </label>
      </div>
    </Modal>
  );
}
