import { lazy, Suspense, useEffect, useState } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { api } from "./api/client";
import { useAuth } from "./auth/AuthContext";
import { useInstitucion } from "./auth/InstitutionContext";
import { Shell } from "./components/Shell";
import { Card, Spinner } from "./components/ui";
import { EstadoError } from "./components/ui/estados";

const Login = lazy(() => import("./pages/Login"));
const PantallaLlamados = lazy(() => import("./pages/PantallaLlamados"));
const Directorio = lazy(() => import("./pages/Directorio"));
const Inicio = lazy(() => import("./pages/Inicio"));
const Dashboard = lazy(() => import("./pages/Dashboard"));
const MiTrabajo = lazy(() => import("./pages/MiTrabajo"));
const PuestoDetalle = lazy(() => import("./pages/PuestoDetalle"));
const Supervision = lazy(() => import("./pages/Supervision"));
const Notificaciones = lazy(() => import("./pages/Notificaciones"));
const Bandejas = lazy(() => import("./pages/ejecucion/Bandejas"));
const Casos = lazy(() => import("./pages/ejecucion/Casos"));
const CasoDetalle = lazy(() => import("./pages/ejecucion/CasoDetalle"));
const Fila = lazy(() => import("./pages/ejecucion/Fila"));
const Internacion = lazy(() => import("./pages/ejecucion/Internacion"));
const Agenda = lazy(() => import("./pages/ejecucion/Agenda"));
const Farmacia = lazy(() => import("./pages/ejecucion/Farmacia"));
const RedTraslados = lazy(() => import("./pages/ejecucion/RedTraslados"));
const Flujos = lazy(() => import("./pages/diseno/Flujos"));
const FlujoEditor = lazy(() => import("./pages/diseno/FlujoEditor"));
const MapaFlujos = lazy(() => import("./pages/diseno/MapaFlujos"));
const Formularios = lazy(() => import("./pages/diseno/Formularios"));
const FormularioDetalle = lazy(() => import("./pages/diseno/FormularioDetalle"));
const Areas = lazy(() => import("./pages/admin/Areas"));
const Usuarios = lazy(() => import("./pages/admin/Usuarios"));
const Registros = lazy(() => import("./pages/registros/Registros"));
const HistoriaDetalle = lazy(() => import("./pages/registros/HistoriaDetalle"));
const Legajo = lazy(() => import("./pages/registros/Legajo"));
const Accesos = lazy(() => import("./pages/auditoria/Accesos"));

// Landing: el super admin ve el directorio; el resto entra a su institución.
function Landing() {
  const { user } = useAuth();
  const { institucion, setInstitucion } = useInstitucion();
  const [estado, setEstado] = useState("cargando");
  // A dónde iba antes de pasar por acá (lo deja `Protected`). Sin esto, entrar
  // por un link a un caso terminaba siempre en Inicio.
  const destino = useLocation().state?.desde;

  useEffect(() => {
    if (institucion) return;
    if (user?.is_superuser) {
      setEstado("directorio");
      return;
    }
    (async () => {
      const d = await api.get("/instituciones/");
      const lista = d.results || d;
      if (lista[0]) {
        setInstitucion(lista[0]); // entra a su institución automáticamente
      } else {
        setEstado("sin-institucion");
      }
    })();
  }, [user, institucion, setInstitucion]);

  if (institucion) return <Navigate to={destino || "/inicio"} replace />;
  if (estado === "directorio") return <Directorio />;
  if (estado === "sin-institucion")
    return <div style={{ padding: 48, textAlign: "center", color: "#667085" }}>No tenés ninguna institución asignada. Pedile a un administrador que te dé acceso.</div>;
  return <Spinner label="Cargando…" />;
}

// Pantalla de inicio según el rol: el operador puro (administrativo/médico) cae
// en su worklist "Mi trabajo"; los roles de configuración/diseño ven el panel.
function InicioHome() {
  const { puedeVer } = useInstitucion();
  const operativo = puedeVer("casos_operar") && !puedeVer("config_institucional") && !puedeVer("diseno_flujos");
  return operativo ? <MiTrabajo /> : <Inicio />;
}

/**
 * Resuelve el estado de sesión común a las rutas protegidas.
 *
 * Devuelve un elemento a renderizar, o null si la sesión está lista.
 * Importa el orden: `error` va ANTES que `!user`. Si no se pudo consultar quién
 * es la persona (sin red, backend caído), mandarla a login sería mentirle: no la
 * echaron, no se pudo preguntar. Se le ofrece reintentar sin perder el token.
 */
