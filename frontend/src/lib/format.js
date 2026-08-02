// Formato de fecha/hora estilo expediente: "24/06/2026 · 14:30".
export function fechaHora(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d)) return iso;
  const p = (n) => String(n).padStart(2, "0");
  return `${p(d.getDate())}/${p(d.getMonth() + 1)}/${d.getFullYear()} · ${p(d.getHours())}:${p(d.getMinutes())}`;
}

export function casoId(id) {
  return "#" + String(id).padStart(4, "0");
}

/**
 * Concuerda el número con su sustantivo: «1 caso activo», «3 casos activos».
 *
 * Con datos de demo el singular casi no aparece y es fácil no verlo; con datos
 * reales de una institución chica salta enseguida y queda desprolijo.
 *
 *     plural(n, "caso activo", "casos activos")
 */
export function plural(n, singular, plural) {
  return `${n} ${n === 1 ? singular : plural}`;
}

// Antigüedad relativa compacta: "5 min", "17 h", "3 d".
export function antiguedad(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d)) return "—";
  const min = Math.max(0, Math.floor((Date.now() - d.getTime()) / 60000));
  if (min < 60) return `${min} min`;
  const h = Math.floor(min / 60);
  if (h < 48) return `${h} h`;
  return `${Math.floor(h / 24)} d`;
}
