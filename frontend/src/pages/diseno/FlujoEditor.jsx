import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../../api/client";
import { Badge, Button, Field, Input, Select, Spinner } from "../../components/ui";
import { Icon } from "../../components/icons";
import { caminoPorDefecto, correrAuto, nodoInicio, siguiente } from "../../lib/simular";
import { color, estadoVersion, nodeCat } from "../../theme";

const NODO_W = 184;
const NODO_H = 64;
const PALETA = Object.entries(nodeCat).map(([tipo, c]) => ({ tipo, ...c }));

export default function FlujoEditor() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [flujo, setFlujo] = useState(null);
  const [version, setVersion] = useState(null); // versión completa (nodos+conexiones)
  const [verId, setVerId] = useState(null);
  const [sel, setSel] = useState(null); // id de nodo seleccionado
  const [problemas, setProblemas] = useState(null);
  const [conectarDesde, setConectarDesde] = useState(null);
  const [campos, setCampos] = useState([]); // campos disponibles para reglas
  const [cargando, setCargando] = useState(true);
  const [errorCarga, setErrorCarga] = useState(null);
  const [sim, setSim] = useState(null); // modo Probar: {current, valores, camino, fin}
  const [repro, setRepro] = useState(null); // Reproducir: {camino, idx}

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

  // --- Drag de nodos -------------------------------------------------------
  const drag = useRef(null);
  const canvasRef = useRef(null);

  function onNodoMouseDown(e, nodo) {
    e.stopPropagation();
    const rect = canvasRef.current.getBoundingClientRect();
    drag.current = {
      id: nodo.id,
      dx: e.clientX - rect.left - nodo.x,
      dy: e.clientY - rect.top - nodo.y,
    };
    setSel(nodo.id);
  }

  useEffect(() => {
    function onMove(e) {
      if (!drag.current) return;
      const rect = canvasRef.current.getBoundingClientRect();
      const x = Math.max(0, e.clientX - rect.left - drag.current.dx);
      const y = Math.max(0, e.clientY - rect.top - drag.current.dy);
      setVersion((v) => ({ ...v, nodos: v.nodos.map((n) => (n.id === drag.current.id ? { ...n, x, y } : n)) }));
    }
    async function onUp() {
      if (!drag.current) return;
      const nodo = version?.nodos.find((n) => n.id === drag.current.id);
      drag.current = null;
      if (nodo) await api.patch(`/nodos/${nodo.id}/`, { x: Math.round(nodo.x), y: Math.round(nodo.y) });
    }
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, [version]);

  // --- Acciones ------------------------------------------------------------
  async function agregarNodo(tipo) {
    const cat = nodeCat[tipo];
    const n = await api.post("/nodos/", {
      version: verId,
      tipo,
      titulo: cat.name,
      x: 360 + (version.nodos.length % 4) * 40,
      y: 120 + (version.nodos.length % 5) * 50,
    });
    setVersion((v) => ({ ...v, nodos: [...v.nodos, n] }));
    setSel(n.id);
  }

  async function clickNodo(nodo) {
    if (conectarDesde && conectarDesde !== nodo.id) {
      const c = await api.post("/conexiones/", { version: verId, origen: conectarDesde, destino: nodo.id });
      setVersion((v) => ({ ...v, conexiones: [...v.conexiones, c] }));
      setConectarDesde(null);
      return;
    }
    setSel(nodo.id);
  }

  async function actualizarNodo(nodoId, cambios) {
    const n = await api.patch(`/nodos/${nodoId}/`, cambios);
    setVersion((v) => ({ ...v, nodos: v.nodos.map((x) => (x.id === nodoId ? n : x)) }));
  }
  async function borrarNodo(nodoId) {
    await api.del(`/nodos/${nodoId}/`);
    setVersion((v) => ({
      ...v,
      nodos: v.nodos.filter((n) => n.id !== nodoId),
      conexiones: v.conexiones.filter((c) => c.origen !== nodoId && c.destino !== nodoId),
    }));
    setSel(null);
  }
  async function borrarConexion(cid) {
    await api.del(`/conexiones/${cid}/`);
    setVersion((v) => ({ ...v, conexiones: v.conexiones.filter((c) => c.id !== cid) }));
  }
  async function actualizarConexion(cid, cambios) {
    const c = await api.patch(`/conexiones/${cid}/`, cambios);
    setVersion((v) => ({ ...v, conexiones: v.conexiones.map((x) => (x.id === cid ? c : x)) }));
  }

  async function validar() {
    const r = await api.get(`/versiones-flujo/${verId}/validar/`);
    setProblemas(r);
  }
  async function publicar() {
    try {
      await api.post(`/versiones-flujo/${verId}/publicar/`, {});
      await cargarVersion(verId);
      const f = await api.get(`/flujos/${id}/`);
      setFlujo(f);
      setProblemas({ problemas: [], errores: 0, avisos: 0, puede_publicar: true, publicado: true });
    } catch (e) {
      if (e?.data?.problemas) setProblemas({ ...e.data, errores: e.data.problemas.filter((p) => p.sev === "error").length });
    }
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
    if (repro.idx >= repro.camino.length - 1) {
      const t = setTimeout(() => setRepro(null), 1200);
      return () => clearTimeout(t);
    }
    const t = setTimeout(() => setRepro((r) => (r ? { ...r, idx: r.idx + 1 } : r)), 750);
    return () => clearTimeout(t);
  }, [repro]);

  if (cargando) return <Spinner label="Cargando flujo…" />;
  if (errorCarga)
    return (
      <div style={{ padding: 40, maxWidth: 460 }}>
        <div style={{ fontSize: 15, fontWeight: 700, color: "#B42318", marginBottom: 6 }}>No se pudo cargar el flujo</div>
        <div style={{ fontSize: 13.5, color: color.slate600, marginBottom: 16 }}>{errorCarga}</div>
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

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      {/* Barra superior */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "14px 24px", borderBottom: `1px solid ${color.border}`, background: "#fff", flex: "none" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <button onClick={() => navigate("/flujos")} style={{ border: "none", background: "none", cursor: "pointer", fontSize: 13.5, color: color.slate500 }}>← Flujos</button>
          <div style={{ fontSize: 17, fontWeight: 800, letterSpacing: "-.4px" }}>{flujo.titulo}</div>
          {flujo.ambito_label && <span style={{ fontSize: 12.5, color: color.slate400 }}>· {flujo.ambito_label}</span>}
          <Badge tone={estV.tone}>{estV.label}</Badge>
          <Select value={verId} onChange={(e) => { setVerId(Number(e.target.value)); cargarVersion(Number(e.target.value)); }} style={{ height: 32, width: "auto" }}>
            {flujo.versiones.map((v) => <option key={v.id} value={v.id}>{v.etiqueta}</option>)}
          </Select>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <Button variant="secondary" onClick={reproducir} style={{ display: "flex", alignItems: "center", gap: 7 }}>▶ Reproducir</Button>
          <Button variant="secondary" onClick={iniciarSim} style={{ display: "flex", alignItems: "center", gap: 7 }}>Probar</Button>
          <Button variant="secondary" onClick={validar}>Validar</Button>
          <Button onClick={publicar} disabled={version.estado === "publicada"}>Publicar</Button>
        </div>
      </div>

      <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
        {/* Paleta */}
        <div style={{ width: 188, borderRight: `1px solid ${color.border}`, background: "#fff", padding: 12, overflow: "auto", flex: "none" }}>
          <div style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: ".6px", color: color.slate400, margin: "4px 4px 10px" }}>NODOS</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {PALETA.map((p) => (
              <button
                key={p.tipo}
                onClick={() => agregarNodo(p.tipo)}
                style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 10px", border: `1px solid ${color.border}`, borderRadius: 10, background: "#fff", cursor: "pointer", textAlign: "left" }}
              >
                <span style={{ width: 26, height: 26, borderRadius: 7, background: p.tint, border: `1px solid ${p.bd}`, display: "flex", alignItems: "center", justifyContent: "center", flex: "none" }}>
                  <span style={{ width: 10, height: 10, borderRadius: p.tipo === "decision" ? 2 : 3, background: p.sol, transform: p.tipo === "decision" ? "rotate(45deg)" : "none" }} />
                </span>
                <span style={{ fontSize: 12.5, fontWeight: 600, color: color.slate700 }}>{p.name}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Canvas */}
        <div style={{ flex: 1, overflow: "auto", background: "#FBFBFD", position: "relative" }}>
          <div
            ref={canvasRef}
            onClick={() => { setSel(null); setConectarDesde(null); }}
            style={{
              position: "relative",
              width: 2200,
              height: 1300,
              backgroundImage: "radial-gradient(circle, #D9DDE5 1.1px, transparent 1.1px)",
              backgroundSize: "20px 20px",
            }}
          >
            {/* Conexiones */}
            <svg style={{ position: "absolute", inset: 0, width: "100%", height: "100%", pointerEvents: "none" }}>
              <defs>
                <marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth">
                  <path d="M0,0 L8,3 L0,6 Z" fill="#9AA2B1" />
                </marker>
              </defs>
              {version.conexiones.map((c) => {
                const o = version.nodos.find((n) => n.id === c.origen);
                const d = version.nodos.find((n) => n.id === c.destino);
                if (!o || !d) return null;
                const x1 = o.x + NODO_W, y1 = o.y + NODO_H / 2;
                const x2 = d.x, y2 = d.y + NODO_H / 2;
                const mx = (x1 + x2) / 2;
                return (
                  <g key={c.id}>
                    <path d={`M ${x1} ${y1} C ${mx} ${y1}, ${mx} ${y2}, ${x2} ${y2}`} stroke="#9AA2B1" strokeWidth="1.6" fill="none" markerEnd="url(#arrow)" />
                    {c.etiqueta && (
                      <text x={mx} y={(y1 + y2) / 2 - 6} fill={color.slate500} fontSize="11" textAnchor="middle" style={{ fontWeight: 600 }}>{c.etiqueta}</text>
                    )}
                  </g>
                );
              })}
            </svg>

            {/* Nodos */}
            {version.nodos.map((n) => {
              const cat = nodeCat[n.tipo] || nodeCat.form;
              const seleccionado = n.id === sel;
              const esOrigenConexion = conectarDesde === n.id;
              const enFoco = n.id === nodoEnFoco;
              return (
                <div
                  key={n.id}
                  onMouseDown={(e) => onNodoMouseDown(e, n)}
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
                    borderRadius: 14,
                    padding: "11px 13px",
                    cursor: "grab",
                    boxShadow: enFoco ? `0 0 0 4px ${cat.sol}55, 0 8px 20px rgba(16,24,40,.14)` : seleccionado ? `0 0 0 3px ${cat.sol}33` : "0 1px 3px rgba(16,24,40,.07)",
                    transition: "box-shadow .2s, border-color .2s",
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                  }}
                >
                  <span style={{ width: 11, height: 11, borderRadius: n.tipo === "decision" ? 2 : 3, background: cat.sol, transform: n.tipo === "decision" ? "rotate(45deg)" : "none", flex: "none" }} />
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <div style={{ fontSize: 9.5, fontWeight: 700, letterSpacing: ".4px", color: cat.sol, opacity: 0.85 }}>{cat.name.toUpperCase()}</div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: "#1F2430", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{n.titulo}</div>
                    {n.grupos_detalle?.length > 0 && (
                      <div title={`Responsable: ${n.grupos_detalle.map((g) => g.nombre).join(", ")}`} style={{ display: "flex", alignItems: "center", gap: 4, marginTop: 3, fontSize: 10.5, color: color.slate500, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                        <Icon name="users" size={11} />
                        {n.grupos_detalle.length === 1 ? n.grupos_detalle[0].nombre : `${n.grupos_detalle.length} grupos`}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}

            {/* Token de "Reproducir" viajando por el lienzo */}
            {reproNodo && (
              <div style={{ position: "absolute", left: reproNodo.x + NODO_W / 2 - 9, top: reproNodo.y + NODO_H / 2 - 9, width: 18, height: 18, borderRadius: "50%", background: color.accent, border: "3px solid #fff", boxShadow: `0 0 0 4px ${color.accent}55, 0 6px 16px rgba(16,24,40,.3)`, transition: "left .65s cubic-bezier(.5,0,.2,1), top .65s cubic-bezier(.5,0,.2,1)", pointerEvents: "none", zIndex: 5 }} />
            )}
          </div>
          {conectarDesde && (
            <div style={{ position: "fixed", bottom: 24, left: "50%", transform: "translateX(-50%)", background: color.slate900, color: "#fff", padding: "8px 16px", borderRadius: 999, fontSize: 12.5 }}>
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
            <div style={{ padding: 22, fontSize: 13, color: color.slate400 }}>
              Seleccioná un nodo para editar sus propiedades, o arrastrá uno desde la paleta.
            </div>
          )}
        </div>
      </div>
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
        <div style={{ fontSize: 14.5, fontWeight: 700, display: "flex", alignItems: "center", gap: 7 }}>
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#1F8A5B" }} /> Modo prueba
        </div>
        <button onClick={onCerrar} style={{ border: "none", background: "none", cursor: "pointer", color: color.slate400, fontSize: 18 }}>×</button>
      </div>
      <div style={{ fontSize: 12, color: color.slate500, marginBottom: 16 }}>Simulación sin datos reales. Recorré el flujo como lo haría un caso.</div>

      {sim.error ? (
        <div style={{ fontSize: 13, color: "#B42318", background: "#FCEBEB", padding: "10px 12px", borderRadius: 9 }}>{sim.error}</div>
      ) : sim.fin ? (
        <div style={{ background: "#E6F5EC", color: "#1B7A4E", padding: "14px 16px", borderRadius: 11, fontSize: 13.5, fontWeight: 600 }}>
          ✓ Caso simulado {sim.sinSalida ? "detenido (nodo sin salida)" : "finalizado"}.
        </div>
      ) : nodo ? (
        <>
          <div style={{ border: `1px solid ${cat.bd}`, background: cat.tint, borderRadius: 11, padding: 13, marginBottom: 14 }}>
            <div style={{ fontSize: 9.5, fontWeight: 700, letterSpacing: ".4px", color: cat.sol }}>{cat.name.toUpperCase()}</div>
            <div style={{ fontSize: 14, fontWeight: 700, color: "#1F2430" }}>{nodo.titulo}</div>
          </div>

          {nodo.tipo === "form" && (
            <div style={{ display: "flex", flexDirection: "column", gap: 12, marginBottom: 14 }}>
              {camposForm.length === 0 ? (
                <div style={{ fontSize: 12.5, color: color.slate400 }}>Este formulario no tiene campos (o no está asignado).</div>
              ) : camposForm.map((c) => (
                <div key={c.id}>
                  <div style={{ fontSize: 12.5, fontWeight: 600, color: color.slate600, marginBottom: 5 }}>{c.label}{c.requerido && <span style={{ color: "#B42318" }}> *</span>}</div>
                  {c.tipo === "seleccion_unica" ? (
                    <Select style={{ height: 34, fontSize: 12.5 }} value={valores[c.id] || ""} onChange={(e) => setValores((v) => ({ ...v, [c.id]: e.target.value }))}>
                      <option value="">Seleccionar…</option>
                      {(c.opciones || []).map((o) => <option key={o} value={o}>{o}</option>)}
                    </Select>
                  ) : (
                    <Input style={{ height: 34, fontSize: 12.5 }} type={c.tipo === "fecha" ? "date" : "text"} value={valores[c.id] || ""} onChange={(e) => setValores((v) => ({ ...v, [c.id]: e.target.value }))} />
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
        <div style={{ fontSize: 13, color: color.slate400 }}>Sin nodo actual.</div>
      )}

      {/* Recorrido */}
      <div style={{ marginTop: 18, borderTop: `1px solid ${color.divider}`, paddingTop: 14 }}>
        <div style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: ".5px", color: color.slate400, marginBottom: 8 }}>RECORRIDO</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          {(sim.camino || []).map((nid, i) => {
            const n = version.nodos.find((x) => x.id === nid);
            if (!n) return null;
            const c = nodeCat[n.tipo] || nodeCat.form;
            return (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12.5, color: nid === sim.current ? color.slate900 : color.slate500 }}>
                <span style={{ width: 8, height: 8, borderRadius: 2, background: c.sol, flex: "none" }} />
                {n.titulo}
              </div>
            );
          })}
        </div>
        <button onClick={onReiniciar} style={{ marginTop: 12, border: "none", background: "none", color: color.accent, cursor: "pointer", fontSize: 12.5, fontWeight: 600 }}>↻ Reiniciar prueba</button>
      </div>
    </div>
  );
}

// --------------------------------------------------------------------------- //
const OPERADORES = ["=", "!=", ">", "<", "contiene"];

function RuleBuilder({ conexion, campos, onActualizar }) {
  const cond = conexion.condicion || {};
  const set = (cambios) => onActualizar(conexion.id, { condicion: { ...cond, ...cambios } });
  const campoSel = campos.find((c) => String(c.id) === String(cond.campo));
  return (
    <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 6 }}>
      <div style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: ".4px", color: color.slate400 }}>SI…</div>
      <Select style={{ height: 32, fontSize: 12.5 }} value={cond.campo || ""} onChange={(e) => set({ campo: e.target.value ? Number(e.target.value) : null })}>
        <option value="">(sin condición · rama por defecto)</option>
        {campos.map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}
      </Select>
      {cond.campo && (
        <div style={{ display: "flex", gap: 6 }}>
          <Select style={{ height: 32, fontSize: 12.5, width: 90 }} value={cond.operador || "="} onChange={(e) => set({ operador: e.target.value })}>
            {OPERADORES.map((o) => <option key={o} value={o}>{o}</option>)}
          </Select>
          {campoSel?.opciones?.length ? (
            <Select style={{ height: 32, fontSize: 12.5 }} value={cond.valor || ""} onChange={(e) => set({ valor: e.target.value })}>
              <option value="">valor…</option>
              {campoSel.opciones.map((o) => <option key={o} value={o}>{o}</option>)}
            </Select>
          ) : (
            <Input style={{ height: 32, fontSize: 12.5 }} placeholder="valor" defaultValue={cond.valor || ""} onBlur={(e) => e.target.value !== cond.valor && set({ valor: e.target.value })} />
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
  const [ayuda, setAyuda] = useState(false);
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
        <div style={{ flex: 1, fontSize: 10.5, fontWeight: 700, letterSpacing: ".5px", color: color.slate400 }}>{cat.name.toUpperCase()}</div>
        <button
          onClick={() => setAyuda((v) => !v)}
          title="¿Qué hace este nodo?"
          style={{ width: 26, height: 26, borderRadius: 7, border: `1px solid ${ayuda ? color.accent : color.inputBorder}`, background: ayuda ? color.accent50 : "#fff", color: ayuda ? color.accent : color.slate400, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", flex: "none" }}
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
              {["recibido", "en_evaluacion", "en_espera", "derivado", "atendido", "cerrado"].map((s) => <option key={s} value={s}>{s}</option>)}
            </Select>
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
            {asignados.size > 0 && (
              <div style={{ marginTop: 6, fontSize: 11, color: color.slate400 }}>
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
                    <span style={{ fontSize: 12.5, fontWeight: 600 }}>→ {destino?.titulo || "?"}</span>
                    <button onClick={() => onBorrarConexion(c.id)} style={{ border: "none", background: "none", color: "#B42318", cursor: "pointer", fontSize: 11.5 }}>quitar</button>
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

        <button onClick={() => onBorrar(nodo.id)} style={{ marginTop: 6, border: "none", background: "#FCEBEB", color: "#B42318", padding: "9px 0", borderRadius: 9, cursor: "pointer", fontSize: 13, fontWeight: 600 }}>
          Eliminar nodo
        </button>
      </div>
    </div>
  );
}

function PanelValidacion({ problemas, onCerrar, onFocus }) {
  const sevColor = { error: "#B42318", aviso: "#A96A12" };
  const sevBg = { error: "#FCEBEB", aviso: "#FBF0DD" };
  return (
    <div style={{ padding: 20 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
        <div style={{ fontSize: 14.5, fontWeight: 700 }}>Validación</div>
        <button onClick={onCerrar} style={{ border: "none", background: "none", cursor: "pointer", color: color.slate400, fontSize: 18 }}>×</button>
      </div>
      {problemas.publicado && (
        <div style={{ fontSize: 13, background: "#E6F5EC", color: "#1B7A4E", padding: "10px 12px", borderRadius: 9, marginBottom: 12, fontWeight: 600 }}>✓ Versión publicada</div>
      )}
      <div style={{ display: "flex", gap: 8, marginBottom: 14 }}>
        <Badge tone={problemas.errores ? "error" : "green"}>{problemas.errores} errores</Badge>
        <Badge tone="amber">{problemas.avisos} avisos</Badge>
      </div>
      {problemas.problemas.length === 0 ? (
        <div style={{ fontSize: 13, color: color.slate500 }}>Sin problemas. {problemas.puede_publicar ? "Lista para publicar." : ""}</div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {problemas.problemas.map((p, i) => (
            <div
              key={i}
              onClick={() => p.nodo_id && onFocus(p.nodo_id)}
              style={{ border: `1px solid ${color.divider}`, borderRadius: 10, padding: 12, cursor: p.nodo_id ? "pointer" : "default" }}
            >
              <span style={{ display: "inline-block", fontSize: 10, fontWeight: 700, letterSpacing: ".4px", background: sevBg[p.sev], color: sevColor[p.sev], padding: "2px 7px", borderRadius: 6, marginBottom: 6 }}>
                {p.sev === "error" ? "ERROR" : "AVISO"}
              </span>
              <div style={{ fontSize: 13, fontWeight: 600 }}>{p.titulo}</div>
              <div style={{ fontSize: 12, color: color.slate500, marginTop: 2 }}>{p.detalle}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
