import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";

import {
  erroresFormulario, limpiarHash, mensajePortal, rutaSegunCuenta, sesionPortal,
  useElegirClave, useIngresar, usePedidoPublico,
} from "@/api/portal";
import foto from "@/assets/portal/bienvenida.png";

import { Boton, Cabecera, Pie, RADIO, TAMANO, TEXTO } from "./ui";

import { Alerta, Aviso, CampoTexto, Exito, NOMBRE_PORTAL, Pantalla, Resultado } from "./comun";

// Pantallas sin sesión: bienvenida, alta, elegir la contraseña desde el enlace,
// ingreso y recupero de la contraseña. Los mensajes de alta, reenvío y olvido son el
// `detail` del backend tal cual: es neutro a propósito y nunca dice si el email
// existe o ya tiene cuenta.

const LINK = "font-semibold text-accent hover:underline";

/**
 * Bienvenida (Figma «1a · Bienvenida — A · Foto a sangre»). La foto es la del
 * diseño, marcada «reemplazar»: cambia cuando se acuerde la marca (#59). Con una
 * sesión abierta en la pestaña, sigue de largo a su cuenta.
 */
export function Bienvenida() {
  if (sesionPortal.access) return <Navigate to="/mi/continuar" replace />;
  return <div className={`flex flex-1 flex-col bg-superficie ${RADIO.marcoMd} md:border md:border-borde md:overflow-hidden`}>
    <div className="relative h-[472px] flex-none overflow-hidden rounded-b-[28px] bg-accent-50">
      <img src={foto} alt="" className="size-full object-cover object-[center_30%]" />
      <div aria-hidden="true" className="absolute inset-x-0 bottom-0 h-[92px] bg-gradient-to-b from-transparent to-white" />
    </div>
    <div className="flex flex-1 flex-col px-6 pb-8 pt-7">
      <p className={`${TAMANO.t13} font-bold uppercase tracking-[.08em] text-accent`}>{NOMBRE_PORTAL}</p>
      <h1 className="mt-3 text-cifra-lg font-extrabold leading-9">Tu cuenta de paciente</h1>
      <p className={`mt-3 ${TAMANO.t16} text-texto-suave`}>Creá tu cuenta con tu email y validá tu identidad con los datos de tu DNI. Es una sola vez: después, tus turnos y resultados van a estar acá.</p>
      <Pie>
        <Boton to="/mi/crear-cuenta">Crear cuenta</Boton>
        <p className="text-center text-sm leading-[21px] text-texto-suave">¿Ya tenés cuenta? <Link to="/mi/ingresar" className={LINK}>Ingresar</Link></p>
      </Pie>
    </div>
  </div>;
}

/** Formulario de un solo email (reenviar verificación, olvidé mi contraseña). */
function FormularioEmail({ titulo, atras, explicacion, path, boton, despues }) {
  const [email, setEmail] = useState("");
  const pedido = usePedidoPublico(path);
  const { campos, general } = erroresFormulario(pedido.error, ["email"]);
  const enviar = (e) => { e.preventDefault(); pedido.mutate({ email: email.trim() }); };
  return <Pantalla><Cabecera titulo={titulo} atras={atras} />
    {pedido.isSuccess
      ? <Resultado icono="enter" tono="ok" titulo="Revisá tu correo" acciones={<Boton to="/mi/ingresar">Ir a ingresar</Boton>}>
        <p role="status">{pedido.data?.detail}</p>
        {despues}
      </Resultado>
      : <form onSubmit={enviar} className="flex flex-1 flex-col" noValidate>
        <p className={TEXTO.cuerpo}>{explicacion}</p>
        <CampoTexto etiqueta="Email" type="email" autoComplete="email" autoFocus required value={email} onChange={(e) => setEmail(e.target.value)} error={campos.email} />
        <Alerta>{general}</Alerta>
        <Pie><Boton type="submit" disabled={!email.trim() || pedido.isPending}>{pedido.isPending ? "Enviando…" : boton}</Boton></Pie>
      </form>}
  </Pantalla>;
}

/**
 * Crear cuenta: SOLO el email. La contraseña se elige desde el enlace del
 * correo; si se eligiera acá, quien registrara primero el email de otra persona
 * le dejaría su clave y la dueña la terminaría confirmando sin saberlo.
 * La respuesta es la misma exista o no el email.
 */
