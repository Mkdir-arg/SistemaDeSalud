import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../../api/client";
import { PageHeader } from "../../components/Shell";
import { Badge, Button, Card, Field, Input, Mono, Select, Spinner, Stepper, Textarea } from "../../components/ui";
import { Icon } from "../../components/icons";
import { casoId, fechaHora } from "../../lib/format";
import { color, estadoCaso, nodeCat } from "../../theme";
import { CancelarModal, ReasignarModal } from "../Supervision";

// Orden conceptual del stepper de ejecución.
const PASOS = [
  { label: "Recibido", estados: ["recibido"] },
  { label: "En proceso", estados: ["en_evaluacion", "en_espera"] },
  { label: "Derivado", estados: ["derivado"] },
  { label: "Atendido", estados: ["atendido"] },
  { label: "Cerrado", estados: ["cerrado"] },
];
function pasoActual(estado) {
  const i = PASOS.findIndex((p) => p.estados.includes(estado));
  return i < 0 ? 0 : i;
}

export default function CasoDetalle() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [caso, setCaso] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [accionando, setAccionando] = useState(false);
  const [error, setError] = useState("");
  const [hc, setHc] = useState(null); // antecedentes de historia clínica (solo lectura)

  async function cargar() {
    setCargando(true);
    try {
      const c = await api.get(`/casos/${id}/`);
      setCaso(c);
      if (c.ciudadano) {
        const d = await api.get(`/historias-clinicas/?ciudadano=${c.ciudadano}`);
        setHc((d.results || d)[0] || null);
      }
    } finally {
      setCargando(false);
    }
  }
  useEffect(() => {
    cargar(); // eslint-disable-next-line
  }, [id]);

  async function ejecutar(fn) {
    setError("");
    setAccionando(true);
    try {
      await fn();
      await cargar();
    } catch (e) {
      setError(e?.data?.detail || "No se pudo completar la acción.");
    } finally {
      setAccionando(false);
    }
  }

  if (cargando || !caso) return <Spinner label="Cargando caso…" />;

  const est = estadoCaso[caso.estado] || { label: caso.estado_display, tone: "neutral" };
  const cerrado = ["cerrado", "cancelado"].includes(caso.estado);
  const catNodo = caso.nodo_tipo ? (nodeCat[caso.nodo_tipo] || nodeCat.form) : null;

  return (
    <>
      <PageHeader
        title={
          <span>
            <Mono style={{ fontSize: 19 }}>{casoId(caso.id)}</Mono>
          </span>
        }
        subtitle={`${caso.flujo_titulo}${caso.ciudadano_nombre ? " · " + caso.ciudadano_nombre : ""}`}
      />

      <div style={{ padding: 32, display: "grid", gridTemplateColumns: "1fr 320px", gap: 24, alignItems: "start" }}>
        {/* Columna principal */}
        <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
          {/* Stepper + paso (nodo) actual */}
          <Card style={{ padding: "28px 32px" }}>
            <Stepper steps={PASOS} current={pasoActual(caso.estado)} />
            {caso.paso_actual && (
              <div style={{ marginTop: 20, paddingTop: 16, borderTop: `1px solid ${color.divider}`, display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: ".5px", color: color.slate400 }}>PASO ACTUAL</span>
                {catNodo && (
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "3px 10px", borderRadius: 999, background: catNodo.tint, border: `1px solid ${catNodo.bd}`, fontSize: 12, fontWeight: 600, color: catNodo.sol }}>
                    <span style={{ width: 7, height: 7, borderRadius: 2, background: catNodo.sol }} /> {catNodo.name}
                  </span>
                )}
                <span style={{ fontSize: 15, fontWeight: 700 }}>{caso.paso_actual}</span>
              </div>
            )}
          </Card>

          {/* Historia clínica · antecedentes (solo lectura) */}
          {hc && (hc.alergias || hc.condiciones) && (
            <Card style={{ padding: 0, overflow: "hidden" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "14px 20px", background: "#FCEAF2", borderBottom: `1px solid ${color.divider}` }}>
                <div style={{ display: "flex", alignItems: "center", gap: 9, fontSize: 14, fontWeight: 700, color: "#D14B8F" }}>
                  <Icon name="clipboard" size={17} /> Historia clínica · antecedentes
                </div>
                <span style={{ fontSize: 11, color: color.slate400 }}>solo lectura</span>
              </div>
              <div style={{ padding: "16px 20px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
                <Dato k="Alergias" v={<span style={{ color: hc.alergias ? "#B42318" : color.slate500 }}>{hc.alergias || "—"}</span>} />
                <Dato k="Condiciones" v={hc.condiciones || "—"} />
              </div>
            </Card>
          )}

          {error && (
            <div style={{ fontSize: 13, color: "#B42318", background: "#FCEBEB", padding: "10px 14px", borderRadius: 9 }}>
              {error}
            </div>
          )}

          {/* Panel del paso actual */}
          <PanelPaso caso={caso} cerrado={cerrado} accionando={accionando} ejecutar={ejecutar} hc={hc} />

          {/* Datos cargados */}
          {caso.valores?.length > 0 && (
            <Card style={{ padding: 24 }}>
              <SectionTitle>Datos cargados</SectionTitle>
              <div style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 12 }}>
                {caso.valores.map((v) => (
                  <div key={v.id} style={{ display: "flex", justifyContent: "space-between", gap: 16, fontSize: 13.5 }}>
                    <span style={{ color: color.slate500 }}>{v.campo_label}</span>
                    <span style={{ fontWeight: 500, color: color.slate900, textAlign: "right" }}>{v.valor || "—"}</span>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>

        {/* Columna lateral */}
        <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
          <Card style={{ padding: 22 }}>
            <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: ".6px", color: color.slate400, marginBottom: 14 }}>INFORMACIÓN DEL CASO</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 13 }}>
              <Dato k="Estado" v={<Badge tone={est.tone}>{est.label}</Badge>} />
              <Dato k="Paso actual" v={caso.paso_actual || "—"} />
              <Dato k="Flujo" v={caso.flujo_titulo} />
              <Dato k="Área actual" v={caso.area_nombre || "—"} />
              <Dato k="Responsable" v={caso.responsables?.length ? caso.responsables.map((g) => g.nombre).join(", ") : "Abierto a todos"} />
              <Dato k="Asignado a" v={caso.asignado_nombre || "Sin asignar"} />
              <Dato k="Ingreso" v={fechaHora(caso.creado)} />
              <Dato k="Prioridad" v={caso.prioridad_display} />
            </div>
          </Card>

          {/* Supervisión: solo para el jefe del área del caso. */}
          {caso.puede_supervisar && !cerrado && (
            <PanelSupervision caso={caso} ejecutar={ejecutar} recargar={cargar} accionando={accionando} />
          )}

          {/* Derivaciones entre flujos (origen / destinos) */}
          {(caso.origen || caso.derivados?.length > 0) && (
            <Card style={{ padding: 22 }}>
              <SectionTitle>Derivaciones</SectionTitle>
              <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 12 }}>
                {caso.origen && (
                  <button
                    onClick={() => navigate(`/casos/${caso.origen}`)}
                    style={{ textAlign: "left", border: `1px solid ${color.divider}`, background: "none", borderRadius: 9, padding: "10px 12px", cursor: "pointer" }}
                  >
                    <div style={{ fontSize: 11, color: color.slate400 }}>Originado desde</div>
                    <div style={{ fontSize: 13.5, fontWeight: 600, color: color.accent }}>{casoId(caso.origen)} · {caso.origen_flujo}</div>
                  </button>
                )}
                {(caso.derivados || []).map((d) => {
                  const e = estadoCaso[d.estado] || { label: d.estado, tone: "neutral" };
                  return (
                    <button
                      key={d.id}
                      onClick={() => navigate(`/casos/${d.id}`)}
                      style={{ textAlign: "left", border: `1px solid ${color.divider}`, background: "none", borderRadius: 9, padding: "10px 12px", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}
                    >
                      <span>
                        <span style={{ display: "block", fontSize: 11, color: color.slate400 }}>Derivado a</span>
                        <span style={{ fontSize: 13.5, fontWeight: 600, color: color.accent }}>{casoId(d.id)} · {d.flujo_titulo}</span>
                      </span>
                      <Badge tone={e.tone}>{e.label}</Badge>
                    </button>
                  );
                })}
              </div>
            </Card>
          )}

          {/* Trazabilidad */}
          <Card style={{ padding: 22 }}>
            <SectionTitle>Trazabilidad</SectionTitle>
            <Timeline eventos={caso.eventos || []} />
          </Card>
        </div>
      </div>
    </>
  );
}

