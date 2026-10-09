// Cliente HTTP del portal del paciente (#120), contra `/api/mi/*`.
//
// Es un cliente APARTE del de `client.js` a propósito: la persona que entra al
// portal no es un usuario del sistema. Nunca manda el JWT de HEN ni
// `X-HEN-Simulacion`, aunque en la misma pestaña haya una sesión del sistema o
// una simulación activa (una médica que se mira su propio portal desde la
// compu de la guardia no le tiene que prestar su sesión al portal, ni al revés).
//
// Los tokens del portal son opacos (`hp_…`) y viven en sessionStorage: mueren al
// cerrar la pestaña. El portal no ofrece «mantener la sesión iniciada».

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, mensajeError, parse } from "./client";

const BASE = `${import.meta.env.VITE_API_URL || "/api"}/mi`;
const ACCESS_KEY = "hen.portal.access";
const REFRESH_KEY = "hen.portal.refresh";

/** Se dispara cuando la sesión del portal venció y no se pudo renovar. */
export const EVENTO_PORTAL_VENCIDO = "hen:portal-vencido";
export const DEMASIADOS_INTENTOS = "Hiciste demasiados intentos. Probá de nuevo en unos minutos.";
// 429 propio de validar-identidad: hay otra validación de la misma cuenta en curso.
export const VALIDACION_EN_CURSO = "Ya estamos validando tu identidad. Esperá unos segundos y volvé a intentar.";

let epoch = 0;

export const sesionPortal = {
  get access() {
    return sessionStorage.getItem(ACCESS_KEY);
  },
  get refresh() {
    return sessionStorage.getItem(REFRESH_KEY);
  },
  set({ access, refresh }) {
    if (access) sessionStorage.setItem(ACCESS_KEY, access);
    if (refresh) sessionStorage.setItem(REFRESH_KEY, refresh);
  },
  clear() {
    epoch += 1;
    sessionStorage.removeItem(ACCESS_KEY);
    sessionStorage.removeItem(REFRESH_KEY);
  },
};

// Una sola renovación en vuelo. El backend rota los dos tokens en cada
// `renovar`: si dos pedidos con 401 renovaran a la vez con el mismo refresh, el
// segundo recibiría 401 y cerraría la sesión que el primero acababa de renovar.
//
// Limitación aceptada: una pestaña DUPLICADA copia el sessionStorage y comparte
// el refresh; cuando una renueva (rota), la otra queda con un refresh muerto y
// su próxima renovación la desloguea.
let renovacion = null;

/**
 * Resultado de renovar:
 * - `{ estado: "renovada" }`.
 * - `{ estado: "rechazada" }`: el servidor dijo que el refresh no sirve (401/400)
 *   o no hay refresh. La sesión terminó.
 * - `{ estado: "fallo", error }`: no se pudo preguntar (429, 5xx, sin red). La
 *   sesión puede seguir viva: se conservan los tokens y se propaga el error
 *   para que la pantalla diga «demasiados intentos» o deje reintentar.
 */
