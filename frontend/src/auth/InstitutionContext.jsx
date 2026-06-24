import { createContext, useContext, useEffect, useState } from "react";
import { api } from "../api/client";
import { useAuth } from "./AuthContext";

const InstitutionContext = createContext(null);
const KEY = "cauce.institucion";

// Capacidades que habilita cada rol. El menú gatea por capacidad (no por grupo),
// porque SISTEMA mezcla ítems de configuración (admin) con ítems de diseño (configurador).
//   config    → Estructura organizativa, Administración
//   diseno    → Flujos, Mapa de flujos, Formularios
//   trabajo   → Bandeja, Filas, Casos
//   registros → Historia clínica, Legajo
const CAPS_POR_ROL = {
  admin: ["config", "diseno", "trabajo", "registros"],
  configurador: ["diseno"],
  administrativo: ["trabajo", "registros"],
  medico: ["trabajo", "registros"], // igual que administrativo; la diferencia es firmar atenciones
};

// Vista "ver como rol" (selector de la barra superior, sólo super admin).
export const VISTA_CAPS = {
  configurador: ["diseno"],
  administrativo: ["trabajo", "registros"],
  sistema: ["config", "diseno", "trabajo", "registros"],
};

export function InstitutionProvider({ children }) {
  const { user } = useAuth();
  const [institucion, setInstitucionState] = useState(null);
  const [roles, setRoles] = useState([]); // roles del usuario en la institución actual
  const [vista, setVista] = useState("sistema"); // vista del super admin
  const [cargandoRoles, setCargandoRoles] = useState(false);

  // Restaura la institución elegida desde localStorage.
  useEffect(() => {
    const raw = localStorage.getItem(KEY);
    if (raw) {
      try {
        setInstitucionState(JSON.parse(raw));
      } catch {
        /* ignore */
      }
    }
  }, []);

  // Carga los roles del usuario en la institución seleccionada.
  useEffect(() => {
    if (!institucion || !user) {
      setRoles([]);
      return;
    }
    if (user.is_superuser) {
      setRoles(["admin"]); // el super admin actúa como admin dentro de cualquier institución
      return;
    }
    let activo = true;
    setCargandoRoles(true);
    (async () => {
      try {
        const d = await api.get(`/membresias/?usuario=${user.id}&institucion=${institucion.id}`);
        const lista = d.results || d;
        if (activo) setRoles(lista.map((m) => m.rol));
      } finally {
        if (activo) setCargandoRoles(false);
      }
    })();
    return () => {
      activo = false;
    };
  }, [institucion, user]);

  function setInstitucion(inst) {
    setInstitucionState(inst);
    if (inst) localStorage.setItem(KEY, JSON.stringify(inst));
    else localStorage.removeItem(KEY);
  }

  // ¿El usuario tiene esta capacidad en la institución actual?
  function puedeVer(cap) {
    if (user?.is_superuser) return (VISTA_CAPS[vista] || VISTA_CAPS.sistema).includes(cap);
    return roles.some((r) => (CAPS_POR_ROL[r] || []).includes(cap));
  }

  return (
    <InstitutionContext.Provider value={{ institucion, setInstitucion, roles, puedeVer, cargandoRoles, vista, setVista }}>
      {children}
    </InstitutionContext.Provider>
  );
}

export function useInstitucion() {
  return useContext(InstitutionContext);
}
