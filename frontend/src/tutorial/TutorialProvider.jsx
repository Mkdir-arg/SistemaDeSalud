import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/auth/AuthContext";
import { useInstitucion } from "@/auth/InstitutionContext";
import { Button, Select } from "@/components/ui";
import { Icon } from "@/components/icons";
import { cn } from "@/lib/cn";

import { Cancelado, crearActor } from "./actor";
import {
  ESCUELA_NOMBRE, YA_HECHO, escuelaTieneDatos, institucionEscuela, resetearEscuela, sembrar,
} from "./escenario";
import { DEMO_STEPS } from "./pasos";

const TutorialContext = createContext(null);

/**
 * Las velocidades del recorrido.
 *
 * Multiplican el ritmo: 0,25× tarda cuatro veces más que 1×. Abajo de 1 sirve
 * para mostrárselo a alguien y poder hablar encima; arriba de 1, para quien ya
 * lo vio y quiere llegar al final.
 */
const VELOCIDADES = [0.25, 0.5, 0.75, 1, 1.25, 1.5, 1.75, 2];

/** «0,5×» — con coma, que es como se escribe un decimal acá. */
const rotuloVelocidad = (v) => `${String(v).replace(".", ",")}×`;

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

/**
 * El rectángulo del elemento que el recorrido está señalando.
 *
 * Sólo se usa en los pasos de sólo mirar. Mientras el actor trabaja, el foco lo
 * marca el cursor sobre el control que está tocando, y un recuadro fijo en el
 * menú lateral competía con él.
 */
function useTarget(selector, activo, pathname) {
  const [rect, setRect] = useState(null);

  useEffect(() => {
    if (!activo || !selector) {
      setRect(null);
      return;
    }
    let raf = 0;

    // Medir y acercar son dos cosas distintas, y mezclarlas colgaba la app.
    //
    // Antes `medir` hacía las dos, y estaba suscripta al evento `scroll`: un
    // `scrollIntoView` suave emite decenas de eventos de scroll mientras anima,
    // cada uno volvía a llamar a `medir`, y `medir` volvía a arrancar el scroll
    // suave desde el principio. El scroll nunca terminaba y el bucle
    // rAF + scrollIntoView se comía el hilo principal: en las pantallas pesadas
    // —el tablero, el editor— el recorrido se veía congelado.
    //
    // Ahora se acerca UNA vez por paso, y el rectángulo se recalcula solo.
    const medir = () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        const el = document.querySelector(selector);
        if (!el) {
          setRect(null);
          return;
        }
        const r = el.getBoundingClientRect();
        setRect({ top: r.top, left: r.left, width: r.width, height: r.height });
      });
    };
    const acercar = window.setTimeout(() => {
      document.querySelector(selector)?.scrollIntoView({ block: "center", inline: "center", behavior: "smooth" });
      medir();
    }, 180);

    window.addEventListener("resize", medir);
    window.addEventListener("scroll", medir, true);
    return () => {
      window.clearTimeout(acercar);
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", medir);
      window.removeEventListener("scroll", medir, true);
    };
  }, [selector, activo, pathname]);

  return rect;
}

/**
 * Cuánto se queda en una pantalla que no tiene nada que actuar.
 *
 * Era fijo en 4,2 segundos para cualquier texto, y por eso el recorrido «iba
 * muy rápido»: los párrafos de estas pantallas tienen 200 y 300 caracteres, y
 * cuatro segundos no alcanzan ni para leer la mitad. Ahora sale del largo del
 * texto, a un ritmo de lectura tranquilo —unos 200 caracteres por cada 12
 * segundos— con piso y techo para que ni el título más corto pase de golpe ni
 * el párrafo más largo se eternice.
 */
function tiempoDeLectura(step) {
  const largo = `${step?.title || ""} ${step?.body || ""}`.trim().length;
  return clamp(2400 + largo * 58, 6000, 24000);
}

