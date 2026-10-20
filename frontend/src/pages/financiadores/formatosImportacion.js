// Registro extensible: las opciones se filtran por tipo de carga y los flujos
// se eligen por capacidad, nunca por nombre de obra social.
export const FORMATOS_IMPORTACION = Object.freeze([
  Object.freeze({
    id: "sistema", nombre: "Plantilla del sistema (predeterminada)",
    tipos: ["padron", "consumos"], modo: "importacion",
    recursoRevision: "importaciones", recursoConfirmacion: "confirmar-importacion",
    recursoRechazos: "rechazos",
    parametrosPlantilla: (tipo) => ({ tipo, ...(tipo === "padron" ? { version: "2" } : {}) }),
    nombrePlantilla: (tipo) => `plantilla-${tipo}.xlsx`,
  }),
  Object.freeze({
    id: "ostel", nombre: "OSTEL",
    tipos: ["padron"], modo: "revision",
    descripcion: "Hojas Hoja1 y afimotook, con las 39 columnas OSTEL.",
    aviso: "Por ahora podés revisar el archivo, pero no importar afiliados. Falta confirmar con OSTEL cómo interpretar sus campos y códigos.",
    recursoRevision: "prevalidar-ostel",
    parametrosPlantilla: (tipo) => ({ tipo, formato: "ostel" }),
    nombrePlantilla: () => "plantilla-ostel.xlsx",
    maxBytes: 5 * 1024 * 1024,
  }),
]);

export const formatosPara = (tipo, registro = FORMATOS_IMPORTACION) => registro.filter((formato) => formato.tipos.includes(tipo));
const clavePreferencia = (usuarioId, tipo) => `salud.formato-importacion.v1:${usuarioId}:${tipo}`;

export function leerFormatoPreferido(usuarioId, tipo, opciones, almacenamiento) {
  const predeterminado = opciones[0].id;
  if (usuarioId == null) return { id: predeterminado, persistencia: false };
  try {
    const id = (almacenamiento ?? globalThis.localStorage).getItem(clavePreferencia(usuarioId, tipo));
    return { id: opciones.some((formato) => formato.id === id) ? id : predeterminado, persistencia: true };
  } catch {
    return { id: predeterminado, persistencia: false };
  }
}

export function guardarFormatoPreferido(usuarioId, tipo, id, almacenamiento) {
  if (usuarioId == null) return false;
  try {
    (almacenamiento ?? globalThis.localStorage).setItem(clavePreferencia(usuarioId, tipo), id);
    return true;
  } catch {
    return false;
  }
}
