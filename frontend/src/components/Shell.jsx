import { createContext, useContext, useEffect, useState } from "react";
import { Link, NavLink, useLocation, useNavigate } from "react-router-dom";
import { Logo } from "./Logo";
import { Avatar, IconButton, Popover } from "./ui";
import { Icon } from "./icons";
import { api } from "../api/client";
import { useLista } from "../api/queries";
import { useAuth } from "../auth/AuthContext";
import { useInstitucion } from "../auth/InstitutionContext";
import { antiguedad } from "../lib/format";
import { cn } from "../lib/cn";
import { useEsEscritorio } from "../lib/media";
import { useTema } from "../lib/tema";
import { usePermisosFinanzas } from "../api/finanzas";
import { resumenCobertura } from "./financiadores/CoberturaAdministrativa";
import { BannerSimulacion, SelectorSimulacion, ambitoSimulable } from "./SimulacionPerfil";

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
  "/bandeja": "Bandeja",
  "/filas": "Filas de espera",
  "/internacion": "Internación",
  "/agenda": "Turnos",
  "/farmacia": "Farmacia e insumos",
  "/red": "Red de establecimientos",
  "/casos": "Casos",
  "/pacientes": "Pacientes",
  "/legajo": "Legajo profesional",
  "/accesos": "Registro de accesos",
  "/flujos": "Flujos",
  "/mapa": "Mapa de flujos",
  "/formularios": "Formularios",
  "/estructura": "Estructura organizativa",
  "/administracion": "Usuarios y permisos",
  "/finanzas": "Finanzas y cobros",
  "/finanzas/coberturas": "Coberturas y copagos",
};
// Rutas con parámetro: llevan prefijo, así que no entran por el mapa de arriba.
// Faltando una, la barra dice «HEN» y la persona pierde la referencia de dónde
// está — que es justamente para lo que sirve el título.
const TITULOS_DETALLE = [
  ["/casos/", "Detalle del caso"],
  ["/pacientes/", "Paciente"],
  ["/flujos/", "Diseñador de flujos"],
  ["/puesto/", "Detalle del paso"],
  ["/formularios/", "Constructor de formulario"],
  ["/estructura/", "Estructura organizativa"],
];

function tituloDeRuta(pathname) {
  const detalle = TITULOS_DETALLE.find(([prefijo]) => pathname.startsWith(prefijo));
  if (detalle) return detalle[1];
  return TITULOS[pathname] || "HEN";
}

// Campana de notificaciones: contador de no leídas + dropdown (poll a /resumen/).
function Campana() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [data, setData] = useState({ no_leidas: 0, items: [] });
  const [abierto, setAbierto] = useState(false);

  async function recargar() {
    try { setData(await api.get("/notificaciones/resumen/")); } catch { /* silencioso */ }
  }
  // Se recarga al cambiar de identidad (simular un perfil o volver a Sistema):
  // los avisos son de quien consulta y no pueden quedar los de la otra cuenta.
  useEffect(() => {
    setData({ no_leidas: 0, items: [] });
    recargar();
    const tick = () => { if (!document.hidden) recargar(); };
    const id = setInterval(tick, 30000);
    window.addEventListener("focus", tick);
    return () => { clearInterval(id); window.removeEventListener("focus", tick); };
  }, [user?.id]);

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