export function TutorialProvider({ children }) {
  const { user } = useAuth();
  const { institucion, setInstitucion, setVista } = useInstitucion();
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();

  const [activo, setActivo] = useState(false);
  const [arranque, setArranque] = useState(null); // null | "preguntando" | "preparando"
  const [paso, setPaso] = useState(0);
  // Sube para volver a lanzar el motor sobre el MISMO paso (retomar el control).
  const [intento, setIntento] = useState(0);
  const [errorDemo, setErrorDemo] = useState("");
  const [estado, setEstado] = useState("mirando"); // mirando | actuando | sembrando | saltado | listo
  const [accionActual, setAccionActual] = useState("");
  const [noActuadas, setNoActuadas] = useState(0);
  // Qué está sembrando, para no perder el «las otras cuatro áreas van igual que
  // esta» cuando la línea de acción pasa a nombrar cada cosa que entra.
  const [sembrado, setSembrado] = useState("");
  const [modo, setModo] = useState("actuado"); // actuado | rapido
  const [velocidad, setVelocidad] = useState(1);
  const [autoAvance, setAutoAvance] = useState(true);
  const [cursorDemo, setCursorDemo] = useState({ visible: false, x: 28, y: 28, click: false });
  const [vozActiva, setVozActiva] = useState(false);
  const [vozPausada, setVozPausada] = useState(false);
  const [tomoElControl, setTomoElControl] = useState(false);

  const step = DEMO_STEPS[paso];
  const actuando = estado === "actuando" || estado === "sembrando";
  const targetRect = useTarget(step?.target, activo && !actuando, location.pathname);

  // Refs porque el actor corre dentro de un async que no se vuelve a crear en
  // cada render: leer el state directo le daría el valor del render en que
  // arrancó, y «pausar» no pausaría nada.
  const corrida = useRef(0);
  const pausadoRef = useRef(false);
  const velocidadRef = useRef(1);
  const saltearRef = useRef(false);
  const clicksDemo = useRef({ n: 0, timer: 0 });
  const hechos = useRef(new Set());

  useEffect(() => { pausadoRef.current = !autoAvance; }, [autoAvance]);
  useEffect(() => { velocidadRef.current = velocidad; }, [velocidad]);

  // ----------------------------------------------------------------------- //
  // Narración
  // ----------------------------------------------------------------------- //
  const narrar = useCallback((texto) => {
    if (!puedeNarrar()) return;
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(texto);
    u.lang = "es-AR";
    u.rate = 0.95;
    u.onend = () => setVozPausada(false);
    u.onerror = () => setVozPausada(false);
    window.speechSynthesis.speak(u);
    setVozPausada(false);
  }, []);

  useEffect(() => {
    if (!activo || !vozActiva) return;
    narrar(textoNarracion(step, errorDemo));
  }, [activo, vozActiva, paso, errorDemo, step, narrar]);

  useEffect(() => {
    if (activo) return;
    if (puedeNarrar()) window.speechSynthesis.cancel();
    setVozPausada(false);
  }, [activo]);

  // ----------------------------------------------------------------------- //
  // El cursor de demo
  // ----------------------------------------------------------------------- //
  const mover = useCallback((x, y, click) => {
    setCursorDemo((c) => ({
      visible: true,
      x: x == null ? c.x : clamp(x, 8, window.innerWidth - 24),
      y: y == null ? c.y : clamp(y, 8, window.innerHeight - 24),
      click: !!click,
    }));
    if (click) window.setTimeout(() => setCursorDemo((c) => ({ ...c, click: false })), 420);
  }, []);

  // En los pasos de sólo mirar el cursor acompaña al recuadro, como antes.
  useEffect(() => {
    if (!activo || actuando || !targetRect) return undefined;
    const r = targetRect;
    mover(r.left + Math.min(r.width - 10, Math.max(14, r.width * 0.42)), r.top + r.height * 0.55, false);
    const t = window.setTimeout(() => mover(null, null, true), 620);
    return () => window.clearTimeout(t);
  }, [activo, actuando, targetRect, mover]);

  // ----------------------------------------------------------------------- //
  // Arranque
  // ----------------------------------------------------------------------- //
  /**
   * Tira la caché de consultas.
   *
   * Sin esto el recorrido trabajaba sobre datos que ya no existen, y de dos
   * formas distintas:
   *
   *  - Después de vaciar la escuela, los desplegables seguían mostrando las áreas
   *    de la institución borrada. El actor elegía una, y el POST del flujo
   *    reventaba con una violación de clave ajena contra un área que ya no está.
   *  - Después de sembrar, la pantalla que se estaba mostrando ya había pedido su
   *    lista vacía y no volvía a pedirla en 30 segundos: Internación y Farmacia
   *    se veían vacías con las camas y los insumos ya cargados.
   */
  const refrescarDatos = useCallback(() => {
    queryClient.invalidateQueries();
  }, [queryClient]);

  const cancelar = useCallback(() => { corrida.current += 1; }, []);

  const cerrar = useCallback(() => {
    cancelar();
    if (puedeNarrar()) window.speechSynthesis.cancel();
    setVozActiva(false);
    setVozPausada(false);
    setActivo(false);
    setArranque(null);
    setErrorDemo("");
    setTomoElControl(false);
    setCursorDemo((c) => ({ ...c, visible: false }));
  }, [cancelar]);

  /**
   * Arranca el recorrido.
   *
   * `desdeCero` vacía la institución escuela. Es un borrado en cascada, así que
   * nunca se decide acá: lo elige quien mira la demo, en el diálogo de arranque.
   */
  const empezar = useCallback(async ({ desdeCero }) => {
    cancelar();
    setArranque("preparando");
    setActivo(true);
    setErrorDemo("");
    hechos.current = new Set();
    saltearRef.current = !desdeCero;
    try {
      if (desdeCero) {
        await resetearEscuela();
        refrescarDatos();
        saltearRef.current = false;
      } else {
        // Continuando sobre una escuela ya cargada, el primer paso se saltea; sin
        // entrar acá al contexto, los pasos que siguen actuarían sobre la
        // institución en la que estaba parado el super admin.
        const inst = await institucionEscuela();
        if (inst) {
          setInstitucion(inst);
          setVista?.("sistema");
        }
      }
      setPaso(0);
      setIntento((n) => n + 1);
      setEstado("mirando");
      setAccionActual("");
      setNoActuadas(0);
      setAutoAvance(true);
      pausadoRef.current = false;
    } catch (e) {
      setErrorDemo(`No pude preparar el modo escuela: ${e?.message || "error inesperado"}`);
    } finally {
      setArranque(null);
    }
  }, [cancelar, setInstitucion, setVista, refrescarDatos]);

  /** Abre el recorrido. Si la escuela ya tiene datos, pregunta antes de borrar. */
  const iniciarDemo = useCallback(async () => {
    if (!user?.is_superuser) return;
    setErrorDemo("");
    setTomoElControl(false);
    try {
      if (await escuelaTieneDatos()) {
        setArranque("preguntando");
        setActivo(true);
        return;
      }
    } catch {
      // Si no se puede ni consultar, que lo diga el primer paso y no el arranque.
    }
    empezar({ desdeCero: false });
  }, [user, empezar]);

  // ----------------------------------------------------------------------- //
  // Navegación entre pasos
  // ----------------------------------------------------------------------- //
  useEffect(() => {
    // En los pasos actuados la ruta la maneja el guion: navegar acá le pisaría
    // la pantalla al actor en medio de un formulario.
    if (!activo || arranque || step?.guion) return;
    if (!step?.route || location.pathname === step.route) return;
    navigate(step.route);
  }, [activo, arranque, step, location.pathname, navigate]);

  const avanzar = useCallback(() => {
    cancelar();
    setPaso((p) => {
      if (p >= DEMO_STEPS.length - 1) {
        cerrar();
        return p;
      }
      return p + 1;
    });
  }, [cancelar, cerrar]);

  const volver = useCallback(() => {
    cancelar();
    setPaso((p) => Math.max(0, p - 1));
  }, [cancelar]);

  // ----------------------------------------------------------------------- //
  // El motor: ejecuta el guion del paso, o lo siembra si el modo es rápido
  // ----------------------------------------------------------------------- //
  const salirAlDirectorio = useCallback(async () => {
    setInstitucion(null);
    navigate("/");
  }, [setInstitucion, navigate]);

  const entrarAEscuela = useCallback(async () => {
    const inst = await institucionEscuela();
    if (!inst) return false;
    setInstitucion(inst);
    setVista?.("sistema");
    navigate("/inicio");
    return true;
  }, [setInstitucion, setVista, navigate]);

  // El motor. Ojo con `errorDemo`: NO es una condición de arranque ni una
  // dependencia. Cuando lo era, un paso que fallaba dejaba el recorrido clavado
  // para siempre —el efecto no volvía a correr y nadie avanzaba—, y eso es lo
  // que se ve como que el recorrido se tildó. Un paso que falla ahora se avisa
  // y se sigue: el sembrado ya dejó los datos completos igual.
  useEffect(() => {
    if (!activo || arranque) return undefined;
    if (!step) return undefined;

    const mia = corrida.current + 1;
    corrida.current = mia;
    let vivo = true;

    const ctl = {
      vigente: () => vivo && corrida.current === mia,
      pausado: () => pausadoRef.current,
      velocidad: () => velocidadRef.current,
      mover,
      contar: setAccionActual,
      navegar: navigate,
      salirAlDirectorio,
      entrarAEscuela,
    };
    const actor = crearActor(ctl);

    (async () => {
      try {
        // --- paso de sólo mirar -----------------------------------------
        if (!step.guion) {
          // Hay pantallas que sólo se miran pero que no tienen nada que mostrar
          // hasta que alguien cargue sus datos, y la app no tiene por dónde
          // cargarlos —camas, insumos—. Se siembran acá, antes de mostrarlas:
          // explicar una pantalla vacía es lo que hacía que la explicación
          // sonara a folleto.
          if (step.prepare && !hechos.current.has(step.prepare)) {
            setEstado("sembrando");
            const ctx = await sembrar(step.prepare, (que) => setAccionActual(que));
            if (!ctl.vigente()) return;
            if (ctx?.inst) setInstitucion(ctx.inst);
            hechos.current.add(step.prepare);
            refrescarDatos();
          }
          setEstado("mirando");
          setAccionActual("");
          await actor.pausa(tiempoDeLectura(step));
          if (ctl.vigente() && !pausadoRef.current) avanzar();
          return;
        }

        // --- ya estaba hecho: se muestra, no se vuelve a cargar ----------
        if (saltearRef.current && !hechos.current.has(step.prepare)) {
          const inst = await institucionEscuela();
          // Sin institución no hay nada hecho. Consultar igual sería peor que no
          // consultar: `?institucion=` vacío no filtra, y el primer área de
          // cualquier hospital daría el paso por cargado.
          const yaEsta = (inst || step.prepare === "institucion")
            && YA_HECHO[step.prepare]
            && await YA_HECHO[step.prepare](inst || {});
          if (!ctl.vigente()) return;
          if (yaEsta) {
            hechos.current.add(step.prepare);
            setEstado("saltado");
            setAccionActual("Esto ya estaba cargado: lo dejamos como está");
            if (step.route && window.location.pathname !== step.route) navigate(step.route);
            await actor.pausa(tiempoDeLectura(step));
            if (ctl.vigente() && !pausadoRef.current) avanzar();
            return;
          }
        }

        // --- modo rápido: los datos sin la actuación ---------------------
        if (modo === "rapido") {
          setEstado("sembrando");
          setAccionActual("Cargando el escenario por sistema");
          const ctx = await sembrar(step.prepare, (que) => setAccionActual(`Cargando ${que}`));
          if (!ctl.vigente()) return;
          if (ctx?.inst) setInstitucion(ctx.inst);
          hechos.current.add(step.prepare);
          refrescarDatos();
          setEstado("listo");
          await actor.pausa(1600);
          if (ctl.vigente() && !pausadoRef.current) avanzar();
          return;
        }

        // --- actuado ----------------------------------------------------
        let fallidas = 0;
        setNoActuadas(0);
        for (const accion of step.guion) {
          if (!ctl.vigente()) return;
          if (accion.t === "sembrar") {
            setEstado("sembrando");
            setSembrado(accion.decir || "Cargando el resto por sistema");
            setAccionActual(accion.decir || "Cargando el resto por sistema");
            const ctx = await sembrar(step.prepare, (que) => setAccionActual(que));
            if (!ctl.vigente()) return;
            if (ctx?.inst) setInstitucion(ctx.inst);
            refrescarDatos();
            await actor.pausa(1100);
            setSembrado("");
            continue;
          }
          setEstado("actuando");
          const r = await actor.ejecutar(accion);
          if (r === "no-actuado") fallidas += 1;
          setNoActuadas(fallidas);
        }

        // La red: el sembrado se corre siempre al cerrar el paso. Es idempotente,
        // así que sobre lo que el actor ya cargó no hace nada; y cuando una
        // acción no encontró su botón, deja el paso completo igual. Un recorrido
        // que se corta a la mitad y deja la institución a medio construir es
        // peor que uno que avisa que tuvo que completar por sistema.
        setEstado("sembrando");
        if (fallidas) setAccionActual("Completamos por sistema lo que no se pudo actuar");
        const ctx = await sembrar(step.prepare, fallidas ? (que) => setAccionActual(que) : undefined);
        if (!ctl.vigente()) return;
        if (ctx?.inst) setInstitucion(ctx.inst);
        hechos.current.add(step.prepare);
        refrescarDatos();

        setEstado("listo");
        setAccionActual(fallidas ? `${fallidas} acción(es) se completaron por sistema` : "Paso terminado");
        await actor.pausa(1800);
        if (ctl.vigente() && !pausadoRef.current) avanzar();
      } catch (e) {
        if (e instanceof Cancelado || !ctl.vigente()) return;
        setErrorDemo(`En este paso falló algo: ${e?.message || "error inesperado"}`);
        setEstado("mirando");
        setAccionActual("");
        try {
          await actor.pausa(9000);
        } catch {
          return; // se canceló mientras mostraba el aviso
        }
        if (!ctl.vigente()) return;
        setErrorDemo("");
        if (!pausadoRef.current) avanzar();
      }
    })();

    return () => { vivo = false; };
    // `location.pathname` queda afuera a propósito: el guion navega, y volver a
    // arrancar el motor en cada navegación reiniciaría el paso desde el principio.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activo, arranque, paso, modo, intento]);

  // ----------------------------------------------------------------------- //
  // Si alguien toca la app, el actor suelta el volante
  // ----------------------------------------------------------------------- //
  useEffect(() => {
    if (!activo || !actuando) return undefined;
    const alTocar = (e) => {
      // El actor llama a `el.click()`, que genera un evento no confiable y no
      // dispara pointerdown: `isTrusted` separa limpio a la persona del actor.
      if (!e.isTrusted) return;
      if (e.target?.closest?.("[data-tour-panel]")) return;
      cancelar();
      setTomoElControl(true);
      setAutoAvance(false);
      setEstado("mirando");
      setAccionActual("Tomaste el control");
    };
    document.addEventListener("pointerdown", alTocar, true);
    document.addEventListener("keydown", alTocar, true);
    return () => {
      document.removeEventListener("pointerdown", alTocar, true);
      document.removeEventListener("keydown", alTocar, true);
    };
  }, [activo, actuando, cancelar]);

  // ----------------------------------------------------------------------- //
  // Disparador: tres clics del super admin
  // ----------------------------------------------------------------------- //
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
      clicksDemo.current.timer = window.setTimeout(() => { clicksDemo.current.n = 0; }, 2500);
    }
    document.addEventListener("click", alClick, true);
    return () => {
      document.removeEventListener("click", alClick, true);
      window.clearTimeout(clicksDemo.current.timer);
    };
  }, [user, iniciarDemo]);

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

  const retomar = () => {
    setTomoElControl(false);
    setAutoAvance(true);
    // Relanza el motor sobre el mismo paso, que reejecuta el guion desde el
    // principio: es lo correcto, porque el formulario quedó a medio llenar.
    corrida.current += 1;
    setEstado("actuando");
    setIntento((n) => n + 1);
  };

  const value = useMemo(() => ({ iniciarDemo, activo }), [iniciarDemo, activo]);

  return (
    <TutorialContext.Provider value={value}>
      {children}
      {activo && arranque === "preguntando" && (
        <DialogoArranque
          onDesdeCero={() => empezar({ desdeCero: true })}
          onContinuar={() => empezar({ desdeCero: false })}
          onCerrar={cerrar}
        />
      )}
      {activo && arranque !== "preguntando" && (
        <TutorialOverlay
          step={step}
          rect={actuando ? null : targetRect}
          paso={paso}
          total={DEMO_STEPS.length}
          error={errorDemo}
          estado={arranque === "preparando" ? "preparando" : estado}
          accion={accionActual}
          sembrado={sembrado}
          noActuadas={noActuadas}
          modo={modo}
          velocidad={velocidad}
          tomoElControl={tomoElControl}
          vozActiva={vozActiva}
          vozPausada={vozPausada}
          vozDisponible={puedeNarrar()}
          enMarcha={autoAvance}
          onCerrar={cerrar}
          onVolver={volver}
          onAvanzar={avanzar}
          onPausar={() => setAutoAvance((v) => !v)}
          onModo={() => setModo((m) => (m === "actuado" ? "rapido" : "actuado"))}
          onVelocidad={setVelocidad}
          onRetomar={retomar}
          onAlternarVoz={alternarVoz}
          onPausarVoz={pausarVoz}
        />
      )}
      {activo && arranque !== "preguntando" && <CursorDemo cursor={cursorDemo} />}
    </TutorialContext.Provider>
  );
}

