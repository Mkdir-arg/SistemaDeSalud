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
  const [areaSel, setAreaSel] = useState(null); // área elegida en el lanzador

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
  const d = data || { iniciar: [], tareas: [], filas: [], esperando: [], puestos: [], turno: null };
  const puestos = d.puestos || [];
  const turno = d.turno || null;
  const vacio = !d.iniciar.length && !d.tareas.length && !d.filas.length && !d.esperando.length && !puestos.length;

  // Áreas donde trabajás → el lanzador. Con una sola, entrás directo (sin tarjetas).
  const areas = [...new Set(
    [...d.iniciar, ...d.tareas, ...d.filas, ...d.esperando, ...puestos].map((x) => x.area_nombre).filter(Boolean)
  )].sort();
  const multi = areas.length > 1;
  const areaActiva = (areaSel && areas.includes(areaSel)) ? areaSel : (multi ? null : areas[0] || null);

  const filtrarArea = (a) => ({
    iniciar: d.iniciar.filter((x) => x.area_nombre === a),
    tareas: d.tareas.filter((x) => x.area_nombre === a),
    filas: d.filas.filter((x) => x.area_nombre === a),
    esperando: d.esperando.filter((x) => x.area_nombre === a),
    puestos: puestos.filter((x) => x.area_nombre === a),
  });
  const resumenArea = (a) => {
    const ps = puestos.filter((x) => x.area_nombre === a);
    return {
      pasos: ps.length,
      ahora: ps.reduce((s, p) => s + (p.ahora || 0), 0),
      urgentes: ps.reduce((s, p) => s + (p.urgentes || 0), 0),
      encola: d.filas.filter((x) => x.area_nombre === a).reduce((s, f) => s + (f.en_cola || 0), 0),
      iniciar: d.iniciar.some((x) => x.area_nombre === a),
    };
  };

  // Las bandas de trabajo de un conjunto de datos (una sola área, o todo).
  const bandas = (dd) => {
    const afilas = [...new Map(dd.filas.map((f) => [f.area_id, f])).values()];
    return (
      <>
        {dd.puestos.length > 0 && (
          <Seccion titulo="Mis puestos">
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: 12 }}>
              {dd.puestos.map((p) => <PuestoCard key={p.nodo_id} p={p} />)}
            </div>
          </Seccion>
        )}
        {afilas.length > 0 && (
          <Seccion titulo="Tu box">
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {afilas.map((f) => <BoxBar key={f.area_id} f={f} recargar={() => cargar(true)} />)}
            </div>
          </Seccion>
        )}
        {dd.iniciar.length > 0 && (
          <Seccion titulo="Iniciar">
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(270px, 1fr))", gap: 12 }}>
              {dd.iniciar.map((it) => (
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
        {dd.tareas.length > 0 && (
          <Seccion titulo="Para hacer ahora">
            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              {dd.tareas.map((b) => (
                <TareaCard key={b.nodo_id} b={b} accion={accion}
                  onAbrir={(id) => navigate(`/casos/${id}`)} onTomar={tomarYAbrir} />
              ))}
            </div>
          </Seccion>
        )}
        {dd.filas.length > 0 && (
          <Seccion titulo="Mis filas">
            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              {dd.filas.map((f) => (
                <FilaCard key={f.nodo_id} f={f} onLlamado={(id) => navigate(`/casos/${id}`)} recargar={() => cargar(true)} />
              ))}
            </div>
          </Seccion>
        )}
        {dd.esperando.length > 0 && (
          <Seccion titulo="Esperando resultados">
            <Card style={{ overflow: "hidden" }}>
              {dd.esperando.map((c, i) => (
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
      </>
    );
  };

  return (
    <>
      <PageHeader
        subtitle={areaActiva && multi ? areaActiva : "Lo que podés iniciar y lo que está esperando por vos."}
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

      <div style={{ padding: "22px 32px", display: "flex", flexDirection: "column", gap: 26 }}>
        {vacio && (
          <EmptyState title="No tenés tareas pendientes" hint="Cuando entren casos a los pasos que operás, van a aparecer acá." />
        )}

        {/* TU TURNO — producción personal del día (siempre visible si tenés puestos). */}
        {turno && puestos.length > 0 && <TurnoBanner turno={turno} esperando={d.esperando.length} />}

        {!vacio && (areaActiva ? (
          <>
            {multi && (
              <button onClick={() => setAreaSel(null)}
                style={{ alignSelf: "flex-start", border: "none", background: "none", color: color.accent, fontSize: 13, fontWeight: 600, cursor: "pointer", padding: 0, display: "flex", alignItems: "center", gap: 6 }}>
                <Icon name="back" size={14} /> Áreas
              </button>
            )}
            {bandas(filtrarArea(areaActiva))}
          </>
        ) : (
          <Seccion titulo="Mis áreas">
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 14 }}>
              {areas.map((a) => <AreaCard key={a} area={a} resumen={resumenArea(a)} onEnter={() => setAreaSel(a)} />)}
            </div>
          </Seccion>
        ))}

        {/* MIS CASOS EN CURSO — lo que tengo a mi nombre, para retomar (solo en el inicio). */}
        {!areaSel && (d.mis_casos || []).length > 0 && (
          <Seccion titulo="Mis casos en curso">
            <Card style={{ overflow: "hidden" }}>
              {d.mis_casos.map((c, i) => (
                <div key={c.id} onClick={() => navigate(`/casos/${c.id}`)}
                  style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px 16px", cursor: "pointer", borderTop: i ? `1px solid ${color.divider}` : "none" }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = color.subtle)}
                  onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}>
                  <PrioridadDot prioridad={c.prioridad} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 13.5, fontWeight: 600 }}>{c.ciudadano_nombre || "—"}</div>
                    <div style={{ fontSize: 12, color: color.slate400 }}>
                      {[c.paso_actual, c.area_nombre, c.flujo_titulo].filter(Boolean).join(" · ")}
                    </div>
                  </div>
                  {c.esperando
                    ? <Badge tone="amber">Esperando</Badge>
                    : <span style={{ fontSize: 12, color: color.slate400 }}>{c.estado_display}</span>}
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

// Tarjeta de área en el lanzador de "Mi trabajo": resumen + entrar.
function AreaCard({ area, resumen: r, onEnter }) {
  return (
    <Card
      onClick={onEnter}
      style={{ padding: 16, cursor: "pointer", display: "flex", flexDirection: "column", gap: 12, borderLeft: `3px solid ${r.urgentes > 0 ? color.danger : color.border}`, transition: "box-shadow .12s" }}
      onMouseEnter={(e) => (e.currentTarget.style.boxShadow = "0 6px 18px rgba(16,24,40,.08)")}
      onMouseLeave={(e) => (e.currentTarget.style.boxShadow = "none")}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <div style={{ width: 34, height: 34, borderRadius: 9, background: color.accent50, color: color.accent, display: "flex", alignItems: "center", justifyContent: "center", flex: "none" }}>
          <Icon name="building" size={18} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 15, fontWeight: 700, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{area}</div>
          <div style={{ fontSize: 12, color: color.slate400 }}>{r.pasos} paso{r.pasos !== 1 ? "s" : ""}</div>
        </div>
        {r.urgentes > 0 && <Badge tone="error">{r.urgentes} urg.</Badge>}
      </div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 18, fontSize: 12.5, color: color.slate500 }}>
        <span><strong style={{ fontSize: 18, color: r.ahora > 0 ? color.ink : color.slate400 }}>{r.ahora}</strong> pendientes</span>
        {r.encola > 0 && <span><strong style={{ fontSize: 18, color: color.ink }}>{r.encola}</strong> en cola</span>}
      </div>
      <div style={{ display: "flex", alignItems: "center" }}>
        {r.iniciar && <span style={{ fontSize: 12, color: color.slate400 }}>+ Ingresar disponible</span>}
        <span style={{ marginLeft: "auto", fontSize: 13, fontWeight: 600, color: color.accent }}>Entrar →</span>
      </div>
    </Card>
  );
}

const subPaso = (b) => {
  const base = [b.flujo_titulo, b.area_nombre].filter(Boolean).join(" · ");
  return b.grupos?.length ? `${base} · 👥 ${b.grupos.join(", ")}` : base;
};

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
      {abierto && (b.casos.length === 0 ? (
        <div style={{ padding: "14px 16px", fontSize: 12.5, color: color.slate400, borderTop: `1px solid ${color.divider}` }}>
          Sin casos por ahora.
        </div>
      ) : b.casos.map((c) => (
        <FilaCaso key={c.id} c={c} cargando={accion === c.id}
          onAbrir={() => onAbrir(c.id)} onTomar={() => onTomar(c)} />
      )))}
    </Card>
  );
}

function PrioridadDot({ prioridad }) {
  const c = prioridad === "urgente" ? color.danger : prioridad === "alta" ? "#A96A12" : "#D0D5DD";
  return <span title={prioridad} style={{ width: 9, height: 9, borderRadius: 99, background: c, flex: "none" }} />;
}

// Chip de prioridad: solo se muestra cuando aporta (urgente / alta).
const PRIO_CHIP = { urgente: { label: "Urgente", tone: "error" }, alta: { label: "Alta", tone: "amber" } };
function PrioridadChip({ prioridad }) {
  const p = PRIO_CHIP[prioridad];
  return p ? <Badge tone={p.tone}>{p.label}</Badge> : null;
}

// "Tu turno": lo que hiciste hoy y lo que tenés en curso, de un vistazo. Pensado
// para roles sin cola propia (admisión): aun sin nada en pantalla, ves tu pulso.
function TurnoBanner({ turno, esperando }) {
  const stats = [
    { label: "Resueltos hoy", n: turno.resueltos_hoy, c: "#1B7A4E" },
    { label: "En curso", n: turno.en_curso, c: color.accent },
    ...(esperando > 0 ? [{ label: "Esperando resultados", n: esperando, c: "#A96A12" }] : []),
  ];
  return (
    <Card style={{ padding: "14px 18px", display: "flex", alignItems: "center", gap: 22, flexWrap: "wrap" }}>
      <div style={{ flex: 1, minWidth: 160 }}>
        <div style={{ fontSize: 14, fontWeight: 700 }}>Tu turno</div>
        <div style={{ fontSize: 12.5, color: color.slate400 }}>
          {turno.ultimo_at ? <>Último movimiento <EsperaChip iso={turno.ultimo_at} prefijo="hace " /></> : "Todavía sin movimientos hoy"}
        </div>
      </div>
      <div style={{ display: "flex", gap: 26 }}>
        {stats.map((s) => (
          <div key={s.label} style={{ textAlign: "center" }}>
            <div style={{ fontSize: 24, fontWeight: 800, lineHeight: 1, color: s.c }}>{s.n}</div>
            <div style={{ fontSize: 11.5, color: color.slate500, marginTop: 5 }}>{s.label}</div>
          </div>
        ))}
      </div>
    </Card>
  );
}

// Tarjeta-indicador de un puesto (nodo del que soy responsable): carga del momento
// + lo resuelto hoy. No es accionable: los casos se operan en las bandas de abajo.
const PUESTO_ICON = { entrada: "enter", fila: "list", tarea: "inbox" };
function PuestoCard({ p }) {
  const t = p.desde ? tonoEspera(p.desde) : null;
  return (
    <Card style={{ padding: 14, display: "flex", flexDirection: "column", gap: 12, borderLeft: `3px solid ${p.urgentes > 0 ? color.danger : color.border}` }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <div style={{ width: 30, height: 30, borderRadius: 8, background: color.accent50, color: color.accent, display: "flex", alignItems: "center", justifyContent: "center", flex: "none" }}>
          <Icon name={PUESTO_ICON[p.rol] || "inbox"} size={15} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 13.5, fontWeight: 700, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{p.nodo_titulo}</div>
          <div style={{ fontSize: 12, color: color.slate400, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
            {[p.flujo_titulo, p.area_nombre].filter(Boolean).join(" · ")}
          </div>
        </div>
        {p.urgentes > 0 && <Badge tone="error">{p.urgentes} urg.</Badge>}
      </div>
      <div style={{ display: "flex", alignItems: "flex-end", gap: 22 }}>
        <div>
          <div style={{ fontSize: 24, fontWeight: 800, lineHeight: 1, color: p.ahora > 0 ? color.ink : color.slate400 }}>{p.ahora}</div>
          <div style={{ fontSize: 11.5, color: color.slate500, marginTop: 5 }}>{p.rol === "fila" ? "en cola" : "ahora"}</div>
        </div>
        <div>
          <div style={{ fontSize: 24, fontWeight: 800, lineHeight: 1, color: color.slate600 }}>{p.hoy}</div>
          <div style={{ fontSize: 11.5, color: color.slate500, marginTop: 5 }}>hoy</div>
        </div>
        {p.desde && (
          <div style={{ flex: 1, textAlign: "right", fontSize: 12 }}>
            <EsperaChip iso={p.desde} prefijo="+ antiguo · " />
          </div>
        )}
      </div>
    </Card>
  );
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
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 13.5, fontWeight: 600 }}>{c.ciudadano_nombre || "Sin paciente"}</span>
          <PrioridadChip prioridad={c.prioridad} />
        </div>
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

// Banda "Tu box": el profesional elige/ocupa su consultorio para un área (lo primero).
function BoxBar({ f, recargar }) {
  const [boxSel, setBoxSel] = useState(() => { const lib = f.boxes.find((b) => !b.ocupado_por); return lib ? String(lib.id) : ""; });
  const [ocupando, setOcupando] = useState(false);
  const miBox = f.boxes.find((b) => b.id === f.mi_box) || null;

  async function ocupar() {
    if (!boxSel) return;
    setOcupando(true);
    try { await api.post(`/boxes/${boxSel}/ocupar/`); recargar(); } finally { setOcupando(false); }
  }
  async function salir() {
    if (!f.mi_box) return;
    setOcupando(true);
    try { await api.post(`/boxes/${f.mi_box}/liberar/`); recargar(); } finally { setOcupando(false); }
  }

  return (
    <Card style={{ padding: 16, display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", borderLeft: `3px solid ${miBox ? "#1B7A4E" : color.accent}` }}>
      <div style={{ width: 34, height: 34, borderRadius: 9, background: miBox ? "#E6F5EC" : color.accent50, color: miBox ? "#1B7A4E" : color.accent, display: "flex", alignItems: "center", justifyContent: "center", flex: "none" }}>
        <Icon name="cube" size={18} />
      </div>
      <div style={{ flex: 1, minWidth: 160 }}>
        <div style={{ fontSize: 14, fontWeight: 700 }}>{f.area_nombre}</div>
        <div style={{ fontSize: 12.5, color: color.slate400 }}>
          {miBox ? <>Atendiendo en <strong style={{ color: "#1B7A4E" }}>{miBox.nombre}</strong></> : "Elegí tu box para empezar a llamar pacientes"}
        </div>
      </div>
      {miBox ? (
        <Button variant="secondary" disabled={ocupando} onClick={salir}>Salir del box</Button>
      ) : f.boxes.length === 0 ? (
        <span style={{ fontSize: 13, color: color.slate400 }}>El área no tiene boxes configurados.</span>
      ) : (
        <>
          <Select value={boxSel} onChange={(e) => setBoxSel(e.target.value)} style={{ maxWidth: 220 }}>
            {f.boxes.map((b) => (
              <option key={b.id} value={b.id} disabled={!!b.ocupado_por}>
                {b.nombre}{b.ocupado_por ? ` · ocupado por ${b.ocupado_por_nombre}` : ""}
              </option>
            ))}
          </Select>
          <Button disabled={!boxSel || ocupando} onClick={ocupar}>{ocupando ? "…" : "Ocupar box"}</Button>
        </>
      )}
    </Card>
  );
}

function FilaCard({ f, onLlamado }) {
  const [llamando, setLlamando] = useState(null); // id del caso que se está llamando
  const [abierto, setAbierto] = useState(true);
  const siguiente = f.casos[0];
  const enCurso = llamando !== null;

  async function llamar(caso) {
    if (!caso || !f.mi_box) return;
    setLlamando(caso.id);
    try { await api.post(`/casos/${caso.id}/llamar/`, { box_id: f.mi_box }); onLlamado(caso.id); }
    finally { setLlamando(null); }
  }

  return (
    <Card style={{ overflow: "hidden" }}>
      <div onClick={() => setAbierto((v) => !v)} style={{ cursor: "pointer" }}>
        <CabeceraPaso icon="list" titulo={f.nodo_titulo} sub={[f.flujo_titulo, f.area_nombre].filter(Boolean).join(" · ")} total={f.en_cola} urgentes={f.urgentes} totalLabel="en cola" desde={masViejo(f.casos.map((c) => c.ingreso))} abierto={abierto} />
      </div>

      {/* Llamar al siguiente (usa el box que ocupaste arriba). */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "12px 16px", borderTop: `1px solid ${color.divider}`, background: color.subtle }}>
        {f.mi_box ? (
          <Button disabled={!siguiente || enCurso} onClick={() => llamar(siguiente)}>
            {llamando === siguiente?.id ? "Llamando…" : siguiente ? `Llamar siguiente${siguiente.ciudadano_nombre ? " · " + siguiente.ciudadano_nombre : ""}` : "Sin pacientes en cola"}
          </Button>
        ) : (
          <span style={{ fontSize: 13, color: color.slate400 }}>Ocupá tu box (arriba, en «Tu box») para poder llamar.</span>
        )}
      </div>

      {abierto && f.casos.slice(0, 6).map((c, i) => {
        const t = tonoEspera(c.ingreso);
        return (
          <div key={c.item_id} style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 16px 8px 13px", borderTop: `1px solid ${color.divider}`, borderLeft: `3px solid ${t.demorado ? t.color : "transparent"}` }}>
            <span style={{ fontSize: 12, color: color.slate400, width: 18, textAlign: "right" }}>{i + 1}</span>
            <PrioridadDot prioridad={c.prioridad || (c.urgente ? "urgente" : "normal")} />
            <div style={{ flex: 1, fontSize: 13.5, minWidth: 0, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{c.ciudadano_nombre || "—"}</div>
            <span style={{ fontSize: 12 }}><EsperaChip iso={c.ingreso} /></span>
            <Button variant="secondary" style={{ height: 28, padding: "0 12px", fontSize: 12 }} disabled={enCurso || !f.mi_box} title={!f.mi_box ? "Ocupá un box primero" : ""} onClick={() => llamar(c)}>
              {llamando === c.id ? "…" : "Llamar"}
            </Button>
          </div>
        );
      })}
      {abierto && f.casos.length === 0 && (
        <div style={{ padding: "16px", textAlign: "center", fontSize: 12.5, color: color.slate400, borderTop: `1px solid ${color.divider}` }}>
          Nadie esperando en la sala por ahora.
        </div>
      )}
    </Card>
  );
}

// Alta de un paciente sobre un flujo manual: buscador → si existe lo elegís,
// si no, formulario breve para crearlo.
function IngresarPacienteModal({ item, institucionId, onClose, onCreated }) {
  const [q, setQ] = useState("");
  const [resultados, setResultados] = useState([]);
  const [buscando, setBuscando] = useState(false);
  const [seleccionado, setSeleccionado] = useState(null);
  const [creandoNuevo, setCreandoNuevo] = useState(false);
  const [nuevo, setNuevo] = useState({ nombre: "", apellido: "", documento: "" });
  const [prioridad, setPrioridad] = useState("normal");
  const [guardando, setGuardando] = useState(false);
  const setN = (k, v) => setNuevo((p) => ({ ...p, [k]: v }));

  // Búsqueda con debounce (mientras no haya paciente elegido ni form abierto).
  useEffect(() => {
    if (seleccionado || creandoNuevo) return;
    const term = q.trim();
    if (!term) { setResultados([]); return; }
    setBuscando(true);
    const t = setTimeout(async () => {
      try {
        const d = await api.get(`/ciudadanos/?institucion=${institucionId}&search=${encodeURIComponent(term)}`);
        setResultados(d.results || d);
      } finally { setBuscando(false); }
    }, 300);
    return () => clearTimeout(t);
  }, [q, institucionId, seleccionado, creandoNuevo]);

  function abrirCrear() {
    const partes = q.trim().split(/\s+/);
    setNuevo({ nombre: partes[0] || "", apellido: partes.slice(1).join(" "), documento: "" });
    setCreandoNuevo(true);
  }

  async function crearYSeleccionar() {
    if (!nuevo.nombre.trim() || guardando) return;
    setGuardando(true);
    try {
      const c = await api.post("/ciudadanos/", {
        institucion: institucionId,
        nombre: nuevo.nombre.trim(), apellido: nuevo.apellido.trim(), documento: nuevo.documento.trim(),
      });
      setSeleccionado(c);
      setCreandoNuevo(false);
    } finally { setGuardando(false); }
  }

  async function ingresar() {
    if (!seleccionado || guardando) return;
    setGuardando(true);
    try {
      const caso = await api.post("/casos/", {
        institucion: institucionId, version: item.version_id, ciudadano: seleccionado.id, prioridad,
      });
      await api.post(`/casos/${caso.id}/iniciar/`);
      onCreated(caso.id);
    } finally { setGuardando(false); }
  }

  let footer;
  if (seleccionado) {
    footer = (<>
      <Button variant="secondary" onClick={onClose}>Cancelar</Button>
      <Button disabled={guardando} onClick={ingresar}>{guardando ? "Ingresando…" : "Ingresar e iniciar"}</Button>
    </>);
  } else if (creandoNuevo) {
    footer = (<>
      <Button variant="secondary" onClick={() => setCreandoNuevo(false)}>Volver</Button>
      <Button disabled={!nuevo.nombre.trim() || guardando} onClick={crearYSeleccionar}>{guardando ? "Creando…" : "Crear y continuar"}</Button>
    </>);
  } else {
    footer = <Button variant="secondary" onClick={onClose}>Cancelar</Button>;
  }

  return (
    <Modal title={`Ingresar paciente · ${item.flujo_titulo}`} onClose={onClose} footer={footer}>
      {seleccionado ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12, padding: 14, border: `1px solid ${color.border}`, borderRadius: 10, background: color.subtle }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 14.5, fontWeight: 700 }}>{seleccionado.nombre} {seleccionado.apellido}</div>
              <div style={{ fontSize: 12.5, color: color.slate400 }}>
                {seleccionado.documento ? `Doc. ${seleccionado.documento}` : "Sin documento"}{seleccionado.obra_social ? ` · ${seleccionado.obra_social}` : ""}
              </div>
            </div>
            <button onClick={() => { setSeleccionado(null); setResultados([]); }} style={{ border: "none", background: "none", color: color.accent, fontSize: 12.5, fontWeight: 600, cursor: "pointer" }}>Cambiar</button>
          </div>
          <Field label="Prioridad">
            <Select value={prioridad} onChange={(e) => setPrioridad(e.target.value)}>
              <option value="normal">Normal</option>
              <option value="alta">Alta</option>
              <option value="urgente">Urgente</option>
            </Select>
          </Field>
        </div>
      ) : creandoNuevo ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <div style={{ fontSize: 12.5, color: color.slate500, marginBottom: 2 }}>Nuevo paciente</div>
          <Input placeholder="Nombre *" value={nuevo.nombre} onChange={(e) => setN("nombre", e.target.value)} autoFocus />
          <Input placeholder="Apellido" value={nuevo.apellido} onChange={(e) => setN("apellido", e.target.value)} />
          <Input placeholder="Documento" value={nuevo.documento} onChange={(e) => setN("documento", e.target.value)} />
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <Field label="Buscar paciente">
            <Input autoFocus placeholder="Nombre, apellido o documento…" value={q} onChange={(e) => setQ(e.target.value)} />
          </Field>
          {q.trim() ? (
            <div style={{ border: `1px solid ${color.border}`, borderRadius: 10, overflow: "hidden" }}>
              {buscando ? (
                <div style={{ padding: 14, fontSize: 13, color: color.slate400 }}>Buscando…</div>
              ) : resultados.length > 0 ? (
                resultados.map((c, i) => (
                  <div key={c.id} onClick={() => setSeleccionado(c)}
                    style={{ padding: "10px 14px", cursor: "pointer", borderTop: i ? `1px solid ${color.divider}` : "none" }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = color.subtle)}
                    onMouseLeave={(e) => (e.currentTarget.style.background = "#fff")}>
                    <div style={{ fontSize: 13.5, fontWeight: 600 }}>{c.nombre} {c.apellido}</div>
                    <div style={{ fontSize: 12, color: color.slate400 }}>{c.documento ? `Doc. ${c.documento}` : "Sin documento"}</div>
                  </div>
                ))
              ) : (
                <div style={{ padding: 14, display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10 }}>
                  <span style={{ fontSize: 13, color: color.slate500 }}>Sin coincidencias para «{q.trim()}»</span>
                  <Button style={{ height: 32, padding: "0 12px" }} onClick={abrirCrear}>+ Crear nuevo</Button>
                </div>
              )}
            </div>
          ) : (
            <div style={{ fontSize: 12.5, color: color.slate400 }}>Escribí para buscar al paciente. Si no existe, lo creás al toque.</div>
          )}
        </div>
      )}
    </Modal>
  );
}
