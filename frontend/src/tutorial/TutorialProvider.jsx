import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { api } from "@/api/client";
import { useAuth } from "@/auth/AuthContext";
import { useInstitucion } from "@/auth/InstitutionContext";
import { Button } from "@/components/ui";
import { Icon } from "@/components/icons";
import { cn } from "@/lib/cn";

const TutorialContext = createContext(null);
const ESCUELA_NOMBRE = "Hospital Escuela Cauce";
const ESCUELA_TAG = "[escuela-cauce]";

const DEMO_STEPS = [
  {
    route: "/inicio",
    target: '[data-tour="inicio-institucion"]',
    prepare: "institucion",
    title: "Modo escuela: sistema desde cero",
    body: "Creamos una institucion de capacitacion separada: Hospital Escuela Cauce. La vamos a poblar paso a paso, como si estuvieras implementando el sistema desde el primer dia.",
    actions: ["Crear Hospital Escuela Cauce", "Entrar al contexto de capacitacion", "Preparar el recorrido guiado"],
  },
  {
    route: "/estructura",
    target: '[data-tour="menu-estructura"]',
    actorTarget: '[data-tour="estructura-nueva-area"], [data-tour="estructura-nueva-area-vacia"]',
    actorScript: "area",
    prepare: "areas",
    title: "Estructura organizativa",
    body: "Primero cargamos las areas reales de trabajo: Guardia, Laboratorio, Imagenes, Internacion y Farmacia. Sin estructura no hay roles, colas ni circuitos operables.",
    actions: ["Tocar Nueva area", "Escribir Guardia escuela", "Guardar area Guardia", "Repetir con Laboratorio e Imagenes", "Repetir con Internacion y Farmacia"],
    demoFormTitle: "Nueva area",
    demoSubmitLabel: "Guardar area",
    demoEntries: [
      ["Area", "Guardia escuela"],
      ["Area", "Laboratorio escuela"],
      ["Area", "Imagenes escuela"],
      ["Area", "Internacion escuela"],
      ["Area", "Farmacia escuela"],
    ],
  },
  {
    route: "/administracion",
    target: '[data-tour="menu-administracion"]',
    prepare: "usuarios",
    title: "Usuarios y accesos",
    body: "Ahora creamos usuarios de entrenamiento y les asignamos roles: administrativo, enfermeria, medico y jefe de area. Cada rol habilita una parte distinta del sistema.",
    actions: ["Crear usuarios escuela", "Asignar roles por institucion", "Acotar permisos al area Guardia", "Crear grupos de Admision, Triage y Medicos"],
    demoFormTitle: "Nuevo usuario",
    demoSubmitLabel: "Cargar usuario",
    demoEntries: [
      ["Usuario", "escuela.adm@cauce.local"],
      ["Rol", "Administrativo en Guardia"],
      ["Usuario", "escuela.enf@cauce.local"],
      ["Rol", "Enfermeria en Guardia"],
      ["Usuario", "escuela.med@cauce.local"],
      ["Rol", "Medico en Guardia"],
    ],
  },
  {
    route: "/flujos",
    target: '[data-tour="menu-flujos"]',
    prepare: "flujo",
    title: "Diseno de procesos",
    body: "Construimos un flujo de guardia publicable: admision administrativa, triage, espera de fila, atencion medica y cierre. Es simple, pero ya usa responsabilidades reales.",
    actions: ["Crear flujo Guardia escuela", "Agregar nodos de admision y triage", "Conectar sala de espera y atencion", "Publicar version v1"],
    demoEntries: [
      ["Flujo", "Guardia escuela"],
      ["Nodo", "Admision administrativa"],
      ["Nodo", "Triage de enfermeria"],
      ["Nodo", "Atencion medica"],
      ["Version", "Publicada v1"],
    ],
  },
  {
    route: "/formularios",
    target: '[data-tour="menu-formularios"]',
    prepare: "formularios",
    title: "Formularios clinicos y operativos",
    body: "El escenario crea formularios para admision y triage: motivo de consulta, cobertura, dolor, temperatura, presion y prioridad.",
    actions: ["Crear formulario de admision", "Agregar motivo y cobertura", "Crear formulario de triage", "Agregar dolor, temperatura y prioridad"],
    demoEntries: [
      ["Formulario", "Admision escuela"],
      ["Campo", "Motivo de consulta"],
      ["Campo", "Cobertura"],
      ["Formulario", "Triage escuela"],
      ["Campo", "Prioridad"],
    ],
  },
  {
    route: "/agenda",
    target: '[data-tour="menu-agenda"]',
    prepare: "agenda",
    title: "Turnos programados",
    body: "Despues cargamos una agenda de consultorio, horarios semanales y turnos de ejemplo. Al registrar llegada, esa agenda abre el flujo de guardia.",
    actions: ["Crear agenda Consultorio escuela", "Asignar profesional y flujo", "Cargar franja de atencion", "Reservar un turno de ejemplo"],
    demoEntries: [
      ["Agenda", "Consultorio escuela"],
      ["Profesional", "Santiago Vera"],
      ["Horario", "08:00 a 12:00"],
      ["Turno", "Ana Escuela"],
    ],
  },
  {
    route: "/inicio",
    target: '[data-tour="inicio-operar"]',
    prepare: "casos",
    title: "Mi trabajo",
    body: "Ahora generamos pacientes y casos de practica. La pantalla de trabajo deja de estar vacia: hay tareas reales para admitir, hacer triage y atender.",
    actions: ["Crear pacientes de practica", "Abrir un caso de guardia", "Iniciar el recorrido del caso", "Dejar tareas listas para operar"],
    demoEntries: [
      ["Paciente", "Ana Escuela"],
      ["Paciente", "Luis Simulado"],
      ["Caso", "Guardia escuela"],
      ["Paso actual", "Admision administrativa"],
    ],
  },
  {
    route: "/internacion",
    target: '[data-tour="menu-internacion"]',
    title: "Internacion",
    body: "Internacion muestra camas, estadias y disponibilidad. Sirve para seguir ocupacion y movimientos del paciente dentro del hospital.",
  },
  {
    route: "/farmacia",
    target: '[data-tour="menu-farmacia"]',
    title: "Farmacia e insumos",
    body: "Farmacia permite consultar stock, lotes, depositos, pedidos y movimientos. Es el modulo operativo de insumos.",
  },
  {
    route: "/red",
    target: '[data-tour="menu-red"]',
    title: "Red y traslados",
    body: "Red coordina traslados entre establecimientos: solicitud, respuesta, viaje, recepcion y seguimiento de demoras.",
  },
  {
    route: "/historia",
    target: '[data-tour="menu-historia"]',
    title: "Historia clinica",
    body: "Aca se busca el paciente y se consulta su historia: atenciones, estudios, recetas y eventos clinicos registrados.",
  },
  {
    route: "/legajo",
    target: '[data-tour="menu-legajo"]',
    title: "Legajo profesional",
    body: "El legajo concentra la informacion profesional del usuario y su trazabilidad dentro de la institucion.",
  },
  {
    route: "/dashboard",
    target: '[data-tour="menu-dashboard"]',
    title: "Tablero",
    body: "El tablero es para jefatura y administracion: volumen de casos, demoras, ausentismo de turnos, saturacion y salud de procesos.",
  },
  {
    route: "/supervision",
    target: '[data-tour="menu-supervision"]',
    title: "Supervision",
    body: "Supervision permite mirar el trabajo del area, detectar demoras y ordenar la operacion sin entrar caso por caso.",
  },
  {
    route: "/accesos",
    target: '[data-tour="menu-accesos"]',
    title: "Auditoria",
    body: "El registro de accesos muestra quien consulto datos clinicos. Es la contracara necesaria de una historia clinica seria.",
  },
];

