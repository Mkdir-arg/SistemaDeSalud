import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../../api/client";
import { Badge, Button, Checkbox, Field, Input, Select, Spinner, Textarea } from "../../components/ui";
import { Icon } from "../../components/icons";
import { estadoCaso, estadoVersion } from "../../lib/dominio";
import { TIPOS_NODO, catDe } from "@/lib/nodos";

const NODO_W = 184;
const NODO_H = 64;
const GRID = 20; // paso de la grilla de puntos del lienzo (para snap-to-grid)
// Tamaño MÍNIMO del «mundo» del lienzo. Crece con el contenido: un flujo
// largo necesita más superficie, y con el mundo fijo los nodos que caían más
// allá del borde quedaban inalcanzables — pasaba al ordenar el diagrama
// automáticamente, que estira la cadena a lo ancho.
//
// El crecimiento va por saltos de 400px y no al milímetro: si siguiera cada
// arrastre, el minimapa cambiaría de escala mientras se mueve un nodo y
// dejaría de servir como referencia.
const MUNDO_MIN_W = 2200;
const MUNDO_MIN_H = 1300;
const PASO_MUNDO = 400;

function tamanoMundo(nodos) {
  const alBorde = (v, min) => Math.max(min, Math.ceil((v + 300) / PASO_MUNDO) * PASO_MUNDO);
  return {
    w: alBorde(Math.max(0, ...nodos.map((n) => n.x + NODO_W)), MUNDO_MIN_W),
    h: alBorde(Math.max(0, ...nodos.map((n) => n.y + NODO_H)), MUNDO_MIN_H),
  };
}
const PALETA = TIPOS_NODO.map((tipo) => ({ tipo, ...catDe(tipo) }));

// Operadores de regla en lenguaje natural (los usa el RuleBuilder y la etiqueta
// automática de las ramas de Decisión en el lienzo).
// Roles que pueden registrar una atención. No están todos los del sistema: un
// configurador o un admin no atienden pacientes, y ofrecerlos acá invitaría a
// modelar un flujo que después nadie puede ejecutar.
const ROLES_FIRMA = [
  { value: "medico", label: "Médico / profesional" },
  { value: "enfermeria", label: "Enfermería" },
  { value: "administrativo", label: "Administrativo" },
  { value: "jefe_area", label: "Jefe / Supervisor de área" },
];

const OPERADOR_LABEL = {
  "=": "es igual a", "!=": "es distinto de",
  ">": "mayor que", "<": "menor que", ">=": "mayor o igual que", "<=": "menor o igual que",
  contiene: "contiene", no_contiene: "no contiene",
  en: "es alguno de", no_en: "no es ninguno de",
  entre: "está entre", vacio: "está vacío", no_vacio: "tiene algún valor",
};

// Operadores que no llevan valor: preguntan por la presencia del dato.
const SIN_VALOR = new Set(["vacio", "no_vacio"]);
// Operadores cuyo valor es una lista separada por comas.
const CON_LISTA = new Set(["en", "no_en", "entre"]);

/**
 * Una condición guardada es una hoja `{campo, operador, valor}` o una compuesta
 * `{op, reglas}`. Acá se trabaja siempre con la lista, y al guardar se vuelve a
 * la forma mínima: así las conexiones de una sola regla —que son todas las ya
 * existentes— conservan su formato y no hace falta migrar nada.
 *
 * El motor admite anidar («(A y B) o C»); este constructor es plano. Cubre el
 * caso real («mayor de 65 Y dolor torácico») sin el costo de un editor de
 * árboles; si algún flujo lo necesita, la capacidad ya está del lado del motor.
 */
function condicionALista(cond) {
  if (!cond || (!cond.campo && !cond.reglas)) return { op: "y", reglas: [] };
  if (cond.reglas) return { op: cond.op || "y", reglas: cond.reglas.filter((r) => !r.reglas) };
  return { op: "y", reglas: [cond] };
}

function listaACondicion(op, reglas) {
  const utiles = reglas.filter((r) => r.campo);
  if (utiles.length === 0) return {};        // rama por defecto
  if (utiles.length === 1) return utiles[0]; // forma hoja, como estaba
  return { op, reglas: utiles };
}

