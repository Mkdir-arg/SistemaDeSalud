import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../api/client";
import { useInstitucion } from "../../auth/InstitutionContext";
import { Button, Card, Field, Input, Modal, Mono, Spinner, Table } from "../../components/ui";
import { Icon } from "../../components/icons";
import { color } from "../../theme";

// Lista de formularios (tabla). El constructor vive en /formularios/:id.
export default function Formularios() {
  const { institucion } = useInstitucion();
  const navigate = useNavigate();
  const [forms, setForms] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [nuevo, setNuevo] = useState(false);

  async function cargar() {
    if (!institucion) return;
    setCargando(true);
    try {
      const d = await api.get(`/formularios/?institucion=${institucion.id}`);
      setForms(d.results || d);
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
          <div style={{ fontSize: 27, fontWeight: 800, letterSpacing: "-.5px" }}>Formularios</div>
          <div style={{ fontSize: 13, color: color.slate500, marginTop: 2 }}>Definí los campos que los flujos piden en cada paso.</div>
        </div>
        <Button onClick={() => setNuevo(true)} style={{ display: "flex", alignItems: "center", gap: 8 }}><Icon name="plus" size={15} /> Nuevo formulario</Button>
      </div>

      <Card style={{ overflow: "hidden", padding: 0 }}>
        {cargando ? (
          <Spinner />
        ) : (
          <Table
            rows={forms}
            onRowClick={(f) => navigate(`/formularios/${f.id}`)}
            vacio="No hay formularios. Creá el primero."
            columns={[
              {
                key: "titulo", label: "Formulario",
                render: (f) => (
                  <div style={{ display: "flex", alignItems: "center", gap: 11 }}>
                    <div style={{ width: 34, height: 34, borderRadius: 9, background: color.accent50, color: color.accent, display: "flex", alignItems: "center", justifyContent: "center", flex: "none" }}><Icon name="form" size={17} /></div>
                    <span style={{ fontWeight: 600 }}>{f.titulo}</span>
                  </div>
                ),
              },
              { key: "campos", label: "Campos", render: (f) => <Mono>{f.campos?.length || 0}</Mono> },
              { key: "vinculados", label: "Vinculados", render: (f) => <Mono>{(f.campos || []).filter((c) => c.origen).length}</Mono> },
              { key: "descripcion", label: "Descripción", render: (f) => <span style={{ color: color.slate500 }}>{f.descripcion || "—"}</span> },
            ]}
          />
        )}
      </Card>

      {nuevo && <NuevoFormModal institucionId={institucion?.id} onClose={() => setNuevo(false)} onCreated={(id) => navigate(`/formularios/${id}`)} />}
    </div>
  );
}

function NuevoFormModal({ institucionId, onClose, onCreated }) {
  const [titulo, setTitulo] = useState("");
  const [guardando, setGuardando] = useState(false);
  async function crear() {
    setGuardando(true);
    try {
      const f = await api.post("/formularios/", { institucion: institucionId, titulo });
      onCreated(f.id);
    } finally {
      setGuardando(false);
    }
  }
  return (
    <Modal title="Nuevo formulario" onClose={onClose} footer={<><Button variant="secondary" onClick={onClose}>Cancelar</Button><Button disabled={guardando || !titulo} onClick={crear}>{guardando ? "…" : "Crear y diseñar"}</Button></>}>
      <Field label="Título *"><Input value={titulo} onChange={(e) => setTitulo(e.target.value)} autoFocus placeholder="Datos del paciente" /></Field>
    </Modal>
  );
}