function clamp(n, min, max) {
  return Math.max(min, Math.min(max, n));
}

function puedeNarrar() {
  return typeof window !== "undefined" && "speechSynthesis" in window && "SpeechSynthesisUtterance" in window;
}

function textoNarracion(step, error) {
  if (error) return error;
  return `${step?.title || "Recorrido guiado"}. ${step?.body || ""}`;
}

const sleep = (ms) => new Promise((resolve) => window.setTimeout(resolve, ms));

async function lista(recurso, params = {}) {
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") qs.set(k, v);
  });
  const d = await api.get(`/${recurso}/${qs.toString() ? `?${qs}` : ""}`);
  return d.results || d;
}

async function primero(recurso, params) {
  return (await lista(recurso, { ...params, page_size: 50 }))[0] || null;
}

async function crearSiFalta(recurso, buscarParams, payload) {
  const existe = await primero(recurso, buscarParams);
  if (existe) return existe;
  return api.post(`/${recurso}/`, payload);
}

async function crearPorCampoExacto(recurso, params, campo, valor, payload) {
  const existentes = await lista(recurso, { ...params, page_size: 200 });
  const existe = existentes.find((x) => String(x[campo] || "").toLowerCase() === String(valor).toLowerCase());
  if (existe) return existe;
  return api.post(`/${recurso}/`, payload);
}

