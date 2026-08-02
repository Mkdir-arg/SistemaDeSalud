import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { useAuth } from "@/auth/AuthContext";
import { Icon } from "@/components/icons";
import { LogoFull } from "@/components/Logo";

/**
 * Login de Cauce. Pantalla partida: panel de marca + formulario.
 *
 * El panel de marca NO sigue el tema: es una superficie de identidad, con su
 * degradado propio y texto blanco encima. El lado del formulario sí, porque ya
 * es la aplicación.
 *
 * Sobre los blancos atenuados: los textos secundarios estaban en `rgba(255,255,255,.62)`,
 * que sobre el índigo del degradado da 3.84:1 y no llega al mínimo de AA. A 85%
 * dan 5.76:1. Es la primera pantalla que ve cualquiera y muchas veces se mira en
 * un monitor viejo de admisión: acá el contraste no es un detalle.
 */

const PUNTOS = [
  { icon: "activity", titulo: "Trazabilidad clínica", desc: "Cada caso, del ingreso al alta, con historial auditable." },
  { icon: "workflow", titulo: "Flujos configurables", desc: "Diseñá el circuito de atención sin escribir código." },
  { icon: "idCard", titulo: "Acceso seguro por rol", desc: "Cada profesional ve solo lo que le corresponde." },
];

const AÑO = new Date().getFullYear();

