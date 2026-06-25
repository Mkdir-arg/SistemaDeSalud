import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useInstitucion } from "../auth/InstitutionContext";
import { PageHeader } from "../components/Shell";
import { Badge, Button, Card, EmptyState, Field, Input, Modal, Select, Spinner } from "../components/ui";
import { Icon } from "../components/icons";
import { antiguedad } from "../lib/format";
import { color } from "../theme";

const REFRESCO_MS = 30000; // auto-refresco silencioso del worklist

// "Mi trabajo": worklist del operador, segmentada por paso (nodo). Las bandas las
// arma el backend (GET /mis-tareas/) a partir de usuario → grupos → nodos.
export default function MiTrabajo() {
  const { institucion } = useInstitucion();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [refrescando, setRefrescando] = useState(false);
  const [error, setError] = useState(false);
  const [ultima, setUltima] = useState(null); // ISO del último refresco OK
  const [accion, setAccion] = useState(null); // id de caso que se está tomando
  const [ingresar, setIngresar] = useState(null); // item de "iniciar" elegido

  const cargar = useCallback(async (silent = false) => {
    if (!institucion) return;
    silent ? setRefrescando(true) : setCargando(true);
    try {
      const d = await api.get(`/mis-tareas/?institucion=${institucion.id}`);
      setData(d);
      setError(false);
      setUltima(new Date().toISOString());
    } catch {
      if (!silent) setError(true); // en refresco silencioso conservamos lo que había
    } finally {
      silent ? setRefrescando(false) : setCargando(false);
    }
  }, [institucion]);
  useEffect(() => { cargar(); }, [cargar]);

  // Worklist vivo: el operador deja la pantalla abierta mientras entran casos.
  // Refresca solo (silencioso) cada 30s y al volver el foco; se pausa si la
  // pestaña no está visible para no machacar la API en segundo plano.
  useEffect(() => {
    const tick = () => { if (!document.hidden) cargar(true); };
    const id = setInterval(tick, REFRESCO_MS);
    document.addEventListener("visibilitychange", tick);
    window.addEventListener("focus", tick);
    return () => {
      clearInterval(id);
      document.removeEventListener("visibilitychange", tick);
      window.removeEventListener("focus", tick);
    };
  }, [cargar]);

  async function tomarYAbrir(c) {
    setAccion(c.id);
    try {
      if (!c.mio) await api.post(`/casos/${c.id}/tomar/`);
      navigate(`/casos/${c.id}`);
    } finally {
      setAccion(null);
    }
  }

  if (cargando && !data) return <Spinner label="Cargando tu trabajo…" />;
  if (error && !data) {
    return (
      <div style={{ padding: 48, textAlign: "center" }}>
        <div style={{ fontSize: 15, fontWeight: 700, color: color.slate700 }}>No pudimos cargar tu trabajo</div>
        <div style={{ fontSize: 13, color: color.slate400, margin: "6px 0 16px" }}>Revisá la conexión y reintentá.</div>
        <Button onClick={() => cargar()}>Reintentar</Button>
      </div>
    );
  }
  const d = data || { iniciar: [], tareas: [], filas: [], esperando: [] };
  const vacio = !d.iniciar.length && !d.tareas.length && !d.filas.length && !d.esperando.length;

  return (
    <>
      <PageHeader
        subtitle="Lo que podés iniciar y lo que está esperando por vos."
        right={
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            {ultima && (
              <span style={{ fontSize: 12, color: color.slate400 }}>
                {refrescando ? "Actualizando…" : `Actualizado hace ${hace(ultima)}`}
              </span>
            )}
            <Button variant="secondary" onClick={() => cargar()}>↻ Actualizar</Button>
          </div>
        }
      />

      <div style={{ padding: "22px 32px", display: "flex", flexDirection: "column", gap: 26, maxWidth: 940 }}>
        {vacio && (
          <EmptyState title="No tenés tareas pendientes" hint="Cuando entren casos a los pasos que operás, van a aparecer acá." />
        )}

        {/* INICIAR */}
        {d.iniciar.length > 0 && (
          <Seccion titulo="Iniciar">
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(270px, 1fr))", gap: 12 }}>
              {d.iniciar.map((it) => (
                <Card key={it.version_id} style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>
                  <div>
                    <div style={{ fontSize: 14.5, fontWeight: 700 }}>{it.flujo_titulo}</div>
                    <div style={{ fontSize: 12.5, color: color.slate400, marginTop: 2 }}>
                      {it.area_nombre} · empieza en «{it.paso}»
                    </div>
                  </div>
                  <Button onClick={() => setIngresar(it)} style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}>
                    <Icon name="enter" size={15} /> Ingresar paciente
                  </Button>
                </Card>
              ))}
            </div>
          </Seccion>
        )}

        {/* PARA HACER AHORA */}
        {d.tareas.length > 0 && (
          <Seccion titulo="Para hacer ahora">
            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              {d.tareas.map((b) => (
                <TareaCard key={b.nodo_id} b={b} accion={accion}
                  onAbrir={(id) => navigate(`/casos/${id}`)} onTomar={tomarYAbrir} />
              ))}
            </div>
          </Seccion>
        )}

        {/* MIS FILAS */}
        {d.filas.length > 0 && (
          <Seccion titulo="Mis filas">
            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              {d.filas.map((f) => (
                <FilaCard key={f.nodo_id} f={f} onLlamado={(id) => navigate(`/casos/${id}`)} />
              ))}
            </div>
          </Seccion>
        )}

        {/* ESPERANDO */}
        {d.esperando.length > 0 && (
          <Seccion titulo="Esperando resultados">
            <Card style={{ overflow: "hidden" }}>
              {d.esperando.map((c, i) => (
                <div key={c.id} onClick={() => navigate(`/casos/${c.id}`)}
                  style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px 16px", cursor: "pointer", borderTop: i ? `1px solid ${color.divider}` : "none" }}>
                  <Icon name="clipboard" size={15} style={{ color: color.slate400, flex: "none" }} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 13.5, fontWeight: 600 }}>{c.ciudadano_nombre || "—"}</div>
                    <div style={{ fontSize: 12, color: color.slate400 }}>{c.flujo_titulo} · esperando «{c.espera_de}»</div>
                  </div>
                  <Badge tone="amber">En espera</Badge>
                </div>
              ))}
            </Card>
          </Seccion>
        )}
      </div>

      {ingresar && (
        <IngresarPacienteModal
          item={ingresar} institucionId={institucion?.id}
          onClose={() => setIngresar(null)}
          onCreated={(id) => { setIngresar(null); navigate(`/casos/${id}`); }}
        />
      )}
    </>
  );
}

