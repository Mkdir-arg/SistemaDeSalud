/**
 * El actor del recorrido guiado: maneja la app de verdad.
 *
 * El recorrido sembraba todo por `api.post` y mostraba un checklist que corría
 * con un temporizador: lo que se veía no era lo que pasaba. Acá está lo otro —
 * un intérprete de acciones que mueve el cursor, abre el diálogo, escribe letra
 * por letra, elige la opción por su texto y aprieta Guardar. Los datos quedan
 * cargados PORQUE el formulario se completó.
 *
 * Dos decisiones que explican casi todo el archivo:
 *
 * 1. Los elementos se resuelven por lo que se VE, no por atributos nuevos. Toda
 *    la app arma sus formularios con `<Field label="…">`, que envuelve el control
 *    en un `<label>`, y sus botones dicen lo que hacen. Así el actor entra a las
 *    30 pantallas sin instrumentar ninguna: si un día el botón deja de decir
 *    «Guardar», el recorrido se rompe fuerte y visible, que es mejor que un
 *    `data-tour` viejo apuntando a un nodo que ya no existe.
 *
 * 2. Nada espera un plazo fijo. React renderiza asincrónico y la red tarda lo
 *    que tarda: cada acción espera su CONDICIÓN (que aparezca el diálogo, que
 *    cierre, que el texto esté en pantalla) con un tope. Un `sleep(520)` que
 *    alcanza en la máquina del que programa es un recorrido roto en la demo.
 */

/** Se lanza cuando el recorrido se cancela a mitad de una acción. */
export class Cancelado extends Error {}

/**
 * Ritmo del actor, en milisegundos. Se divide por la velocidad elegida.
 *
 * `viaje` está atado a la transición del cursor en `CursorDemo` (700ms): si el
 * clic sale antes de que el puntero llegue, se ve al sistema apretando un botón
 * que el cursor todavía no tocó, que es justo la sensación que queremos evitar.
 */
export const RITMO = {
  viaje: 640,
  antesDelClick: 200,
  tecla: 38,
  trasClick: 420,
  trasGuardar: 640,
  entreOpciones: 150,
  leerCampo: 260,
};

// --------------------------------------------------------------------------- //
// Resolvedores: del texto que se ve al nodo del DOM
// --------------------------------------------------------------------------- //

/** Normaliza para comparar: sin dobles espacios, sin el asterisco de requerido. */
export function norm(s) {
  return String(s == null ? "" : s)
    .replace(/\s+/g, " ")
    .replace(/\s*\*\s*$/, "")
    .trim()
    .toLowerCase();
}

function visible(el) {
  return !!el && !el.disabled && el.getClientRects().length > 0;
}

/**
 * El ámbito de búsqueda: el diálogo abierto si hay uno, el documento si no.
 *
 * Importa para que «Guardar» no encuentre el botón de otra pantalla que quedó
 * detrás del modal, y para que «Nombre» sea el del formulario que estamos
 * completando y no el del buscador de arriba.
 */
export function ambito() {
  const dialogos = Array.from(document.querySelectorAll('[role="dialog"]')).filter(visible);
  return dialogos.length ? dialogos[dialogos.length - 1] : document.body;
}

export function hayDialogo() {
  return Array.from(document.querySelectorAll('[role="dialog"]')).some(visible);
}

/** El texto propio de un `<label>`, sin el de los `<option>` que tenga adentro. */
function textoDeEtiqueta(lab) {
  const primero = lab.firstElementChild;
  if (primero && !primero.matches("input, select, textarea")) return norm(primero.textContent);
  return norm(lab.getAttribute("aria-label"));
}

/**
 * El control de un campo, buscado por su etiqueta visible.
 *
 * Acepta prefijo a propósito: hay etiquetas que llevan el nombre de la
 * institución adentro («Rol en Hospital Escuela Cauce»), y el guion no puede
 * saberlo de antemano.
 */
export function buscarCampo(etiqueta, raiz = ambito()) {
  const buscada = norm(etiqueta);
  const labels = Array.from(raiz.querySelectorAll("label"));
  const exacto = labels.find((l) => textoDeEtiqueta(l) === buscada);
  const porPrefijo = labels.find((l) => textoDeEtiqueta(l).startsWith(buscada));
  const lab = exacto || porPrefijo;
  if (!lab) return null;
  const control = lab.querySelector("input, select, textarea");
  return visible(control) ? control : null;
}

/**
 * Un botón (o cualquier cosa clickeable) por su texto visible.
 *
 * Resuelve, con el mismo código, los botones de acción («Nueva área»), las filas
 * del árbol de áreas —que son `<button>` con el nombre adentro— y las pestañas
 * de sección. Por eso el guion habla de «tocar Agendas» sin saber si Agendas es
 * una pestaña, una tarjeta o un renglón.
 */
