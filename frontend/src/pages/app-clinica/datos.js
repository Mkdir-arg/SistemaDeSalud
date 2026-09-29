// Datos ficticios de la app clínica de demostración. No hay API detrás: todo lo
// que la persona "reserva" vive en la pestaña (ver `estado.jsx`).

const direccion = "Av. Rivadavia 4800, Caballito, CABA";

export const CLINICA = {
  nombre: "Clínica Modelo",
  direccion,
  mapa: `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(`${direccion}, Argentina`)}`,
  telefonos: [
    { titulo: "Turnos y consultas", texto: "011 4555-0000", tel: "+541145550000" },
    { titulo: "Guardia", texto: "011 4555-0911", tel: "+541145550911" },
  ],
  horarios: [
    { titulo: "Consultorios", detalle: "Lunes a viernes, 8 a 20 h · sábados, 8 a 13 h" },
    { titulo: "Guardia", detalle: "Todos los días, las 24 h" },
    { titulo: "Laboratorio (extracciones)", detalle: "Lunes a sábado, 7 a 10 h, sin turno" },
  ],
};

export const PROFESIONALES = [
  { id: "paula-rios", nombre: "Dra. Paula Ríos", especialidad: "Clínica médica", consultorio: "4", turno: "mañana" },
  { id: "hernan-ruiz", nombre: "Dr. Hernán Ruiz", especialidad: "Clínica médica", consultorio: "6", turno: "tarde" },
  { id: "laura-molina", nombre: "Dra. Laura Molina", especialidad: "Pediatría", consultorio: "2", turno: "mañana" },
  { id: "tomas-gil", nombre: "Dr. Tomás Gil", especialidad: "Pediatría", consultorio: "3", turno: "tarde" },
  { id: "martin-diaz", nombre: "Dr. Martín Díaz", especialidad: "Cardiología", consultorio: "8", turno: "mañana" },
  { id: "carla-vega", nombre: "Dra. Carla Vega", especialidad: "Cardiología", consultorio: "8", turno: "tarde" },
  { id: "julia-perez", nombre: "Dra. Julia Pérez", especialidad: "Ginecología", consultorio: "5", turno: "mañana" },
  { id: "ana-ledesma", nombre: "Dra. Ana Ledesma", especialidad: "Ginecología", consultorio: "5", turno: "tarde" },
  { id: "diego-rivas", nombre: "Dr. Diego Rivas", especialidad: "Traumatología", consultorio: "10", turno: "mañana" },
  { id: "sofia-gomez", nombre: "Dra. Sofía Gómez", especialidad: "Traumatología", consultorio: "10", turno: "tarde" },
];

export const ESPECIALIDADES = [...new Set(PROFESIONALES.map((p) => p.especialidad))];
export const profesional = (id) => PROFESIONALES.find((p) => p.id === id);
export const profesionalesDe = (especialidad) => PROFESIONALES.filter((p) => p.especialidad === especialidad);

// `copago: null` es consulta particular: se paga el valor completo.
export const COBERTURAS = [
  { id: "osde", nombre: "OSDE 210", copago: 3500 },
  { id: "swiss", nombre: "Swiss Medical SMG20", copago: 0 },
  { id: "pami", nombre: "PAMI", copago: 0 },
  { id: "particular", nombre: "Sin cobertura (particular)", copago: null },
];
export const VALOR_CONSULTA = 32000;
export const cobertura = (id) => COBERTURAS.find((c) => c.id === id) || COBERTURAS.at(-1);

export const pesos = (n) => new Intl.NumberFormat("es-AR", { style: "currency", currency: "ARS", maximumFractionDigits: 0 }).format(n);

/** Lo que paga la persona en la caja de la clínica, según su cobertura. */
export function aPagar(coberturaId) {
  const c = cobertura(coberturaId);
  if (c.copago === null) return { monto: VALOR_CONSULTA, detalle: "Valor de la consulta particular" };
  if (c.copago === 0) return { monto: 0, detalle: `Sin cargo con ${c.nombre}` };
  return { monto: c.copago, detalle: `Copago de ${c.nombre}` };
}

// ── Fechas ────────────────────────────────────────────────────────────────────
// Los días se guardan como "AAAA-MM-DD" en hora local: comparar y persistir
// cadenas evita los corrimientos de zona horaria de `toISOString`.

export const claveDia = (fecha) => `${fecha.getFullYear()}-${String(fecha.getMonth() + 1).padStart(2, "0")}-${String(fecha.getDate()).padStart(2, "0")}`;
export const hoy = () => claveDia(new Date());
const aFecha = (dia) => new Date(`${dia}T12:00:00`);
export const diaRelativo = (dias) => { const f = new Date(); f.setDate(f.getDate() + dias); return claveDia(f); };

export function fechaLarga(dia) {
  if (dia === hoy()) return "Hoy";
  if (dia === diaRelativo(1)) return "Mañana";
  const texto = aFecha(dia).toLocaleDateString("es-AR", { weekday: "long", day: "numeric", month: "long" });
  return texto.charAt(0).toUpperCase() + texto.slice(1);
}
export const fechaCorta = (dia) => aFecha(dia).toLocaleDateString("es-AR", { day: "2-digit", month: "2-digit" });
export const fechaConAnio = (dia) => aFecha(dia).toLocaleDateString("es-AR", { day: "numeric", month: "long", year: "numeric" });
export const diaSemana = (dia) => aFecha(dia).toLocaleDateString("es-AR", { weekday: "short" }).replace(".", "").toUpperCase();
export const numeroDia = (dia) => aFecha(dia).getDate();

