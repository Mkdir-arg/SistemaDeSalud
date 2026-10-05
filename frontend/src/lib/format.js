// Una fecha de calendario no es un instante UTC: conservar el día recibido.
export function fechaCalendario(valor) {
  const m = String(valor || "").match(/^(\d{4})-(\d{2})-(\d{2})$/);
  return m ? `${m[3]}/${m[2]}/${m[1]}` : valor || "—";
}

export function periodoCalendario(valor) {
  const m = String(valor || "").match(/^(\d{4})-(\d{2})$/);
  return m ? new Date(Number(m[1]), Number(m[2]) - 1, 1).toLocaleDateString("es-AR", { month: "long", year: "numeric" }) : valor || "—";
}

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

// Una duración recibida en minutos, separada de la antigüedad de una fecha.
export function duracionMinutos(valor) {
  if (valor == null || valor === "") return "—";
  const exacto = Number(valor);
  if (!Number.isFinite(exacto) || exacto < 0) return "—";
  // Se redondea ANTES de partir en horas: si no, 119,6 min salía «1 h 60 min».
  const minutos = Math.round(exacto);
  if (minutos < 60) return `${minutos} min`;
  // Sin el resto en cero: «2 h», no «2 h 0 min».
  if (minutos < 2880) return `${Math.floor(minutos / 60)} h${minutos % 60 ? ` ${minutos % 60} min` : ""}`;
  const horas = Math.floor(minutos % 1440 / 60);
  return `${Math.floor(minutos / 1440)} d${horas ? ` ${horas} h` : ""}`;
}
