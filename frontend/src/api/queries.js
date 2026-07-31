import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "./client";

/** Arma `?a=1&b=2` descartando los valores vacíos (no ensucia la URL ni la cache). */
export function query(params = {}) {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") continue;
    qs.set(k, String(v));
  }
  const s = qs.toString();
  return s ? `?${s}` : "";
}

/**
 * Lista paginada de un recurso de la API.
 *
 * Django REST pagina de a 25 (`PAGE_SIZE` en settings) y devuelve
 * `{count, next, previous, results}`. Hasta ahora **ninguna** pantalla leía más
 * que `results`, así que mostraban los primeros 25 y descartaban el resto en
 * silencio: la pantalla de Casos enseñaba 25 de 531. Este hook devuelve también
 * el total y la cantidad de páginas para que la tabla pueda navegarlas.
 *
 * `placeholderData: keepPreviousData` evita el parpadeo al cambiar de página o de
 * orden: la tabla se queda con las filas anteriores (atenuadas) mientras llega la
 * nueva página, en vez de colapsar a un spinner.
 */
export function useLista(recurso, params = {}, opciones = {}) {
  const { page = 1, pageSize, ...resto } = params;

  const r = useQuery({
    queryKey: ["lista", recurso, { page, pageSize, ...resto }],
    queryFn: () => api.get(`/${recurso}/${query({ page, page_size: pageSize, ...resto })}`),
    placeholderData: keepPreviousData,
    ...opciones,
  });

  const d = r.data;
  // Algunos endpoints (los que no paginan) devuelven un array pelado.
  const filas = Array.isArray(d) ? d : d?.results || [];
  const total = Array.isArray(d) ? d.length : d?.count ?? 0;
  const porPagina = pageSize || (Array.isArray(d) ? filas.length : 25);

  return {
    ...r,
    filas,
    total,
    paginas: porPagina ? Math.max(1, Math.ceil(total / porPagina)) : 1,
    // `isPlaceholderData` marca que en pantalla están las filas de la consulta
    // anterior: sirve para atenuar la tabla sin desmontarla.
    refrescando: r.isPlaceholderData || r.isFetching,
  };
}

/** Un objeto por id. `null`/`undefined` como id deja la consulta en pausa. */
export function useDetalle(recurso, id, opciones = {}) {
  return useQuery({
    queryKey: ["detalle", recurso, id],
    queryFn: () => api.get(`/${recurso}/${id}/`),
    enabled: id != null,
    ...opciones,
  });
}

/**
 * Una acción que cambia datos del servidor.
 *
 * Al terminar invalida las listas: después de llamar a un paciente, la fila, la
 * bandeja y el tablero quedaron viejos. Antes esto se hacía recargando a mano en
 * cada pantalla y era la fuente habitual de «la pantalla no se actualizó».
 *
 *     const llamar = useAccion((caso) => api.post(`/casos/${caso}/llamar/`, {…}))
 *     llamar.mutate(id, { onSuccess: … })
 */
export function useAccion(fn, { invalida = ["lista"], ...opciones } = {}) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    ...opciones,
    onSuccess: (...args) => {
      for (const clave of invalida) qc.invalidateQueries({ queryKey: [clave] });
      return opciones.onSuccess?.(...args);
    },
  });
}