/** Hoy y los próximos cinco días hábiles. */
export function diasDisponibles() {
  const dias = [hoy()];
  for (let i = 1; dias.length < 6; i++) {
    const f = new Date();
    f.setDate(f.getDate() + i);
    if (f.getDay() !== 0 && f.getDay() !== 6) dias.push(claveDia(f));
  }
  return dias;
}

const aMinutos = (hora) => { const [h, m] = hora.split(":").map(Number); return h * 60 + m; };
const aHora = (min) => `${String(Math.floor(min / 60)).padStart(2, "0")}:${String(min % 60).padStart(2, "0")}`;
const BASE = { mañana: ["09:00", "09:20", "10:40", "11:40", "12:00", "12:40"], tarde: ["15:00", "15:20", "16:40", "17:00", "18:20", "19:00"] };

/**
 * Horarios libres de un profesional en un día. Son determinísticos (el mismo
 * día muestra siempre los mismos) y hoy solo se ofrecen los que todavía no
 * pasaron, con media hora de margen para llegar.
 */
export function horariosLibres(profesionalId, dia) {
  const p = profesional(profesionalId);
  if (!p) return [];
  if (dia === hoy()) return horariosDeHoy(30, PROFESIONALES.indexOf(p) % 2 ? [20, 60, 100] : [0, 40, 60]);
  const semilla = [...`${profesionalId}${dia}`].reduce((s, c) => s + c.charCodeAt(0), 0);
  return BASE[p.turno].filter((_, i) => (semilla + i) % 3 !== 0);
}

/** Horarios de hoy desde `margen` minutos en adelante (redondeado a 20), corridos `extras` minutos. */
export function horariosDeHoy(margen = 30, extras = [0, 20, 60]) {
  const ahora = new Date();
  const desde = Math.ceil((ahora.getHours() * 60 + ahora.getMinutes() + margen) / 20) * 20;
  return extras.map((extra) => desde + extra).filter((m) => m <= aMinutos("23:40")).map(aHora);
}

// ── Paciente conocida ────────────────────────────────────────────────────────
// Con este DNI la clínica "ya la conoce": entra directo con historia, un turno
// para hoy y resultados. Cualquier otro DNI recorre el alta de primera vez.

export const DNI_CONOCIDO = "34521521";

export function pacienteConocida() {
  return {
    dni: DNI_CONOCIDO,
    nombre: "Martina Sosa",
    nacimiento: "1989-04-12",
    celular: "11 5555-4521",
    cobertura: "osde",
    credencial: "61 234567 8 01",
    desde: "2019",
  };
}

let secuencia = 0;
export const nuevoId = (prefijo) => `${prefijo}-${Date.now().toString(36)}${(secuencia++).toString(36)}`;

export function turno(profesionalId, dia, hora, extra = {}) {
  const p = profesional(profesionalId);
  return { id: nuevoId("t"), profesionalId, especialidad: p.especialidad, profesional: p.nombre, consultorio: p.consultorio, dia, hora, estado: "confirmado", recordatorio: true, ...extra };
}

export function historiaConocida() {
  // Si ya es muy tarde para un turno hoy, el control queda para mañana.
  const [horaHoy] = horariosDeHoy(45);
  const turnos = [
    turno("paula-rios", horaHoy ? hoy() : diaRelativo(1), horaHoy || "09:20", { motivo: "Control con resultados de laboratorio" }),
    turno("paula-rios", diaRelativo(-45), "10:20", { estado: "atendido" }),
    turno("martin-diaz", diaRelativo(-30), "11:40", { estado: "atendido" }),
    turno("diego-rivas", diaRelativo(-12), "16:40", { estado: "cancelado" }),
  ];
  const resultados = [
    {
      id: "laboratorio", titulo: "Análisis de sangre completo", area: "Laboratorio", dia: diaRelativo(-5), estado: "listo", nuevo: true,
      pedidoPor: "Dra. Paula Ríos",
      aviso: "2 valores fuera del rango de referencia. Los vas a revisar con tu médica en el próximo control.",
      valores: [
        { nombre: "Glucemia", valor: "126 mg/dl", referencia: "70 a 110 mg/dl", fuera: true },
        { nombre: "Colesterol total", valor: "238 mg/dl", referencia: "Menor a 200 mg/dl", fuera: true },
        { nombre: "Colesterol HDL", valor: "52 mg/dl", referencia: "Mayor a 40 mg/dl" },
        { nombre: "Triglicéridos", valor: "140 mg/dl", referencia: "Menor a 150 mg/dl" },
        { nombre: "Hemoglobina", valor: "13,8 g/dl", referencia: "12 a 16 g/dl" },
        { nombre: "Leucocitos", valor: "6.800 /mm³", referencia: "4.500 a 11.000 /mm³" },
      ],
    },
    {
      id: "ecocardiograma", titulo: "Ecocardiograma", area: "Cardiología", dia: diaRelativo(-2), estado: "en-proceso",
      pedidoPor: "Dr. Martín Díaz",
    },
    {
      id: "radiografia-torax", titulo: "Radiografía de tórax", area: "Diagnóstico por imágenes", dia: diaRelativo(-44), estado: "listo",
      pedidoPor: "Dra. Paula Ríos",
      informe: "Campos pulmonares sin infiltrados ni consolidaciones. Senos costofrénicos libres. Silueta cardíaca de tamaño normal. Sin hallazgos patológicos.",
    },
  ];
  return { turnos, resultados };
}
