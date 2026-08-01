// Cliente HTTP contra la API de Cauce.
// Maneja el token JWT (access + refresh) en localStorage y reintenta una vez
// ante un 401 refrescando el access token.

const BASE = import.meta.env.VITE_API_URL || "/api";
const ACCESS_KEY = "cauce.access";
const REFRESH_KEY = "cauce.refresh";
const PERSISTIR_KEY = "cauce.persistir";

/**
 * Dónde viven los tokens según haya elegido la persona.
 *
 * En una guardia la computadora es compartida. Si alguien NO marca «mantener la
 * sesión iniciada en este equipo», su token tiene que morir al cerrar el
 * navegador y no quedar disponible para el turno siguiente: eso es
 * `sessionStorage`, que se vacía solo al cerrar la pestaña.
 *
 * Hasta ahora la casilla estaba en la pantalla pero no hacía nada: la sesión
 * quedaba siempre guardada en el equipo. Una casilla de seguridad que miente es
 * peor que no tenerla, porque la gente se apoya en ella.
 */
const persistente = () => localStorage.getItem(PERSISTIR_KEY) !== "0";
const almacen = () => (persistente() ? localStorage : sessionStorage);

// Se lee de los dos: el token puede haber quedado en cualquiera según la elección
// de la sesión anterior.
const leer = (k) => sessionStorage.getItem(k) ?? localStorage.getItem(k);

export const tokens = {
  get access() {
    return leer(ACCESS_KEY);
  },
  get refresh() {
    return leer(REFRESH_KEY);
  },
  set({ access, refresh }) {
    const donde = almacen();
    if (access) donde.setItem(ACCESS_KEY, access);
    if (refresh) donde.setItem(REFRESH_KEY, refresh);
  },
  /** Elige dónde guardar. Se llama ANTES de `set`, al iniciar sesión. */
  persistir(si) {
    localStorage.setItem(PERSISTIR_KEY, si ? "1" : "0");
    // Se limpian los dos para no dejar un token viejo en el almacén que se deja
    // de usar: quedaría vivo y accesible sin que nadie lo espere.
    this.clear();
  },
  clear() {
    for (const donde of [localStorage, sessionStorage]) {
      donde.removeItem(ACCESS_KEY);
      donde.removeItem(REFRESH_KEY);
    }
  },
};

export class ApiError extends Error {
  constructor(status, data) {
    super(data?.detail || `Error ${status}`);
    this.status = status;
    this.data = data;
  }
}

async function parse(res) {
  const text = await res.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

// Refresco en vuelo, compartido por todas las llamadas.
//
// El backend tiene ROTATE_REFRESH_TOKENS activo: cada refresh invalida el token
// anterior. Sin esto, cuando varios pedidos reciben 401 a la vez —lo normal en
// una pantalla que carga tres consultas en paralelo— cada uno intenta refrescar
// con el MISMO token: el primero rota, los demás reciben 401 del refresh y
// terminan llamando a `tokens.clear()`, o sea cerrando la sesión del usuario en
// medio de la carga.
let refrescoEnVuelo = null;

function refreshAccess() {
  if (!tokens.refresh) return Promise.resolve(false);
  // Si ya hay uno en curso, todos esperan ese mismo resultado.
  if (refrescoEnVuelo) return refrescoEnVuelo;

  refrescoEnVuelo = (async () => {
    const res = await fetch(`${BASE}/auth/token/refresh/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh: tokens.refresh }),
    });
    if (!res.ok) return false;
    const data = await parse(res);
    tokens.set({ access: data.access, refresh: data.refresh });
    return true;
  })().finally(() => { refrescoEnVuelo = null; });

  return refrescoEnVuelo;
}

async function request(method, path, body, _retried = false) {
  const headers = { "Content-Type": "application/json" };
  if (tokens.access) headers.Authorization = `Bearer ${tokens.access}`;

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body != null ? JSON.stringify(body) : undefined,
  });

  if (res.status === 401 && !_retried && tokens.refresh) {
    const ok = await refreshAccess();
    if (ok) return request(method, path, body, true);
    tokens.clear();
  }

  const data = await parse(res);
  if (!res.ok) throw new ApiError(res.status, data);
  return data;
}

export const api = {
  get: (path) => request("GET", path),
  post: (path, body) => request("POST", path, body),
  patch: (path, body) => request("PATCH", path, body),
  put: (path, body) => request("PUT", path, body),
  del: (path) => request("DELETE", path),

  // Sube un archivo (multipart) y devuelve {nombre, url}.
  async upload(file) {
    const fd = new FormData();
    fd.append("archivo", file);
    const headers = {};
    if (tokens.access) headers.Authorization = `Bearer ${tokens.access}`;
    const res = await fetch(`${BASE}/archivos/`, { method: "POST", headers, body: fd });
    const data = await parse(res);
    if (!res.ok) throw new ApiError(res.status, data);
    return data;
  },

  async login(email, password, { recordar = true } = {}) {
    const res = await fetch(`${BASE}/auth/token/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    const data = await parse(res);
    if (!res.ok) throw new ApiError(res.status, data);
    // Primero se decide dónde guardar, después se guarda.
    tokens.persistir(recordar);
    tokens.set(data);
    return data;
  },
  logout() {
    tokens.clear();
  },
};
