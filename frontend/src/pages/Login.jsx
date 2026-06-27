import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { LogoFull } from "../components/Logo";
import { Icon } from "../components/icons";
import { useAuth } from "../auth/AuthContext";
import { color, font } from "../theme";

// Login de Cauce. Split-screen: panel de marca (motivo de flujo/pulso clínico)
// + formulario tradicional. Innovador en lo visual, convencional en el uso.

const TEAL = "#0E8893"; // acento "salud" del sistema de diseño

// Puntos de confianza del panel de marca.
const PUNTOS = [
  { icon: "activity", titulo: "Trazabilidad clínica", desc: "Cada caso, del ingreso al alta, con historial auditable." },
  { icon: "workflow", titulo: "Flujos configurables", desc: "Diseñá el circuito de atención sin escribir código." },
  { icon: "idCard", titulo: "Acceso seguro por rol", desc: "Cada profesional ve solo lo que le corresponde." },
];

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("admin@cauce.local");
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
      await login(email, password);
      navigate("/");
    } catch (err) {
      setError(err.status === 401 ? "Email o contraseña incorrectos." : "No se pudo iniciar sesión. Reintentá en unos segundos.");
    } finally {
      setCargando(false);
    }
  }

  return (
    <div className="lg-root">
      <style>{CSS}</style>

      {/* ── Panel de marca (oculto en pantallas chicas) ── */}
      <aside className="lg-brand">
        <NodeMotif />
        <div className="lg-brand-inner">
          <div className="lg-brand-top">
            <LogoFull size={42} light descriptor="Salud" />
          </div>

          <div className="lg-brand-mid">
            <div className="lg-pill">
              <span style={{ width: 7, height: 7, borderRadius: "50%", background: "#5EE6C4", boxShadow: "0 0 0 3px rgba(94,230,196,.25)" }} />
              Plataforma de gestión asistencial
            </div>
            <h1 className="lg-headline">
              El recorrido de cada paciente,<br />ordenado de principio a fin.
            </h1>
            <div className="lg-points">
              {PUNTOS.map((p) => (
                <div key={p.titulo} className="lg-point">
                  <div className="lg-point-ic"><Icon name={p.icon} size={18} /></div>
                  <div>
                    <div style={{ fontSize: 14, fontWeight: 700, color: "#fff" }}>{p.titulo}</div>
                    <div style={{ fontSize: 12.8, color: "rgba(255,255,255,.62)", marginTop: 2, lineHeight: 1.45 }}>{p.desc}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Pulso clínico: hairline que vincula la marca con salud (motivo del sistema de marca) */}
          <svg className="lg-brand-pulse" viewBox="0 0 1200 24" fill="none" preserveAspectRatio="none" aria-hidden="true">
            <path d="M0 12 H470 l14 -8 l12 16 l12 -20 l11 24 l10 -12 H700 l16 -6 l9 6 H1200" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>

          <div className="lg-brand-foot">
            <span>© {AÑO} I-Core · Sistema de gestión asistencial</span>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              <ShieldDot /> Conexión cifrada
            </span>
          </div>
        </div>
      </aside>

      {/* ── Panel del formulario ── */}
      <main className="lg-form-side">
        <div className="lg-card lg-fade">
          {/* Marca compacta para mobile (cuando el panel se oculta) */}
          <div className="lg-mobile-brand">
            <LogoFull size={44} descriptor="Salud" />
          </div>

          <div style={{ marginBottom: 26 }}>
            <h2 style={{ fontFamily: font.display, fontSize: 25, fontWeight: 800, letterSpacing: "-.4px", margin: 0 }}>Iniciá sesión</h2>
            <p style={{ fontSize: 13.5, color: color.slate500, margin: "7px 0 0" }}>
              Ingresá con tu cuenta institucional para continuar.
            </p>
          </div>

          <form onSubmit={onSubmit} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <CampoLabel label="Email">
              <CampoIcono icon="idCard">
                <input
                  className="lg-input"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="nombre@institucion.gob"
                  autoFocus
                  required
                />
              </CampoIcono>
            </CampoLabel>

            <CampoLabel
              label="Contraseña"
              right={<a href="#" className="lg-link" onClick={(e) => e.preventDefault()}>¿Olvidaste tu contraseña?</a>}
            >
              <CampoIcono icon="lock">
                <input
                  className="lg-input"
                  type={verPass ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  style={{ paddingRight: 44 }}
                  required
                />
                <button
                  type="button"
                  onClick={() => setVerPass((v) => !v)}
                  className="lg-eye"
                  title={verPass ? "Ocultar contraseña" : "Mostrar contraseña"}
                  aria-label={verPass ? "Ocultar contraseña" : "Mostrar contraseña"}
                >
                  {verPass ? <EyeOff /> : <Eye />}
                </button>
              </CampoIcono>
            </CampoLabel>

            <label className="lg-remember">
              <input type="checkbox" checked={recordar} onChange={(e) => setRecordar(e.target.checked)} />
              <span>Mantener la sesión iniciada en este equipo</span>
            </label>

            {error && (
              <div className="lg-error" role="alert">
                <Icon name="bell" size={15} style={{ flex: "none", marginTop: 1 }} />
                <span>{error}</span>
              </div>
            )}

            <button type="submit" className="lg-submit" disabled={cargando}>
              {cargando ? "Ingresando…" : "Ingresar"}
              {!cargando && <Icon name="enter" size={16} />}
            </button>
          </form>

          <div className="lg-help">
            <Icon name="help" size={14} style={{ flex: "none" }} />
            <span>¿No tenés acceso? Solicitalo a la administración de tu institución.</span>
          </div>
        </div>
      </main>
    </div>
  );
}

// Año fijo de copyright (evita new Date en SSR/loops; se calcula al cargar).
const AÑO = new Date().getFullYear();

/* ── Subcomponentes ── */

function CampoLabel({ label, right, children }) {
  return (
    <label style={{ display: "block" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 7 }}>
        <span style={{ fontSize: 13, fontWeight: 600, color: color.slate700 }}>{label}</span>
        {right}
      </div>
      {children}
    </label>
  );
}

function CampoIcono({ icon, children }) {
  return (
    <div style={{ position: "relative", display: "flex", alignItems: "center" }}>
      <span style={{ position: "absolute", left: 13, display: "flex", color: color.slate400, pointerEvents: "none" }}>
        {icon === "lock" ? <LockIcon /> : <Icon name={icon} size={17} />}
      </span>
      {children}
    </div>
  );
}

// Motivo de fondo: grafo de nodos conectados (el isotipo, en grande y difuso).
function NodeMotif() {
  return (
    <svg className="lg-motif" viewBox="0 0 600 600" fill="none" aria-hidden="true">
      <g stroke="#fff" strokeWidth="1.4" opacity=".5">
        <path d="M120 150 L300 90 M120 150 L260 280 M300 90 L470 160 M260 280 L470 160 M260 280 L210 440 M470 160 L500 360 M210 440 L420 470 M500 360 L420 470" />
      </g>
      {[[120, 150], [300, 90], [470, 160], [260, 280], [500, 360], [210, 440], [420, 470]].map(([x, y], i) => (
        <circle key={i} cx={x} cy={y} r={i % 3 === 0 ? 9 : 6} fill="#fff" opacity={i % 2 ? ".7" : ".95"} />
      ))}
    </svg>
  );
}

/* ── Íconos inline (no existen en el set base) ── */
function LockIcon() {
  return (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3.5" y="11" width="17" height="10" rx="2" /><path d="M7.5 11V7.5a4.5 4.5 0 0 1 9 0V11" /><circle cx="12" cy="16" r="1.3" fill="currentColor" stroke="none" />
    </svg>
  );
}
function Eye() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z" /><circle cx="12" cy="12" r="3" />
    </svg>
  );
}
function EyeOff() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9.9 4.24A9.1 9.1 0 0 1 12 4c6.5 0 10 8 10 8a18 18 0 0 1-2.16 3.19M6.6 6.6A18 18 0 0 0 2 12s3.5 7 10 7a9 9 0 0 0 5.4-1.6" /><path d="M14.12 14.12a3 3 0 1 1-4.24-4.24M2 2l20 20" />
    </svg>
  );
}
function ShieldDot() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2 4 5v6c0 5 3.5 8.5 8 11 4.5-2.5 8-6 8-11V5z" /><path d="m9 12 2 2 4-4" />
    </svg>
  );
}

