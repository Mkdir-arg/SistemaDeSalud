/**
 * El recorrido, paso por paso.
 *
 * Los primeros siete pasos CONSTRUYEN la institución y traen un `guion`: una
 * lista de acciones que el actor ejecuta sobre la app real (ver `actor.js`). Los
 * últimos sólo muestran pantallas ya cargadas y no tienen nada que actuar.
 *
 * Reglas del guion, aprendidas armándolo:
 *
 *  - Los campos se nombran con la etiqueta que se VE, sin el asterisco. «Rol en»
 *    alcanza para «Rol en Hospital Escuela Cauce *»: el guion no puede saber el
 *    nombre de la institución de antemano.
 *  - Las opciones de un desplegable se eligen por texto y conviene que sea el
 *    trozo estable. En «Profesional» la app muestra el nombre completo o el mail
 *    según lo que tenga cargado la persona, así que se busca «Vera».
 *  - `sembrar` es la única acción que no se actúa: carga el resto por API y lo
 *    dice. Está en el guion, y no escondida al final del paso, porque el orden
 *    importa: primero se ve hacer uno, después se dice que los otros van igual.
 *
 * El orden de los pasos es el orden de las dependencias reales: sin áreas no hay
 * roles; sin usuarios no hay a quién asignarle una agenda; sin formularios no hay
 * qué poner en un nodo; sin flujo publicado no hay casos.
 */
import { ESCUELA_NOMBRE } from "./escenario";