// --------------------------------------------------------------------------- //
// Acciones del jefe/supervisor de área sobre el caso (reasignar / repriorizar / cancelar).
function PanelSupervision({ caso, ejecutar, recargar, accionando }) {
  const [modal, setModal] = useState(null); // "reasignar" | "cancelar"
  const [candidatos, setCandidatos] = useState([]);

  useEffect(() => {
    (async () => {
      try {
        const [u, m] = await Promise.all([
          api.get(`/usuarios/`),
          api.get(`/membresias/?institucion=${caso.institucion}`),
        ]);
        const staff = u.results || u;
        const mem = m.results || m;
        let lista = staff;
        if (caso.area_actual) {
          const ids = new Set(mem.filter((x) => (x.areas || []).includes(caso.area_actual)).map((x) => x.usuario));
          const f = staff.filter((s) => ids.has(s.id));
          lista = f.length ? f : staff;
        }
        setCandidatos(lista);
      } catch { /* silencioso */ }
    })();
  }, [caso.institucion, caso.area_actual]);

  return (
    <Card style={{ padding: 22 }}>
      <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: ".6px", color: color.slate400, marginBottom: 14 }}>SUPERVISIÓN</div>
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <Field label="Prioridad">
          <Select value={caso.prioridad} disabled={accionando}
            onChange={(e) => ejecutar(() => api.post(`/casos/${caso.id}/priorizar/`, { prioridad: e.target.value }))}>
            <option value="normal">Normal</option>
            <option value="alta">Alta</option>
            <option value="urgente">Urgente</option>
          </Select>
        </Field>
        <Button variant="secondary" disabled={accionando} onClick={() => setModal("reasignar")}>Reasignar</Button>
        <Button variant="danger" disabled={accionando} onClick={() => setModal("cancelar")}>Cancelar caso</Button>
      </div>
      {modal === "reasignar" && (
        <ReasignarModal caso={caso} candidatos={candidatos} onClose={() => setModal(null)} onDone={() => { setModal(null); recargar(); }} />
      )}
      {modal === "cancelar" && (
        <CancelarModal caso={caso} onClose={() => setModal(null)} onDone={() => { setModal(null); recargar(); }} />
      )}
    </Card>
  );
}