function usePuerta() {
  const { user, loading, error, reintentar } = useAuth();
  if (loading) return <Spinner label="Cargando sesión…" />;
  if (error)
    return (
      <EstadoError
        error={error}
        onReintentar={reintentar}
        titulo="No se pudo conectar con el servidor"
      />
    );
  if (!user) return <Navigate to="/login" replace />;
  return null;
}

// Ruta protegida que además requiere una institución en contexto.
function AccesoDenegado() {
  return (
    <div className="p-lg sm:p-[30px]">
      <Card className="max-w-[36rem] p-6">
        <h2 className="text-lg font-bold">Acceso denegado</h2>
        <p className="mt-2 text-md text-texto-debil">
          Tu rol en esta institucion no habilita esta seccion.
        </p>
      </Card>
    </div>
  );
}

function PantallaCargando() {
  return (
    <div className="flex min-h-[280px] items-center justify-center">
      <Spinner label="Cargando pantalla..." />
    </div>
  );
}

function Protected({ children, cap }) {
  const puerta = usePuerta();
  const { institucion, puedeVer, cargandoRoles } = useInstitucion();
  const loc = useLocation();
  if (puerta) return puerta;
  // Se recuerda a dónde iba: el Landing elige institución y lo devuelve ahí.
  if (!institucion) return <Navigate to="/" state={{ desde: loc.pathname + loc.search }} replace />;
  if (cargandoRoles) return <Spinner label="Cargando permisos..." />;
  if (cap && !puedeVer(cap)) return <Shell><AccesoDenegado /></Shell>;
  return <Shell><Suspense fallback={<PantallaCargando />}>{children}</Suspense></Shell>;
}

function AuthOnly({ children }) {
  return usePuerta() ?? children;
}

const P = (el, cap) => <Protected cap={cap}>{el}</Protected>;

export default function App() {
  return (
    <Suspense fallback={<PantallaCargando />}>
    <Routes>
      <Route path="/login" element={<Login />} />
      {/* Pantalla pública de llamados (TV de sala de espera): sin login, por token. */}
      <Route path="/pantalla/:token" element={<PantallaLlamados />} />
      <Route path="/" element={<AuthOnly><Landing /></AuthOnly>} />

      <Route path="/inicio" element={P(<InicioHome />)} />
      <Route path="/dashboard" element={P(<Dashboard />, "supervision")} />
      <Route path="/notificaciones" element={P(<Notificaciones />)} />
      <Route path="/puesto/:id" element={P(<PuestoDetalle />, "casos_operar")} />

      {/* TRABAJO */}
      <Route path="/supervision" element={P(<Supervision />, "supervision")} />
      <Route path="/bandeja" element={P(<Bandejas />, "casos_operar")} />
      <Route path="/filas" element={P(<Fila />, "filas")} />
      <Route path="/internacion" element={P(<Internacion />, "internacion")} />
      <Route path="/agenda" element={P(<Agenda />, "turnos")} />
      <Route path="/farmacia" element={P(<Farmacia />, "farmacia_stock")} />
      <Route path="/red" element={P(<RedTraslados />, "traslados_red")} />
      <Route path="/casos" element={P(<Casos />, "casos_operar")} />
      <Route path="/casos/:id" element={P(<CasoDetalle />, "casos_operar")} />

      {/* REGISTROS */}
      <Route path="/historia" element={P(<Registros />, "historia_clinica")} />
      <Route path="/historia/:id" element={P(<HistoriaDetalle />, "historia_clinica")} />
      <Route path="/legajo" element={P(<Legajo />)} />
      <Route path="/accesos" element={P(<Accesos />, "auditoria")} />

      {/* DISEÑO */}
      <Route path="/flujos" element={P(<Flujos />, "diseno_flujos")} />
      <Route path="/flujos/:id" element={P(<FlujoEditor />, "diseno_flujos")} />
      <Route path="/mapa" element={P(<MapaFlujos />, "diseno_flujos")} />
      <Route path="/formularios" element={P(<Formularios />, "diseno_flujos")} />
      <Route path="/formularios/:id" element={P(<FormularioDetalle />, "diseno_flujos")} />

      {/* SISTEMA */}
      {/* Cada sección del área es una página: /estructura/12/staff. La ficha de
          sub-área cuelga aparte porque lleva su propio id y no es una sección. */}
      <Route path="/estructura" element={P(<Areas />, "config_institucional")} />
      <Route path="/estructura/:areaId" element={P(<Areas />, "config_institucional")} />
      <Route path="/estructura/:areaId/sub/:subId" element={P(<Areas />, "config_institucional")} />
      <Route path="/estructura/:areaId/:seccion" element={P(<Areas />, "config_institucional")} />
      <Route path="/administracion" element={P(<Usuarios />, "config_institucional")} />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
    </Suspense>
  );
}
