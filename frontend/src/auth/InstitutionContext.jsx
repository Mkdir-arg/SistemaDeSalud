import { createContext, useContext, useEffect, useState } from "react";
import { api } from "../api/client";
import { useAuth } from "./AuthContext";

const InstitutionContext = createContext(null);
const KEY = "cauce.institucion";

// Grupos del menú que habilita cada rol (además, el super admin ve todo).
const GRUPOS_POR_ROL = {
  admin: ["TRABAJO", "REGISTROS", "DISEÑO", "SISTEMA"],
  configurador: ["DISEÑO"],
  administrativo: ["TRABAJO", "REGISTROS"],
};

// Vista "ver como rol" (selector de la barra superior, sólo super admin).
export const VISTA_GRUPOS = {
  configurador: ["DISEÑO"],
  administrativo: ["TRABAJO", "REGISTROS"],
  sistema: ["TRABAJO", "REGISTROS", "DISEÑO", "SISTEMA"],
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

  // ¿El usuario puede ver este grupo del menú en la institución actual?
  function puedeVer(grupo) {
    if (user?.is_superuser) return (VISTA_GRUPOS[vista] || VISTA_GRUPOS.sistema).includes(grupo);
    return roles.some((r) => (GRUPOS_POR_ROL[r] || []).includes(grupo));
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
