import { createContext, useContext, useEffect, useState } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { Logo } from "./Logo";
import { Avatar, IconButton, Popover } from "./ui";
import { Icon } from "./icons";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useInstitucion } from "../auth/InstitutionContext";
import { antiguedad } from "../lib/format";
import { cn } from "../lib/cn";
import { useEsEscritorio } from "../lib/media";
import { useTema } from "../lib/tema";

// Estado de "última actualización" que una pantalla publica para mostrarlo en la
// barra superior (al lado de la campana). Null cuando no aplica.
const RefreshCtx = createContext({ refresco: null, setRefresco: () => {} });
export function useRefresh() { return useContext(RefreshCtx); }

function textoRefresco(r) {
  if (!r) return null;
  if (r.refrescando) return "Actualizando⬦";
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
  "/internacion": "Internación",
  "/agenda": "Turnos programados",
  "/farmacia": "Farmacia e insumos",
  "/red": "Red de establecimientos",
  "/casos": "Casos",
  "/historia": "Historia clínica",
  "/legajo": "Legajo profesional",
  "/flujos": "Flujos",
  "/mapa": "Mapa de flujos",
  "/formularios": "Formularios",
  "/estructura": "Estructura organizativa",
  "/administracion": "Administración",
};
// Rutas con parámetro: llevan prefijo, así que no entran por el mapa de arriba.
// Faltando una, la barra dice «Cauce» y la persona pierde la referencia de dónde
// está — que es justamente para lo que sirve el título.
const TITULOS_DETALLE = [
  ["/casos/", "Detalle del caso"],
  ["/flujos/", "Diseñador de flujos"],
  ["/puesto/", "Detalle del paso"],
  ["/formularios/", "Constructor de formulario"],
  ["/historia/", "Historia clínica"],
  ["/estructura/", "Estructura organizativa"],
];

function tituloDeRuta(pathname) {
  const detalle = TITULOS_DETALLE.find(([prefijo]) => pathname.startsWith(prefijo));
  if (detalle) return detalle[1];
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
    <div className="relative flex-none">
      <IconButton
        icon="bell"
        label="Notificaciones"
        badge={data.no_leidas}
        onClick={() => setAbierto((v) => !v)}
      />
      {abierto && (
        <Popover className="w-[324px]" onClose={() => setAbierto(false)}>
          <div className="flex items-center justify-between border-b border-division px-3.5 py-3">
            <span className="text-md font-bold">Notificaciones</span>
            {data.no_leidas > 0 && (
              <button onClick={marcarTodas} className="text-base font-semibold text-accent hover:underline">
                Marcar todas
              </button>
            )}
          </div>
          <div className="max-h-[360px] overflow-y-auto">
            {data.items.length === 0 ? (
              <div className="px-3.5 py-6 text-center text-base text-texto-tenue">Sin notificaciones</div>
            ) : data.items.map((n) => (
              <button
                key={n.id}
                onClick={() => abrir(n)}
                className={cn(
                  "flex w-full gap-2.5 border-t border-division px-3.5 py-2.5 text-left hover:bg-superficie-2",
                  !n.leida && "bg-accent-50",
                )}
              >
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-md font-semibold">{n.titulo}</span>
                  {n.detalle && <span className="block truncate text-base text-texto-debil">{n.detalle}</span>}
                  <span className="mt-0.5 block text-xs text-texto-tenue">hace {antiguedad(n.creada)}</span>
                </span>
                {!n.leida && <span className="mt-1.5 size-2 shrink-0 rounded-pill bg-accent" />}
              </button>
            ))}
          </div>
          <button
            onClick={() => { setAbierto(false); navigate("/notificaciones"); }}
            className="w-full border-t border-division px-3.5 py-2.5 text-base font-semibold text-accent hover:bg-superficie-2"
          >
            Ver todas
          </button>
        </Popover>
      )}
    </div>
  );
}

