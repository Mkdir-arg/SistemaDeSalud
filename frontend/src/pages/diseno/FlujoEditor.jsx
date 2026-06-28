import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../../api/client";
import { Badge, Button, Checkbox, Field, Input, Select, Spinner } from "../../components/ui";
import { Icon } from "../../components/icons";
import { caminoPorDefecto, correrAuto, nodoInicio, siguiente } from "../../lib/simular";
import { badgeTone, color, estadoCaso, estadoVersion, nodeCat, radius, shadow, type } from "../../theme";

const NODO_W = 184;
const NODO_H = 64;
const GRID = 20; // paso de la grilla de puntos del lienzo (para snap-to-grid)
const PALETA = Object.entries(nodeCat).map(([tipo, c]) => ({ tipo, ...c }));

// Operadores de regla en lenguaje natural (los usa el RuleBuilder y la etiqueta
// automática de las ramas de Decisión en el lienzo).
const OPERADOR_LABEL = { "=": "es igual a", "!=": "es distinto de", ">": "mayor que", "<": "menor que", contiene: "contiene" };

export default function FlujoEditor() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [flujo, setFlujo] = useState(null);
  const [version, setVersion] = useState(null); // versión completa (nodos+conexiones)
  const [verId, setVerId] = useState(null);
  const [sel, setSel] = useState(null); // id de nodo seleccionado
  const [selConexion, setSelConexion] = useState(null); // id de conexión seleccionada en el lienzo
  const [hoverConn, setHoverConn] = useState(null); // id de conexión bajo el cursor
  const [problemas, setProblemas] = useState(null);
  const [conectarDesde, setConectarDesde] = useState(null);
  const [campos, setCampos] = useState([]); // campos disponibles para reglas
  const [cargando, setCargando] = useState(true);
  const [errorCarga, setErrorCarga] = useState(null);
  const [sim, setSim] = useState(null); // modo Probar: {current, valores, camino, fin}
  const [repro, setRepro] = useState(null); // Reproducir: {camino, idx}
  const [guardado, setGuardado] = useState("idle"); // idle | guardando | guardado | error
  const [toast, setToast] = useState(null); // { tipo:'ok'|'error', msg, accion?:{label,fn} }
  const [publicando, setPublicando] = useState(false);
  const [validando, setValidando] = useState(false);
  const guardadoTimer = useRef(null);
  const toastTimer = useRef(null);

  // Indicador de autosave (barra superior) + feedback de error de red.
  function marcarGuardando() { setGuardado("guardando"); }
  function marcarGuardado() {
    setGuardado("guardado");
    clearTimeout(guardadoTimer.current);
    guardadoTimer.current = setTimeout(() => setGuardado("idle"), 1800);
  }
  function mostrarToast(t, ms = 4000) {
    clearTimeout(toastTimer.current);
    setToast(t);
    toastTimer.current = setTimeout(() => setToast(null), ms);
  }
  function marcarError() {
    setGuardado("error");
    mostrarToast({ tipo: "error", msg: "No se pudo guardar. Revisá tu conexión e intentá de nuevo." });
  }

  const cargarVersion = useCallback(async (vid) => {
    const v = await api.get(`/versiones-flujo/${vid}/`);
    setVersion(v);
  }, []);

  const cargarTodo = useCallback(async () => {
    setCargando(true);
    setErrorCarga(null);
    try {
      const f = await api.get(`/flujos/${id}/`);
      setFlujo(f);
      const v = (f.versiones || [])[0];
      if (v) {
        setVerId(v.id);
        await cargarVersion(v.id);
      }
      // Campos disponibles para reglas: los de los formularios de la institución.
      const fs = await api.get(`/formularios/?institucion=${f.institucion}`);
      const lista = (fs.results || fs).flatMap((form) =>
        (form.campos || []).map((c) => ({ id: c.id, label: c.label, formulario: form.titulo, formularioId: form.id, opciones: c.opciones, tipo: c.tipo, requerido: c.requerido }))
      );
      setCampos(lista);
    } catch (e) {
      setErrorCarga(e?.data?.detail || e?.message || "No se pudo cargar el flujo.");
    } finally {
      setCargando(false);
    }
  }, [id, cargarVersion]);

  useEffect(() => {
    cargarTodo();
  }, [cargarTodo]);

  // --- Drag de nodos (Pointer Events: mouse + touch + lápiz) ---------------
  const drag = useRef(null);
  const canvasRef = useRef(null);
  // Ref con la versión actual: el listener se monta una sola vez y lee de acá,
  // así no re-suscribimos en cada movimiento ni quedan listeners colgados.
  const versionRef = useRef(version);
  versionRef.current = version;
  const [dragId, setDragId] = useState(null);
  // Arrastre de conexión desde el handle de salida de un nodo (línea-fantasma).
  const conn = useRef(null);
  const [ghost, setGhost] = useState(null); // { x1, y1, x2, y2 }
  // Zoom del lienzo (0.4–1.6). zoomRef permite leerlo desde los listeners de
  // puntero montados una sola vez sin re-suscribir.
  const [zoom, setZoom] = useState(1);
  const zoomRef = useRef(1);
  zoomRef.current = zoom;
  const scrollRef = useRef(null);

  function onNodoPointerDown(e, nodo) {
    e.stopPropagation();
    if (e.button != null && e.button !== 0) return; // solo botón primario
    const rect = canvasRef.current.getBoundingClientRect();
    const z = zoomRef.current;
    drag.current = {
      id: nodo.id,
      dx: (e.clientX - rect.left) / z - nodo.x,
      dy: (e.clientY - rect.top) / z - nodo.y,
      moved: false,
    };
    setSel(nodo.id);
    setDragId(nodo.id);
    try { e.currentTarget.setPointerCapture(e.pointerId); } catch { /* no soportado */ }
  }

  useEffect(() => {
    function onMove(e) {
      if (!drag.current) return;
      const rect = canvasRef.current.getBoundingClientRect();
      const z = zoomRef.current;
      const x = Math.max(0, (e.clientX - rect.left) / z - drag.current.dx);
      const y = Math.max(0, (e.clientY - rect.top) / z - drag.current.dy);
      drag.current.moved = true;
      setVersion((v) => ({ ...v, nodos: v.nodos.map((n) => (n.id === drag.current.id ? { ...n, x, y } : n)) }));
    }
    async function onUp() {
      if (!drag.current) return;
      const id = drag.current.id;
      const moved = drag.current.moved;
      drag.current = null;
      setDragId(null);
      if (!moved) return;
      const nodo = versionRef.current?.nodos.find((n) => n.id === id);
      if (!nodo) return;
      // Snap a la grilla de 20px que dibuja el lienzo: flujos prolijos sin esfuerzo.
      const sx = Math.round(nodo.x / GRID) * GRID;
      const sy = Math.round(nodo.y / GRID) * GRID;
      setVersion((v) => ({ ...v, nodos: v.nodos.map((n) => (n.id === id ? { ...n, x: sx, y: sy } : n)) }));
      try { await api.patch(`/nodos/${id}/`, { x: sx, y: sy }); } catch { marcarError(); }
    }
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
  }, []);

  // Inicia el arrastre de una conexión desde el handle de salida de un nodo.
  function onHandlePointerDown(e, nodo) {
    e.stopPropagation();
    if (e.button != null && e.button !== 0) return;
    conn.current = { fromId: nodo.id };
    const rect = canvasRef.current.getBoundingClientRect();
    const z = zoomRef.current;
    setGhost({ x1: nodo.x + NODO_W, y1: nodo.y + NODO_H / 2, x2: (e.clientX - rect.left) / z, y2: (e.clientY - rect.top) / z });
    try { e.currentTarget.setPointerCapture(e.pointerId); } catch { /* no soportado */ }
  }

  useEffect(() => {
    function onMove(e) {
      if (!conn.current) return;
      const rect = canvasRef.current.getBoundingClientRect();
      const z = zoomRef.current;
      setGhost((g) => (g ? { ...g, x2: (e.clientX - rect.left) / z, y2: (e.clientY - rect.top) / z } : g));
    }
    async function onUp(e) {
      if (!conn.current) return;
      const from = conn.current.fromId;
      conn.current = null;
      setGhost(null);
      const host = document.elementFromPoint(e.clientX, e.clientY)?.closest?.("[data-nodo]");
      const toId = host ? Number(host.getAttribute("data-nodo")) : null;
      if (toId == null || toId === from) return;
      if (versionRef.current.conexiones.some((c) => c.origen === from && c.destino === toId)) return;
      marcarGuardando();
      try {
        const c = await api.post("/conexiones/", { version: verId, origen: from, destino: toId });
        setVersion((v) => ({ ...v, conexiones: [...v.conexiones, c] }));
        marcarGuardado();
      } catch { marcarError(); }
    }
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
  }, [verId]);

  // --- Acciones ------------------------------------------------------------
  // Coloca el nodo nuevo cerca del centro del área visible del lienzo (no
  // apilado en una esquina) y alineado a la grilla.
  function posicionNuevoNodo() {
    const cont = canvasRef.current?.parentElement;
    const off = ((version?.nodos.length || 0) % 5) * GRID;
    const bx = cont ? cont.scrollLeft + cont.clientWidth / 2 - NODO_W / 2 : 360;
    const by = cont ? cont.scrollTop + cont.clientHeight / 2 - NODO_H / 2 : 160;
    return { x: Math.max(0, Math.round((bx + off) / GRID) * GRID), y: Math.max(0, Math.round((by + off) / GRID) * GRID) };
  }

  async function agregarNodo(tipo) {
    const cat = nodeCat[tipo];
    const { x, y } = posicionNuevoNodo();
    marcarGuardando();
    try {
      const n = await api.post("/nodos/", { version: verId, tipo, titulo: cat.name, x, y });
      setVersion((v) => ({ ...v, nodos: [...v.nodos, n] }));
      setSel(n.id);
      marcarGuardado();
    } catch { marcarError(); }
  }

  async function clickNodo(nodo) {
    if (conectarDesde && conectarDesde !== nodo.id) {
      // No duplicar una conexión que ya existe entre ese par.
      if (version.conexiones.some((c) => c.origen === conectarDesde && c.destino === nodo.id)) {
        setConectarDesde(null);
        return;
      }
      const origen = conectarDesde;
      setConectarDesde(null);
      marcarGuardando();
      try {
        const c = await api.post("/conexiones/", { version: verId, origen, destino: nodo.id });
        setVersion((v) => ({ ...v, conexiones: [...v.conexiones, c] }));
        marcarGuardado();
      } catch { marcarError(); }
      return;
    }
    setSel(nodo.id);
  }

  async function actualizarNodo(nodoId, cambios) {
    const prev = version;
    setVersion((v) => ({ ...v, nodos: v.nodos.map((x) => (x.id === nodoId ? { ...x, ...cambios } : x)) }));
    marcarGuardando();
    try {
      const n = await api.patch(`/nodos/${nodoId}/`, cambios);
      setVersion((v) => ({ ...v, nodos: v.nodos.map((x) => (x.id === nodoId ? n : x)) }));
      marcarGuardado();
    } catch { setVersion(prev); marcarError(); }
  }

  async function borrarNodo(nodoId) {
    const nodo = version.nodos.find((n) => n.id === nodoId);
    const conexiones = version.conexiones.filter((c) => c.origen === nodoId || c.destino === nodoId);
    const snapshot = version;
    setVersion((v) => ({
      ...v,
      nodos: v.nodos.filter((n) => n.id !== nodoId),
      conexiones: v.conexiones.filter((c) => c.origen !== nodoId && c.destino !== nodoId),
    }));
    setSel(null);
    if (conectarDesde === nodoId) setConectarDesde(null);
    marcarGuardando();
    try {
      await api.del(`/nodos/${nodoId}/`);
      marcarGuardado();
      mostrarToast({
        tipo: "ok",
        msg: `Se eliminó «${nodo?.titulo}»${conexiones.length ? ` y ${conexiones.length} conexión${conexiones.length > 1 ? "es" : ""}` : ""}.`,
        accion: { label: "Deshacer", fn: () => restaurarNodo(nodo, conexiones) },
      }, 7000);
    } catch { setVersion(snapshot); marcarError(); }
  }

  // Rehace un nodo borrado y sus conexiones (remapeando el id al nuevo nodo).
  async function restaurarNodo(nodo, conexiones) {
    setToast(null);
    marcarGuardando();
    try {
      const n = await api.post("/nodos/", {
        version: verId, tipo: nodo.tipo, titulo: nodo.titulo, descripcion: nodo.descripcion,
        x: nodo.x, y: nodo.y, config: nodo.config || {}, formulario: nodo.formulario, grupos: nodo.grupos || [],
      });
      const nuevas = [];
      for (const c of conexiones) {
        // La otra punta debe seguir existiendo; si no, se omite esa conexión.
        const origen = c.origen === nodo.id ? n.id : c.origen;
        const destino = c.destino === nodo.id ? n.id : c.destino;
        const existe = (gid) => gid === n.id || versionRef.current.nodos.some((x) => x.id === gid);
        if (!existe(origen) || !existe(destino)) continue;
        nuevas.push(await api.post("/conexiones/", { version: verId, origen, destino, etiqueta: c.etiqueta, condicion: c.condicion }));
      }
      setVersion((v) => ({ ...v, nodos: [...v.nodos, n], conexiones: [...v.conexiones, ...nuevas] }));
      setSel(n.id);
      marcarGuardado();
    } catch { marcarError(); }
  }

  async function borrarConexion(cid) {
    const snapshot = version;
    setVersion((v) => ({ ...v, conexiones: v.conexiones.filter((c) => c.id !== cid) }));
    if (selConexion === cid) setSelConexion(null);
    marcarGuardando();
    try { await api.del(`/conexiones/${cid}/`); marcarGuardado(); }
    catch { setVersion(snapshot); marcarError(); }
  }

  async function actualizarConexion(cid, cambios) {
    const prev = version;
    setVersion((v) => ({ ...v, conexiones: v.conexiones.map((x) => (x.id === cid ? { ...x, ...cambios } : x)) }));
    marcarGuardando();
    try {
      const c = await api.patch(`/conexiones/${cid}/`, cambios);
      setVersion((v) => ({ ...v, conexiones: v.conexiones.map((x) => (x.id === cid ? c : x)) }));
      marcarGuardado();
    } catch { setVersion(prev); marcarError(); }
  }

  async function validar() {
    setValidando(true);
    try {
      const r = await api.get(`/versiones-flujo/${verId}/validar/`);
      setProblemas(r);
    } catch { mostrarToast({ tipo: "error", msg: "No se pudo validar el flujo." }); }
    finally { setValidando(false); }
  }
  async function publicar() {
    setPublicando(true);
    try {
      await api.post(`/versiones-flujo/${verId}/publicar/`, {});
      await cargarVersion(verId);
      const f = await api.get(`/flujos/${id}/`);
      setFlujo(f);
      setProblemas({ problemas: [], errores: 0, avisos: 0, puede_publicar: true, publicado: true });
      mostrarToast({ tipo: "ok", msg: "Versión publicada ✓" });
    } catch (e) {
      if (e?.data?.problemas) setProblemas({ ...e.data, errores: e.data.problemas.filter((p) => p.sev === "error").length });
      else mostrarToast({ tipo: "error", msg: "No se pudo publicar la versión." });
    } finally { setPublicando(false); }
  }

  // --- Modo Probar (simulación sin datos reales) --------------------------
  function iniciarSim() {
    setProblemas(null); setSel(null); setRepro(null);
    const inicio = nodoInicio(version.nodos);
    if (!inicio) { setSim({ current: null, valores: {}, camino: [], fin: false, error: "El flujo no tiene un nodo Inicio." }); return; }
    const { parada, camino } = correrAuto(version.nodos, version.conexiones, inicio.id, {});
    const nodo = version.nodos.find((n) => n.id === parada);
    setSim({ current: parada, valores: {}, camino, fin: nodo?.tipo === "fin" });
  }
  function avanzarSim(nuevosValores = {}) {
    setSim((s) => {
      const valores = { ...s.valores, ...nuevosValores };
      const sig = siguiente(version.nodos, version.conexiones, s.current, valores);
      if (sig == null) return { ...s, valores, fin: true, sinSalida: true };
      const { parada, camino } = correrAuto(version.nodos, version.conexiones, sig, valores);
      const nodo = version.nodos.find((n) => n.id === parada);
      return { current: parada, valores, camino: [...s.camino, ...camino], fin: nodo?.tipo === "fin" };
    });
  }

  // --- Reproducir (animación del recorrido) -------------------------------
  function reproducir() {
    setProblemas(null); setSel(null);
    const camino = sim?.camino?.length ? sim.camino : caminoPorDefecto(version.nodos, version.conexiones);
    if (!camino.length) return;
    setRepro({ camino, idx: 0 });
  }
  useEffect(() => {
    if (!repro) return;
    // Seguir el token: mantener el nodo en foco siempre visible en el viewport.
    const nid = repro.camino[repro.idx];
    const el = canvasRef.current?.querySelector(`[data-nodo="${nid}"]`);
    el?.scrollIntoView({ behavior: "smooth", block: "center", inline: "center" });
    if (repro.idx >= repro.camino.length - 1) {
      const t = setTimeout(() => setRepro(null), 1200);
      return () => clearTimeout(t);
    }
    const t = setTimeout(() => setRepro((r) => (r ? { ...r, idx: r.idx + 1 } : r)), 750);
    return () => clearTimeout(t);
  }, [repro]);

  // --- Atajos de teclado ---------------------------------------------------
  useEffect(() => {
    function onKey(e) {
      const tag = e.target?.tagName;
      const editando = tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || e.target?.isContentEditable;
      if (e.key === "Escape") {
        if (conectarDesde) return setConectarDesde(null);
        if (sim) return setSim(null);
        if (problemas) return setProblemas(null);
        setSel(null); setSelConexion(null);
        return;
      }
      if (editando) return;
      if (e.key === "Delete" || e.key === "Backspace") {
        if (sel != null) { e.preventDefault(); borrarNodo(sel); }
        else if (selConexion != null) { e.preventDefault(); borrarConexion(selConexion); }
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [sel, selConexion, conectarDesde, sim, problemas, version]);

  if (cargando) return <Spinner label="Cargando flujo…" />;
  if (errorCarga)
    return (
      <div style={{ padding: 40, maxWidth: 460 }}>
        <div style={{ fontSize: type.lg, fontWeight: 700, color: color.danger, marginBottom: 6 }}>No se pudo cargar el flujo</div>
        <div style={{ fontSize: type.base, color: color.slate600, marginBottom: 16 }}>{errorCarga}</div>
        <div style={{ display: "flex", gap: 10 }}>
          <Button onClick={cargarTodo}>Reintentar</Button>
          <Button variant="secondary" onClick={() => navigate("/flujos")}>← Flujos</Button>
        </div>
      </div>
    );
  if (!version) return <div style={{ padding: 32 }}>Este flujo no tiene versiones.</div>;

  const nodoSel = version.nodos.find((n) => n.id === sel);
  const estV = estadoVersion[version.estado];
  const nodoEnFoco = repro ? repro.camino[repro.idx] : sim ? sim.current : null;
  const reproNodo = repro ? version.nodos.find((n) => n.id === repro.camino[repro.idx]) : null;
  const flujoVacio = version.nodos.length <= 1;

  // Título del formulario asignado a un nodo (lo deduce de los campos cargados).
  const tituloForm = (fid) => campos.find((c) => c.formularioId === fid)?.formulario;

  // Subtítulo contextual de un nodo: resume su configuración para que el lienzo
  // se entienda sin abrir el panel de cada nodo.
  function subtituloNodo(n) {
    const cfg = n.config || {};
    if (n.tipo === "form") return n.formulario ? (tituloForm(n.formulario) || "Formulario asignado") : "Sin formulario";
    if (n.tipo === "decision") {
      const ramas = version.conexiones.filter((c) => c.origen === n.id).length;
      return ramas ? `${ramas} rama${ramas > 1 ? "s" : ""}` : "Sin ramas";
    }
    if (n.tipo === "derivar") return cfg.flujo_destino_id ? "Abre otro flujo" : cfg.area_destino_id ? "Cambia de área" : "Sin destino";
    if (n.tipo === "estado") return cfg.estado ? estadoCaso[cfg.estado]?.label || cfg.estado : "Sin estado";
    if (n.tipo === "atencion" && cfg.con_fila) return "Con fila de espera";
    if (n.tipo === "tiempo" && cfg.duracion) return `Pausa ${cfg.duracion}`;
    return null;
  }

  // Etiqueta de una rama de Decisión: manual si existe, derivada de la condición
  // si no. La rama sin condición (else) se rotula "si no".
  function etiquetaRama(c, origen) {
    if (c.etiqueta) return c.etiqueta;
    if (origen?.tipo !== "decision") return null;
    const cond = c.condicion;
    if (!cond || !cond.campo) return "si no";
    const campo = campos.find((cc) => String(cc.id) === String(cond.campo));
    return `${campo?.label || "campo"} ${OPERADOR_LABEL[cond.operador] || cond.operador || "="} ${cond.valor ?? ""}`.trim();
  }

  // Aristas que forman el recorrido activo (Probar / Reproducir) para resaltarlas.
  const edgesActivos = new Set();
  const caminoArr = repro ? repro.camino.slice(0, repro.idx + 1) : sim ? sim.camino : [];
  for (let i = 0; i < caminoArr.length - 1; i++) edgesActivos.add(`${caminoArr[i]}->${caminoArr[i + 1]}`);
  // Sin recorrido posible: deshabilita Probar/Reproducir y explica por qué.
  const sinRecorrido = version.nodos.length < 2 || version.conexiones.length === 0;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      {/* Barra superior */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "14px 24px", borderBottom: `1px solid ${color.border}`, background: "#fff", flex: "none", gap: 12, flexWrap: "wrap" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, minWidth: 0 }}>
          <button onClick={() => navigate("/flujos")} title="Volver a Flujos" style={{ border: "none", background: "none", cursor: "pointer", fontSize: type.base, color: color.slate500, display: "flex", alignItems: "center", gap: 5, padding: 4, borderRadius: radius.sm }}>
            <Icon name="back" size={15} /> Flujos
          </button>
          <div style={{ fontSize: type.xl, fontWeight: 700, letterSpacing: "-.4px", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{flujo.titulo}</div>
          {flujo.ambito_label && <span style={{ fontSize: type.sm, color: color.slate500, whiteSpace: "nowrap" }}>· {flujo.ambito_label}</span>}
          <Badge tone={estV.tone}>{estV.label}</Badge>
          <Select size="sm" value={verId} onChange={(e) => { setVerId(Number(e.target.value)); cargarVersion(Number(e.target.value)); }} style={{ width: "auto" }}>
            {flujo.versiones.map((v) => <option key={v.id} value={v.id}>{v.etiqueta}</option>)}
          </Select>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <SaveStatus estado={guardado} />
          <Button variant="secondary" onClick={reproducir} disabled={sinRecorrido} title={sinRecorrido ? "Agregá y conectá nodos para reproducir el recorrido" : "Anima el recorrido del flujo"} style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <Icon name="play" size={13} /> Reproducir
          </Button>
          <Button variant="secondary" onClick={iniciarSim} disabled={sinRecorrido} title={sinRecorrido ? "Agregá y conectá nodos para probar el flujo" : "Simulá un caso paso a paso"}>Probar</Button>
          <Button variant="secondary" onClick={validar} disabled={validando}>{validando ? "Validando…" : "Validar"}</Button>
          <Button onClick={publicar} disabled={version.estado === "publicada" || publicando}>{publicando ? "Publicando…" : "Publicar"}</Button>
        </div>
      </div>

      <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
        {/* Paleta */}
        <div style={{ width: 188, borderRight: `1px solid ${color.border}`, background: "#fff", padding: 12, overflow: "auto", flex: "none" }}>
          <div style={{ fontSize: type.micro, fontWeight: 700, letterSpacing: ".6px", color: color.slate500, margin: "4px 4px 4px" }}>NODOS</div>
          <div style={{ fontSize: type.xs, color: color.slate400, margin: "0 4px 10px" }}>Hacé clic para agregar al lienzo</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {PALETA.map((p) => (
              <button
                key={p.tipo}
                onClick={() => agregarNodo(p.tipo)}
                title={`Agregar nodo «${p.name}»`}
                style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 10px", border: `1px solid ${color.border}`, borderRadius: radius.md, background: "#fff", cursor: "pointer", textAlign: "left", transition: "background .12s, border-color .12s" }}
                onMouseEnter={(e) => { e.currentTarget.style.background = p.tint; e.currentTarget.style.borderColor = p.bd; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = "#fff"; e.currentTarget.style.borderColor = color.border; }}
              >
                <span style={{ width: 26, height: 26, borderRadius: radius.sm, background: p.tint, border: `1px solid ${p.bd}`, display: "flex", alignItems: "center", justifyContent: "center", flex: "none" }}>
                  <span style={{ width: 10, height: 10, borderRadius: p.tipo === "decision" ? 2 : 3, background: p.sol, transform: p.tipo === "decision" ? "rotate(45deg)" : "none" }} />
                </span>
                <span style={{ fontSize: type.sm, fontWeight: 600, color: color.slate700, flex: 1 }}>{p.name}</span>
                <Icon name="plus" size={13} style={{ color: color.slate400 }} />
              </button>
            ))}
          </div>
        </div>

        {/* Canvas */}
        <div style={{ flex: 1, overflow: "auto", background: color.canvas, position: "relative" }}>
          <div
            ref={canvasRef}
            onClick={() => { setSel(null); setSelConexion(null); setConectarDesde(null); }}
            style={{
              position: "relative",
              width: 2200,
              height: 1300,
              backgroundImage: "radial-gradient(circle, #D9DDE5 1.1px, transparent 1.1px)",
              backgroundSize: `${GRID}px ${GRID}px`,
            }}
          >
            {/* Conexiones */}
            <svg style={{ position: "absolute", inset: 0, width: "100%", height: "100%", pointerEvents: "none" }}>
              <defs>
                <marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth">
                  <path d="M0,0 L8,3 L0,6 Z" fill="#9AA2B1" />
                </marker>
                <marker id="arrow-activo" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth">
                  <path d="M0,0 L8,3 L0,6 Z" fill={color.accent} />
                </marker>
              </defs>
              {version.conexiones.map((c) => {
                const o = version.nodos.find((n) => n.id === c.origen);
                const d = version.nodos.find((n) => n.id === c.destino);
                if (!o || !d) return null;
                const x1 = o.x + NODO_W, y1 = o.y + NODO_H / 2;
                const x2 = d.x, y2 = d.y + NODO_H / 2;
                const mx = (x1 + x2) / 2, my = (y1 + y2) / 2;
                const activo = edgesActivos.has(`${c.origen}->${c.destino}`);
                const seleccionada = c.id === selConexion;
                const resaltada = seleccionada || activo || c.id === hoverConn;
                const stroke = seleccionada || activo ? color.accent : c.id === hoverConn ? color.slate500 : "#9AA2B1";
                const path = `M ${x1} ${y1} C ${mx} ${y1}, ${mx} ${y2}, ${x2} ${y2}`;
                const etiqueta = etiquetaRama(c, o);
                return (
                  <g
                    key={c.id}
                    style={{ pointerEvents: "auto", cursor: "pointer" }}
                    onMouseEnter={() => setHoverConn(c.id)}
                    onMouseLeave={() => setHoverConn((h) => (h === c.id ? null : h))}
                    onClick={(e) => { e.stopPropagation(); setSelConexion(c.id); setSel(null); }}
                  >
                    {/* zona de impacto invisible más ancha para facilitar el clic/hover */}
                    <path d={path} stroke="transparent" strokeWidth="16" fill="none" />
                    <path d={path} stroke={stroke} strokeWidth={resaltada ? 2.6 : 1.6} fill="none" markerEnd={`url(#${seleccionada || activo ? "arrow-activo" : "arrow"})`} style={{ transition: "stroke .15s, stroke-width .15s" }} />
                    {etiqueta && (
                      <>
                        <rect x={mx - (etiqueta.length * 3.2 + 6)} y={my - 18} width={etiqueta.length * 6.4 + 12} height={16} rx={8} fill={color.canvas} stroke={color.divider} />
                        <text x={mx} y={my - 6} fill={seleccionada || activo ? color.accent : color.slate600} fontSize="11" textAnchor="middle" style={{ fontWeight: 600 }}>{etiqueta}</text>
                      </>
                    )}
                    {seleccionada && (
                      <g onClick={(e) => { e.stopPropagation(); borrarConexion(c.id); }} style={{ cursor: "pointer" }}>
                        <circle cx={mx} cy={my + 13} r="9" fill={color.danger} />
                        <path d={`M ${mx - 3} ${my + 10} L ${mx + 3} ${my + 16} M ${mx + 3} ${my + 10} L ${mx - 3} ${my + 16}`} stroke="#fff" strokeWidth="1.6" strokeLinecap="round" />
                      </g>
                    )}
                  </g>
                );
              })}
              {/* Línea-fantasma mientras se arrastra una conexión nueva */}
              {ghost && (
                <path
                  d={`M ${ghost.x1} ${ghost.y1} C ${(ghost.x1 + ghost.x2) / 2} ${ghost.y1}, ${(ghost.x1 + ghost.x2) / 2} ${ghost.y2}, ${ghost.x2} ${ghost.y2}`}
                  stroke={color.accent} strokeWidth="2" strokeDasharray="5 4" fill="none" markerEnd="url(#arrow-activo)" style={{ pointerEvents: "none" }}
                />
              )}
            </svg>

            {/* Nodos */}
            {version.nodos.map((n) => {
              const cat = nodeCat[n.tipo] || nodeCat.form;
              const seleccionado = n.id === sel;
              const esOrigenConexion = conectarDesde === n.id;
              const enFoco = n.id === nodoEnFoco;
              const arrastrando = dragId === n.id;
              const sub = subtituloNodo(n);
              const subFalta = sub && sub.startsWith("Sin ");
              return (
                <div
                  key={n.id}
                  data-nodo={n.id}
                  onPointerDown={(e) => onNodoPointerDown(e, n)}
                  onClick={(e) => { e.stopPropagation(); clickNodo(n); }}
                  style={{
                    position: "absolute",
                    left: n.x,
                    top: n.y,
                    width: NODO_W,
                    minHeight: NODO_H,
                    boxSizing: "border-box",
                    background: cat.tint,
                    border: `1.5px solid ${seleccionado || esOrigenConexion || enFoco ? cat.sol : cat.bd}`,
                    borderRadius: radius.lg,
                    padding: "11px 13px",
                    cursor: arrastrando ? "grabbing" : "grab",
                    touchAction: "none",
                    boxShadow: enFoco ? `0 0 0 4px ${cat.sol}55, ${shadow.float}` : arrastrando ? shadow.float : seleccionado ? `0 0 0 3px ${cat.sol}33` : shadow.card,
                    transform: arrastrando ? "scale(1.02)" : "none",
                    transition: arrastrando ? "none" : "box-shadow .2s, border-color .2s, transform .12s",
                    zIndex: arrastrando ? 4 : 1,
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                  }}
                >
                  <span style={{ width: 11, height: 11, borderRadius: n.tipo === "decision" ? 2 : 3, background: cat.sol, transform: n.tipo === "decision" ? "rotate(45deg)" : "none", flex: "none" }} />
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <div style={{ fontSize: type.micro, fontWeight: 700, letterSpacing: ".4px", color: cat.sol }}>{cat.name.toUpperCase()}</div>
                    <div style={{ fontSize: type.base, fontWeight: 600, color: color.slate900, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{n.titulo}</div>
                    {sub && (
                      <div style={{ fontSize: type.xs, color: subFalta ? color.danger : color.slate500, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", marginTop: 2 }}>{sub}</div>
                    )}
                    {n.grupos_detalle?.length > 0 && (
                      <div title={`Responsable: ${n.grupos_detalle.map((g) => g.nombre).join(", ")}`} style={{ display: "flex", alignItems: "center", gap: 4, marginTop: 3, fontSize: type.xs, color: color.slate500, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                        <Icon name="users" size={11} />
                        {n.grupos_detalle.length === 1 ? n.grupos_detalle[0].nombre : `${n.grupos_detalle.length} grupos`}
                      </div>
                    )}
                  </div>
                  {/* Handle de entrada (visual) */}
                  {n.tipo !== "inicio" && (
                    <span style={{ position: "absolute", left: -5, top: NODO_H / 2 - 4, width: 9, height: 9, borderRadius: "50%", background: "#fff", border: `2px solid ${cat.bd}`, pointerEvents: "none" }} />
                  )}
                  {/* Handle de salida: arrastrar desde acá para conectar */}
                  {n.tipo !== "fin" && (
                    <span
                      title="Arrastrá para conectar con otro nodo"
                      onPointerDown={(e) => onHandlePointerDown(e, n)}
                      onMouseDown={(e) => e.stopPropagation()}
                      onClick={(e) => e.stopPropagation()}
                      style={{ position: "absolute", right: -7, top: NODO_H / 2 - 6, width: 13, height: 13, borderRadius: "50%", background: "#fff", border: `2px solid ${cat.sol}`, cursor: "crosshair", touchAction: "none", zIndex: 3 }}
                    />
                  )}
                </div>
              );
            })}

            {/* Token de "Reproducir" viajando por el lienzo */}
            {reproNodo && (
              <div style={{ position: "absolute", left: reproNodo.x + NODO_W / 2 - 9, top: reproNodo.y + NODO_H / 2 - 9, width: 18, height: 18, borderRadius: "50%", background: color.accent, border: "3px solid #fff", boxShadow: `0 0 0 4px ${color.accent}55, 0 6px 16px rgba(16,24,40,.3)`, transition: "left .65s cubic-bezier(.5,0,.2,1), top .65s cubic-bezier(.5,0,.2,1)", pointerEvents: "none", zIndex: 5 }} />
            )}
          </div>

          {/* Onboarding del lienzo vacío */}
          {flujoVacio && (
            <div style={{ position: "absolute", top: 90, left: "50%", transform: "translateX(-50%)", width: 320, maxWidth: "80%", background: "#fff", border: `1px solid ${color.border}`, borderRadius: radius.lg, boxShadow: shadow.dropdown, padding: "18px 20px", animation: "fadeUp .2s ease", zIndex: 6 }}>
              <div style={{ fontSize: type.md, fontWeight: 700, color: color.slate900, marginBottom: 4 }}>Diseñá tu primer proceso</div>
              <div style={{ fontSize: type.sm, color: color.slate500, marginBottom: 12 }}>Tres pasos para armar un flujo:</div>
              {[
                ["1", "Agregá nodos", "Hacé clic en un tipo de la columna NODOS (izquierda)."],
                ["2", "Conectalos", "Arrastrá desde el punto del borde derecho de un nodo al siguiente."],
                ["3", "Probalo", "Usá «Probar» para recorrer el flujo como un caso real."],
              ].map(([n, t, d]) => (
                <div key={n} style={{ display: "flex", gap: 10, marginBottom: 10 }}>
                  <span style={{ flex: "none", width: 20, height: 20, borderRadius: "50%", background: color.accent50, color: color.accent, fontSize: type.xs, fontWeight: 700, display: "flex", alignItems: "center", justifyContent: "center" }}>{n}</span>
                  <div>
                    <div style={{ fontSize: type.base, fontWeight: 600, color: color.slate700 }}>{t}</div>
                    <div style={{ fontSize: type.xs, color: color.slate500 }}>{d}</div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {conectarDesde && (
            <div style={{ position: "fixed", bottom: 24, left: "50%", transform: "translateX(-50%)", background: color.slate900, color: "#fff", padding: "8px 16px", borderRadius: radius.pill, fontSize: type.sm, boxShadow: shadow.dropdown, zIndex: 40 }}>
              Hacé clic en el nodo destino · <span style={{ cursor: "pointer", textDecoration: "underline" }} onClick={() => setConectarDesde(null)}>cancelar</span>
            </div>
          )}
        </div>

        {/* Panel de propiedades */}
        <div style={{ width: 300, borderLeft: `1px solid ${color.border}`, background: "#fff", overflow: "auto", flex: "none" }}>
          {sim ? (
            <PanelSimulacion sim={sim} version={version} campos={campos} onAvanzar={avanzarSim} onReiniciar={iniciarSim} onCerrar={() => setSim(null)} />
          ) : problemas ? (
            <PanelValidacion problemas={problemas} onCerrar={() => setProblemas(null)} onFocus={(nid) => { setSel(nid); setProblemas(null); }} />
          ) : nodoSel ? (
            <PanelNodo
              key={nodoSel.id}
              nodo={nodoSel}
              version={version}
              flujoInstId={flujo.institucion}
              flujoAreaId={flujo.area}
              campos={campos}
              onActualizar={actualizarNodo}
              onBorrar={borrarNodo}
              onConectar={() => setConectarDesde(nodoSel.id)}
              onBorrarConexion={borrarConexion}
              onActualizarConexion={actualizarConexion}
            />
          ) : (
            <div style={{ padding: 22, fontSize: type.base, color: color.slate500 }}>
              Seleccioná un nodo para editar sus propiedades, o agregá uno desde la paleta.
            </div>
          )}
        </div>
      </div>

      {toast && <Toast toast={toast} onClose={() => setToast(null)} />}
    </div>
  );
}

// Indicador de autosave en la barra superior.
function SaveStatus({ estado }) {
  if (estado === "idle") return null;
  const map = {
    guardando: { txt: "Guardando…", col: color.slate500 },
    guardado: { txt: "Guardado ✓", col: "#1B7A4E" },
    error: { txt: "Error al guardar", col: color.danger },
  };
  const s = map[estado] || map.guardando;
  return <span style={{ fontSize: type.sm, fontWeight: 600, color: s.col, whiteSpace: "nowrap" }}>{s.txt}</span>;
}

// Toast efímero con acción opcional (p. ej. «Deshacer»).
function Toast({ toast, onClose }) {
  const ok = toast.tipo === "ok";
  return (
    <div style={{ position: "fixed", bottom: 24, left: "50%", transform: "translateX(-50%)", display: "flex", alignItems: "center", gap: 14, background: color.slate900, color: "#fff", padding: "11px 16px", borderRadius: radius.md, fontSize: type.base, boxShadow: shadow.dropdown, zIndex: 60, maxWidth: 460, animation: "fadeUp .16s ease" }}>
      <span style={{ width: 8, height: 8, borderRadius: "50%", background: ok ? "#46C08A" : "#F26D6D", flex: "none" }} />
      <span style={{ flex: 1 }}>{toast.msg}</span>
      {toast.accion && (
        <button onClick={toast.accion.fn} style={{ border: "none", background: "none", color: "#9FB0FF", fontWeight: 700, cursor: "pointer", fontSize: type.base, whiteSpace: "nowrap" }}>{toast.accion.label}</button>
      )}
      <button onClick={onClose} aria-label="Cerrar" style={{ border: "none", background: "none", color: "#fff", cursor: "pointer", display: "flex", opacity: .7 }}>
        <Icon name="x" size={15} />
      </button>
    </div>
  );
}

// --------------------------------------------------------------------------- //
function PanelSimulacion({ sim, version, campos, onAvanzar, onReiniciar, onCerrar }) {
  const nodo = version.nodos.find((n) => n.id === sim.current);
  const cat = nodo ? nodeCat[nodo.tipo] || nodeCat.form : nodeCat.inicio;
  const [valores, setValores] = useState({});

  const camposForm = nodo?.tipo === "form" && nodo.formulario
    ? campos.filter((c) => c.formularioId === nodo.formulario)
    : [];

  function completarForm() {
    onAvanzar(valores);
    setValores({});
  }

  return (
    <div style={{ padding: 20 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
        <div style={{ fontSize: type.md, fontWeight: 700, display: "flex", alignItems: "center", gap: 7 }}>
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: badgeTone.green.fg }} /> Modo prueba
        </div>
        <button onClick={onCerrar} aria-label="Cerrar" style={{ border: "none", background: "none", cursor: "pointer", color: color.slate500, display: "flex", padding: 4, borderRadius: radius.sm }}><Icon name="x" size={18} /></button>
      </div>
      <div style={{ fontSize: type.sm, color: color.slate500, marginBottom: 16 }}>Simulación sin datos reales. Recorré el flujo como lo haría un caso.</div>

      {sim.error ? (
        <div style={{ fontSize: type.base, color: color.danger, background: badgeTone.error.bg, padding: "10px 12px", borderRadius: radius.md }}>{sim.error}</div>
      ) : sim.fin ? (
        <div style={{ background: badgeTone.green.bg, color: badgeTone.green.fg, padding: "14px 16px", borderRadius: radius.md, fontSize: type.base, fontWeight: 600 }}>
          ✓ Caso simulado {sim.sinSalida ? "detenido (nodo sin salida)" : "finalizado"}.
        </div>
      ) : nodo ? (
        <>
          <div style={{ border: `1px solid ${cat.bd}`, background: cat.tint, borderRadius: radius.md, padding: 13, marginBottom: 14 }}>
            <div style={{ fontSize: type.micro, fontWeight: 700, letterSpacing: ".4px", color: cat.sol }}>{cat.name.toUpperCase()}</div>
            <div style={{ fontSize: type.md, fontWeight: 700, color: color.slate900 }}>{nodo.titulo}</div>
          </div>

          {nodo.tipo === "form" && (
            <div style={{ display: "flex", flexDirection: "column", gap: 12, marginBottom: 14 }}>
              {camposForm.length === 0 ? (
                <div style={{ fontSize: type.sm, color: color.slate500 }}>Este formulario no tiene campos (o no está asignado).</div>
              ) : camposForm.map((c) => (
                <div key={c.id}>
                  <div style={{ fontSize: type.sm, fontWeight: 600, color: color.slate600, marginBottom: 5 }}>{c.label}{c.requerido && <span style={{ color: color.danger }}> *</span>}</div>
                  {c.tipo === "seleccion_unica" ? (
                    <Select size="sm" value={valores[c.id] || ""} onChange={(e) => setValores((v) => ({ ...v, [c.id]: e.target.value }))}>
                      <option value="">Seleccionar…</option>
                      {(c.opciones || []).map((o) => <option key={o} value={o}>{o}</option>)}
                    </Select>
                  ) : (
                    <Input size="sm" type={c.tipo === "fecha" ? "date" : "text"} value={valores[c.id] || ""} onChange={(e) => setValores((v) => ({ ...v, [c.id]: e.target.value }))} />
                  )}
                </div>
              ))}
            </div>
          )}

          <Button onClick={nodo.tipo === "form" ? completarForm : () => onAvanzar({})} style={{ width: "100%" }}>
            {nodo.tipo === "form" ? "Completar y avanzar" : nodo.tipo === "atencion" ? "Registrar y avanzar" : nodo.tipo === "espera" ? "Llamar y continuar" : nodo.tipo === "tiempo" ? "Reactivar" : "Avanzar"}
          </Button>
        </>
      ) : (
        <div style={{ fontSize: type.base, color: color.slate500 }}>Sin nodo actual.</div>
      )}

      {/* Recorrido */}
      <div style={{ marginTop: 18, borderTop: `1px solid ${color.divider}`, paddingTop: 14 }}>
        <div style={{ fontSize: type.micro, fontWeight: 700, letterSpacing: ".5px", color: color.slate500, marginBottom: 8 }}>RECORRIDO</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          {(sim.camino || []).map((nid, i) => {
            const n = version.nodos.find((x) => x.id === nid);
            if (!n) return null;
            const c = nodeCat[n.tipo] || nodeCat.form;
            return (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: type.sm, color: nid === sim.current ? color.slate900 : color.slate500 }}>
                <span style={{ width: 8, height: 8, borderRadius: 2, background: c.sol, flex: "none" }} />
                {n.titulo}
              </div>
            );
          })}
        </div>
        <button onClick={onReiniciar} style={{ marginTop: 12, border: "none", background: "none", color: color.accent, cursor: "pointer", fontSize: type.sm, fontWeight: 600 }}>↻ Reiniciar prueba</button>
      </div>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Operadores válidos según el tipo del campo (>, < solo tienen sentido en
// números/fechas; el motor hace parseFloat y devuelve false para texto).
const OP_POR_TIPO = {
  numero: ["=", "!=", ">", "<"],
  entero: ["=", "!=", ">", "<"],
  decimal: ["=", "!=", ">", "<"],
  fecha: ["=", "!=", ">", "<"],
  seleccion_unica: ["=", "!="],
};
function operadoresDe(campo) {
  if (!campo) return ["=", "!=", "contiene"];
  return OP_POR_TIPO[campo.tipo] || (campo.opciones?.length ? ["=", "!="] : ["=", "!=", "contiene"]);
}

function RuleBuilder({ conexion, campos, onActualizar }) {
  const cond = conexion.condicion || {};
  const set = (cambios) => onActualizar(conexion.id, { condicion: { ...cond, ...cambios } });
  const campoSel = campos.find((c) => String(c.id) === String(cond.campo));
  const ops = operadoresDe(campoSel);
  // Agrupar por formulario para desambiguar labels repetidos entre formularios.
  const porForm = campos.reduce((acc, c) => { (acc[c.formulario] = acc[c.formulario] || []).push(c); return acc; }, {});
  return (
    <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 6 }}>
      <div style={{ fontSize: type.micro, fontWeight: 700, letterSpacing: ".4px", color: color.slate500 }}>SI…</div>
      <Select size="sm" value={cond.campo || ""} onChange={(e) => set({ campo: e.target.value ? Number(e.target.value) : null, operador: "=", valor: "" })}>
        <option value="">(sin condición · rama por defecto)</option>
        {Object.entries(porForm).map(([form, cs]) => (
          <optgroup key={form} label={form}>
            {cs.map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}
          </optgroup>
        ))}
      </Select>
      {cond.campo && (
        <div style={{ display: "flex", gap: 6 }}>
          <Select size="sm" style={{ width: 138 }} value={cond.operador || "="} onChange={(e) => set({ operador: e.target.value })}>
            {ops.map((o) => <option key={o} value={o}>{OPERADOR_LABEL[o] || o}</option>)}
          </Select>
          {campoSel?.opciones?.length ? (
            <Select size="sm" value={cond.valor || ""} onChange={(e) => set({ valor: e.target.value })}>
              <option value="">valor…</option>
              {campoSel.opciones.map((o) => <option key={o} value={o}>{o}</option>)}
            </Select>
          ) : (
            // key fuerza el refresh del defaultValue al cambiar de campo/operador.
            <Input key={`${cond.campo}-${cond.operador}`} size="sm" placeholder="valor" defaultValue={cond.valor || ""} onBlur={(e) => e.target.value !== (cond.valor || "") && set({ valor: e.target.value })} />
          )}
        </div>
      )}
    </div>
  );
}

// Pasos donde una persona ejecuta el trabajo: ahí tiene sentido decir "quién lo hace".
const TIPOS_CON_RESPONSABLE = ["form", "atencion", "accion", "espera"];

// Ayuda por tipo de nodo: para qué sirve y cómo se usa (helper del panel).
const AYUDA_NODO = {
  inicio: "Punto de arranque del flujo. Acá nace o entra el caso. Definí cómo entra: «Manual» (se crea desde Nuevo caso), «Solo por derivación» (lo manda otro flujo) o «Ambas».",
  form: "Muestra un formulario para cargar datos del caso. El caso se detiene hasta que alguien lo completa. Elegí qué formulario usar y, en «Responsable», qué grupos pueden completarlo.",
  decision: "Bifurca el camino según los datos ya cargados. En cada conexión de salida definí una regla (campo / operador / valor); la salida sin regla es la rama por defecto (else).",
  accion: "Paso automático: ejecuta una acción del sistema y el flujo sigue solo (no se detiene). Útil para marcar un hito del proceso. (Ej.: «Solicitud de estudios» — en desarrollo.)",
  atencion: "Registra una atención profesional que queda en la historia clínica del paciente. Si activás «fila de espera», el paciente queda en cola y un médico lo llama desde un box antes de atenderlo.",
  derivar: "Envía el caso a otra área. Si además elegís un flujo de destino, abre un caso nuevo en ese flujo (ej.: ingreso → especialidad), vinculado al original. El caso de origen sigue hacia su cierre.",
  espera: "Fila de espera genérica: encola el caso (orden de llegada; urgentes primero) y, al llamarlo, avanza al SIGUIENTE paso. Si lo que sigue es atender al paciente, conviene usar el nodo «Atención» con la opción «fila de espera» (une espera + llamado + atención en un solo paso).",
  tiempo: "Pausa el caso por un período (dato informativo). Hoy se reactiva manualmente; la reactivación automática por tiempo es un pendiente.",
  estado: "Cambia el estado del caso (Recibido, En espera, Atendido, Cerrado…). Es automático: sirve para reflejar en qué etapa está el caso.",
  fin: "Cierra el caso: marca el estado como Cerrado y termina el recorrido. Un flujo puede tener varios nodos Fin.",
};

function PanelNodo({ nodo, version, flujoInstId, flujoAreaId, campos, onActualizar, onBorrar, onConectar, onBorrarConexion, onActualizarConexion }) {
  const [titulo, setTitulo] = useState(nodo.titulo);
  // La preferencia de ayuda se recuerda entre nodos (localStorage) en vez de
  // resetearse cada vez que se selecciona otro nodo.
  const [ayuda, setAyuda] = useState(() => localStorage.getItem("cauce.ayudaNodo") === "1");
  const [areas, setAreas] = useState([]);
  const [flujos, setFlujos] = useState([]);
  const [formularios, setFormularios] = useState([]);
  const [grupos, setGrupos] = useState([]);
  const [boxesArea, setBoxesArea] = useState([]);
  const cat = nodeCat[nodo.tipo] || nodeCat.form;
  const salidas = version.conexiones.filter((c) => c.origen === nodo.id);
  const aplicaResponsable = TIPOS_CON_RESPONSABLE.includes(nodo.tipo);

  useEffect(() => {
    if (nodo.tipo === "derivar") {
      api.get(`/areas/?institucion=${flujoInstId}`).then((d) => setAreas(d.results || d));
      api.get(`/flujos/?institucion=${flujoInstId}`).then((d) => setFlujos(d.results || d));
    }
    if (nodo.tipo === "form") api.get(`/formularios/?institucion=${flujoInstId}`).then((d) => setFormularios(d.results || d));
    if (aplicaResponsable) api.get(`/grupos/?area__institucion=${flujoInstId}&activo=true`).then((d) => setGrupos(d.results || d));
    if ((nodo.tipo === "atencion" || nodo.tipo === "espera") && flujoAreaId)
      api.get(`/boxes/?area=${flujoAreaId}&activo=true`).then((d) => setBoxesArea(d.results || d));
  }, [nodo.tipo, flujoInstId, flujoAreaId, aplicaResponsable]);

  // Flujos de destino candidatos: los del área elegida, sin el flujo actual
  // (evita derivar a sí mismo) y que acepten derivación (no los "solo manual").
  const areaDestinoId = (nodo.config || {}).area_destino_id;
  const flujosDelArea = flujos.filter(
    (f) => f.area === areaDestinoId && f.id !== version.flujo && f.origen_inicio !== "manual"
  );
  const tienePublicada = (f) => (f.versiones || []).some((v) => v.estado === "publicada");

  const setConfig = (cambios) => onActualizar(nodo.id, { config: { ...(nodo.config || {}), ...cambios } });

  const asignados = new Set(nodo.grupos || []);
  const toggleGrupo = (gid) => {
    const next = asignados.has(gid) ? [...asignados].filter((x) => x !== gid) : [...asignados, gid];
    onActualizar(nodo.id, { grupos: next });
  };

  return (
    <div style={{ padding: 20 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
        <span style={{ width: 28, height: 28, borderRadius: 8, background: cat.tint, border: `1px solid ${cat.bd}`, display: "flex", alignItems: "center", justifyContent: "center", flex: "none" }}>
          <span style={{ width: 11, height: 11, borderRadius: 3, background: cat.sol }} />
        </span>
        <div style={{ flex: 1, fontSize: type.sm, fontWeight: 700, letterSpacing: ".5px", color: cat.sol }}>{cat.name.toUpperCase()}</div>
        <button
          onClick={() => setAyuda((v) => { localStorage.setItem("cauce.ayudaNodo", v ? "0" : "1"); return !v; })}
          title="¿Qué hace este nodo?"
          aria-label="¿Qué hace este nodo?"
          style={{ width: 28, height: 28, borderRadius: radius.sm, border: `1px solid ${ayuda ? color.accent : color.inputBorder}`, background: ayuda ? color.accent50 : "#fff", color: ayuda ? color.accent : color.slate500, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", flex: "none" }}
        >
          <Icon name="help" size={15} />
        </button>
      </div>

      {ayuda && (
        <div style={{ display: "flex", gap: 9, background: color.accent50, border: `1px solid ${color.accent100}`, borderRadius: 10, padding: "11px 12px", marginBottom: 16 }}>
          <Icon name="help" size={15} style={{ color: color.accent, marginTop: 1 }} />
          <div style={{ fontSize: 12.5, lineHeight: 1.5, color: color.slate700 }}>
            {AYUDA_NODO[nodo.tipo] || "Nodo del flujo."}
          </div>
        </div>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <Field label="Título">
          <Input value={titulo} onChange={(e) => setTitulo(e.target.value)} onBlur={() => titulo !== nodo.titulo && onActualizar(nodo.id, { titulo })} />
        </Field>

        {nodo.tipo === "inicio" && (
          <Field label="¿Cómo entran los casos a este flujo?">
            <Select value={(nodo.config || {}).origen || "ambos"} onChange={(e) => setConfig({ origen: e.target.value })}>
              <option value="manual">Manual — se crea desde «Nuevo caso»</option>
              <option value="derivado">Solo por derivación — no se crea a mano</option>
              <option value="ambos">Ambas</option>
            </Select>
            <div style={{ marginTop: 6, fontSize: 11, color: color.slate400 }}>
              Define si el flujo aparece en «Nuevo caso» y/o si puede ser destino de una derivación.
            </div>
          </Field>
        )}

        {nodo.tipo === "form" && (
          <Field label="Formulario">
            <Select value={nodo.formulario || ""} onChange={(e) => onActualizar(nodo.id, { formulario: e.target.value || null })}>
              <option value="">— Elegir —</option>
              {formularios.map((f) => <option key={f.id} value={f.id}>{f.titulo}</option>)}
            </Select>
            {!nodo.formulario && <AvisoFalta texto="Elegí qué formulario se completa en este paso." />}
          </Field>
        )}

        {nodo.tipo === "atencion" && (
          <Field label="Fila de espera">
            <label style={{ display: "flex", alignItems: "center", gap: 9, fontSize: 13.5, cursor: "pointer" }}>
              <input
                type="checkbox"
                checked={!!(nodo.config || {}).con_fila}
                onChange={(e) => setConfig({ con_fila: e.target.checked })}
              />
              El paciente espera y se lo llama desde un box
            </label>
            {(nodo.config || {}).con_fila && (
              <div style={{ marginTop: 8, fontSize: 11.5, color: color.slate500 }}>
                {!flujoAreaId
                  ? "Este flujo no tiene área: configurá un área para usar boxes."
                  : boxesArea.length === 0
                    ? "El área no tiene boxes. Cargalos en Estructura → área → Boxes."
                    : <>Se llama desde los boxes de <strong>{boxesArea[0].area_nombre}</strong>: {boxesArea.map((b) => b.nombre).join(", ")}.</>}
              </div>
            )}
          </Field>
        )}

        {nodo.tipo === "atencion" && (nodo.config || {}).con_fila && <PantallaUrl nodo={nodo} />}

        {nodo.tipo === "espera" && (
          <>
            <div style={{ fontSize: 12, color: color.slate500 }}>
              Los casos esperan en una fila (FIFO + urgentes primero) y se los llama desde un box para que avancen al siguiente paso.
            </div>
            <PantallaUrl nodo={nodo} />
          </>
        )}

        {nodo.tipo === "derivar" && (
          <>
            <Field label="Área de destino">
              {/* Cambiar de área limpia el flujo elegido (puede no pertenecer a la nueva área). */}
              <Select
                value={areaDestinoId || ""}
                onChange={(e) => setConfig({ area_destino_id: e.target.value ? Number(e.target.value) : null, flujo_destino_id: null })}
              >
                <option value="">— Elegir —</option>
                {areas.map((a) => <option key={a.id} value={a.id}>{a.nombre}</option>)}
              </Select>
              {!areaDestinoId && <AvisoFalta texto="Elegí a qué área se deriva el caso." />}
            </Field>

            {areaDestinoId && (
              <Field label="Flujo de destino">
                <Select
                  value={(nodo.config || {}).flujo_destino_id || ""}
                  onChange={(e) => setConfig({ flujo_destino_id: e.target.value ? Number(e.target.value) : null })}
                >
                  <option value="">— Solo cambiar de área (sin abrir un flujo) —</option>
                  {flujosDelArea.map((f) => (
                    <option key={f.id} value={f.id} disabled={!tienePublicada(f)}>
                      {f.titulo}{tienePublicada(f) ? "" : " (sin publicar)"}
                    </option>
                  ))}
                </Select>
                <div style={{ marginTop: 6, fontSize: 11, color: color.slate400 }}>
                  {flujosDelArea.length === 0
                    ? "El área no tiene flujos que acepten derivación. Se derivará solo cambiando el área."
                    : (nodo.config || {}).flujo_destino_id
                      ? "Al derivar se abre un caso nuevo en este flujo (debe estar publicado)."
                      : "Sin flujo: la derivación solo cambia el área del caso."}
                </div>
              </Field>
            )}
          </>
        )}

        {nodo.tipo === "estado" && (
          <Field label="Estado a aplicar">
            <Select value={(nodo.config || {}).estado || ""} onChange={(e) => setConfig({ estado: e.target.value })}>
              <option value="">— Elegir —</option>
              {["recibido", "en_evaluacion", "en_espera", "derivado", "atendido", "cerrado"].map((s) => <option key={s} value={s}>{estadoCaso[s]?.label || s}</option>)}
            </Select>
            {!(nodo.config || {}).estado && <AvisoFalta texto="Elegí qué estado aplica este nodo." />}
          </Field>
        )}

        {nodo.tipo === "tiempo" && (
          <Field label="Duración (informativa)">
            <Input value={(nodo.config || {}).duracion || ""} onChange={(e) => setConfig({ duracion: e.target.value })} placeholder="1 mes" />
          </Field>
        )}

        {/* Quién hace este paso: grupos responsables. */}
        {aplicaResponsable && (
          <Field label="Responsable — ¿quién lo hace?">
            {grupos.length === 0 ? (
              <div style={{ fontSize: 12, color: color.slate400 }}>
                No hay grupos en la institución. Crealos en Estructura → área → Grupos.
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 2, maxHeight: 190, overflow: "auto", border: `1px solid ${color.inputBorder}`, borderRadius: 9, padding: 6 }}>
                {grupos.map((g) => {
                  const on = asignados.has(g.id);
                  return (
                    <label key={g.id} style={{ display: "flex", alignItems: "center", gap: 9, padding: "6px 7px", borderRadius: 7, cursor: "pointer", background: on ? color.accent50 : "transparent" }}>
                      <input type="checkbox" checked={on} onChange={() => toggleGrupo(g.id)} />
                      <span style={{ minWidth: 0 }}>
                        <span style={{ display: "block", fontSize: 12.5, fontWeight: 600, color: color.slate700, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{g.nombre}</span>
                        <span style={{ fontSize: 10.5, color: color.slate400 }}>{g.area_nombre}</span>
                      </span>
                    </label>
                  );
                })}
              </div>
            )}
            {grupos.length > 0 && asignados.size === 0 && (
              <AvisoFalta texto="Sin grupo asignado: nadie podrá tomar este paso." />
            )}
            {asignados.size > 0 && (
              <div style={{ marginTop: 6, fontSize: type.xs, color: color.slate500 }}>
                Cualquier integrante de {asignados.size === 1 ? "el grupo asignado" : `los ${asignados.size} grupos asignados`} podrá tomar este paso.
              </div>
            )}
          </Field>
        )}

        {/* Conexiones salientes */}
        <div style={{ borderTop: `1px solid ${color.divider}`, paddingTop: 14 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
            <div style={{ fontSize: 12.5, fontWeight: 700, color: color.slate700 }}>Conexiones</div>
            <button onClick={onConectar} style={{ border: "none", background: "none", color: color.accent, cursor: "pointer", fontSize: 12.5, fontWeight: 600 }}>+ conectar</button>
          </div>
          {salidas.length === 0 ? (
            <div style={{ fontSize: 12.5, color: color.slate400 }}>Sin salidas.</div>
          ) : (
            salidas.map((c) => {
              const destino = version.nodos.find((n) => n.id === c.destino);
              return (
                <div key={c.id} style={{ border: `1px solid ${color.divider}`, borderRadius: 9, padding: 10, marginBottom: 8 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                    <span style={{ fontSize: type.sm, fontWeight: 600 }}>→ {destino?.titulo || "?"}</span>
                    <button onClick={() => onBorrarConexion(c.id)} style={{ border: "none", background: "none", color: color.danger, cursor: "pointer", fontSize: type.xs, padding: "4px 6px", borderRadius: radius.sm }}>quitar</button>
                  </div>
                  {nodo.tipo === "decision" && (
                    <>
                      <Input
                        style={{ height: 32, fontSize: 12.5 }}
                        placeholder="Etiqueta de la rama"
                        defaultValue={c.etiqueta}
                        onBlur={(e) => e.target.value !== c.etiqueta && onActualizarConexion(c.id, { etiqueta: e.target.value })}
                      />
                      <RuleBuilder conexion={c} campos={campos} onActualizar={onActualizarConexion} />
                    </>
                  )}
                </div>
              );
            })
          )}
        </div>

        <button onClick={() => onBorrar(nodo.id)} style={{ marginTop: 6, border: "none", background: badgeTone.error.bg, color: color.danger, padding: "9px 0", borderRadius: radius.md, cursor: "pointer", fontSize: type.base, fontWeight: 600, display: "flex", alignItems: "center", justifyContent: "center", gap: 7 }}>
          <Icon name="trash" size={15} /> Eliminar nodo
        </button>
      </div>
    </div>
  );
}

// Pantalla de llamados del nodo: genera/muestra la URL pública (TV de sala de
// espera). El token se crea bajo demanda contra POST /nodos/<id>/pantalla/.
function PantallaUrl({ nodo }) {
  const [token, setToken] = useState(nodo.pantalla_token || "");
  const [cargando, setCargando] = useState(false);
  const [copiado, setCopiado] = useState(false);
  const url = token ? `${window.location.origin}/pantalla/${token}` : "";

  async function generar(rotar = false) {
    setCargando(true);
    try {
      const d = await api.post(`/nodos/${nodo.id}/pantalla/`, rotar ? { rotar: true } : {});
      setToken(d.token);
      nodo.pantalla_token = d.token; // refleja en el nodo cargado en memoria
    } finally {
      setCargando(false);
    }
  }

  async function copiar() {
    try {
      await navigator.clipboard.writeText(url);
      setCopiado(true);
      setTimeout(() => setCopiado(false), 1500);
    } catch { /* sin portapapeles: el usuario copia a mano */ }
  }

  return (
    <Field label="Pantalla de llamados">
      {!token ? (
        <>
          <button onClick={() => generar(false)} disabled={cargando}
            style={{ height: 36, padding: "0 14px", borderRadius: 9, background: color.accent, color: "#fff", border: "none", cursor: "pointer", fontSize: 13, fontWeight: 600 }}>
            {cargando ? "Generando…" : "Generar URL de pantalla"}
          </button>
          <div style={{ marginTop: 6, fontSize: 11, color: color.slate400 }}>
            Una pantalla pública (TV de sala de espera) que muestra a quién se llama y desde qué box.
          </div>
        </>
      ) : (
        <>
          <div style={{ display: "flex", gap: 6 }}>
            <Input readOnly value={url} onFocus={(e) => e.target.select()} style={{ fontSize: 12, fontFamily: "monospace" }} />
            <button onClick={copiar} title="Copiar enlace"
              style={{ flex: "none", height: 38, padding: "0 12px", borderRadius: 9, background: copiado ? "#E6F5EC" : "#EEF0F3", color: copiado ? "#1B7A4E" : color.slate600, border: "none", cursor: "pointer", fontSize: 12.5, fontWeight: 600 }}>
              {copiado ? "✓" : "Copiar"}
            </button>
          </div>
          <div style={{ display: "flex", gap: 14, marginTop: 8, alignItems: "center" }}>
            <a href={url} target="_blank" rel="noreferrer" style={{ fontSize: type.sm, fontWeight: 600, color: color.accent, textDecoration: "none" }}>
              Abrir pantalla ↗
            </a>
            <button onClick={() => { if (window.confirm("¿Regenerar el enlace? La pantalla abierta actualmente dejará de funcionar.")) generar(true); }} disabled={cargando}
              style={{ border: "none", background: "none", color: color.slate500, cursor: "pointer", fontSize: type.xs }}>
              {cargando ? "…" : "Regenerar enlace"}
            </button>
          </div>
          <div style={{ marginTop: 6, fontSize: type.xs, color: color.slate500 }}>
            Abrila en el televisor de la sala. Al regenerar, el enlace anterior deja de funcionar.
          </div>
        </>
      )}
    </Field>
  );
}

function PanelValidacion({ problemas, onCerrar, onFocus }) {
  const sevColor = { error: color.danger, aviso: badgeTone.amber.fg };
  const sevBg = { error: badgeTone.error.bg, aviso: badgeTone.amber.bg };
  return (
    <div style={{ padding: 20 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
        <div style={{ fontSize: type.md, fontWeight: 700 }}>Validación</div>
        <button onClick={onCerrar} aria-label="Cerrar" style={{ border: "none", background: "none", cursor: "pointer", color: color.slate500, display: "flex", padding: 4, borderRadius: radius.sm }}><Icon name="x" size={18} /></button>
      </div>
      {problemas.publicado && (
        <div style={{ fontSize: type.base, background: badgeTone.green.bg, color: badgeTone.green.fg, padding: "10px 12px", borderRadius: radius.md, marginBottom: 12, fontWeight: 600 }}>✓ Versión publicada</div>
      )}
      <div style={{ display: "flex", gap: 8, marginBottom: 14 }}>
        <Badge tone={problemas.errores ? "error" : "green"}>{problemas.errores} errores</Badge>
        <Badge tone="amber">{problemas.avisos} avisos</Badge>
      </div>
      {problemas.problemas.length === 0 ? (
        <div style={{ fontSize: type.base, color: color.slate500 }}>Sin problemas. {problemas.puede_publicar ? "Lista para publicar." : ""}</div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {problemas.problemas.map((p, i) => (
            <div
              key={i}
              role={p.nodo_id ? "button" : undefined}
              tabIndex={p.nodo_id ? 0 : undefined}
              onClick={() => p.nodo_id && onFocus(p.nodo_id)}
              onKeyDown={(e) => { if (p.nodo_id && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); onFocus(p.nodo_id); } }}
              style={{ border: `1px solid ${color.divider}`, borderRadius: radius.md, padding: 12, cursor: p.nodo_id ? "pointer" : "default" }}
            >
              <span style={{ display: "inline-block", fontSize: type.micro, fontWeight: 700, letterSpacing: ".4px", background: sevBg[p.sev], color: sevColor[p.sev], padding: "2px 7px", borderRadius: radius.sm, marginBottom: 6 }}>
                {p.sev === "error" ? "ERROR" : "AVISO"}
              </span>
              <div style={{ fontSize: type.base, fontWeight: 600 }}>{p.titulo}</div>
              <div style={{ fontSize: type.sm, color: color.slate500, marginTop: 2 }}>{p.detalle}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// Aviso inline ámbar para configuraciones incompletas de un nodo.
function AvisoFalta({ texto }) {
  return (
    <div style={{ marginTop: 6, display: "flex", alignItems: "center", gap: 6, fontSize: type.xs, color: badgeTone.amber.fg, background: badgeTone.amber.bg, padding: "5px 8px", borderRadius: radius.sm }}>
      <span style={{ fontWeight: 800 }}>!</span> {texto}
    </div>
  );
}
