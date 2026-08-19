import { createContext, useContext, useEffect, useState } from "react";
import { useAuth } from "./AuthContext";

const InstitutionContext = createContext(null);
const KEY = "cauce.institucion";

// Solo aplica al super admin cuando usa "ver como". Para usuarios reales, las
// capacidades vienen de /usuarios/me/ y el frontend no replica la matriz de roles.
const CAPS_SISTEMA = [
  "config", "diseno", "trabajo", "registros", "supervision", "auditoria",
  "padron_admision", "historia_clinica", "prescripcion", "solicitud_estudios",
  "turnos", "casos_operar", "filas", "internacion", "farmacia_stock",
  "traslados_red", "config_institucional", "diseno_flujos", "gobierno_plataforma",
];

export const VISTA_CAPS = {
  configurador: ["diseno", "diseno_flujos"],
  administrativo: [
    "trabajo", "registros", "padron_admision", "turnos", "casos_operar",
    "filas", "traslados_red",
  ],
  sistema: CAPS_SISTEMA,
};

function institucionGuardada() {
  try {
    return JSON.parse(localStorage.getItem(KEY)) || null;
  } catch {
    return null;
  }
}

function listaDe(mapa, institucionId) {
  if (!mapa || !institucionId) return [];
  return mapa[String(institucionId)] || mapa[institucionId] || [];
}

export function InstitutionProvider({ children }) {
  const { user, loading } = useAuth();
  const [institucion, setInstitucionState] = useState(institucionGuardada);
  const [vista, setVista] = useState("sistema");

  const roles = user?.is_superuser
    ? ["admin"]
    : listaDe(user?.roles_por_institucion, institucion?.id);

  const capacidades = user?.is_superuser
    ? (VISTA_CAPS[vista] || VISTA_CAPS.sistema)
    : listaDe(user?.capacidades_por_institucion, institucion?.id);

  const cargandoRoles = Boolean(
    institucion && user && !user.is_superuser && !user.capacidades_por_institucion
  );

  function setInstitucion(inst) {
    setInstitucionState(inst);
    if (inst) localStorage.setItem(KEY, JSON.stringify(inst));
    else localStorage.removeItem(KEY);
  }

  useEffect(() => {
    if (loading) return;
    if (!user) {
      setVista("sistema");
      setInstitucion(null);
      return;
    }
    if (user.is_superuser || !institucion) return;
    const mapa = user.capacidades_por_institucion;
    if (!mapa) return;
    const permitida = Object.prototype.hasOwnProperty.call(mapa, String(institucion.id))
      || Object.prototype.hasOwnProperty.call(mapa, institucion.id);
    if (!permitida) setInstitucion(null);
  }, [loading, user, institucion?.id]);

  function puedeVer(cap) {
    return capacidades.includes(cap);
  }

  return (
    <InstitutionContext.Provider value={{
      institucion,
      setInstitucion,
      roles,
      capacidades,
      puedeVer,
      cargandoRoles,
      vista,
      setVista,
    }}>
      {children}
    </InstitutionContext.Provider>
  );
}

export function useInstitucion() {
  return useContext(InstitutionContext);
}
