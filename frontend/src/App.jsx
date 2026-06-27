import { useEffect, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { api } from "./api/client";
import { useAuth } from "./auth/AuthContext";
import { useInstitucion } from "./auth/InstitutionContext";
import { Shell } from "./components/Shell";
import { Spinner } from "./components/ui";
import Login from "./pages/Login";
import PantallaLlamados from "./pages/PantallaLlamados";
import Directorio from "./pages/Directorio";
import Inicio from "./pages/Inicio";
import Dashboard from "./pages/Dashboard";
import MiTrabajo from "./pages/MiTrabajo";
import PuestoDetalle from "./pages/PuestoDetalle";
import Supervision from "./pages/Supervision";
import Notificaciones from "./pages/Notificaciones";
import Bandejas from "./pages/ejecucion/Bandejas";
import Casos from "./pages/ejecucion/Casos";
import CasoDetalle from "./pages/ejecucion/CasoDetalle";
import Fila from "./pages/ejecucion/Fila";
import Flujos from "./pages/diseno/Flujos";
import FlujoEditor from "./pages/diseno/FlujoEditor";
import MapaFlujos from "./pages/diseno/MapaFlujos";
import Formularios from "./pages/diseno/Formularios";
import FormularioDetalle from "./pages/diseno/FormularioDetalle";
import Areas from "./pages/admin/Areas";
import Usuarios from "./pages/admin/Usuarios";
import Registros from "./pages/registros/Registros";
import HistoriaDetalle from "./pages/registros/HistoriaDetalle";
import Legajo from "./pages/registros/Legajo";

// Landing: el super admin ve el directorio; el resto entra a su institución.
function Landing() {
  const { user } = useAuth();
  const { institucion, setInstitucion } = useInstitucion();
  const [estado, setEstado] = useState("cargando");

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

  if (institucion) return <Navigate to="/inicio" replace />;
  if (estado === "directorio") return <Directorio />;
  if (estado === "sin-institucion")
    return <div style={{ padding: 48, textAlign: "center", color: "#667085" }}>No tenés ninguna institución asignada. Pedile a un administrador que te dé acceso.</div>;
  return <Spinner label="Cargando…" />;
}

// Pantalla de inicio según el rol: el operador puro (administrativo/médico) cae
// en su worklist "Mi trabajo"; los roles de configuración/diseño ven el panel.
function InicioHome() {
  const { puedeVer } = useInstitucion();
  const operativo = puedeVer("trabajo") && !puedeVer("config") && !puedeVer("diseno");
  return operativo ? <MiTrabajo /> : <Inicio />;
}

// Ruta protegida que además requiere una institución en contexto.
function Protected({ children }) {
  const { user, loading } = useAuth();
  const { institucion } = useInstitucion();
  if (loading) return <Spinner label="Cargando sesión…" />;
  if (!user) return <Navigate to="/login" replace />;
  if (!institucion) return <Navigate to="/" replace />;
  return <Shell>{children}</Shell>;
}

function AuthOnly({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <Spinner label="Cargando sesión…" />;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

const P = (el) => <Protected>{el}</Protected>;

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      {/* Pantalla pública de llamados (TV de sala de espera): sin login, por token. */}
      <Route path="/pantalla/:token" element={<PantallaLlamados />} />
      <Route path="/" element={<AuthOnly><Landing /></AuthOnly>} />

      <Route path="/inicio" element={P(<InicioHome />)} />
      <Route path="/dashboard" element={P(<Dashboard />)} />
      <Route path="/notificaciones" element={P(<Notificaciones />)} />
      <Route path="/puesto/:id" element={P(<PuestoDetalle />)} />

      {/* TRABAJO */}
      <Route path="/supervision" element={P(<Supervision />)} />
      <Route path="/bandeja" element={P(<Bandejas />)} />
      <Route path="/filas" element={P(<Fila />)} />
      <Route path="/casos" element={P(<Casos />)} />
      <Route path="/casos/:id" element={P(<CasoDetalle />)} />

      {/* REGISTROS */}
      <Route path="/historia" element={P(<Registros />)} />
      <Route path="/historia/:id" element={P(<HistoriaDetalle />)} />
      <Route path="/legajo" element={P(<Legajo />)} />

      {/* DISEÑO */}
      <Route path="/flujos" element={P(<Flujos />)} />
      <Route path="/flujos/:id" element={P(<FlujoEditor />)} />
      <Route path="/mapa" element={P(<MapaFlujos />)} />
      <Route path="/formularios" element={P(<Formularios />)} />
      <Route path="/formularios/:id" element={P(<FormularioDetalle />)} />

      {/* SISTEMA */}
      <Route path="/estructura" element={P(<Areas />)} />
      <Route path="/administracion" element={P(<Usuarios />)} />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
