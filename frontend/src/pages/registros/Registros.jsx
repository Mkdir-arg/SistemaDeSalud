import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../../api/client";
import { useInstitucion } from "../../auth/InstitutionContext";
import { Avatar, Badge, Button, Card, Field, Input, Modal, Mono, Spinner, Table } from "../../components/ui";
import { color } from "../../theme";

// Lista de historias clínicas (tabla). El detalle vive en /historia/:id.
export default function Registros() {
  const { institucion } = useInstitucion();
  const navigate = useNavigate();
  const [ciudadanos, setCiudadanos] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [busca, setBusca] = useState("");
  const [params] = useSearchParams();
  const [nuevo, setNuevo] = useState(params.get("nuevo") === "1"); // abrir alta directo desde "Accesos rápidos"

  async function cargar() {
    if (!institucion) return;
    setCargando(true);
    try {
      const d = await api.get(`/ciudadanos/?institucion=${institucion.id}`);
      setCiudadanos(d.results || d);
    } finally {
      setCargando(false);
    }
  }
  useEffect(() => {
    cargar(); // eslint-disable-next-line
  }, [institucion]);

  const filtrados = ciudadanos.filter((c) =>
    `${c.nombre} ${c.apellido} ${c.documento}`.toLowerCase().includes(busca.toLowerCase())
  );

  return (
    <div style={{ padding: "26px 30px" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16, marginBottom: 18, flexWrap: "wrap" }}>
        <div>
          <div style={{ fontSize: 22, fontWeight: 800, letterSpacing: "-.4px" }}>Historias clínicas</div>
          <div style={{ fontSize: 12.5, color: color.slate500 }}>{ciudadanos.length} pacientes con registro</div>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <div style={{ width: 280 }}>
            <Input placeholder="Buscar por nombre o documento…" value={busca} onChange={(e) => setBusca(e.target.value)} />
          </div>
          <Button style={{ whiteSpace: "nowrap" }} onClick={() => setNuevo(true)}>+ Crear registro</Button>
        </div>
      </div>

      <Card style={{ overflow: "hidden", padding: 0 }}>
        {cargando ? (
          <Spinner />
        ) : (
          <Table
            rows={filtrados}
            onRowClick={(c) => navigate(`/historia/${c.id}`)}
            vacio="Sin pacientes"
            columns={[
              {
                key: "paciente", label: "Paciente",
                render: (c) => (
                  <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                    <Avatar nombre={`${c.nombre} ${c.apellido}`} i={c.id} size={38} />
                    <div>
                      <div style={{ fontWeight: 600 }}>{c.nombre} {c.apellido}</div>
                      <div style={{ fontSize: 12, color: color.slate500 }}>
                        {c.documento ? <>DNI {c.documento}</> : c.codigo}{c.fecha_nacimiento ? ` · ${new Date(c.fecha_nacimiento).toLocaleDateString("es-AR")}` : ""}
                      </div>
                    </div>
                  </div>
                ),
              },
              { key: "obra_social", label: "Obra social", render: (c) => c.obra_social || "—" },
              {
                key: "cond", label: "Condiciones / alergias",
                render: (c) => (
                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                    {c.condiciones && <Badge tone="amber">{c.condiciones}</Badge>}
                    {c.alergias && <Badge tone="error">⚠ {c.alergias}</Badge>}
                    {!c.condiciones && !c.alergias && <span style={{ color: color.slate400 }}>—</span>}
                  </div>
                ),
              },
              { key: "entradas", label: "Entradas", render: (c) => <Mono>{c.entradas}</Mono> },
              { key: "ultima", label: "Última", render: (c) => (c.ultima ? new Date(c.ultima).toLocaleDateString("es-AR") : "—") },
            ]}
          />
        )}
      </Card>

      {nuevo && <NuevoPacienteModal institucionId={institucion?.id} onClose={() => setNuevo(false)} onSaved={(id) => { setNuevo(false); id ? navigate(`/historia/${id}`) : cargar(); }} />}
    </div>
  );
}

function NuevoPacienteModal({ institucionId, onClose, onSaved }) {
  const [f, setF] = useState({ nombre: "", apellido: "", documento: "", fecha_nacimiento: "", obra_social: "" });
  const [guardando, setGuardando] = useState(false);
  const set = (k, v) => setF((p) => ({ ...p, [k]: v }));
  async function crear() {
    setGuardando(true);
    try {
      const c = await api.post("/ciudadanos/", { institucion: institucionId, ...f, fecha_nacimiento: f.fecha_nacimiento || null });
      onSaved(c.id);
    } finally {
      setGuardando(false);
    }
  }
  return (
    <Modal title="Nuevo registro de paciente" onClose={onClose} footer={<>
      <Button variant="secondary" onClick={onClose}>Cancelar</Button>
      <Button disabled={guardando || !f.nombre} onClick={crear}>{guardando ? "Creando…" : "Crear"}</Button>
    </>}>
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <div style={{ display: "flex", gap: 12 }}>
          <Field label="Nombre *"><Input value={f.nombre} onChange={(e) => set("nombre", e.target.value)} autoFocus /></Field>
          <Field label="Apellido"><Input value={f.apellido} onChange={(e) => set("apellido", e.target.value)} /></Field>
        </div>
        <Field label="Documento"><Input value={f.documento} onChange={(e) => set("documento", e.target.value)} placeholder="27418305" /></Field>
        <Field label="Fecha de nacimiento"><Input type="date" value={f.fecha_nacimiento} onChange={(e) => set("fecha_nacimiento", e.target.value)} /></Field>
        <Field label="Obra social"><Input value={f.obra_social} onChange={(e) => set("obra_social", e.target.value)} placeholder="OSDE" /></Field>
      </div>
    </Modal>
  );
}
