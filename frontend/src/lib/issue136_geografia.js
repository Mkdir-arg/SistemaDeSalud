export const NIVELES_GEO = ["provincia", "partido", "localidad"];
export const nombreGeo = (valor) => valor?.manual ?? valor?.nombre ?? "";
export const origenGeo = (valor) => valor?.pendiente ? "Revisar selección" : valor?.manual != null || valor?.origen === "manual" ? "Manual · sin verificar" : valor?.origen === "georef" ? "Georef" : nombreGeo(valor) ? "Sin homologar" : "Sin informar";
export const hayGeoPendiente = (geo) => NIVELES_GEO.some((n) => geo?.[n]?.pendiente);

export function geografiaInicial(geo, textos = {}) {
  return Object.fromEntries(NIVELES_GEO.map((n) => [n, geo?.[n] || (textos[n] ? { nombre: textos[n], origen: "legado" } : null)]));
}

export function cambiarGeo(geo, nivel, valor) {
  const nuevo = { ...geo, [nivel]: valor };
  for (const descendiente of NIVELES_GEO.slice(NIVELES_GEO.indexOf(nivel) + 1)) {
    const nombre = nombreGeo(nuevo[descendiente]);
    nuevo[descendiente] = nombre ? { nombre, pendiente: true } : null;
  }
  return nuevo;
}

export function cuerpoGeo(geo) {
  return Object.fromEntries(NIVELES_GEO.map((n) => {
    const v = geo?.[n];
    return [n, !v ? null : v.pendiente ? { pendiente: true } : v.id ? { id: v.id }
      : v.manual != null ? { manual: v.manual } : { nombre: v.nombre || "", origen: "legado" }];
  }));
}

export function descripcionGeo(geo) {
  return NIVELES_GEO.map((n) => geo?.[n]?.nombre ? `${geo[n].nombre} (${origenGeo(geo[n])})` : "").filter(Boolean).join(" · ");
}
