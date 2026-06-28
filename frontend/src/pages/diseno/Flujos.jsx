import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../api/client";
import { useInstitucion } from "../../auth/InstitutionContext";
import { PageHeader } from "../../components/Shell";
import { Badge, Button, Card, EmptyState, Field, Input, Modal, Select, Spinner } from "../../components/ui";
import { Icon } from "../../components/icons";
import { badgeTone, color, estadoVersion, font, radius, type } from "../../theme";

const TABS = [
  { key: "todos", label: "Todos" },
  { key: "publicada", label: "Publicado" },
  { key: "borrador", label: "Borrador" },
  { key: "archivada", label: "Archivado" },
];

const COLS = "minmax(160px,1.7fr) 150px 120px 56px 90px 110px 70px";

// Plantillas de arranque: en vez de un lienzo en blanco, el flujo nuevo puede
// nacer con un esqueleto de nodos+conexiones listo para editar. Las claves `k`
// se remapean a los ids reales tras crear cada nodo.
const PLANTILLAS = [
  { key: "vacio", nombre: "En blanco", desc: "Solo el nodo Inicio.", nodos: [{ k: "ini", tipo: "inicio", titulo: "Inicio", x: 80, y: 220 }], conexiones: [] },
  {
    key: "ingreso", nombre: "Ingreso de paciente", desc: "Inicio → Formulario de datos → Cierre.",
    nodos: [
      { k: "ini", tipo: "inicio", titulo: "Inicio", x: 80, y: 220 },
      { k: "form", tipo: "form", titulo: "Datos del paciente", x: 360, y: 220 },
      { k: "fin", tipo: "fin", titulo: "Cierre", x: 640, y: 220 },
    ],
    conexiones: [["ini", "form"], ["form", "fin"]],
  },
  {
    key: "derivacion", nombre: "Derivación a especialidad", desc: "Inicio → Evaluación → Decisión → Derivar / Cierre.",
    nodos: [
      { k: "ini", tipo: "inicio", titulo: "Inicio", x: 60, y: 260 },
      { k: "form", tipo: "form", titulo: "Evaluación", x: 320, y: 260 },
      { k: "dec", tipo: "decision", titulo: "¿Requiere especialista?", x: 580, y: 260 },
      { k: "der", tipo: "derivar", titulo: "Derivar a especialidad", x: 860, y: 160 },
      { k: "fin", tipo: "fin", titulo: "Cierre", x: 860, y: 360 },
    ],
    conexiones: [["ini", "form"], ["form", "dec"], ["dec", "der"], ["dec", "fin"]],
  },
  {
    key: "fila", nombre: "Atención con fila de espera", desc: "Inicio → Atención (con fila) → Cierre.",
    nodos: [
      { k: "ini", tipo: "inicio", titulo: "Inicio", x: 80, y: 220 },
      { k: "at", tipo: "atencion", titulo: "Atención", x: 360, y: 220 },
      { k: "fin", tipo: "fin", titulo: "Cierre", x: 640, y: 220 },
    ],
    conexiones: [["ini", "at"], ["at", "fin"]],
  },
];

