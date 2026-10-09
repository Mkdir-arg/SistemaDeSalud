import { useEffect, useRef } from "react";
import { Link } from "react-router-dom";

import { Icon } from "@/components/icons";
import { Logo } from "@/components/Logo";
import { useTema } from "@/lib/tema";

/**
 * Landing pública de HEN (lámina 0 de los paquetes claro y oscuro).
 *
 * No consulta la API: todo lo que muestra es fijo. Las cifras y alertas son de
 * ejemplo y así se rotulan; reemplazarlas por datos reales requiere una fuente
 * pública autorizada.
 *
 * Los destinos externos (demo, legales, soporte) solo aparecen si el despliegue
 * los configura. Sin un canal aprobado no se muestra un enlace que parezca
 * funcionar y no lleve a ningún lado.
 */
const https = (valor) => (valor?.trim().startsWith("https://") ? valor.trim() : null);
const DEMO_CONFIGURADA = import.meta.env.VITE_DEMO_URL?.trim();
const DEMO_URL = DEMO_CONFIGURADA?.startsWith("mailto:") ? DEMO_CONFIGURADA : https(DEMO_CONFIGURADA);
const SOPORTE_EMAIL = import.meta.env.VITE_SOPORTE_EMAIL?.trim();
const LEGALES = [
  ["Términos", https(import.meta.env.VITE_TERMINOS_URL)],
  ["Privacidad", https(import.meta.env.VITE_PRIVACIDAD_URL)],
  ["Accesibilidad", https(import.meta.env.VITE_ACCESIBILIDAD_URL)],
].filter(([, url]) => url);

const INDICADORES = [
  ["Pacientes atendidos", "128", "+9 %"],
  ["Espera promedio", "18 min", "−27 %"],
  ["Ocupación", "71 %", "19 de 26"],
  ["Cobrado del mes", "66 %", "$ 6,1 M"],
];
const BARRAS = [19, 28, 39, 56, 75, 88, 69, 53, 44, 32, 24, 17];
const PICO = [4, 5];
const ALERTAS = [
  ["Guardia sobre el objetivo", "58 min · 12 en fila"],
  ["4 derivaciones sin respuesta", "Más de 24 h"],
  ["Stock bajo en 6 insumos", "Botiquín de guardia"],
];
const CIFRAS = [
  ["26", "instituciones en la red"],
  ["1.284", "profesionales activos"],
  ["18.402", "pacientes por semana"],
  ["9", "financiadores con convenio"],
];
const TRIAGE = [
  ["Rojo", 1, "var(--color-danger)"],
  ["Naranja", 3, "var(--color-nodo-integracion-sol)"],
  ["Amarillo", 6, "var(--color-nodo-decision-sol)"],
  ["Verde", 4, "var(--color-nodo-inicio-sol)"],
  ["Azul", 2, "var(--color-nodo-accion-sol)"],
];
const CAMAS = Array.from({ length: 24 }, (_, i) => i);
const TUBOS = [42, 72, 55, 86];
const FILA = [["Llamando", "Paciente 14", "Consultorio 3"], ["Presente", "Paciente 15", "En sala de espera"]];
const HISTORIA = [["Alergias", "Penicilina"], ["Firmada por", "Dra. R. · M.N."]];
const STOCK = [["Ibuprofeno 400", 80, "var(--color-brand-teal)"], ["Guantes M", 15, "var(--color-danger)"]];
const CIRCUITO = ["Admisión", "Triage", "Sala", "Atención"];
const BENEFICIOS = [
  { titulo: "Atención sin filas", detalle: "Turnos, presente al llegar, fila ordenada y llamado al consultorio. El paciente espera donde quiere.", icono: "users", destacado: true, ancho: true, grafico: "fila" },
  { titulo: "Sistema de Triage", detalle: "Guardias ordenadas según prioridad: cada paciente se atiende en el orden que su urgencia requiere.", icono: "activity", alto: true, grafico: "triage" },
  { titulo: "Historia clínica firmada", detalle: "Alergias, estudios, recetas y registro de quién accedió a cada dato.", icono: "fileText", grafico: "historia" },
  { titulo: "Internación", detalle: "Ocupación de camas por sector, asignación desde el caso, pases y egresos.", icono: "bed", ancho: true, grafico: "camas" },
  { titulo: "Laboratorio e imágenes", detalle: "Órdenes y resultados integrados a la atención de cada paciente.", icono: "flask", grafico: "laboratorio" },
  { titulo: "Farmacia e insumos", detalle: "Stock por depósito y lote, alertas de faltantes y vencimientos, y trazabilidad del lote hasta el paciente.", icono: "cube", grafico: "stock" },
  { titulo: "Coberturas y cobros", detalle: "Cupos, copagos y saldos calculados según cada convenio.", icono: "wallet", completaFila: true, grafico: "cobertura" },
  { titulo: "App para pacientes", detalle: "Turnos, presente al llegar, aviso de llamado, resultados y cobertura desde el celular, con la marca de tu institución.", icono: "calendar", ancho: true, enlaceApp: true, grafico: "app" },
  { titulo: "Circuitos configurables", detalle: "Cada institución dibuja su circuito de atención y ese diagrama pasa a ser el sistema. Cambiarlo no afecta los casos en curso.", icono: "workflow", ancho: true, grafico: "circuito" },
  { titulo: "Red de establecimientos", detalle: "Derivaciones entre instituciones, con aceptación, traslado y recepción en destino.", icono: "map", ancho: true, grafico: "red" },
];