// Buscador de pacientes (barra superior): nombre o documento y ficha del paciente.
function BuscadorPacientes() {
  const { institucion, puedeVer } = useInstitucion();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [resultado, setResultado] = useState({});
  const [intento, setIntento] = useState(0);
  const [abierto, setAbierto] = useState(false);
  const puedeBuscarPacientes = puedeVer("padron_admision");
  const contexto = JSON.stringify([user?.id, institucion?.id, q.trim()]);
  const actual = resultado.contexto === contexto;
  const res = actual ? resultado.filas || [] : [];
  const error = actual ? resultado.error : null;
  const buscando = !!q.trim() && (!actual || resultado.cargando);

  useEffect(() => {
    const term = q.trim();
    if (!term || !institucion || !puedeBuscarPacientes) { setResultado({}); return; }
    let vigente = true;
    setResultado({ contexto, cargando: true });
    const t = setTimeout(async () => {
      try {
        const d = await api.get(`/ciudadanos/?institucion=${institucion.id}&search=${encodeURIComponent(term)}`);
        if (vigente) setResultado({ contexto, filas: (d.results || d).slice(0, 8) });
      } catch (errorConsulta) {
        if (vigente) setResultado({ contexto, error: errorConsulta });
      }
    }, 250);
    return () => { vigente = false; clearTimeout(t); };
  }, [contexto, puedeBuscarPacientes, intento]);

  function ir(c) {
    setQ(""); setResultado({}); setAbierto(false);
    navigate(`/pacientes/${c.id}`);
  }

  if (!puedeBuscarPacientes) return null;

  return (
    <div className="relative w-full max-w-[420px]">
      <span className="absolute left-3 top-1/2 flex -translate-y-1/2 text-texto-tenue">
        <Icon name="search" size={16} />
      </span>
      <input
        placeholder="Buscar paciente por nombre o documento…"
        value={q}
        onChange={(e) => { setQ(e.target.value); setAbierto(true); }}
        onFocus={() => setAbierto(true)}
        onKeyDown={(e) => { if (e.key === "Enter" && res[0]) ir(res[0]); if (e.key === "Escape") setAbierto(false); }}
        role="combobox"
        aria-label="Buscar paciente por nombre o documento"
        aria-expanded={abierto && !!q.trim()}
        aria-controls="buscador-pacientes-resultados"
        className="h-[38px] w-full rounded-md border border-campo-borde bg-superficie-2 px-3 pl-8.5 text-md outline-none placeholder:text-texto-tenue focus:border-accent"
      />
      {abierto && q.trim() && (
        <Popover align="left" className="right-0 max-h-[360px] overflow-y-auto" onClose={() => setAbierto(false)}>
          <div id="buscador-pacientes-resultados" role="listbox">
            {buscando ? (
              <div style={{ padding: "14px 16px", fontSize: 13, color: "var(--color-texto-tenue)" }}>Buscando…</div>
            ) : error ? (
              <div className="p-3.5 text-sm text-texto-debil" role="alert">
                No se pudo buscar al paciente.
                <button className="ml-2 font-semibold text-accent hover:underline" onClick={() => setIntento((v) => v + 1)}>Reintentar</button>
              </div>
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
                  <div style={{ fontSize: 11.5, color: "var(--color-texto-tenue)" }}>{c.documento ? `DNI ${c.documento}` : c.codigo || "Sin documento"}{resumenCobertura(c) ? ` · ${resumenCobertura(c)}` : ""}</div>
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

function TopBar({ onAbrirMenu, titulo, contexto, hospital = true, plataforma = false, volverA = "/inicio" }) {
  const { logout } = useAuth();
  const { refresco } = useRefresh();
  const location = useLocation();
  const navigate = useNavigate();
  const txtRefresco = textoRefresco(refresco);
  // Volver: en toda página salvo el inicio (que es la base del recorrido).
  const puedeVolver = !["/inicio", "/directorio", "/financiadores"].includes(location.pathname);
  return (
    <header className="flex h-[64px] shrink-0 items-center gap-2.5 border-b border-borde bg-superficie px-lg sm:gap-3.5 sm:px-[24px]">
      {/* Hamburguesa: solo en angosto, donde el menú es un cajón. */}
      <button onClick={onAbrirMenu} aria-label="Abrir menú" className={cn(BOTON_BARRA, "md:hidden")}>
        <Icon name="rows" size={17} />
      </button>
      {puedeVolver && !plataforma && location.pathname.split("/").filter(Boolean).length > 1 && (
        <button onClick={() => window.history.state?.idx > 0 ? navigate(-1) : navigate(volverA)} aria-label="Volver" title="Volver" className={BOTON_BARRA}>
          <Icon name="back" size={17} />
        </button>
      )}
      {/* `truncate` y no `nowrap`: un título largo en pantalla angosta debe
          recortarse, no empujar la barra y desbordar la página. */}
      <h1 className="truncate text-xs font-medium text-texto-suave">
        <span>{contexto}</span><span className="mx-2">/</span><span className="text-texto">{titulo || tituloDeRuta(location.pathname)}</span>
      </h1>
      {/* El buscador se esconde en angosto: compite con el título y la campana.
          Queda accesible desde «Pacientes». */}
      <div className="hidden flex-1 justify-center md:flex">
        {hospital && <BuscadorPacientes />}
      </div>
      <div className="flex flex-1 items-center justify-end gap-2.5 md:flex-none">
        {txtRefresco && <span className="hidden whitespace-nowrap text-sm text-texto-tenue lg:inline">{txtRefresco}</span>}
        <BotonTema />
        {hospital && <Campana />}
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

// Los grupos corresponden al recorrido de Figma y se abren según la sección activa.
const GRUPOS = [
  {
    label: "DIRECCIÓN",
    items: [
      { to: "/dashboard", label: "Tablero", icon: "activity", cap: "supervision" },
      { to: "/finanzas", label: "Finanzas y cobros", icon: "wallet", especial: "finanzas" },
      { to: "/finanzas/coberturas", label: "Coberturas y copagos", icon: "shieldCheck", especial: "coberturas" },
      { to: "/red", label: "Red de establecimientos", icon: "mapPin", cap: "traslados_red" },
    ],
  },
  {
    label: "OPERACIÓN",
    items: [
      { to: "/inicio", label: "Inicio", icon: "home" },
      { to: "/bandeja", label: "Bandeja", icon: "inbox", cap: "casos_operar" },
      { to: "/agenda", label: "Turnos", icon: "calendar", cap: "turnos" },
      { to: "/pacientes", label: "Pacientes", icon: "idCard", cap: "padron_admision" },
      { to: "/internacion", label: "Internación", icon: "bed", cap: "internacion" },
      { to: "/farmacia", label: "Farmacia e insumos", icon: "pill", cap: "farmacia_stock" },
    ],
  },
  {
    label: "SEGUIMIENTO",
    items: [
      { to: "/casos", label: "Casos", icon: "fileText", cap: "casos_operar" },
      { to: "/supervision", label: "Supervisión", icon: "eye", cap: "supervision" },
    ],
  },
  {
    label: "CONFIGURACIÓN",
    items: [
      { to: "/estructura", label: "Estructura organizativa", icon: "network", cap: "config_institucional" },
      { to: "/administracion", label: "Usuarios y permisos", icon: "users", cap: "config_institucional" },
      { to: "/flujos", label: "Flujos", icon: "workflow", cap: "diseno_flujos" },
      { to: "/mapa", label: "Mapa de flujos", icon: "map", cap: "diseno_flujos" },
      { to: "/formularios", label: "Formularios", icon: "form", cap: "diseno_flujos" },
      { to: "/legajo", label: "Legajo profesional", icon: "stethoscope", cap: "config_institucional" },
      { to: "/accesos", label: "Registro de accesos", icon: "enter", cap: "auditoria" },
    ],
  },
];

const ROL_LABEL = {
  plataforma: "Autoridad estatal / plataforma",
  auditor: "Auditor estatal",
  reportes: "Reportes / solo lectura",
  admin: "Admin de institución",
  configurador: "Configurador",
  jefe_area: "Jefe / Supervisor de área",
  administrativo: "Administrativo",
  enfermeria: "Enfermería",
  medico: "Médico / profesional",
};

// Clases del ítem de menú. Migrado de estilos inline a tokens semánticos porque
// con el literal `slate600` sobre la superficie oscura el menú quedaba en 2,22:1
// «ilegible» y es el marco que se ve en todas las pantallas.
// El anillo de foco va hacia ADENTRO del ítem: los grupos del menú recortan con
// `overflow-hidden` (lo necesita la animación de plegado) y un anillo exterior
// quedaba cortado justo en el menú, que es por donde más se navega con teclado.
const itemClase = (col) => ({ isActive }) =>
  cn(
    "relative flex items-center gap-2 rounded-md text-xs font-medium focus-visible:-outline-offset-2",
    col ? "justify-center py-2" : "px-2 py-2",
    isActive
      ? "bg-accent-50 text-accent"
      : "text-texto-suave hover:bg-superficie-2 hover:text-texto",
  );

// Contador de un ítem. Plegado no hay lugar al lado del ícono —lo corría del
// centro y lo pegaba al número—, así que pasa a la esquina, como en la campana.
const contadorClase = (col) =>
  cn(
    "rounded-pill bg-accent-50 px-1.5 text-xs font-bold text-accent",
    col ? "absolute right-0.5 top-0.5 border border-accent-100 px-1 text-micro leading-4" : "ml-auto",
  );

export function Shell({ children, financiador = null, plataforma = false }) {
  const esFinanciador = Boolean(financiador);
  const esPlataforma = plataforma && !esFinanciador;
  const permisosFinanzas = usePermisosFinanzas({ enabled: !esFinanciador && !esPlataforma });
  const { user, logout, simulacion } = useAuth();
  const { institucion, setInstitucion, roles, puedeVer } = useInstitucion();
  const navigate = useNavigate();

  // "Última actualización" que publica la pantalla activa (lo muestra la TopBar).
  const [refresco, setRefresco] = useState(null);

  // Menú lateral colapsable (recordado entre sesiones).
  const [colapsadoPref, setColapsado] = useState(() => localStorage.getItem("salud.menu") === "col");
  const [gruposCerrados, setGruposCerrados] = useState(() => {
    const ruta = window.location.pathname;
    const activo = GRUPOS.find((grupo) => grupo.items.some((item) => ruta === item.to || ruta.startsWith(`${item.to}/`)));
    return new Set(GRUPOS.map((grupo) => grupo.label).filter((label) => label !== activo?.label));
  });
  const toggleMenu = () => setColapsado((v) => { localStorage.setItem("salud.menu", v ? "exp" : "col"); return !v; });
  // El colapso solo vale en escritorio: en el cajón móvil el menú se muestra
  // siempre completo (si no, alguien que colapsó en la compu abre el cajón en el
  // celular y ve una columna de iconos sin texto).
  const esEscritorio = useEsEscritorio();
  const colapsado = colapsadoPref && esEscritorio;

  // Cajón del menú en pantallas angostas.
  const [cajon, setCajon] = useState(false);
  const location = useLocation();
  // Al navegar se cierra solo: si no, queda tapando la pantalla a la que fuiste.
  useEffect(() => { setCajon(false); setMenuInst(false); }, [location.pathname, location.search]);
  useEffect(() => {
    const activo = GRUPOS.find((grupo) => grupo.items.some((item) => location.pathname === item.to || location.pathname.startsWith(`${item.to}/`)));
    if (!activo) return;
    setGruposCerrados((anteriores) => {
      if (!anteriores.has(activo.label)) return anteriores;
      const siguientes = new Set(anteriores);
      siguientes.delete(activo.label);
      return siguientes;
    });
  }, [location.pathname]);
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
    if (!user || user.is_superuser || esFinanciador || esPlataforma) return;
    api.get("/instituciones/").then((d) => setMisInst(d.results || d)).catch(() => {});
  }, [user, esFinanciador, esPlataforma]);
  const puedeCambiar = !esFinanciador && !esPlataforma && !user?.is_superuser && misInst.length > 1;

  // Contador de tareas pendientes para roles operativos (el "Inicio" es su worklist).
  // Se refresca solo cada 30s y se pausa con la pestaña oculta.
  const operativo = !esFinanciador && !esPlataforma && puedeVer("casos_operar") && !puedeVer("config_institucional") && !puedeVer("diseno_flujos");
  const conteoBandeja = useLista("casos", { institucion: institucion?.id, tomables: true, pageSize: 1 }, {
    enabled: !esFinanciador && !esPlataforma && Boolean(institucion?.id) && puedeVer("casos_operar"),
    placeholderData: undefined,
    refetchInterval: () => document.hidden ? false : 30000,
  });
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

  const rolLabel = esFinanciador ? ({ admin: "Administrador", operador: "Operador", auditor: "Auditor" }[financiador.rol] || financiador.rol) : user?.is_superuser
    ? "Super admin"
    : roles.map((r) => ROL_LABEL[r] || r).join(" · ") || "Usuario";
  const gruposInstitucion = GRUPOS;
  const ambitoActual = ambitoSimulable({ simulacion, esPlataforma, esFinanciador, institucion, location });
  const itemVisible = (item) => {
    if (item.especial === "finanzas") return permisosFinanzas.acceso && !permisosFinanzas.error;
    if (item.especial === "coberturas") return puedeVer("casos_operar") || (!permisosFinanzas.error && (permisosFinanzas.acceso || permisosFinanzas.tiene("resolver_cobertura")));
    return !item.cap || puedeVer(item.cap);
  };

  return (
    <RefreshCtx.Provider value={{ refresco, setRefresco }}>
    <div className="flex min-h-screen bg-fondo">
      <a href="#contenido-principal" className="sr-only fixed left-4 top-3 z-[100] rounded-md bg-superficie px-4 py-2 text-accent shadow-float focus:not-sr-only focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent">
        Ir al contenido principal
      </a>
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
          "transition-transform duration-150 motion-reduce:transition-none",
          // De `md` para arriba deja de ser cajón: vuelve al flujo y lo que
          // cambia es el ancho (colapsado o no).
          "md:sticky md:top-0 md:shrink-0 md:translate-x-0 md:transition-[width] md:duration-200 md:ease-out motion-reduce:md:transition-none",
          colapsadoPref ? "md:w-[68px]" : "md:w-[200px] xl:w-[264px]",
          cajon ? "translate-x-0 shadow-modal" : "-translate-x-full",
        )}
      >
        {/* Marca y control del menú: el contexto queda en el selector inferior. */}
        <div style={{ position: "relative", flex: "none", display: "flex", alignItems: "center", gap: 8, flexDirection: colapsado ? "column" : "row", padding: colapsado ? "14px 0 12px" : "14px 12px", borderBottom: colapsado ? `1px solid var(--color-division)` : "none" }}>
          <span className="flex min-w-0 flex-1 items-center gap-2 font-bold"><Logo size={24} />{!colapsado && "HEN"}</span>
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
            <Icon name="chevronRight" size={14} className={colapsado ? undefined : "rotate-180"} />
          </button>

          {/* Menú desplegable de instituciones */}
          {!esFinanciador && !esPlataforma && menuInst && !colapsado && (
            <>
              <div onClick={() => setMenuInst(false)} style={{ position: "fixed", inset: 0, zIndex: 20 }} />
              <div style={{ position: "absolute", top: 112, left: 12, right: 12, background: "var(--color-superficie)", border: `1px solid var(--color-borde)`, borderRadius: 10, boxShadow: "0 8px 24px rgba(16,24,40,.16)", zIndex: 21, padding: 6, maxHeight: 280, overflowY: "auto" }}>
                <div style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: ".6px", color: "var(--color-texto-tenue)", padding: "6px 8px 4px" }}>CAMBIAR DE INSTITUCIÓN</div>
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

        {esPlataforma && !colapsado && <div className="mx-3 rounded-md border border-borde bg-superficie-2 px-2 py-2 text-xs">
          <div className="flex items-center justify-between font-semibold"><span>Plataforma</span><Icon name="chevronRight" size={13} className="rotate-90" /></div>
          <div className="mt-0.5 text-texto-suave">Administración general</div>
        </div>}
        {!esPlataforma && !esFinanciador && !colapsado && <button type="button"
          onClick={() => puedeCambiar && setMenuInst((v) => !v)}
          aria-expanded={puedeCambiar ? menuInst : undefined}
          className="mx-3 flex items-center justify-between rounded-md border border-borde bg-superficie-2 px-2 py-2 text-left text-xs">
          <span className="min-w-0"><span className="block truncate font-semibold">{institucion?.nombre || "Institución"}</span><span className="block truncate text-texto-suave">{institucion?.tipo || "Institución"}</span></span>
          {puedeCambiar && <Icon name="chevronRight" size={13} className="rotate-90" />}
        </button>}
        {/* «Ver como»: solo el superusuario, simule o no, y con el menú expandido. */}
        {!colapsado && (user?.is_superuser || simulacion) && ambitoActual && <SelectorSimulacion ambito={ambitoActual} />}
        {/* Volver al directorio (super admin) / rol del usuario (no-super) — solo expandido */}
        {!colapsado && !esPlataforma && (
          <div style={{ flex: "none", padding: "10px 14px", borderBottom: `1px solid var(--color-division)` }}>
            {esFinanciador ? financiador.selector : (user?.is_superuser || puedeVer("gobierno_plataforma")) && !simulacion ? (
              <>
              <button
                onClick={() => { setInstitucion(null); navigate("/directorio"); }}
                // El gris estaba hardcodeado (#F2F3F6) y en tema oscuro dejaba
                // texto claro sobre fondo claro: 1,7:1.
                style={{ display: "flex", alignItems: "center", gap: 7, width: "100%", padding: "8px 10px", borderRadius: 8, background: "var(--color-superficie-2)", color: "var(--color-texto-suave)", fontSize: 12, fontWeight: 600, border: "none", cursor: "pointer" }}
              >
                <Icon name="back" size={14} /> Volver al directorio
              </button>
              </>
            ) : (
              <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: "var(--color-texto-tenue)", padding: "4px 2px" }}>
                {/* Credencial y no «power»: ese es el de «Salir» y se leía como cerrar sesión. */}
                <Icon name="idCard" size={12} /> {rolLabel}{puedeCambiar ? "" : " · acceso fijo"}
              </div>
            )}
          </div>
        )}

        {/* Navegación */}
        <nav aria-label={esFinanciador ? "Menú del financiador" : esPlataforma ? "Menú de plataforma" : "Menú principal"} style={{ flex: 1, overflowY: "auto", padding: colapsado ? "12px 10px" : "12px 12px", display: "flex", flexDirection: "column", gap: 3 }}>
          {esPlataforma ? <>
            {!colapsado && <div className="px-3 pb-1.5 pt-3 text-xs font-bold tracking-wide text-texto-tenue">PLATAFORMA</div>}
            {[
              ...(puedeVer("gobierno_plataforma") ? [
                { to: "/directorio?vista=instituciones", label: "Instituciones", icon: "building", key: "instituciones" },
                { to: "/directorio?vista=usuarios", label: "Usuarios", icon: "users", key: "usuarios" },
                { to: "/directorio?vista=financiadores", label: "Financiadores", icon: "handshake", key: "financiadores" },
              ] : []),
              ...(puedeVer("auditoria") ? [
                { to: "/directorio?vista=accesos", label: "Registro de accesos", icon: "enter", key: "accesos" },
              ] : []),
            ].map((item) => {
              const actual = location.pathname.startsWith("/financiadores") ? "financiadores" : new URLSearchParams(location.search).get("vista") || (puedeVer("gobierno_plataforma") ? "instituciones" : "accesos");
              return <Link key={item.key} to={item.to} aria-current={actual === item.key ? "page" : undefined}
                className={itemClase(colapsado)({ isActive: actual === item.key })} title={item.label}>
                <Icon name={item.icon} size={17} />{!colapsado && item.label}
              </Link>;
            })}
          </> : esFinanciador ? <>
            {!colapsado && <div className="px-3 pb-1.5 pt-3 text-xs font-bold tracking-wide text-texto-tenue">MI FINANCIADOR</div>}
            {financiador.items.map((item) => (
              <NavLink key={item.key} to={item.to} end className={itemClase(colapsado)} title={item.label} aria-label={item.label}>
                <Icon name={item.icon} size={17} />
                {!colapsado && item.label}
              </NavLink>
            ))}
            {financiador.volver && <NavLink to={financiador.volver.to} className={cn("mt-3 border-t border-division", itemClase(colapsado)({ isActive: false }))} title={financiador.volver.label} aria-label={financiador.volver.label}>
              <Icon name="back" size={17} />
              {!colapsado && financiador.volver.label}
            </NavLink>}
          </> : <>
          {gruposInstitucion.map((g) => {
            const items = g.items.filter(itemVisible);
            if (!items.length) return null;
            return (
              <div key={g.label}>
                {colapsado
                  ? <div style={{ height: 1, background: "var(--color-division)", margin: "8px 8px 6px" }} />
                  : <button type="button" aria-expanded={!gruposCerrados.has(g.label)}
                      onClick={() => setGruposCerrados((actual) => {
                        const nuevos = new Set(actual);
                        if (nuevos.has(g.label)) nuevos.delete(g.label); else nuevos.add(g.label);
                        return nuevos;
                      })}
                      className="flex w-full items-center justify-between rounded-md px-3 pb-1.5 pt-3 text-left text-xs font-bold tracking-wide text-texto-tenue hover:bg-superficie-2 focus-visible:outline-2 focus-visible:outline-accent">
                      {g.label}<Icon name="chevronRight" size={13} className={gruposCerrados.has(g.label) ? "" : "rotate-90"} />
                    </button>}
                <div className={cn("grid transition-[grid-template-rows] duration-200 ease-out motion-reduce:transition-none", colapsado || !gruposCerrados.has(g.label) ? "grid-rows-[1fr]" : "grid-rows-[0fr]")}>
                <div inert={!colapsado && gruposCerrados.has(g.label) ? "" : undefined} aria-hidden={!colapsado && gruposCerrados.has(g.label)} className="flex min-h-0 flex-col gap-0.5 overflow-hidden">
                  {items.map((n) => (
                    <NavLink
                      key={n.to}
                      to={n.to}
                      data-tour={`menu-${n.to.slice(1)}`}
                      className={itemClase(colapsado)}
                      end={n.to === "/flujos" || n.to === "/finanzas"}
                      title={n.label}
                    >
                      <Icon name={n.icon} size={16} />
                      {/* Plegado, el nombre sigue en el árbol de accesibilidad: si
                          no, un ítem con contador se anunciaba solo por el número
                          («7 casos para tomar») y no decía a dónde lleva. */}
                      <span className={colapsado ? "sr-only" : undefined}>{n.to === "/inicio" && operativo ? "Mi trabajo" : n.label}</span>
                      {n.to === "/inicio" && operativo && pendientes > 0 && (
                        <span className={contadorClase(colapsado)} aria-label={`${pendientes} tareas pendientes`}>{pendientes > 99 ? "99+" : pendientes}</span>
                      )}
                      {n.to === "/bandeja" && conteoBandeja.total > 0 && (
                        <span className={contadorClase(colapsado)} aria-label={`${conteoBandeja.total} casos para tomar`}>
                          {conteoBandeja.total > 99 ? "99+" : conteoBandeja.total}
                        </span>
                      )}
                    </NavLink>
                  ))}
                </div></div>
              </div>
            );
          })}
          {user?.financiadores?.length > 0 && !user?.is_superuser && !puedeVer("gobierno_plataforma") && (
            <NavLink to="/financiadores" className={itemClase(colapsado)} title="Portal de financiadores">
              <Icon name="handshake" size={17} />
              {!colapsado && "Financiadores"}
            </NavLink>
          )}
          </>}
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
        </div>
      </aside>

      <main className="flex h-screen min-w-0 flex-1 flex-col">
        <BannerSimulacion />
        <TopBar onAbrirMenu={() => setCajon(true)}
          titulo={esPlataforma ? (location.pathname.startsWith("/financiadores") ? "Financiadores" : ({ usuarios: "Usuarios", financiadores: "Financiadores", accesos: "Registro de accesos" })[new URLSearchParams(location.search).get("vista")] || (puedeVer("gobierno_plataforma") ? "Instituciones" : "Registro de accesos")) : financiador?.titulo}
          contexto={esPlataforma ? "Plataforma" : esFinanciador ? financiador.nombre : institucion?.nombre || "Institución"}
          hospital={!esFinanciador && !esPlataforma}
          plataforma={esPlataforma}
          volverA={esPlataforma ? "/directorio" : esFinanciador ? "/financiadores" : "/inicio"} />
        <div id="contenido-principal" tabIndex={-1} className="min-h-0 flex-1 overflow-auto">{children}</div>
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