export const DEMO_STEPS = [
  {
    prepare: "institucion",
    route: "/inicio",
    target: '[data-tour="inicio-institucion"]',
    title: "Modo escuela: el sistema desde cero",
    body: "Creamos una institución de capacitación aparte, Hospital Escuela Cauce, y la vamos a poblar paso a paso como si estuvieras implementando el sistema el primer día.",
    guion: [
      { t: "salir", decir: "Salimos al directorio de la plataforma" },
      { t: "click", boton: "Nueva institución", abreDialogo: true, decir: "Tocamos Nueva institución" },
      { t: "escribir", campo: "Nombre", valor: ESCUELA_NOMBRE, decir: "Le ponemos el nombre" },
      { t: "escribir", campo: "Tipo", valor: "Hospital general de capacitacion", decir: "Qué tipo de establecimiento es" },
      { t: "escribir", campo: "CUIT", valor: "30-00000000-7", decir: "Cargamos el CUIT" },
      { t: "boton", texto: "Crear", decir: "Creamos la institución" },
      { t: "esperar", hasta: "sin-dialogo" },
      { t: "entrar", decir: "Entramos al contexto de capacitación" },
    ],
  },
  {
    prepare: "areas",
    route: "/estructura",
    target: '[data-tour="menu-estructura"]',
    title: "Estructura organizativa",
    body: "Primero las áreas reales de trabajo: Guardia, Laboratorio, Imágenes, Internación y Farmacia. Sin estructura no hay roles, ni colas, ni circuitos operables.",
    guion: [
      { t: "ir", ruta: "/estructura", menu: '[data-tour="menu-estructura"]', decir: "Vamos a Estructura" },
      { t: "click", boton: "Nueva área", abreDialogo: true, decir: "Tocamos Nueva área" },
      { t: "escribir", campo: "Nombre", valor: "Guardia escuela", decir: "Escribimos el nombre del área" },
      { t: "escribir", campo: "Responsable / jefe", valor: "Jefatura de guardia", decir: "Quién responde por el área" },
      { t: "escribir", campo: "Descripción", valor: "Puerta de entrada de urgencias y demanda espontanea.", decir: "Para qué sirve" },
      { t: "boton", texto: "Guardar", decir: "Guardamos el área" },
      { t: "esperar", hasta: "sin-dialogo" },
      { t: "sembrar", decir: "Las otras cuatro áreas van igual que esta" },
    ],
  },
  {
    prepare: "usuarios",
    route: "/administracion",
    target: '[data-tour="menu-administracion"]',
    title: "Usuarios y accesos",
    body: "Ahora el equipo: administrativo, enfermería, médico y jefe de área. Cada rol habilita una parte distinta del sistema, y la membresía lo ata al área Guardia.",
    guion: [
      { t: "ir", ruta: "/administracion", menu: '[data-tour="menu-administracion"]', decir: "Vamos a Administración" },
      { t: "click", boton: "Nuevo usuario", abreDialogo: true, decir: "Tocamos Nuevo usuario" },
      { t: "escribir", campo: "Email", valor: "escuela.med@cauce.local", decir: "Con qué mail entra" },
      { t: "escribir", campo: "Nombre", valor: "Santiago", decir: "Nombre" },
      { t: "escribir", campo: "Apellido", valor: "Vera", decir: "Apellido" },
      { t: "escribir", campo: "Contraseña", valor: "demo1234", decir: "Contraseña inicial" },
      { t: "elegir", campo: "Rol en", opcion: "Médico", decir: "Entra como médico de la institución" },
      { t: "boton", texto: "Guardar", decir: "Damos de alta al usuario" },
      { t: "esperar", hasta: "sin-dialogo" },
      { t: "sembrar", decir: "El resto del equipo y los grupos de Admisión, Triage y Médicos" },
    ],
  },
  {
    prepare: "formularios",
    route: "/formularios",
    target: '[data-tour="menu-formularios"]',
    title: "Formularios clínicos",
    body: "El formulario de triage. El campo Temperatura va como número con rango, no como texto: es la diferencia entre una decisión «> 38» que compara y una que no compara nada.",
    guion: [
      { t: "ir", ruta: "/formularios", menu: '[data-tour="menu-formularios"]', decir: "Vamos a Formularios" },
      { t: "click", boton: "Nuevo formulario", abreDialogo: true, decir: "Tocamos Nuevo formulario" },
      { t: "escribir", campo: "Título", valor: "Triage escuela", decir: "Lo llamamos Triage escuela" },
      { t: "elegir", campo: "Área", opcion: "Guardia escuela", decir: "Es de la Guardia" },
      { t: "escribir", campo: "Descripción", valor: "Clasificacion inicial de enfermeria.", decir: "Para qué sirve" },
      { t: "boton", texto: "Crear y diseñar", decir: "Creamos y pasamos al diseño" },
      { t: "esperar", hasta: "ruta:/formularios/" },
      { t: "click", boton: "Agregar campo", abreDialogo: true, decir: "Agregamos el primer campo" },
      { t: "escribir", campo: "Etiqueta", valor: "Temperatura", decir: "La etiqueta que ve enfermería" },
      { t: "elegir", campo: "Tipo", opcion: "Número", decir: "Tipo número, no texto libre" },
      { t: "escribir", campo: "Unidad", valor: "°C", decir: "La unidad se muestra al lado del casillero" },
      { t: "escribir", campo: "Mínimo", valor: "30", decir: "Mínimo razonable" },
      { t: "escribir", campo: "Máximo", valor: "45", decir: "Máximo razonable" },
      { t: "boton", texto: "Agregar", decir: "Guardamos el campo" },
      { t: "esperar", hasta: "sin-dialogo" },
      { t: "sembrar", decir: "Dolor y Prioridad, y el formulario de admisión completo" },
    ],
  },
  {
    prepare: "flujo",
    route: "/flujos",
    target: '[data-tour="menu-flujos"]',
    title: "Diseño del proceso",
    body: "El circuito de guardia: ingreso, admisión administrativa, triage, sala de espera, atención médica y cierre. Publicarlo es lo que lo vuelve operable.",
    guion: [
      { t: "ir", ruta: "/flujos", menu: '[data-tour="menu-flujos"]', decir: "Vamos a Flujos" },
      { t: "click", boton: "Nuevo flujo", abreDialogo: true, decir: "Tocamos Nuevo flujo" },
      { t: "escribir", campo: "Título", valor: "Guardia escuela", decir: "Lo llamamos Guardia escuela" },
      { t: "elegir", campo: "Área", opcion: "Guardia escuela", decir: "Es de la Guardia" },
      { t: "boton", texto: "Crear y diseñar", decir: "Creamos y entramos al editor" },
      { t: "esperar", hasta: "ruta:/flujos/" },
      // Los nodos y las conexiones no se actúan: son seis nodos y cinco
      // conexiones, y sobre todo, la paleta deja el nodo con su título por
      // defecto. Publicar exige un circuito conectado de punta a punta, así que
      // un nodo suelto agregado «para la demo» hace fallar el Publicar de dos
      // acciones más abajo. Se siembra el circuito y se actúa el gesto que
      // importa, que es publicarlo.
      { t: "sembrar", decir: "Los seis nodos, las cinco conexiones y el grupo responsable de cada paso" },
      { t: "recargar", ruta: "/flujos", decir: "Volvemos a abrir el flujo ya armado" },
      { t: "boton", texto: "Publicar", decir: "Publicamos la versión 1" },
    ],
  },
  {
    prepare: "agenda",
    route: "/estructura",
    target: '[data-tour="menu-estructura"]',
    title: "Turnos programados",
    body: "La agenda del consultorio, con su profesional y con el flujo que se abre cuando el paciente se presenta. Una agenda sin flujo da turnos que no abren ningún caso.",
    guion: [
      { t: "ir", ruta: "/estructura", menu: '[data-tour="menu-estructura"]', decir: "Volvemos a Estructura" },
      { t: "click", boton: "Guardia escuela", decir: "Entramos al área Guardia escuela" },
      { t: "click", boton: "Agendas", decir: "Abrimos la sección Agendas" },
      { t: "click", boton: "Crear agenda", abreDialogo: true, decir: "Tocamos Crear agenda" },
      { t: "escribir", campo: "Nombre", valor: "Consultorio escuela", decir: "Nombramos la agenda" },
      { t: "elegir", campo: "Tipo", opcion: "Profesional", decir: "Es la agenda de una persona" },
      { t: "elegir", campo: "Profesional", opcion: "Vera", decir: "Asignamos a Santiago Vera" },
      { t: "elegir", campo: "Flujo que se abre al presentarse", opcion: "Guardia escuela", decir: "Al presentarse se abre el flujo de guardia" },
      { t: "escribir", campo: "Duración del turno (min)", valor: "20", decir: "Turnos de veinte minutos" },
      { t: "boton", texto: "Crear", decir: "Creamos la agenda" },
      { t: "esperar", hasta: "texto:Consultorio escuela" },
      { t: "sembrar", decir: "La franja de 8 a 12 y el turno de ejemplo" },
    ],
  },
  {
    prepare: "casos",
    route: "/padron",
    title: "Pacientes y casos",
    body: "Por último, gente. Se carga un paciente en el padrón y el escenario deja un caso abierto en guardia, así la pantalla de trabajo tiene tareas reales para admitir, clasificar y atender.",
    guion: [
      { t: "ir", ruta: "/padron", decir: "Vamos al padrón" },
      { t: "click", boton: "Crear registro", abreDialogo: true, decir: "Tocamos Crear registro" },
      { t: "escribir", campo: "Nombre", valor: "Ana", decir: "Nombre de la paciente" },
      { t: "escribir", campo: "Apellido", valor: "Escuela", decir: "Apellido" },
      { t: "escribir", campo: "Documento", valor: "90000001", decir: "Documento" },
      { t: "boton", texto: "Crear", decir: "La damos de alta" },
      { t: "esperar", hasta: "sin-dialogo" },
      { t: "sembrar", decir: "El segundo paciente, el turno de Ana y un caso ya abierto en guardia" },
    ],
  },

  // A partir de acá no hay nada que construir: son pantallas que muestran lo que
  // los pasos anteriores dejaron cargado.
  {
    route: "/inicio",
    target: '[data-tour="inicio-operar"]',
    title: "Mi trabajo",
    body: "La pantalla de trabajo dejó de estar vacía: hay tareas reales para admitir, hacer triage y atender.",
  },
  {
    route: "/internacion",
    target: '[data-tour="menu-internacion"]',
    title: "Internación",
    body: "Internación muestra camas, estadías y disponibilidad. Sirve para seguir ocupación y movimientos del paciente dentro del hospital.",
  },
  {
    route: "/farmacia",
    target: '[data-tour="menu-farmacia"]',
    title: "Farmacia e insumos",
    body: "Farmacia permite consultar stock, lotes, depósitos, pedidos y movimientos. Es el módulo operativo de insumos.",
  },
  {
    route: "/red",
    target: '[data-tour="menu-red"]',
    title: "Red y traslados",
    body: "Red coordina traslados entre establecimientos: solicitud, respuesta, viaje, recepción y seguimiento de demoras.",
  },
  {
    route: "/historia",
    target: '[data-tour="menu-historia"]',
    title: "Historia clínica",
    body: "Acá se busca el paciente y se consulta su historia: atenciones, estudios, recetas y eventos clínicos registrados.",
  },
  {
    route: "/legajo",
    target: '[data-tour="menu-legajo"]',
    title: "Legajo profesional",
    body: "El legajo concentra la información profesional del usuario y su trazabilidad dentro de la institución.",
  },
  {
    route: "/dashboard",
    target: '[data-tour="menu-dashboard"]',
    title: "Tablero",
    body: "El tablero es para jefatura y administración: volumen de casos, demoras, ausentismo de turnos, saturación y salud de procesos.",
  },
  {
    route: "/supervision",
    target: '[data-tour="menu-supervision"]',
    title: "Supervisión",
    body: "Supervisión permite mirar el trabajo del área, detectar demoras y ordenar la operación sin entrar caso por caso.",
  },
  {
    route: "/accesos",
    target: '[data-tour="menu-accesos"]',
    title: "Auditoría",
    body: "El registro de accesos muestra quién consultó datos clínicos. Es la contracara necesaria de una historia clínica seria.",
  },
];
