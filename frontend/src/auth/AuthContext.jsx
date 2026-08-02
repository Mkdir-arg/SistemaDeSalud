import { createContext, useContext, useEffect, useState } from "react";
import { ApiError, api, tokens } from "../api/client";

const AuthContext = createContext(null);

/** Espera n ms (para el reintento escalonado del arranque). */
const esperar = (ms) => new Promise((r) => setTimeout(r, ms));

/**
 * Recupera el usuario al arrancar, reintentando ante fallas transitorias.
 *
 * Distingue dos cosas que antes se trataban igual:
 *  - el servidor dice que la credencial no sirve (401/403) → la sesión terminó
 *    de verdad, hay que ir a login;
 *  - no se pudo preguntar (sin red, 500, backend reiniciándose) → NO significa
 *    que la persona no esté autenticada. Antes cualquiera de estos borraba el
 *    token: un microcorte en medio de una guardia dejaba a alguien afuera y le
 *    hacía perder lo que estaba cargando.
 */
async function recuperarUsuario(intentos = 3) {
  for (let i = 0; ; i++) {
    try {
      return { user: await api.get("/usuarios/me/") };
    } catch (e) {
      const credencialRechazada = e instanceof ApiError && (e.status === 401 || e.status === 403);
      if (credencialRechazada) return { user: null };
      if (i >= intentos - 1) return { user: null, error: e };
      await esperar(300 * 2 ** i); // 300ms, 600ms
    }
  }
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [intento, setIntento] = useState(0); // lo incrementa `reintentar`

  // Al montar, si hay token intenta recuperar el usuario.
  useEffect(() => {
    let activo = true;
    async function cargar() {
      if (!tokens.access && !tokens.refresh) {
        setLoading(false);
        return;
      }
      setLoading(true);
      setError(null);
      const r = await recuperarUsuario();
      if (!activo) return;
      if (r.user) setUser(r.user);
      else if (r.error) setError(r.error); // se conserva el token: fue la red, no la sesión
      else api.logout(); // el servidor rechazó la credencial
      setLoading(false);
    }
    cargar();
    return () => {
      activo = false;
    };
  }, [intento]);

  const reintentar = () => setIntento((n) => n + 1);

  async function login(email, password, opciones) {
    await api.login(email, password, opciones);
    const me = await api.get("/usuarios/me/");
    setError(null);
    setUser(me);
    return me;
  }

  function logout() {
    api.logout();
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, loading, error, reintentar, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
