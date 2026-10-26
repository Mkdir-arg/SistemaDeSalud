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
    tipos: ["padron"], modo: "administrativa",
    descripcion: "Hojas Hoja1 y afimotook, con las 39 columnas OSTEL o con CUILTIT como columna 40. CUIL y NUMERO identifican individualmente; NROAFI puede compartirse. TIPO distingue activo/pasivo, no vigencia de cobertura. FECVTO no equivale a baja. CUILTIT se conserva como evidencia, pero todavía no se vinculan familias. El importador no interpreta códigos pendientes ni aplica movimientos de baja.",
    aviso: "La habilitación para personas nuevas se elige al cargar. En personas existentes se conserva la habilitación actual y las diferencias requieren revisión. Las reglas de prestaciones siguen pendientes de OSTEL.",
    recursoRevision: "previsualizar-ostel",
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
