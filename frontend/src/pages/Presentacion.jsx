import { Link } from "react-router-dom";

import { Logo } from "@/components/Logo";
import { useTema } from "@/lib/tema";

const BARRAS = [18, 24, 31, 42, 55, 67, 74, 61, 50, 43, 36, 29];
const BENEFICIOS = [
  { titulo: "Atención sin filas", detalle: "Turnos, presencia y llamados al consultorio desde el recorrido del paciente.", destacado: true },
  { titulo: "Historia clínica firmada", detalle: "Alergias, estudios, recetas y registro de quién accedió." },
  { titulo: "Coberturas y cobros", detalle: "Convenios, copagos y saldos según la atención registrada." },
  { titulo: "App para pacientes", detalle: "Turnos y resultados desde el celular, con la marca de cada institución.", ruta: "/demo/app-clinica" },
];

function Marca() {
  return <span className="inline-flex items-center gap-2 text-sm font-bold"><Logo size={24} /> HEN</span>;
}

function Pulso() {
  return <svg aria-hidden="true" viewBox="0 0 1000 58" preserveAspectRatio="none" className="presentacion-pulso pointer-events-none absolute inset-x-0 top-[60%] w-full text-accent"><path d="M0 30H92l16-22 16 49 17-57 16 42 11-12H1000" fill="none" stroke="currentColor" strokeWidth="1.2" vectorEffect="non-scaling-stroke" /></svg>;
}