/* ── Estilos (clases + media queries que el inline style no cubre) ── */
const CSS = `
.lg-root { min-height: 100vh; display: flex; background: ${color.canvas}; font-family: ${font.sans}; }

.lg-brand {
  position: relative; flex: 1.05; overflow: hidden; color: #fff;
  background:
    radial-gradient(120% 120% at 85% 10%, ${TEAL} 0%, rgba(14,136,147,0) 42%),
    linear-gradient(155deg, ${color.accentHover} 0%, ${color.accent} 55%, #2330A0 100%);
}
.lg-motif { position: absolute; right: -60px; top: 50%; transform: translateY(-50%); width: 560px; height: 560px; pointer-events: none; }
.lg-brand-inner { position: relative; z-index: 1; height: 100%; box-sizing: border-box; padding: 48px 52px; display: flex; flex-direction: column; }
.lg-brand-top { display: flex; align-items: center; gap: 13px; }
.lg-brand-mid { margin-top: auto; margin-bottom: auto; }
.lg-pill {
  display: inline-flex; align-items: center; gap: 9px; font-size: 12.5px; font-weight: 600;
  color: rgba(255,255,255,.9); background: rgba(255,255,255,.12); border: 1px solid rgba(255,255,255,.18);
  padding: 7px 14px; border-radius: 999px; backdrop-filter: blur(4px);
}
.lg-headline { font-family: ${font.display}; font-size: 33px; line-height: 1.18; font-weight: 800; letter-spacing: -.6px; margin: 22px 0 34px; color: #fff; }
.lg-points { display: flex; flex-direction: column; gap: 20px; max-width: 400px; }
.lg-point { display: flex; gap: 14px; align-items: flex-start; }
.lg-point-ic {
  width: 38px; height: 38px; border-radius: 11px; flex: none; display: flex; align-items: center; justify-content: center;
  background: rgba(255,255,255,.13); border: 1px solid rgba(255,255,255,.18); color: #fff;
}
.lg-brand-pulse { width: 100%; height: 22px; flex: none; color: #5EE6C4; opacity: .42; margin: 18px 0; }
.lg-brand-foot { display: flex; align-items: center; justify-content: space-between; font-size: 12px; color: rgba(255,255,255,.6); }

/* Foco visible por teclado (accesibilidad) */
.lg-link:focus-visible, .lg-eye:focus-visible, .lg-remember input:focus-visible { outline: 2px solid ${color.accent}; outline-offset: 2px; border-radius: 4px; }
.lg-submit:focus-visible { outline: 2px solid ${color.accentHover}; outline-offset: 3px; }

.lg-form-side { flex: 1; display: flex; align-items: center; justify-content: center; padding: 32px; }
.lg-card { width: 100%; max-width: 396px; }
.lg-fade { animation: lgFade .5s ease both; }
@keyframes lgFade { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }

.lg-mobile-brand { display: none; flex-direction: column; align-items: center; text-align: center; margin-bottom: 26px; }

.lg-input {
  height: 46px; width: 100%; box-sizing: border-box; border: 1px solid ${color.inputBorder}; border-radius: 11px;
  padding: 0 14px 0 42px; font-size: 14px; font-family: ${font.sans}; color: ${color.ink}; background: ${color.subtle};
  outline: none; transition: border-color .14s, box-shadow .14s, background .14s;
}
.lg-input::placeholder { color: ${color.slate400}; }
.lg-input:focus { border-color: ${color.accent}; background: #fff; box-shadow: 0 0 0 4px rgba(57,73,192,.12); }

.lg-eye {
  position: absolute; right: 8px; width: 32px; height: 32px; border: none; background: none; cursor: pointer;
  color: ${color.slate400}; display: flex; align-items: center; justify-content: center; border-radius: 8px; transition: .12s;
}
.lg-eye:hover { color: ${color.slate600}; background: ${color.divider}; }

.lg-link { font-size: 12.5px; font-weight: 600; color: ${color.accent}; text-decoration: none; }
.lg-link:hover { text-decoration: underline; }

.lg-remember { display: flex; align-items: center; gap: 9px; font-size: 13px; color: ${color.slate600}; cursor: pointer; user-select: none; }
.lg-remember input { width: 16px; height: 16px; accent-color: ${color.accent}; cursor: pointer; }

.lg-error {
  display: flex; gap: 9px; align-items: flex-start; font-size: 13px; color: ${color.danger};
  background: #FCEBEB; border: 1px solid #F4C9C5; padding: 10px 13px; border-radius: 10px; line-height: 1.4;
}

.lg-submit {
  height: 47px; width: 100%; margin-top: 2px; border: none; border-radius: 11px; cursor: pointer;
  background: ${color.accent}; color: #fff; font-size: 14.5px; font-weight: 700; font-family: ${font.sans};
  display: flex; align-items: center; justify-content: center; gap: 9px;
  box-shadow: 0 6px 16px rgba(57,73,192,.28); transition: background .14s, transform .06s, box-shadow .14s;
}
.lg-submit:hover:not(:disabled) { background: ${color.accentHover}; box-shadow: 0 8px 20px rgba(57,73,192,.34); }
.lg-submit:active:not(:disabled) { transform: translateY(1px); }
.lg-submit:disabled { background: #A7AEDC; cursor: not-allowed; box-shadow: none; }

.lg-help {
  display: flex; gap: 8px; align-items: center; margin-top: 26px; padding-top: 20px;
  border-top: 1px solid ${color.divider}; font-size: 12.5px; color: ${color.slate500};
}

@media (max-width: 900px) {
  .lg-brand { display: none; }
  .lg-mobile-brand { display: flex; }
  .lg-form-side { padding: 24px; }
}
`;