async function contextoEscuela() {
  const inst = await crearSiFalta(
    "instituciones",
    { search: ESCUELA_NOMBRE },
    {
      nombre: ESCUELA_NOMBRE,
      tipo: "Hospital general de capacitacion",
      cuit: "30-00000000-7",
      estado: "en_alta",
    },
  );
  return { inst };
}

async function prepararAreas(ctx) {
  const area = async (nombre, responsable, descripcion = "") =>
    crearPorCampoExacto("areas", { institucion: ctx.inst.id }, "nombre", nombre, {
      institucion: ctx.inst.id,
      nombre,
      responsable,
      descripcion: `${ESCUELA_TAG} ${descripcion}`.trim(),
      activa: true,
    });

  const guardia = await area("Guardia escuela", "Jefatura de guardia", "Puerta de entrada de urgencias y demanda espontanea.");
  const laboratorio = await area("Laboratorio escuela", "Bioquimica de guardia", "Procesa estudios solicitados desde guardia.");
  const imagenes = await area("Imagenes escuela", "Diagnostico por imagenes", "Radiologia y ecografia de entrenamiento.");
  const internacion = await area("Internacion escuela", "Coordinacion de camas", "Camas para observar el pase desde guardia.");
  const farmacia = await area("Farmacia escuela", "Deposito central", "Stock inicial para capacitacion.");
  return { ...ctx, areas: { guardia, laboratorio, imagenes, internacion, farmacia } };
}

async function prepararUsuarios(ctx) {
  const usuario = async (email, nombre, apellido) =>
    crearPorCampoExacto("usuarios", { search: email }, "email", email, {
      email, nombre, apellido, password: "demo1234", is_active: true,
    });
  const membresia = async (u, rol, areas = []) => {
    const m = await primero("membresias", { usuario: u.id, institucion: ctx.inst.id, rol });
    if (m) return m;
    return api.post("/membresias/", {
      usuario: u.id,
      institucion: ctx.inst.id,
      rol,
      areas: areas.map((a) => a.id),
      activo: true,
    });
  };

  const jefe = await usuario("escuela.jefe@cauce.local", "Julia", "Molina");
  const adm = await usuario("escuela.adm@cauce.local", "Rafael", "Paz");
  const enf = await usuario("escuela.enf@cauce.local", "Camila", "Rojas");
  const med = await usuario("escuela.med@cauce.local", "Santiago", "Vera");
  await membresia(jefe, "jefe_area", [ctx.areas.guardia]);
  await membresia(adm, "administrativo", [ctx.areas.guardia]);
  await membresia(enf, "enfermeria", [ctx.areas.guardia]);
  await membresia(med, "medico", [ctx.areas.guardia]);

  const grupo = async (nombre, descripcion, miembros) =>
    crearPorCampoExacto("grupos", { area: ctx.areas.guardia.id }, "nombre", nombre, {
      area: ctx.areas.guardia.id,
      nombre,
      descripcion: `${ESCUELA_TAG} ${descripcion}`,
      miembros: miembros.map((u) => u.id),
      activo: true,
    });
  const admision = await grupo("Admision escuela", "Mostrador de ingreso de pacientes.", [adm]);
  const triage = await grupo("Triage escuela", "Enfermeria que clasifica prioridad.", [enf]);
  const medicos = await grupo("Medicos guardia escuela", "Profesionales que firman atenciones.", [med]);
  return { ...ctx, usuarios: { jefe, adm, enf, med }, grupos: { admision, triage, medicos } };
}

