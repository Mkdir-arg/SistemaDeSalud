// Cómo se muestran los datos del portal (#122). Todo sale de `/api/mi/*`: acá
// sólo se formatea. Las reglas (qué se puede confirmar o cancelar) las decide el
// backend y llegan en cada turno.

import { guardarArchivo } from "@/api/portal";

const ZONA = "America/Argentina/Buenos_Aires";

const en = (iso, opciones) => new Date(iso).toLocaleString("es-AR", { timeZone: ZONA, ...opciones });

export const hora = (iso) => en(iso, { hour: "2-digit", minute: "2-digit", hour12: false });
/** «martes 14 de octubre». */
export const fechaLarga = (iso) => en(iso, { weekday: "long", day: "numeric", month: "long" });
/** Lo de arriba de la caja de un turno: «Hoy» o «mar 30» (en mayúsculas por CSS). */
export const diaDeLaCaja = (iso) => (esHoy(iso) ? "Hoy" : `${en(iso, { weekday: "short" }).replace(".", "").slice(0, 3)} ${en(iso, { day: "numeric" })}`);
const diaDe = (iso) => en(iso, { year: "numeric", month: "2-digit", day: "2-digit" });
export const esHoy = (iso) => diaDe(iso) === diaDe(new Date().toISOString());

// Una fecha de calendario (`AAAA-MM-DD`) con otro formato; si no tiene esa forma, tal cual.
const conFormato = (formato) => (fecha) => {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(fecha || "");
  return m ? formato(m[1], m[2], m[3]) : fecha || "";
};
/** «dd/mm». */
export const diaMes = conFormato((anio, mes, dia) => `${dia}/${mes}`);
/** «dd/mm/aaaa». */
export const diaMesAnio = conFormato((anio, mes, dia) => `${dia}/${mes}/${anio}`);

export const primerNombre = (nombre = "") => nombre.trim().split(/\s+/)[0] || "";

// Lo que todavía puede pasar con un turno, y lo que ya pasó.
export const VIGENTES = new Set(["reservado", "confirmado", "presente"]);
export const esProximo = (t) => VIGENTES.has(t.estado) && new Date(t.fin || t.inicio) > new Date();

/** Etiqueta y tono de la insignia de estado. El texto es el del backend. */
export function estadoTurno(t) {
  const tono = {
    reservado: "ambar", confirmado: "verde", presente: "acento",
    realizado: "gris", ausente: "gris", cancelado: "rojo",
  }[t.estado] || "gris";
  if (t.estado === "confirmado" && t.confirmado_via === "portal") return ["Confirmaste tu asistencia", tono];
  if (t.estado === "cancelado" && t.cancelado_via === "portal") return ["Lo cancelaste", tono];
  return [t.estado_display, tono];
}

/** Qué es el turno: la especialidad (el área) o, si no tiene, el nombre de la agenda. */
export const tituloTurno = (t) => t.area || t.agenda;
/** Quién atiende y dónde, en una línea: «Laura Méndez · Hospital Central». */
export const quienYDonde = (t) => [t.profesional || (t.area ? t.agenda : null), t.institucion?.nombre].filter(Boolean).join(" · ");

const sinAcentos = (s) => s.normalize("NFD").replace(/[̀-ͯ]/g, "");
const fechaIcs = (iso) => new Date(iso).toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, "");
const textoIcs = (s = "") => s.replace(/\\/g, "\\\\").replace(/([,;])/g, "\\$1").replace(/\n/g, "\\n");

/** El turno como evento de calendario (.ics), con aviso 2 horas antes. */
export function eventoIcs(t) {
  const lugar = [t.institucion?.nombre, t.area].filter(Boolean).join(", ");
  return [
    "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//HEN//Portal del paciente//ES",
    "BEGIN:VEVENT", `UID:turno-${t.id}@hen`,
    `DTSTAMP:${fechaIcs(new Date().toISOString())}`,
    `DTSTART:${fechaIcs(t.inicio)}`, `DTEND:${fechaIcs(t.fin || t.inicio)}`,
    `SUMMARY:${textoIcs(`Turno · ${tituloTurno(t)}`)}`,
    `LOCATION:${textoIcs(t.modalidad === "virtual" && t.enlace ? t.enlace : lugar)}`,
    `DESCRIPTION:${textoIcs(quienYDonde(t))}`,
    "BEGIN:VALARM", "ACTION:DISPLAY", `DESCRIPTION:${textoIcs(`Turno en ${t.institucion?.nombre || "tu institución"}`)}`, "TRIGGER:-PT2H", "END:VALARM",
    "END:VEVENT", "END:VCALENDAR",
  ].join("\r\n");
}

export function agregarAlCalendario(t) {
  const nombre = `turno-${sinAcentos(tituloTurno(t)).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "")}-${diaDe(t.inicio).split("/").reverse().join("-")}.ics`;
  guardarArchivo(new Blob([eventoIcs(t)], { type: "text/calendar;charset=utf-8" }), nombre);
}