const FOCO = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent";
const CTA_PRINCIPAL = `hen-cta inline-flex h-10 items-center rounded-md px-4.5 text-sm font-medium text-sobre-accent ${FOCO}`;
const CTA_TERCIARIO = `inline-flex h-10 items-center rounded-md border border-borde bg-superficie px-4.5 text-sm font-medium text-texto transition-colors hover:border-accent hover:text-accent ${FOCO}`;
// Títulos de sección: la lámina los lleva a ~36 px en escritorio. La escala del
// sistema termina en 24 px para texto, por eso el tamaño va acotado acá.
const TITULO_SECCION = "text-balance text-[clamp(1.75rem,3.2vw,2.25rem)] font-bold leading-tight tracking-[-.03em]";
const ENLACE_SUAVE = `rounded-sm transition-colors hover:text-accent ${FOCO}`;

/** Entrada escalonada del primer pantallazo; `retardo` en milisegundos. */
const entrada = (retardo) => ({ className: "landing-entrada", style: { "--retardo": `${retardo}ms` } });

function Marca() {
  return <span translate="no" className="inline-flex items-center gap-2 text-sm font-bold"><span aria-hidden="true"><Logo size={24} /></span>HEN</span>;
}

/**
 * Línea de pulso. Con `degradeId` va de violeta a teal, como la que cruza la
 * vista ilustrativa; sin él toma el color del texto. El trazo es estático.
 */
function Pulso({ className, degradeId }) {
  return <svg aria-hidden="true" viewBox="0 0 1000 58" preserveAspectRatio="none" className={`pointer-events-none ${className}`}>
    {degradeId && <defs><linearGradient id={degradeId} x1="0" x2="1" y1="0" y2="0"><stop offset="0" stopColor="var(--color-accent)" /><stop offset=".2" stopColor="var(--color-brand-teal)" /></linearGradient></defs>}
    <path d="M0 30H72l12-22 13 49 13-57 13 42 9-12H1000" fill="none" stroke={degradeId ? `url(#${degradeId})` : "currentColor"} strokeWidth="1.2" vectorEffect="non-scaling-stroke" />
  </svg>;
}

