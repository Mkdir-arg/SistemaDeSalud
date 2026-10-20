// Los enlaces institucionales sólo transportan credenciales en el fragmento.
// No guardar este resultado en storage, cache de consultas ni estado del router.
export function leerCredencialesFragmento(fragmento) {
  const parametros = new URLSearchParams((fragmento || "").replace(/^#/, ""));
  return {
    uid: parametros.get("uid") || "",
    token: parametros.get("token") || "",
    nuevo_email: parametros.get("nuevo_email") || "",
  };
}

export function limpiarFragmentoCredenciales(ubicacion, historial) {
  if (ubicacion.hash) {
    historial.replaceState(historial.state, "", `${ubicacion.pathname}${ubicacion.search}`);
  }
}