export function buscarBoton(texto, raiz = ambito()) {
  const buscado = norm(texto);
  const cands = Array.from(raiz.querySelectorAll('button, [role="button"], a[href]')).filter(visible);
  return (
    cands.find((b) => norm(b.textContent) === buscado)
    || cands.find((b) => norm(b.getAttribute("title")) === buscado)
    || cands.find((b) => norm(b.getAttribute("aria-label")) === buscado)
    || cands.find((b) => norm(b.textContent).includes(buscado))
    || cands.find((b) => norm(b.getAttribute("title")).includes(buscado))
    || null
  );
}

/** ¿Está este texto en pantalla? Para las esperas por resultado. */
export function hayTexto(texto) {
  return norm(document.body.textContent).includes(norm(texto));
}

/**
 * Escribe en un input de React.
 *
 * Asignar `.value` a secas no dispara el onChange: React guarda su propio valor
 * y lo pisa en el siguiente render. Hay que pasar por el setter del prototipo y
 * avisar con eventos que burbujeen.
 */
export function escribirEnControl(control, valor) {
  if (!control) return false;
  const proto = control.constructor.prototype;
  const setter = Object.getOwnPropertyDescriptor(proto, "value")?.set;
  if (!setter) return false;
  setter.call(control, valor);
  control.dispatchEvent(new Event("input", { bubbles: true }));
  control.dispatchEvent(new Event("change", { bubbles: true }));
  return true;
}

/** Elige una opción de un `<select>` por su texto, no por su value. */
export function elegirOpcion(select, texto) {
  if (!select || !select.options) return false;
  const buscado = norm(texto);
  const opciones = Array.from(select.options);
  const op = opciones.find((o) => norm(o.textContent) === buscado)
    || opciones.find((o) => norm(o.textContent).includes(buscado));
  if (!op) return false;
  return escribirEnControl(select, op.value);
}

// --------------------------------------------------------------------------- //
// El intérprete
// --------------------------------------------------------------------------- //

/**
 * Crea el actor.
 *
 * `ctl` es lo que el actor necesita del mundo de React y no puede tener acá:
 *  - vigente()  : false cuando el recorrido se canceló (cerrar, reiniciar, el
 *                 usuario tomó el control). Corta la acción a mitad.
 *  - pausado()  : true mientras está en pausa.
 *  - velocidad(): 1 o 2.
 *  - mover(x,y,click) : posiciona el cursor de demo.
 *  - contar(texto)    : lo que el panel muestra como acción en curso.
 *  - navegar(ruta)    : el navigate de React Router.
 */