function PanelPaso({ caso, cerrado, accionando, ejecutar, hc }) {
  // Caso aún no iniciado.
  if (!caso.nodo_actual && !cerrado) {
    return (
      <Card style={{ padding: 24 }}>
        <SectionTitle>Sin iniciar</SectionTitle>
        <p style={{ fontSize: 13.5, color: color.slate500, margin: "8px 0 16px" }}>
          El caso todavía no arrancó por el flujo. Iniciá para colocarlo en el primer paso.
        </p>
        <Button disabled={accionando} onClick={() => ejecutar(() => api.post(`/casos/${caso.id}/iniciar/`))}>
          {accionando ? "Iniciando…" : "Iniciar caso"}
        </Button>
      </Card>
    );
  }

  if (cerrado) {
    return (
      <Card style={{ padding: 24, display: "flex", alignItems: "center", gap: 12 }}>
        <span style={{ fontSize: 22 }}>✓</span>
        <div>
          <div style={{ fontSize: 15, fontWeight: 700 }}>Caso cerrado</div>
          <div style={{ fontSize: 13, color: color.slate500 }}>Este caso completó su recorrido.</div>
        </div>
      </Card>
    );
  }

  // Esperando que vuelva un estudio derivado a otra área.
  if (caso.esperando) {
    return (
      <Card style={{ padding: 24 }}>
        <PanelHeader tipo={caso.nodo_tipo} titulo={caso.paso_actual} />
        <p style={{ fontSize: 13.5, color: color.slate600, margin: 0 }}>
          El caso está <strong>esperando el resultado de un estudio</strong> derivado a otra área.
          Cuando el estudio se realice, el caso vuelve solo y vas a poder continuar la atención.
        </p>
      </Card>
    );
  }

  // Este paso tiene grupos responsables y el usuario no integra ninguno.
  if (caso.responsables?.length > 0 && !caso.puede_tomar) {
    return (
      <Card style={{ padding: 24 }}>
        <PanelHeader tipo={caso.nodo_tipo} titulo={caso.paso_actual} />
        <p style={{ fontSize: 13.5, color: color.slate600, margin: 0 }}>
          Este paso lo realiza{" "}
          <strong>{caso.responsables.map((g) => g.nombre).join(", ")}</strong>.
          No integrás {caso.responsables.length === 1 ? "ese grupo" : "esos grupos"}, así que no podés ejecutarlo.
        </p>
      </Card>
    );
  }

  const tipo = caso.nodo_tipo;
  // Atención con fila, todavía en espera (no llamado desde un box).
  if (tipo === "atencion" && caso.nodo_con_fila && !caso.llamado) {
    return (
      <Card style={{ padding: 24 }}>
        <PanelHeader tipo="atencion" titulo={caso.paso_actual} />
        <p style={{ fontSize: 13.5, color: color.slate600, margin: 0 }}>
          El paciente está en la <strong>sala de espera</strong>. Será atendido cuando se lo llame desde un box, en la pantalla <strong>«Filas de espera»</strong>.
        </p>
      </Card>
    );
  }
  if (tipo === "form") return <PasoFormulario caso={caso} accionando={accionando} ejecutar={ejecutar} />;
  if (tipo === "atencion") return <PasoAtencion caso={caso} accionando={accionando} ejecutar={ejecutar} hc={hc} />;
  if (tipo === "espera") return <PasoSimple caso={caso} accionando={accionando} ejecutar={ejecutar} titulo="Sala de espera" texto="El caso está en la fila. Cuando sea llamado, continúa al siguiente paso." accion="Llamar y continuar" />;
  if (tipo === "tiempo") return <PasoSimple caso={caso} accionando={accionando} ejecutar={ejecutar} titulo="Espera programada" texto="El caso está en pausa hasta cumplir el tiempo. Reactivá para continuar." accion="Reactivar" />;

  // Nodo automático que quedó como actual (poco común) o sin acción.
  return (
    <Card style={{ padding: 24 }}>
      <SectionTitle>{caso.paso_actual}</SectionTitle>
      <p style={{ fontSize: 13.5, color: color.slate500, marginTop: 8 }}>Este paso no requiere una acción manual.</p>
    </Card>
  );
}

