/**
 * El escenario de capacitación: Hospital Escuela Cauce.
 *
 * Acá vive lo que el recorrido carga por API. Dejó de ser el camino principal
 * —ahora el actor completa los formularios de la app— y pasó a cumplir tres
 * papeles:
 *
 *  1. El SEMBRADO declarado. Actuar las cinco áreas, los cuatro usuarios, los
 *     tres grupos, los dos formularios con sus campos, los seis nodos con sus
 *     conexiones, la agenda, la franja y el turno son unos cuarenta formularios:
 *     entre ocho y doce minutos que nadie mira. El actor hace el caso
 *     representativo y el resto entra por acá, dicho en el panel («las otras
 *     cuatro áreas van igual que esta») en vez de tildado en silencio.
 *  2. La RED del actuado. Todo es idempotente, así que al cerrar cada paso se
 *     corre igual: si una acción no encontró su botón, el paso termina completo
 *     y el recorrido sigue.
 *  3. El modo RÁPIDO, para quien ya vio la demo y quiere los datos.
 */
import { api } from "@/api/client";

export const ESCUELA_NOMBRE = "Hospital Escuela Cauce";
export const ESCUELA_TAG = "[escuela-cauce]";

export async function lista(recurso, params = {}) {
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") qs.set(k, v);
  });
  const d = await api.get(`/${recurso}/${qs.toString() ? `?${qs}` : ""}`);
  return d.results || d;
}

