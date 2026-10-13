// Borrador del alta de afiliación: uno por usuario y financiador, en este navegador.
// Contiene datos personales (DNI, CUIL, domicilio): se borra al registrar, al
// descartar y al cerrar sesión explícitamente.
const PREFIJO = "salud.alta-afiliado.";

const clave = (usuarioId, financiadorId) => `${PREFIJO}${usuarioId}.${financiadorId}`;

export function leerBorradorAlta(usuarioId, financiadorId) {
  try { return JSON.parse(localStorage.getItem(clave(usuarioId, financiadorId)) || "null"); }
  catch { return null; }
}

export function guardarBorradorAlta(usuarioId, financiadorId, borrador) {
  try { localStorage.setItem(clave(usuarioId, financiadorId), JSON.stringify({ ...borrador, guardado: new Date().toISOString() })); }
  catch { /* Sin espacio o almacenamiento bloqueado: el alta sigue funcionando sin borrador. */ }
}

export function borrarBorradorAlta(usuarioId, financiadorId) {
  try { localStorage.removeItem(clave(usuarioId, financiadorId)); }
  catch { /* idem */ }
}

export function borrarBorradoresAlta() {
  try { Object.keys(localStorage).filter((k) => k.startsWith(PREFIJO)).forEach((k) => localStorage.removeItem(k)); }
  catch { /* idem */ }
}