function VistaIlustrativa() {
  const { className, style } = entrada(240);
  return <figure aria-labelledby="vista-ilustrativa" style={style} className={`${className} relative mx-auto mt-16 max-w-[980px] sm:mt-20`}>
    <div aria-hidden="true" className="presentacion-brillo pointer-events-none absolute inset-x-[15%] -top-10 h-28" />
    {/* Cruza la pantalla de lado a lado; el contenedor raíz recorta el sobrante. */}
    <Pulso degradeId="pulso-degrade" className="absolute left-1/2 top-1/2 h-[58px] w-screen -translate-x-1/2 -translate-y-1/2 opacity-80" />
    <div className="relative rounded-lg border border-borde bg-superficie p-3 shadow-float sm:p-4">
      <div className="mb-3 flex items-center justify-between gap-3 text-xs text-texto-suave">
        <span aria-hidden="true" className="tracking-[.2em]">●●●</span>
        <p id="vista-ilustrativa">Vista ilustrativa · datos de ejemplo</p>
      </div>
      <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
        {INDICADORES.map(([titulo, valor, detalle]) => <div key={titulo} className="rounded-md border border-borde bg-superficie-2 p-3">
          <p className="text-[11px] text-texto-suave">{titulo}</p>
          <p className="mt-1 text-xl font-bold tabular-nums">{valor}</p>
          <p className="mt-0.5 text-[11px] font-medium text-brand-teal">{detalle}</p>
        </div>)}
      </div>
      <div className="mt-2 grid gap-2 md:grid-cols-[2fr_1fr]">
        <div className="rounded-md border border-borde bg-superficie-2 p-3">
          <p className="text-xs font-semibold">Ingresos por hora</p>
          {/* Al pasar el mouse, la barra se destaca, las demás se atenúan y aparece
              su hora. Es decorativo (datos de ejemplo), por eso queda oculto al
              lector de pantalla. */}
          <div aria-hidden="true" className="group/barras mt-4 flex h-28 items-end gap-1.5 sm:h-32">
            {BARRAS.map((alto, i) => <div key={i} className="group/barra relative flex h-full flex-1 items-end transition-opacity duration-150 group-hover/barras:opacity-50 hover:opacity-100!">
              <span style={{ bottom: `calc(${alto}% + 6px)` }}
                className="pointer-events-none absolute left-1/2 -translate-x-1/2 whitespace-nowrap rounded-sm bg-texto px-1.5 py-0.5 text-micro font-medium tabular-nums text-fondo opacity-0 transition-opacity duration-150 group-hover/barra:opacity-100">{7 + i} h · {alto}</span>
              <div style={{ height: `${alto}%` }}
                className={`w-full origin-bottom rounded-t-sm transition-[scale] duration-150 group-hover/barra:scale-y-105 motion-reduce:transition-none motion-reduce:group-hover/barra:scale-y-100 ${PICO.includes(i) ? "bg-linear-to-t from-accent to-brand-teal" : "border border-brand-teal bg-brand-teal/10 group-hover/barra:bg-brand-teal/25"}`} />
            </div>)}
          </div>
        </div>
        <div className="rounded-md border border-borde bg-superficie-2 p-3 text-xs">
          <p className="font-semibold">Requiere atención</p>
          <ul className="mt-3 space-y-3">
            {ALERTAS.map(([titulo, detalle]) => <li key={titulo}><p className="font-semibold">{titulo}</p><p className="mt-0.5 text-texto-suave">{detalle}</p></li>)}
          </ul>
        </div>
      </div>
    </div>
  </figure>;
}

