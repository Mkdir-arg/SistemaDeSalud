// Cliente HTTP contra la API del sistema.
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

/**
 * Simulación de perfiles del superusuario.
 *
 * Mientras hay una, cada pedido lleva `X-PLEXO-Simulacion` y el backend responde
 * con los permisos y el alcance de la cuenta de referencia. Vive en
 * `sessionStorage`: vale solo para esta pestaña y muere con ella. Los pedidos
 * que administran la simulación (catálogo, inicio, salida) salen sin el
 * encabezado, con la identidad real del superusuario.
 */
const SIMULACION_KEY = "salud.simulacion";
export const EVENTO_SIMULACION_TERMINADA = "salud:simulacion-terminada";

export const simulacion = {
  get() {
    try {
      return JSON.parse(sessionStorage.getItem(SIMULACION_KEY) || "null");
    } catch {
      return null;
    }
  },
  set(datos) {
    sessionStorage.setItem(SIMULACION_KEY, JSON.stringify(datos));
  },
  clear() {
    sessionStorage.removeItem(SIMULACION_KEY);
  },
};

function encabezadoSimulacion(headers, sinSimulacion) {
  const actual = sinSimulacion ? null : simulacion.get();
  if (actual?.id) headers["X-PLEXO-Simulacion"] = actual.id;
}

// El servidor rechazó la simulación (terminó, venció o la cuenta cambió). Se
// abandona en el acto: seguir mandando el encabezado dejaría la pantalla sin
// poder hacer nada, y nunca se reintenta como superusuario sin avisar.
function simulacionRechazada(status, data) {
  if (status !== 403 || data?.simulacion !== "rechazada" || !simulacion.get()) return;
  simulacion.clear();
  window.dispatchEvent(new CustomEvent(EVENTO_SIMULACION_TERMINADA, { detail: data?.detail || "" }));
}

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