export async function primero(recurso, params) {
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

export async function institucionEscuela() {
  return primero("instituciones", { search: ESCUELA_NOMBRE });
}

export async function contextoEscuela() {
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
  const area = async (nombre, responsable, descripcion = "") => {
    ctx.avisar?.(`Área ${nombre}`);
    return crearPorCampoExacto("areas", { institucion: ctx.inst.id }, "nombre", nombre, {
      institucion: ctx.inst.id,
      nombre,
      responsable,
      descripcion: `${ESCUELA_TAG} ${descripcion}`.trim(),
      activa: true,
    });
  };

  const guardia = await area("Guardia escuela", "Jefatura de guardia", "Puerta de entrada de urgencias y demanda espontanea.");
  const laboratorio = await area("Laboratorio escuela", "Bioquimica de guardia", "Procesa estudios solicitados desde guardia.");
  const imagenes = await area("Imagenes escuela", "Diagnostico por imagenes", "Radiologia y ecografia de entrenamiento.");
  const internacion = await area("Internacion escuela", "Coordinacion de camas", "Camas para observar el pase desde guardia.");
  const farmacia = await area("Farmacia escuela", "Deposito central", "Stock inicial para capacitacion.");
  return { ...ctx, areas: { guardia, laboratorio, imagenes, internacion, farmacia } };
}

async function prepararUsuarios(ctx) {
  const usuario = async (email, nombre, apellido) => {
    ctx.avisar?.(`${nombre} ${apellido}`);
    return crearPorCampoExacto("usuarios", { search: email }, "email", email, {
      email, nombre, apellido, password: "demo1234", is_active: true,
    });
  };

  const membresia = async (u, rol, areas = []) => {
    const m = await primero("membresias", { usuario: u.id, institucion: ctx.inst.id, rol });
    const ids = areas.map((a) => a.id);
    if (m) {
      // El alta de usuario de la app crea la membresía con el rol pero sin áreas
      // —el modal sólo pregunta el rol—, y el staff de un área se lista con
      // `membresias?areas=<id>`. Sin este parche, la persona que el actor acaba
      // de crear no aparece en el desplegable «Profesional» de la agenda del
      // área: el paso siguiente del recorrido se queda sin a quién asignar.
      const faltan = ids.filter((id) => !(m.areas || []).includes(id));
      if (!faltan.length) return m;
      return api.patch(`/membresias/${m.id}/`, { areas: [...(m.areas || []), ...faltan] });
    }
    return api.post("/membresias/", {
      usuario: u.id,
      institucion: ctx.inst.id,
      rol,
      areas: ids,
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

  const grupo = async (nombre, descripcion, miembros) => {
    ctx.avisar?.(`Grupo ${nombre}`);
    return crearPorCampoExacto("grupos", { area: ctx.areas.guardia.id }, "nombre", nombre, {
      area: ctx.areas.guardia.id,
      nombre,
      descripcion: `${ESCUELA_TAG} ${descripcion}`,
      miembros: miembros.map((u) => u.id),
      activo: true,
    });
  };
  const admision = await grupo("Admision escuela", "Mostrador de ingreso de pacientes.", [adm]);
  const triage = await grupo("Triage escuela", "Enfermeria que clasifica prioridad.", [enf]);
  const medicos = await grupo("Medicos guardia escuela", "Profesionales que firman atenciones.", [med]);
  return { ...ctx, usuarios: { jefe, adm, enf, med }, grupos: { admision, triage, medicos } };
}

async function prepararFormularios(ctx) {
  const formulario = async (titulo, descripcion) => {
    ctx.avisar?.(`Formulario ${titulo}`);
    return crearPorCampoExacto("formularios", { institucion: ctx.inst.id, area: ctx.areas.guardia.id }, "titulo", titulo, {
      institucion: ctx.inst.id,
      area: ctx.areas.guardia.id,
      titulo,
      descripcion: `${ESCUELA_TAG} ${descripcion}`,
    });
  };
  const campo = async (form, label, tipo, orden, extra = {}) => {
    ctx.avisar?.(`Campo ${label}`);
    const yaEsta = (await lista("campos", { formulario: form.id, page_size: 100 }))
      .find((c) => c.label === label);
    if (yaEsta) return yaEsta;
    return api.post("/campos/", {
      formulario: form.id,
      label,
      tipo,
      orden,
      requerido: true,
      ...extra,
    });
  };

  const admision = await formulario("Admision escuela", "Datos minimos de ingreso.");
  await campo(admision, "Motivo de consulta", "texto_largo", 1);
  await campo(admision, "Cobertura", "seleccion_unica", 2, { opciones: ["Publica", "Obra social", "Prepaga"] });
  const triage = await formulario("Triage escuela", "Clasificacion inicial de enfermeria.");
  await campo(triage, "Dolor", "seleccion_unica", 1, { opciones: ["Leve", "Moderado", "Severo"] });
  // Temperatura es un NÚMERO con rango: es el campo que la escuela usa para
  // mostrar por qué el tipo importa —una Decisión «> 38» sobre texto libre no
  // compara nada y manda al paciente febril por el circuito del que no tiene
  // fiebre. Por eso es el campo que el actor carga a mano en la demo.
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
    ctx.avisar?.(`Nodo ${titulo}`);
    if (porTitulo.has(titulo)) return porTitulo.get(titulo);
    const n = await api.post("/nodos/", { version: version.id, titulo, tipo, x, y, ...payload });
    porTitulo.set(titulo, n);
    return n;
  };
  // El nodo de inicio se REUSA si ya hay uno, sin mirar el título. Cuando el
  // flujo lo creó el actor desde «Nuevo flujo», la plantilla «En blanco» ya dejó
  // un nodo Inicio: crear además el nuestro dejaba dos arranques en el mismo
  // circuito, y un flujo con dos inicios no publica.
  const inicio = nodosExistentes.find((n) => n.tipo === "inicio")
    || await nodo("Ingreso", "inicio", 80, 260, { config: { origen: "ambos" } });
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
    ctx.avisar?.(`${origen.titulo} → ${destino.titulo}`);
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
  return { ...ctx, flujo, version };
}

/**
 * Publica la versión.
 *
 * Va aparte del armado porque en el recorrido actuado el que publica es el
 * actor, apretando el botón Publicar del editor. Esto es la red para cuando ese
 * clic no salió: sin versión publicada no hay casos, y los dos pasos que siguen
 * quedan sin nada que mostrar.
 */
async function publicarFlujo(ctx) {
  if (!ctx.version || ctx.version.estado === "publicada") return ctx;
  const version = await api.post(`/versiones-flujo/${ctx.version.id}/publicar/`);
  return { ...ctx, version };
}

async function prepararAgenda(ctx) {
  ctx = await publicarFlujo(await prepararFlujo(ctx));
  ctx.avisar?.("Agenda Consultorio escuela");
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
  const paciente = async (nombre, apellido, documento) => {
    ctx.avisar?.(`Paciente ${nombre} ${apellido}`);
    return crearPorCampoExacto("ciudadanos", { institucion: ctx.inst.id, search: documento }, "documento", documento, {
      institucion: ctx.inst.id,
      nombre,
      apellido,
      documento,
      obra_social: "Publica",
      domicilio: "Escenario de capacitacion",
    });
  };
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

/**
 * Camas de internación.
 *
 * Van sembradas y no actuadas porque la app no tiene por dónde cargarlas: la
 * ficha del área tiene secciones para staff, grupos, boxes, agendas y sub-áreas,
 * y ninguna para camas —el vacío de Internación manda a «Estructura
 * organizativa → área de internación», que hoy no existe—. Sin camas, la
 * pantalla de Internación es un cartel de vacío, y una pantalla vacía no se
 * puede explicar.
 */
async function prepararInternacion(ctx) {
  const cama = async (nombre) => {
    ctx.avisar?.(`Cama ${nombre}`);
    return crearPorCampoExacto("camas", { area: ctx.areas.internacion.id, page_size: 100 }, "nombre", nombre, {
      area: ctx.areas.internacion.id,
      nombre,
      activa: true,
    });
  };
  for (const n of ["101-A", "101-B", "102-A", "102-B", "103-A", "103-B"]) await cama(n);
  return ctx;
}

/**
 * Depósito e insumos.
 *
 * Uno de los tres queda por debajo de su mínimo a propósito: la primera pestaña
 * de Farmacia es «Qué resolver», y con todo el stock en orden esa pestaña —que
 * es la que explica para qué sirve la pantalla— aparece vacía.
 */
async function prepararFarmacia(ctx) {
  ctx.avisar?.("Depósito de farmacia");
  const deposito = await crearPorCampoExacto(
    "depositos", { institucion: ctx.inst.id }, "nombre", "Farmacia central escuela",
    {
      institucion: ctx.inst.id,
      area: ctx.areas.farmacia.id,
      nombre: "Farmacia central escuela",
      central: true,
      activo: true,
    },
  );

  const insumo = async (nombre, presentacion, unidad, minimo, cantidad) => {
    ctx.avisar?.(nombre);
    const i = await crearPorCampoExacto("insumos", { institucion: ctx.inst.id, page_size: 200 }, "nombre", nombre, {
      institucion: ctx.inst.id,
      nombre,
      presentacion,
      unidad,
      stock_minimo: minimo,
      // Sin lote, para que el stock inicial entre sin inventar vencimientos.
      requiere_lote: false,
      activo: true,
    });
    // El stock no se escribe: se mueve. `/stock/` es de sólo lectura y
    // `/movimientos-stock/` rechaza el POST directo con un mensaje que lo dice
    // —«usá las acciones: cada tipo mueve el stock distinto»—, porque un ingreso
    // y un consumo tocan la existencia en sentidos opuestos. Un stock inicial
    // es un ingreso.
    const existe = (await lista("stock", { deposito: deposito.id, insumo: i.id, page_size: 10 }))[0];
    if (!existe) {
      await api.post("/movimientos-stock/ingreso/", {
        deposito: deposito.id,
        insumo: i.id,
        cantidad,
        motivo: `${ESCUELA_TAG} stock inicial de capacitacion`,
      });
    }
    return i;
  };

  await insumo("Paracetamol 500 mg", "Comprimido", "comprimido", 200, 640);
  await insumo("Solución fisiológica 500 ml", "Sachet", "sachet", 50, 180);
  // Éste queda corto: es el que hace que «Qué resolver» tenga algo que mostrar.
  await insumo("Gasa estéril 10x10", "Sobre", "sobre", 300, 45);
  return ctx;
}

/**
 * Siembra hasta el paso pedido, sin repetir lo que ya está.
 *
 * `avisar(texto)` se llama con cada cosa que entra, y no es decoración: el
 * sembrado tardaba entre tres y siete segundos con el cursor escondido y la
 * pantalla quieta, diciendo «Sembrando» y nada más. Eso se lee como que el
 * recorrido se colgó, no como que está trabajando. Cada aviso es un renglón que
 * se mueve, y de paso dice exactamente qué se cargó.
 */
export async function sembrar(nombre, avisar) {
  const CON_AREAS = ["areas", "usuarios", "formularios", "flujo", "agenda", "casos", "internacion", "farmacia"];
  const CON_USUARIOS = ["usuarios", "formularios", "flujo", "agenda", "casos"];

  let ctx = { ...(await contextoEscuela()), avisar };
  if (CON_AREAS.includes(nombre)) ctx = await prepararAreas(ctx);
  if (CON_USUARIOS.includes(nombre)) ctx = await prepararUsuarios(ctx);

  if (nombre === "formularios") return prepararFormularios(ctx);
  if (nombre === "flujo") return publicarFlujo(await prepararFlujo(ctx));
  if (nombre === "agenda") return prepararAgenda(ctx);
  if (nombre === "casos") return prepararCasos(ctx);
  if (nombre === "internacion") return prepararInternacion(ctx);
  if (nombre === "farmacia") return prepararFarmacia(ctx);
  return ctx;
}

/** Vacía la escuela para volver a construirla desde cero. */
export async function resetearEscuela() {
  const inst = await institucionEscuela();
  if (!inst) return;
  await api.post(`/instituciones/${inst.id}/reset-escuela/`, {});
}

/**
 * ¿Este paso ya está hecho?
 *
 * Sirve para «continuar donde quedó»: el actor no puede volver a completar el
 * formulario de un área que ya existe —se comería un «ya existe un área con ese
 * nombre»—, así que ese paso se salta y se muestra lo que hay.
 */
export const YA_HECHO = {
  institucion: async () => !!(await institucionEscuela()),
  areas: async (inst) => !!(await primero("areas", { institucion: inst.id, search: "Guardia escuela" })),
  usuarios: async () => !!(await primero("usuarios", { search: "escuela.med@cauce.local" })),
  formularios: async (inst) => !!(await primero("formularios", { institucion: inst.id, search: "Triage escuela" })),
  flujo: async (inst) => !!(await primero("flujos", { institucion: inst.id, search: "Guardia escuela" })),
  agenda: async (inst) => !!(await primero("agendas", { institucion: inst.id, search: "Consultorio escuela" })),
  casos: async (inst) => !!(await primero("ciudadanos", { institucion: inst.id, search: "90000001" })),
};

/** ¿Hay algo cargado, como para ofrecer empezar de cero? */
export async function escuelaTieneDatos() {
  const inst = await institucionEscuela();
  if (!inst) return false;
  const areas = await lista("areas", { institucion: inst.id, page_size: 1 });
  return areas.length > 0;
}
