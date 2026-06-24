import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { useInstitucion } from "../../auth/InstitutionContext";
import { PageHeader } from "../../components/Shell";
import { Badge, Button, Card, EmptyState, Field, Input, Modal, Select, Spinner, Textarea } from "../../components/ui";
import { Icon } from "../../components/icons";
import { color } from "../../theme";

// Color del punto por tipo de campo (calcado del prototipo).
const TIPO_DOT = { texto_corto: "#3949C0", texto_largo: "#1F8A5B", fecha: "#0E8893", seleccion_unica: "#A96A12", archivo: "#9A3DB8" };
const ORIGEN = {
  historia_clinica: { label: "Historia clínica", bg: "#ECEEFB", fg: "#2D3A9E" },
  legajo_ciudadano: { label: "Legajo ciudadano", bg: "#E2F6F9", fg: "#0C7C8E" },
};

const TIPOS = [
  { value: "texto_corto", label: "Texto corto" },
  { value: "texto_largo", label: "Texto largo" },
  { value: "fecha", label: "Fecha" },
  { value: "seleccion_unica", label: "Selección única" },
  { value: "archivo", label: "Archivo adjunto" },
];

export default function Formularios() {
  const { institucion } = useInstitucion();
  const [forms, setForms] = useState([]);
  const [sel, setSel] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [nuevo, setNuevo] = useState(false);

  async function cargar(seleccionar) {
    if (!institucion) return;
    setCargando(true);
    try {
      const d = await api.get(`/formularios/?institucion=${institucion.id}`);
      const lista = d.results || d;
      setForms(lista);
      setSel((prev) => lista.find((f) => f.id === (seleccionar ?? prev?.id)) || lista[0] || null);
    } finally {
      setCargando(false);
    }
  }
  useEffect(() => {
    cargar(); // eslint-disable-next-line
  }, [institucion]);

  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <PageHeader subtitle="Definí los campos que los flujos piden en cada paso." right={<Button onClick={() => setNuevo(true)}>+ Nuevo formulario</Button>} />
      <div style={{ display: "flex", flex: 1, minHeight: 0, marginTop: 12 }}>
        <div style={{ width: 300, borderRight: `1px solid ${color.border}`, background: "#fff", overflow: "auto", flex: "none" }}>
          {cargando ? <Spinner /> : forms.length === 0 ? <EmptyState title="Sin formularios" /> : forms.map((f) => (
            <div key={f.id} onClick={() => setSel(f)} style={{ padding: "13px 18px", cursor: "pointer", borderBottom: `1px solid ${color.divider}`, background: sel?.id === f.id ? color.accent50 : "transparent" }}>
              <div style={{ fontSize: 13.5, fontWeight: 600 }}>{f.titulo}</div>
              <div style={{ fontSize: 12, color: color.slate500 }}>{f.campos?.length || 0} campos</div>
            </div>
          ))}
        </div>
        <div style={{ flex: 1, overflow: "auto", padding: 32 }}>
          {sel ? <FormDetalle key={sel.id} form={sel} onChange={() => cargar(sel.id)} /> : <EmptyState title="Elegí un formulario" />}
        </div>
      </div>
      {nuevo && <NuevoFormModal institucionId={institucion?.id} onClose={() => setNuevo(false)} onCreated={(id) => { setNuevo(false); cargar(id); }} />}
    </div>
  );
}