/**
 * Lo primero que ve quien arranca el recorrido con la escuela ya cargada.
 *
 * El actor completa los formularios de la app, así que no tiene la red del
 * sembrado: sobre un área que ya existe, el alta se come un «ya existe un área
 * con ese nombre». Las dos salidas honestas son vaciar o saltear, y ninguna de
 * las dos la puede decidir el sistema solo: vaciar borra en cascada.
 */
function DialogoArranque({ onDesdeCero, onContinuar, onCerrar }) {
  return (
    <div className="fixed inset-0 z-[95] flex items-center justify-center bg-ink/45 p-lg" data-tour-panel>
      <div role="dialog" aria-modal="true" aria-label="Empezar el recorrido guiado"
           className="w-[min(520px,100%)] rounded-lg bg-superficie shadow-modal">
        <div className="flex items-center justify-between border-b border-division px-xl py-lg">
          <div className="text-lg font-bold">Recorrido guiado</div>
          <button onClick={onCerrar} aria-label="Cerrar" className="flex rounded-sm p-1 text-texto-debil hover:text-texto">
            <Icon name="x" size={18} />
          </button>
        </div>
        <div className="flex flex-col gap-3 p-xl">
          <p className="text-md text-texto-suave">
            «{ESCUELA_NOMBRE}» ya tiene datos cargados. El recorrido completa los formularios de la
            app de verdad, así que sobre lo que ya existe no puede volver a darlo de alta.
          </p>
          <p className="text-md text-texto-suave">
            <b className="text-texto">Empezar de cero</b> vacía la institución de capacitación —áreas,
            usuarios, flujos, pacientes y casos— y la construye de nuevo delante tuyo.{" "}
            <b className="text-texto">Continuar</b> deja lo cargado y sólo actúa lo que falta.
          </p>
        </div>
        <div className="flex flex-wrap justify-end gap-2.5 border-t border-division px-xl py-lg">
          <Button variant="secondary" onClick={onContinuar}>Continuar donde quedó</Button>
          <Button onClick={onDesdeCero}>Empezar de cero</Button>
        </div>
      </div>
    </div>
  );
}