function PanelHeader({ tipo, titulo }) {
  const cat = nodeCat[tipo] || nodeCat.form;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 11, marginBottom: 16 }}>
      <span style={{ width: 30, height: 30, borderRadius: 8, background: cat.tint, border: `1px solid ${cat.bd}`, display: "flex", alignItems: "center", justifyContent: "center", flex: "none" }}>
        <span style={{ width: 11, height: 11, borderRadius: 3, background: cat.sol }} />
      </span>
      <div>
        <div style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: ".6px", color: color.slate400 }}>{cat.name.toUpperCase()}</div>
        <div style={{ fontSize: 16, fontWeight: 700 }}>{titulo}</div>
      </div>
    </div>
  );
}

function PasoFormulario({ caso, accionando, ejecutar }) {
  const [campos, setCampos] = useState(null);
  const [valores, setValores] = useState({});

  useEffect(() => {
    let activo = true;
    (async () => {
      const nodo = await api.get(`/nodos/${caso.nodo_actual}/`);
      if (!nodo.formulario) {
        if (activo) setCampos([]);
        return;
      }
      const form = await api.get(`/formularios/${nodo.formulario}/`);
      if (activo) setCampos(form.campos || []);
    })();
    return () => { activo = false; };
  }, [caso.nodo_actual]);

  if (campos === null) return <Card style={{ padding: 24 }}><Spinner label="Cargando formulario…" /></Card>;

  const set = (id, v) => setValores((prev) => ({ ...prev, [id]: v }));

  return (
    <Card style={{ padding: 24 }}>
      <PanelHeader tipo="form" titulo={caso.paso_actual} />
      {campos.length === 0 ? (
        <p style={{ fontSize: 13.5, color: color.slate500 }}>Este formulario no tiene campos definidos.</p>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {campos.map((c) => (
            <Field key={c.id} label={c.label + (c.requerido ? " *" : "")}>
              <CampoInput campo={c} value={valores[c.id] || ""} onChange={(v) => set(c.id, v)} />
              {c.ayuda && <div style={{ fontSize: 12, color: color.slate400, marginTop: 4 }}>{c.ayuda}</div>}
            </Field>
          ))}
        </div>
      )}
      <div style={{ marginTop: 20 }}>
        <Button
          disabled={accionando}
          onClick={() => ejecutar(() => api.post(`/casos/${caso.id}/avanzar/`, { valores }))}
        >
          {accionando ? "Guardando…" : "Completar y avanzar"}
        </Button>
      </div>
    </Card>
  );
}