export function Registro() {
  const [email, setEmail] = useState("");
  const pedido = usePedidoPublico("/cuenta/registro/");
  const reenviar = usePedidoPublico("/cuenta/reenviar-verificacion/");
  const { campos, general } = erroresFormulario(pedido.error, ["email"]);
  const enviar = (e) => { e.preventDefault(); pedido.mutate({ email: email.trim() }); };
  if (pedido.isSuccess) return <Pantalla><Cabecera titulo="Crear cuenta" atras="/mi" />
    <Resultado icono="enter" tono="ok" titulo="Revisá tu correo" acciones={<>
      <Boton variante="secundario" onClick={() => reenviar.mutate({ email: email.trim() })} disabled={reenviar.isPending}>{reenviar.isPending ? "Enviando…" : "Reenviar el correo"}</Boton>
      <Boton to="/mi/ingresar" variante="texto">Ir a ingresar</Boton>
    </>}>
      <p>Abrí el enlace que te mandamos para elegir tu contraseña.</p>
      <p role="status">{pedido.data?.detail}</p>
      <p>¿No te llegó? Revisá el correo no deseado o pedí que te lo reenviemos.</p>
      {reenviar.isSuccess && <Exito>{reenviar.data?.detail}</Exito>}
      <Alerta>{reenviar.isError ? mensajePortal(reenviar.error) : ""}</Alerta>
    </Resultado>
  </Pantalla>;
  return <Pantalla><Cabecera titulo="Crear cuenta" atras="/mi" />
    <form onSubmit={enviar} className="flex flex-1 flex-col" noValidate>
      <p className={TEXTO.cuerpo}>Escribí tu email. Te mandamos un enlace para elegir tu contraseña.</p>
      <CampoTexto etiqueta="Email" type="email" autoComplete="email" autoFocus required value={email} onChange={(e) => setEmail(e.target.value)} error={campos.email} />
      <Alerta>{general}</Alerta>
      <Pie>
        <Boton type="submit" disabled={!email.trim() || pedido.isPending}>{pedido.isPending ? "Enviando…" : "Crear cuenta"}</Boton>
        <p className="text-center text-sm leading-[21px] text-texto-suave">¿Ya tenés cuenta? <Link to="/mi/ingresar" className={LINK}>Ingresar</Link></p>
      </Pie>
    </form>
  </Pantalla>;
}

