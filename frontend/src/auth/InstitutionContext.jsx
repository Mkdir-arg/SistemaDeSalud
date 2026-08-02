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
  admin: ["config", "diseno", "trabajo", "registros", "supervision"],
  configurador: ["diseno"],
  jefe_area: ["trabajo", "registros", "supervision"], // supervisa su área
  administrativo: ["trabajo", "registros"],
  enfermeria: ["trabajo", "registros"], // opera, pero no firma atenciones (regla del motor)
  medico: ["trabajo", "registros"], // la diferencia es firmar atenciones
};

// Vista "ver como rol" (selector de la barra superior, sólo super admin).
export const VISTA_CAPS = {
  configurador: ["diseno"],
  administrativo: ["trabajo", "registros"],
  sistema: ["config", "diseno", "trabajo", "registros"],
};

/*
 * La institución guardada, leída ANTES del primer render.
 *
 * Estaba en un `useEffect`, que corre un render tarde: en esa primera pasada
 * `institucion` era null y las rutas protegidas ya habían redirigido a «/»,
 * aunque el dato estuviera en localStorage todo el tiempo. En la práctica eso
 * significaba que recargar la página estando en Filas —o abrir el link a un
 * caso que te pasaron— te dejaba en Inicio, perdiendo dónde estabas.
 */
function institucionGuardada() {
  try {
    return JSON.parse(localStorage.getItem(KEY)) || null;
  } catch {
    return null;
  }
}

export function InstitutionProvider({ children }) {
  const { user } = useAuth();
  const [institucion, setInstitucionState] = useState(institucionGuardada);
  const [roles, setRoles] = useState([]); // roles del usuario en la institución actual
  const [vista, setVista] = useState("sistema"); // vista del super admin
  const [cargandoRoles, setCargandoRoles] = useState(false);

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
