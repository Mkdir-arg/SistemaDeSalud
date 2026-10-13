export function cambiosPadron(campos, inicial, datos) {
  const cambios = {};
  for (const campo of campos) {
    const previo = inicial[campo.name] ?? (campo.boolean ? false : "");
    const actual = datos[campo.name] ?? (campo.boolean ? false : "");
    if (String(actual) === String(previo)) continue;
    cambios[campo.name] = campo.tristate ? (actual === "" ? null : actual === "true" || actual === true)
      : campo.nullable && actual === "" ? null
      : campo.boolean ? Boolean(actual)
      : campo.numeric ? (actual === "" ? null : Number(actual))
        : actual;
  }
  return cambios;
}

export function errorCampoPadron(error, campo) {
  const valor = error?.data?.[campo];
  return Array.isArray(valor) ? valor.join(" ") : typeof valor === "string" ? valor : undefined;
}

export function estadoVencimiento(fecha, hoy = new Date().toLocaleDateString("en-CA", { timeZone: "America/Argentina/Buenos_Aires" })) {
  return !fecha ? "Sin vencimiento informado" : fecha < hoy ? "Vencido" : fecha === hoy ? "Vence hoy" : "Vigente por fecha";
}