function CampoInput({ campo, value, onChange }) {
  if (campo.tipo === "texto_largo") return <Textarea value={value} onChange={(e) => onChange(e.target.value)} />;
  if (campo.tipo === "fecha") return <Input type="date" value={value} onChange={(e) => onChange(e.target.value)} />;
  if (campo.tipo === "seleccion_unica")
    return (
      <Select value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">Seleccionar…</option>
        {(campo.opciones || []).map((o) => (
          <option key={o} value={o}>{o}</option>
        ))}
      </Select>
    );
  if (campo.tipo === "archivo") return <CampoArchivo value={value} onChange={onChange} />;
  return <Input value={value} onChange={(e) => onChange(e.target.value)} />;
}

function CampoArchivo({ value, onChange }) {
  const [subiendo, setSubiendo] = useState(false);
  async function onFile(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setSubiendo(true);
    try {
      const r = await api.upload(file);
      onChange(r.nombre);
    } finally {
      setSubiendo(false);
    }
  }
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
      <input type="file" onChange={onFile} disabled={subiendo} style={{ fontSize: 13 }} />
      {subiendo && <span style={{ fontSize: 12, color: color.slate400 }}>Subiendo…</span>}
      {value && !subiendo && <span style={{ fontSize: 12.5, color: color.slate600 }}>✓ {value}</span>}
    </div>
  );
}

