// Cliente HTTP contra la API de I-Core Salud.
// Maneja el token JWT (access + refresh) en localStorage y reintenta una vez
// ante un 401 refrescando el access token.

const BASE = import.meta.env.VITE_API_URL || "/api";
const ACCESS_KEY = "salud.access";
const REFRESH_KEY = "salud.refresh";
const PERSISTIR_KEY = "salud.persistir";
let sessionEpoch = 0;

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
const persistente = () => localStorage.getItem(PERSISTIR_KEY) === "1";
const almacen = () => (persistente() ? localStorage : sessionStorage);

// Antes de que existiera la elección, todas las sesiones quedaban en
// localStorage. Si no hay un opt-in explícito, se descartan esos tokens al
// cargar la aplicación, incluso si esta pestaña no llega a iniciar sesión.
if (!persistente()) {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

// Se lee de los dos: el token puede haber quedado en cualquiera según la elección
// de la sesión anterior.
const leer = (k) => sessionStorage.getItem(k) ?? (persistente() ? localStorage.getItem(k) : null);

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
    sessionEpoch += 1;
    for (const donde of [localStorage, sessionStorage]) {
      donde.removeItem(ACCESS_KEY);
      donde.removeItem(REFRESH_KEY);
    }
  },
};

export class ApiError extends Error {
  constructor(status, data) {
    super(mensajeRespuesta(status, data));
    this.status = status;
    this.data = data;
  }
}

function mensajesValidacion(value) {
  if (typeof value === "string") return value.trim();
  if (Array.isArray(value)) return value.map(mensajesValidacion).filter(Boolean).join(" ");
  if (value && typeof value === "object") {
    return Object.entries(value).map(([campo, error]) => {
      const mensaje = mensajesValidacion(error);
      return mensaje ? `${["detail", "non_field_errors"].includes(campo) ? "" : `${campo}: `}${mensaje}` : "";
    }).filter(Boolean).join(" ");
  }
  return "";
}

export function mensajeRespuesta(status, data) {
  if (status >= 500) return "El servicio no está disponible en este momento. Reintentá más tarde.";
  if (status === 401) return "Tu sesión venció o las credenciales no son válidas. Ingresá nuevamente.";
  if (status === 403) return "No tenés permiso para realizar esta operación.";
  if (status === 404) return "No se encontró el recurso solicitado.";
  if (typeof data === "object" && data !== null) {
    const mensaje = mensajesValidacion(data);
    if (mensaje) return mensaje;
  }
  return "No se pudo completar la operación. Reintentá o consultá a soporte.";
}