// Buscador de pacientes (barra superior): nombre o documento �  su historia clínica.
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
    <div className="relative w-full max-w-[420px]">
      <span className="absolute left-3 top-1/2 flex -translate-y-1/2 text-texto-tenue">
        <Icon name="search" size={16} />
      </span>
      <input
        placeholder="Buscar paciente por nombre o documento⬦"
        value={q}
        onChange={(e) => { setQ(e.target.value); setAbierto(true); }}
        onFocus={() => setAbierto(true)}
        onKeyDown={(e) => { if (e.key === "Enter" && res[0]) ir(res[0]); if (e.key === "Escape") setAbierto(false); }}
        role="combobox"
        aria-expanded={abierto && !!q.trim()}
        aria-controls="buscador-pacientes-resultados"
        className="h-[38px] w-full rounded-md border border-campo-borde bg-superficie-2 px-3 pl-8.5 text-md outline-none placeholder:text-texto-tenue focus:border-accent"
      />
      {abierto && q.trim() && (
        <Popover align="left" className="right-0 max-h-[360px] overflow-y-auto" onClose={() => setAbierto(false)}>
          <div id="buscador-pacientes-resultados" role="listbox">
            {buscando ? (
              <div style={{ padding: "14px 16px", fontSize: 13, color: "var(--color-texto-tenue)" }}>Buscando⬦</div>
            ) : res.length === 0 ? (
              <div style={{ padding: "14px 16px", fontSize: 13, color: "var(--color-texto-tenue)" }}>Sin pacientes para «{q.trim()}».</div>
            ) : res.map((c, i) => (
              <div key={c.id} onClick={() => ir(c)}
                style={{ display: "flex", alignItems: "center", gap: 11, padding: "10px 14px", cursor: "pointer", borderTop: i ? `1px solid var(--color-division)` : "none" }}
                onMouseEnter={(e) => (e.currentTarget.style.background = "var(--color-superficie-2)")}
                onMouseLeave={(e) => (e.currentTarget.style.background = "var(--color-superficie)")}>
                <Avatar nombre={`${c.nombre} ${c.apellido}`} i={c.id} size={30} />
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 13.5, fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{c.nombre} {c.apellido}</div>
                  <div style={{ fontSize: 11.5, color: "var(--color-texto-tenue)" }}>{c.documento ? `DNI ${c.documento}` : c.codigo || "Sin documento"}{c.obra_social ? ` · ${c.obra_social}` : ""}</div>
                </div>
              </div>
            ))}
          </div>
        </Popover>
      )}
    </div>
  );
}

const BOTON_BARRA =
  "flex size-[34px] shrink-0 items-center justify-center rounded-md border " +
  "border-accent-100 bg-accent-50 text-accent hover:bg-accent-100";

function BotonTema() {
  const { oscuro, alternar } = useTema();
  return (
    <IconButton
      icon={oscuro ? "sol" : "luna"}
      onClick={alternar}
      label={oscuro ? "Cambiar a tema claro" : "Cambiar a tema oscuro"}
    />
  );
}

