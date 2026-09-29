import { useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "@/auth/AuthContext";
import { Logo } from "@/components/Logo";

const SOPORTE_EMAIL = import.meta.env.VITE_SOPORTE_EMAIL?.trim();
const SOPORTE_URL = import.meta.env.VITE_SOPORTE_URL?.trim();
const minutosConfigurados = Number(import.meta.env.VITE_IDLE_LOCK_MINUTES);
const MINUTOS_INACTIVIDAD = Number.isFinite(minutosConfigurados) && minutosConfigurados >= 3 ? minutosConfigurados : 15;

/**
 * A dónde ir después de autenticar.
 *
 * Si se llegó desde un enlace a una pantalla protegida, se vuelve ahí; si no, a
 * la entrada que resuelve directorio o institución. Nunca a la landing pública
 * ni al propio login, y solo rutas internas.
 */
function destinoTrasIngreso(desde) {
  const interna = typeof desde === "string" && desde.startsWith("/") && !desde.startsWith("//");
  const publica = interna && ["/", "/login", "/presentacion"].includes(desde.split(/[?#]/)[0]);
  return interna && !publica ? desde : "/directorio";
}

export default function Login() {
  const { login, user } = useAuth();
  const navigate = useNavigate();
  const destino = destinoTrasIngreso(useLocation().state?.desde);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [verPass, setVerPass] = useState(false);
  const [recordar, setRecordar] = useState(false);
  const [ayudaAbierta, setAyudaAbierta] = useState(false);
  const [error, setError] = useState("");
  const [cargando, setCargando] = useState(false);

  // Con la sesión ya abierta el formulario no tiene nada que hacer.
  if (user && !cargando) return <Navigate to={destino} replace />;

  async function onSubmit(e) {
    e.preventDefault();
    setError("");
    setCargando(true);
    try {
      await login(email, password, { recordar });
      navigate(destino, { replace: true });
    } catch (err) {
      setError(err.status === 401
        ? "Email o contraseña incorrectos."
        : "No se pudo iniciar sesión. Reintentá en unos segundos.");
    } finally {
      setCargando(false);
    }
  }

  return (
    <div className="login-page flex min-h-screen flex-col bg-fondo text-texto">
      <header className="relative z-10 flex h-[46px] items-center justify-between border-b border-borde bg-superficie px-5 sm:px-[max(24px,9.6vw)]">
        <span className="flex items-center gap-2 text-md font-bold"><Logo size={24} /> HEN</span>
        <Link to="/" className="text-sm text-texto-suave hover:text-accent">Volver al inicio</Link>
      </header>

      <main className="login-main relative flex flex-1 items-center justify-center overflow-hidden px-5 py-12 sm:px-8">
        <svg className="login-pulso pointer-events-none absolute inset-x-0 top-1/2 h-[64px] w-full -translate-y-1/2" viewBox="0 0 1045 64" preserveAspectRatio="none" fill="none" aria-hidden="true">
          <path d="M0 32 H75 L86 9 L99 57 L111 0 L122 42 L132 32 H1045" stroke="currentColor" strokeWidth="1.3" vectorEffect="non-scaling-stroke" />
        </svg>

        <section className="relative z-[1] w-full max-w-[350px] rounded-[15px] border border-borde bg-superficie p-[29px] shadow-card sm:p-[30px]" aria-labelledby="login-titulo">
          <h1 id="login-titulo" className="text-xl font-bold tracking-tight">Iniciá sesión</h1>
          <p className="mt-1 text-xs text-texto-suave">Usá el email y la contraseña de tu institución.</p>

          <form onSubmit={onSubmit} className="mt-[10px] space-y-3">
            <label className="block text-xs font-medium">
              Email <span className="text-accent">*</span>
              <input className={CLASE_INPUT} type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="nombre@institucion.gob.ar" autoComplete="username" required />
            </label>
            <label className="block text-xs font-medium">
              Contraseña <span className="text-accent">*</span>
              <span className="relative mt-1 block">
                <input className={`${CLASE_INPUT} mt-0 pr-9`} type={verPass ? "text" : "password"} value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />
                <button type="button" onClick={() => setVerPass((v) => !v)} aria-label={verPass ? "Ocultar contraseña" : "Mostrar contraseña"} aria-pressed={verPass} className="absolute right-0 top-0 flex size-9 items-center justify-center rounded-md text-texto-debil hover:text-accent focus-visible:outline-2 focus-visible:outline-accent">
                  {verPass ? <OjoTachado /> : <Ojo />}
                </button>
              </span>
            </label>

            <div className="flex flex-wrap items-center justify-between gap-x-2 gap-y-1 text-[10px]">
              <label className="flex cursor-pointer items-center gap-1.5 whitespace-nowrap">
                <input type="checkbox" checked={recordar} onChange={(e) => setRecordar(e.target.checked)} className="size-3.5 accent-accent" />
                Mantener la sesión iniciada
              </label>
              <a href="#ayuda-acceso" onClick={() => setAyudaAbierta(true)} className="text-accent hover:underline">¿Olvidaste tu contraseña?</a>
            </div>
            <p className="text-[10px] leading-relaxed text-texto-suave">No la actives en equipos compartidos. Si no hay actividad durante {MINUTOS_INACTIVIDAD} minutos, la sesión se bloquea.</p>

            {error && <div role="alert" className="rounded-md border border-badge-error-fg/25 bg-badge-error-bg px-3 py-2 text-sm text-badge-error-fg">{error}</div>}

            <button type="submit" disabled={cargando} className="hen-cta flex h-[36px] w-full items-center justify-center rounded-md text-sm font-medium text-sobre-accent disabled:cursor-not-allowed disabled:opacity-60">
              {cargando ? "Ingresando…" : "Ingresar"}
            </button>
          </form>

          <div id="ayuda-acceso" className="mt-3 border-t border-division pt-4 text-[10px] leading-relaxed text-texto-suave">
            <details open={ayudaAbierta} onToggle={(e) => setAyudaAbierta(e.currentTarget.open)}>
              <summary className="cursor-pointer text-accent focus-visible:outline-2 focus-visible:outline-accent">¿Problemas para ingresar?</summary>
              <p className="mt-2">Pedí asistencia a la administración de tu institución. Para recuperar el acceso, verificá tu identidad por un canal seguro. Nunca envíes tu contraseña ni datos clínicos.</p>
              {SOPORTE_EMAIL && <p className="mt-2"><a href={`mailto:${SOPORTE_EMAIL}`} className="text-accent underline">Escribí a {SOPORTE_EMAIL}</a></p>}
              {SOPORTE_URL?.startsWith("https://") && <p className="mt-2"><a href={SOPORTE_URL} className="text-accent underline">Abrir soporte</a></p>}
            </details>
          </div>
        </section>
      </main>
    </div>
  );
}

const CLASE_INPUT = "mt-1 block h-[30px] w-full rounded-md border border-campo-borde bg-superficie-2 px-2 text-xs text-texto outline-none placeholder:text-texto-tenue focus:border-accent focus-visible:ring-2 focus-visible:ring-accent";

function Ojo() {
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z" /><circle cx="12" cy="12" r="3" /></svg>;
}
function OjoTachado() {
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M9.9 4.24A9.1 9.1 0 0 1 12 4c6.5 0 10 8 10 8a18 18 0 0 1-2.16 3.19M6.6 6.6A18 18 0 0 0 2 12s3.5 7 10 7a9 9 0 0 0 5.4-1.6" /><path d="M14.12 14.12a3 3 0 1 1-4.24-4.24M2 2l20 20" /></svg>;
}