function PasoAtencion({ caso, accionando, ejecutar, hc }) {
  const realizandoEstudio = !!caso.estudio_tipo; // este caso vino a REALIZAR un estudio
  const [titulo, setTitulo] = useState(caso.paso_actual || "");
  const [contenido, setContenido] = useState("");
  const [firmada, setFirmada] = useState(true);
  const [tipoEstudio, setTipoEstudio] = useState("");
  const [areaEstudio, setAreaEstudio] = useState("");
  const [areasDestino, setAreasDestino] = useState([]);
  const [detalleReceta, setDetalleReceta] = useState("");
  const [motivoIc, setMotivoIc] = useState("");
  const [areaIc, setAreaIc] = useState("");
  const [resultado, setResultado] = useState("");
  const [archivo, setArchivo] = useState("");

  const estudios = hc?.estudios || [];
  const recetas = hc?.recetas || [];

  // Rellamar: el paciente fue llamado a un box pero no se presentó. Vuelve a
  // destacarlo (y suena) en la pantalla de la sala. No recarga: feedback liviano.
  const [rellamando, setRellamando] = useState(false);
  const [rellamos, setRellamos] = useState(0); // rellamados hechos en esta sesión
  async function rellamar() {
    setRellamando(true);
    try {
      await api.post(`/casos/${caso.id}/rellamar/`);
      setRellamos((n) => n + 1);
    } finally {
      setRellamando(false);
    }
  }

  // Áreas destino para derivar (estudio o interconsulta): tienen flujo publicado derivable.
  useEffect(() => {
    if (realizandoEstudio) return;
    api.get(`/flujos/?institucion=${caso.institucion}`).then((d) => {
      const lista = d.results || d;
      const mapa = {};
      lista.forEach((f) => {
        const pub = (f.versiones || []).some((v) => v.estado === "publicada");
        if (pub && f.origen_inicio !== "manual" && f.area && f.area !== caso.area_actual) mapa[f.area] = f.area_nombre;
      });
      setAreasDestino(Object.entries(mapa).map(([id, nombre]) => ({ id: Number(id), nombre })));
    });
  }, [caso.institucion, caso.area_actual, realizandoEstudio]);

  async function solicitarEstudio() {
    if (!tipoEstudio.trim()) return;
    const body = { tipo: tipoEstudio.trim() };
    if (areaEstudio) body.area_id = Number(areaEstudio);
    await ejecutar(() => api.post(`/casos/${caso.id}/estudio/`, body));
    setTipoEstudio("");
  }
  async function emitirReceta() {
    if (!detalleReceta.trim()) return;
    await ejecutar(() => api.post(`/casos/${caso.id}/receta/`, { detalle: detalleReceta.trim() }));
    setDetalleReceta("");
  }
  async function pedirInterconsulta() {
    if (!areaIc) return;
    await ejecutar(() => api.post(`/casos/${caso.id}/interconsulta/`, { area_id: Number(areaIc), motivo: motivoIc.trim() }));
    setMotivoIc(""); setAreaIc("");
  }
  function registrar() {
    const body = { titulo, contenido, firmada };
    if (realizandoEstudio) { body.resultado = resultado; body.archivo = archivo; }
    return api.post(`/casos/${caso.id}/avanzar/`, body);
  }

  const tituloSec = { fontSize: 12.5, fontWeight: 700, color: color.slate600, marginBottom: 8 };

  return (
    <Card style={{ padding: 24 }}>
      <PanelHeader tipo="atencion" titulo={caso.paso_actual} />

      {/* Atención con fila: el paciente fue llamado a un box. Si no se presenta,
          se lo puede volver a llamar (parpadea en la pantalla de la sala). */}
      {caso.nodo_con_fila && caso.llamado && (
        <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px 14px", marginBottom: 16, background: "#FFF4DF", border: "1px solid #F3D49B", borderRadius: 10 }}>
          <Icon name="enter" size={18} style={{ color: "#B4690E", flex: "none" }} />
          <div style={{ flex: 1, minWidth: 0, fontSize: 13, color: "#7A4D08" }}>
            Paciente llamado{caso.llamado_box ? <> a <strong>{caso.llamado_box}</strong></> : ""}.
            {rellamos > 0 ? <> Se rellamó {rellamos === 1 ? "una vez" : `${rellamos} veces`} — mirá la pantalla de la sala.</> : <> ¿No se presentó?</>}
          </div>
          <Button variant="secondary" disabled={rellamando} onClick={rellamar} style={{ flex: "none" }}>
            {rellamando ? "Rellamando…" : "Rellamar"}
          </Button>
        </div>
      )}

      {realizandoEstudio && (
        <div style={{ fontSize: 12.5, color: color.slate500, marginBottom: 12 }}>
          Estudio a realizar: <strong style={{ color: color.slate700 }}>{caso.estudio_tipo}</strong>
        </div>
      )}
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <Field label="Título de la atención">
          <Input value={titulo} onChange={(e) => setTitulo(e.target.value)} />
        </Field>
        <Field label={realizandoEstudio ? "Informe / observaciones" : "Evolución / observaciones"}>
          <Textarea value={contenido} onChange={(e) => setContenido(e.target.value)} placeholder="Lo que se asienta en la historia clínica…" />
        </Field>
        <label style={{ display: "flex", alignItems: "center", gap: 9, fontSize: 13.5, color: color.slate600, cursor: "pointer" }}>
          <input type="checkbox" checked={firmada} onChange={(e) => setFirmada(e.target.checked)} />
          Firmar la entrada
        </label>
      </div>

      {realizandoEstudio ? (
        /* Quien REALIZA el estudio carga su resultado estructurado. */
        <div style={{ marginTop: 20, borderTop: `1px solid ${color.divider}`, paddingTop: 16, display: "flex", flexDirection: "column", gap: 14 }}>
          <Field label="Resultado del estudio">
            <Select value={resultado} onChange={(e) => setResultado(e.target.value)}>
              <option value="">— Sin especificar —</option>
              <option value="normal">Normal</option>
              <option value="alterado">Alterado</option>
            </Select>
          </Field>
          <Field label="Archivo del estudio (opcional)">
            <CampoArchivo value={archivo} onChange={setArchivo} />
          </Field>
        </div>
      ) : (
        /* Quien ATIENDE puede pedir estudios, interconsultas y recetas. */
        <div style={{ marginTop: 20, borderTop: `1px solid ${color.divider}`, paddingTop: 16, display: "flex", flexDirection: "column", gap: 18 }}>
          <div>
            <div style={tituloSec}>Solicitar estudio</div>
            <div style={{ display: "flex", gap: 8 }}>
              <Input value={tipoEstudio} onChange={(e) => setTipoEstudio(e.target.value)} placeholder="Ej.: Radiografía de tórax" onKeyDown={(e) => e.key === "Enter" && solicitarEstudio()} />
              <Button variant="secondary" disabled={accionando || !tipoEstudio.trim()} onClick={solicitarEstudio}>Solicitar</Button>
            </div>
            <div style={{ marginTop: 8 }}>
              <Select value={areaEstudio} onChange={(e) => setAreaEstudio(e.target.value)} style={{ height: 36 }}>
                <option value="">Registrar en la HC (sin derivar)</option>
                {areasDestino.map((a) => <option key={a.id} value={a.id}>Derivar a {a.nombre} (el caso espera la vuelta)</option>)}
              </Select>
            </div>
            {estudios.length > 0 && (
              <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 10 }}>
                {estudios.map((e) => (
                  <div key={e.id} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, fontSize: 13, background: color.subtle, border: `1px solid ${color.border}`, borderRadius: 8, padding: "7px 11px" }}>
                    <span style={{ color: color.slate700 }}>{e.tipo}{e.resultado_display ? ` · ${e.resultado_display}` : ""}</span>
                    <Badge tone={e.realizado ? "green" : "amber"}>{e.realizado ? "realizado" : "pendiente"}</Badge>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div>
            <div style={tituloSec}>Interconsulta a otra área</div>
            <Input value={motivoIc} onChange={(e) => setMotivoIc(e.target.value)} placeholder="Motivo (ej.: descartar foco neurológico)" />
            <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
              <Select value={areaIc} onChange={(e) => setAreaIc(e.target.value)} style={{ height: 36 }}>
                <option value="">— Elegir área —</option>
                {areasDestino.map((a) => <option key={a.id} value={a.id}>{a.nombre}</option>)}
              </Select>
              <Button variant="secondary" disabled={accionando || !areaIc} onClick={pedirInterconsulta}>Derivar y esperar</Button>
            </div>
          </div>

          <Accion
            label="Emitir receta"
            placeholder="Medicación / indicaciones"
            value={detalleReceta}
            onChange={setDetalleReceta}
            onAdd={emitirReceta}
            disabled={accionando}
            items={recetas.map((r) => ({ id: r.id, txt: r.detalle, tag: r.activa ? "activa" : "" }))}
            vacio="Sin recetas."
          />
        </div>
      )}

      <div style={{ marginTop: 20 }}>
        <Button disabled={accionando} onClick={() => ejecutar(registrar)}>
          {accionando ? "Registrando…" : realizandoEstudio ? "Cargar resultado y cerrar" : "Registrar atención y avanzar"}
        </Button>
      </div>
    </Card>
  );
}

// Sección reutilizable: input + botón "Agregar" y lista de lo ya cargado.
function Accion({ label, placeholder, value, onChange, onAdd, disabled, items, vacio }) {
  return (
    <div>
      <div style={{ fontSize: 12.5, fontWeight: 700, color: color.slate600, marginBottom: 8 }}>{label}</div>
      <div style={{ display: "flex", gap: 8 }}>
        <Input value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} onKeyDown={(e) => e.key === "Enter" && onAdd()} />
        <Button variant="secondary" disabled={disabled || !value.trim()} onClick={onAdd}>Agregar</Button>
      </div>
      {items.length === 0 ? (
        <div style={{ fontSize: 12, color: color.slate400, marginTop: 8 }}>{vacio}</div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 10 }}>
          {items.map((it) => (
            <div key={it.id} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, fontSize: 13, background: color.subtle, border: `1px solid ${color.border}`, borderRadius: 8, padding: "7px 11px" }}>
              <span style={{ color: color.slate700 }}>{it.txt}</span>
              {it.tag && <Badge tone="neutral">{it.tag}</Badge>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function PasoSimple({ caso, accionando, ejecutar, titulo, texto, accion }) {
  return (
    <Card style={{ padding: 24 }}>
      <PanelHeader tipo={caso.nodo_tipo} titulo={caso.paso_actual || titulo} />
      <p style={{ fontSize: 13.5, color: color.slate500, marginBottom: 16 }}>{texto}</p>
      <Button disabled={accionando} onClick={() => ejecutar(() => api.post(`/casos/${caso.id}/avanzar/`, {}))}>
        {accionando ? "Procesando…" : accion}
      </Button>
    </Card>
  );
}

// --------------------------------------------------------------------------- //
function SectionTitle({ children }) {
  return <div style={{ fontSize: 16, fontWeight: 700 }}>{children}</div>;
}
function Dato({ k, v }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, fontSize: 13.5 }}>
      <span style={{ color: color.slate500 }}>{k}</span>
      <span style={{ fontWeight: 500, color: color.slate900, textAlign: "right" }}>{v}</span>
    </div>
  );
}

function Timeline({ eventos }) {
  if (eventos.length === 0)
    return <div style={{ fontSize: 13, color: color.slate400, marginTop: 12 }}>Sin eventos todavía.</div>;
  return (
    <div style={{ marginTop: 14, display: "flex", flexDirection: "column" }}>
      {eventos.map((e, i) => (
        <div key={e.id} style={{ display: "flex", gap: 11 }}>
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
            <span style={{ width: 11, height: 11, borderRadius: "50%", background: color.accent, border: "2.5px solid #fff", boxShadow: `0 0 0 1.5px ${color.accent}55`, flex: "none", marginTop: 3 }} />
            {i < eventos.length - 1 && <span style={{ flex: 1, width: 2, background: color.divider, margin: "2px 0" }} />}
          </div>
          <div style={{ paddingBottom: 16 }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: color.slate700 }}>{e.titulo}</div>
            {e.detalle && <div style={{ fontSize: 12, color: color.slate500, marginTop: 1 }}>{e.detalle}</div>}
            <div style={{ fontSize: 11, color: color.slate400, marginTop: 2 }}>
              {e.autor_nombre} · {fechaHora(e.fecha)}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