function TopBar({ onAbrirMenu }) {
  const { logout } = useAuth();
  const { refresco } = useRefresh();
  const location = useLocation();
  const navigate = useNavigate();
  const txtRefresco = textoRefresco(refresco);
  // Volver: en toda página salvo el inicio (que es la base del recorrido).
  const puedeVolver = !["/inicio", "/"].includes(location.pathname);
  return (
    <header className="flex h-16 shrink-0 items-center gap-2.5 border-b border-borde bg-superficie px-lg sm:gap-3.5 sm:px-[26px]">
      {/* Hamburguesa: solo en angosto, donde el menú es un cajón. */}
      <button onClick={onAbrirMenu} aria-label="Abrir menú" className={cn(BOTON_BARRA, "md:hidden")}>
        <Icon name="rows" size={17} />
      </button>
      {puedeVolver && (
        <button onClick={() => navigate(-1)} aria-label="Volver" title="Volver" className={BOTON_BARRA}>
          <Icon name="back" size={17} />
        </button>
      )}
      {/* `truncate` y no `nowrap`: un título largo en pantalla angosta debe
          recortarse, no empujar la barra y desbordar la página. */}
      <h1 className="truncate text-xl font-bold tracking-tight">{tituloDeRuta(location.pathname)}</h1>
      {/* El buscador se esconde en angosto: compite con el título y la campana.
          Queda accesible desde «Historia clínica». */}
      <div className="hidden flex-1 justify-center md:flex">
        <BuscadorPacientes />
      </div>
      <div className="flex flex-1 items-center justify-end gap-2.5 md:flex-none">
        {txtRefresco && <span className="hidden whitespace-nowrap text-sm text-texto-tenue lg:inline">{txtRefresco}</span>}
        <BotonTema />
        <Campana />
        <button
          onClick={() => { logout(); navigate("/login"); }}
          title="Cerrar sesión"
          className="flex h-9 shrink-0 items-center gap-1.5 rounded-md border border-accent-100 bg-accent-50 px-2 text-md font-semibold text-accent hover:bg-accent-100 sm:px-3"
        >
          <Icon name="power" size={15} /> <span className="hidden sm:inline">Salir</span>
        </button>
      </div>
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
      // Bandeja / Filas / Casos se operan desde «Mi trabajo» (Inicio); quedan las
      // rutas vivas pero fuera del menú. Acá solo la vista de supervisión (jefe).
      // Internación sí va en el menú: el tablero de camas se consulta todo el
      // día por sí mismo, no como paso de un caso.
      // El Tablero se gatea por `supervision` y no por `config`: la solapa por
      // área —mapa del flujo, casos por paso, top de demoras— existe para el jefe
      // de área, que es el único rol sin `config` y por lo tanto el único que no
      // tenía por dónde entrar. Dárselo con `config` le abriría también
      // Estructura y Administración: el jefe de Guardia dando de alta usuarios
      // del hospital para poder mirar su propia espera promedio.
      { to: "/dashboard", label: "Tablero", icon: "activity", cap: "supervision" },
      { to: "/agenda", label: "Turnos programados", icon: "calendar", cap: "trabajo" },
      { to: "/internacion", label: "Internación", icon: "bed", cap: "trabajo" },
      { to: "/farmacia", label: "Farmacia e insumos", icon: "cube", cap: "trabajo" },
      { to: "/red", label: "Red y traslados", icon: "map", cap: "trabajo" },
      { to: "/supervision", label: "Supervisión", icon: "users", cap: "supervision" },
    ],
  },
  {
    label: "REGISTROS",
    items: [
      { to: "/historia", label: "Historia clínica", icon: "clipboard", cap: "registros" },
      { to: "/legajo", label: "Legajo profesional", icon: "idCard", cap: "registros" },
      // Quién consultó datos clínicos. Va en REGISTROS y no en SISTEMA: es la
      // contracara de la historia clínica, no una opción de configuración.
      { to: "/accesos", label: "Registro de accesos", icon: "search", cap: "auditoria" },
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

// Clases del ítem de menú. Migrado de estilos inline a tokens semánticos porque
// con el literal `slate600` sobre la superficie oscura el menú quedaba en 2,22:1
// �ilegible� y es el marco que se ve en todas las pantallas.
const itemClase = (col) => ({ isActive }) =>
  cn(
    "flex items-center gap-2.5 rounded-md text-md font-semibold",
    col ? "justify-center py-2.5" : "px-3 py-2.5",
    isActive
      ? "bg-accent-fuerte text-sobre-accent"
      : "text-texto-suave hover:bg-superficie-2 hover:text-texto",
  );

export function Shell({ children }) {
  const { user, logout } = useAuth();
  const { institucion, setInstitucion, roles, puedeVer } = useInstitucion();
  const navigate = useNavigate();

  // "�altima actualización" que publica la pantalla activa (lo muestra la TopBar).
  const [refresco, setRefresco] = useState(null);

  // Menú lateral colapsable (recordado entre sesiones).
  const [colapsadoPref, setColapsado] = useState(() => localStorage.getItem("cauce.menu") === "col");
  const toggleMenu = () => setColapsado((v) => { localStorage.setItem("cauce.menu", v ? "exp" : "col"); return !v; });
  // El colapso solo vale en escritorio: en el cajón móvil el menú se muestra
  // siempre completo (si no, alguien que colapsó en la compu abre el cajón en el
  // celular y ve una columna de iconos sin texto).
  const esEscritorio = useEsEscritorio();
  const colapsado = colapsadoPref && esEscritorio;

  // Cajón del menú en pantallas angostas.
  const [cajon, setCajon] = useState(false);
  const location = useLocation();
  // Al navegar se cierra solo: si no, queda tapando la pantalla a la que fuiste.
  useEffect(() => { setCajon(false); }, [location.pathname]);
  useEffect(() => {
    if (!cajon) return;
    const onKey = (e) => { if (e.key === "Escape") setCajon(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [cajon]);

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
    <div className="flex min-h-screen bg-fondo">
      {/* Fondo del cajón: solo existe en angosto y con el menú abierto. */}
      {cajon && (
        <div
          onClick={() => setCajon(false)}
          className="fixed inset-0 z-30 bg-texto/40 md:hidden"
          aria-hidden="true"
        />
      )}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex h-screen w-[264px] flex-col border-r border-borde bg-superficie",
          "transition-transform duration-150",
          // De `md` para arriba deja de ser cajón: vuelve al flujo y lo que
          // cambia es el ancho (colapsado o no).
          "md:sticky md:top-0 md:shrink-0 md:translate-x-0 md:transition-[width]",
          colapsadoPref ? "md:w-[68px]" : "md:w-[244px]",
          cajon ? "translate-x-0 shadow-modal" : "-translate-x-full",
        )}
      >
        {/* Cabecera: institución + colapsar (en una sola fila) */}
        <div style={{ position: "relative", flex: "none", display: "flex", alignItems: "center", gap: 8, flexDirection: colapsado ? "column" : "row", padding: colapsado ? "14px 0 12px" : "14px 12px", borderBottom: colapsado ? `1px solid var(--color-division)` : "none" }}>
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
                <div style={{ fontSize: 11, color: "var(--color-texto-tenue)", fontWeight: 500 }}>{institucion?.tipo || "Institución"}</div>
              </div>
            )}
          </button>
          {/* En angosto este botón cierra el cajón; de `md` para arriba colapsa
              el menú. Son dos botones distintos porque también cambia el icono. */}
          <button
            onClick={() => setCajon(false)}
            aria-label="Cerrar menú"
            className="flex size-7 shrink-0 items-center justify-center rounded-md border border-accent-100 bg-accent-50 text-accent md:hidden"
          >
            <Icon name="x" size={14} />
          </button>
          <button
            onClick={toggleMenu}
            title={colapsado ? "Expandir menú" : "Colapsar menú"}
            aria-label={colapsado ? "Expandir menú" : "Colapsar menú"}
            className="hidden size-7 shrink-0 items-center justify-center rounded-md border border-accent-100 bg-accent-50 text-accent md:flex"
          >
            <Icon name="back" size={14} className={colapsado ? "rotate-180" : undefined} />
          </button>

          {/* Menú desplegable de instituciones */}
          {menuInst && !colapsado && (
            <>
              <div onClick={() => setMenuInst(false)} style={{ position: "fixed", inset: 0, zIndex: 20 }} />
              <div style={{ position: "absolute", top: 62, left: 12, right: 12, background: "var(--color-superficie)", border: `1px solid var(--color-borde)`, borderRadius: 10, boxShadow: "0 8px 24px rgba(16,24,40,.16)", zIndex: 21, padding: 6, maxHeight: 280, overflowY: "auto" }}>
                <div style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: ".6px", color: "var(--color-texto-tenue)", padding: "6px 8px 4px" }}>CAMBIAR DE INSTITUCI�N</div>
                {misInst.map((inst) => {
                  const activa = inst.id === institucion?.id;
                  return (
                    <button
                      key={inst.id}
                      onClick={() => cambiarInstitucion(inst)}
                      style={{ display: "flex", alignItems: "center", gap: 9, width: "100%", padding: "9px 8px", borderRadius: 7, border: "none", background: activa ? "var(--color-accent-50)" : "transparent", cursor: "pointer", textAlign: "left" }}
                    >
                      <div style={{ width: 26, height: 26, borderRadius: 7, background: "var(--color-superficie-2)", color: "var(--color-texto-debil)", display: "flex", alignItems: "center", justifyContent: "center", flex: "none" }}><Icon name="building" size={14} /></div>
                      <div style={{ minWidth: 0, flex: 1 }}>
                        <div style={{ fontSize: 13, fontWeight: 600, color: activa ? "var(--color-accent)" : "var(--color-texto-medio)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{inst.nombre}</div>
                        <div style={{ fontSize: 11, color: "var(--color-texto-tenue)" }}>{inst.tipo || "Institución"}</div>
                      </div>
                      {activa && <Icon name="enter" size={14} style={{ color: "var(--color-accent)" }} />}
                    </button>
                  );
                })}
              </div>
            </>
          )}
        </div>

        {/* Volver al directorio (super admin) / rol del usuario (no-super) � solo expandido */}
        {!colapsado && (
          <div style={{ flex: "none", padding: "10px 14px", borderBottom: `1px solid var(--color-division)` }}>
            {user?.is_superuser ? (
              <button
                onClick={() => { setInstitucion(null); navigate("/"); }}
                // El gris estaba hardcodeado (#F2F3F6) y en tema oscuro dejaba
                // texto claro sobre fondo claro: 1,7:1.
                style={{ display: "flex", alignItems: "center", gap: 7, width: "100%", padding: "8px 10px", borderRadius: 8, background: "var(--color-superficie-2)", color: "var(--color-texto-suave)", fontSize: 12, fontWeight: 600, border: "none", cursor: "pointer" }}
              >
                <Icon name="back" size={14} /> Volver al directorio
              </button>
            ) : (
              <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: "var(--color-texto-tenue)", padding: "4px 2px" }}>
                <Icon name="power" size={12} /> {rolLabel}{puedeCambiar ? "" : " · acceso fijo"}
              </div>
            )}
          </div>
        )}

        {/* Navegación */}
        <nav style={{ flex: 1, overflowY: "auto", padding: colapsado ? "12px 10px" : "12px 12px", display: "flex", flexDirection: "column", gap: 3 }}>
          <NavLink to={ITEM_INICIO.to} className={itemClase(colapsado)} title={operativo ? "Mi trabajo" : "Inicio"}>
            {({ isActive }) => (
              <>
                <span style={{ position: "relative", display: "flex" }}>
                  <Icon name={ITEM_INICIO.icon} size={17} />
                  {colapsado && operativo && pendientes > 0 && (
                    <span style={{ position: "absolute", top: -5, right: -7, minWidth: 15, height: 15, padding: "0 3px", borderRadius: 8, background: "var(--color-danger-fuerte)", color: "var(--color-sobre-danger)", fontSize: 9.5, fontWeight: 700, display: "flex", alignItems: "center", justifyContent: "center", boxSizing: "border-box" }}>
                      {pendientes > 9 ? "9+" : pendientes}
                    </span>
                  )}
                </span>
                {!colapsado && (operativo ? "Mi trabajo" : ITEM_INICIO.label)}
                {!colapsado && operativo && pendientes > 0 && (
                  <span style={{ marginLeft: "auto", minWidth: 20, height: 20, padding: "0 6px", borderRadius: 10, fontSize: 11.5, fontWeight: 700, display: "inline-flex", alignItems: "center", justifyContent: "center", background: isActive ? "rgba(255,255,255,.25)" : "var(--color-accent-50)", color: isActive ? "#fff" : "var(--color-accent)" }}>
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
                  ? <div style={{ height: 1, background: "var(--color-division)", margin: "8px 8px 6px" }} />
                  : <div style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: ".7px", color: "var(--color-texto-tenue)", padding: "12px 12px 6px" }}>{g.label}</div>}
                <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                  {items.map((n) => (
                    <NavLink
                      key={n.to}
                      to={n.to}
                      data-tour={`menu-${n.to.slice(1)}`}
                      className={itemClase(colapsado)}
                      end={n.to === "/flujos"}
                      title={n.label}
                    >
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
        <div
          data-demo-trigger={user?.is_superuser ? "super-admin" : undefined}
          title={user?.is_superuser ? "Tocar 3 veces para iniciar el modo demo" : undefined}
          style={{ flex: "none", borderTop: `1px solid var(--color-division)`, padding: colapsado ? "12px 0" : 14, display: "flex", flexDirection: colapsado ? "column" : "row", alignItems: "center", gap: colapsado ? 8 : 11, cursor: user?.is_superuser ? "pointer" : "default" }}
        >
          <Avatar nombre={user?.nombre_completo || user?.email} size={34} />
          {!colapsado && (
            <div style={{ minWidth: 0, flex: 1, lineHeight: 1.25 }}>
              <div style={{ fontSize: 13, fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{user?.nombre_completo || user?.email}</div>
              {user?.is_superuser ? (
                <button
                  type="button"
                  data-tour="shell-super-admin"
                  title="Super admin"
                  style={{
                    display: "block",
                    padding: 0,
                    border: "none",
                    background: "none",
                    color: "var(--color-texto-tenue)",
                    fontSize: 11,
                    cursor: "pointer",
                    textAlign: "left",
                  }}
                >
                  {rolLabel}
                </button>
              ) : (
                <div style={{ fontSize: 11, color: "var(--color-texto-tenue)" }}>{rolLabel}</div>
              )}
            </div>
          )}
          <button onClick={() => { logout(); navigate("/login"); }} title="Cerrar sesión" style={{ border: "none", background: "none", cursor: "pointer", color: "var(--color-texto-tenue)", display: "flex" }}>
            <Icon name="power" size={17} />
          </button>
        </div>
      </aside>

      <main className="flex h-screen min-w-0 flex-1 flex-col">
        <TopBar onAbrirMenu={() => setCajon(true)} />
        <div className="min-h-0 flex-1 overflow-auto">{children}</div>
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
      <div style={{ fontSize: 13.5, color: "var(--color-texto-debil)" }}>{subtitle}</div>
      {right}
    </div>
  );
}