const subPaso = (b) => [b.flujo_titulo, b.area_nombre].filter(Boolean).join(" · ");

// Relativo corto para el sello de "actualizado": segundos hasta el minuto, luego antigüedad.
function hace(iso) {
  const s = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 50) return "unos segundos";
  return antiguedad(iso);
}

// Umbrales de espera (minutos) para resaltar demoras en el worklist. En una
// guardia, cuánto lleva esperando un caso pesa tanto como su prioridad.
const ESPERA_AMBAR_MIN = 15;
const ESPERA_ROJO_MIN = 30;

function tonoEspera(iso) {
  const m = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 60000));
  if (m >= ESPERA_ROJO_MIN) return { color: color.danger, demorado: true };
  if (m >= ESPERA_AMBAR_MIN) return { color: "#A96A12", demorado: true };
  return { color: color.slate400, demorado: false };
}

// Tiempo de espera coloreado según el umbral (verde → ámbar → rojo).
function EsperaChip({ iso, prefijo = "" }) {
  const t = tonoEspera(iso);
  return <span style={{ color: t.color, fontWeight: t.demorado ? 700 : 400 }}>{prefijo}{antiguedad(iso)}</span>;
}

// ISO más antiguo (el que más espera) de una lista; null si está vacía.
const masViejo = (isos) => (isos.length ? isos.reduce((a, b) => (new Date(a) < new Date(b) ? a : b)) : null);

function Seccion({ titulo, children }) {
  return (
    <div>
      <div style={{ fontSize: 11.5, fontWeight: 700, letterSpacing: ".6px", color: color.slate400, marginBottom: 10, textTransform: "uppercase" }}>
        {titulo}
      </div>
      {children}
    </div>
  );
}

function CabeceraPaso({ icon, titulo, sub, total, urgentes, totalLabel = "esperando", desde, abierto }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "13px 16px" }}>
      <div style={{ width: 32, height: 32, borderRadius: 8, background: color.accent50, color: color.accent, display: "flex", alignItems: "center", justifyContent: "center", flex: "none" }}>
        <Icon name={icon} size={16} />
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 14, fontWeight: 700 }}>{titulo}</div>
        <div style={{ fontSize: 12, color: color.slate400, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{sub}</div>
      </div>
      {desde && <span style={{ fontSize: 12 }}><EsperaChip iso={desde} prefijo="el más antiguo · " /></span>}
      {urgentes > 0 && <Badge tone="error">{urgentes} urgente{urgentes > 1 ? "s" : ""}</Badge>}
      <Badge tone="neutral">{total} {totalLabel}</Badge>
      {abierto !== undefined && (
        <Icon name="back" size={13} style={{ color: color.slate400, flex: "none", transform: abierto ? "rotate(-90deg)" : "rotate(90deg)" }} />
      )}
    </div>
  );
}

