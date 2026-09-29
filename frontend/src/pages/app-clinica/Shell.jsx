import { Link, NavLink, Navigate, Outlet } from "react-router-dom";

import { Icon } from "@/components/icons";

import { useApp } from "./estado";
import { Avatar, MarcaClinica, primerNombre, ruta } from "./ui";

const SECCIONES = [
  { a: "inicio", texto: "Inicio", icono: "home" },
  { a: "turnos", texto: "Turnos", icono: "calendar" },
  { a: "resultados", texto: "Resultados", icono: "flask" },
  { a: "clinica", texto: "La clínica", icono: "building" },
];

function Encabezado({ enfoque }) {
  const { paciente, resultados } = useApp();
  const nuevos = resultados.filter((r) => r.nuevo && r.estado === "listo").length;
  return <header className={`sticky top-0 z-20 border-b border-borde bg-superficie/95 backdrop-blur ${enfoque ? "hidden md:block" : ""}`}>
    <div className="mx-auto flex h-16 max-w-5xl items-center gap-6 px-4">
      <Link to={ruta("inicio")} className="flex items-center gap-2.5 rounded-md font-bold focus-visible:outline-2 focus-visible:outline-accent">
        <MarcaClinica size={34} /><span className="text-sm">Clínica Modelo</span>
      </Link>
      <nav aria-label="Secciones" className="hidden flex-1 items-center gap-1 md:flex">
        {SECCIONES.map((s) => <NavLink key={s.a} to={ruta(s.a)} className={({ isActive }) => `relative rounded-md px-3 py-2 text-sm font-medium ${isActive ? "bg-accent-50 text-accent" : "text-texto-medio hover:bg-accent-50"}`}>
          {s.texto}{s.a === "resultados" && nuevos > 0 && <span className="ml-1.5 rounded-pill bg-accent-fuerte px-1.5 text-micro font-bold text-white">{nuevos}</span>}
        </NavLink>)}
      </nav>
      <Link to={ruta("perfil")} aria-label="Mi perfil" className="ml-auto flex items-center gap-2 rounded-pill py-1 pl-1 pr-1 text-sm font-medium hover:bg-accent-50 md:pr-3 focus-visible:outline-2 focus-visible:outline-accent">
        <Avatar nombre={paciente.nombre} size={32} /><span className="hidden md:inline">{primerNombre(paciente.nombre)}</span>
      </Link>
    </div>
  </header>;
}

function Pestanas() {
  const { resultados } = useApp();
  const nuevos = resultados.some((r) => r.nuevo && r.estado === "listo");
  return <nav aria-label="Secciones" className="fixed inset-x-0 bottom-0 z-20 border-t border-borde bg-superficie pb-[env(safe-area-inset-bottom)] md:hidden">
    <div className="mx-auto grid max-w-xl grid-cols-4">
      {SECCIONES.map((s) => <NavLink key={s.a} to={ruta(s.a)} className={({ isActive }) => `relative flex h-16 flex-col items-center justify-center gap-1 text-micro font-semibold ${isActive ? "text-accent" : "text-texto-suave"}`}>
        <span className="relative"><Icon name={s.icono} size={22} />{s.a === "resultados" && nuevos && <span aria-label="Hay resultados nuevos" className="absolute -right-1 -top-0.5 size-2.5 rounded-full border-2 border-superficie bg-accent-fuerte" />}</span>
        {s.texto}
      </NavLink>)}
    </div>
  </nav>;
}

export function Aviso() {
  const { aviso } = useApp();
  return <div aria-live="polite" className="pointer-events-none fixed inset-x-0 bottom-20 z-30 flex justify-center px-4 md:bottom-8">
    {aviso && <p key={aviso.id} role="status" className="max-w-sm rounded-md bg-texto px-4 py-3 text-sm text-white shadow-float">{aviso.texto}</p>}
  </div>;
}

/**
 * Marco de las pantallas con sesión. Las secciones principales llevan
 * encabezado y pestañas; los recorridos (`enfoque`) ocupan la pantalla del
 * celular con su propio "atrás", como en una app nativa.
 */
export function Marco({ enfoque = false }) {
  const { paciente } = useApp();
  if (!paciente) return <Navigate to={ruta()} replace />;
  return <div className="flex min-h-dvh flex-col bg-fondo text-texto">
    <Encabezado enfoque={enfoque} />
    <main className={`mx-auto flex w-full max-w-xl flex-1 flex-col px-4 pt-5 md:pb-12 md:pt-8 ${enfoque ? "pb-6" : "pb-24"}`}>
      <Outlet />
    </main>
    <footer className="hidden border-t border-borde py-5 text-center text-xs text-texto-suave md:block">
      Clínica Modelo · Demo de HEN con datos ficticios · <Link to="/presentacion" className="font-medium text-accent hover:underline">Conocé HEN</Link>
    </footer>
    {!enfoque && <Pestanas />}
    <Aviso />
  </div>;
}