const ETIQUETA_ESTADO = {
  preparando: "Preparando",
  actuando: "Actuando",
  sembrando: "Sembrando",
  saltado: "Ya estaba",
  listo: "Listo",
  mirando: "Viendo",
};

function TutorialOverlay({
  step, rect, paso, total, error, estado, accion, sembrado, noActuadas, modo, velocidad, tomoElControl,
  vozActiva, vozPausada, vozDisponible, enMarcha,
  onCerrar, onVolver, onAvanzar, onPausar, onModo, onVelocidad, onRetomar, onAlternarVoz, onPausarVoz,
}) {
  const trabajando = estado === "actuando" || estado === "sembrando" || estado === "preparando";
  const detalle = accion || (trabajando ? "Cargando" : "Mostrando pantalla");

  return (
    <div className="pointer-events-none fixed inset-0 z-[80]">
      {rect && (
        <div
          className="absolute rounded-lg border-2 border-accent bg-accent-50/10 shadow-[0_0_0_4px_rgba(72,79,210,.12)]"
          style={{ top: rect.top - 6, left: rect.left - 6, width: rect.width + 12, height: rect.height + 12 }}
        />
      )}
      <section
        role="status"
        aria-live="polite"
        aria-label="Recorrido guiado"
        data-tour-panel
        className="pointer-events-auto fixed bottom-4 left-1/2 w-[min(1040px,calc(100vw-32px))] -translate-x-1/2 rounded-lg border border-borde bg-superficie/95 p-3 shadow-modal backdrop-blur"
      >
        <div className="grid gap-3 md:grid-cols-[1fr_auto] md:items-center">
          <div className="min-w-0">
            <div className="mb-1 flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-2 rounded-pill bg-accent-50 px-3 py-1 text-sm font-bold text-accent">
                <Icon name={trabajando ? "refresh" : "play"} size={13} className={cn(trabajando && "animate-spin")} />
                Recorrido guiado
              </span>
              <span className="text-sm font-semibold text-texto-tenue">{paso + 1} de {total}</span>
              <span className="rounded-pill bg-superficie-2 px-2 py-0.5 text-sm font-semibold text-texto-suave">
                {modo === "actuado" ? "actuado" : "rápido"}
              </span>
              {enMarcha && !error && !tomoElControl && (
                <span className="text-sm font-semibold text-badge-green-fg">automático</span>
              )}
              {tomoElControl && <span className="text-sm font-bold text-badge-amber-fg">en tus manos</span>}
            </div>

            {/* El título arriba y la explicación abajo, entera.
                Estaban uno al lado del otro y el párrafo llevaba `truncate`: se
                veía la primera línea y tres puntos. Toda la explicación de la
                pantalla quedaba escrita y sin leerse, que es la peor forma de
                que un recorrido guiado parezca vago. */}
            <h2 className="text-base font-bold">{step?.title}</h2>
            {step?.body && (
              <p className="mt-0.5 max-w-[85ch] text-sm leading-relaxed text-texto-suave">{step.body}</p>
            )}
            {/* El error va como aviso al lado de la explicación, no en lugar de
                ella: el paso falló pero el recorrido sigue, y la pantalla que
                está mostrando se sigue explicando igual. */}
            {error && (
              <p className="mt-1.5 flex items-start gap-1.5 rounded-md bg-badge-amber-bg px-2 py-1 text-sm font-semibold text-badge-amber-fg">
                <Icon name="alert" size={14} className="mt-0.5 flex-none" />
                {error}
              </p>
            )}

            <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
              <span className={cn("font-bold", estado === "saltado" ? "text-texto-tenue" : "text-accent")}>
                {ETIQUETA_ESTADO[estado] || "Viendo"}
              </span>
              {/* Sembrando, el renglón de acción va nombrando cada cosa que
                  entra, así que el «las otras cuatro áreas van igual que esta»
                  se muestra al lado y no se pierde. */}
              {sembrado && (
                <span className="font-semibold text-texto-suave">{sembrado} ·</span>
              )}
              <span className="rounded-md bg-superficie-2 px-2 py-1 font-semibold text-texto-suave">{detalle}</span>
              {noActuadas > 0 && (
                <span className="rounded-md bg-badge-amber-bg px-2 py-1 font-semibold text-badge-amber-fg">
                  {noActuadas} sin actuar
                </span>
              )}
            </div>

            <div className="mt-2 h-1.5 overflow-hidden rounded-pill bg-division">
              <div className="h-full rounded-pill bg-accent transition-all" style={{ width: `${((paso + 1) / total) * 100}%` }} />
            </div>
          </div>

          <div className="flex flex-wrap justify-end gap-2">
            {tomoElControl ? (
              <Button type="button" size="sm" onClick={onRetomar}>Que siga el recorrido</Button>
            ) : (
              <Button type="button" size="sm" variant="secondary" onClick={onPausar}>
                {enMarcha ? "Pausar" : "Reanudar"}
              </Button>
            )}
            {/* Ocho pasos y no un botón que alterna 1×/2×: mostrarle esto a
                alguien y poder hablar encima necesita bajar de 1, y cada persona
                lee a su ritmo. */}
            <Select
              size="sm"
              aria-label="Velocidad del recorrido"
              title="Velocidad del recorrido"
              value={velocidad}
              onChange={(e) => onVelocidad(Number(e.target.value))}
              className="w-24"
            >
              {VELOCIDADES.map((v) => (
                <option key={v} value={v}>{rotuloVelocidad(v)}</option>
              ))}
            </Select>
            <Button
              type="button" size="sm" variant="secondary" onClick={onModo}
              title={modo === "actuado"
                ? "Cargar el escenario sin actuarlo, para ir más rápido"
                : "Volver a completar los formularios en pantalla"}
            >
              {modo === "actuado" ? "Ir rápido" : "Actuar"}
            </Button>
            <Button
              type="button" size="sm" variant={vozActiva ? "primary" : "secondary"}
              disabled={!vozDisponible} onClick={onAlternarVoz}
              title={vozDisponible ? "Leer en voz alta este recorrido" : "Este navegador no tiene narrador disponible"}
            >
              <Icon name={vozActiva ? "x" : "play"} size={13} />
              {vozActiva ? "Silenciar" : "Narrar"}
            </Button>
            {vozActiva && (
              <Button type="button" size="sm" variant="secondary" onClick={onPausarVoz}>
                {vozPausada ? "Seguir voz" : "Pausar voz"}
              </Button>
            )}
            {paso > 0 && <Button variant="secondary" size="sm" onClick={onVolver}>Anterior</Button>}
            <Button size="sm" onClick={onAvanzar}>
              {paso === total - 1 ? "Finalizar" : "Siguiente"}
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
        <svg width="28" height="28" viewBox="0 0 28 28" className="drop-shadow-[0_3px_8px_rgba(16,24,40,.35)]">
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
