import { useEffect, useState } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { Logo } from "./Logo";
import { Avatar } from "./ui";
import { Icon } from "./icons";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useInstitucion } from "../auth/InstitutionContext";
import { color } from "../theme";

const TITULOS = {
  "/inicio": "Inicio",
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
  return TITULOS[pathname] || "Cauce";
}

const VISTAS = [
  { key: "configurador", label: "Configurador" },
  { key: "administrativo", label: "Administrativo" },
  { key: "sistema", label: "Sistema" },
];

function TopBar() {
  const { user } = useAuth();
  const { vista, setVista } = useInstitucion();
  const location = useLocation();
  return (
    <header style={{ height: 64, flex: "none", background: "#fff", borderBottom: `1px solid ${color.border}`, display: "flex", alignItems: "center", gap: 20, padding: "0 26px" }}>
      <div style={{ fontSize: 17, fontWeight: 700, letterSpacing: "-.2px", whiteSpace: "nowrap" }}>{tituloDeRuta(location.pathname)}</div>
      <div style={{ flex: 1, display: "flex", justifyContent: "center" }}>
        <div style={{ position: "relative", width: "100%", maxWidth: 380 }}>
          <span style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)", color: color.slate400, display: "flex" }}>
            <Icon name="search" size={16} />
          </span>
          <input placeholder="Buscar casos, flujos, personas…" style={{ width: "100%", height: 38, border: `1px solid ${color.inputBorder}`, borderRadius: 9, padding: "0 12px 0 34px", fontSize: 13.5, background: color.subtle, outline: "none" }} />
        </div>
      </div>
      {user?.is_superuser && (
        <div style={{ display: "flex", alignItems: "center", background: "#F2F3F6", border: `1px solid ${color.border}`, borderRadius: 9, padding: 3, gap: 2, flex: "none" }}>
          {VISTAS.map((v) => (
            <button
              key={v.key}
              onClick={() => setVista(v.key)}
              style={{ padding: "6px 12px", borderRadius: 7, fontSize: 12.5, fontWeight: 600, border: "none", cursor: "pointer", background: vista === v.key ? "#fff" : "transparent", color: vista === v.key ? color.accent : color.slate500, boxShadow: vista === v.key ? "0 1px 2px rgba(16,24,40,.12)" : "none" }}
            >
              {v.label}
            </button>
          ))}
        </div>
      )}
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
      { to: "/bandeja", label: "Bandeja de tareas", icon: "inbox", cap: "trabajo" },
      { to: "/filas", label: "Filas de espera", icon: "list", cap: "trabajo" },
      { to: "/casos", label: "Casos", icon: "fileText", cap: "trabajo" },
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
  administrativo: "Administrativo",
  medico: "Médico / profesional",
};

const itemStyle = ({ isActive }) => ({
  display: "flex",
  alignItems: "center",
  gap: 11,
  padding: "9px 12px",
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
    <div style={{ display: "flex", minHeight: "100vh", background: color.canvas }}>
      <aside style={{ width: 244, background: "#fff", borderRight: `1px solid ${color.border}`, display: "flex", flexDirection: "column", flex: "none", height: "100vh", position: "sticky", top: 0 }}>
        {/* Cabecera: institución actual (con selector si el usuario tiene varias) */}
        <div style={{ position: "relative", flex: "none" }}>
          <button
            onClick={() => puedeCambiar && setMenuInst((v) => !v)}
            style={{ display: "flex", alignItems: "center", gap: 11, width: "100%", padding: "16px 16px 12px", background: "none", border: "none", textAlign: "left", cursor: puedeCambiar ? "pointer" : "default" }}
          >
            <Logo size={34} />
            <div style={{ lineHeight: 1.15, minWidth: 0, flex: 1 }}>
              <div style={{ fontSize: 14, fontWeight: 700, letterSpacing: "-.2px", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                {institucion?.nombre || "Cauce"}
              </div>
              <div style={{ fontSize: 11, color: color.slate400, fontWeight: 500 }}>{institucion?.tipo || "Institución"}</div>
            </div>
            {puedeCambiar && <Icon name="back" size={13} style={{ transform: menuInst ? "rotate(90deg)" : "rotate(-90deg)", color: color.slate400 }} />}
          </button>

          {/* Menú desplegable de instituciones */}
          {menuInst && (
            <>
              <div onClick={() => setMenuInst(false)} style={{ position: "fixed", inset: 0, zIndex: 20 }} />
              <div style={{ position: "absolute", top: 60, left: 14, right: 14, background: "#fff", border: `1px solid ${color.border}`, borderRadius: 10, boxShadow: "0 8px 24px rgba(16,24,40,.16)", zIndex: 21, padding: 6, maxHeight: 280, overflowY: "auto" }}>
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

        {/* Volver al directorio (super admin) / rol del usuario (no-super) */}
        <div style={{ flex: "none", padding: "0 14px 10px", borderBottom: `1px solid ${color.divider}` }}>
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

        {/* Navegación */}
        <nav style={{ flex: 1, overflowY: "auto", padding: "12px 12px", display: "flex", flexDirection: "column", gap: 3 }}>
          <NavLink to={ITEM_INICIO.to} style={itemStyle}>
            {({ isActive }) => (
              <>
                <Icon name={ITEM_INICIO.icon} size={17} />
                {operativo ? "Mi trabajo" : ITEM_INICIO.label}
                {operativo && pendientes > 0 && (
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
                <div style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: ".7px", color: color.slate400, padding: "12px 12px 6px" }}>{g.label}</div>
                <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                  {items.map((n) => (
                    <NavLink key={n.to} to={n.to} style={itemStyle} end={n.to === "/flujos"}>
                      <Icon name={n.icon} size={17} />
                      {n.label}
                    </NavLink>
                  ))}
                </div>
              </div>
            );
          })}
        </nav>

        {/* Usuario */}
        <div style={{ flex: "none", borderTop: `1px solid ${color.divider}`, padding: 14, display: "flex", alignItems: "center", gap: 11 }}>
          <Avatar nombre={user?.nombre_completo || user?.email} size={34} />
          <div style={{ minWidth: 0, flex: 1, lineHeight: 1.25 }}>
            <div style={{ fontSize: 13, fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{user?.nombre_completo || user?.email}</div>
            <div style={{ fontSize: 11, color: color.slate400 }}>{rolLabel}</div>
          </div>
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