// Card de un paso de la banda "Para hacer ahora", plegable por su cabecera.
function TareaCard({ b, accion, onAbrir, onTomar }) {
  const [abierto, setAbierto] = useState(true);
  return (
    <Card style={{ overflow: "hidden" }}>
      <div onClick={() => setAbierto((v) => !v)} style={{ cursor: "pointer" }}>
        <CabeceraPaso icon="inbox" titulo={b.nodo_titulo} sub={subPaso(b)} total={b.total} urgentes={b.urgentes}
          desde={masViejo(b.casos.map((c) => c.creado))} abierto={abierto} />
      </div>
      {abierto && b.casos.map((c) => (
        <FilaCaso key={c.id} c={c} cargando={accion === c.id}
          onAbrir={() => onAbrir(c.id)} onTomar={() => onTomar(c)} />
      ))}
    </Card>
  );
}

function PrioridadDot({ prioridad }) {
  const c = prioridad === "urgente" ? color.danger : prioridad === "alta" ? "#A96A12" : "#D0D5DD";
  return <span title={prioridad} style={{ width: 9, height: 9, borderRadius: 99, background: c, flex: "none" }} />;
}

function FilaCaso({ c, cargando, onAbrir, onTomar }) {
  const enCurso = c.asignado_a && !c.mio;
  const t = tonoEspera(c.creado);
  return (
    <div
      onClick={onAbrir}
      style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px 16px 12px 13px", borderTop: `1px solid ${color.divider}`, borderLeft: `3px solid ${t.demorado ? t.color : "transparent"}`, cursor: "pointer", opacity: enCurso ? 0.62 : 1 }}
      onMouseEnter={(e) => (e.currentTarget.style.background = color.subtle)}
      onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
    >
      <PrioridadDot prioridad={c.prioridad} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13.5, fontWeight: 600 }}>{c.ciudadano_nombre || "Sin paciente"}</div>
        <div style={{ fontSize: 12, color: color.slate400 }}>
          <EsperaChip iso={c.creado} /> · {c.estado_display}{enCurso ? ` · en curso por ${c.asignado_nombre}` : ""}
        </div>
      </div>
      {c.mio ? (
        <Button style={{ height: 32, padding: "0 14px" }} onClick={(e) => { e.stopPropagation(); onAbrir(); }}>Continuar</Button>
      ) : enCurso ? (
        <Badge tone="neutral">Tomado</Badge>
      ) : (
        <Button variant="secondary" style={{ height: 32, padding: "0 14px" }} disabled={cargando} onClick={(e) => { e.stopPropagation(); onTomar(); }}>
          {cargando ? "…" : "Tomar y abrir"}
        </Button>
      )}
    </div>
  );
}

function FilaCard({ f, onLlamado }) {
  const [box, setBox] = useState(f.boxes[0] ? String(f.boxes[0].id) : "");
  const [llamando, setLlamando] = useState(null); // id del caso que se está llamando
  const [abierto, setAbierto] = useState(true);
  const siguiente = f.casos[0];
  const enCurso = llamando !== null;

  async function llamar(caso) {
    if (!caso) return;
    setLlamando(caso.id);
    try {
      await api.post(`/casos/${caso.id}/llamar/`, { box_id: box ? Number(box) : null });
      onLlamado(caso.id);
    } finally {
      setLlamando(null);
    }
  }

  return (
    <Card style={{ overflow: "hidden" }}>
      <div onClick={() => setAbierto((v) => !v)} style={{ cursor: "pointer" }}>
        <CabeceraPaso icon="list" titulo={f.nodo_titulo} sub={[f.flujo_titulo, f.area_nombre].filter(Boolean).join(" · ")} total={f.en_cola} urgentes={f.urgentes} totalLabel="en cola" desde={masViejo(f.casos.map((c) => c.ingreso))} abierto={abierto} />
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "12px 16px", borderTop: `1px solid ${color.divider}`, background: color.subtle }}>
        {f.boxes.length > 0 && (
          <Select value={box} onChange={(e) => setBox(e.target.value)} style={{ maxWidth: 190 }}>
            {f.boxes.map((b) => <option key={b.id} value={b.id}>{b.nombre}</option>)}
          </Select>
        )}
        <Button disabled={!siguiente || enCurso} onClick={() => llamar(siguiente)}>
          {llamando === siguiente?.id ? "Llamando…" : siguiente ? `Llamar siguiente${siguiente.ciudadano_nombre ? " · " + siguiente.ciudadano_nombre : ""}` : "Sin pacientes en cola"}
        </Button>
      </div>
      {abierto && f.casos.slice(0, 6).map((c, i) => {
        const t = tonoEspera(c.ingreso);
        return (
          <div key={c.item_id} style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 16px 8px 13px", borderTop: `1px solid ${color.divider}`, borderLeft: `3px solid ${t.demorado ? t.color : "transparent"}` }}>
            <span style={{ fontSize: 12, color: color.slate400, width: 18, textAlign: "right" }}>{i + 1}</span>
            <PrioridadDot prioridad={c.urgente ? "urgente" : "normal"} />
            <div style={{ flex: 1, fontSize: 13.5, minWidth: 0, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{c.ciudadano_nombre || "—"}</div>
            <span style={{ fontSize: 12 }}><EsperaChip iso={c.ingreso} /></span>
            <Button variant="secondary" style={{ height: 28, padding: "0 12px", fontSize: 12 }} disabled={enCurso} onClick={() => llamar(c)}>
              {llamando === c.id ? "…" : "Llamar"}
            </Button>
          </div>
        );
      })}
    </Card>
  );
}