const tokenDe = (hash) => new URLSearchParams(hash.replace(/^#/, "")).get("token") || "";

/**
 * Token del enlace (`#token=…`). Se saca de la barra de direcciones (y del
 * historial) apenas aparece, pero queda en memoria hasta que el pedido salga
 * bien: una contraseña débil no gasta el enlace y se reintenta con el mismo.
 *
 * Se lee de `window.location` y se escucha `hashchange`, no el `hash` de React
 * Router: `replaceState` no le avisa al router, así que si se pegaba el MISMO
 * enlace otra vez en la pestaña (navegación de fragmento, sin recarga) el
 * router no veía cambio y el token quedaba en la barra.
 */
function useTokenDelEnlace() {
  const [token, setToken] = useState(() => tokenDe(window.location.hash));
  useEffect(() => {
    const leer = () => {
      const nuevo = tokenDe(window.location.hash);
      if (!nuevo) return;
      setToken(nuevo);
      limpiarHash();
    };
    leer();
    window.addEventListener("hashchange", leer);
    return () => window.removeEventListener("hashchange", leer);
  }, []);
  return token;
}

/** Contraseña nueva y su repetición, con el «no coinciden» y el error del backend. */
function useClaveRepetida() {
  const [datos, setDatos] = useState({ password: "", repetir: "" });
  const [noCoinciden, setNoCoinciden] = useState(false);
  const cambiar = (clave) => (e) => setDatos((d) => ({ ...d, [clave]: e.target.value }));
  const coinciden = () => {
    const distintas = datos.password !== datos.repetir;
    setNoCoinciden(distintas);
    return !distintas;
  };
  const campos = (errorPassword, etiqueta = "Contraseña") => <>
    <CampoTexto etiqueta={etiqueta} type="password" autoComplete="new-password" autoFocus required value={datos.password} onChange={cambiar("password")} error={errorPassword} />
    <CampoTexto etiqueta="Repetí la contraseña" type="password" autoComplete="new-password" required value={datos.repetir} onChange={cambiar("repetir")} error={noCoinciden ? "Las contraseñas no coinciden." : ""} />
  </>;
  return { datos, coinciden, campos, completo: Boolean(datos.password && datos.repetir) };
}

const ENLACE_INCOMPLETO = <p>Abrí el enlace tal como llegó en el correo, o pedí uno nuevo.</p>;

/**
 * Destino del enlace del alta: `/mi/verificar-email#token=…`. Acá se elige la
 * contraseña; al guardarla el email queda confirmado y la persona, logueada.
 * Cada token monta la pantalla de nuevo (`key`): un enlace distinto arranca de cero.
 */
export function VerificarEmail() {
  const token = useTokenDelEnlace();
  return <ElegirClave key={token} token={token} />;
}

function ElegirClave({ token }) {
  const navigate = useNavigate();
  const elegir = useElegirClave();
  const clave = useClaveRepetida();
  const { campos, general } = erroresFormulario(elegir.error, ["password"]);
  const enviar = (e) => {
    e.preventDefault();
    if (!clave.coinciden()) return;
    elegir.mutate({ token, password: clave.datos.password }, {
      onSuccess: (data) => navigate(rutaSegunCuenta(data.cuenta), { replace: true }),
    });
  };
  const pedirOtro = <Boton to="/mi/reenviar-verificacion" variante="secundario">Pedir un enlace nuevo</Boton>;
  return <Pantalla><Cabecera titulo="Elegí tu contraseña" />
    {!token
      ? <Resultado titulo="El enlace está incompleto" acciones={pedirOtro}>{ENLACE_INCOMPLETO}</Resultado>
      : elegir.error?.data?.codigo === "enlace_invalido"
        ? <Resultado titulo="El enlace ya no sirve" acciones={pedirOtro}><p role="alert">{mensajePortal(elegir.error)}</p><p>Se usó, venció o no es válido.</p></Resultado>
        : <form onSubmit={enviar} className="flex flex-1 flex-col" noValidate>
          <p className={TEXTO.cuerpo}>Elegí la contraseña de tu cuenta. Con esto también confirmás tu email.</p>
          {clave.campos(campos.password)}
          <Alerta>{general}</Alerta>
          <Pie><Boton type="submit" disabled={!clave.completo || elegir.isPending}>{elegir.isPending ? "Guardando…" : "Guardar y entrar"}</Boton></Pie>
        </form>}
  </Pantalla>;
}

export function ReenviarVerificacion() {
  return <FormularioEmail titulo="Reenviar verificación" atras="/mi/ingresar" path="/cuenta/reenviar-verificacion/" boton="Reenviar el enlace"
    explicacion="Escribí el email con el que creaste la cuenta y te mandamos un enlace nuevo para elegir tu contraseña." />;
}

export function Olvide() {
  return <FormularioEmail titulo="Olvidé mi contraseña" atras="/mi/ingresar" path="/cuenta/olvide/" boton="Enviar el enlace"
    explicacion="Escribí el email de tu cuenta y te mandamos un enlace para elegir una contraseña nueva."
    despues={<p>El enlace vence al rato. Si no te llega, revisá el correo no deseado.</p>} />;
}

/** Ingresar. Después, cada cuenta va a la pantalla de lo que le falta completar. */
export function Ingresar() {
  const navigate = useNavigate();
  const { state } = useLocation();
  const [datos, setDatos] = useState({ email: "", password: "" });
  const ingresar = useIngresar();
  const { campos, general } = erroresFormulario(ingresar.error, ["email", "password"]);
  if (sesionPortal.access && !ingresar.isPending && !ingresar.isSuccess) return <Navigate to="/mi/continuar" replace />;
  const cambiar = (clave) => (e) => setDatos((d) => ({ ...d, [clave]: e.target.value }));
  const enviar = (e) => {
    e.preventDefault();
    ingresar.mutate({ email: datos.email.trim(), password: datos.password }, {
      onSuccess: (data) => navigate(rutaSegunCuenta(data.cuenta), { replace: true }),
    });
  };
  return <Pantalla><Cabecera titulo="Ingresar" atras="/mi" />
    <form onSubmit={enviar} className="flex flex-1 flex-col" noValidate>
      {state?.aviso && !ingresar.error && <Aviso>{state.aviso}</Aviso>}
      <CampoTexto etiqueta="Email" type="email" autoComplete="email" autoFocus required value={datos.email} onChange={cambiar("email")} error={campos.email} />
      <CampoTexto etiqueta="Contraseña" type="password" autoComplete="current-password" required value={datos.password} onChange={cambiar("password")} error={campos.password} />
      <p className="mt-3 text-xs"><Link to="/mi/olvide" className={LINK}>Olvidé mi contraseña</Link></p>
      <Alerta>{general}</Alerta>
      {/* Una cuenta sin confirmar da el mismo 401 que una clave mala (no se
          revela qué cuentas existen): la ayuda cubre a quien recién se registró. */}
      {ingresar.error?.data?.codigo === "credenciales_invalidas" && <p className={`mt-3 ${TEXTO.nota}`}>¿Recién creaste tu cuenta? Abrí el enlace que te mandamos para elegir tu contraseña. <Link to="/mi/reenviar-verificacion" className={LINK}>Reenviar el correo</Link></p>}
      <Pie>
        <Boton type="submit" disabled={!datos.email.trim() || !datos.password || ingresar.isPending}>{ingresar.isPending ? "Ingresando…" : "Ingresar"}</Boton>
        <p className="text-center text-sm leading-[21px] text-texto-suave">¿No tenés cuenta? <Link to="/mi/crear-cuenta" className={LINK}>Creala</Link></p>
      </Pie>
    </form>
  </Pantalla>;
}

/** Destino del enlace de recupero: `/mi/restablecer#token=…`. Remonta por token, como verificar. */
export function Restablecer() {
  const token = useTokenDelEnlace();
  return <RestablecerConToken key={token} token={token} />;
}

function RestablecerConToken({ token }) {
  const qc = useQueryClient();
  const clave = useClaveRepetida();
  const pedido = usePedidoPublico("/cuenta/restablecer/");
  const { campos, general } = erroresFormulario(pedido.error, ["password"]);
  const enviar = (e) => {
    e.preventDefault();
    if (!clave.coinciden()) return;
    pedido.mutate({ token, password: clave.datos.password }, {
      // El backend cierra todas las sesiones de la cuenta: la de esta pestaña también.
      onSuccess: () => { sesionPortal.clear(); qc.removeQueries({ queryKey: ["portal"] }); },
    });
  };
  const pedirOtro = <Boton to="/mi/olvide" variante="secundario">Pedir un enlace nuevo</Boton>;
  return <Pantalla><Cabecera titulo="Nueva contraseña" />
    {!token
      ? <Resultado titulo="El enlace está incompleto" acciones={pedirOtro}>{ENLACE_INCOMPLETO}</Resultado>
      : pedido.isSuccess
        ? <Resultado icono="shieldCheck" tono="ok" titulo="Listo, cambiaste tu contraseña" acciones={<Boton to="/mi/ingresar">Ingresar</Boton>}>
          <p role="status">{pedido.data?.detail}</p>
          <p>Cerramos las sesiones abiertas: ingresá con la contraseña nueva.</p>
        </Resultado>
        : pedido.error?.data?.codigo === "enlace_invalido"
          ? <Resultado titulo="El enlace ya no sirve" acciones={pedirOtro}><p role="alert">{mensajePortal(pedido.error)}</p><p>Se usó, venció o no es válido.</p></Resultado>
          : <form onSubmit={enviar} className="flex flex-1 flex-col" noValidate>
            <p className={TEXTO.cuerpo}>Elegí una contraseña nueva para tu cuenta.</p>
            {clave.campos(campos.password, "Contraseña nueva")}
            <Alerta>{general}</Alerta>
            <Pie><Boton type="submit" disabled={!clave.completo || pedido.isPending}>{pedido.isPending ? "Guardando…" : "Guardar contraseña"}</Boton></Pie>
          </form>}
  </Pantalla>;
}