function GraficoBeneficio({ tipo }) {
  if (tipo === "fila") return <div aria-hidden="true" className="space-y-2 text-xs">
    {FILA.map(([estado, paciente, lugar], i) =>
      <div key={estado} className="presentacion-aparece flex flex-wrap items-center gap-x-3 gap-y-1 rounded-md border border-borde bg-superficie-2 px-3 py-2" style={{ "--paso": i }}>
        <span className={`rounded-pill px-2 py-0.5 font-semibold ${i ? "bg-badge-green-bg text-badge-green-fg" : "bg-badge-info-bg text-badge-info-fg"}`}>{estado}</span>
        <span className="font-semibold">{paciente}</span><span className="ml-auto text-texto-suave">{lugar}</span>
      </div>)}
  </div>;
  if (tipo === "triage") return <div aria-hidden="true" className="space-y-3">
    {TRIAGE.map(([nivel, cantidad, color], i) => <div key={nivel} className="grid grid-cols-[58px_1fr_12px] items-center gap-2 text-xs tabular-nums">
      <span>{nivel}</span><span className="h-2 overflow-hidden rounded-pill bg-superficie-2"><span className="presentacion-barra block h-full origin-left rounded-pill" style={{ width: `${cantidad / 6 * 100}%`, backgroundColor: color, "--paso": i }} /></span><span>{cantidad}</span>
    </div>)}
  </div>;
  if (tipo === "historia") return <div aria-hidden="true" className="space-y-2 text-xs">
    {HISTORIA.map(([clave, valor], i) => <div key={clave} className="presentacion-aparece flex justify-between gap-2 border-b border-borde pb-2" style={{ "--paso": i }}><span className="text-texto-suave">{clave}</span><strong className="text-right font-semibold">{valor}</strong></div>)}
  </div>;
  if (tipo === "camas") return <div aria-hidden="true">
    <div className="grid grid-cols-12 gap-1.5">{CAMAS.map((cama) => <span key={cama} className={`presentacion-cama aspect-square rounded-sm border ${cama < 19 ? "border-accent bg-accent" : "border-borde bg-superficie-2"}`} style={{ "--paso": cama }} />)}</div>
    <div className="mt-3 flex items-end justify-between gap-3"><div><strong className="text-xxl tabular-nums">79 %</strong><span className="ml-2 text-xs text-texto-suave">ocupación</span></div><span className="pb-1 text-xs text-texto-suave">19 de 24 camas</span></div>
  </div>;
  if (tipo === "laboratorio") return <div aria-hidden="true" className="flex h-24 items-end justify-center gap-4">
    {TUBOS.map((nivel, i) => <span key={i} className="relative h-full w-7 overflow-hidden rounded-b-pill border-2 border-borde bg-superficie-2"><span className="presentacion-tubo absolute origin-bottom inset-x-0 bottom-0 rounded-b-pill bg-linear-to-t from-accent to-brand-teal" style={{ height: `${nivel}%`, "--paso": i }} /></span>)}
  </div>;
  if (tipo === "stock") return <div aria-hidden="true" className="space-y-3 text-xs">
    {STOCK.map(([nombre, nivel, color], i) => <div key={nombre}><span className="font-medium">{nombre}</span><span className="mt-1 block h-2 overflow-hidden rounded-pill bg-superficie-2"><span className="presentacion-barra block h-full origin-left rounded-pill" style={{ width: `${nivel}%`, backgroundColor: color, "--paso": i }} /></span></div>)}
    <span className="inline-block rounded-sm border border-borde bg-superficie-2 px-2 py-0.5 text-texto-suave">Lote L-3-A</span>
  </div>;
  if (tipo === "cobertura") return <div aria-hidden="true" className="flex flex-wrap gap-2 text-xs font-semibold">
    <span className="presentacion-aparece rounded-pill bg-badge-green-bg px-3 py-1.5 text-badge-green-fg" style={{ "--paso": 0 }}>Cubierto 70 %</span><span className="presentacion-aparece rounded-pill bg-badge-amber-bg px-3 py-1.5 text-badge-amber-fg" style={{ "--paso": 1 }}>Copago</span>
  </div>;
  if (tipo === "circuito") return <div aria-hidden="true" className="flex flex-wrap items-center gap-1.5 text-xs">
    {CIRCUITO.map((paso, i) => <span key={paso} className="flex items-center gap-1.5"><span className="rounded-md border border-borde bg-superficie-2 px-2 py-1.5 font-medium">{paso}</span>{i < CIRCUITO.length - 1 && <span className="text-accent">→</span>}</span>)}
  </div>;
  if (tipo === "red") return <div aria-hidden="true" className="grid grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)_minmax(0,1fr)] items-center gap-2 text-xs">
    <span className="flex min-w-0 items-center gap-1 rounded-md border border-borde bg-superficie-2 px-2 py-2"><Icon name="building" size={14} /><span>Villa Real</span></span>
    <span className="flex min-w-0 flex-col items-center"><span className="rounded-pill bg-badge-green-bg px-2 py-0.5 text-center text-[10px] font-semibold text-badge-green-fg">Aceptada · En viaje</span><span className="mt-1 h-px w-full bg-brand-teal" /></span>
    <span className="flex min-w-0 items-center gap-1 rounded-md border border-borde bg-superficie-2 px-2 py-2"><Icon name="building" size={14} /><span>Central</span></span>
  </div>;
  if (tipo === "app") return <div aria-hidden="true" className="flex justify-end"><div className="w-32 rounded-[20px] border-[3px] border-texto bg-superficie-2 p-2 shadow-card"><div className="mx-auto mb-2 h-1 w-8 rounded-pill bg-texto-suave" /><div className="rounded-md bg-accent-fuerte p-2 text-[10px] text-sobre-accent"><span className="block">Próximo turno</span><strong className="mt-1 block text-xs">Jueves 10:30</strong></div><div className="mt-2 h-2 rounded-sm bg-borde" /><div className="mt-1.5 h-2 w-3/4 rounded-sm bg-borde" /></div></div>;
  return null;
}