function renovar() {
  if (!sesionPortal.refresh) return Promise.resolve({ estado: "rechazada" });
  if (renovacion) return renovacion;
  const propia = epoch;
  renovacion = (async () => {
    let res;
    try {
      res = await fetch(`${BASE}/cuenta/renovar/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh: sesionPortal.refresh }),
      });
    } catch (error) {
      return { estado: "fallo", error };
    }
    const data = await parse(res);
    // Cerró sesión mientras tanto: no se resucita con tokens nuevos.
    if (propia !== epoch) return { estado: "fallo", error: new ApiError(401, null) };
    if (res.ok) {
      sesionPortal.set(data);
      return { estado: "renovada" };
    }
    if (res.status === 401 || res.status === 400) return { estado: "rechazada" };
    return { estado: "fallo", error: new ApiError(res.status, data) };
  })().finally(() => { renovacion = null; });
  return renovacion;
}

function sesionVencida() {
  sesionPortal.clear();
  window.dispatchEvent(new CustomEvent(EVENTO_PORTAL_VENCIDO));
}

/**
 * Pedido al portal. `publico` no manda token ni intenta renovar: un 401 ahí es
 * la respuesta del endpoint (credenciales inválidas), no una sesión vencida.
 */
async function pedir(method, path, body, { publico = false, renovado = false, sinRenovar = false, binario = false } = {}) {
  const headers = { "Content-Type": "application/json" };
  const usado = publico ? null : sesionPortal.access;
  if (usado) headers.Authorization = `Bearer ${usado}`;
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body != null ? JSON.stringify(body) : undefined,
  });

  if (res.status === 401 && !publico && !sinRenovar) {
    // Si mientras tanto otro pedido ya renovó, alcanza con reintentar.
    if (!renovado && sesionPortal.access && sesionPortal.access !== usado) return pedir(method, path, body, { renovado: true, binario });
    const r = renovado ? { estado: "rechazada" } : await renovar();
    if (r.estado === "renovada") return pedir(method, path, body, { renovado: true, binario });
    if (r.estado === "fallo") throw r.error;
    sesionVencida();
  }

  if (binario && res.ok) return { blob: await res.blob(), nombre: nombreDeArchivo(res) };
  const data = await parse(res);
  if (!res.ok) throw new ApiError(res.status, data);
  return data;
}

/** El nombre que manda el backend en `Content-Disposition`, si lo manda. */
function nombreDeArchivo(res) {
  const cabecera = res.headers.get("Content-Disposition") || "";
  const utf8 = /filename\*=UTF-8''([^;]+)/i.exec(cabecera);
  if (utf8) return decodeURIComponent(utf8[1]);
  return /filename="?([^";]+)"?/i.exec(cabecera)?.[1] || null;
}

export const portal = {
  get: (path) => pedir("GET", path),
  post: (path, body) => pedir("POST", path, body),
  publico: (path, body) => pedir("POST", path, body, { publico: true }),
  /** Un archivo: `{blob, nombre}`. Pasa por la misma renovación que el resto. */
  archivo: (path) => pedir("GET", path, null, { binario: true }),
};

/**
 * Texto para la persona. El 429 tiene el suyo; en el resto se muestra el
 * `detail` del backend, que en registro, olvido y reenvío es neutro a propósito:
 * nunca dice si el email existe.
 */
export function mensajePortal(error, porDefecto) {
  if (error instanceof ApiError) {
    if (error.status === 429) return error.data?.codigo === "validacion_en_curso" ? VALIDACION_EN_CURSO : DEMASIADOS_INTENTOS;
    if (error.status < 500 && typeof error.data?.detail === "string" && error.data.detail) return error.data.detail;
  }
  return mensajeError(error, porDefecto);
}

/**
 * Separa los errores de un 400 de DRF (`{campo: [mensajes]}`) en los de cada
 * campo conocido, para mostrarlos debajo del campo, y un mensaje general con el
 * resto (o con el error entero si no era de validación).
 */
export function erroresFormulario(error, campos) {
  if (!error) return { campos: {}, general: "" };
  const data = error instanceof ApiError && error.status === 400 && error.data && typeof error.data === "object" ? error.data : null;
  const porCampo = {};
  if (data) for (const campo of campos) {
    const valor = data[campo];
    if (valor) porCampo[campo] = Array.isArray(valor) ? valor.join(" ") : String(valor);
  }
  const quedan = data && Object.keys(data).some((k) => !campos.includes(k));
  const general = !data || quedan || !Object.keys(porCampo).length ? mensajePortal(error) : "";
  return { campos: porCampo, general };
}

/**
 * A qué pantalla corresponde la cuenta según cuánto completó. Con sesión el
 * email siempre está confirmado: la cuenta nace al elegir la contraseña desde
 * el enlace del correo, y el backend no emite sesión antes.
 */
export function rutaSegunCuenta(cuenta) {
  if (cuenta?.identidad !== "validada") return "/mi/validar-identidad";
  return "/mi/inicio";
}

const CLAVE_CUENTA = ["portal", "cuenta"];

export function useCuentaPortal() {
  return useQuery({
    queryKey: CLAVE_CUENTA,
    queryFn: () => portal.get("/cuenta/"),
    enabled: Boolean(sesionPortal.access),
  });
}

export function usePerfilPortal({ enabled = true } = {}) {
  return useQuery({ queryKey: ["portal", "perfil"], queryFn: () => portal.get("/perfil/"), enabled });
}

// Datos del paciente en toda la red (#121/#122). Todos exigen la identidad
// validada: la app sólo los pide detrás de `ConIdentidadValidada`.

export const CLAVE_TURNOS = ["portal", "turnos"];

export function useTurnosPortal() {
  return useQuery({ queryKey: CLAVE_TURNOS, queryFn: () => portal.get("/turnos/").then((d) => d.turnos) });
}

/** Confirmar o cancelar (`accion`). Devuelve el turno actualizado y lo reemplaza en la lista. */
export function useAccionTurno(accion) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id) => portal.post(`/turnos/${id}/${accion}/`),
    onSuccess: (turno) => qc.setQueryData(CLAVE_TURNOS, (lista) => lista?.map((t) => (t.id === turno.id ? turno : t))),
    // Un 409 dice que el turno cambió del lado del hospital: se relee.
    onError: () => qc.invalidateQueries({ queryKey: CLAVE_TURNOS }),
  });
}

export const LLAMADO_CADA_MS = 5000;

/** ¿Me están llamando? Mientras la pantalla está abierta, cada 5 segundos. */
export function useLlamadoPortal({ consultar = true } = {}) {
  return useQuery({
    queryKey: ["portal", "llamado"],
    queryFn: () => portal.get("/llamado/"),
    refetchInterval: consultar ? LLAMADO_CADA_MS : false,
    // Una pestaña en segundo plano no consulta; al volver, consulta en el acto.
    refetchIntervalInBackground: false,
  });
}

export function useResultadosPortal() {
  return useQuery({ queryKey: ["portal", "resultados"], queryFn: () => portal.get("/resultados/").then((d) => d.resultados) });
}

export function useCoberturaPortal() {
  return useQuery({ queryKey: ["portal", "cobertura"], queryFn: () => portal.get("/cobertura/").then((d) => d.coberturas) });
}

/** Baja el archivo real del estudio y lo entrega al navegador como descarga. */
export function useDescargarResultado() {
  return useMutation({
    mutationFn: async (estudio) => {
      const { blob, nombre } = await portal.archivo(`/resultados/${estudio.id}/archivo/`);
      guardarArchivo(blob, nombre || `estudio-${estudio.id}`);
    },
  });
}

/** Entrega un archivo al navegador como descarga. Las barras del nombre no se respetan. */
export function guardarArchivo(blob, nombre) {
  const url = URL.createObjectURL(blob);
  const enlace = document.createElement("a");
  enlace.href = url;
  enlace.download = nombre.replace(/[\\/]/g, "_");
  document.body.append(enlace);
  enlace.click();
  enlace.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** Pedido público sin efectos en la cache: registro, reenvío, olvido, verificar, restablecer. */
export function usePedidoPublico(path) {
  return useMutation({ mutationFn: (cuerpo) => portal.publico(path, cuerpo) });
}

export function useIngresar() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (cuerpo) => portal.publico("/cuenta/ingresar/", cuerpo),
    onSuccess: (data) => {
      qc.removeQueries({ queryKey: ["portal"] });
      sesionPortal.set(data);
      qc.setQueryData(CLAVE_CUENTA, data.cuenta);
    },
  });
}

/**
 * Elegir la contraseña desde el enlace del correo (`{token, password}`). Si sale
 * bien, el backend devuelve lo mismo que ingresar: queda logueada.
 */
export function useElegirClave() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (cuerpo) => portal.publico("/cuenta/verificar-email/", cuerpo),
    onSuccess: (data) => {
      qc.removeQueries({ queryKey: ["portal"] });
      sesionPortal.set(data);
      qc.setQueryData(CLAVE_CUENTA, data.cuenta);
    },
  });
}

export function useValidarIdentidad() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (datos) => portal.post("/cuenta/validar-identidad/", datos),
    onSuccess: (cuenta) => qc.setQueryData(CLAVE_CUENTA, cuenta),
  });
}

export function useSalir() {
  const qc = useQueryClient();
  return useMutation({
    // Se revoca la sesión en el servidor si se puede; si no (sin red, ya
    // vencida), igual se olvida acá: cerrar sesión nunca puede fallar.
    //
    // Si hay una renovación en vuelo se la espera: salir con el access viejo
    // dejaría viva en el servidor la sesión que esa renovación acaba de rotar.
    mutationFn: async () => {
      await renovacion?.catch(() => null);
      return pedir("POST", "/cuenta/salir/", null, { sinRenovar: true }).catch(() => null);
    },
    onSettled: () => {
      sesionPortal.clear();
      qc.removeQueries({ queryKey: ["portal"] });
    },
  });
}

/**
 * Saca el token de la barra de direcciones (y del historial) sin recargar. Se
 * conserva `history.state`: es donde React Router guarda su índice.
 */
export function limpiarHash() {
  if (!window.location.hash) return;
  window.history.replaceState(window.history.state, "", window.location.pathname + window.location.search);
}