async function prepararFormularios(ctx) {
  const formulario = async (titulo, descripcion) =>
    crearPorCampoExacto("formularios", { institucion: ctx.inst.id, area: ctx.areas.guardia.id }, "titulo", titulo, {
      institucion: ctx.inst.id,
      area: ctx.areas.guardia.id,
      titulo,
      descripcion: `${ESCUELA_TAG} ${descripcion}`,
    });
  const campo = async (form, label, tipo, orden, extra = {}) =>
    (await lista("campos", { formulario: form.id, page_size: 100 })).find((c) => c.label === label)
    || api.post("/campos/", {
      formulario: form.id,
      label,
      tipo,
      orden,
      requerido: true,
      ...extra,
    });

  const admision = await formulario("Admision escuela", "Datos minimos de ingreso.");
  await campo(admision, "Motivo de consulta", "texto_largo", 1);
  await campo(admision, "Cobertura", "seleccion_unica", 2, { opciones: ["Publica", "Obra social", "Prepaga"] });
  const triage = await formulario("Triage escuela", "Clasificacion inicial de enfermeria.");
  await campo(triage, "Dolor", "seleccion_unica", 1, { opciones: ["Leve", "Moderado", "Severo"] });
  // Temperatura es un NÚMERO con rango: es el campo que la escuela usa para
  // mostrar por qué el tipo importa —una Decisión «> 38» sobre texto libre no
  // compara nada y manda al paciente febril por el circuito del que no tiene fiebre.
  await campo(triage, "Temperatura", "numero", 2, { unidad: "°C", minimo: 30, maximo: 45 });
  await campo(triage, "Prioridad", "seleccion_unica", 3, { opciones: ["Baja", "Media", "Alta", "Urgente"] });
  return { ...ctx, formularios: { admision, triage } };
}

async function prepararFlujo(ctx) {
  ctx = await prepararFormularios(ctx);
  const flujo = await crearPorCampoExacto("flujos", { institucion: ctx.inst.id, area: ctx.areas.guardia.id }, "titulo", "Guardia escuela", {
    institucion: ctx.inst.id,
    area: ctx.areas.guardia.id,
    titulo: "Guardia escuela",
    descripcion: `${ESCUELA_TAG} Flujo base de capacitacion: admision, triage, fila medica y cierre.`,
  });
  let version = await primero("versiones-flujo", { flujo: flujo.id });
  if (!version) version = await api.post("/versiones-flujo/", { flujo: flujo.id, numero: 1, nota: ESCUELA_TAG });
  if (version.estado !== "borrador") return { ...ctx, flujo, version };

  const nodosExistentes = await lista("nodos", { version: version.id, page_size: 100 });
  const porTitulo = new Map(nodosExistentes.map((n) => [n.titulo, n]));
  const nodo = async (titulo, tipo, x, y, payload = {}) => {
    if (porTitulo.has(titulo)) return porTitulo.get(titulo);
    const n = await api.post("/nodos/", { version: version.id, titulo, tipo, x, y, ...payload });
    porTitulo.set(titulo, n);
    return n;
  };
  const inicio = await nodo("Ingreso", "inicio", 80, 260, { config: { origen: "ambos" } });
  const admision = await nodo("Admision administrativa", "form", 300, 260, {
    formulario: ctx.formularios.admision.id,
    grupos: [ctx.grupos.admision.id],
  });
  const triage = await nodo("Triage de enfermeria", "form", 540, 260, {
    formulario: ctx.formularios.triage.id,
    grupos: [ctx.grupos.triage.id],
  });
  const espera = await nodo("Sala de espera", "espera", 780, 260, { config: { con_fila: true } });
  const atencion = await nodo("Atencion medica", "atencion", 1020, 260, {
    grupos: [ctx.grupos.medicos.id],
    config: { con_fila: true, plantilla: "Evaluacion clinica, conducta y cierre." },
  });
  const fin = await nodo("Alta / cierre", "fin", 1260, 260);

  const conexiones = await lista("conexiones", { version: version.id, page_size: 100 });
  const ya = new Set(conexiones.map((c) => `${c.origen}-${c.destino}`));
  const conectar = async (origen, destino, etiqueta = "") => {
    const k = `${origen.id}-${destino.id}`;
    if (ya.has(k)) return;
    await api.post("/conexiones/", { version: version.id, origen: origen.id, destino: destino.id, etiqueta, condicion: {} });
    ya.add(k);
  };
  await conectar(inicio, admision);
  await conectar(admision, triage);
  await conectar(triage, espera);
  await conectar(espera, atencion);
  await conectar(atencion, fin);
  version = await api.post(`/versiones-flujo/${version.id}/publicar/`);
  return { ...ctx, flujo, version };
}