export function crearActor(ctl) {
  const dormir = (ms) => new Promise((r) => setTimeout(r, Math.max(16, ms / ctl.velocidad())));

  async function pausa(ms) {
    await dormir(ms);
    while (ctl.pausado()) {
      if (!ctl.vigente()) throw new Cancelado();
      await dormir(140);
    }
    if (!ctl.vigente()) throw new Cancelado();
  }

  /** Espera una condición con tope. Devuelve si se cumplió. */
  async function hasta(pred, tope = 6000) {
    const limite = Date.now() + tope;
    while (Date.now() < limite) {
      if (pred()) return true;
      await pausa(110);
    }
    return pred();
  }

  /** Igual que `hasta`, pero devuelve el elemento que apareció. */
  async function hastaElemento(buscar, tope = 6000) {
    let el = null;
    await hasta(() => {
      el = buscar();
      return !!el;
    }, tope);
    return el;
  }

  /** Lleva el cursor al centro del elemento y espera a que llegue. */
  async function viajar(el) {
    const r = el.getBoundingClientRect();
    // Un poco a la izquierda del centro: la punta del puntero cae sobre el texto
    // del botón y no sobre el borde derecho, que es donde se ve raro.
    ctl.mover(r.left + Math.min(r.width * 0.42, r.width - 8), r.top + r.height * 0.55, false);
    await pausa(RITMO.viaje);
  }

  /** Viaja, hace la onda del clic, y recién entonces dispara el clic real. */
  async function clickear(el) {
    await viajar(el);
    ctl.mover(null, null, true);
    await pausa(RITMO.antesDelClick);
    el.click();
    await pausa(RITMO.trasClick);
  }

  async function tipear(control, valor) {
    control.focus?.();
    escribirEnControl(control, "");
    await pausa(RITMO.leerCampo / 2);
    for (let i = 0; i < valor.length; i += 1) {
      if (!ctl.vigente()) throw new Cancelado();
      escribirEnControl(control, valor.slice(0, i + 1));
      await pausa(RITMO.tecla);
    }
    await pausa(RITMO.leerCampo);
  }

  /**
   * Ejecuta una acción del guion.
   *
   * Devuelve "ok" o "no-actuado". Nunca tira por no encontrar un elemento: un
   * guion de sesenta acciones que muere en la doce es peor que el recorrido de
   * antes. Lo que no se pudo actuar lo completa el sembrado del paso, y el panel
   * lo dice.
   */
  async function ejecutar(a) {
    ctl.contar(a.decir || "");

    switch (a.t) {
      case "ir": {
        const menu = document.querySelector(a.menu);
        if (menu) await clickear(menu);
        ctl.navegar(a.ruta);
        await hasta(() => window.location.pathname === a.ruta, 3000);
        await pausa(RITMO.trasClick);
        return "ok";
      }

      // El directorio de la plataforma sólo se ve cuando no hay institución
      // elegida (ver Landing en App.jsx), así que para actuar el alta hay que
      // soltar el contexto primero. Es lo mismo que hace el super admin cuando
      // vuelve a la lista de instituciones.
      case "salir": {
        await ctl.salirAlDirectorio();
        await hasta(() => !!buscarBoton("Nueva institución"), 6000);
        await pausa(RITMO.trasClick);
        return "ok";
      }

      case "entrar": {
        const ok = await ctl.entrarAEscuela();
        await pausa(RITMO.trasGuardar);
        return ok ? "ok" : "no-actuado";
      }

      case "click": {
        const el = await hastaElemento(() => buscarBoton(a.boton), a.tope || 6000);
        if (!el) return "no-actuado";
        await clickear(el);
        // Si el clic abre un diálogo, esperarlo acá evita que la acción
        // siguiente busque un campo en la pantalla de atrás.
        if (a.abreDialogo) await hasta(hayDialogo, 4000);
        return "ok";
      }

      case "escribir": {
        const control = await hastaElemento(() => buscarCampo(a.campo), a.tope || 4000);
        if (!control) return "no-actuado";
        await viajar(control);
        await tipear(control, a.valor);
        return "ok";
      }

      case "elegir": {
        const control = await hastaElemento(() => buscarCampo(a.campo), a.tope || 4000);
        if (!control) return "no-actuado";
        await viajar(control);
        ctl.mover(null, null, true);
        await pausa(RITMO.antesDelClick);
        // Las opciones se recorren de a una para que se vea de dónde sale la que
        // queda elegida: en la demo importa que «Santiago Vera» sea uno de varios
        // profesionales posibles, no un valor que apareció solo.
        const opciones = Array.from(control.options || []);
        const destino = opciones.findIndex((o) => norm(o.textContent) === norm(a.opcion));
        if (destino > 0) {
          for (let i = 0; i <= destino; i += 1) {
            if (!ctl.vigente()) throw new Cancelado();
            escribirEnControl(control, opciones[i].value);
            await pausa(RITMO.entreOpciones);
          }
          await pausa(RITMO.leerCampo);
          return "ok";
        }
        const ok = elegirOpcion(control, a.opcion);
        await pausa(RITMO.leerCampo);
        return ok ? "ok" : "no-actuado";
      }

      case "boton": {
        const el = await hastaElemento(() => buscarBoton(a.texto), a.tope || 5000);
        if (!el) return "no-actuado";
        await clickear(el);
        await pausa(RITMO.trasGuardar);
        return "ok";
      }

      case "esperar": {
        const ok = await hasta(condicion(a.hasta), a.tope || 8000);
        return ok ? "ok" : "no-actuado";
      }

      case "recargar": {
        // Volver a montar la pantalla para que relea del servidor lo que el
        // sembrado acaba de crear. El editor de flujos tiene la versión en
        // estado local: sin esto muestra dos nodos donde ya hay seis.
        const volver = window.location.pathname;
        ctl.navegar(a.ruta);
        await pausa(RITMO.trasClick);
        ctl.navegar(volver);
        await pausa(RITMO.trasGuardar);
        return "ok";
      }

      default:
        return "no-actuado";
    }
  }

  return { ejecutar, pausa, hasta };
}

/** Traduce el `hasta:` del guion a un predicado. */
function condicion(spec) {
  if (spec === "sin-dialogo") return () => !hayDialogo();
  if (spec === "con-dialogo") return hayDialogo;
  if (typeof spec === "string" && spec.startsWith("texto:")) {
    const t = spec.slice(6);
    return () => hayTexto(t);
  }
  if (typeof spec === "string" && spec.startsWith("ruta:")) {
    const r = spec.slice(5);
    return () => window.location.pathname.startsWith(r);
  }
  return () => true;
}