export default function Presentacion() {
  const { oscuro, alternar } = useTema();
  return <div className="min-h-screen bg-fondo text-texto">
    <header className="mx-auto flex h-[70px] max-w-[1280px] items-center justify-between px-5 sm:px-8">
      <Link to="/presentacion" aria-label="HEN, inicio"><Marca /></Link>
      <nav aria-label="Navegación pública" className="flex items-center gap-4 text-xs sm:gap-6">
        <a href="#como-funciona" className="text-texto-suave hover:text-accent">Cómo funciona</a>
        <button type="button" onClick={alternar} aria-label={oscuro ? "Cambiar a tema claro" : "Cambiar a tema oscuro"} className="rounded-md border border-borde px-2.5 py-2 text-texto-suave hover:text-accent">{oscuro ? "☀" : "☾"}</button>
        <Link to="/login" className="rounded-md border border-borde bg-superficie px-3 py-2 font-medium hover:border-accent">Ingresar</Link>
      </nav>
    </header>

    <main className="presentacion-hero relative overflow-hidden border-t border-borde">
      <Pulso />
      <div className="relative mx-auto max-w-[1120px] px-5 pb-20 pt-20 sm:px-8 sm:pt-24">
        <div className="max-w-[800px]">
          <h1 className="text-[clamp(2.5rem,6vw,5rem)] font-bold leading-[1.05] tracking-[-.045em]">Salud conectada.<br /><span className="presentacion-titulo-gradiente">Decisiones claras.</span></h1>
          <p className="mt-5 max-w-[660px] text-base leading-relaxed text-texto-suave">La plataforma que une la atención, la historia clínica y la gestión de hospitales, centros de salud y financiadores.</p>
          <div className="mt-6 flex flex-wrap gap-2.5">
            <Link to="/login" className="hen-cta rounded-md px-5 py-3 text-sm font-semibold text-sobre-accent">Ingresar al sistema</Link>
            <a href="#como-funciona" className="rounded-md border border-borde bg-superficie px-5 py-3 text-sm font-semibold hover:border-accent">Conocer HEN</a>
          </div>
        </div>

        <section aria-label="Ejemplo visual del tablero" className="relative mx-auto mt-20 max-w-[800px] rounded-lg border border-borde bg-superficie p-4 shadow-float sm:p-6">
          <div className="mb-4 flex items-center justify-between text-xs text-texto-tenue"><span>● ● ●</span><span>Vista ilustrativa · datos de ejemplo</span></div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {[["Pacientes atendidos", "128"], ["Espera promedio", "18 min"], ["Ocupación", "71 %"], ["Cobrado del mes", "66 %"]].map(([titulo, valor]) =>
              <div key={titulo} className="rounded-md border border-borde bg-superficie-2 p-3"><p className="text-[11px] text-texto-suave">{titulo}</p><strong className="mt-1 block text-xl">{valor}</strong></div>)}
          </div>
          <div className="mt-2 grid gap-2 sm:grid-cols-[2fr_1fr]">
            <div className="rounded-md border border-borde bg-superficie-2 p-3"><h2 className="text-xs font-semibold">Ingresos por hora</h2><div className="mt-4 flex h-24 items-end gap-1.5">{BARRAS.map((alto, i) => <div key={i} style={{ height: `${alto}%` }} className={`flex-1 rounded-t-sm ${i === 5 || i === 6 ? "hen-cta" : "border border-accent bg-accent-50"}`} />)}</div></div>
            <div className="rounded-md border border-borde bg-superficie-2 p-3 text-xs"><h2 className="font-semibold">Requiere atención</h2><p className="mt-3 font-medium">Guardia sobre el objetivo</p><p className="mt-1 text-texto-suave">38 min · 12 en fila</p><p className="mt-3 font-medium">6 derivaciones sin respuesta</p><p className="mt-1 text-texto-suave">Hace más de 24 h</p></div>
          </div>
        </section>

        <div className="mx-auto mt-16 grid max-w-[850px] grid-cols-2 gap-6 text-center sm:grid-cols-4" aria-label="Cifras ilustrativas">
          {[["26", "instituciones en la red"], ["1.284", "profesionales activos"], ["18.402", "pacientes por semana"], ["9", "financiadores con convenio"]].map(([valor, rotulo]) => <div key={rotulo} className="border-l-2 border-accent px-2"><strong className="block text-xxl">{valor}</strong><span className="text-xs text-texto-suave">{rotulo}</span></div>)}
        </div>
        <p className="mt-3 text-center text-xs text-texto-tenue">Cifras de ejemplo para mostrar el diseño.</p>

        <section id="como-funciona" className="mx-auto mt-20 max-w-[850px] scroll-mt-8">
          <h2 className="text-xxl font-bold tracking-tight">Todo lo que tu institución necesita, en un solo lugar</h2>
          <div className="mt-5 grid gap-3 sm:grid-cols-2">
            {BENEFICIOS.map(({ titulo, detalle, destacado, ruta }) => <div key={titulo} className={`rounded-lg border border-borde p-5 ${destacado ? "presentacion-beneficio" : "bg-superficie"}`}>
              <h3 className="text-base font-bold">{titulo}</h3><p className="mt-2 text-sm leading-relaxed text-texto-suave">{detalle}</p>
              {ruta && <Link to={ruta} className="mt-4 inline-block text-sm font-semibold text-accent hover:underline">Ver maqueta de la app clínica →</Link>}
            </div>)}
          </div>
        </section>
      </div>
      <section className="relative border-t border-borde bg-superficie-2 px-5 py-16 text-center sm:py-20">
        <h2 className="text-xxl font-bold tracking-tight">Llevá tu institución al siguiente nivel.</h2>
        <p className="mx-auto mt-3 max-w-[580px] text-sm text-texto-suave">Conocé cómo se vería el recorrido de una persona desde su celular.</p>
        <Link to="/demo/app-clinica" className="hen-cta mt-6 inline-flex rounded-md px-5 py-3 text-sm font-semibold text-sobre-accent">Ver app clínica de ejemplo</Link>
      </section>
    </main>
    <footer className="border-t border-borde bg-superficie-2"><div className="mx-auto flex max-w-[1120px] flex-wrap items-center justify-between gap-4 px-5 py-8 sm:px-8"><Marca /><p className="text-xs text-texto-suave">HEN · Presentación de diseño</p></div></footer>
  </div>;
}
