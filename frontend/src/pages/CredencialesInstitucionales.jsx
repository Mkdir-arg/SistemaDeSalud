import { useLayoutEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { api, mensajeError } from "@/api/client";
import { useAuth } from "@/auth/AuthContext";
import { leerCredencialesFragmento, limpiarFragmentoCredenciales } from "@/auth/credencialesInstitucionales";
import { Logo } from "@/components/Logo";
import { Button, Card, Field, Input } from "@/components/ui";
import { NOMBRE_SISTEMA } from "@/lib/marca";

const SOLICITUD_ACEPTADA = "Si la cuenta puede recibir el enlace, enviaremos las instrucciones a su correo. La solicitud aceptada no confirma la entrega del mensaje.";

function PanelCredenciales({ titulo, children }) {
  return <main className="min-h-screen bg-fondo px-4 py-10 text-texto">
    <div className="mx-auto w-full max-w-[32rem]">
      <div className="mb-6 flex items-center gap-2 font-bold"><Logo size={26} /> {NOMBRE_SISTEMA}</div>
      <Card className="p-6 sm:p-8">
        <h1 className="mb-4 text-xl font-bold">{titulo}</h1>
        {children}
      </Card>
      <Link to="/login" className="mt-5 inline-block text-sm text-accent underline">Volver al ingreso institucional</Link>
    </div>
  </main>;
}

function Aviso({ error, children }) {
  if (!children) return null;
  return <p role={error ? "alert" : "status"} className={`rounded-md border p-3 text-sm ${error ? "border-danger bg-badge-error-bg text-danger" : "border-division bg-superficie-2 text-texto-suave"}`}>{children}</p>;
}

function useCredencialesDelEnlace() {
  // El inicializador sólo lee: React puede ejecutarlo dos veces en StrictMode.
  const [credenciales, setCredenciales] = useState(() => leerCredencialesFragmento(window.location.hash));
  useLayoutEffect(() => {
    limpiarFragmentoCredenciales(window.location, window.history);
  }, []);
  return [credenciales, () => setCredenciales({ uid: "", token: "", nuevo_email: "" })];
}

function PasswordNueva({ password, confirmar, onPassword, onConfirmar }) {
  return <>
    <Field label="Nueva contraseña" hint="Evitá contraseñas comunes, numéricas o similares a tus datos personales.">
      <Input type="password" value={password} onChange={(e) => onPassword(e.target.value)} autoComplete="new-password" required />
    </Field>
    <Field label="Confirmar nueva contraseña" error={confirmar && password !== confirmar ? "Las contraseñas no coinciden." : undefined}>
      <Input type="password" value={confirmar} onChange={(e) => onConfirmar(e.target.value)} autoComplete="new-password" required />
    </Field>
  </>;
}

export function RecuperarAcceso() {
  const { simulacion } = useAuth();
  const [email, setEmail] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState("");
  const [solicitado, setSolicitado] = useState(false);

  async function enviar(e) {
    e.preventDefault();
    if (ocupado || simulacion) return;
    setOcupado(true);
    setError("");
    setSolicitado(false);
    try {
      await api.public.post("/auth/recuperacion/", { email: email.trim() });
      setSolicitado(true);
    } catch (err) {
      setError(mensajeError(err, "No se pudo solicitar el enlace. Reintentá más tarde."));
    } finally { setOcupado(false); }
  }

  return <PanelCredenciales titulo="Recuperar acceso institucional">
    {simulacion ? <Aviso error>Finalizá la simulación antes de gestionar credenciales.</Aviso> : <>
    <p className="mb-5 text-sm text-texto-debil">Ingresá el correo de tu cuenta institucional. Este formulario también permite solicitar otro enlace de invitación.</p>
    <form onSubmit={enviar} className="space-y-4" aria-busy={ocupado}>
      <Field label="Email"><Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" required /></Field>
      <Aviso error>{error}</Aviso>
      {solicitado && <Aviso>{SOLICITUD_ACEPTADA}</Aviso>}
      <Button type="submit" disabled={ocupado || !email.trim()}>{ocupado ? "Solicitando…" : "Solicitar enlace"}</Button>
    </form>
    </>}
  </PanelCredenciales>;
}

export function RestablecerAcceso() {
  const [credenciales, olvidarEnlace] = useCredencialesDelEnlace();
  const { logout, simulacion } = useAuth();
  const [password, setPassword] = useState("");
  const [confirmar, setConfirmar] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState("");
  const [completado, setCompletado] = useState(false);
  const valido = !!credenciales.uid && !!credenciales.token;

  async function enviar(e) {
    e.preventDefault();
    if (ocupado || !valido || simulacion || !password || password !== confirmar) return;
    setOcupado(true);
    setError("");
    try {
      await api.public.post("/auth/restablecer/", { uid: credenciales.uid, token: credenciales.token, nueva_password: password });
      olvidarEnlace();
      setPassword("");
      setConfirmar("");
      logout();
      setCompletado(true);
    } catch (err) {
      setError(mensajeError(err, "No se pudo restablecer el acceso. Solicitá otro enlace si venció."));
    } finally { setOcupado(false); }
  }

  return <PanelCredenciales titulo="Establecer contraseña">
    {completado ? <Aviso>Contraseña guardada. Ingresá nuevamente con tu email y la nueva contraseña.</Aviso>
      : simulacion ? <Aviso error>Finalizá la simulación antes de gestionar credenciales.</Aviso>
        : !valido ? <Aviso error>El enlace está incompleto. Abrí el enlace del correo o <Link to="/recuperar-acceso" className="underline">solicitá uno nuevo</Link>.</Aviso>
          : <form onSubmit={enviar} className="space-y-4" aria-busy={ocupado}>
            <PasswordNueva password={password} confirmar={confirmar} onPassword={setPassword} onConfirmar={setConfirmar} />
            <Aviso error>{error}</Aviso>
            <Button type="submit" disabled={ocupado || !password || password !== confirmar}>{ocupado ? "Guardando…" : "Guardar contraseña"}</Button>
          </form>}
  </PanelCredenciales>;
}

export function ConfirmarEmail() {
  const [credenciales, olvidarEnlace] = useCredencialesDelEnlace();
  const { logout, simulacion } = useAuth();
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState("");
  const [completado, setCompletado] = useState(false);
  const valido = !!credenciales.uid && !!credenciales.token && !!credenciales.nuevo_email;

  async function confirmar(e) {
    e.preventDefault();
    if (ocupado || !valido || simulacion) return;
    setOcupado(true);
    setError("");
    try {
      await api.public.post("/auth/confirmar-email/", credenciales);
      olvidarEnlace();
      logout();
      setCompletado(true);
    } catch (err) {
      setError(mensajeError(err, "No se pudo confirmar el email. Solicitá un nuevo enlace desde tu cuenta."));
    } finally { setOcupado(false); }
  }

  return <PanelCredenciales titulo="Confirmar nuevo email">
    {completado ? <Aviso>Email actualizado. Ingresá nuevamente con tu nueva dirección.</Aviso>
      : simulacion ? <Aviso error>Finalizá la simulación antes de gestionar credenciales.</Aviso>
        : !valido ? <Aviso error>El enlace está incompleto. Solicitá el cambio de email nuevamente desde tu cuenta.</Aviso>
          : <form onSubmit={confirmar} className="space-y-4" aria-busy={ocupado}>
            <p className="break-words text-sm text-texto-suave">Confirmá que querés usar <strong>{credenciales.nuevo_email}</strong> como email de ingreso.</p>
            <Aviso error>{error}</Aviso>
            <Button type="submit" disabled={ocupado}>{ocupado ? "Confirmando…" : "Confirmar email"}</Button>
          </form>}
  </PanelCredenciales>;
}

export function MiCuenta() {
  const { user, logout, simulacion } = useAuth();
  const navigate = useNavigate();
  const [actualPassword, setActualPassword] = useState("");
  const [nuevaPassword, setNuevaPassword] = useState("");
  const [confirmarPassword, setConfirmarPassword] = useState("");
  const [actualEmailPassword, setActualEmailPassword] = useState("");
  const [nuevoEmail, setNuevoEmail] = useState("");
  const [ocupado, setOcupado] = useState("");
  const [error, setError] = useState("");
  const [solicitado, setSolicitado] = useState(false);

  async function cambiarPassword(e) {
    e.preventDefault();
    if (ocupado || simulacion || !nuevaPassword || nuevaPassword !== confirmarPassword) return;
    setOcupado("password");
    setError("");
    try {
      await api.post("/auth/cambiar-password/", { password_actual: actualPassword, nueva_password: nuevaPassword });
      setActualPassword(""); setNuevaPassword(""); setConfirmarPassword(""); setActualEmailPassword("");
      logout();
      navigate("/login", { replace: true, state: { aviso: "Contraseña actualizada. Volvé a ingresar; las sesiones anteriores quedaron revocadas." } });
    } catch (err) {
      setError(mensajeError(err, "No se pudo cambiar la contraseña."));
    } finally { setOcupado(""); }
  }

  async function cambiarEmail(e) {
    e.preventDefault();
    if (ocupado || simulacion) return;
    setOcupado("email"); setError(""); setSolicitado(false);
    try {
      await api.post("/auth/cambio-email/", { password_actual: actualEmailPassword, nuevo_email: nuevoEmail.trim() });
      setActualEmailPassword(""); setNuevoEmail(""); setSolicitado(true);
    } catch (err) {
      setError(mensajeError(err, "No se pudo solicitar el cambio de email."));
    } finally { setOcupado(""); }
  }

  return <div className="mx-auto max-w-3xl space-y-5 px-4 py-8">
    <Link to="/directorio" className="inline-block text-sm text-accent underline">Volver a mi espacio de trabajo</Link>
    <header><h1 className="text-xl font-bold">Mi cuenta institucional</h1><p className="mt-1 break-all text-sm text-texto-debil">{user?.email}</p></header>
    {simulacion ? <Aviso error>Finalizá la simulación antes de gestionar tu cuenta.</Aviso> : <>
      <Aviso error>{error}</Aviso>
      <Card className="p-5 sm:p-6">
        <h2 className="mb-2 text-lg font-bold">Cambiar contraseña</h2>
        <p className="mb-4 text-sm text-texto-debil">Al guardarla se cerrarán todas tus sesiones y tendrás que ingresar nuevamente.</p>
        <form onSubmit={cambiarPassword} className="space-y-4" aria-busy={ocupado === "password"}>
          <Field label="Contraseña actual"><Input type="password" value={actualPassword} onChange={(e) => setActualPassword(e.target.value)} autoComplete="current-password" required /></Field>
          <PasswordNueva password={nuevaPassword} confirmar={confirmarPassword} onPassword={setNuevaPassword} onConfirmar={setConfirmarPassword} />
          <Button type="submit" disabled={!!ocupado || !actualPassword || !nuevaPassword || nuevaPassword !== confirmarPassword}>{ocupado === "password" ? "Guardando…" : "Cambiar contraseña"}</Button>
        </form>
      </Card>
      <Card className="p-5 sm:p-6">
        <h2 className="mb-2 text-lg font-bold">Cambiar email de ingreso</h2>
        <p className="mb-4 text-sm text-texto-debil">Tu email actual seguirá vigente hasta confirmar el enlace enviado al nuevo correo.</p>
        <form onSubmit={cambiarEmail} className="space-y-4" aria-busy={ocupado === "email"}>
          <Field label="Nuevo email"><Input type="email" value={nuevoEmail} onChange={(e) => setNuevoEmail(e.target.value)} autoComplete="email" required /></Field>
          <Field label="Contraseña actual"><Input type="password" value={actualEmailPassword} onChange={(e) => setActualEmailPassword(e.target.value)} autoComplete="current-password" required /></Field>
          {solicitado && <Aviso>Solicitud aceptada. Si puede completarse el cambio, recibirás instrucciones en el nuevo correo. Esto no confirma la entrega.</Aviso>}
          <Button type="submit" disabled={!!ocupado || !actualEmailPassword || !nuevoEmail.trim()}>{ocupado === "email" ? "Solicitando…" : "Solicitar cambio de email"}</Button>
        </form>
      </Card>
    </>}
  </div>;
}