// Degradado de marca: valores concretos y decorativos, no tokens del sistema.
const FONDO_MARCA = {
  backgroundImage: [
    "radial-gradient(120% 120% at 85% 10%, #0E8893 0%, rgba(14,136,147,0) 42%)",
    "linear-gradient(155deg, #2C3AA8 0%, #3949C0 55%, #2330A0 100%)",
  ].join(","),
};

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [verPass, setVerPass] = useState(false);
  const [recordar, setRecordar] = useState(true);
  const [error, setError] = useState("");
  const [cargando, setCargando] = useState(false);

  async function onSubmit(e) {
    e.preventDefault();
    setError("");
    setCargando(true);
    try {
      // `recordar` decide si el token sobrevive al cierre del navegador. En un
      // equipo compartido de guardia eso importa de verdad.
      await login(email, password, { recordar });
      navigate("/");
    } catch (err) {
      setError(
        err.status === 401
          ? "Email o contraseña incorrectos."
          : "No se pudo iniciar sesión. Reintentá en unos segundos.",
      );
    } finally {
      setCargando(false);
    }
  }

  return (
    <div className="flex min-h-screen bg-fondo">
      {/* Panel de marca: se oculta cuando no hay ancho para él. */}
      <aside
        className="relative hidden flex-[1.05] overflow-hidden text-white lg:block"
        style={FONDO_MARCA}
      >
        <MotivoNodos />

        <div className="relative z-10 flex h-full flex-col p-12 xl:px-[52px]">
          <div className="flex items-center gap-3">
            <LogoFull size={42} light descriptor="Salud" />
          </div>

          <div className="my-auto">
            <div className="inline-flex items-center gap-2.5 rounded-pill border border-white/20 bg-white/15 px-3.5 py-1.5 text-sm font-semibold text-white">
              <span className="size-1.5 rounded-full bg-[#5EE6C4] ring-4 ring-[#5EE6C4]/25" />
              Plataforma de gestión asistencial
            </div>

            <h1 className="mb-8 mt-5 text-[2rem] font-extrabold leading-tight tracking-tight text-white">
              El recorrido de cada paciente,
              <br />
              ordenado de principio a fin.
            </h1>

            <ul className="flex max-w-[26rem] flex-col gap-5">
              {PUNTOS.map((p) => (
                <li key={p.titulo} className="flex items-start gap-3.5">
                  <span className="flex size-10 flex-none items-center justify-center rounded-lg border border-white/20 bg-white/15 text-white">
                    <Icon name={p.icon} size={18} />
                  </span>
                  <div>
                    <div className="text-md font-bold text-white">{p.titulo}</div>
                    <div className="mt-0.5 text-sm leading-snug text-white/85">{p.desc}</div>
                  </div>
                </li>
              ))}
            </ul>
          </div>

          {/* Pulso clínico: el hairline que liga la marca con salud. */}
          <svg
            className="my-lg h-6 w-full flex-none text-[#5EE6C4] opacity-50"
            viewBox="0 0 1200 24"
            fill="none"
            preserveAspectRatio="none"
            aria-hidden="true"
          >
            <path
              d="M0 12 H470 l14 -8 l12 16 l12 -20 l11 24 l10 -12 H700 l16 -6 l9 6 H1200"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>

          <div className="flex items-center justify-between text-sm text-white/80">
            <span>© {AÑO} I-Core · Sistema de gestión asistencial</span>
            <span className="inline-flex items-center gap-1.5">
              <IconoEscudo /> Conexión cifrada
            </span>
          </div>
        </div>
      </aside>

      {/* Formulario */}
      <main className="flex flex-1 items-center justify-center p-6 sm:p-8">
        <div className="w-full max-w-[24.75rem] animate-[fadeUp_.5s_ease_both]">
          {/* Marca compacta para cuando el panel no entra. */}
          <div className="mb-6 flex flex-col items-center text-center lg:hidden">
            <LogoFull size={44} descriptor="Salud" />
          </div>

          <div className="mb-6">
            <h2 className="font-display text-cifra font-extrabold tracking-tight">Iniciá sesión</h2>
            <p className="mt-1.5 text-md text-texto-debil">
              Ingresá con tu cuenta institucional para continuar.
            </p>
          </div>

          <form onSubmit={onSubmit} className="flex flex-col gap-lg">
            <Campo label="Email">
              <ConIcono icono="idCard">
                <input
                  className={CLASE_INPUT}
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="nombre@institucion.gob"
                  autoComplete="username"
                  autoFocus
                  required
                />
              </ConIcono>
            </Campo>

            <Campo label="Contraseña">
              <ConIcono icono="lock">
                <input
                  className={`${CLASE_INPUT} pr-11`}
                  type={verPass ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  autoComplete="current-password"
                  required
                />
                <button
                  type="button"
                  onClick={() => setVerPass((v) => !v)}
                  title={verPass ? "Ocultar contraseña" : "Mostrar contraseña"}
                  aria-label={verPass ? "Ocultar contraseña" : "Mostrar contraseña"}
                  className="absolute right-2 flex size-8 items-center justify-center rounded-md text-texto-debil hover:bg-division hover:text-texto-medio"
                >
                  {verPass ? <OjoTachado /> : <Ojo />}
                </button>
              </ConIcono>
            </Campo>

            <label className="flex cursor-pointer select-none items-center gap-2.5 text-base text-texto-medio">
              <input
                type="checkbox"
                checked={recordar}
                onChange={(e) => setRecordar(e.target.checked)}
                className="size-4 cursor-pointer"
              />
              <span>Mantener la sesión iniciada en este equipo</span>
            </label>

            {error && (
              <div
                role="alert"
                className="flex items-start gap-2.5 rounded-lg border border-badge-error-fg/25 bg-badge-error-bg px-3.5 py-2.5 text-base leading-snug text-badge-error-fg"
              >
                <Icon name="alert" size={15} className="mt-px flex-none" />
                <span>{error}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={cargando}
              className="mt-0.5 flex h-12 w-full items-center justify-center gap-2.5 rounded-lg bg-accent-fuerte text-lg font-bold text-sobre-accent shadow-float transition hover:brightness-110 active:translate-y-px disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:brightness-100"
            >
              {cargando ? "Ingresando…" : "Ingresar"}
              {!cargando && <Icon name="enter" size={16} />}
            </button>
          </form>

          <div className="mt-6 flex items-center gap-2 border-t border-division pt-5 text-sm text-texto-debil">
            <Icon name="help" size={14} className="flex-none" />
            <span>¿No tenés acceso? Solicitalo a la administración de tu institución.</span>
          </div>
        </div>
      </main>
    </div>
  );
}

const CLASE_INPUT =
  "h-12 w-full rounded-lg border border-campo-borde bg-superficie-2 pl-11 pr-3.5 text-md text-texto " +
  "outline-none transition placeholder:text-texto-tenue focus:border-accent focus:bg-superficie";

function Campo({ label, children }) {
  return (
    <label className="block">
      <div className="mb-1.5 text-base font-semibold text-texto-suave">{label}</div>
      {children}
    </label>
  );
}

function ConIcono({ icono, children }) {
  return (
    <div className="relative flex items-center">
      <span className="pointer-events-none absolute left-3.5 flex text-texto-debil">
        {icono === "lock" ? <Candado /> : <Icon name={icono} size={17} />}
      </span>
      {children}
    </div>
  );
}

/** Motivo de fondo: el isotipo en grande y difuso (grafo de nodos conectados). */
function MotivoNodos() {
  return (
    <svg
      className="pointer-events-none absolute -right-14 top-1/2 size-[35rem] -translate-y-1/2"
      viewBox="0 0 600 600"
      fill="none"
      aria-hidden="true"
    >
      <g stroke="#fff" strokeWidth="1.4" opacity=".5">
        <path d="M120 150 L300 90 M120 150 L260 280 M300 90 L470 160 M260 280 L470 160 M260 280 L210 440 M470 160 L500 360 M210 440 L420 470 M500 360 L420 470" />
      </g>
      {[[120, 150], [300, 90], [470, 160], [260, 280], [500, 360], [210, 440], [420, 470]].map(([x, y], i) => (
        <circle key={i} cx={x} cy={y} r={i % 3 === 0 ? 9 : 6} fill="#fff" opacity={i % 2 ? ".7" : ".95"} />
      ))}
    </svg>
  );
}

/* Íconos que no están en el set base. */
function Candado() {
  return (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3.5" y="11" width="17" height="10" rx="2" /><path d="M7.5 11V7.5a4.5 4.5 0 0 1 9 0V11" /><circle cx="12" cy="16" r="1.3" fill="currentColor" stroke="none" />
    </svg>
  );
}
function Ojo() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z" /><circle cx="12" cy="12" r="3" />
    </svg>
  );
}
function OjoTachado() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9.9 4.24A9.1 9.1 0 0 1 12 4c6.5 0 10 8 10 8a18 18 0 0 1-2.16 3.19M6.6 6.6A18 18 0 0 0 2 12s3.5 7 10 7a9 9 0 0 0 5.4-1.6" /><path d="M14.12 14.12a3 3 0 1 1-4.24-4.24M2 2l20 20" />
    </svg>
  );
}
function IconoEscudo() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2 4 5v6c0 5 3.5 8.5 8 11 4.5-2.5 8-6 8-11V5z" /><path d="m9 12 2 2 4-4" />
    </svg>
  );
}