async function prepararAgenda(ctx) {
  ctx = await prepararFlujo(ctx);
  const agenda = await crearPorCampoExacto("agendas", { institucion: ctx.inst.id, area: ctx.areas.guardia.id }, "nombre", "Consultorio escuela", {
    institucion: ctx.inst.id,
    area: ctx.areas.guardia.id,
    tipo: "profesional",
    nombre: "Consultorio escuela",
    profesional: ctx.usuarios.med.id,
    flujo: ctx.flujo.id,
    duracion_min: 20,
    sobreturnos_max: 2,
    activa: true,
  });
  const manana = new Date();
  manana.setDate(manana.getDate() + 1);
  const diaSemana = (manana.getDay() + 6) % 7;
  const disp = await primero("disponibilidades", { agenda: agenda.id, dia_semana: diaSemana });
  if (!disp) {
    await api.post("/disponibilidades/", { agenda: agenda.id, dia_semana: diaSemana, desde: "08:00", hasta: "12:00" });
  }
  return { ...ctx, agenda, manana };
}

async function prepararCasos(ctx) {
  ctx = await prepararAgenda(ctx);
  const paciente = async (nombre, apellido, documento) =>
    crearPorCampoExacto("ciudadanos", { institucion: ctx.inst.id, search: documento }, "documento", documento, {
      institucion: ctx.inst.id,
      nombre,
      apellido,
      documento,
      obra_social: "Publica",
      domicilio: "Escenario de capacitacion",
    });
  const ana = await paciente("Ana", "Escuela", "90000001");
  const luis = await paciente("Luis", "Simulado", "90000002");
  const fecha = ctx.manana.toISOString().slice(0, 10);
  const inicio = `${fecha}T08:00:00`;
  const turnoExistente = await primero("turnos", { agenda: ctx.agenda.id, ciudadano: ana.id, desde: fecha, hasta: fecha });
  if (!turnoExistente) {
    await api.post("/turnos/", { agenda: ctx.agenda.id, ciudadano: ana.id, inicio, motivo: "Control post guardia" });
  }
  const casoExistente = await primero("casos", { institucion: ctx.inst.id, ciudadano: luis.id });
  if (!casoExistente && ctx.version?.estado === "publicada") {
    const caso = await api.post("/casos/", {
      institucion: ctx.inst.id,
      version: ctx.version.id,
      ciudadano: luis.id,
      area_actual: ctx.areas.guardia.id,
      prioridad: "normal",
    });
    await api.post(`/casos/${caso.id}/iniciar/`);
  }
  return { ...ctx, pacientes: { ana, luis } };
}

async function prepararEscuela(nombre) {
  let ctx = await contextoEscuela();
  if (["areas", "usuarios", "formularios", "flujo", "agenda", "casos"].includes(nombre)) {
    ctx = await prepararAreas(ctx);
  }
  if (["usuarios", "formularios", "flujo", "agenda", "casos"].includes(nombre)) {
    ctx = await prepararUsuarios(ctx);
  }
  if (nombre === "formularios") return prepararFormularios(ctx);
  if (nombre === "flujo") return prepararFlujo(ctx);
  if (nombre === "agenda") return prepararAgenda(ctx);
  if (nombre === "casos") return prepararCasos(ctx);
  return ctx;
}

function useTarget(selector, activo, pathname) {
  const [rect, setRect] = useState(null);

  useEffect(() => {
    if (!activo || !selector) {
      setRect(null);
      return;
    }
    let raf = 0;
    const medir = () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        const el = document.querySelector(selector);
        if (!el) {
          setRect(null);
          return;
        }
        el.scrollIntoView({ block: "center", inline: "center", behavior: "smooth" });
        const r = el.getBoundingClientRect();
        setRect({ top: r.top, left: r.left, width: r.width, height: r.height });
      });
    };
    const t = setTimeout(medir, 180);
    window.addEventListener("resize", medir);
    window.addEventListener("scroll", medir, true);
    return () => {
      clearTimeout(t);
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", medir);
      window.removeEventListener("scroll", medir, true);
    };
  }, [selector, activo, pathname]);

  return rect;
}

function setInputValue(input, value) {
  if (!input) return;
  const setter = Object.getOwnPropertyDescriptor(input.constructor.prototype, "value")?.set;
  setter?.call(input, value);
  input.dispatchEvent(new Event("input", { bubbles: true }));
  input.dispatchEvent(new Event("change", { bubbles: true }));
}

async function ejecutarActorScript(script, step) {
  if (script !== "area") return;
  const yaExiste = document.body.textContent?.includes("Guardia escuela");
  const botonNuevo = document.querySelector(step.actorTarget);
  botonNuevo?.click();
  await sleep(550);

  const modal = document.querySelector('[role="dialog"], [aria-modal="true"]') || document.body;
  const inputNombre = modal.querySelector("input");
  setInputValue(inputNombre, "Guardia escuela");
  await sleep(650);

  const botones = Array.from(modal.querySelectorAll("button"));
  const guardar = botones.find((b) => /guardar/i.test(b.textContent || ""));
  const cancelar = botones.find((b) => /cancelar/i.test(b.textContent || ""));
  (yaExiste ? cancelar : guardar)?.click();
  await sleep(900);
}