// En un 4xx el `detail` del servidor le explica a la persona qué pasó («acceso
// revocado», «antecedente no disponible con tu acceso actual») y se muestra
// (#112, decisión G1). El genérico queda de respaldo cuando no viene, y siempre
// en 5xx, para no exponer detalles internos. El 401 sigue genérico: lo maneja
// el circuito de sesión y no conviene distinguir por qué falló un ingreso.
export function mensajeRespuesta(status, data) {
  if (status >= 500) return "El servicio no está disponible en este momento. Reintentá más tarde.";
  if (status === 401) return "Tu sesión venció o las credenciales no son válidas. Ingresá nuevamente.";
  const objeto = typeof data === "object" && data !== null;
  if (status === 403 || status === 404) {
    // Sólo el `detail`: el resto de la respuesta trae marcas para la app
    // (por ejemplo `simulacion`), no texto para la persona.
    const detalle = objeto ? mensajesValidacion(data.detail) : "";
    if (detalle) return detalle;
    return status === 403
      ? "No tenés permiso para realizar esta operación."
      : "No se encontró el recurso solicitado.";
  }
  if (objeto) {
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

export async function parse(res) {
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
let credencialesDelRefresco = null;

// Lo mismo entre pestañas. Con «mantener la sesión» todas comparten el refresh
// de localStorage, y el backend lo acepta una sola vez: la segunda pestaña
// recibe 401 aunque la sesión siga viva (#172, «conservar la renovación
// válida»). Si ese 401 llevara a `tokens.clear()`, borraría también la
// renovación ganadora. Web Locks serializa la renovación; sin soporte, el
// almacén releído después del 401 distingue carrera de revocación.
function conCandadoEntrePestanas(renovar) {
  const locks = globalThis.navigator?.locks;
  if (!persistente() || typeof locks?.request !== "function") return renovar();
  return locks.request("salud.renovacion", renovar);
}

// Otra pestaña ya guardó una renovación distinta de la que esta iba a usar.
function renovadoEnOtraPestana(captura) {
  const vigente = tokens.refresh;
  if (!vigente || vigente === captura.refresh) return false;
  captura.refresh = vigente;
  return true;
}

function refreshAccess() {
  if (!tokens.refresh) return Promise.resolve(false);
  // Si ya hay uno en curso, todos esperan ese mismo resultado.
  if (refrescoEnVuelo && refrescoEpoch === sessionEpoch) return refrescoEnVuelo;

  const epoch = sessionEpoch;
  refrescoEpoch = epoch;
  const captura = { refresh: tokens.refresh };
  credencialesDelRefresco = captura;
  refrescoEnVuelo = conCandadoEntrePestanas(async () => {
    if (epoch !== sessionEpoch) return false;
    if (renovadoEnOtraPestana(captura)) return true;
    const res = await fetch(`${BASE}/auth/token/refresh/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh: captura.refresh }),
    });
    const data = await parse(res);
    // Un cierre explícito puede necesitar revocar el refresh recién rotado,
    // aunque ya se haya limpiado esta sesión. Nunca reinstalarlo en ese caso.
    if (res.ok && typeof data?.refresh === "string") captura.refresh = data.refresh;
    if (epoch !== sessionEpoch) return false;
    // Como en el portal: un fallo temporal no demuestra que la credencial
    // esté revocada. Propagarlo permite reintentar sin perder la sesión.
    if (!res.ok) {
      if (res.status === 400 || res.status === 401) return renovadoEnOtraPestana(captura);
      throw new ApiError(res.status, data);
    }
    tokens.set({ access: data.access, refresh: data.refresh });
    return true;
  }).finally(() => {
    if (refrescoEpoch === epoch) {
      refrescoEnVuelo = null;
      refrescoEpoch = null;
      credencialesDelRefresco = null;
    }
  });

  return refrescoEnVuelo;
}

async function cerrarSesionRemota(pendiente, captura) {
  // Es un límite de espera local: un timeout no demuestra que el servidor
  // haya cancelado el efecto ni confirma la revocación.
  const limite = AbortSignal.timeout(10_000);
  let alVencer;
  const vencimiento = new Promise(resolve => {
    alVencer = () => resolve(false);
    limite.addEventListener("abort", alVencer, { once: true });
  });
  const cierre = (async () => {
    if (pendiente) await pendiente.catch(() => null);
    if (limite.aborted) return false;
    try {
      const respuesta = await fetch(`${BASE}/auth/logout/`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh: captura.refresh }),
        credentials: "omit", redirect: "error", cache: "no-store", signal: limite,
      });
      return respuesta.status === 204;
    } catch {
      return false;
    }
  })();
  try {
    return await Promise.race([cierre, vencimiento]);
  } finally {
    limite.removeEventListener("abort", alVencer);
  }
}

async function request(method, path, body, _retried = false, { multipart = false, blob = false, sinSimulacion = false, publico = false } = {}) {
  const epoch = sessionEpoch;
  const headers = multipart ? {} : { "Content-Type": "application/json" };
  // Con cuál salió ESTE pedido. Se guarda para poder distinguir, al volver con
  // 401, si el token sigue siendo el mismo o si mientras tanto ya lo renovaron.
  const usado = publico ? null : tokens.access;
  if (usado) headers.Authorization = `Bearer ${usado}`;
  if (!publico) encabezadoSimulacion(headers, sinSimulacion);

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body != null ? (multipart ? body : JSON.stringify(body)) : undefined,
    ...(publico ? { credentials: "omit", redirect: "error", cache: "no-store" } : {}),
  });
  if (!publico && epoch !== sessionEpoch) throw new ApiError(401, null);

  if (!publico && res.status === 401 && !_retried && tokens.refresh) {
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
      return request(method, path, body, true, { multipart, blob, sinSimulacion, publico });
    }
    const ok = await refreshAccess();
    if (epoch !== sessionEpoch) throw new ApiError(401, null);
    if (ok) return request(method, path, body, true, { multipart, blob, sinSimulacion, publico });
    tokens.clear();
  }

  if (res.ok && blob) {
    const archivo = await res.blob();
    if (!publico && epoch !== sessionEpoch) throw new ApiError(401, null);
    return { blob: archivo, disposition: res.headers.get("Content-Disposition") };
  }
  const data = await parse(res);
  if (!publico && epoch !== sessionEpoch) throw new ApiError(401, null);
  if (!res.ok) {
    if (!publico) simulacionRechazada(res.status, data);
    throw new ApiError(res.status, data);
  }
  return data;
}

export const api = {
  get: (path) => request("GET", path),
  post: (path, body) => request("POST", path, body),
  // Recuperación y canje no dependen de la sesión institucional del navegador.
  public: {
    post: (path, body) => request("POST", path, body, false, { publico: true }),
  },
  // Con la identidad real del superusuario aunque haya una simulación activa.
  real: {
    get: (path) => request("GET", path, null, false, { sinSimulacion: true }),
    post: (path, body) => request("POST", path, body, false, { sinSimulacion: true }),
  },
  patch: (path, body) => request("PATCH", path, body),
  put: (path, body) => request("PUT", path, body),
  del: (path) => request("DELETE", path),
  multipart: (path, body) => request("POST", path, body, false, { multipart: true }),
  async download(path, nombre = "archivo", vigente = () => true) {
    const { blob, disposition } = await request("GET", path, null, false, { blob: true });
    // Una descarga de una vista desmontada o de otra consulta no se entrega.
    if (!vigente()) return;
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
    const { blob, disposition } = await request("POST", path, body, false, { blob: true, multipart: body instanceof FormData });
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
    encabezadoSimulacion(headers);
    const res = await fetch(`${BASE}/archivos/`, { method: "POST", headers, body: fd });
    if (epoch !== sessionEpoch) throw new ApiError(401, null);
    const data = await parse(res);
    if (!res.ok) {
      simulacionRechazada(res.status, data);
      throw new ApiError(res.status, data);
    }
    return data;
  },

  async downloadArchivo(ref, nombre = "archivo") {
    const epoch = sessionEpoch;
    const s = String(ref || "");
    // El estudio no decide a qué servidor enviamos el JWT o la simulación.
    // Admitir claves y URLs del endpoint propio, nunca destinos arbitrarios.
    let url;
    try {
      const base = new URL(`${BASE.replace(/\/+$/, "")}/`, window.location.href);
      const archivos = new URL("archivos/descargar/", base);
      url = new URL(/^[a-z][a-z\d+.-]*:|^\//i.test(s) ? s : `${archivos.href}${s}`, base);
      if (!s || /[\u0000-\u001f\u007f\\]/.test(s)
        || !["http:", "https:"].includes(url.protocol)
        || url.origin !== base.origin || url.username || url.password
        || !url.pathname.startsWith(archivos.pathname)
        || url.pathname === archivos.pathname) throw new Error("Referencia inválida");
    } catch {
      throw new ApiError(400, { detail: "El archivo no tiene una referencia válida en el sistema. Consultá a la institución." });
    }
    const headers = {};
    if (tokens.access) headers.Authorization = `Bearer ${tokens.access}`;
    encabezadoSimulacion(headers);
    let res = await fetch(url.href, { headers, redirect: "error" });
    if (epoch !== sessionEpoch) throw new ApiError(401, null);
    if (res.status === 401 && tokens.refresh) {
      const ok = await refreshAccess();
      if (ok) {
        const retryHeaders = {};
        if (tokens.access) retryHeaders.Authorization = `Bearer ${tokens.access}`;
        encabezadoSimulacion(retryHeaders);
        res = await fetch(url.href, { headers: retryHeaders, redirect: "error" });
        if (epoch !== sessionEpoch) throw new ApiError(401, null);
      }
    }
    const data = res.ok ? null : await parse(res);
    if (!res.ok) {
      simulacionRechazada(res.status, data);
      throw new ApiError(res.status, data);
    }
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
  cerrarSesion() {
    const mismaSesion = refrescoEpoch === sessionEpoch;
    const pendiente = mismaSesion ? refrescoEnVuelo : null;
    const captura = mismaSesion && credencialesDelRefresco
      ? credencialesDelRefresco : { refresh: tokens.refresh };
    const habiaAccess = Boolean(tokens.access);
    // Inmediato y único: ninguna continuación remota vuelve a tocar storage.
    tokens.clear();
    if (!captura.refresh) return Promise.resolve(habiaAccess ? false : null);
    return cerrarSesionRemota(pendiente, captura).catch(() => false);
  },
};
