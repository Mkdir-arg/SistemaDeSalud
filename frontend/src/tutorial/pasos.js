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
    body: "Se crea una institución aparte, Hospital Escuela Cauce, y se la puebla paso a paso como el primer día de una implementación. No es un modo de prueba: son las mismas pantallas, los mismos formularios y la misma base que en producción, sobre un establecimiento que se puede vaciar y volver a construir.",
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
    body: "El área es la unidad de la que cuelga todo lo demás: los permisos se dan por área, las colas de espera son de un área, y un flujo y una agenda pertenecen a un área. Por eso va primero — antes de esto no hay a quién darle un rol ni dónde poner una fila. Cargamos cinco: Guardia, Laboratorio, Imágenes, Internación y Farmacia.",
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
    body: "Dar de alta a una persona son dos decisiones en un solo formulario: el rol, que define qué partes del sistema se le abren, y la institución, que sale del contexto en el que estamos. La membresía además la ata al área: el staff de Guardia es quien tiene membresía en Guardia, y de ahí sale después la lista de profesionales de una agenda.",
    guion: [
      { t: "ir", ruta: "/administracion", menu: '[data-tour="menu-administracion"]', decir: "Vamos a Administración" },
      { t: "click", boton: "Crear usuario", abreDialogo: true, decir: "Tocamos Crear usuario" },
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
    body: "El formulario de triage, y el campo que explica por qué el tipo de dato importa. Temperatura va como número con mínimo y máximo, no como texto libre: sobre texto, una decisión «mayor a 38» no compara nada, da falso en silencio, y manda al paciente con fiebre por el circuito del que no tiene fiebre. Nadie ve el error hasta que ya pasó.",
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
    body: "El circuito de guardia, de punta a punta: ingreso, admisión administrativa, triage de enfermería, sala de espera, atención médica y cierre. Cada paso tiene un grupo responsable, y por eso la tarea le aparece a la persona correcta y no a todos. Publicar es lo que lo vuelve operable: en borrador se puede diseñar, pero no abre ningún caso.",
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
    route: "/mapa",
    target: '[data-tour="menu-mapa"]',
    title: "Cómo se encadenan los procesos",
    body: "Un flujo publicado no vive solo. El mapa muestra cómo los circuitos se llaman entre sí a través de los pasos de derivación: guardia que pide un estudio al laboratorio, laboratorio que devuelve. Recién armamos uno, así que el mapa tiene un solo nodo — y ese vacío es informativo, porque es lo que se ve antes de que la institución tenga varios procesos conectados.",
  },
  {
    prepare: "agenda",
    route: "/estructura",
    target: '[data-tour="menu-estructura"]',
    title: "Turnos programados",
    body: "Una agenda define a quién o a qué se le pueden dar turnos: un profesional, o un recurso como un tomógrafo. Los dos campos que la conectan con el resto son el profesional y el flujo que se abre al presentarse. Sin ese flujo la agenda sigue dando turnos, pero cuando el paciente llega no se abre ningún caso y el turno no lleva a nada.",
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
    body: "Por último, personas. El padrón es la identidad —quién es, cómo se lo encuentra—, separado de la historia clínica, que es lo que le pasó. Con el paciente cargado y el flujo publicado se puede abrir un caso, que es lo que recorre el circuito paso por paso y le va apareciendo a cada responsable.",
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

  // A partir de acá no hay nada que construir. Estas pantallas se miran, y el
  // texto es todo lo que se lleva quien las mira: dice qué decisión permite
  // tomar la pantalla y quién la usa, no qué datos contiene. «Muestra camas,
  // estadías y disponibilidad» era la versión anterior de este archivo, y no
  // dice nada que no se adivine del título.
  //
  // Dos de ellas traen `prepare`: la app no tiene por dónde cargar camas ni
  // insumos, y sin datos son un cartel de vacío.
  {
    route: "/inicio",
    target: '[data-tour="inicio-operar"]',
    title: "Mi trabajo",
    body: "La worklist de quien opera. No lista «los casos del hospital»: lista lo que le toca a esta persona, separado por el paso del que es responsable —lo asignado, lo que está en sus grupos sin que nadie lo haya tomado, y las esperas que se vencieron—. Un administrativo y un médico abren la misma pantalla y ven cosas distintas.",
  },
  {
    prepare: "internacion",
    route: "/internacion",
    target: '[data-tour="menu-internacion"]',
    title: "Internación",
    body: "El tablero de camas por sector, con la ocupación arriba a la derecha. Sirve para la pregunta que se hace en la guardia cuando un paciente tiene que quedarse: si hay dónde, y desde cuándo está ocupada la que no. Cargamos seis camas en el área de internación de la escuela.",
  },
  {
    prepare: "farmacia",
    route: "/farmacia",
    target: '[data-tour="menu-farmacia"]',
    title: "Farmacia e insumos",
    body: "La primera pestaña no es el stock: es «Qué resolver», y trae sólo lo que está por debajo de su mínimo o vence en los próximos dos meses. Un listado completo de mil insumos no dice qué hacer; esta lista sí. Dejamos la gasa estéril por debajo del mínimo para que se vea funcionando.",
  },
  {
    route: "/red",
    target: '[data-tour="menu-red"]',
    title: "Red y traslados",
    body: "Coordina el traslado de un paciente a otro establecimiento: se pide, el otro lado responde, el paciente viaja, y del otro lado lo reciben. Las dos pestañas son las dos puntas —«Nos derivan» y «Derivamos»— porque el mismo hospital hace las dos cosas. La escuela todavía no está en ninguna red, así que muestra el vacío que ve una institución nueva.",
  },
  {
    route: "/historia",
    target: '[data-tour="menu-historia"]',
    title: "Historia clínica",
    body: "Se busca a la persona y se lee lo que le pasó: atenciones, estudios, recetas y eventos, en orden. Es distinto del padrón, que son los datos de identidad y contacto: acá está lo clínico, y por eso cada consulta a esta pantalla queda registrada en Auditoría.",
  },
  {
    route: "/legajo",
    target: '[data-tour="menu-legajo"]',
    title: "Legajo profesional",
    body: "La contracara de la historia clínica, del lado del equipo: quién es cada profesional en esta institución y qué viene haciendo. «Actividad reciente» es lo que permite responder por una atención meses después, cuando ya nadie se acuerda quién estaba de guardia.",
  },
  {
    route: "/dashboard",
    target: '[data-tour="menu-dashboard"]',
    title: "Tablero",
    body: "Para jefatura, y está partido en dos a propósito. Arriba «Requiere atención», que son los indicadores que conviene resolver antes de sentarse a analizar nada; abajo «Pulso operativo», la carga de ahora y la producción del período —7, 30 o 90 días—. Un tablero que mezcla las dos cosas se mira y no se hace nada.",
  },
  {
    route: "/supervision",
    target: '[data-tour="menu-supervision"]',
    title: "Supervisión",
    body: "Lo que ve el jefe de área: los casos activos de su área y las acciones para ordenarlos —reasignar, priorizar, desatascar— sin tener que entrar caso por caso. El filtro lo hace el servidor: trae los que esta persona puede supervisar, no los del hospital entero recortados a la primera página.",
  },
  {
    route: "/accesos",
    target: '[data-tour="menu-accesos"]',
    title: "Auditoría",
    body: "Quién consultó, cuándo, y de quién. Registra las tres formas de ver datos clínicos que existen —abrir un registro, listar, y exportar a un archivo— porque las tres son un acceso, y la exportación es la que se lleva los datos afuera. Es la condición para que la historia clínica del módulo anterior sea seria.",
  },
];