export function mensajeError(error, porDefecto = "No se pudo completar la operación.") {
  if (error instanceof ApiError) return error.message;
  if (error instanceof TypeError) return "No se pudo conectar con el servicio. Comprobá la conexión y reintentá.";
  return porDefecto;
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
let refrescoEpoch = null;

function refreshAccess() {
  if (!tokens.refresh) return Promise.resolve(false);
  // Si ya hay uno en curso, todos esperan ese mismo resultado.
  if (refrescoEnVuelo && refrescoEpoch === sessionEpoch) return refrescoEnVuelo;

  const epoch = sessionEpoch;
  refrescoEpoch = epoch;
  refrescoEnVuelo = (async () => {
    const res = await fetch(`${BASE}/auth/token/refresh/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh: tokens.refresh }),
    });
    if (!res.ok || epoch !== sessionEpoch) return false;
    const data = await parse(res);
    if (epoch !== sessionEpoch) return false;
    tokens.set({ access: data.access, refresh: data.refresh });
    return true;
  })().finally(() => {
    if (refrescoEpoch === epoch) {
      refrescoEnVuelo = null;
      refrescoEpoch = null;
    }
  });

  return refrescoEnVuelo;
}

async function request(method, path, body, _retried = false, { multipart = false, blob = false } = {}) {
  const epoch = sessionEpoch;
  const headers = multipart ? {} : { "Content-Type": "application/json" };
  // Con cuál salió ESTE pedido. Se guarda para poder distinguir, al volver con
  // 401, si el token sigue siendo el mismo o si mientras tanto ya lo renovaron.
  const usado = tokens.access;
  if (usado) headers.Authorization = `Bearer ${usado}`;

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body != null ? (multipart ? body : JSON.stringify(body)) : undefined,
  });
  if (epoch !== sessionEpoch) throw new ApiError(401, null);

  if (res.status === 401 && !_retried && tokens.refresh) {
    /*
     * El pedido rezagado.
     *
     * `refrescoEnVuelo` junta a los que reciben 401 A LA VEZ, pero no alcanza:
     * un pedido más lento sale con el token viejo y vuelve DESPUÉS de que otro
     * ya refrescó. Ahí no hay refresco en vuelo al que sumarse, así que abría
     * uno nuevo —para un token que ya estaba renovado—. Con
     * ROTATE_REFRESH_TOKENS eso es una rotación de más; con
     * BLACKLIST_AFTER_ROTATION, si dos rezagados coinciden, uno invalida el
     * token del otro y la sesión se cierra en medio de la pantalla.
     *
     * Si el token cambió, no hay nada que refrescar: alcanza con reintentar.
     */
    if (tokens.access && tokens.access !== usado) {
      return request(method, path, body, true, { multipart, blob });
    }
    const ok = await refreshAccess();
    if (epoch !== sessionEpoch) throw new ApiError(401, null);
    if (ok) return request(method, path, body, true, { multipart, blob });
    tokens.clear();
  }

  if (res.ok && blob) {
    const archivo = await res.blob();
    if (epoch !== sessionEpoch) throw new ApiError(401, null);
    return { blob: archivo, disposition: res.headers.get("Content-Disposition") };
  }
  const data = await parse(res);
  if (epoch !== sessionEpoch) throw new ApiError(401, null);
  if (!res.ok) throw new ApiError(res.status, data);
  return data;
}

export const api = {
  get: (path) => request("GET", path),
  post: (path, body) => request("POST", path, body),
  patch: (path, body) => request("PATCH", path, body),
  put: (path, body) => request("PUT", path, body),
  del: (path) => request("DELETE", path),
  multipart: (path, body) => request("POST", path, body, false, { multipart: true }),
  async download(path, nombre = "archivo") {
    const { blob, disposition } = await request("GET", path, null, false, { blob: true });
    const href = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = href;
    a.download = (disposition?.match(/filename="?([^";]+)"?/)?.[1] || nombre).replace(/[\\/]/g, "_");
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(href), 1000);
  },

  async downloadPost(path, body, nombre = "archivo") {
    const { blob, disposition } = await request("POST", path, body, false, { blob: true });
    const href = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = href;
    a.download = (disposition?.match(/filename="?([^";]+)"?/)?.[1] || nombre).replace(/[\\/]/g, "_");
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(href), 1000);
  },

  // Sube un archivo (multipart) y devuelve {nombre, ruta, url}.
  async upload(file, { institucion } = {}) {
    const epoch = sessionEpoch;
    const fd = new FormData();
    fd.append("archivo", file);
    if (institucion) fd.append("institucion", String(institucion));
    const headers = {};
    if (tokens.access) headers.Authorization = `Bearer ${tokens.access}`;
    const res = await fetch(`${BASE}/archivos/`, { method: "POST", headers, body: fd });
    if (epoch !== sessionEpoch) throw new ApiError(401, null);
    const data = await parse(res);
    if (!res.ok) throw new ApiError(res.status, data);
    return data;
  },

  async downloadArchivo(ref, nombre = "archivo") {
    const epoch = sessionEpoch;
    const s = String(ref || "");
    const url = /^https?:\/\//.test(s) || s.startsWith("/api/")
      ? s
      : `${BASE}/archivos/descargar/${s.replace(/^\/+/, "")}`;
    const headers = {};
    if (tokens.access) headers.Authorization = `Bearer ${tokens.access}`;
    let res = await fetch(url, { headers });
    if (epoch !== sessionEpoch) throw new ApiError(401, null);
    if (res.status === 401 && tokens.refresh) {
      const ok = await refreshAccess();
      if (ok) {
        const retryHeaders = {};
        if (tokens.access) retryHeaders.Authorization = `Bearer ${tokens.access}`;
        res = await fetch(url, { headers: retryHeaders });
        if (epoch !== sessionEpoch) throw new ApiError(401, null);
      }
    }
    const data = res.ok ? null : await parse(res);
    if (!res.ok) throw new ApiError(res.status, data);
    const blob = await res.blob();
    const href = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = href;
    a.download = (res.headers.get("Content-Disposition") || "").match(/filename="?([^"]+)"?/)?.[1] || nombre;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(href);
  },

  async login(email, password, { recordar = false } = {}) {
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
