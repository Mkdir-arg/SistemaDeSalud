import { createContext, useContext, useEffect, useState } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { Logo } from "./Logo";
import { Avatar } from "./ui";
import { Icon } from "./icons";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useInstitucion } from "../auth/InstitutionContext";
import { antiguedad } from "../lib/format";
import { color } from "../theme";

// Estado de "última actualización" que una pantalla publica para mostrarlo en la
// barra superior (al lado de la campana). Null cuando no aplica.
const RefreshCtx = createContext({ refresco: null, setRefresco: () => {} });
export function useRefresh() { return useContext(RefreshCtx); }

function textoRefresco(r) {
  if (!r) return null;
  if (r.refrescando) return "Actualizando…";
  if (!r.ultima) return null;
  const s = Math.floor((Date.now() - new Date(r.ultima).getTime()) / 1000);
  return `Actualizado hace ${s < 50 ? "unos segundos" : antiguedad(r.ultima)}`;
}

const TITULOS = {
  "/inicio": "Inicio",
  "/dashboard": "Tablero",
  "/supervision": "Supervisión",
  "/notificaciones": "Notificaciones",
  "/bandeja": "Bandeja de tareas",
  "/filas": "Filas de espera",
  "/casos": "Casos",
  "/historia": "Historia clínica",
  "/legajo": "Legajo profesional",
  "/flujos": "Flujos",
  "/mapa": "Mapa de flujos",
  "/formularios": "Formularios",
  "/estructura": "Estructura organizativa",
  "/administracion": "Administración",
};
function tituloDeRuta(pathname) {
  if (pathname.startsWith("/casos/")) return "Detalle del caso";
  if (pathname.startsWith("/flujos/")) return "Diseñador de flujos";
  if (pathname.startsWith("/puesto/")) return "Detalle del paso";
  return TITULOS[pathname] || "Cauce";
}