export default function FlujoEditor() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [flujo, setFlujo] = useState(null);
  const [version, setVersion] = useState(null); // versión completa (nodos+conexiones)
  const [verId, setVerId] = useState(null);
  /*
   * Selección de nodos.
   *
   * El conjunto es la ÚNICA fuente de verdad y `sel` se deriva de él: con dos
   * estados en paralelo (uno para el panel y otro para las acciones masivas) se
   * desincronizan a la primera. El panel de propiedades sólo tiene sentido con
   * un nodo elegido; con varios muestra las acciones del grupo.
   */
  const [seleccion, setSeleccion] = useState(() => new Set());
  const sel = seleccion.size === 1 ? [...seleccion][0] : null;
  const seleccionRef = useRef(seleccion);
  seleccionRef.current = seleccion;

  const seleccionarSolo = useCallback((id) => setSeleccion(id == null ? new Set() : new Set([id])), []);
  const alternarSeleccion = useCallback((id) => setSeleccion((s) => {
    const n = new Set(s);
    if (n.has(id)) n.delete(id);
    else n.add(id);
    return n;
  }), []);
  // Alias para no reescribir las decenas de `setSel(...)` que ya existían.
  const setSel = seleccionarSolo;
  const [selConexion, setSelConexion] = useState(null); // id de conexión seleccionada en el lienzo
  const [hoverConn, setHoverConn] = useState(null); // id de conexión bajo el cursor
  const [problemas, setProblemas] = useState(null);
  const [conectarDesde, setConectarDesde] = useState(null);
  const [campos, setCampos] = useState([]); // campos disponibles para reglas
  const [cargando, setCargando] = useState(true);
  const [errorCarga, setErrorCarga] = useState(null);
  const [sim, setSim] = useState(null); // modo Probar: {current, valores, camino, fin}
  const [repro, setRepro] = useState(null); // Reproducir: {camino, idx}
  const [guardado, setGuardado] = useState("idle"); // idle | guardando | guardado | error
  const [toast, setToast] = useState(null); // { tipo:'ok'|'error', msg, accion?:{label,fn} }
  const [publicando, setPublicando] = useState(false);
  const [validando, setValidando] = useState(false);
  const guardadoTimer = useRef(null);
  const toastTimer = useRef(null);

  // Indicador de autosave (barra superior) + feedback de error de red.
  function marcarGuardando() { setGuardado("guardando"); }
  function marcarGuardado() {
    setGuardado("guardado");
    clearTimeout(guardadoTimer.current);
    guardadoTimer.current = setTimeout(() => setGuardado("idle"), 1800);
  }
  function mostrarToast(t, ms = 4000) {
    clearTimeout(toastTimer.current);
    setToast(t);
    toastTimer.current = setTimeout(() => setToast(null), ms);
  }
  function marcarError() {
    setGuardado("error");
    mostrarToast({ tipo: "error", msg: "No se pudo guardar. Revisá tu conexión e intentá de nuevo." });
  }

  const cargarVersion = useCallback(async (vid) => {
    const v = await api.get(`/versiones-flujo/${vid}/`);
    setVersion(v);
  }, []);

  const cargarTodo = useCallback(async () => {
    setCargando(true);
    setErrorCarga(null);
    try {
      const f = await api.get(`/flujos/${id}/`);
      setFlujo(f);
      const v = (f.versiones || [])[0];
      if (v) {
        setVerId(v.id);
        await cargarVersion(v.id);
      }
      // Campos disponibles para reglas: los de los formularios de la institución.
      const fs = await api.get(`/formularios/?institucion=${f.institucion}`);
      const lista = (fs.results || fs).flatMap((form) =>
        (form.campos || []).map((c) => ({ id: c.id, label: c.label, formulario: form.titulo, formularioId: form.id, opciones: c.opciones, tipo: c.tipo, requerido: c.requerido }))
      );
      setCampos(lista);
    } catch (e) {
      setErrorCarga(e?.data?.detail || e?.message || "No se pudo cargar el flujo.");
    } finally {
      setCargando(false);
    }
  }, [id, cargarVersion]);

  useEffect(() => {
    cargarTodo();
  }, [cargarTodo]);

  // --- Drag de nodos (Pointer Events: mouse + touch + lápiz) ---------------
  const drag = useRef(null);
  const canvasRef = useRef(null);
  // Ref con la versión actual: el listener se monta una sola vez y lee de acá,
  // así no re-suscribimos en cada movimiento ni quedan listeners colgados.
  const versionRef = useRef(version);
  versionRef.current = version;
  const [dragId, setDragId] = useState(null);
  // Arrastre de conexión desde el handle de salida de un nodo (línea-fantasma).
  const conn = useRef(null);
  const [ghost, setGhost] = useState(null); // { x1, y1, x2, y2 }
  // Zoom del lienzo (0.4–1.6). zoomRef permite leerlo desde los listeners de
  // puntero montados una sola vez sin re-suscribir.
  const [zoom, setZoom] = useState(1);
  const zoomRef = useRef(1);
  zoomRef.current = zoom;
  const scrollRef = useRef(null);

  const LIMITE_ZOOM = [0.3, 2];
  const acotarZoom = (z) => Math.min(LIMITE_ZOOM[1], Math.max(LIMITE_ZOOM[0], +z.toFixed(3)));

  // Acercar/alejar con los botones de la barra de zoom.
  function zoomBoton(delta) {
    setZoom((z) => acotarZoom(z + delta));
  }

  /**
   * Zoom con la rueda, anclado al cursor.
   *
   * Anclarlo importa: si el zoom sale del origen, acercarse a un nodo del medio
   * del lienzo lo manda fuera de la pantalla y hay que volver a buscarlo. Con el
   * ancla, el punto que está bajo el mouse se queda donde está.
   *
   * Con Ctrl/Cmd —el gesto estándar de zoom, y el que hace el pellizco en un
   * trackpad— o con la rueda sola, porque en un flujo de 40 nodos moverse es
   * sobre todo acercarse y alejarse. Shift+rueda queda para el scroll lateral.
   */
  function onRueda(e) {
    if (e.shiftKey) return; // scroll horizontal del navegador
    const cont = scrollRef.current;
    if (!cont) return;
    e.preventDefault();

    const z = zoomRef.current;
    // deltaMode 1 = líneas (Firefox); se normaliza para que no salte de golpe.
    const paso = e.deltaMode === 1 ? e.deltaY * 16 : e.deltaY;
    const z2 = acotarZoom(z * Math.exp(-paso * 0.0015));
    if (z2 === z) return;

    const caja = cont.getBoundingClientRect();
    const mx = e.clientX - caja.left;
    const my = e.clientY - caja.top;
    // Punto del lienzo (sin escalar) que está bajo el cursor.
    const cx = (cont.scrollLeft + mx) / z;
    const cy = (cont.scrollTop + my) / z;

    setZoom(z2);
    // El scroll se ajusta después de que el sizer haya cambiado de tamaño.
    requestAnimationFrame(() => {
      cont.scrollLeft = Math.max(0, cx * z2 - mx);
      cont.scrollTop = Math.max(0, cy * z2 - my);
    });
  }

  /*
   * La rueda se suscribe a mano porque `onWheel` de React es pasivo y no puede
   * llamar a `preventDefault`.
   *
   * Se engancha con una ref-callback y no con un `useEffect`: mientras el flujo
   * carga, el editor devuelve un spinner y el contenedor del lienzo todavía no
   * existe, así que el efecto corría con `scrollRef.current` en null y el zoom
   * no se enganchaba nunca — sin ningún error a la vista. Con la ref-callback,
   * React avisa exactamente cuando el nodo entra y sale del DOM; no hay lista de
   * dependencias que adivinar.
   */
  const onRuedaRef = useRef(onRueda);
  onRuedaRef.current = onRueda;
  const manejarRueda = useCallback((e) => onRuedaRef.current(e), []);

  const montarScroll = useCallback((el) => {
    if (scrollRef.current) scrollRef.current.removeEventListener("wheel", manejarRueda);
    scrollRef.current = el;
    if (el) el.addEventListener("wheel", manejarRueda, { passive: false });
  }, [manejarRueda]);
  /**
   * Ordena el diagrama solo: columnas por profundidad, filas dentro de cada una.
   *
   * Sirve para dos momentos concretos: un flujo que creció a los tirones y quedó
   * enredado, y uno recién importado o duplicado donde todos los nodos están
   * amontonados.
   *
   * Se registra como UNA operación del historial. Es lo que lo hace usable:
   * alguien pasó un rato acomodando ese diagrama a mano y un clic no puede
   * perder ese trabajo sin vuelta atrás.
   */
  async function ordenar() {
    const v = versionRef.current;
    const nodos = v?.nodos || [];
    if (nodos.length < 2) return;

    /*
     * Profundidad por NIVELES desde el inicio (recorrido en anchura).
     *
     * No por «camino más largo»: un flujo clínico tiene ciclos —observar,
     * reevaluar, volver a observar— y ahí la relajación por camino más largo no
     * converge, sigue sumando una vuelta por pasada. Con este mismo flujo daba
     * columnas 0,1,2,3 y de golpe 47,48,49,50: el diagrama quedaba estirado
     * cuatro mil píxeles y fuera de la pantalla.
     *
     * Por niveles cada nodo se fija la primera vez que se lo alcanza, así que un
     * ciclo no lo mueve nunca más.
     */
    const salidas = new Map();
    for (const c of v.conexiones) {
      if (!salidas.has(c.origen)) salidas.set(c.origen, []);
      salidas.get(c.origen).push(c.destino);
    }
    const prof = new Map();
    const raiz = nodos.find((n) => n.tipo === "inicio") || nodos[0];
    let frontera = [raiz.id];
    prof.set(raiz.id, 0);
    let nivel = 0;
    while (frontera.length) {
      nivel += 1;
      const siguiente = [];
      for (const id of frontera) {
        for (const d of salidas.get(id) || []) {
          if (prof.has(d)) continue;
          prof.set(d, nivel);
          siguiente.push(d);
        }
      }
      frontera = siguiente;
    }
    // Los que no cuelgan del inicio (todavía sin conectar) van al final.
    for (const n of nodos) if (!prof.has(n.id)) prof.set(n.id, nivel);

    const columnas = new Map();
    for (const n of nodos) {
      const d = prof.get(n.id);
      if (!columnas.has(d)) columnas.set(d, []);
      columnas.get(d).push(n);
    }

    // Dentro de cada columna, se ordena por la altura promedio de los nodos que
    // apuntan a cada uno (baricentro). Es el truco barato que evita que las
    // conexiones se crucen: sin esto el orden sería arbitrario y el diagrama
    // ordenado quedaría más enredado que el original.
    const fila = new Map();
    for (const d of [...columnas.keys()].sort((a, b) => a - b)) {
      const lista = columnas.get(d);
      lista.sort((a, b) => {
        const centro = (n) => {
          const previos = v.conexiones
            .filter((c) => c.destino === n.id && fila.has(c.origen))
            .map((c) => fila.get(c.origen));
          return previos.length ? previos.reduce((s, x) => s + x, 0) / previos.length : n.y / 200;
        };
        return centro(a) - centro(b);
      });
      lista.forEach((n, i) => fila.set(n.id, i));
    }

    const PAD = 60;
    const GAP_X = 110;
    const GAP_Y = 40;
    const antes = new Map();
    const despues = new Map();
    for (const n of nodos) {
      antes.set(n.id, { x: n.x, y: n.y });
      despues.set(n.id, {
        x: PAD + prof.get(n.id) * (NODO_W + GAP_X),
        y: PAD + fila.get(n.id) * (NODO_H + GAP_Y),
      });
    }
    const quedaIgual = [...despues].every(([id, p]) => {
      const o = antes.get(id);
      return o.x === p.x && o.y === p.y;
    });
    if (quedaIgual) return;

    const mover = (m) => Promise.all([...m].map(([id, p]) => aplicarPos(id, p.x, p.y)));
    registrarCambio(() => mover(antes), () => mover(despues));
    // Se ESPERA a que las posiciones nuevas estén aplicadas antes de encuadrar:
    // `ajustar` lee el bounding box de `versionRef`, y lanzado un frame después
    // lo calculaba con las posiciones viejas y dejaba el lienzo mirando a un
    // lugar vacío.
    await mover(despues);
    mostrarToast({ tipo: "ok", msg: "Diagrama ordenado", accion: { txt: "Deshacer", fn: deshacer } });
    ajustar();
  }

  // Ajustar al contenido: calcula el bounding box de los nodos, elige el zoom
  // que lo encuadra y centra el lienzo en esa zona.
  function ajustar() {
    const ns = versionRef.current?.nodos || [];
    const cont = scrollRef.current;
    if (!ns.length || !cont) { setZoom(1); return; }
    const minX = Math.min(...ns.map((n) => n.x));
    const minY = Math.min(...ns.map((n) => n.y));
    const maxX = Math.max(...ns.map((n) => n.x + NODO_W));
    const maxY = Math.max(...ns.map((n) => n.y + NODO_H));
    const w = Math.max(1, maxX - minX), h = Math.max(1, maxY - minY);
    const pad = 80;
    const k = Math.min(2, Math.max(0.3, Math.min((cont.clientWidth - pad) / w, (cont.clientHeight - pad) / h)));
    setZoom(k);
    requestAnimationFrame(() => {
      cont.scrollLeft = Math.max(0, minX * k - (cont.clientWidth - w * k) / 2);
      cont.scrollTop = Math.max(0, minY * k - (cont.clientHeight - h * k) / 2);
    });
  }
  /**
   * Trae un nodo al centro de la vista y lo selecciona.
   *
   * Es la pieza que le falta a un lienzo grande: sin esto, encontrar un nodo en
   * un flujo de 40 es arrastrar el scroll a ojo hasta dar con él.
   */
  function irAlNodo(id) {
    const n = versionRef.current?.nodos.find((x) => x.id === id);
    const cont = scrollRef.current;
    if (!n || !cont) return;
    const z = zoomRef.current;
    cont.scrollTo({
      left: Math.max(0, (n.x + NODO_W / 2) * z - cont.clientWidth / 2),
      top: Math.max(0, (n.y + NODO_H / 2) * z - cont.clientHeight / 2),
      behavior: "smooth",
    });
    setSel(id);
    setSelConexion(null);
  }

  // Historial de cambios reversibles (mover/editar nodos y conexiones). Cada
  // entrada guarda su operación inversa concreta (un PATCH), por eso es segura:
  // no recrea ids. Crear/borrar nodos quedan fuera (el borrado tiene su «Deshacer»).
  const undoStack = useRef([]);
  const redoStack = useRef([]);
  const [, setHistTick] = useState(0);
  // Paneles laterales colapsables (para pantallas chicas / tablets).
  const [paletaAbierta, setPaletaAbierta] = useState(true);
  const [panelAbierto, setPanelAbierto] = useState(true);

  function onNodoPointerDown(e, nodo) {
    e.stopPropagation();
    if (e.button != null && e.button !== 0) return; // solo botón primario

    // Shift/Ctrl suma o quita de la selección sin arrastrar: es el gesto que
    // todo el mundo espera y evita tener que encerrar los nodos con la marquesina.
    if (e.shiftKey || e.ctrlKey || e.metaKey) {
      alternarSeleccion(nodo.id);
      return;
    }

    // Agarrar un nodo que YA está en la selección arrastra el grupo entero;
    // agarrar uno de afuera pasa a seleccionarlo solo a él.
    const enGrupo = seleccionRef.current.has(nodo.id) && seleccionRef.current.size > 1;
    if (!enGrupo) seleccionarSolo(nodo.id);

    const ids = enGrupo ? [...seleccionRef.current] : [nodo.id];
    const rect = canvasRef.current.getBoundingClientRect();
    const z = zoomRef.current;
    drag.current = {
      id: nodo.id,
      dx: (e.clientX - rect.left) / z - nodo.x,
      dy: (e.clientY - rect.top) / z - nodo.y,
      // Posición de partida de cada nodo movido: hace falta para el snap y para
      // registrar el movimiento en el historial como una sola operación.
      origen: new Map(
        ids.map((id) => {
          const n = versionRef.current.nodos.find((x) => x.id === id);
          return [id, { x: n.x, y: n.y }];
        }),
      ),
      moved: false,
    };
    setDragId(nodo.id);
    try { e.currentTarget.setPointerCapture(e.pointerId); } catch { /* no soportado */ }
  }

  useEffect(() => {
    function onMove(e) {
      if (!drag.current) return;
      const rect = canvasRef.current.getBoundingClientRect();
      const z = zoomRef.current;
      const { id, dx, dy, origen } = drag.current;
      const x = Math.max(0, (e.clientX - rect.left) / z - dx);
      const y = Math.max(0, (e.clientY - rect.top) / z - dy);
      // Todo el grupo se mueve el mismo delta que el nodo agarrado: así conserva
      // su forma en vez de amontonarse en el cursor.
      const base = origen.get(id);
      const ddx = x - base.x;
      const ddy = y - base.y;
      drag.current.moved = true;
      setVersion((v) => ({
        ...v,
        nodos: v.nodos.map((n) => {
          const o = origen.get(n.id);
          return o ? { ...n, x: Math.max(0, o.x + ddx), y: Math.max(0, o.y + ddy) } : n;
        }),
      }));
    }
    async function onUp() {
      if (!drag.current) return;
      const { moved, origen } = drag.current;
      drag.current = null;
      setDragId(null);
      if (!moved) return;

      // Snap a la grilla de 20px que dibuja el lienzo: flujos prolijos sin esfuerzo.
      const destino = new Map();
      for (const [id] of origen) {
        const n = versionRef.current?.nodos.find((x) => x.id === id);
        if (n) destino.set(id, { x: Math.round(n.x / GRID) * GRID, y: Math.round(n.y / GRID) * GRID });
      }
      const cambio = [...destino].some(([id, d]) => {
        const o = origen.get(id);
        return d.x !== o.x || d.y !== o.y;
      });

      const mover = (posiciones) => Promise.all(
        [...posiciones].map(([id, p]) => aplicarPos(id, p.x, p.y)),
      );
      if (!cambio) {
        // Sin desplazamiento neto: re-encajar en la grilla sin tocar el historial.
        setVersion((v) => ({
          ...v,
          nodos: v.nodos.map((n) => (destino.has(n.id) ? { ...n, ...destino.get(n.id) } : n)),
        }));
        return;
      }
      // Una sola entrada de historial para todo el grupo: deshacer tiene que
      // devolver el movimiento completo, no nodo por nodo.
      registrarCambio(() => mover(origen), () => mover(destino));
      mover(destino);
    }
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
  }, []);

  // Inicia el arrastre de una conexión desde el handle de salida de un nodo.
  function onHandlePointerDown(e, nodo) {
    e.stopPropagation();
    if (e.button != null && e.button !== 0) return;
    conn.current = { fromId: nodo.id };
    const rect = canvasRef.current.getBoundingClientRect();
    const z = zoomRef.current;
    setGhost({ x1: nodo.x + NODO_W, y1: nodo.y + NODO_H / 2, x2: (e.clientX - rect.left) / z, y2: (e.clientY - rect.top) / z });
    try { e.currentTarget.setPointerCapture(e.pointerId); } catch { /* no soportado */ }
  }

  useEffect(() => {
    function onMove(e) {
      if (!conn.current) return;
      const rect = canvasRef.current.getBoundingClientRect();
      const z = zoomRef.current;
      setGhost((g) => (g ? { ...g, x2: (e.clientX - rect.left) / z, y2: (e.clientY - rect.top) / z } : g));
    }
    async function onUp(e) {
      if (!conn.current) return;
      const from = conn.current.fromId;
      conn.current = null;
      setGhost(null);
      const host = document.elementFromPoint(e.clientX, e.clientY)?.closest?.("[data-nodo]");
      const toId = host ? Number(host.getAttribute("data-nodo")) : null;
      if (toId == null || toId === from) return;
      if (versionRef.current.conexiones.some((c) => c.origen === from && c.destino === toId)) return;
      marcarGuardando();
      try {
        const c = await api.post("/conexiones/", { version: verId, origen: from, destino: toId });
        setVersion((v) => ({ ...v, conexiones: [...v.conexiones, c] }));
        marcarGuardado();
      } catch { marcarError(); }
    }
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
  }, [verId]);

  // --- Acciones ------------------------------------------------------------
  // Coloca el nodo nuevo cerca del centro del área visible del lienzo (no
  // apilado en una esquina) y alineado a la grilla.
  function posicionNuevoNodo() {
    const cont = canvasRef.current?.parentElement;
    const off = ((version?.nodos.length || 0) % 5) * GRID;
    const bx = cont ? cont.scrollLeft + cont.clientWidth / 2 - NODO_W / 2 : 360;
    const by = cont ? cont.scrollTop + cont.clientHeight / 2 - NODO_H / 2 : 160;
    return { x: Math.max(0, Math.round((bx + off) / GRID) * GRID), y: Math.max(0, Math.round((by + off) / GRID) * GRID) };
  }

  async function agregarNodo(tipo) {
    const cat = catDe(tipo);
    const { x, y } = posicionNuevoNodo();
    marcarGuardando();
    try {
      const n = await api.post("/nodos/", { version: verId, tipo, titulo: cat.name, x, y });
      setVersion((v) => ({ ...v, nodos: [...v.nodos, n] }));
      setSel(n.id);
      marcarGuardado();
    } catch { marcarError(); }
  }

  async function clickNodo(nodo, e) {
    // Con modificador, el pointerdown ya resolvió la selección: volver a fijarla
    // acá la reduciría a un solo nodo y shift+clic no serviría de nada.
    if (e && (e.shiftKey || e.ctrlKey || e.metaKey)) return;
    if (conectarDesde && conectarDesde !== nodo.id) {
      // No duplicar una conexión que ya existe entre ese par.
      if (version.conexiones.some((c) => c.origen === conectarDesde && c.destino === nodo.id)) {
        setConectarDesde(null);
        return;
      }
      const origen = conectarDesde;
      setConectarDesde(null);
      marcarGuardando();
      try {
        const c = await api.post("/conexiones/", { version: verId, origen, destino: nodo.id });
        setVersion((v) => ({ ...v, conexiones: [...v.conexiones, c] }));
        marcarGuardado();
      } catch { marcarError(); }
      return;
    }
    setSel(nodo.id);
  }

  // --- Historial (undo/redo) ----------------------------------------------
  function registrarCambio(undo, redo) {
    undoStack.current.push({ undo, redo });
    if (undoStack.current.length > 60) undoStack.current.shift();
    redoStack.current = [];
    setHistTick((t) => t + 1);
  }
  async function deshacer() {
    const cmd = undoStack.current.pop();
    if (!cmd) return;
    redoStack.current.push(cmd);
    setHistTick((t) => t + 1);
    await cmd.undo();
  }
  async function rehacer() {
    const cmd = redoStack.current.pop();
    if (!cmd) return;
    undoStack.current.push(cmd);
    setHistTick((t) => t + 1);
    await cmd.redo();
  }

  // Aplicadores «silenciosos»: mutan + persisten SIN registrar en el historial
  // (los usan tanto las acciones del usuario como el propio undo/redo).
  async function aplicarPos(nodoId, x, y) {
    if (!versionRef.current.nodos.some((n) => n.id === nodoId)) return;
    setVersion((v) => ({ ...v, nodos: v.nodos.map((n) => (n.id === nodoId ? { ...n, x, y } : n)) }));
    marcarGuardando();
    try { await api.patch(`/nodos/${nodoId}/`, { x, y }); marcarGuardado(); } catch { marcarError(); }
  }
  async function aplicarNodo(nodoId, cambios) {
    const prev = versionRef.current;
    setVersion((v) => ({ ...v, nodos: v.nodos.map((x) => (x.id === nodoId ? { ...x, ...cambios } : x)) }));
    marcarGuardando();
    try {
      const n = await api.patch(`/nodos/${nodoId}/`, cambios);
      setVersion((v) => ({ ...v, nodos: v.nodos.map((x) => (x.id === nodoId ? n : x)) }));
      marcarGuardado();
    } catch { setVersion(prev); marcarError(); }
  }

  async function actualizarNodo(nodoId, cambios) {
    const prev = version.nodos.find((n) => n.id === nodoId);
    if (prev) {
      const inverso = {};
      for (const k of Object.keys(cambios)) inverso[k] = prev[k];
      registrarCambio(() => aplicarNodo(nodoId, inverso), () => aplicarNodo(nodoId, cambios));
    }
    await aplicarNodo(nodoId, cambios);
  }

  async function borrarNodo(nodoId) {
    const nodo = version.nodos.find((n) => n.id === nodoId);
    const conexiones = version.conexiones.filter((c) => c.origen === nodoId || c.destino === nodoId);
    const snapshot = version;
    setVersion((v) => ({
      ...v,
      nodos: v.nodos.filter((n) => n.id !== nodoId),
      conexiones: v.conexiones.filter((c) => c.origen !== nodoId && c.destino !== nodoId),
    }));
    setSel(null);
    if (conectarDesde === nodoId) setConectarDesde(null);
    marcarGuardando();
    try {
      await api.del(`/nodos/${nodoId}/`);
      marcarGuardado();
      mostrarToast({
        tipo: "ok",
        msg: `Se eliminó «${nodo?.titulo}»${conexiones.length ? ` y ${conexiones.length} conexión${conexiones.length > 1 ? "es" : ""}` : ""}.`,
        accion: { label: "Deshacer", fn: () => restaurarNodo(nodo, conexiones) },
      }, 7000);
    } catch { setVersion(snapshot); marcarError(); }
  }

  // Rehace un nodo borrado y sus conexiones (remapeando el id al nuevo nodo).
  async function restaurarNodo(nodo, conexiones) {
    setToast(null);
    marcarGuardando();
    try {
      const n = await api.post("/nodos/", {
        version: verId, tipo: nodo.tipo, titulo: nodo.titulo, descripcion: nodo.descripcion,
        x: nodo.x, y: nodo.y, config: nodo.config || {}, formulario: nodo.formulario, grupos: nodo.grupos || [],
      });
      const nuevas = [];
      for (const c of conexiones) {
        // La otra punta debe seguir existiendo; si no, se omite esa conexión.
        const origen = c.origen === nodo.id ? n.id : c.origen;
        const destino = c.destino === nodo.id ? n.id : c.destino;
        const existe = (gid) => gid === n.id || versionRef.current.nodos.some((x) => x.id === gid);
        if (!existe(origen) || !existe(destino)) continue;
        nuevas.push(await api.post("/conexiones/", { version: verId, origen, destino, etiqueta: c.etiqueta, condicion: c.condicion }));
      }
      setVersion((v) => ({ ...v, nodos: [...v.nodos, n], conexiones: [...v.conexiones, ...nuevas] }));
      setSel(n.id);
      marcarGuardado();
    } catch { marcarError(); }
  }

  async function borrarConexion(cid) {
    const snapshot = version;
    setVersion((v) => ({ ...v, conexiones: v.conexiones.filter((c) => c.id !== cid) }));
    if (selConexion === cid) setSelConexion(null);
    marcarGuardando();
    try { await api.del(`/conexiones/${cid}/`); marcarGuardado(); }
    catch { setVersion(snapshot); marcarError(); }
  }

  async function aplicarConexion(cid, cambios) {
    const prev = versionRef.current;
    setVersion((v) => ({ ...v, conexiones: v.conexiones.map((x) => (x.id === cid ? { ...x, ...cambios } : x)) }));
    marcarGuardando();
    try {
      const c = await api.patch(`/conexiones/${cid}/`, cambios);
      setVersion((v) => ({ ...v, conexiones: v.conexiones.map((x) => (x.id === cid ? c : x)) }));
      marcarGuardado();
    } catch { setVersion(prev); marcarError(); }
  }

  async function actualizarConexion(cid, cambios) {
    const prev = version.conexiones.find((c) => c.id === cid);
    if (prev) {
      const inverso = {};
      for (const k of Object.keys(cambios)) inverso[k] = prev[k];
      registrarCambio(() => aplicarConexion(cid, inverso), () => aplicarConexion(cid, cambios));
    }
    await aplicarConexion(cid, cambios);
  }

  async function validar() {
    setValidando(true);
    try {
      const r = await api.get(`/versiones-flujo/${verId}/validar/`);
      setProblemas(r);
    } catch { mostrarToast({ tipo: "error", msg: "No se pudo validar el flujo." }); }
    finally { setValidando(false); }
  }
  async function publicar() {
    setPublicando(true);
    try {
      await api.post(`/versiones-flujo/${verId}/publicar/`, {});
      await cargarVersion(verId);
      const f = await api.get(`/flujos/${id}/`);
      setFlujo(f);
      setProblemas({ problemas: [], errores: 0, avisos: 0, puede_publicar: true, publicado: true });
      mostrarToast({ tipo: "ok", msg: "Versión publicada ✓" });
    } catch (e) {
      if (e?.data?.problemas) setProblemas({ ...e.data, errores: e.data.problemas.filter((p) => p.sev === "error").length });
      else mostrarToast({ tipo: "error", msg: "No se pudo publicar la versión." });
    } finally { setPublicando(false); }
  }

  /* --- Modo Probar -----------------------------------------------------------
   *
   * Corre contra el MOTOR REAL (`POST /versiones-flujo/:id/ensayo/`), que ejecuta
   * el caso en una transacción y la deshace. Antes esto lo resolvía un simulador
   * propio en el navegador que espejaba a `motor.py`: 83 líneas contra 800, ya
   * divergidas —no sabía de grupos responsables, boxes, prioridad de triage,
   * estudios de ida y vuelta ni de la regla de firma médica—. O sea que el botón
   * mentía, en silencio, y cada vez que el motor creciera iba a mentir más.
   *
   * El ensayo es sin estado: se guardan los pasos dados y en cada avance se
   * reenvía la lista completa. Reproducible y sin sesión que se desincronice.
   */
  const [ensayando, setEnsayando] = useState(false);

  async function correrEnsayo(pasos) {
    setEnsayando(true);
    try {
      const r = await api.post(`/versiones-flujo/${version.id}/ensayo/`, { pasos });
      const estado = {
        pasos,
        camino: (r.camino || []).map((p) => p.nodo),
        current: r.parada?.nodo ?? null,
        acciones: r.parada?.acciones || [],
        fin: r.termino,
        // Sin parada, sin fin y sin error = el motor se quedó sin conexión.
        sinSalida: !r.termino && r.parada == null && !r.error,
        error: r.error,
        estado: r.estado,
        prioridad: r.prioridad,
      };
      setSim(estado);
      return estado;
    } catch (e) {
      mostrarToast({ tipo: "error", msg: e?.data?.detail || "No se pudo probar el flujo." });
      return null;
    } finally {
      setEnsayando(false);
    }
  }

  function iniciarSim() {
    setProblemas(null); setSel(null); setRepro(null);
    correrEnsayo([]);
  }
  function avanzarSim(datos = {}) {
    correrEnsayo([...(sim?.pasos || []), datos]);
  }

  // --- Reproducir (animación del recorrido) -------------------------------
  // Anima el recorrido del último ensayo. Si no hay ninguno, corre uno: el camino
  // llega hasta la primera parada, que es hasta donde un caso avanza SOLO. Antes
  // se dibujaba un camino hasta el final atravesando formularios sin datos, que
  // es un recorrido que en la realidad no ocurre.
  async function reproducir() {
    setProblemas(null); setSel(null);
    const camino = sim?.camino?.length ? sim.camino : (await correrEnsayo([]))?.camino;
    if (!camino?.length) return;
    setRepro({ camino, idx: 0 });
  }
  useEffect(() => {
    if (!repro) return;
    // Seguir el token: mantener el nodo en foco siempre visible en el viewport.
    const nid = repro.camino[repro.idx];
    const el = canvasRef.current?.querySelector(`[data-nodo="${nid}"]`);
    el?.scrollIntoView({ behavior: "smooth", block: "center", inline: "center" });
    if (repro.idx >= repro.camino.length - 1) {
      const t = setTimeout(() => setRepro(null), 1200);
      return () => clearTimeout(t);
    }
    const t = setTimeout(() => setRepro((r) => (r ? { ...r, idx: r.idx + 1 } : r)), 750);
    return () => clearTimeout(t);
  }, [repro]);

  /* --- Copiar y pegar --------------------------------------------------------
   *
   * El portapapeles vive en memoria y no en el del sistema: lo que se copia son
   * nodos con su configuración y las conexiones ENTRE ellos, que no tienen
   * representación razonable como texto.
   *
   * Copiar un tramo y pegarlo es lo que convierte «rehacer un circuito parecido»
   * de veinte clics en dos. Las conexiones que salen o entran desde afuera del
   * grupo no se copian: apuntarían a nodos que el pegado no reprodujo.
   */
  // Ref y no estado: Ctrl+D copia y pega en el MISMO tick, y el estado de
  // React todavía no está actualizado cuando corre `pegar()` — con `useState`
  // el duplicado leía el portapapeles anterior (vacío) y no hacía nada.
  const portapapeles = useRef(null);

  function copiar() {
    const ids = new Set(seleccionRef.current);
    if (!ids.size) return;
    const v = versionRef.current;
    const nodos = v.nodos.filter((n) => ids.has(n.id));
    portapapeles.current = {
      nodos: nodos.map((n) => ({ tipo: n.tipo, titulo: n.titulo, x: n.x, y: n.y, config: n.config, formulario: n.formulario })),
      // Índices dentro de `nodos`, no ids: al pegar los ids son otros.
      conexiones: v.conexiones
        .filter((c) => ids.has(c.origen) && ids.has(c.destino))
        .map((c) => ({
          origen: nodos.findIndex((n) => n.id === c.origen),
          destino: nodos.findIndex((n) => n.id === c.destino),
          etiqueta: c.etiqueta,
          condicion: c.condicion,
        })),
    };
    mostrarToast({ tipo: "ok", msg: `${nodos.length === 1 ? "Nodo copiado" : `${nodos.length} nodos copiados`}` });
  }

  async function pegar() {
    const pp = portapapeles.current;
    if (!pp?.nodos.length) return;
    marcarGuardando();
    try {
      // Desplazamiento fijo para que la copia no tape al original.
      const OFFSET = GRID * 2;
      const creados = [];
      for (const n of pp.nodos) {
        creados.push(await api.post("/nodos/", {
          version: verId, tipo: n.tipo, titulo: n.titulo,
          x: n.x + OFFSET, y: n.y + OFFSET,
          config: n.config || {}, formulario: n.formulario || null,
        }));
      }
      const nuevasConex = [];
      for (const c of pp.conexiones) {
        nuevasConex.push(await api.post("/conexiones/", {
          version: verId,
          origen: creados[c.origen].id,
          destino: creados[c.destino].id,
          etiqueta: c.etiqueta || "",
          condicion: c.condicion || {},
        }));
      }
      setVersion((v) => ({
        ...v,
        nodos: [...v.nodos, ...creados],
        conexiones: [...v.conexiones, ...nuevasConex],
      }));
      // Lo pegado queda seleccionado: se puede mover en bloque enseguida.
      setSeleccion(new Set(creados.map((n) => n.id)));
      marcarGuardado();
    } catch {
      marcarError();
    }
  }

  /* --- Marquesina ------------------------------------------------------------
   *
   * Arrastrar sobre el lienzo vacío encierra nodos. Es la otra mitad de la
   * multi-selección: con shift+clic se juntan tres o cuatro, pero para agarrar
   * una rama entera hay que poder rodearla.
   */
  const [marquesina, setMarquesina] = useState(null); // {x1,y1,x2,y2} en coords del lienzo
  const marcaRef = useRef(null);
  const ignorarClick = useRef(false);

  function onLienzoPointerDown(e) {
    // Sólo el fondo, con el botón primario y sin estar tendiendo una conexión.
    if (e.target !== e.currentTarget || e.button !== 0 || conectarDesde) return;
    const rect = canvasRef.current.getBoundingClientRect();
    const z = zoomRef.current;
    const x = (e.clientX - rect.left) / z;
    const y = (e.clientY - rect.top) / z;
    marcaRef.current = { x1: x, y1: y, x2: x, y2: y, aditiva: e.shiftKey };
    setMarquesina(marcaRef.current);
  }

  useEffect(() => {
    function onMove(e) {
      if (!marcaRef.current) return;
      const rect = canvasRef.current?.getBoundingClientRect();
      if (!rect) return;
      const z = zoomRef.current;
      marcaRef.current = {
        ...marcaRef.current,
        x2: (e.clientX - rect.left) / z,
        y2: (e.clientY - rect.top) / z,
      };
      setMarquesina(marcaRef.current);
    }
    function onUp() {
      const m = marcaRef.current;
      marcaRef.current = null;
      setMarquesina(null);
      if (!m) return;
      const [ix, fx] = [Math.min(m.x1, m.x2), Math.max(m.x1, m.x2)];
      const [iy, fy] = [Math.min(m.y1, m.y2), Math.max(m.y1, m.y2)];
      // Un clic suelto no es una marquesina: limpia la selección y ya.
      if (fx - ix < 5 && fy - iy < 5) return;
      const dentro = (versionRef.current?.nodos || []).filter(
        (n) => n.x + NODO_W > ix && n.x < fx && n.y + NODO_H > iy && n.y < fy,
      );
      setSeleccion((prev) => {
        const s = m.aditiva ? new Set(prev) : new Set();
        dentro.forEach((n) => s.add(n.id));
        return s;
      });
      // Tras soltar, el navegador dispara un `click` sobre el lienzo, y ése
      // limpia la selección: se descarta el próximo para no borrar lo recién
      // encerrado.
      ignorarClick.current = true;
    }
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
  }, []);

  /* --- Minimapa --------------------------------------------------------------
   *
   * Da lo que el scroll solo no da: dónde estás parado dentro del flujo entero.
   * En un diagrama de 40 nodos, sin esto se navega a ciegas.
   *
   * El rectángulo de la vista se recalcula al scrollear y al hacer zoom. Se
   * agrupa con `requestAnimationFrame` porque el scroll dispara decenas de
   * eventos por segundo y re-renderizar en cada uno traba el arrastre.
   */
  const [vista, setVista] = useState(null); // {x, y, w, h} en coords del mundo

  useEffect(() => {
    const cont = scrollRef.current;
    if (!cont) return;
    let pendiente = false;
    const medir = () => {
      pendiente = false;
      const z = zoomRef.current;
      setVista({
        x: cont.scrollLeft / z,
        y: cont.scrollTop / z,
        w: cont.clientWidth / z,
        h: cont.clientHeight / z,
      });
    };
    const alScrollear = () => {
      if (pendiente) return;
      pendiente = true;
      requestAnimationFrame(medir);
    };
    medir();
    cont.addEventListener("scroll", alScrollear, { passive: true });
    window.addEventListener("resize", alScrollear);
    return () => {
      cont.removeEventListener("scroll", alScrollear);
      window.removeEventListener("resize", alScrollear);
    };
  }, [flujo, verId, zoom]);

  /** Centra la vista en un punto del mundo (lo usa el minimapa al hacer clic). */
  function centrarEn(x, y) {
    const cont = scrollRef.current;
    if (!cont) return;
    const z = zoomRef.current;
    cont.scrollTo({
      left: Math.max(0, x * z - cont.clientWidth / 2),
      top: Math.max(0, y * z - cont.clientHeight / 2),
    });
  }

  // --- Atajos de teclado ---------------------------------------------------
  useEffect(() => {
    function onKey(e) {
      const tag = e.target?.tagName;
      const editando = tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || e.target?.isContentEditable;
      if (e.key === "Escape") {
        if (conectarDesde) return setConectarDesde(null);
        if (sim) return setSim(null);
        if (problemas) return setProblemas(null);
        setSel(null); setSelConexion(null);
        return;
      }
      // Undo/redo (también dentro de inputs, como en cualquier editor).
      if ((e.ctrlKey || e.metaKey) && (e.key === "z" || e.key === "Z")) {
        e.preventDefault();
        if (e.shiftKey) rehacer(); else deshacer();
        return;
      }
      if ((e.ctrlKey || e.metaKey) && (e.key === "y" || e.key === "Y")) { e.preventDefault(); rehacer(); return; }
      if (editando) return;

      const k = e.key.toLowerCase();
      const meta = e.ctrlKey || e.metaKey;
      // Seleccionar todo, copiar, pegar y duplicar: los atajos de siempre.
      if (meta && k === "a") { e.preventDefault(); setSeleccion(new Set(version.nodos.map((n) => n.id))); return; }
      if (meta && k === "c") { e.preventDefault(); copiar(); return; }
      if (meta && k === "v") { e.preventDefault(); pegar(); return; }
      if (meta && k === "d") { e.preventDefault(); copiar(); pegar(); return; }

      if (e.key === "Delete" || e.key === "Backspace") {
        if (seleccion.size) { e.preventDefault(); [...seleccion].forEach(borrarNodo); }
        else if (selConexion != null) { e.preventDefault(); borrarConexion(selConexion); }
        return;
      }
      // Mover la selección con las flechas (un paso de grilla).
      if (seleccion.size && e.key.startsWith("Arrow")) {
        e.preventDefault();
        let ddx = 0, ddy = 0;
        if (e.key === "ArrowUp") ddy = -GRID;
        else if (e.key === "ArrowDown") ddy = GRID;
        else if (e.key === "ArrowLeft") ddx = -GRID;
        else if (e.key === "ArrowRight") ddx = GRID;

        const antes = new Map(), despues = new Map();
        for (const id of seleccion) {
          const n = version.nodos.find((x) => x.id === id);
          if (!n) continue;
          antes.set(id, { x: n.x, y: n.y });
          despues.set(id, { x: Math.max(0, n.x + ddx), y: Math.max(0, n.y + ddy) });
        }
        if (!antes.size) return;
        const mover = (m) => Promise.all([...m].map(([id, p]) => aplicarPos(id, p.x, p.y)));
        registrarCambio(() => mover(antes), () => mover(despues));
        mover(despues);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seleccion, selConexion, conectarDesde, sim, problemas, version]);

  if (cargando) return <Spinner label="Cargando flujo…" />;
  if (errorCarga)
    return (
      <div style={{ padding: 40, maxWidth: 460 }}>
        <div style={{ fontSize: "var(--text-lg)", fontWeight: 700, color: "var(--color-danger)", marginBottom: 6 }}>No se pudo cargar el flujo</div>
        <div style={{ fontSize: "var(--text-base)", color: "var(--color-texto-suave)", marginBottom: 16 }}>{errorCarga}</div>
        <div style={{ display: "flex", gap: 10 }}>
          <Button onClick={cargarTodo}>Reintentar</Button>
          <Button variant="secondary" onClick={() => navigate("/flujos")}>← Flujos</Button>
        </div>
      </div>
    );
  if (!version) return <div style={{ padding: 32 }}>Este flujo no tiene versiones.</div>;

  const nodoSel = version.nodos.find((n) => n.id === sel);
  const estV = estadoVersion[version.estado];
  const nodoEnFoco = repro ? repro.camino[repro.idx] : sim ? sim.current : null;
  const reproNodo = repro ? version.nodos.find((n) => n.id === repro.camino[repro.idx]) : null;
  const flujoVacio = version.nodos.length <= 1;

  // Título del formulario asignado a un nodo (lo deduce de los campos cargados).
  const tituloForm = (fid) => campos.find((c) => c.formularioId === fid)?.formulario;

  // Subtítulo contextual de un nodo: resume su configuración para que el lienzo
  // se entienda sin abrir el panel de cada nodo.
  function subtituloNodo(n) {
    const cfg = n.config || {};
    if (n.tipo === "form") return n.formulario ? (tituloForm(n.formulario) || "Formulario asignado") : "Sin formulario";
    if (n.tipo === "decision") {
      const ramas = version.conexiones.filter((c) => c.origen === n.id).length;
      return ramas ? `${ramas} rama${ramas > 1 ? "s" : ""}` : "Sin ramas";
    }
    if (n.tipo === "derivar") return cfg.flujo_destino_id ? "Abre otro flujo" : cfg.area_destino_id ? "Cambia de área" : "Sin destino";
    if (n.tipo === "estado") return cfg.estado ? estadoCaso[cfg.estado]?.label || cfg.estado : "Sin estado";
    if (n.tipo === "atencion" && cfg.con_fila) return "Con fila de espera";
    if (n.tipo === "tiempo" && cfg.duracion) return `Pausa ${cfg.duracion}`;
    return null;
  }

  // Etiqueta de una rama de Decisión: manual si existe, derivada de la condición
  // si no. La rama sin condición (else) se rotula "si no".
  function etiquetaRama(c, origen) {
    if (c.etiqueta) return c.etiqueta;
    if (origen?.tipo !== "decision") return null;
    const { op, reglas } = condicionALista(c.condicion);
    if (!reglas.length) return "si no";
    const texto = (r) => {
      const campo = campos.find((cc) => String(cc.id) === String(r.campo));
      const nombre = campo?.label || "campo";
      const oper = OPERADOR_LABEL[r.operador] || r.operador || "=";
      return SIN_VALOR.has(r.operador) ? `${nombre} ${oper}` : `${nombre} ${oper} ${r.valor ?? ""}`.trim();
    };
    // Con más de dos condiciones la etiqueta taparía el diagrama: se resume.
    if (reglas.length > 2) return `${texto(reglas[0])} ${op === "o" ? "o" : "y"} ${reglas.length - 1} más`;
    return reglas.map(texto).join(op === "o" ? "  o  " : "  y  ");
  }

  // Superficie del lienzo, derivada de dónde llegaron los nodos.
  const mundo = tamanoMundo(version.nodos);

  // Aristas que forman el recorrido activo (Probar / Reproducir) para resaltarlas.
  const edgesActivos = new Set();
  const caminoArr = repro ? repro.camino.slice(0, repro.idx + 1) : sim ? sim.camino : [];
  for (let i = 0; i < caminoArr.length - 1; i++) edgesActivos.add(`${caminoArr[i]}->${caminoArr[i + 1]}`);
  // Sin recorrido posible: deshabilita Probar/Reproducir y explica por qué.
  const sinRecorrido = version.nodos.length < 2 || version.conexiones.length === 0;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      {/* Barra superior */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "14px 24px", borderBottom: `1px solid var(--color-borde)`, background: "var(--color-superficie)", flex: "none", gap: 12, flexWrap: "wrap" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, minWidth: 0 }}>
          <button onClick={() => navigate("/flujos")} title="Volver a Flujos" style={{ border: "none", background: "none", cursor: "pointer", fontSize: "var(--text-base)", color: "var(--color-texto-debil)", display: "flex", alignItems: "center", gap: 5, padding: 4, borderRadius: "var(--radius-sm)" }}>
            <Icon name="back" size={15} /> Flujos
          </button>
          <div style={{ fontSize: "var(--text-xl)", fontWeight: 700, letterSpacing: "-.4px", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{flujo.titulo}</div>
          {flujo.ambito_label && <span style={{ fontSize: "var(--text-sm)", color: "var(--color-texto-debil)", whiteSpace: "nowrap" }}>· {flujo.ambito_label}</span>}
          <Badge tone={estV.tone}>{estV.label}</Badge>
          <Select size="sm" value={verId} onChange={(e) => { setVerId(Number(e.target.value)); cargarVersion(Number(e.target.value)); }} style={{ width: "auto" }}>
            {flujo.versiones.map((v) => <option key={v.id} value={v.id}>{v.etiqueta}</option>)}
          </Select>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <BuscarNodo nodos={version.nodos} onElegir={irAlNodo} />
          <SaveStatus estado={guardado} />
          <div style={{ display: "flex", gap: 2 }}>
            <ZoomBtn title="Deshacer (Ctrl+Z)" onClick={deshacer} disabled={undoStack.current.length === 0}><Icon name="undo" size={16} /></ZoomBtn>
            <ZoomBtn title="Rehacer (Ctrl+Shift+Z)" onClick={rehacer} disabled={redoStack.current.length === 0}><Icon name="redo" size={16} /></ZoomBtn>
          </div>
          <Button variant="secondary" onClick={reproducir} disabled={sinRecorrido} title={sinRecorrido ? "Agregá y conectá nodos para reproducir el recorrido" : "Anima el recorrido del flujo"} style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <Icon name="play" size={13} /> Reproducir
          </Button>
          <Button variant="secondary" onClick={iniciarSim} disabled={sinRecorrido} title={sinRecorrido ? "Agregá y conectá nodos para probar el flujo" : "Simulá un caso paso a paso"}>Probar</Button>
          <Button variant="secondary" onClick={validar} disabled={validando}>{validando ? "Validando…" : "Validar"}</Button>
          <Button onClick={publicar} disabled={version.estado === "publicada" || publicando}>{publicando ? "Publicando…" : "Publicar"}</Button>
        </div>
      </div>

      <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
        {/* Paleta (colapsable para pantallas chicas) */}
        {paletaAbierta ? (
        <div style={{ width: 188, borderRight: `1px solid var(--color-borde)`, background: "var(--color-superficie)", padding: 12, overflow: "auto", flex: "none" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", margin: "4px 4px 4px" }}>
            <span style={{ fontSize: "var(--text-micro)", fontWeight: 700, letterSpacing: ".6px", color: "var(--color-texto-debil)" }}>NODOS</span>
            <button onClick={() => setPaletaAbierta(false)} title="Ocultar nodos" aria-label="Ocultar panel de nodos" style={{ border: "none", background: "none", cursor: "pointer", color: "var(--color-texto-tenue)", display: "flex", padding: 2, borderRadius: "var(--radius-sm)" }}><Icon name="back" size={14} /></button>
          </div>
          <div style={{ fontSize: "var(--text-xs)", color: "var(--color-texto-tenue)", margin: "0 4px 10px" }}>Hacé clic para agregar al lienzo</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {PALETA.map((p) => (
              <button
                key={p.tipo}
                onClick={() => agregarNodo(p.tipo)}
                title={`Agregar nodo «${p.name}»`}
                style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 10px", border: `1px solid var(--color-borde)`, borderRadius: "var(--radius-md)", background: "var(--color-superficie)", cursor: "pointer", textAlign: "left", transition: "background .12s, border-color .12s" }}
                onMouseEnter={(e) => { e.currentTarget.style.background = p.tint; e.currentTarget.style.borderColor = p.bd; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = "var(--color-superficie)"; e.currentTarget.style.borderColor = "var(--color-borde)"; }}
              >
                <span style={{ width: 26, height: 26, borderRadius: "var(--radius-sm)", background: p.tint, border: `1px solid ${p.bd}`, display: "flex", alignItems: "center", justifyContent: "center", flex: "none" }}>
                  <span style={{ width: 10, height: 10, borderRadius: p.tipo === "decision" ? 2 : 3, background: p.sol, transform: p.tipo === "decision" ? "rotate(45deg)" : "none" }} />
                </span>
                <span style={{ fontSize: "var(--text-sm)", fontWeight: 600, color: "var(--color-texto-medio)", flex: 1 }}>{p.name}</span>
                <Icon name="plus" size={13} style={{ color: "var(--color-texto-tenue)" }} />
              </button>
            ))}
          </div>
        </div>
        ) : (
          <button onClick={() => setPaletaAbierta(true)} title="Mostrar nodos" aria-label="Mostrar panel de nodos" style={{ width: 34, flex: "none", borderRight: `1px solid var(--color-borde)`, background: "var(--color-superficie)", cursor: "pointer", color: "var(--color-texto-debil)", display: "flex", flexDirection: "column", alignItems: "center", paddingTop: 14, border: "none" }}>
            <Icon name="plus" size={16} />
          </button>
        )}

        {/* Canvas (viewport sin scroll → scrolleable → sizer a escala → capa escalada) */}
        <div style={{ flex: 1, position: "relative", minWidth: 0 }}>
          <div ref={montarScroll} style={{ position: "absolute", inset: 0, overflow: "auto", background: "var(--color-fondo)" }}>
            <div style={{ width: mundo.w * zoom, height: mundo.h * zoom }}>
              <div
                ref={canvasRef}
                // Marca la capa escalada. La usa la suite para leer el zoom real
                // del DOM sin adivinarlo por el `style`, que es frágil.
                data-lienzo=""
                onPointerDown={onLienzoPointerDown}
                onClick={(e) => {
                  // Sólo el fondo limpia la selección; un clic sobre un nodo no
                  // debe llegar acá (los nodos ya cortan la propagación).
                  if (e.target !== e.currentTarget) return;
                  if (ignorarClick.current) { ignorarClick.current = false; return; }
                  setSel(null); setSelConexion(null); setConectarDesde(null);
                }}
                style={{
                  position: "relative",
                  width: mundo.w,
                  height: mundo.h,
                  transform: `scale(${zoom})`,
                  transformOrigin: "top left",
                  backgroundImage: "radial-gradient(circle, var(--color-borde) 1.1px, transparent 1.1px)",
                  backgroundSize: `${GRID}px ${GRID}px`,
                }}
              >
            {/* Conexiones */}
            <svg style={{ position: "absolute", inset: 0, width: "100%", height: "100%", pointerEvents: "none" }}>
              <defs>
                <marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth">
                  <path d="M0,0 L8,3 L0,6 Z" fill="var(--color-texto-tenue)" />
                </marker>
                <marker id="arrow-activo" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth">
                  <path d="M0,0 L8,3 L0,6 Z" fill={"var(--color-accent)"} />
                </marker>
              </defs>
              {version.conexiones.map((c) => {
                const o = version.nodos.find((n) => n.id === c.origen);
                const d = version.nodos.find((n) => n.id === c.destino);
                if (!o || !d) return null;
                const x1 = o.x + NODO_W, y1 = o.y + NODO_H / 2;
                const x2 = d.x, y2 = d.y + NODO_H / 2;
                const mx = (x1 + x2) / 2, my = (y1 + y2) / 2;
                const activo = edgesActivos.has(`${c.origen}->${c.destino}`);
                const seleccionada = c.id === selConexion;
                const resaltada = seleccionada || activo || c.id === hoverConn;
                const stroke = seleccionada || activo ? "var(--color-accent)" : c.id === hoverConn ? "var(--color-texto-debil)" : "var(--color-texto-tenue)";
                const path = `M ${x1} ${y1} C ${mx} ${y1}, ${mx} ${y2}, ${x2} ${y2}`;
                const etiqueta = etiquetaRama(c, o);
                return (
                  <g
                    key={c.id}
                    style={{ pointerEvents: "auto", cursor: "pointer" }}
                    onMouseEnter={() => setHoverConn(c.id)}
                    onMouseLeave={() => setHoverConn((h) => (h === c.id ? null : h))}
                    onClick={(e) => { e.stopPropagation(); setSelConexion(c.id); setSel(null); }}
                  >
                    {/* zona de impacto invisible más ancha para facilitar el clic/hover */}
                    <path d={path} stroke="transparent" strokeWidth="16" fill="none" />
                    <path d={path} stroke={stroke} strokeWidth={resaltada ? 2.6 : 1.6} fill="none" markerEnd={`url(#${seleccionada || activo ? "arrow-activo" : "arrow"})`} style={{ transition: "stroke .15s, stroke-width .15s" }} />
                    {etiqueta && (
                      <>
                        <rect x={mx - (etiqueta.length * 3.2 + 6)} y={my - 18} width={etiqueta.length * 6.4 + 12} height={16} rx={8} fill={"var(--color-fondo)"} stroke={"var(--color-division)"} />
                        <text x={mx} y={my - 6} fill={seleccionada || activo ? "var(--color-accent)" : "var(--color-texto-suave)"} fontSize="11" textAnchor="middle" style={{ fontWeight: 600 }}>{etiqueta}</text>
                      </>
                    )}
                    {seleccionada && (
                      <g onClick={(e) => { e.stopPropagation(); borrarConexion(c.id); }} style={{ cursor: "pointer" }}>
                        <circle cx={mx} cy={my + 13} r="9" fill={"var(--color-danger)"} />
                        <path d={`M ${mx - 3} ${my + 10} L ${mx + 3} ${my + 16} M ${mx + 3} ${my + 10} L ${mx - 3} ${my + 16}`} stroke="#fff" strokeWidth="1.6" strokeLinecap="round" />
                      </g>
                    )}
                  </g>
                );
              })}
              {/* Línea-fantasma mientras se arrastra una conexión nueva */}
              {ghost && (
                <path
                  d={`M ${ghost.x1} ${ghost.y1} C ${(ghost.x1 + ghost.x2) / 2} ${ghost.y1}, ${(ghost.x1 + ghost.x2) / 2} ${ghost.y2}, ${ghost.x2} ${ghost.y2}`}
                  stroke={"var(--color-accent)"} strokeWidth="2" strokeDasharray="5 4" fill="none" markerEnd="url(#arrow-activo)" style={{ pointerEvents: "none" }}
                />
              )}
            </svg>

            {/* Nodos */}
            {version.nodos.map((n) => {
              const cat = catDe(n.tipo);
              const seleccionado = seleccion.has(n.id);
              const esOrigenConexion = conectarDesde === n.id;
              const enFoco = n.id === nodoEnFoco;
              const arrastrando = dragId === n.id;
              const sub = subtituloNodo(n);
              const subFalta = sub && sub.startsWith("Sin ");
              return (
                <div
                  key={n.id}
                  data-nodo={n.id}
                  tabIndex={0}
                  role="button"
                  aria-label={`${cat.name}: ${n.titulo}. Flechas para mover, Suprimir para eliminar.`}
                  // El foco no pisa una selección múltiple: en un elemento con
                  // tabIndex el focus dispara junto con el pointerdown, así que
                  // sin esto un shift+clic quedaba reducido a un solo nodo.
                  onFocus={() => { if (!seleccion.has(n.id)) setSel(n.id); }}
                  onPointerDown={(e) => onNodoPointerDown(e, n)}
                  onClick={(e) => { e.stopPropagation(); clickNodo(n, e); }}
                  style={{
                    position: "absolute",
                    left: n.x,
                    top: n.y,
                    width: NODO_W,
                    minHeight: NODO_H,
                    boxSizing: "border-box",
                    background: cat.tint,
                    border: `1.5px solid ${seleccionado || esOrigenConexion || enFoco ? cat.sol : cat.bd}`,
                    borderRadius: "var(--radius-lg)",
                    padding: "11px 13px",
                    cursor: arrastrando ? "grabbing" : "grab",
                    touchAction: "none",
                    boxShadow: enFoco ? `0 0 0 4px ${cat.sol}55, var(--shadow-float)` : arrastrando ? "var(--shadow-float)" : seleccionado ? `0 0 0 3px ${cat.sol}33` : "var(--shadow-card)",
                    transform: arrastrando ? "scale(1.02)" : "none",
                    transition: arrastrando ? "none" : "box-shadow .2s, border-color .2s, transform .12s",
                    zIndex: arrastrando ? 4 : 1,
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                  }}
                >
                  <span style={{ width: 11, height: 11, borderRadius: n.tipo === "decision" ? 2 : 3, background: cat.sol, transform: n.tipo === "decision" ? "rotate(45deg)" : "none", flex: "none" }} />
                  <div style={{ minWidth: 0, flex: 1 }}>
                    {/* La categoría va en un gris legible, NO en el color del nodo: esa paleta
                        está pensada para bordes y rellenos, y como texto no llega a
                        4.5:1 («Decisión» daba 2.64:1). El cuadradito de la izquierda,
                        el borde y el tinte ya identifican el tipo. */}
                    <div style={{ fontSize: "var(--text-micro)", fontWeight: 700, letterSpacing: ".4px", color: "var(--color-texto-suave)" }}>{cat.name.toUpperCase()}</div>
                    <div style={{ fontSize: "var(--text-base)", fontWeight: 600, color: "var(--color-texto-fuerte)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{n.titulo}</div>
                    {sub && (
                      <div style={{ fontSize: "var(--text-xs)", color: subFalta ? "var(--color-danger)" : "var(--color-texto-suave)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", marginTop: 2 }}>{sub}</div>
                    )}
                    {n.grupos_detalle?.length > 0 && (
                      <div title={`Responsable: ${n.grupos_detalle.map((g) => g.nombre).join(", ")}`} style={{ display: "flex", alignItems: "center", gap: 4, marginTop: 3, fontSize: "var(--text-xs)", color: "var(--color-texto-suave)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                        <Icon name="users" size={11} />
                        {n.grupos_detalle.length === 1 ? n.grupos_detalle[0].nombre : `${n.grupos_detalle.length} grupos`}
                      </div>
                    )}
                  </div>
                  {/* Handle de entrada (visual) */}
                  {n.tipo !== "inicio" && (
                    <span style={{ position: "absolute", left: -5, top: NODO_H / 2 - 4, width: 9, height: 9, borderRadius: "50%", background: "var(--color-superficie)", border: `2px solid ${cat.bd}`, pointerEvents: "none" }} />
                  )}
                  {/* Handle de salida: arrastrar desde acá para conectar */}
                  {n.tipo !== "fin" && (
                    <span
                      title="Arrastrá para conectar con otro nodo"
                      onPointerDown={(e) => onHandlePointerDown(e, n)}
                      onMouseDown={(e) => e.stopPropagation()}
                      onClick={(e) => e.stopPropagation()}
                      style={{ position: "absolute", right: -7, top: NODO_H / 2 - 6, width: 13, height: 13, borderRadius: "50%", background: "var(--color-superficie)", border: `2px solid ${cat.sol}`, cursor: "crosshair", touchAction: "none", zIndex: 3 }}
                    />
                  )}
                </div>
              );
            })}

            {/* Marquesina de selección */}
            {marquesina && (
              <div
                aria-hidden="true"
                style={{
                  position: "absolute",
                  left: Math.min(marquesina.x1, marquesina.x2),
                  top: Math.min(marquesina.y1, marquesina.y2),
                  width: Math.abs(marquesina.x2 - marquesina.x1),
                  height: Math.abs(marquesina.y2 - marquesina.y1),
                  border: `1px solid var(--color-accent)`,
                  background: `var(--color-accent)14`,
                  borderRadius: 3,
                  pointerEvents: "none",
                  zIndex: 4,
                }}
              />
            )}

            {/* Token de "Reproducir" viajando por el lienzo */}
            {reproNodo && (
              <div style={{ position: "absolute", left: reproNodo.x + NODO_W / 2 - 9, top: reproNodo.y + NODO_H / 2 - 9, width: 18, height: 18, borderRadius: "50%", background: "var(--color-accent)", border: "3px solid #fff", boxShadow: `0 0 0 4px var(--color-accent)55, 0 6px 16px rgba(16,24,40,.3)`, transition: "left .65s cubic-bezier(.5,0,.2,1), top .65s cubic-bezier(.5,0,.2,1)", pointerEvents: "none", zIndex: 5 }} />
            )}
              </div>
            </div>
          </div>

          {/* Controles de zoom (fijos sobre el viewport, no scrollean) */}
          <div style={{ position: "absolute", left: 14, bottom: 14, display: "flex", alignItems: "center", gap: 4, background: "var(--color-superficie)", border: `1px solid var(--color-borde)`, borderRadius: "var(--radius-md)", boxShadow: "var(--shadow-card)", padding: 3, zIndex: 7 }}>
            <ZoomBtn title="Alejar" onClick={() => zoomBoton(-0.1)}><Icon name="minus" size={15} /></ZoomBtn>
            <button onClick={() => setZoom(1)} title="Restablecer zoom (100%)" style={{ border: "none", background: "none", cursor: "pointer", fontSize: "var(--text-sm)", fontWeight: 600, color: "var(--color-texto-suave)", minWidth: 42, fontVariantNumeric: "tabular-nums" }}>{Math.round(zoom * 100)}%</button>
            <ZoomBtn title="Acercar" onClick={() => zoomBoton(0.1)}><Icon name="plus" size={15} /></ZoomBtn>
            <div style={{ width: 1, height: 18, background: "var(--color-division)", margin: "0 2px" }} />
            <ZoomBtn title="Ajustar al contenido" onClick={ajustar}><Icon name="maximize" size={15} /></ZoomBtn>
            <ZoomBtn
              title="Ordenar el diagrama automáticamente (se puede deshacer)"
              onClick={ordenar}
              disabled={version.nodos.length < 2}
            >
              <Icon name="workflow" size={15} />
            </ZoomBtn>
          </div>

          {/* Minimapa (abajo a la derecha, del lado opuesto al zoom) */}
          {version.nodos.length > 3 && (
            <MiniMapa nodos={version.nodos} seleccion={seleccion} vista={vista} mundo={mundo} onIr={centrarEn} />
          )}

          {/* Mostrar/ocultar el panel de propiedades */}
          <button onClick={() => setPanelAbierto((v) => !v)} title={panelAbierto ? "Ocultar propiedades" : "Mostrar propiedades"} aria-label={panelAbierto ? "Ocultar panel de propiedades" : "Mostrar panel de propiedades"} style={{ position: "absolute", right: 10, top: 12, zIndex: 7, width: 30, height: 30, borderRadius: "var(--radius-sm)", border: `1px solid var(--color-borde)`, background: "var(--color-superficie)", boxShadow: "var(--shadow-card)", cursor: "pointer", color: "var(--color-texto-suave)", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <Icon name="back" size={15} style={{ transform: panelAbierto ? "rotate(180deg)" : "none" }} />
          </button>

          {/* Onboarding del lienzo vacío */}
          {flujoVacio && (
            <div style={{ position: "absolute", top: 90, left: "50%", transform: "translateX(-50%)", width: 320, maxWidth: "80%", background: "var(--color-superficie)", border: `1px solid var(--color-borde)`, borderRadius: "var(--radius-lg)", boxShadow: "var(--shadow-dropdown)", padding: "18px 20px", animation: "fadeUp .2s ease", zIndex: 6 }}>
              <div style={{ fontSize: "var(--text-md)", fontWeight: 700, color: "var(--color-texto-fuerte)", marginBottom: 4 }}>Diseñá tu primer proceso</div>
              <div style={{ fontSize: "var(--text-sm)", color: "var(--color-texto-debil)", marginBottom: 12 }}>Tres pasos para armar un flujo:</div>
              {[
                ["1", "Agregá nodos", "Hacé clic en un tipo de la columna NODOS (izquierda)."],
                ["2", "Conectalos", "Arrastrá desde el punto del borde derecho de un nodo al siguiente."],
                ["3", "Probalo", "Usá «Probar» para recorrer el flujo como un caso real."],
              ].map(([n, t, d]) => (
                <div key={n} style={{ display: "flex", gap: 10, marginBottom: 10 }}>
                  <span style={{ flex: "none", width: 20, height: 20, borderRadius: "50%", background: "var(--color-accent-50)", color: "var(--color-accent)", fontSize: "var(--text-xs)", fontWeight: 700, display: "flex", alignItems: "center", justifyContent: "center" }}>{n}</span>
                  <div>
                    <div style={{ fontSize: "var(--text-base)", fontWeight: 600, color: "var(--color-texto-medio)" }}>{t}</div>
                    <div style={{ fontSize: "var(--text-xs)", color: "var(--color-texto-debil)" }}>{d}</div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {conectarDesde && (
            <div style={{ position: "fixed", bottom: 24, left: "50%", transform: "translateX(-50%)", background: "var(--color-ink)", color: "var(--color-white)", padding: "8px 16px", borderRadius: "var(--radius-pill)", fontSize: "var(--text-sm)", boxShadow: "var(--shadow-dropdown)", zIndex: 40 }}>
              Hacé clic en el nodo destino · <span style={{ cursor: "pointer", textDecoration: "underline" }} onClick={() => setConectarDesde(null)}>cancelar</span>
            </div>
          )}
        </div>

        {/* Panel de propiedades (colapsable) */}
        {panelAbierto && (
        <div style={{ width: 300, borderLeft: `1px solid var(--color-borde)`, background: "var(--color-superficie)", overflow: "auto", flex: "none" }}>
          {sim ? (
            <PanelSimulacion sim={sim} version={version} campos={campos} onAvanzar={avanzarSim} onReiniciar={iniciarSim} onCerrar={() => setSim(null)} />
          ) : problemas ? (
            <PanelValidacion problemas={problemas} onCerrar={() => setProblemas(null)} onFocus={(nid) => { setSel(nid); setProblemas(null); }} />
          ) : seleccion.size > 1 ? (
            <PanelSeleccion
              cantidad={seleccion.size}
              onDuplicar={() => { copiar(); pegar(); }}
              onBorrar={() => [...seleccion].forEach(borrarNodo)}
              onLimpiar={() => setSeleccion(new Set())}
            />
          ) : nodoSel ? (
            <PanelNodo
              key={nodoSel.id}
              nodo={nodoSel}
              version={version}
              flujoInstId={flujo.institucion}
              flujoAreaId={flujo.area}
              campos={campos}
              onActualizar={actualizarNodo}
              onBorrar={borrarNodo}
              onConectar={() => setConectarDesde(nodoSel.id)}
              onBorrarConexion={borrarConexion}
              onActualizarConexion={actualizarConexion}
            />
          ) : (
            <div style={{ padding: 22, fontSize: "var(--text-base)", color: "var(--color-texto-debil)" }}>
              Seleccioná un nodo para editar sus propiedades, o agregá uno desde la paleta.
            </div>
          )}
        </div>
        )}
      </div>

      {toast && <Toast toast={toast} onClose={() => setToast(null)} />}
    </div>
  );
}

// Botón cuadrado e ícono (barra de zoom y deshacer/rehacer).
function ZoomBtn({ title, onClick, children, disabled }) {
  return (
    <button
      onClick={onClick}
      title={title}
      aria-label={title}
      disabled={disabled}
      style={{ width: 28, height: 28, borderRadius: "var(--radius-sm)", border: "none", background: "none", color: disabled ? "var(--color-texto-tenue)" : "var(--color-texto-suave)", opacity: disabled ? 0.45 : 1, cursor: disabled ? "default" : "pointer", display: "flex", alignItems: "center", justifyContent: "center" }}
      onMouseEnter={(e) => { if (!disabled) e.currentTarget.style.background = "var(--color-division)"; }}
      onMouseLeave={(e) => (e.currentTarget.style.background = "none")}
    >
      {children}
    </button>
  );
}

// Indicador de autosave en la barra superior.
function SaveStatus({ estado }) {
  if (estado === "idle") return null;
  const map = {
    guardando: { txt: "Guardando…", col: "var(--color-texto-debil)" },
    guardado: { txt: "Guardado ✓", col: "var(--color-badge-green-fg)" },
    error: { txt: "Error al guardar", col: "var(--color-danger)" },
  };
  const s = map[estado] || map.guardando;
  return <span style={{ fontSize: "var(--text-sm)", fontWeight: 600, color: s.col, whiteSpace: "nowrap" }}>{s.txt}</span>;
}

// Toast efímero con acción opcional (p. ej. «Deshacer»).
function Toast({ toast, onClose }) {
  const ok = toast.tipo === "ok";
  return (
    <div style={{ position: "fixed", bottom: 24, left: "50%", transform: "translateX(-50%)", display: "flex", alignItems: "center", gap: 14, background: "var(--color-ink)", color: "var(--color-white)", padding: "11px 16px", borderRadius: "var(--radius-md)", fontSize: "var(--text-base)", boxShadow: "var(--shadow-dropdown)", zIndex: 60, maxWidth: 460, animation: "fadeUp .16s ease" }}>
      {/* Estos colores NO siguen el tema a propósito: el aviso va siempre sobre
          tinta oscura (`--color-ink`, que es literal), así que están elegidos para
          leerse ahí. Pasarlos a tokens semánticos los volvería ilegibles en claro. */}
      <span style={{ width: 8, height: 8, borderRadius: "50%", background: ok ? "#46C08A" : "#F26D6D", flex: "none" }} />
      <span style={{ flex: 1 }}>{toast.msg}</span>
      {toast.accion && (
        <button onClick={toast.accion.fn} style={{ border: "none", background: "none", color: "#9FB0FF", fontWeight: 700, cursor: "pointer", fontSize: "var(--text-base)", whiteSpace: "nowrap" }}>{toast.accion.label}</button>
      )}
      <button onClick={onClose} aria-label="Cerrar" style={{ border: "none", background: "none", color: "#fff", cursor: "pointer", display: "flex", opacity: .7 }}>
        <Icon name="x" size={15} />
      </button>
    </div>
  );
}

// --------------------------------------------------------------------------- //
function PanelSimulacion({ sim, version, campos, onAvanzar, onReiniciar, onCerrar }) {
  const nodo = version.nodos.find((n) => n.id === sim.current);
  const cat = nodo ? catDe(nodo.tipo) : catDe("inicio");
  const [valores, setValores] = useState({});

  const camposForm = nodo?.tipo === "form" && nodo.formulario
    ? campos.filter((c) => c.formularioId === nodo.formulario)
    : [];

  // Qué admite esta parada lo dice el motor, no el editor: si acá se dedujera,
  // sería otra copia de la misma regla, que es justo el problema que se acaba
  // de eliminar.
  const toca = sim.acciones?.[0] || "avanzar";

  // Los datos van en el formato que espera el motor, sin traductor en el medio.
  function datosDelPaso() {
    if (toca === "llamar") return { accion: "llamar" };
    if (nodo?.tipo === "form") return { valores };
    if (nodo?.tipo === "atencion") {
      // `firmada: false` a propósito: firmar exige matrícula, y el ensayo no
      // debería fallar por eso cuando lo que se está probando es el recorrido.
      return { titulo: nodo.titulo, contenido: "Ensayo del diseñador", firmada: false };
    }
    return {};
  }

  function avanzar() {
    onAvanzar(datosDelPaso());
    setValores({});
  }

  return (
    <div style={{ padding: 20 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
        <div style={{ fontSize: "var(--text-md)", fontWeight: 700, display: "flex", alignItems: "center", gap: 7 }}>
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--color-badge-green-fg)" }} /> Modo prueba
        </div>
        <button onClick={onCerrar} aria-label="Cerrar" style={{ border: "none", background: "none", cursor: "pointer", color: "var(--color-texto-debil)", display: "flex", padding: 4, borderRadius: "var(--radius-sm)" }}><Icon name="x" size={18} /></button>
      </div>
      <div style={{ fontSize: "var(--text-sm)", color: "var(--color-texto-debil)", marginBottom: 16 }}>
        Corre con el motor real y después se deshace: no queda nada en la base.
      </div>

      {sim.error ? (
        // El error del motor es el resultado del ensayo, no una falla: dice qué
        // impide que el caso siga y en qué nodo. Es justo lo que el simulador
        // viejo no podía saber.
        <div style={{ fontSize: "var(--text-base)", color: "var(--color-danger)", background: "var(--color-badge-error-bg)", padding: "10px 12px", borderRadius: "var(--radius-md)" }}>
          <div style={{ fontWeight: 700, marginBottom: 3 }}>
            Se detiene en «{sim.error.titulo}»
          </div>
          {sim.error.mensaje}
        </div>
      ) : sim.fin ? (
        <div style={{ background: "var(--color-badge-green-bg)", color: "var(--color-badge-green-fg)", padding: "14px 16px", borderRadius: "var(--radius-md)", fontSize: "var(--text-base)", fontWeight: 600 }}>
          ✓ Caso simulado {sim.sinSalida ? "detenido (nodo sin salida)" : "finalizado"}.
        </div>
      ) : nodo ? (
        <>
          <div style={{ border: `1px solid ${cat.bd}`, background: cat.tint, borderRadius: "var(--radius-md)", padding: 13, marginBottom: 14 }}>
            {/* La categoría va en un gris legible, NO en el color del nodo: esa paleta
                        está pensada para bordes y rellenos, y como texto no llega a
                        4.5:1 («Decisión» daba 2.64:1). El cuadradito de la izquierda,
                        el borde y el tinte ya identifican el tipo. */}
                    <div style={{ fontSize: "var(--text-micro)", fontWeight: 700, letterSpacing: ".4px", color: "var(--color-texto-suave)" }}>{cat.name.toUpperCase()}</div>
            <div style={{ fontSize: "var(--text-md)", fontWeight: 700, color: "var(--color-texto-fuerte)" }}>{nodo.titulo}</div>
          </div>

          {nodo.tipo === "form" && (
            <div style={{ display: "flex", flexDirection: "column", gap: 12, marginBottom: 14 }}>
              {camposForm.length === 0 ? (
                <div style={{ fontSize: "var(--text-sm)", color: "var(--color-texto-debil)" }}>Este formulario no tiene campos (o no está asignado).</div>
              ) : camposForm.map((c) => (
                <div key={c.id}>
                  <div style={{ fontSize: "var(--text-sm)", fontWeight: 600, color: "var(--color-texto-suave)", marginBottom: 5 }}>{c.label}{c.requerido && <span style={{ color: "var(--color-danger)" }}> *</span>}</div>
                  {c.tipo === "seleccion_unica" ? (
                    <Select size="sm" value={valores[c.id] || ""} onChange={(e) => setValores((v) => ({ ...v, [c.id]: e.target.value }))}>
                      <option value="">Seleccionar…</option>
                      {(c.opciones || []).map((o) => <option key={o} value={o}>{o}</option>)}
                    </Select>
                  ) : (
                    <Input size="sm" type={c.tipo === "fecha" ? "date" : "text"} value={valores[c.id] || ""} onChange={(e) => setValores((v) => ({ ...v, [c.id]: e.target.value }))} />
                  )}
                </div>
              ))}
            </div>
          )}

          <Button onClick={avanzar} style={{ width: "100%" }}>
            {toca === "llamar"
              ? "Llamar al paciente"
              : nodo.tipo === "form" ? "Completar y avanzar"
              : nodo.tipo === "atencion" ? "Registrar y avanzar"
              : nodo.tipo === "tiempo" ? "Reactivar"
              : "Avanzar"}
          </Button>
        </>
      ) : (
        <div style={{ fontSize: "var(--text-base)", color: "var(--color-texto-debil)" }}>Sin nodo actual.</div>
      )}

      {/* Recorrido */}
      <div style={{ marginTop: 18, borderTop: `1px solid var(--color-division)`, paddingTop: 14 }}>
        <div style={{ fontSize: "var(--text-micro)", fontWeight: 700, letterSpacing: ".5px", color: "var(--color-texto-debil)", marginBottom: 8 }}>RECORRIDO</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          {(sim.camino || []).map((nid, i) => {
            const n = version.nodos.find((x) => x.id === nid);
            if (!n) return null;
            const c = catDe(n.tipo);
            return (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: "var(--text-sm)", color: nid === sim.current ? "var(--color-texto-fuerte)" : "var(--color-texto-debil)" }}>
                <span style={{ width: 8, height: 8, borderRadius: 2, background: c.sol, flex: "none" }} />
                {n.titulo}
              </div>
            );
          })}
        </div>
        <button onClick={onReiniciar} style={{ marginTop: 12, border: "none", background: "none", color: "var(--color-accent)", cursor: "pointer", fontSize: "var(--text-sm)", fontWeight: 600 }}>↻ Reiniciar prueba</button>
      </div>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Operadores válidos según el tipo del campo (>, < solo tienen sentido en
// números/fechas; el motor hace parseFloat y devuelve false para texto).
// Operadores que ofrece cada tipo de campo. Los de orden comparan como número y,
// si no se puede, como fecha ISO — por eso `fecha` los incluye.
const ORDEN = [">", "<", ">=", "<=", "entre"];
const PRESENCIA = ["vacio", "no_vacio"];
const OP_POR_TIPO = {
  numero: ["=", "!=", ...ORDEN, ...PRESENCIA],
  entero: ["=", "!=", ...ORDEN, ...PRESENCIA],
  decimal: ["=", "!=", ...ORDEN, ...PRESENCIA],
  fecha: ["=", "!=", ...ORDEN, ...PRESENCIA],
  seleccion_unica: ["=", "!=", "en", "no_en", ...PRESENCIA],
};
const OP_TEXTO = ["=", "!=", "contiene", "no_contiene", "en", "no_en", ...PRESENCIA];

function operadoresDe(campo) {
  if (!campo) return OP_TEXTO;
  return OP_POR_TIPO[campo.tipo] || (campo.opciones?.length ? OP_POR_TIPO.seleccion_unica : OP_TEXTO);
}

/**
 * Minimapa del lienzo.
 *
 * Responde a «dónde estoy parado dentro del flujo entero», que el scroll solo no
 * contesta. Cada nodo es un rectángulo con el color de su categoría y el marco
 * claro es la porción visible; haciendo clic o arrastrando ahí, el lienzo salta.
 *
 * Mapea el mundo COMPLETO y no el rectángulo que ocupan los nodos: si se
 * ajustara al contenido, el mapa cambiaría de escala cada vez que alguien mueve
 * un nodo y dejaría de servir como referencia estable.
 *
 * Se oculta con flujos de pocos nodos: ahí no orienta, sólo tapa lienzo.
 */
const MAPA_W = 168;

function MiniMapa({ nodos, seleccion, vista, mundo, onIr }) {
  const ref = useRef(null);
  const arrastrando = useRef(false);
  // Misma escala en los dos ejes, y el alto sale de la proporción del mundo:
  // así el mapa acompaña cuando el lienzo crece con el flujo.
  const k = MAPA_W / mundo.w;
  const MAPA_H = Math.round(mundo.h * k);

  function irDesdeEvento(e) {
    const caja = ref.current?.getBoundingClientRect();
    if (!caja) return;
    onIr((e.clientX - caja.left) / k, (e.clientY - caja.top) / k);
  }

  return (
    <div
      ref={ref}
      onPointerDown={(e) => {
        arrastrando.current = true;
        e.currentTarget.setPointerCapture(e.pointerId);
        irDesdeEvento(e);
      }}
      onPointerMove={(e) => arrastrando.current && irDesdeEvento(e)}
      onPointerUp={() => { arrastrando.current = false; }}
      title="Mapa del flujo · hacé clic para ir a esa zona"
      style={{
        position: "absolute", right: 14, bottom: 14, width: MAPA_W, height: MAPA_H,
        background: "var(--color-superficie)", border: `1px solid var(--color-borde)`, borderRadius: "var(--radius-md)",
        boxShadow: "var(--shadow-card)", overflow: "hidden", cursor: "pointer", zIndex: 7,
        touchAction: "none",
      }}
    >
      {nodos.map((n) => (
        <span
          key={n.id}
          style={{
            position: "absolute",
            left: n.x * k,
            top: n.y * k,
            width: Math.max(3, NODO_W * k),
            height: Math.max(2, NODO_H * k),
            borderRadius: 1,
            background: catDe(n.tipo).sol,
            // Lo elegido se destaca: el minimapa también sirve para ubicar dónde
            // quedó lo que se acaba de seleccionar o pegar.
            outline: seleccion.has(n.id) ? `1.5px solid var(--color-accent)` : "none",
          }}
        />
      ))}

      {vista && (
        <span
          aria-hidden="true"
          style={{
            position: "absolute",
            left: vista.x * k,
            top: vista.y * k,
            width: Math.min(MAPA_W, vista.w * k),
            height: Math.min(MAPA_H, vista.h * k),
            border: `1.5px solid var(--color-accent)`,
            background: `var(--color-accent)12`,
            borderRadius: 2,
            pointerEvents: "none",
          }}
        />
      )}
    </div>
  );
}

/**
 * Panel de varios nodos elegidos.
 *
 * Con más de uno no hay propiedades que editar —son de distinto tipo—, así que
 * el panel pasa a ofrecer lo que sí aplica al grupo. Dejarlo vacío haría pensar
 * que la selección múltiple no sirve para nada.
 */
function PanelSeleccion({ cantidad, onDuplicar, onBorrar, onLimpiar }) {
  return (
    <div style={{ padding: 20 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
        <div style={{ fontSize: "var(--text-md)", fontWeight: 700 }}>{cantidad} nodos elegidos</div>
        <button onClick={onLimpiar} aria-label="Quitar la selección" title="Quitar la selección" style={{ border: "none", background: "none", cursor: "pointer", color: "var(--color-texto-debil)", display: "flex", padding: 4 }}>
          <Icon name="x" size={18} />
        </button>
      </div>
      <div style={{ fontSize: "var(--text-sm)", color: "var(--color-texto-debil)", marginBottom: 16 }}>
        Arrastrá cualquiera de ellos para mover el grupo, o usá las flechas del teclado.
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        <Button variant="secondary" onClick={onDuplicar}>Duplicar (Ctrl+D)</Button>
        <Button variant="danger" onClick={onBorrar}>Eliminar los {cantidad}</Button>
      </div>
      <div style={{ marginTop: 16, fontSize: "var(--text-xs)", color: "var(--color-texto-tenue)", lineHeight: 1.5 }}>
        Al duplicar se copian también las conexiones entre los nodos elegidos. Las que
        entran o salen del grupo no, porque apuntarían a nodos que la copia no reprodujo.
      </div>
    </div>
  );
}

/**
 * Buscador de nodos del lienzo.
 *
 * Escribís, ves los que coinciden y al elegir uno el lienzo lo trae al centro.
 * Sin esto, en un flujo grande encontrar un nodo es arrastrar el scroll a ojo.
 * Se abre con Ctrl+F —el atajo que todo el mundo ya tiene en los dedos— y se
 * cierra con Escape.
 */
function BuscarNodo({ nodos, onElegir }) {
  const [texto, setTexto] = useState("");
  const [abierto, setAbierto] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    function alTeclado(e) {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "f") {
        e.preventDefault();
        setAbierto(true);
        requestAnimationFrame(() => ref.current?.focus());
      }
    }
    document.addEventListener("keydown", alTeclado);
    return () => document.removeEventListener("keydown", alTeclado);
  }, []);

  const plano = (s) => (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  const coincide = texto.trim()
    ? nodos.filter((n) => plano(n.titulo).includes(plano(texto))).slice(0, 8)
    : [];

  if (!abierto) {
    return (
      <ZoomBtn title="Buscar un nodo (Ctrl+F)" onClick={() => { setAbierto(true); requestAnimationFrame(() => ref.current?.focus()); }}>
        <Icon name="search" size={16} />
      </ZoomBtn>
    );
  }

  function cerrar() { setAbierto(false); setTexto(""); }

  return (
    <div style={{ position: "relative" }}>
      <Input
        ref={ref}
        size="sm"
        value={texto}
        onChange={(e) => setTexto(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Escape") cerrar();
          // Enter salta al primero: buscar y elegir sin soltar el teclado.
          if (e.key === "Enter" && coincide[0]) { onElegir(coincide[0].id); cerrar(); }
        }}
        onBlur={() => setTimeout(cerrar, 150)}
        placeholder="Buscar nodo…"
        aria-label="Buscar un nodo del flujo"
        style={{ width: 190 }}
      />
      {coincide.length > 0 && (
        <div style={{ position: "absolute", top: "100%", left: 0, marginTop: 4, width: 240, background: "var(--color-superficie)", border: `1px solid var(--color-borde)`, borderRadius: "var(--radius-md)", boxShadow: "var(--shadow-dropdown)", zIndex: 30, overflow: "hidden" }}>
          {coincide.map((n) => (
            <button
              key={n.id}
              onMouseDown={(e) => { e.preventDefault(); onElegir(n.id); cerrar(); }}
              style={{ display: "flex", alignItems: "center", gap: 8, width: "100%", padding: "8px 11px", border: "none", background: "none", cursor: "pointer", textAlign: "left", fontSize: "var(--text-base)" }}
            >
              <span style={{ width: 7, height: 7, borderRadius: 2, background: catDe(n.tipo).sol, flex: "none" }} />
              <span style={{ flex: 1, minWidth: 0, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{n.titulo}</span>
              <span style={{ fontSize: "var(--text-xs)", color: "var(--color-texto-tenue)" }}>{catDe(n.tipo).name}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function RuleBuilder({ conexion, campos, onActualizar }) {
  const { op, reglas } = condicionALista(conexion.condicion);
  const guardar = (nuevoOp, nuevasReglas) =>
    onActualizar(conexion.id, { condicion: listaACondicion(nuevoOp, nuevasReglas) });

  const cambiar = (i, cambios) =>
    guardar(op, reglas.map((r, j) => (j === i ? { ...r, ...cambios } : r)));
  const quitar = (i) => guardar(op, reglas.filter((_, j) => j !== i));
  const agregar = () => guardar(op, [...reglas, { campo: null, operador: "=", valor: "" }]);

  // Agrupar por formulario para desambiguar labels repetidos entre formularios.
  const porForm = campos.reduce((acc, c) => { (acc[c.formulario] = acc[c.formulario] || []).push(c); return acc; }, {});

  return (
    <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 8 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
        <span style={{ fontSize: "var(--text-micro)", fontWeight: 700, letterSpacing: ".4px", color: "var(--color-texto-debil)" }}>SI</span>
        {reglas.length > 1 && (
          <Select
            size="sm"
            style={{ width: 132 }}
            value={op}
            onChange={(e) => guardar(e.target.value, reglas)}
            aria-label="Cómo se combinan las condiciones"
          >
            <option value="y">se cumplen TODAS</option>
            <option value="o">se cumple ALGUNA</option>
          </Select>
        )}
      </div>

      {reglas.length === 0 && (
        <div style={{ fontSize: "var(--text-sm)", color: "var(--color-texto-debil)" }}>
          Sin condiciones: es la rama por defecto (si no).
        </div>
      )}

      {reglas.map((r, i) => {
        const campoSel = campos.find((c) => String(c.id) === String(r.campo));
        const ops = operadoresDe(campoSel);
        const operador = r.operador || "=";
        return (
          <div key={i} style={{ display: "flex", flexDirection: "column", gap: 5, borderLeft: `2px solid var(--color-division)`, paddingLeft: 9 }}>
            <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
              <Select
                size="sm"
                value={r.campo || ""}
                onChange={(e) => cambiar(i, { campo: e.target.value ? Number(e.target.value) : null, operador: "=", valor: "" })}
                aria-label={`Campo de la condición ${i + 1}`}
              >
                <option value="">elegí un campo…</option>
                {Object.entries(porForm).map(([form, cs]) => (
                  <optgroup key={form} label={form}>
                    {cs.map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}
                  </optgroup>
                ))}
              </Select>
              <button
                onClick={() => quitar(i)}
                title="Quitar esta condición"
                aria-label={`Quitar la condición ${i + 1}`}
                style={{ border: "none", background: "none", cursor: "pointer", color: "var(--color-texto-tenue)", display: "flex", padding: 3, flex: "none" }}
              >
                <Icon name="x" size={14} />
              </button>
            </div>

            {r.campo && (
              <div style={{ display: "flex", gap: 6 }}>
                <Select size="sm" style={{ width: 150 }} value={operador} onChange={(e) => cambiar(i, { operador: e.target.value })} aria-label={`Operador de la condición ${i + 1}`}>
                  {ops.map((o) => <option key={o} value={o}>{OPERADOR_LABEL[o] || o}</option>)}
                </Select>

                {/* «vacío» no lleva valor: pedirlo sería pedir un dato que no se usa. */}
                {SIN_VALOR.has(operador) ? null : campoSel?.opciones?.length && !CON_LISTA.has(operador) ? (
                  <Select size="sm" value={r.valor || ""} onChange={(e) => cambiar(i, { valor: e.target.value })} aria-label={`Valor de la condición ${i + 1}`}>
                    <option value="">valor…</option>
                    {campoSel.opciones.map((o) => <option key={o} value={o}>{o}</option>)}
                  </Select>
                ) : (
                  // key fuerza el refresh del defaultValue al cambiar de campo/operador.
                  <Input
                    key={`${r.campo}-${operador}`}
                    size="sm"
                    placeholder={operador === "entre" ? "desde, hasta" : CON_LISTA.has(operador) ? "uno, otro, otro más" : "valor"}
                    defaultValue={r.valor || ""}
                    onBlur={(e) => e.target.value !== (r.valor || "") && cambiar(i, { valor: e.target.value })}
                    aria-label={`Valor de la condición ${i + 1}`}
                  />
                )}
              </div>
            )}
          </div>
        );
      })}

      <button
        onClick={agregar}
        style={{ alignSelf: "flex-start", border: "none", background: "none", cursor: "pointer", color: "var(--color-accent)", fontSize: "var(--text-sm)", fontWeight: 600, padding: 0 }}
      >
        + Agregar condición
      </button>
    </div>
  );
}

// Pasos donde una persona ejecuta el trabajo: ahí tiene sentido decir "quién lo hace".
const TIPOS_CON_RESPONSABLE = ["form", "atencion", "accion", "espera"];

// Ayuda por tipo de nodo: para qué sirve y cómo se usa (helper del panel).
const AYUDA_NODO = {
  inicio: "Punto de arranque del flujo. Acá nace o entra el caso. Definí cómo entra: «Manual» (se crea desde Nuevo caso), «Solo por derivación» (lo manda otro flujo) o «Ambas».",
  form: "Muestra un formulario para cargar datos del caso. El caso se detiene hasta que alguien lo completa. Elegí qué formulario usar y, en «Responsable», qué grupos pueden completarlo.",
  decision: "Bifurca el camino según los datos ya cargados. En cada conexión de salida definí una o varias condiciones y decidí si tienen que cumplirse todas o alcanza con una; la salida sin condiciones es la rama por defecto (else).",
  accion: "Paso automático: ejecuta una acción del sistema y el flujo sigue solo (no se detiene). Útil para marcar un hito del proceso. (Ej.: «Solicitud de estudios» — en desarrollo.)",
  atencion: "Registra una atención profesional que queda en la historia clínica del paciente. Si activás «fila de espera», el paciente queda en cola y un médico lo llama desde un box antes de atenderlo.",
  derivar: "Envía el caso a otra área. Si además elegís un flujo de destino, abre un caso nuevo en ese flujo (ej.: ingreso → especialidad), vinculado al original. El caso de origen sigue hacia su cierre.",
  espera: "Fila de espera genérica: encola el caso (orden de llegada; urgentes primero) y, al llamarlo, avanza al SIGUIENTE paso. Si lo que sigue es atender al paciente, conviene usar el nodo «Atención» con la opción «fila de espera» (une espera + llamado + atención en un solo paso).",
  tiempo: "Pausa el caso por un período (dato informativo). Hoy se reactiva manualmente; la reactivación automática por tiempo es un pendiente.",
  estado: "Cambia el estado del caso (Recibido, En espera, Atendido, Cerrado…). Es automático: sirve para reflejar en qué etapa está el caso.",
  fin: "Cierra el caso: marca el estado como Cerrado y termina el recorrido. Un flujo puede tener varios nodos Fin.",
};

function PanelNodo({ nodo, version, flujoInstId, flujoAreaId, campos, onActualizar, onBorrar, onConectar, onBorrarConexion, onActualizarConexion }) {
  const [titulo, setTitulo] = useState(nodo.titulo);
  // La preferencia de ayuda se recuerda entre nodos (localStorage) en vez de
  // resetearse cada vez que se selecciona otro nodo.
  const [ayuda, setAyuda] = useState(() => localStorage.getItem("cauce.ayudaNodo") === "1");
  const [areas, setAreas] = useState([]);
  const [flujos, setFlujos] = useState([]);
  const [formularios, setFormularios] = useState([]);
  const [grupos, setGrupos] = useState([]);
  const [boxesArea, setBoxesArea] = useState([]);
  const cat = catDe(nodo.tipo);
  const salidas = version.conexiones.filter((c) => c.origen === nodo.id);
  const aplicaResponsable = TIPOS_CON_RESPONSABLE.includes(nodo.tipo);

  useEffect(() => {
    if (nodo.tipo === "derivar") {
      api.get(`/areas/?institucion=${flujoInstId}`).then((d) => setAreas(d.results || d));
      api.get(`/flujos/?institucion=${flujoInstId}`).then((d) => setFlujos(d.results || d));
    }
    if (nodo.tipo === "form") api.get(`/formularios/?institucion=${flujoInstId}`).then((d) => setFormularios(d.results || d));
    if (aplicaResponsable) api.get(`/grupos/?area__institucion=${flujoInstId}&activo=true`).then((d) => setGrupos(d.results || d));
    if ((nodo.tipo === "atencion" || nodo.tipo === "espera") && flujoAreaId)
      api.get(`/boxes/?area=${flujoAreaId}&activo=true`).then((d) => setBoxesArea(d.results || d));
  }, [nodo.tipo, flujoInstId, flujoAreaId, aplicaResponsable]);

  // Flujos de destino candidatos: los del área elegida, sin el flujo actual
  // (evita derivar a sí mismo) y que acepten derivación (no los "solo manual").
  const areaDestinoId = (nodo.config || {}).area_destino_id;
  const flujosDelArea = flujos.filter(
    (f) => f.area === areaDestinoId && f.id !== version.flujo && f.origen_inicio !== "manual"
  );
  const tienePublicada = (f) => (f.versiones || []).some((v) => v.estado === "publicada");

  const setConfig = (cambios) => onActualizar(nodo.id, { config: { ...(nodo.config || {}), ...cambios } });

  const asignados = new Set(nodo.grupos || []);
  const toggleGrupo = (gid) => {
    const next = asignados.has(gid) ? [...asignados].filter((x) => x !== gid) : [...asignados, gid];
    onActualizar(nodo.id, { grupos: next });
  };

  return (
    <div style={{ padding: 20 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
        <span style={{ width: 28, height: 28, borderRadius: 8, background: cat.tint, border: `1px solid ${cat.bd}`, display: "flex", alignItems: "center", justifyContent: "center", flex: "none" }}>
          <span style={{ width: 11, height: 11, borderRadius: 3, background: cat.sol }} />
        </span>
        <div style={{ flex: 1, fontSize: "var(--text-sm)", fontWeight: 700, letterSpacing: ".5px", color: cat.sol }}>{cat.name.toUpperCase()}</div>
        <button
          onClick={() => setAyuda((v) => { localStorage.setItem("cauce.ayudaNodo", v ? "0" : "1"); return !v; })}
          title="¿Qué hace este nodo?"
          aria-label="¿Qué hace este nodo?"
          style={{ width: 28, height: 28, borderRadius: "var(--radius-sm)", border: `1px solid ${ayuda ? "var(--color-accent)" : "var(--color-campo-borde)"}`, background: ayuda ? "var(--color-accent-50)" : "var(--color-superficie)", color: ayuda ? "var(--color-accent)" : "var(--color-texto-debil)", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", flex: "none" }}
        >
          <Icon name="help" size={15} />
        </button>
      </div>

      {ayuda && (
        <div style={{ display: "flex", gap: 9, background: "var(--color-accent-50)", border: `1px solid var(--color-accent-100)`, borderRadius: 10, padding: "11px 12px", marginBottom: 16 }}>
          <Icon name="help" size={15} style={{ color: "var(--color-accent)", marginTop: 1 }} />
          <div style={{ fontSize: 12.5, lineHeight: 1.5, color: "var(--color-texto-medio)" }}>
            {AYUDA_NODO[nodo.tipo] || "Nodo del flujo."}
          </div>
        </div>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <Field label="Título">
          <Input value={titulo} onChange={(e) => setTitulo(e.target.value)} onBlur={() => titulo !== nodo.titulo && onActualizar(nodo.id, { titulo })} />
        </Field>

        {nodo.tipo === "inicio" && (
          <Field label="¿Cómo entran los casos a este flujo?">
            <Select value={(nodo.config || {}).origen || "ambos"} onChange={(e) => setConfig({ origen: e.target.value })}>
              <option value="manual">Manual — se crea desde «Nuevo caso»</option>
              <option value="derivado">Solo por derivación — no se crea a mano</option>
              <option value="ambos">Ambas</option>
            </Select>
            <div style={{ marginTop: 6, fontSize: 11, color: "var(--color-texto-tenue)" }}>
              Define si el flujo aparece en «Nuevo caso» y/o si puede ser destino de una derivación.
            </div>
          </Field>
        )}

        {nodo.tipo === "form" && (
          <Field label="Formulario">
            <Select value={nodo.formulario || ""} onChange={(e) => onActualizar(nodo.id, { formulario: e.target.value || null })}>
              <option value="">— Elegir —</option>
              {formularios.map((f) => <option key={f.id} value={f.id}>{f.titulo}</option>)}
            </Select>
            {!nodo.formulario && <AvisoFalta texto="Elegí qué formulario se completa en este paso." />}
          </Field>
        )}

        {nodo.tipo === "atencion" && (
          <Field label="Fila de espera">
            <label style={{ display: "flex", alignItems: "center", gap: 9, fontSize: 13.5, cursor: "pointer" }}>
              <input
                type="checkbox"
                checked={!!(nodo.config || {}).con_fila}
                onChange={(e) => setConfig({ con_fila: e.target.checked })}
              />
              El paciente espera y se lo llama desde un box
            </label>
            {(nodo.config || {}).con_fila && (
              <div style={{ marginTop: 8, fontSize: 11.5, color: "var(--color-texto-debil)" }}>
                {!flujoAreaId
                  ? "Este flujo no tiene área: configurá un área para usar boxes."
                  : boxesArea.length === 0
                    ? "El área no tiene boxes. Cargalos en Estructura → área → Boxes."
                    : <>Se llama desde los boxes de <strong>{boxesArea[0].area_nombre}</strong>: {boxesArea.map((b) => b.nombre).join(", ")}.</>}
              </div>
            )}
          </Field>
        )}

        {nodo.tipo === "atencion" && (nodo.config || {}).con_fila && <PantallaUrl nodo={nodo} />}

        {nodo.tipo === "espera" && (
          <>
            <div style={{ fontSize: 12, color: "var(--color-texto-debil)" }}>
              Los casos esperan en una fila (FIFO + urgentes primero) y se los llama desde un box para que avancen al siguiente paso.
            </div>
            <PantallaUrl nodo={nodo} />
          </>
        )}

        {nodo.tipo === "derivar" && (
          <>
            <Field label="Área de destino">
              {/* Cambiar de área limpia el flujo elegido (puede no pertenecer a la nueva área). */}
              <Select
                value={areaDestinoId || ""}
                onChange={(e) => setConfig({ area_destino_id: e.target.value ? Number(e.target.value) : null, flujo_destino_id: null })}
              >
                <option value="">— Elegir —</option>
                {areas.map((a) => <option key={a.id} value={a.id}>{a.nombre}</option>)}
              </Select>
              {!areaDestinoId && <AvisoFalta texto="Elegí a qué área se deriva el caso." />}
            </Field>

            {areaDestinoId && (
              <Field label="Flujo de destino">
                <Select
                  value={(nodo.config || {}).flujo_destino_id || ""}
                  onChange={(e) => setConfig({ flujo_destino_id: e.target.value ? Number(e.target.value) : null })}
                >
                  <option value="">— Solo cambiar de área (sin abrir un flujo) —</option>
                  {flujosDelArea.map((f) => (
                    <option key={f.id} value={f.id} disabled={!tienePublicada(f)}>
                      {f.titulo}{tienePublicada(f) ? "" : " (sin publicar)"}
                    </option>
                  ))}
                </Select>
                <div style={{ marginTop: 6, fontSize: 11, color: "var(--color-texto-tenue)" }}>
                  {flujosDelArea.length === 0
                    ? "El área no tiene flujos que acepten derivación. Se derivará solo cambiando el área."
                    : (nodo.config || {}).flujo_destino_id
                      ? "Al derivar se abre un caso nuevo en este flujo (debe estar publicado)."
                      : "Sin flujo: la derivación solo cambia el área del caso."}
                </div>
              </Field>
            )}
          </>
        )}

        {nodo.tipo === "estado" && (
          <Field label="Estado a aplicar">
            <Select value={(nodo.config || {}).estado || ""} onChange={(e) => setConfig({ estado: e.target.value })}>
              <option value="">— Elegir —</option>
              {["recibido", "en_evaluacion", "en_espera", "derivado", "atendido", "cerrado"].map((s) => <option key={s} value={s}>{estadoCaso[s]?.label || s}</option>)}
            </Select>
            {!(nodo.config || {}).estado && <AvisoFalta texto="Elegí qué estado aplica este nodo." />}
          </Field>
        )}

        {nodo.tipo === "tiempo" && (
          <Field
            label="Duración de la espera"
            hint="El caso vuelve solo al vencer. Se entiende «6 horas», «2 días», «1 mes»."
          >
            <Input value={(nodo.config || {}).duracion || ""} onChange={(e) => setConfig({ duracion: e.target.value })} placeholder="6 horas" />
            {!(nodo.config || {}).duracion && (
              <AvisoFalta texto="Sin duración, el caso queda esperando hasta que alguien lo reactive a mano." />
            )}
          </Field>
        )}

        {/* Quién firma. Sólo en Atención: es el nodo que produce un acto
            registrable en la historia clínica. */}
        {nodo.tipo === "atencion" && (
          <div style={{ borderTop: `1px solid var(--color-division)`, paddingTop: 14, marginTop: 4 }}>
            <div style={{ fontSize: "var(--text-micro)", fontWeight: 700, letterSpacing: ".5px", color: "var(--color-texto-debil)", marginBottom: 10 }}>
              QUIÉN REGISTRA LA ATENCIÓN
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 7, marginBottom: 10 }}>
              {ROLES_FIRMA.map((r) => {
                const actuales = (nodo.config || {}).firma_roles || ["medico"];
                const marcado = actuales.includes(r.value);
                return (
                  <Checkbox
                    key={r.value}
                    checked={marcado}
                    onChange={() => {
                      const siguiente = marcado
                        ? actuales.filter((x) => x !== r.value)
                        : [...actuales, r.value];
                      // Vacío vuelve al default (médico): dejarlo sin roles no
                      // abriría el paso a cualquiera, pero confunde al leerlo.
                      setConfig({ firma_roles: siguiente.length ? siguiente : ["medico"] });
                    }}
                    label={r.label}
                  />
                );
              })}
            </div>
            <Checkbox
              checked={(nodo.config || {}).firma_matricula !== false}
              onChange={(e) => setConfig({ firma_matricula: e.target.checked })}
              label="Exigir matrícula para firmar"
            />
            <div style={{ fontSize: "var(--text-xs)", color: "var(--color-texto-debil)", lineHeight: 1.5, marginTop: 6 }}>
              Destildalo en pasos que registra alguien sin matrícula, como una admisión
              administrativa. La matrícula es lo que convierte a la firma en un acto
              profesional registrable.
            </div>
          </div>
        )}

        {/* SLA: sólo tiene sentido donde el caso ESPERA a una persona. */}
        {["form", "atencion", "espera"].includes(nodo.tipo) && (
          <div style={{ borderTop: `1px solid var(--color-division)`, paddingTop: 14, marginTop: 4 }}>
            <div style={{ fontSize: "var(--text-micro)", fontWeight: 700, letterSpacing: ".5px", color: "var(--color-texto-debil)", marginBottom: 10 }}>
              TIEMPO MÁXIMO EN ESTE PASO
            </div>
            <Field label="Avisar si tarda más de (minutos)" hint="Vacío = sin control de demora.">
              <Input
                type="number"
                min="1"
                value={(nodo.config || {}).sla_minutos ?? ""}
                onChange={(e) => setConfig({ sla_minutos: e.target.value ? Number(e.target.value) : null })}
                placeholder="30"
              />
            </Field>
            {(nodo.config || {}).sla_minutos ? (
              <Field label="Qué hacer al pasarse">
                <Select value={(nodo.config || {}).sla_accion || "avisar"} onChange={(e) => setConfig({ sla_accion: e.target.value })}>
                  <option value="avisar">Avisar al equipo responsable</option>
                  <option value="escalar">Avisar también al jefe del área</option>
                </Select>
              </Field>
            ) : null}
          </div>
        )}

        {nodo.tipo === "notificar" && (
          <>
            <Field label="Título del aviso">
              <Input
                value={(nodo.config || {}).titulo || ""}
                onChange={(e) => setConfig({ titulo: e.target.value })}
                placeholder="Paciente en espera prolongada"
              />
            </Field>
            <Field label="Detalle" hint="Podés usar {paciente} y se reemplaza por su nombre.">
              <Textarea
                value={(nodo.config || {}).detalle || ""}
                onChange={(e) => setConfig({ detalle: e.target.value })}
                placeholder="{paciente} lleva más de 2 horas esperando."
              />
            </Field>
            <Field label="¿A quién le llega?">
              <Select value={(nodo.config || {}).a || "grupos"} onChange={(e) => setConfig({ a: e.target.value })}>
                <option value="grupos">A los grupos responsables de este nodo</option>
                <option value="asignado">A quien tenga el caso</option>
              </Select>
            </Field>
          </>
        )}

        {nodo.tipo === "integracion" && (
          <>
            <Field label="URL del servicio">
              <Input
                value={(nodo.config || {}).url || ""}
                onChange={(e) => setConfig({ url: e.target.value })}
                placeholder="https://padron.gob.ar/api/afiliado"
              />
              {!(nodo.config || {}).url && <AvisoFalta texto="Sin URL, este paso no hace nada." />}
            </Field>
            <Field label="Método">
              <Select value={(nodo.config || {}).metodo || "GET"} onChange={(e) => setConfig({ metodo: e.target.value })}>
                <option value="GET">GET (consultar)</option>
                <option value="POST">POST (enviar)</option>
              </Select>
            </Field>
            <Field label="Guardar la respuesta en" hint="El dato queda cargado en el caso y se puede usar en una Decisión.">
              <Select value={(nodo.config || {}).guardar_en || ""} onChange={(e) => setConfig({ guardar_en: e.target.value ? Number(e.target.value) : null })}>
                <option value="">— No guardar nada —</option>
                {campos.map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}
              </Select>
            </Field>
            {(nodo.config || {}).guardar_en && (
              <Field label="Qué parte de la respuesta" hint="Ruta dentro del JSON, por ejemplo: afiliado.plan">
                <Input
                  value={(nodo.config || {}).ruta || ""}
                  onChange={(e) => setConfig({ ruta: e.target.value })}
                  placeholder="afiliado.plan"
                />
              </Field>
            )}
            <Checkbox
              checked={!!(nodo.config || {}).obligatorio}
              onChange={(e) => setConfig({ obligatorio: e.target.checked })}
              label="Detener el caso si el servicio no responde"
            />
            <div style={{ fontSize: "var(--text-xs)", color: "var(--color-texto-debil)", lineHeight: 1.5, marginTop: 4 }}>
              Sin tildar, si el servicio falla se anota en el historial y el caso sigue: un
              padrón caído no debería dejar a un paciente trabado.
              <br /><br />
              El destino tiene que estar habilitado por un administrador del sistema. Es a
              propósito: que alguien pueda elegir a qué servidor llama la aplicación es una
              decisión de infraestructura, no del diseño del flujo.
            </div>
          </>
        )}

        {/* Quién hace este paso: grupos responsables. */}
        {aplicaResponsable && (
          <Field label="Responsable — ¿quién lo hace?">
            {grupos.length === 0 ? (
              <div style={{ fontSize: 12, color: "var(--color-texto-tenue)" }}>
                No hay grupos en la institución. Crealos en Estructura → área → Grupos.
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 2, maxHeight: 190, overflow: "auto", border: `1px solid var(--color-campo-borde)`, borderRadius: 9, padding: 6 }}>
                {grupos.map((g) => {
                  const on = asignados.has(g.id);
                  return (
                    <label key={g.id} style={{ display: "flex", alignItems: "center", gap: 9, padding: "6px 7px", borderRadius: 7, cursor: "pointer", background: on ? "var(--color-accent-50)" : "transparent" }}>
                      <input type="checkbox" checked={on} onChange={() => toggleGrupo(g.id)} />
                      <span style={{ minWidth: 0 }}>
                        <span style={{ display: "block", fontSize: 12.5, fontWeight: 600, color: "var(--color-texto-medio)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{g.nombre}</span>
                        <span style={{ fontSize: 10.5, color: "var(--color-texto-tenue)" }}>{g.area_nombre}</span>
                      </span>
                    </label>
                  );
                })}
              </div>
            )}
            {grupos.length > 0 && asignados.size === 0 && (
              <AvisoFalta texto="Sin grupo asignado: nadie podrá tomar este paso." />
            )}
            {asignados.size > 0 && (
              <div style={{ marginTop: 6, fontSize: "var(--text-xs)", color: "var(--color-texto-debil)" }}>
                Cualquier integrante de {asignados.size === 1 ? "el grupo asignado" : `los ${asignados.size} grupos asignados`} podrá tomar este paso.
              </div>
            )}
          </Field>
        )}

        {/* Conexiones salientes */}
        <div style={{ borderTop: `1px solid var(--color-division)`, paddingTop: 14 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
            <div style={{ fontSize: 12.5, fontWeight: 700, color: "var(--color-texto-medio)" }}>Conexiones</div>
            <button onClick={onConectar} style={{ border: "none", background: "none", color: "var(--color-accent)", cursor: "pointer", fontSize: 12.5, fontWeight: 600 }}>+ conectar</button>
          </div>
          {salidas.length === 0 ? (
            <div style={{ fontSize: 12.5, color: "var(--color-texto-tenue)" }}>Sin salidas.</div>
          ) : (
            salidas.map((c) => {
              const destino = version.nodos.find((n) => n.id === c.destino);
              return (
                <div key={c.id} style={{ border: `1px solid var(--color-division)`, borderRadius: 9, padding: 10, marginBottom: 8 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                    <span style={{ fontSize: "var(--text-sm)", fontWeight: 600 }}>→ {destino?.titulo || "?"}</span>
                    <button onClick={() => onBorrarConexion(c.id)} style={{ border: "none", background: "none", color: "var(--color-danger)", cursor: "pointer", fontSize: "var(--text-xs)", padding: "4px 6px", borderRadius: "var(--radius-sm)" }}>quitar</button>
                  </div>
                  {nodo.tipo === "decision" && (
                    <>
                      <Input
                        style={{ height: 32, fontSize: 12.5 }}
                        placeholder="Etiqueta de la rama"
                        defaultValue={c.etiqueta}
                        onBlur={(e) => e.target.value !== c.etiqueta && onActualizarConexion(c.id, { etiqueta: e.target.value })}
                      />
                      <RuleBuilder conexion={c} campos={campos} onActualizar={onActualizarConexion} />
                    </>
                  )}
                </div>
              );
            })
          )}
        </div>

        <button onClick={() => onBorrar(nodo.id)} style={{ marginTop: 6, border: "none", background: "var(--color-badge-error-bg)", color: "var(--color-danger)", padding: "9px 0", borderRadius: "var(--radius-md)", cursor: "pointer", fontSize: "var(--text-base)", fontWeight: 600, display: "flex", alignItems: "center", justifyContent: "center", gap: 7 }}>
          <Icon name="trash" size={15} /> Eliminar nodo
        </button>
      </div>
    </div>
  );
}

// Pantalla de llamados del nodo: genera/muestra la URL pública (TV de sala de
// espera). El token se crea bajo demanda contra POST /nodos/<id>/pantalla/.
function PantallaUrl({ nodo }) {
  const [token, setToken] = useState(nodo.pantalla_token || "");
  const [cargando, setCargando] = useState(false);
  const [copiado, setCopiado] = useState(false);
  const url = token ? `${window.location.origin}/pantalla/${token}` : "";

  async function generar(rotar = false) {
    setCargando(true);
    try {
      const d = await api.post(`/nodos/${nodo.id}/pantalla/`, rotar ? { rotar: true } : {});
      setToken(d.token);
      nodo.pantalla_token = d.token; // refleja en el nodo cargado en memoria
    } finally {
      setCargando(false);
    }
  }

  async function copiar() {
    try {
      await navigator.clipboard.writeText(url);
      setCopiado(true);
      setTimeout(() => setCopiado(false), 1500);
    } catch { /* sin portapapeles: el usuario copia a mano */ }
  }

  return (
    <Field label="Pantalla de llamados">
      {!token ? (
        <>
          <button onClick={() => generar(false)} disabled={cargando}
            style={{ height: 36, padding: "0 14px", borderRadius: 9, background: "var(--color-accent-fuerte)", color: "var(--color-sobre-accent)", border: "none", cursor: "pointer", fontSize: 13, fontWeight: 600 }}>
            {cargando ? "Generando…" : "Generar URL de pantalla"}
          </button>
          <div style={{ marginTop: 6, fontSize: 11, color: "var(--color-texto-tenue)" }}>
            Una pantalla pública (TV de sala de espera) que muestra a quién se llama y desde qué box.
          </div>
        </>
      ) : (
        <>
          <div style={{ display: "flex", gap: 6 }}>
            <Input readOnly value={url} onFocus={(e) => e.target.select()} style={{ fontSize: 12, fontFamily: "monospace" }} />
            <button onClick={copiar} title="Copiar enlace"
              style={{ flex: "none", height: 38, padding: "0 12px", borderRadius: 9, background: copiado ? "var(--color-badge-green-bg)" : "var(--color-badge-neutral-bg)", color: copiado ? "var(--color-badge-green-fg)" : "var(--color-texto-suave)", border: "none", cursor: "pointer", fontSize: 12.5, fontWeight: 600 }}>
              {copiado ? "✓" : "Copiar"}
            </button>
          </div>
          <div style={{ display: "flex", gap: 14, marginTop: 8, alignItems: "center" }}>
            <a href={url} target="_blank" rel="noreferrer" style={{ fontSize: "var(--text-sm)", fontWeight: 600, color: "var(--color-accent)", textDecoration: "none" }}>
              Abrir pantalla ↗
            </a>
            <button onClick={() => { if (window.confirm("¿Regenerar el enlace? La pantalla abierta actualmente dejará de funcionar.")) generar(true); }} disabled={cargando}
              style={{ border: "none", background: "none", color: "var(--color-texto-debil)", cursor: "pointer", fontSize: "var(--text-xs)" }}>
              {cargando ? "…" : "Regenerar enlace"}
            </button>
          </div>
          <div style={{ marginTop: 6, fontSize: "var(--text-xs)", color: "var(--color-texto-debil)" }}>
            Abrila en el televisor de la sala. Al regenerar, el enlace anterior deja de funcionar.
          </div>
        </>
      )}
    </Field>
  );
}

function PanelValidacion({ problemas, onCerrar, onFocus }) {
  const sevColor = { error: "var(--color-danger)", aviso: "var(--color-badge-amber-fg)" };
  const sevBg = { error: "var(--color-badge-error-bg)", aviso: "var(--color-badge-amber-bg)" };
  return (
    <div style={{ padding: 20 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
        <div style={{ fontSize: "var(--text-md)", fontWeight: 700 }}>Validación</div>
        <button onClick={onCerrar} aria-label="Cerrar" style={{ border: "none", background: "none", cursor: "pointer", color: "var(--color-texto-debil)", display: "flex", padding: 4, borderRadius: "var(--radius-sm)" }}><Icon name="x" size={18} /></button>
      </div>
      {problemas.publicado && (
        <div style={{ fontSize: "var(--text-base)", background: "var(--color-badge-green-bg)", color: "var(--color-badge-green-fg)", padding: "10px 12px", borderRadius: "var(--radius-md)", marginBottom: 12, fontWeight: 600 }}>✓ Versión publicada</div>
      )}
      <div style={{ display: "flex", gap: 8, marginBottom: 14 }}>
        <Badge tone={problemas.errores ? "error" : "green"}>{problemas.errores} errores</Badge>
        <Badge tone="amber">{problemas.avisos} avisos</Badge>
      </div>
      {problemas.problemas.length === 0 ? (
        <div style={{ fontSize: "var(--text-base)", color: "var(--color-texto-debil)" }}>Sin problemas. {problemas.puede_publicar ? "Lista para publicar." : ""}</div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {problemas.problemas.map((p, i) => (
            <div
              key={i}
              role={p.nodo_id ? "button" : undefined}
              tabIndex={p.nodo_id ? 0 : undefined}
              onClick={() => p.nodo_id && onFocus(p.nodo_id)}
              onKeyDown={(e) => { if (p.nodo_id && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); onFocus(p.nodo_id); } }}
              style={{ border: `1px solid var(--color-division)`, borderRadius: "var(--radius-md)", padding: 12, cursor: p.nodo_id ? "pointer" : "default" }}
            >
              <span style={{ display: "inline-block", fontSize: "var(--text-micro)", fontWeight: 700, letterSpacing: ".4px", background: sevBg[p.sev], color: sevColor[p.sev], padding: "2px 7px", borderRadius: "var(--radius-sm)", marginBottom: 6 }}>
                {p.sev === "error" ? "ERROR" : "AVISO"}
              </span>
              <div style={{ fontSize: "var(--text-base)", fontWeight: 600 }}>{p.titulo}</div>
              <div style={{ fontSize: "var(--text-sm)", color: "var(--color-texto-debil)", marginTop: 2 }}>{p.detalle}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// Aviso inline ámbar para configuraciones incompletas de un nodo.
function AvisoFalta({ texto }) {
  return (
    <div style={{ marginTop: 6, display: "flex", alignItems: "center", gap: 6, fontSize: "var(--text-xs)", color: "var(--color-badge-amber-fg)", background: "var(--color-badge-amber-bg)", padding: "5px 8px", borderRadius: "var(--radius-sm)" }}>
      <span style={{ fontWeight: 800 }}>!</span> {texto}
    </div>
  );
}
