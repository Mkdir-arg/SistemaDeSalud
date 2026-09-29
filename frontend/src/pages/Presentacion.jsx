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
const BENEFICIOS = [
  { titulo: "Atención sin filas", detalle: "Turnos, presente a 500 m, fila ordenada y llamado al consultorio. El paciente espera donde quiere.", destacado: true, ancho: true },
  { titulo: "Historia clínica firmada", detalle: "Alergias, estudios, recetas y registro de quién accedió.", arriba: true },
  { titulo: "Coberturas y cobros", detalle: "Cupos, copagos y saldos calculados según cada convenio." },
  { titulo: "App para pacientes", detalle: "Turnos, resultados y pagos desde el celular, con la marca de tu institución.", ancho: true, maqueta: true },
];

const FOCO = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent";
const CTA_PRINCIPAL = `hen-cta inline-flex h-10 items-center rounded-md px-4.5 text-sm font-medium text-sobre-accent ${FOCO}`;
const CTA_TERCIARIO = `inline-flex h-10 items-center rounded-md border border-borde bg-superficie px-4.5 text-sm font-medium text-texto transition-colors hover:border-accent hover:text-accent ${FOCO}`;
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

export default function Presentacion() {
  const { oscuro, alternar } = useTema();
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

        <section id="como-funciona" aria-labelledby="como-funciona-titulo" className="mx-auto mt-16 max-w-[980px] scroll-mt-8 sm:mt-20">
          <h2 id="como-funciona-titulo" className="text-balance text-xxl font-bold tracking-tight">Todo lo que tu institución necesita, en un solo lugar</h2>
          <div className="mt-5 grid gap-3 md:grid-cols-5">
            {BENEFICIOS.map(({ titulo, detalle, destacado, ancho, arriba, maqueta }) => <article key={titulo}
              className={`rounded-lg border border-borde p-5 ${ancho ? "md:col-span-3" : "md:col-span-2"} ${destacado ? "presentacion-beneficio" : "bg-superficie"} ${arriba ? "md:self-start" : ""}`}>
              <h3 className="text-base font-bold">{titulo}</h3>
              <p className="mt-2 text-sm leading-relaxed text-texto-suave">{detalle}</p>
              {destacado && <Pulso className="mt-4 h-[40px] w-full max-w-[320px] text-brand-teal" />}
              {maqueta && <Link to="/demo/app-clinica" className={`group mt-4 inline-flex items-center gap-1 rounded-sm text-sm font-semibold text-accent hover:underline ${FOCO}`}>Ver app clínica<span aria-hidden="true" className="transition-transform duration-150 group-hover:translate-x-0.5 motion-reduce:transition-none">→</span></Link>}
            </article>)}
          </div>
        </section>
      </div>

      <section aria-labelledby="cierre-titulo" className="relative border-t border-borde px-5 py-16 text-center sm:py-20">
        <h2 id="cierre-titulo" className="text-balance text-xxl font-bold tracking-tight">Llevá tu institución al siguiente nivel.</h2>
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