// Campana de notificaciones: contador de no leídas + dropdown (poll a /resumen/).
function Campana() {
  const navigate = useNavigate();
  const [data, setData] = useState({ no_leidas: 0, items: [] });
  const [abierto, setAbierto] = useState(false);

  async function recargar() {
    try { setData(await api.get("/notificaciones/resumen/")); } catch { /* silencioso */ }
  }
  useEffect(() => {
    recargar();
    const tick = () => { if (!document.hidden) recargar(); };
    const id = setInterval(tick, 30000);
    window.addEventListener("focus", tick);
    return () => { clearInterval(id); window.removeEventListener("focus", tick); };
  }, []);

  async function abrir(n) {
    setAbierto(false);
    if (!n.leida) await api.post("/notificaciones/leer/", { ids: [n.id] });
    if (n.caso) navigate(`/casos/${n.caso}`);
    recargar();
  }
  async function marcarTodas() { await api.post("/notificaciones/leer/", {}); recargar(); }

  return (
    <div style={{ position: "relative", flex: "none" }}>
      <button onClick={() => setAbierto((v) => !v)} title="Notificaciones"
        style={{ position: "relative", border: "none", background: "none", cursor: "pointer", color: color.slate500, display: "flex", padding: 6 }}>
        <Icon name="bell" size={19} />
        {data.no_leidas > 0 && (
          <span style={{ position: "absolute", top: -1, right: -1, minWidth: 16, height: 16, padding: "0 4px", borderRadius: 8, background: color.danger, color: "#fff", fontSize: 10, fontWeight: 700, display: "flex", alignItems: "center", justifyContent: "center", boxSizing: "border-box" }}>
            {data.no_leidas > 9 ? "9+" : data.no_leidas}
          </span>
        )}
      </button>
      {abierto && (
        <>
          <div onClick={() => setAbierto(false)} style={{ position: "fixed", inset: 0, zIndex: 30 }} />
          <div style={{ position: "absolute", top: 42, right: 0, width: 324, background: "#fff", border: `1px solid ${color.border}`, borderRadius: 12, boxShadow: "0 12px 32px rgba(16,24,40,.18)", zIndex: 31, overflow: "hidden" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 14px", borderBottom: `1px solid ${color.divider}` }}>
              <span style={{ fontSize: 13, fontWeight: 700 }}>Notificaciones</span>
              {data.no_leidas > 0 && <button onClick={marcarTodas} style={{ border: "none", background: "none", color: color.accent, fontSize: 12, fontWeight: 600, cursor: "pointer" }}>Marcar todas</button>}
            </div>
            <div style={{ maxHeight: 360, overflowY: "auto" }}>
              {data.items.length === 0 ? (
                <div style={{ padding: "24px 14px", textAlign: "center", fontSize: 12.5, color: color.slate400 }}>Sin notificaciones</div>
              ) : data.items.map((n) => (
                <div key={n.id} onClick={() => abrir(n)}
                  style={{ display: "flex", gap: 10, padding: "11px 14px", borderTop: `1px solid ${color.divider}`, cursor: "pointer", background: n.leida ? "#fff" : color.accent50 }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 13, fontWeight: 600 }}>{n.titulo}</div>
                    {n.detalle && <div style={{ fontSize: 12, color: color.slate500 }}>{n.detalle}</div>}
                    <div style={{ fontSize: 11, color: color.slate400, marginTop: 2 }}>hace {antiguedad(n.creada)}</div>
                  </div>
                  {!n.leida && <span style={{ width: 8, height: 8, borderRadius: 99, background: color.accent, flex: "none", marginTop: 5 }} />}
                </div>
              ))}
            </div>
            <button onClick={() => { setAbierto(false); navigate("/notificaciones"); }}
              style={{ width: "100%", padding: "10px 14px", border: "none", borderTop: `1px solid ${color.divider}`, background: "#fff", color: color.accent, fontSize: 12.5, fontWeight: 600, cursor: "pointer" }}>
              Ver todas
            </button>
          </div>
        </>
      )}
    </div>
  );
}

// Buscador de pacientes (barra superior): nombre o documento → su historia clínica.
function BuscadorPacientes() {
  const { institucion } = useInstitucion();
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [res, setRes] = useState([]);
  const [buscando, setBuscando] = useState(false);
  const [abierto, setAbierto] = useState(false);

  useEffect(() => {
    const term = q.trim();
    if (!term || !institucion) { setRes([]); return; }
    setBuscando(true);
    const t = setTimeout(async () => {
      try {
        const d = await api.get(`/ciudadanos/?institucion=${institucion.id}&search=${encodeURIComponent(term)}`);
        setRes((d.results || d).slice(0, 8));
      } catch { /* silencioso */ } finally { setBuscando(false); }
    }, 250);
    return () => clearTimeout(t);
  }, [q, institucion]);

  function ir(c) {
    setQ(""); setRes([]); setAbierto(false);
    navigate(`/historia/${c.id}`);
  }

  return (
    <div style={{ position: "relative", width: "100%", maxWidth: 420 }}>
      <span style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)", color: color.slate400, display: "flex" }}>
        <Icon name="search" size={16} />
      </span>
      <input
        placeholder="Buscar paciente por nombre o documento…"
        value={q}
        onChange={(e) => { setQ(e.target.value); setAbierto(true); }}
        onFocus={() => setAbierto(true)}
        onKeyDown={(e) => { if (e.key === "Enter" && res[0]) ir(res[0]); if (e.key === "Escape") setAbierto(false); }}
        style={{ width: "100%", height: 38, border: `1px solid ${color.inputBorder}`, borderRadius: 9, padding: "0 12px 0 34px", fontSize: 13.5, background: color.subtle, outline: "none", boxSizing: "border-box" }}
      />
      {abierto && q.trim() && (
        <>
          <div onClick={() => setAbierto(false)} style={{ position: "fixed", inset: 0, zIndex: 20 }} />
          <div style={{ position: "absolute", top: 44, left: 0, right: 0, background: "#fff", border: `1px solid ${color.border}`, borderRadius: 10, boxShadow: "0 12px 32px rgba(16,24,40,.16)", zIndex: 21, overflow: "hidden", maxHeight: 360, overflowY: "auto" }}>
            {buscando ? (
              <div style={{ padding: "14px 16px", fontSize: 13, color: color.slate400 }}>Buscando…</div>
            ) : res.length === 0 ? (
              <div style={{ padding: "14px 16px", fontSize: 13, color: color.slate400 }}>Sin pacientes para «{q.trim()}».</div>
            ) : res.map((c, i) => (
              <div key={c.id} onClick={() => ir(c)}
                style={{ display: "flex", alignItems: "center", gap: 11, padding: "10px 14px", cursor: "pointer", borderTop: i ? `1px solid ${color.divider}` : "none" }}
                onMouseEnter={(e) => (e.currentTarget.style.background = color.subtle)}
                onMouseLeave={(e) => (e.currentTarget.style.background = "#fff")}>
                <Avatar nombre={`${c.nombre} ${c.apellido}`} i={c.id} size={30} />
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 13.5, fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{c.nombre} {c.apellido}</div>
                  <div style={{ fontSize: 11.5, color: color.slate400 }}>{c.documento ? `DNI ${c.documento}` : c.codigo || "Sin documento"}{c.obra_social ? ` · ${c.obra_social}` : ""}</div>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function TopBar() {
  const { logout } = useAuth();
  const { refresco } = useRefresh();
  const location = useLocation();
  const navigate = useNavigate();
  const txtRefresco = textoRefresco(refresco);
  // Volver: en toda página salvo el inicio (que es la base del recorrido).
  const puedeVolver = !["/inicio", "/"].includes(location.pathname);
  return (
    <header style={{ height: 64, flex: "none", background: "#fff", borderBottom: `1px solid ${color.border}`, display: "flex", alignItems: "center", gap: 14, padding: "0 26px" }}>
      {puedeVolver && (
        <button onClick={() => navigate(-1)} title="Volver"
          style={{ width: 34, height: 34, borderRadius: 9, border: `1px solid ${color.accent100}`, background: color.accent50, color: color.accent, display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer", flex: "none" }}>
          <Icon name="back" size={17} />
        </button>
      )}
      <div style={{ fontSize: 17, fontWeight: 700, letterSpacing: "-.2px", whiteSpace: "nowrap" }}>{tituloDeRuta(location.pathname)}</div>
      <div style={{ flex: 1, display: "flex", justifyContent: "center" }}>
        <BuscadorPacientes />
      </div>
      {txtRefresco && <span style={{ fontSize: 12, color: color.slate400, whiteSpace: "nowrap" }}>{txtRefresco}</span>}
      <Campana />
      <button onClick={() => { logout(); navigate("/login"); }} title="Cerrar sesión"
        style={{ height: 36, padding: "0 12px", borderRadius: 9, border: `1px solid ${color.accent100}`, background: color.accent50, color: color.accent, display: "flex", alignItems: "center", gap: 7, fontSize: 13, fontWeight: 600, cursor: "pointer", flex: "none" }}>
        <Icon name="power" size={15} /> Salir
      </button>
    </header>
  );
}

const ITEM_INICIO = { to: "/inicio", label: "Inicio", icon: "home" };

// Grupos del menú. Orden: configuración primero (SISTEMA), luego operación.
// Cada ítem se muestra según su capacidad (cap) y el rol del usuario.
const GRUPOS = [
  {
    label: "SISTEMA",
    items: [
      { to: "/dashboard", label: "Tablero", icon: "activity", cap: "config" },
      { to: "/estructura", label: "Estructura organizativa", icon: "cube", cap: "config" },
      { to: "/administracion", label: "Administración", icon: "users", cap: "config" },
      { to: "/flujos", label: "Flujos", icon: "workflow", cap: "diseno" },
      { to: "/mapa", label: "Mapa de flujos", icon: "map", cap: "diseno" },
      { to: "/formularios", label: "Formularios", icon: "form", cap: "diseno" },
    ],
  },
  {
    label: "TRABAJO",
    items: [
      // Bandeja / Filas / Casos se operan desde «Mi trabajo» (Inicio); quedan las
      // rutas vivas pero fuera del menú. Acá solo la vista de supervisión (jefe).
      { to: "/supervision", label: "Supervisión", icon: "users", cap: "supervision" },
    ],
  },
  {
    label: "REGISTROS",
    items: [
      { to: "/historia", label: "Historia clínica", icon: "clipboard", cap: "registros" },
      { to: "/legajo", label: "Legajo profesional", icon: "idCard", cap: "registros" },
    ],
  },
];

const ROL_LABEL = {
  admin: "Admin de institución",
  configurador: "Configurador",
  jefe_area: "Jefe / Supervisor de área",
  administrativo: "Administrativo",
  enfermeria: "Enfermería",
  medico: "Médico / profesional",
};

const itemStyle = (col) => ({ isActive }) => ({
  display: "flex",
  alignItems: "center",
  justifyContent: col ? "center" : "flex-start",
  gap: 11,
  padding: col ? "10px 0" : "9px 12px",
  borderRadius: 9,
  fontSize: 13.5,
  fontWeight: 600,
  color: isActive ? "#fff" : color.slate600,
  background: isActive ? color.accent : "transparent",
});

export function Shell({ children }) {
  const { user, logout } = useAuth();
  const { institucion, setInstitucion, roles, puedeVer } = useInstitucion();
  const navigate = useNavigate();

  // "Última actualización" que publica la pantalla activa (lo muestra la TopBar).
  const [refresco, setRefresco] = useState(null);

  // Menú lateral colapsable (recordado entre sesiones).
  const [colapsado, setColapsado] = useState(() => localStorage.getItem("cauce.menu") === "col");
  const toggleMenu = () => setColapsado((v) => { localStorage.setItem("cauce.menu", v ? "exp" : "col"); return !v; });

  // Instituciones del usuario (no-super): habilitan el selector si hay más de una.
  const [misInst, setMisInst] = useState([]);
  const [menuInst, setMenuInst] = useState(false);
  useEffect(() => {
    if (!user || user.is_superuser) return;
    api.get("/instituciones/").then((d) => setMisInst(d.results || d)).catch(() => {});
  }, [user]);
  const puedeCambiar = !user?.is_superuser && misInst.length > 1;

  // Contador de tareas pendientes para roles operativos (el "Inicio" es su worklist).
  // Se refresca solo cada 30s y se pausa con la pestaña oculta.
  const operativo = puedeVer("trabajo") && !puedeVer("config") && !puedeVer("diseno");
  const [pendientes, setPendientes] = useState(0);
  useEffect(() => {
    if (!operativo || !institucion) { setPendientes(0); return; }
    let activo = true;
    const cargar = async () => {
      try {
        const d = await api.get(`/mis-tareas/?institucion=${institucion.id}`);
        if (!activo) return;
        const t = (d.tareas || []).reduce((s, b) => s + (b.total || 0), 0);
        const f = (d.filas || []).reduce((s, x) => s + (x.en_cola || 0), 0);
        setPendientes(t + f);
      } catch { /* silencioso */ }
    };
    cargar();
    const id = setInterval(() => { if (!document.hidden) cargar(); }, 30000);
    return () => { activo = false; clearInterval(id); };
  }, [operativo, institucion]);

  function cambiarInstitucion(inst) {
    setMenuInst(false);
    if (inst.id === institucion?.id) return;
    setInstitucion(inst);
    navigate("/inicio");
  }

  const rolLabel = user?.is_superuser
    ? "Super admin"
    : roles.map((r) => ROL_LABEL[r] || r).join(" · ") || "Usuario";

  return (
    <RefreshCtx.Provider value={{ refresco, setRefresco }}>
    <div style={{ display: "flex", minHeight: "100vh", background: color.canvas }}>
      <aside style={{ width: colapsado ? 68 : 244, transition: "width .15s ease", background: "#fff", borderRight: `1px solid ${color.border}`, display: "flex", flexDirection: "column", flex: "none", height: "100vh", position: "sticky", top: 0 }}>
        {/* Cabecera: institución + colapsar (en una sola fila) */}
        <div style={{ position: "relative", flex: "none", display: "flex", alignItems: "center", gap: 8, flexDirection: colapsado ? "column" : "row", padding: colapsado ? "14px 0 12px" : "14px 12px", borderBottom: colapsado ? `1px solid ${color.divider}` : "none" }}>
          <button
            onClick={() => puedeCambiar && !colapsado && setMenuInst((v) => !v)}
            title={colapsado ? institucion?.nombre : undefined}
            style={{ display: "flex", alignItems: "center", gap: 11, flex: colapsado ? "none" : 1, minWidth: 0, padding: 0, background: "none", border: "none", textAlign: "left", cursor: (puedeCambiar && !colapsado) ? "pointer" : "default" }}
          >
            <Logo size={34} />
            {!colapsado && (
              <div style={{ lineHeight: 1.15, minWidth: 0 }}>
                <div style={{ fontSize: 14, fontWeight: 700, letterSpacing: "-.2px", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                  {institucion?.nombre || "Cauce"}
                </div>
                <div style={{ fontSize: 11, color: color.slate400, fontWeight: 500 }}>{institucion?.tipo || "Institución"}</div>
              </div>
            )}
          </button>
          <button onClick={toggleMenu} title={colapsado ? "Expandir menú" : "Colapsar menú"}
            style={{ width: 28, height: 28, borderRadius: 8, border: `1px solid ${color.accent100}`, background: color.accent50, color: color.accent, display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer", flex: "none" }}>
            <Icon name="back" size={14} style={{ transform: colapsado ? "rotate(180deg)" : "none" }} />
          </button>

          {/* Menú desplegable de instituciones */}
          {menuInst && !colapsado && (
            <>
              <div onClick={() => setMenuInst(false)} style={{ position: "fixed", inset: 0, zIndex: 20 }} />
              <div style={{ position: "absolute", top: 62, left: 12, right: 12, background: "#fff", border: `1px solid ${color.border}`, borderRadius: 10, boxShadow: "0 8px 24px rgba(16,24,40,.16)", zIndex: 21, padding: 6, maxHeight: 280, overflowY: "auto" }}>
                <div style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: ".6px", color: color.slate400, padding: "6px 8px 4px" }}>CAMBIAR DE INSTITUCIÓN</div>
                {misInst.map((inst) => {
                  const activa = inst.id === institucion?.id;
                  return (
                    <button
                      key={inst.id}
                      onClick={() => cambiarInstitucion(inst)}
                      style={{ display: "flex", alignItems: "center", gap: 9, width: "100%", padding: "9px 8px", borderRadius: 7, border: "none", background: activa ? color.accent50 : "transparent", cursor: "pointer", textAlign: "left" }}
                    >
                      <div style={{ width: 26, height: 26, borderRadius: 7, background: color.subtle, color: color.slate500, display: "flex", alignItems: "center", justifyContent: "center", flex: "none" }}><Icon name="building" size={14} /></div>
                      <div style={{ minWidth: 0, flex: 1 }}>
                        <div style={{ fontSize: 13, fontWeight: 600, color: activa ? color.accent : color.slate700, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{inst.nombre}</div>
                        <div style={{ fontSize: 11, color: color.slate400 }}>{inst.tipo || "Institución"}</div>
                      </div>
                      {activa && <Icon name="enter" size={14} style={{ color: color.accent }} />}
                    </button>
                  );
                })}
              </div>
            </>
          )}
        </div>

        {/* Volver al directorio (super admin) / rol del usuario (no-super) — solo expandido */}
        {!colapsado && (
          <div style={{ flex: "none", padding: "10px 14px", borderBottom: `1px solid ${color.divider}` }}>
            {user?.is_superuser ? (
              <button
                onClick={() => { setInstitucion(null); navigate("/"); }}
                style={{ display: "flex", alignItems: "center", gap: 7, width: "100%", padding: "8px 10px", borderRadius: 8, background: "#F2F3F6", color: color.slate600, fontSize: 12, fontWeight: 600, border: "none", cursor: "pointer" }}
              >
                <Icon name="back" size={14} /> Volver al directorio
              </button>
            ) : (
              <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: color.slate400, padding: "4px 2px" }}>
                <Icon name="power" size={12} /> {rolLabel}{puedeCambiar ? "" : " · acceso fijo"}
              </div>
            )}
          </div>
        )}

        {/* Navegación */}
        <nav style={{ flex: 1, overflowY: "auto", padding: colapsado ? "12px 10px" : "12px 12px", display: "flex", flexDirection: "column", gap: 3 }}>
          <NavLink to={ITEM_INICIO.to} style={itemStyle(colapsado)} title={operativo ? "Mi trabajo" : "Inicio"}>
            {({ isActive }) => (
              <>
                <span style={{ position: "relative", display: "flex" }}>
                  <Icon name={ITEM_INICIO.icon} size={17} />
                  {colapsado && operativo && pendientes > 0 && (
                    <span style={{ position: "absolute", top: -5, right: -7, minWidth: 15, height: 15, padding: "0 3px", borderRadius: 8, background: color.danger, color: "#fff", fontSize: 9.5, fontWeight: 700, display: "flex", alignItems: "center", justifyContent: "center", boxSizing: "border-box" }}>
                      {pendientes > 9 ? "9+" : pendientes}
                    </span>
                  )}
                </span>
                {!colapsado && (operativo ? "Mi trabajo" : ITEM_INICIO.label)}
                {!colapsado && operativo && pendientes > 0 && (
                  <span style={{ marginLeft: "auto", minWidth: 20, height: 20, padding: "0 6px", borderRadius: 10, fontSize: 11.5, fontWeight: 700, display: "inline-flex", alignItems: "center", justifyContent: "center", background: isActive ? "rgba(255,255,255,.25)" : color.accent50, color: isActive ? "#fff" : color.accent }}>
                    {pendientes}
                  </span>
                )}
              </>
            )}
          </NavLink>

          {GRUPOS.map((g) => {
            const items = g.items.filter((n) => puedeVer(n.cap));
            if (!items.length) return null;
            return (
              <div key={g.label}>
                {colapsado
                  ? <div style={{ height: 1, background: color.divider, margin: "8px 8px 6px" }} />
                  : <div style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: ".7px", color: color.slate400, padding: "12px 12px 6px" }}>{g.label}</div>}
                <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                  {items.map((n) => (
                    <NavLink key={n.to} to={n.to} style={itemStyle(colapsado)} end={n.to === "/flujos"} title={n.label}>
                      <Icon name={n.icon} size={17} />
                      {!colapsado && n.label}
                    </NavLink>
                  ))}
                </div>
              </div>
            );
          })}
        </nav>

        {/* Usuario */}
        <div style={{ flex: "none", borderTop: `1px solid ${color.divider}`, padding: colapsado ? "12px 0" : 14, display: "flex", flexDirection: colapsado ? "column" : "row", alignItems: "center", gap: colapsado ? 8 : 11 }}>
          <Avatar nombre={user?.nombre_completo || user?.email} size={34} />
          {!colapsado && (
            <div style={{ minWidth: 0, flex: 1, lineHeight: 1.25 }}>
              <div style={{ fontSize: 13, fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{user?.nombre_completo || user?.email}</div>
              <div style={{ fontSize: 11, color: color.slate400 }}>{rolLabel}</div>
            </div>
          )}
          <button onClick={() => { logout(); navigate("/login"); }} title="Cerrar sesión" style={{ border: "none", background: "none", cursor: "pointer", color: color.slate400, display: "flex" }}>
            <Icon name="power" size={17} />
          </button>
        </div>
      </aside>

      <main style={{ flex: 1, minWidth: 0, height: "100vh", display: "flex", flexDirection: "column" }}>
        <TopBar />
        <div style={{ flex: 1, overflow: "auto", minHeight: 0 }}>{children}</div>
      </main>
    </div>
    </RefreshCtx.Provider>
  );
}

// Barra de contenido (subtítulo + acciones). El título grande vive en la TopBar.
export function PageHeader({ title, subtitle, right }) {
  if (!subtitle && !right) return null;
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "20px 32px 0", gap: 16 }}>
      <div style={{ fontSize: 13.5, color: color.slate500 }}>{subtitle}</div>
      {right}
    </div>
  );
}