export default function Presentacion() {
  const { oscuro, alternar } = useTema();
  const beneficiosRef = useRef(null);
  useEffect(() => {
    if (typeof IntersectionObserver === "undefined") return;
    const seccion = beneficiosRef.current;
    const observador = new IntersectionObserver(([entrada]) => {
      if (entrada.isIntersecting) { seccion.classList.add("es-visible"); observador.disconnect(); }
    }, { threshold: 0.2 });
    observador.observe(seccion);
    return () => observador.disconnect();
  }, []);
  const [h1, bajada, acciones] = [entrada(0), entrada(80), entrada(160)];
  return <div className="landing min-h-screen overflow-x-clip bg-fondo text-texto">
    <a href="#contenido" className={`sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-10 focus:rounded-md focus:bg-superficie focus:px-3 focus:py-2 focus:text-sm focus:shadow-float ${FOCO}`}>Saltar al contenido</a>
    <header className="border-b border-borde bg-superficie">
      <div className="mx-auto flex h-[70px] max-w-[1120px] items-center justify-between gap-3 px-5 sm:px-8">
        <Link to="/" aria-label="HEN, inicio" className={`rounded-md ${FOCO}`}><Marca /></Link>
        <nav aria-label="Navegación pública" className="flex items-center gap-3 text-xs sm:gap-5">
          <a href="#como-funciona" className={`text-texto-suave underline underline-offset-4 ${ENLACE_SUAVE}`}>Cómo funciona</a>
          <button type="button" onClick={alternar} aria-label={oscuro ? "Cambiar a tema claro" : "Cambiar a tema oscuro"} className={`flex size-9 items-center justify-center rounded-md border border-borde text-texto-suave transition-colors hover:border-accent hover:text-accent ${FOCO}`}><Icon name={oscuro ? "sol" : "luna"} size={16} /></button>
          <Link to="/login" className={`inline-flex h-9 items-center rounded-md border border-borde bg-superficie px-3 font-medium transition-colors hover:border-accent hover:text-accent ${FOCO}`}>Ingresar</Link>
        </nav>
      </div>
    </header>

    <main id="contenido" tabIndex={-1} className="presentacion-hero relative outline-none">
      <div className="relative mx-auto max-w-[1120px] px-5 pb-16 pt-16 sm:px-8 sm:pb-20 sm:pt-24">
        <div className="mx-auto max-w-[980px]">
        <h1 style={h1.style} className={`${h1.className} text-balance text-[clamp(2.5rem,7vw,4.5rem)] font-bold leading-[1.05] tracking-[-.045em]`}>Salud conectada.<br /><span className="presentacion-titulo-gradiente">Decisiones claras.</span></h1>
        <p style={bajada.style} className={`${bajada.className} mt-5 max-w-[660px] text-pretty text-base leading-relaxed text-texto-suave`}>La plataforma que une la atención, la historia clínica y la gestión de hospitales, centros de salud y financiadores.</p>
        <div style={acciones.style} className={`${acciones.className} mt-6 flex flex-wrap gap-2.5`}>
          <Link to="/login" className={CTA_PRINCIPAL}>Ingresar al sistema</Link>
          {DEMO_URL
            ? <a href={DEMO_URL} className={CTA_TERCIARIO}>Solicitar una demo</a>
            : <a href="#como-funciona" className={CTA_TERCIARIO}>Conocer HEN</a>}
        </div>
        </div>

        <VistaIlustrativa />

        <section aria-labelledby="cifras-titulo" className="mx-auto mt-16 max-w-[980px]">
          <h2 id="cifras-titulo" className="sr-only">HEN en números</h2>
          <ul className="grid grid-cols-2 gap-y-6 text-center lg:grid-cols-4">
            {/* Separadores alternados teal y violeta; el borde derecho cierra cada fila. */}
            {CIFRAS.map(([valor, rotulo], i) => <li key={rotulo} className={`border-l-2 px-2 ${i % 2 ? "border-l-accent border-r-2 border-r-brand-teal" : "border-l-brand-teal"} ${i === 1 ? "lg:border-r-0" : ""}`}>
              <strong className="block text-cifra-xl font-bold tabular-nums">{valor}</strong>
              <span className="text-xs text-texto-suave">{rotulo}</span>
            </li>)}
          </ul>
          <p className="mt-3 text-center text-xs text-texto-suave">Cifras de ejemplo para mostrar el diseño; no son datos reales de la red.</p>
        </section>

        <section id="como-funciona" ref={beneficiosRef} aria-labelledby="como-funciona-titulo" className="mx-auto mt-16 max-w-[980px] scroll-mt-8 sm:mt-20">
          <h2 id="como-funciona-titulo" className={TITULO_SECCION}>Todo lo que tu institución necesita, en un solo lugar</h2>
          <p className="mt-2 text-xs text-texto-suave">Ilustraciones con datos de ejemplo.</p>
          <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {BENEFICIOS.map(({ titulo, detalle, icono, destacado, ancho, alto, completaFila, enlaceApp, grafico }) => <article key={titulo}
              className={`flex min-w-0 flex-col rounded-lg border border-borde p-5 ${ancho ? "sm:col-span-2" : ""} ${alto ? "lg:row-span-2" : ""} ${completaFila ? "sm:col-span-2 lg:col-span-1" : ""} ${destacado ? "presentacion-beneficio" : "bg-superficie"}`}>
              <h3 className="flex items-center gap-2 text-xl font-bold tracking-tight"><Icon name={icono} size={18} className="shrink-0 text-brand-teal" />{titulo}</h3>
              <p className="mt-2 text-sm leading-relaxed text-texto-suave">{detalle}</p>
              <div className="mt-auto pt-6">{destacado && <Pulso className="mb-2 h-6 w-full text-brand-teal" />}
                {enlaceApp ? <div className="flex items-end justify-between gap-3"><Link to="/mi" className={`group inline-flex items-center gap-1 rounded-sm text-sm font-semibold text-accent hover:underline ${FOCO}`}>Ver la app<span aria-hidden="true" className="transition-transform duration-150 group-hover:translate-x-0.5 motion-reduce:transition-none">→</span></Link><GraficoBeneficio tipo={grafico} /></div> : <GraficoBeneficio tipo={grafico} />}
              </div>
            </article>)}
          </div>
        </section>
      </div>

      <section aria-labelledby="cierre-titulo" className="relative border-t border-borde px-5 py-16 text-center sm:py-20">
        <h2 id="cierre-titulo" className={TITULO_SECCION}>Llevá tu institución al siguiente nivel.</h2>
        <div className="mt-5 flex justify-center">
          {DEMO_URL
            ? <a href={DEMO_URL} className={CTA_PRINCIPAL}>Solicitar una demo</a>
            : <Link to="/login" className={CTA_PRINCIPAL}>Ingresar al sistema</Link>}
        </div>
      </section>
    </main>

    <footer className="border-t border-borde">
      <div className="mx-auto flex max-w-[1120px] flex-wrap items-center justify-between gap-4 px-5 py-8 sm:px-8">
        <Marca />
        {(LEGALES.length > 0 || SOPORTE_EMAIL) && <nav aria-label="Información legal y soporte">
          <ul className="flex flex-wrap gap-x-5 gap-y-2 text-xs text-texto-suave">
            {LEGALES.map(([nombre, url]) => <li key={nombre}><a href={url} className={ENLACE_SUAVE}>{nombre}</a></li>)}
            {SOPORTE_EMAIL && <li><a href={`mailto:${SOPORTE_EMAIL}`} className={ENLACE_SUAVE}>{SOPORTE_EMAIL}</a></li>}
          </ul>
        </nav>}
      </div>
    </footer>
  </div>;
}