export function TutorialProvider({ children }) {
  const { user } = useAuth();
  const { institucion, setInstitucion, setVista } = useInstitucion();
  const navigate = useNavigate();
  const location = useLocation();
  const [activo, setActivo] = useState(false);
  const [paso, setPaso] = useState(0);
  const [errorDemo, setErrorDemo] = useState("");
  const [preparando, setPreparando] = useState("");
  const [accionesDemo, setAccionesDemo] = useState([]);
  const [accionActiva, setAccionActiva] = useState(-1);
  const [cursorDemo, setCursorDemo] = useState({ visible: false, x: 28, y: 28, click: false });
  const [vozActiva, setVozActiva] = useState(false);
  const [vozPausada, setVozPausada] = useState(false);
  const [autoAvance, setAutoAvance] = useState(true);
  const clicksDemo = useRef({ n: 0, timer: 0 });
  const preparados = useRef(new Set());
  const step = DEMO_STEPS[paso];
  const targetRect = useTarget(step?.target, activo, location.pathname);
  const actorRect = useTarget(step?.actorTarget, activo && Boolean(step?.actorTarget), location.pathname);
  const rect = preparando && actorRect ? actorRect : targetRect;

  useEffect(() => {
    if (!activo || !rect) return;
    setCursorDemo((c) => ({
      ...c,
      visible: true,
      x: rect.left + Math.min(rect.width - 10, Math.max(14, rect.width * 0.42)),
      y: rect.top + Math.min(rect.height - 8, Math.max(14, rect.height * 0.55)),
      click: false,
    }));
    const t = window.setTimeout(() => {
      setCursorDemo((c) => ({ ...c, click: true }));
      window.setTimeout(() => setCursorDemo((c) => ({ ...c, click: false })), 260);
    }, 620);
    return () => window.clearTimeout(t);
  }, [activo, rect, paso]);

  const narrar = useCallback((texto) => {
    if (!puedeNarrar()) return;
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(texto);
    u.lang = "es-AR";
    u.rate = 0.95;
    u.pitch = 1;
    u.onend = () => setVozPausada(false);
    u.onerror = () => setVozPausada(false);
    window.speechSynthesis.speak(u);
    setVozPausada(false);
  }, []);

  useEffect(() => {
    if (!activo || !step?.route || location.pathname === step.route) return;
    navigate(step.route);
  }, [activo, step, location.pathname, navigate]);

  useEffect(() => {
    if (!activo || !vozActiva) return;
    narrar(textoNarracion(step, errorDemo));
  }, [activo, vozActiva, paso, errorDemo, step, narrar]);

  useEffect(() => {
    if (activo) return;
    if (puedeNarrar()) window.speechSynthesis.cancel();
    setVozPausada(false);
  }, [activo]);

  async function iniciarDemo() {
    if (!user?.is_superuser) return;
    setErrorDemo("");
    setPreparando("Creando institucion escuela...");
    try {
      const ctx = await contextoEscuela();
      setInstitucion(ctx.inst);
      setVista?.("sistema");
      preparados.current = new Set(["institucion"]);
      setPaso(0);
      setActivo(true);
      navigate("/inicio");
    } catch {
      setErrorDemo("No pude preparar el modo escuela. Revisemos que el backend este levantado y que el usuario sea super admin.");
      setActivo(true);
      setPaso(0);
    } finally {
      setPreparando("");
    }
  }

  useEffect(() => {
    if (!activo || !step?.prepare || preparados.current.has(step.prepare)) return;
    let cancelado = false;
    (async () => {
      setPreparando(`Preparando: ${step.title}`);
      setAccionesDemo(step.actions || []);
      setAccionActiva(-1);
      try {
        for (let i = 0; i < (step.actions || []).length; i += 1) {
          if (cancelado) return;
          setAccionActiva(i);
          setCursorDemo((c) => ({ ...c, click: true }));
          await sleep(260);
          setCursorDemo((c) => ({ ...c, click: false }));
          if (i === 0 && step.actorScript) {
            await ejecutarActorScript(step.actorScript, step);
          }
          await sleep(520);
        }
        const ctx = await prepararEscuela(step.prepare);
        if (cancelado) return;
        if (ctx?.inst) setInstitucion(ctx.inst);
        preparados.current.add(step.prepare);
        setErrorDemo("");
      } catch (e) {
        if (!cancelado) {
          setErrorDemo(`No pude preparar este paso: ${e?.message || "error inesperado"}`);
        }
      } finally {
        if (!cancelado) {
          setPreparando("");
          setAccionActiva((step.actions || []).length);
        }
      }
    })();
    return () => { cancelado = true; };
  }, [activo, paso, step, setInstitucion]);

  useEffect(() => {
    function alClick(e) {
      if (!user?.is_superuser) return;
      if (!e.target?.closest?.('[data-demo-trigger="super-admin"]')) return;

      if (e.detail >= 3) {
        clicksDemo.current.n = 0;
        window.clearTimeout(clicksDemo.current.timer);
        iniciarDemo();
        return;
      }

      clicksDemo.current.n += 1;
      window.clearTimeout(clicksDemo.current.timer);
      if (clicksDemo.current.n >= 3) {
        clicksDemo.current.n = 0;
        iniciarDemo();
        return;
      }
      clicksDemo.current.timer = window.setTimeout(() => {
        clicksDemo.current.n = 0;
      }, 2500);
    }

    document.addEventListener("click", alClick, true);
    return () => {
      document.removeEventListener("click", alClick, true);
      window.clearTimeout(clicksDemo.current.timer);
    };
  }, [user, institucion]);

  const value = useMemo(() => ({ iniciarDemo, activo }), [activo]);

  const cerrar = () => {
    if (puedeNarrar()) window.speechSynthesis.cancel();
    setVozActiva(false);
    setVozPausada(false);
    setActivo(false);
    setErrorDemo("");
  };
  const avanzar = () => {
    if (paso >= DEMO_STEPS.length - 1) {
      cerrar();
      return;
    }
    setPaso((p) => p + 1);
  };
  const volver = () => setPaso((p) => Math.max(0, p - 1));
  useEffect(() => {
    if (!activo || errorDemo || preparando || !autoAvance) return undefined;
    const espera = step?.prepare ? 2600 : 4200;
    const t = window.setTimeout(() => {
      if (paso >= DEMO_STEPS.length - 1) cerrar();
      else setPaso((p) => p + 1);
    }, espera);
    return () => window.clearTimeout(t);
  }, [activo, errorDemo, preparando, autoAvance, paso, step]);

  const alternarVoz = () => {
    if (!puedeNarrar()) return;
    if (vozActiva) {
      window.speechSynthesis.cancel();
      setVozActiva(false);
      setVozPausada(false);
      return;
    }
    setVozActiva(true);
    narrar(textoNarracion(step, errorDemo));
  };
  const pausarVoz = () => {
    if (!puedeNarrar()) return;
    if (window.speechSynthesis.paused) {
      window.speechSynthesis.resume();
      setVozPausada(false);
    } else {
      window.speechSynthesis.pause();
      setVozPausada(true);
    }
  };

  return (
    <TutorialContext.Provider value={value}>
      {children}
      {activo && (
        <TutorialOverlay
          step={step}
          rect={rect}
          paso={paso}
          total={DEMO_STEPS.length}
          error={errorDemo}
          vozActiva={vozActiva}
          vozPausada={vozPausada}
          vozDisponible={puedeNarrar()}
          preparando={preparando}
          acciones={accionesDemo}
          accionActiva={accionActiva}
          autoAvance={autoAvance}
          onCerrar={cerrar}
          onVolver={volver}
          onAvanzar={avanzar}
          onToggleAuto={() => setAutoAvance((v) => !v)}
          onAlternarVoz={alternarVoz}
          onPausarVoz={pausarVoz}
        />
      )}
      {activo && <CursorDemo cursor={cursorDemo} />}
    </TutorialContext.Provider>
  );
}