// Alta de un paciente sobre un flujo manual concreto (la banda "Iniciar").
function IngresarPacienteModal({ item, institucionId, onClose, onCreated }) {
  const [ciudadanos, setCiudadanos] = useState([]);
  const [modo, setModo] = useState("existente"); // "existente" | "nuevo"
  const [ciudadanoId, setCiudadanoId] = useState("");
  const [nuevo, setNuevo] = useState({ nombre: "", apellido: "", documento: "" });
  const [prioridad, setPrioridad] = useState("normal");
  const [creando, setCreando] = useState(false);
  const setNuevoCampo = (k, v) => setNuevo((p) => ({ ...p, [k]: v }));

  useEffect(() => {
    (async () => {
      const c = await api.get(`/ciudadanos/?institucion=${institucionId}`);
      const lista = c.results || c;
      setCiudadanos(lista);
      if (lista.length === 0) setModo("nuevo");
      else setCiudadanoId(String(lista[0].id));
    })();
  }, [institucionId]);

  const pacienteOk = modo === "existente" ? !!ciudadanoId : !!nuevo.nombre.trim();

  async function crear() {
    if (!pacienteOk || creando) return;
    setCreando(true);
    try {
      let cid = ciudadanoId;
      if (modo === "nuevo") {
        const c = await api.post("/ciudadanos/", {
          institucion: institucionId,
          nombre: nuevo.nombre.trim(), apellido: nuevo.apellido.trim(), documento: nuevo.documento.trim(),
        });
        cid = c.id;
      }
      const caso = await api.post("/casos/", {
        institucion: institucionId, version: item.version_id, ciudadano: Number(cid), prioridad,
      });
      await api.post(`/casos/${caso.id}/iniciar/`);
      onCreated(caso.id);
    } finally {
      setCreando(false);
    }
  }

  const tabBtn = (k, label) => (
    <button
      onClick={() => setModo(k)}
      style={{ flex: 1, padding: "7px 0", fontSize: 12.5, fontWeight: 600, borderRadius: 8, cursor: "pointer",
        border: `1px solid ${modo === k ? color.accent : color.inputBorder}`,
        background: modo === k ? color.accent50 : "#fff", color: modo === k ? color.accent : color.slate500 }}
    >
      {label}
    </button>
  );

  return (
    <Modal
      title={`Ingresar paciente · ${item.flujo_titulo}`}
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancelar</Button>
          <Button disabled={!pacienteOk || creando} onClick={crear}>{creando ? "Ingresando…" : "Ingresar e iniciar"}</Button>
        </>
      }
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <Field label="Paciente *">
          <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
            {tabBtn("existente", "Paciente existente")}
            {tabBtn("nuevo", "Nuevo paciente")}
          </div>
          {modo === "existente" ? (
            ciudadanos.length === 0 ? (
              <div style={{ fontSize: 12.5, color: color.slate400 }}>No hay pacientes cargados. Usá «Nuevo paciente».</div>
            ) : (
              <Select value={ciudadanoId} onChange={(e) => setCiudadanoId(e.target.value)}>
                {ciudadanos.map((c) => (
                  <option key={c.id} value={c.id}>{c.nombre} {c.apellido}{c.documento ? ` · ${c.documento}` : ""}</option>
                ))}
              </Select>
            )
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <Input placeholder="Nombre *" value={nuevo.nombre} onChange={(e) => setNuevoCampo("nombre", e.target.value)} autoFocus />
              <Input placeholder="Apellido" value={nuevo.apellido} onChange={(e) => setNuevoCampo("apellido", e.target.value)} />
              <Input placeholder="Documento" value={nuevo.documento} onChange={(e) => setNuevoCampo("documento", e.target.value)} />
            </div>
          )}
        </Field>

        <Field label="Prioridad">
          <Select value={prioridad} onChange={(e) => setPrioridad(e.target.value)}>
            <option value="normal">Normal</option>
            <option value="alta">Alta</option>
            <option value="urgente">Urgente</option>
          </Select>
        </Field>
      </div>
    </Modal>
  );
}