function FormDetalle({ form, onChange }) {
  const [agregar, setAgregar] = useState(false);
  const campos = form.campos || [];
  async function borrarCampo(id) {
    await api.del(`/campos/${id}/`);
    onChange();
  }
  return (
    <div>
      {/* Cabecera */}
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 20 }}>
        <div style={{ width: 44, height: 44, borderRadius: 11, background: color.accent50, color: color.accent, display: "flex", alignItems: "center", justifyContent: "center", flex: "none" }}>
          <Icon name="form" size={22} />
        </div>
        <div>
          <div style={{ fontSize: 18, fontWeight: 700 }}>{form.titulo}</div>
          <div style={{ fontSize: 12.5, color: color.slate500 }}>Formulario de la institución · {campos.length} campos</div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, alignItems: "start" }}>
        {/* Campos */}
        <Card style={{ padding: 16 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
            <div style={{ fontSize: 14, fontWeight: 700 }}>Campos <span style={{ color: color.slate400, fontWeight: 500 }}>· {campos.length}</span></div>
            <Button variant="secondary" onClick={() => setAgregar(true)} style={{ height: 32, padding: "0 12px" }}>+ Agregar</Button>
          </div>
          {campos.length === 0 ? (
            <EmptyState title="Sin campos" hint="Agregá el primero." />
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {campos.map((c) => {
                const o = ORIGEN[c.origen];
                return (
                  <div key={c.id} style={{ display: "flex", alignItems: "center", gap: 11, padding: "11px 12px", border: `1px solid ${color.border}`, borderRadius: 10 }}>
                    <span style={{ width: 9, height: 9, borderRadius: 3, background: TIPO_DOT[c.tipo] || color.slate400, flex: "none" }} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 13.5, fontWeight: 600 }}>{c.label} {c.requerido && <span style={{ color: "#B42318" }}>*</span>}</div>
                      <div style={{ fontSize: 11.5, color: color.slate500, display: "flex", alignItems: "center", gap: 6, marginTop: 2 }}>
                        {c.tipo_display}
                        {o && <span style={{ fontSize: 10, fontWeight: 700, padding: "1px 7px", borderRadius: 5, background: o.bg, color: o.fg }}>{o.label}</span>}
                      </div>
                    </div>
                    <button onClick={() => borrarCampo(c.id)} style={{ border: "none", background: "none", color: "#B42318", cursor: "pointer", fontSize: 11.5 }}>quitar</button>
                  </div>
                );
              })}
            </div>
          )}
        </Card>

        {/* Vista previa en vivo */}
        <div>
          <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 12 }}>
            <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#1F8A5B" }} />
            <span style={{ fontSize: 14, fontWeight: 700 }}>Vista previa en vivo</span>
            <span style={{ fontSize: 12, color: color.slate400 }}>así lo verá el administrativo</span>
          </div>
          <Card style={{ padding: 22 }}>
            <div style={{ fontSize: 16, fontWeight: 700 }}>{form.titulo}</div>
            <div style={{ fontSize: 13, color: color.slate500, marginBottom: 16 }}>Completá los campos para continuar.</div>
            {campos.length === 0 ? (
              <div style={{ fontSize: 13, color: color.slate400 }}>Sin campos para previsualizar.</div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                {campos.map((c) => (
                  <div key={c.id}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: color.slate600, marginBottom: 6 }}>{c.label} {c.requerido && <span style={{ color: "#B42318" }}>*</span>}</div>
                    <PreviewInput campo={c} />
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      </div>

      {agregar && <CampoModal formularioId={form.id} orden={campos.length} onClose={() => setAgregar(false)} onSaved={() => { setAgregar(false); onChange(); }} />}
    </div>
  );
}

function PreviewInput({ campo }) {
  const dis = { pointerEvents: "none", background: color.subtle };
  if (campo.tipo === "texto_largo") return <Textarea placeholder="Escribí aquí…" readOnly style={dis} />;
  if (campo.tipo === "fecha") return <Input type="date" readOnly style={dis} />;
  if (campo.tipo === "seleccion_unica")
    return (
      <Select readOnly style={dis}>
        <option>Seleccionar…</option>
        {(campo.opciones || []).map((o) => <option key={o}>{o}</option>)}
      </Select>
    );
  if (campo.tipo === "archivo") return <Input placeholder="Adjuntar archivo…" readOnly style={dis} />;
  return <Input placeholder="Ingresá el dato" readOnly style={dis} />;
}

function CampoModal({ formularioId, orden, onClose, onSaved }) {
  const [f, setF] = useState({ label: "", tipo: "texto_corto", requerido: false, opciones: "" });
  const [guardando, setGuardando] = useState(false);
  const set = (k, v) => setF((p) => ({ ...p, [k]: v }));
  async function guardar() {
    setGuardando(true);
    try {
      await api.post("/campos/", {
        formulario: formularioId,
        label: f.label,
        tipo: f.tipo,
        requerido: f.requerido,
        opciones: f.tipo === "seleccion_unica" ? f.opciones.split(",").map((s) => s.trim()).filter(Boolean) : [],
        orden,
      });
      onSaved();
    } finally {
      setGuardando(false);
    }
  }
  return (
    <Modal title="Nuevo campo" onClose={onClose} footer={<><Button variant="secondary" onClick={onClose}>Cancelar</Button><Button disabled={guardando || !f.label} onClick={guardar}>{guardando ? "…" : "Agregar"}</Button></>}>
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <Field label="Etiqueta *"><Input value={f.label} onChange={(e) => set("label", e.target.value)} autoFocus placeholder="Nombre, Obra social…" /></Field>
        <Field label="Tipo"><Select value={f.tipo} onChange={(e) => set("tipo", e.target.value)}>{TIPOS.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}</Select></Field>
        {f.tipo === "seleccion_unica" && (
          <Field label="Opciones (separadas por coma)"><Input value={f.opciones} onChange={(e) => set("opciones", e.target.value)} placeholder="OSDE, PAMI, Particular" /></Field>
        )}
        <label style={{ display: "flex", alignItems: "center", gap: 9, fontSize: 13.5 }}>
          <input type="checkbox" checked={f.requerido} onChange={(e) => set("requerido", e.target.checked)} /> Requerido
        </label>
      </div>
    </Modal>
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
    <Modal title="Nuevo formulario" onClose={onClose} footer={<><Button variant="secondary" onClick={onClose}>Cancelar</Button><Button disabled={guardando || !titulo} onClick={crear}>{guardando ? "…" : "Crear"}</Button></>}>
      <Field label="Título *"><Input value={titulo} onChange={(e) => setTitulo(e.target.value)} autoFocus placeholder="Datos del paciente" /></Field>
    </Modal>
  );
}
