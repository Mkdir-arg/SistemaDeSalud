export function normalizarDocumento(valor) {
  return String(valor || "").replace(/[^0-9A-Za-z]/g, "").toUpperCase();
}

export function precargarPaciente(texto) {
  const valor = String(texto || "").trim();
  const esDni = /^[0-9][0-9.\s-]*$/.test(valor);
  const esDocumentoAlfanumerico = /^(?=.*[A-Za-z])(?=.*[0-9])[A-Za-z0-9.-]+$/.test(valor);
  if (esDni || esDocumentoAlfanumerico) {
    return { nombre: "", apellido: "", documento: valor };
  }

  const [nombre = "", ...apellido] = valor.split(/\s+/);
  return { nombre, apellido: apellido.join(" "), documento: "" };
}

export function busquedaPaciente(texto) {
  const valor = String(texto || "").trim();
  return precargarPaciente(valor).documento ? normalizarDocumento(valor) : valor;
}