export default function Flujos() {
  const navigate = useNavigate();
  const { institucion } = useInstitucion();
  const [flujos, setFlujos] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [nuevo, setNuevo] = useState(false);
  const [tab, setTab] = useState("todos");
  const [area, setArea] = useState("");

  async function cargar() {
    if (!institucion) return;
    setCargando(true);
    try {
      const d = await api.get(`/flujos/?institucion=${institucion.id}`);
      setFlujos(d.results || d);
    } finally {
      setCargando(false);
    }
  }
  useEffect(() => {
    cargar(); // eslint-disable-next-line
  }, [institucion]);

  // Cada flujo: versión "vigente" (publicada o última) → estado + etiqueta.
  const filas = useMemo(
    () =>
      flujos.map((f) => {
        const pub = (f.versiones || []).find((v) => v.estado === "publicada");
        const v = pub || (f.versiones || [])[0];
        return { ...f, _ver: v, _estado: v?.estado || "borrador" };
      }),
    [flujos]
  );

  const areas = useMemo(() => [...new Set(filas.map((f) => f.area_nombre).filter(Boolean))], [filas]);

  const visibles = filas.filter((f) => {
    if (tab !== "todos" && f._estado !== tab) return false;
    if (area && f.area_nombre !== area) return false;
    return true;
  });

  return (
    <>
      <PageHeader subtitle="Diseñá un proceso como diagrama. La misma definición se ejecuta." />
      <div style={{ padding: "18px 30px 30px" }}>
        {/* Toolbar: tabs + área + nuevo */}
        <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 18, flexWrap: "wrap" }}>
          <div style={{ display: "flex", gap: 7 }}>
            {TABS.map((t) => {
              const activo = tab === t.key;
              return (
                <button
                  key={t.key}
                  onClick={() => setTab(t.key)}
                  style={{ padding: "7px 14px", borderRadius: radius.md, fontSize: type.base, fontWeight: activo ? 600 : 500, background: "#fff", border: `1px solid ${activo ? color.accent : color.inputBorder}`, color: activo ? color.accent : color.slate500, cursor: "pointer" }}
                >
                  {t.label}
                </button>
              );
            })}
          </div>
          <Select size="sm" value={area} onChange={(e) => setArea(e.target.value)} style={{ width: "auto" }}>
            <option value="">Todas las áreas</option>
            {areas.map((a) => <option key={a} value={a}>{a}</option>)}
          </Select>
          <div style={{ flex: 1 }} />
          <Button onClick={() => setNuevo(true)} style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Icon name="plus" size={15} /> Nuevo flujo
          </Button>
        </div>

        <Card style={{ overflow: "hidden", padding: 0 }}>
          {cargando ? (
            <Spinner />
          ) : visibles.length === 0 ? (
            <EmptyState title="No hay flujos" hint="Creá el primero o cambiá los filtros." />
          ) : (
            // Scroll horizontal propio para que la página no se desborde en pantallas chicas.
            <div style={{ overflowX: "auto" }}>
              {/* Encabezado */}
              <div style={{ display: "grid", gridTemplateColumns: COLS, gap: 13, padding: "12px 20px", minWidth: 720, background: color.subtle, borderBottom: `1px solid ${color.divider}`, fontSize: type.sm, fontWeight: 700, letterSpacing: ".5px", color: color.slate500 }}>
                <div>FLUJO</div><div>ÁREA</div><div>ESTADO</div><div>VER.</div><div>CASOS</div><div>ÚLT. EDICIÓN</div><div />
              </div>
              {/* Filas */}
              {visibles.map((f) => {
                const est = f._ver ? estadoVersion[f._ver.estado] : { label: "Borrador", tone: "neutral" };
                const abrir = () => navigate(`/flujos/${f.id}`);
                return (
                  <div
                    key={f.id}
                    role="button"
                    tabIndex={0}
                    aria-label={`Abrir flujo ${f.titulo}`}
                    onClick={abrir}
                    onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); abrir(); } }}
                    style={{ display: "grid", gridTemplateColumns: COLS, gap: 13, padding: "15px 20px", minWidth: 720, alignItems: "center", borderBottom: `1px solid ${color.divider}`, cursor: "pointer" }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = color.subtle)}
                    onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 11, minWidth: 0 }}>
                      <div style={{ width: 32, height: 32, borderRadius: radius.md, background: color.accent50, color: color.accent, display: "flex", alignItems: "center", justifyContent: "center", flex: "none" }}>
                        <Icon name="workflow" size={16} />
                      </div>
                      <div style={{ fontSize: type.md, fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{f.titulo}</div>
                    </div>
                    <div title={f.ambito_label}>
                      {f.subarea_nombre ? (
                        <span style={{ display: "inline-flex", alignItems: "center", gap: 5, minWidth: 0 }}>
                          <Badge tone="info">{f.area_nombre}</Badge>
                          <span style={{ fontSize: type.sm, color: color.slate500, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>› {f.subarea_nombre}</span>
                        </span>
                      ) : (
                        <Badge tone="info">{f.area_nombre}</Badge>
                      )}
                    </div>
                    <div><Badge tone={est.tone}>{est.label}</Badge></div>
                    <div style={{ fontFamily: font.mono, fontSize: type.base, color: color.slate500 }}>{f._ver?.etiqueta || "—"}</div>
                    <div style={{ fontSize: type.md, color: color.slate700 }}>{f.casos_activos > 0 ? `${f.casos_activos} activos` : "—"}</div>
                    <div style={{ fontSize: type.base, color: color.slate500 }}>{f._ver ? new Date(f._ver.creada).toLocaleDateString("es-AR") : "—"}</div>
                    <div style={{ display: "flex", gap: 4, justifyContent: "flex-end" }} onClick={(e) => e.stopPropagation()}>
                      <IconBtn title="Abrir en diseñador" onClick={abrir} name="edit" />
                      <IconBtn title="Duplicar" onClick={() => duplicar(f, cargar)} name="copy" />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </Card>
      </div>

      {nuevo && <NuevoFlujoModal institucionId={institucion?.id} onClose={() => setNuevo(false)} onCreated={(id) => navigate(`/flujos/${id}`)} />}
    </>
  );
}

async function duplicar(flujo, recargar) {
  try {
    const nf = await api.post("/flujos/", { institucion: flujo.institucion, area: flujo.area, subarea: flujo.subarea, titulo: `${flujo.titulo} (copia)` });
    const ver = await api.post("/versiones-flujo/", { flujo: nf.id, numero: 1, estado: "borrador" });
    await api.post("/nodos/", { version: ver.id, tipo: "inicio", titulo: "Inicio", x: 80, y: 220 });
    await recargar();
  } catch {
    alert("No se pudo duplicar el flujo. Intentá de nuevo.");
  }
}

function IconBtn({ title, onClick, name }) {
  return (
    <button
      title={title}
      aria-label={title}
      onClick={onClick}
      style={{ width: 32, height: 32, borderRadius: radius.sm, border: "none", background: "none", color: color.slate500, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center" }}
      onMouseEnter={(e) => (e.currentTarget.style.background = color.divider)}
      onMouseLeave={(e) => (e.currentTarget.style.background = "none")}
    >
      <Icon name={name} size={15} />
    </button>
  );
}

function NuevoFlujoModal({ institucionId, onClose, onCreated }) {
  const [areas, setAreas] = useState([]);
  const [form, setForm] = useState({ area: "", subarea: "", titulo: "" });
  const [plantilla, setPlantilla] = useState("vacio");
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState(null);
  const set = (k, v) => setForm((p) => ({ ...p, [k]: v }));

  useEffect(() => {
    if (!institucionId) return;
    api.get(`/areas/?institucion=${institucionId}`).then((d) => setAreas(d.results || d)).catch(() => {});
  }, [institucionId]);

  const areaSel = useMemo(() => areas.find((a) => String(a.id) === String(form.area)), [areas, form.area]);
  const subareas = areaSel?.subareas || [];
  const plantillaSel = PLANTILLAS.find((p) => p.key === plantilla) || PLANTILLAS[0];

  // Crea flujo + versión + nodos/conexiones de la plantilla, con manejo de error
  // (si falla un paso intermedio se avisa en vez de dejar al usuario sin feedback).
  async function crear() {
    setGuardando(true);
    setError(null);
    try {
      const flujo = await api.post("/flujos/", {
        institucion: institucionId,
        area: form.area || null,
        subarea: form.subarea || null,
        titulo: form.titulo,
      });
      const ver = await api.post("/versiones-flujo/", { flujo: flujo.id, numero: 1, estado: "borrador" });
      const idMap = {};
      for (const n of plantillaSel.nodos) {
        const creado = await api.post("/nodos/", { version: ver.id, tipo: n.tipo, titulo: n.titulo, x: n.x, y: n.y });
        idMap[n.k] = creado.id;
      }
      for (const [o, d] of plantillaSel.conexiones) {
        await api.post("/conexiones/", { version: ver.id, origen: idMap[o], destino: idMap[d] });
      }
      onCreated(flujo.id);
    } catch (e) {
      setError(e?.data?.detail || "No se pudo crear el flujo. Revisá los datos e intentá de nuevo.");
      setGuardando(false);
    }
  }

  return (
    <Modal
      title="Nuevo flujo"
      onClose={onClose}
      footer={<><Button variant="secondary" onClick={onClose}>Cancelar</Button><Button disabled={guardando || !form.titulo} onClick={crear}>{guardando ? "Creando…" : "Crear y diseñar"}</Button></>}
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        {error && (
          <div style={{ fontSize: type.base, color: color.danger, background: badgeTone.error.bg, padding: "10px 12px", borderRadius: radius.md }}>{error}</div>
        )}
        <Field label="Título *"><Input value={form.titulo} onChange={(e) => set("titulo", e.target.value)} autoFocus placeholder="Ingreso de paciente" /></Field>
        <Field label="Plantilla">
          <Select value={plantilla} onChange={(e) => setPlantilla(e.target.value)}>
            {PLANTILLAS.map((p) => <option key={p.key} value={p.key}>{p.nombre}</option>)}
          </Select>
          <div style={{ marginTop: 6, fontSize: type.xs, color: color.slate500 }}>{plantillaSel.desc}</div>
        </Field>
        <Field label="Área">
          {/* Al cambiar de área se resetea la sub-área elegida. */}
          <Select value={form.area} onChange={(e) => setForm((p) => ({ ...p, area: e.target.value, subarea: "" }))}>
            <option value="">— Toda la institución —</option>
            {areas.map((a) => <option key={a.id} value={a.id}>{a.nombre}</option>)}
          </Select>
        </Field>
        {areaSel && subareas.length > 0 && (
          <Field label="Sub-área (proceso específico)">
            <Select value={form.subarea} onChange={(e) => set("subarea", e.target.value)}>
              <option value="">— Proceso general del área —</option>
              {subareas.map((s) => <option key={s.id} value={s.id}>{s.nombre}</option>)}
            </Select>
          </Field>
        )}
        <div style={{ fontSize: type.sm, color: color.slate500 }}>
          {form.subarea
            ? "Proceso específico de la sub-área."
            : form.area
              ? "Proceso general del área."
              : "Proceso de toda la institución."}
        </div>
      </div>
    </Modal>
  );
}
