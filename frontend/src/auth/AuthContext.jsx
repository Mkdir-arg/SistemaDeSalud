import { createContext, useContext, useEffect, useState } from "react";
import { api, tokens } from "../api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // Al montar, si hay token intenta recuperar el usuario.
  useEffect(() => {
    let activo = true;
    async function cargar() {
      if (!tokens.access && !tokens.refresh) {
        setLoading(false);
        return;
      }
      try {
        const me = await api.get("/usuarios/me/");
        if (activo) setUser(me);
      } catch {
        api.logout();
      } finally {
        if (activo) setLoading(false);
      }
    }
    cargar();
    return () => {
      activo = false;
    };
  }, []);

  async function login(email, password) {
    await api.login(email, password);
    const me = await api.get("/usuarios/me/");
    setUser(me);
    return me;
  }

  function logout() {
    api.logout();
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
