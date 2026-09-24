import { createContext, useContext, useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ApiError, api, tokens } from "../api/client";

const AuthContext = createContext(null);
const minutosConfigurados = Number(import.meta.env.VITE_IDLE_LOCK_MINUTES);
const MINUTOS_INACTIVIDAD = Number.isFinite(minutosConfigurados) && minutosConfigurados >= 3
  ? minutosConfigurados : 15;
const AVISO_MS = 2 * 60_000;

function ambitoGuardado() {
  try {
    return JSON.parse(localStorage.getItem("salud.institucion") || "null")?.id ?? null;
  } catch {
    return null;
  }
}

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
  const queryClient = useQueryClient();
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [intento, setIntento] = useState(0); // lo incrementa `reintentar`
  const [locked, setLocked] = useState(false);
  const [aviso, setAviso] = useState(0);
  const ultimaActividad = useRef(Date.now());
  const ambitoAlBloquear = useRef(null);
  const bloqueando = useRef(false);

  useEffect(() => {
    if (locked) document.body.dataset.sesionBloqueada = "1";
    else delete document.body.dataset.sesionBloqueada;
    return () => { delete document.body.dataset.sesionBloqueada; };
  }, [locked]);

  useEffect(() => {
    if (!user || locked || !window.BroadcastChannel) return undefined;
    const canal = new BroadcastChannel("salud-sesion");
    canal.onmessage = (evento) => {
      if (evento.data !== "bloquear" || bloqueando.current) return;
      bloqueando.current = true;
      ambitoAlBloquear.current = ambitoGuardado();
      api.logout();
      setLocked(true);
    };
    return () => canal.close();
  }, [user, locked]);

  useEffect(() => {
    if (!user || locked) return undefined;
    ultimaActividad.current = Date.now();
    const registrarActividad = () => {
      ultimaActividad.current = Date.now();
      setAviso(0);
    };
    const controlar = () => {
      const restante = MINUTOS_INACTIVIDAD * 60_000 - (Date.now() - ultimaActividad.current);
      if (restante <= 0 && !bloqueando.current) {
        bloqueando.current = true;
        ambitoAlBloquear.current = ambitoGuardado();
        api.logout();
        if (window.BroadcastChannel) {
          const canal = new BroadcastChannel("salud-sesion");
          canal.postMessage("bloquear");
          canal.close();
        }
        setLocked(true);
        setAviso(0);
      } else {
        setAviso(restante <= AVISO_MS ? Math.ceil(restante / 60_000) : 0);
      }
    };
    const eventos = ["keydown", "pointerdown", "pointermove", "touchstart", "wheel"];
    eventos.forEach((evento) => window.addEventListener(evento, registrarActividad, { passive: true }));
    window.addEventListener("focus", controlar);
    document.addEventListener("visibilitychange", controlar);
    const intervalo = window.setInterval(controlar, 10_000);
    return () => {
      eventos.forEach((evento) => window.removeEventListener(evento, registrarActividad));
      window.removeEventListener("focus", controlar);
      document.removeEventListener("visibilitychange", controlar);
      window.clearInterval(intervalo);
    };
  }, [user, locked]);

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
    ultimaActividad.current = Date.now();
    return me;
  }

  function logout() {
    api.logout();
    if (window.BroadcastChannel) {
      const canal = new BroadcastChannel("salud-sesion");
      canal.postMessage("bloquear");
      canal.close();
    }
    queryClient.clear();
    setUser(null);
    setLocked(false);
    setAviso(0);
  }

  async function desbloquear(email, password) {
    await api.login(email, password, { recordar: false });
    try {
      const me = await api.get("/usuarios/me/");
      const ambitoActual = ambitoGuardado();
      const capacidades = me.capacidades_por_institucion || {};
      const accesoGlobal = me.is_superuser || Object.values(capacidades).some((lista) => lista.includes("gobierno_plataforma"));
      const ambitoAutorizado = ambitoActual == null || accesoGlobal || Object.prototype.hasOwnProperty.call(capacidades, String(ambitoActual));
      if (String(me.id) !== String(user?.id) || String(ambitoActual) !== String(ambitoAlBloquear.current) || !ambitoAutorizado) {
        // La vista clínica sigue oculta durante la navegación: otra persona o
        // una cuenta sin este ámbito jamás ve el borrador que quedó en memoria.
        api.logout();
        queryClient.clear();
        window.location.replace("/login");
        return;
      }
      queryClient.invalidateQueries();
      setUser(me);
      ultimaActividad.current = Date.now();
      bloqueando.current = false;
      setLocked(false);
    } catch (error) {
      api.logout();
      throw error;
    }
  }

  return (
    <AuthContext.Provider value={{ user, loading, error, reintentar, login, logout }}>
      <div aria-hidden={locked || undefined} inert={locked ? "" : undefined}
        style={locked ? { display: "none" } : undefined}>{children}</div>
      {locked && <PantallaBloqueada onDesbloquear={desbloquear} />}
      {!!aviso && !locked && <div role="status" className="fixed bottom-4 left-4 z-[1000] rounded-lg border border-division bg-superficie p-4 shadow-float">
        <p>La sesión se bloqueará por inactividad en {aviso} {aviso === 1 ? "minuto" : "minutos"}.</p>
        <button className="mt-2 rounded-md bg-accent px-3 py-2 text-sobre-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
          onClick={() => { ultimaActividad.current = Date.now(); setAviso(0); }}>Continuar trabajando</button>
      </div>}
    </AuthContext.Provider>
  );
}

function PantallaBloqueada({ onDesbloquear }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [cargando, setCargando] = useState(false);
  async function enviar(e) {
    e.preventDefault();
    setCargando(true);
    setError("");
    try {
      await onDesbloquear(email, password);
    } catch {
      setError("No se pudo reanudar la sesión. Comprobá tus credenciales y reintentá.");
    } finally {
      setCargando(false);
    }
  }
  return <main className="fixed inset-0 z-[10000] flex items-center justify-center bg-fondo p-6">
    <form onSubmit={enviar} className="w-full max-w-[28rem] rounded-lg border border-division bg-superficie p-6 shadow-modal">
      <h1 className="text-xxl font-bold text-texto-fuerte">Sesión bloqueada</h1>
      <p className="mt-2 text-md text-texto-debil">Por inactividad, ingresá de nuevo con la misma cuenta para continuar. El formulario abierto permanece en esta pestaña.</p>
      <label className="mt-5 block text-md font-semibold">Correo de la cuenta
        <input type="email" required autoComplete="username" autoFocus value={email} onChange={(e) => setEmail(e.target.value)}
          className="mt-1 h-11 w-full rounded-md border border-campo-borde bg-superficie px-3 focus-visible:outline-2 focus-visible:outline-accent" />
      </label>
      <label className="mt-4 block text-md font-semibold">Contraseña
        <input type="password" required autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)}
          className="mt-1 h-11 w-full rounded-md border border-campo-borde bg-superficie px-3 focus-visible:outline-2 focus-visible:outline-accent" />
      </label>
      {error && <p role="alert" className="mt-3 text-md text-danger">{error}</p>}
      <button disabled={cargando} className="mt-5 h-11 w-full rounded-md bg-accent font-semibold text-sobre-accent disabled:opacity-50">
        {cargando ? "Verificando…" : "Reanudar sesión"}
      </button>
    </form>
  </main>;
}

export function useAuth() {
  return useContext(AuthContext);
}