function TutorialOverlay({
  step, rect, paso, total, error, vozActiva, vozPausada, vozDisponible,
  preparando, acciones, accionActiva, autoAvance, onCerrar, onVolver, onAvanzar, onToggleAuto, onAlternarVoz, onPausarVoz,
}) {
  const actual = acciones?.[accionActiva] || (preparando ? "Cargando datos de practica" : "Mostrando pantalla");

  return (
    <div className="pointer-events-none fixed inset-0 z-[80]">
      {rect && (
        <div
          className="absolute rounded-lg border-2 border-accent bg-accent-50/10 shadow-[0_0_0_4px_rgba(72,79,210,.12)]"
          style={{
            top: rect.top - 6,
            left: rect.left - 6,
            width: rect.width + 12,
            height: rect.height + 12,
          }}
        />
      )}
      <section
        role="status"
        aria-live="polite"
        aria-label="Recorrido guiado"
        className="pointer-events-auto fixed bottom-4 left-1/2 w-[min(980px,calc(100vw-32px))] -translate-x-1/2 rounded-lg border border-borde bg-superficie/95 p-3 shadow-modal backdrop-blur"
      >
        <div className="grid gap-3 md:grid-cols-[1fr_auto] md:items-center">
          <div className="min-w-0">
            <div className="mb-1 flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-2 rounded-pill bg-accent-50 px-3 py-1 text-sm font-bold text-accent">
                <Icon name={preparando ? "refresh" : "play"} size={13} className={cn(preparando && "animate-spin")} />
                Recorrido guiado
              </span>
              <span className="text-sm font-semibold text-texto-tenue">{paso + 1} de {total}</span>
              {autoAvance && !error && <span className="text-sm font-semibold text-badge-green-fg">automatico</span>}
            </div>
            <div className="flex min-w-0 flex-col gap-1 md:flex-row md:items-baseline md:gap-3">
              <h2 className="shrink-0 text-base font-bold">{error || step?.title}</h2>
              <p className="min-w-0 truncate text-sm text-texto-suave">{error || step?.body}</p>
            </div>
            {!error && (
              <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
                <span className="font-bold text-accent">{preparando ? "Ejecutando" : "Viendo"}</span>
                <span className="rounded-md bg-superficie-2 px-2 py-1 font-semibold text-texto-suave">{actual}</span>
              </div>
            )}
            {!error && (
              <div className="mt-2 h-1.5 overflow-hidden rounded-pill bg-division">
                <div className="h-full rounded-pill bg-accent transition-all" style={{ width: `${((paso + 1) / total) * 100}%` }} />
              </div>
            )}
          </div>
          <div className="flex flex-wrap justify-end gap-2">
            <Button type="button" size="sm" variant="secondary" onClick={onToggleAuto}>
              {autoAvance ? "Pausar recorrido" : "Reanudar"}
            </Button>
            <Button type="button" size="sm" variant={vozActiva ? "primary" : "secondary"} disabled={!vozDisponible} onClick={onAlternarVoz} title={vozDisponible ? "Leer en voz alta este recorrido" : "Este navegador no tiene narrador disponible"}>
              <Icon name={vozActiva ? "x" : "play"} size={13} />
              {vozActiva ? "Silenciar" : "Narrar"}
            </Button>
            {vozActiva && (
              <Button type="button" size="sm" variant="secondary" onClick={onPausarVoz}>
                {vozPausada ? "Seguir voz" : "Pausar voz"}
              </Button>
            )}
            {!error && paso > 0 && <Button variant="secondary" size="sm" onClick={onVolver}>Anterior</Button>}
            <Button size="sm" disabled={!!preparando} onClick={error ? onCerrar : onAvanzar} className={cn(error && "bg-accent-fuerte")}>
              {error ? "Cerrar" : paso === total - 1 ? "Finalizar" : "Siguiente"}
            </Button>
            <button onClick={onCerrar} aria-label="Cerrar recorrido" className="rounded-sm p-2 text-texto-debil hover:text-texto">
              <Icon name="x" size={17} />
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}

function CursorDemo({ cursor }) {
  if (!cursor.visible) return null;
  return (
    <div
      className="pointer-events-none fixed z-[90] transition-[left,top] duration-700 ease-out"
      style={{ left: cursor.x, top: cursor.y }}
      aria-hidden="true"
    >
      <div className="relative">
        <svg
          width="28"
          height="28"
          viewBox="0 0 28 28"
          className="drop-shadow-[0_3px_8px_rgba(16,24,40,.35)]"
        >
          <path
            d="M5 3l15 13-8 1.5L8.5 25 5 3z"
            fill="var(--color-superficie)"
            stroke="var(--color-accent)"
            strokeWidth="2"
            strokeLinejoin="round"
          />
        </svg>
        {cursor.click && (
          <span className="absolute left-3 top-3 size-9 -translate-x-1/2 -translate-y-1/2 animate-ping rounded-pill border-2 border-accent bg-accent-50/40" />
        )}
      </div>
    </div>
  );
}

export function useTutorial() {
  return useContext(TutorialContext);
}
