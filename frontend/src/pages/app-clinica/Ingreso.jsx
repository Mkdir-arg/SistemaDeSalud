import { useState } from "react";
import { Link, Navigate, Outlet, useNavigate } from "react-router-dom";

import { CLINICA, cobertura, COBERTURAS, fechaConAnio, pacienteConocida } from "./datos";
import { useApp } from "./estado";
import { Aviso } from "./Shell";
import { Boton, Cabecera, Campo, CLASE_CAMPO, MarcaClinica, Pie, ruta, Tarjeta } from "./ui";

// Figma «1 · Ingreso» (ready for dev): 1a bienvenida con foto a sangre, 1b DNI,
// 1c código por SMS y 1d datos de paciente nueva.
const FOTO = "/app-clinica/bienvenida.jpg";
const FOTO_ALT = "Paciente sentada en la sala de espera de la clínica, mirando su celular";
const LARGO_CODIGO = 6;

const soloDigitos = (s = "") => s.replace(/\D/g, "");
const formatoDni = (dni) => (dni ? Number(dni).toLocaleString("es-AR") : "");
const ultimos4 = (celular) => soloDigitos(celular).slice(-4);

/** Marco del ingreso: en escritorio, la foto a la izquierda y el paso a la derecha. */
export function MarcoIngreso() {
  const { paciente } = useApp();
  if (paciente) return <Navigate to={ruta("inicio")} replace />;
  return <div className="flex min-h-dvh bg-fondo text-texto">
    <aside className="relative hidden flex-1 overflow-hidden bg-accent-50 md:block">
      <img src={FOTO} alt="" className="absolute inset-0 size-full object-cover object-[center_30%]" />
      <span className="absolute left-8 top-8 flex items-center gap-2.5 rounded-md bg-superficie/95 px-3 py-2 text-sm font-bold shadow-card"><MarcaClinica size={28} />{CLINICA.nombre}</span>
    </aside>
    <main className="flex flex-1 flex-col md:items-center md:justify-center md:p-10">
      <div className="flex w-full flex-1 flex-col md:max-w-[24rem] md:flex-none"><Outlet /></div>
    </main>
    <Aviso />
  </div>;
}

function Pantalla({ children }) {
  return <div className="flex flex-1 flex-col px-5 pb-6 pt-4 md:min-h-[560px] md:px-0">{children}</div>;
}

/** 1a · Bienvenida — foto a sangre. */
export function Bienvenida() {
  return <>
    <img src={FOTO} alt={FOTO_ALT} className="h-[54dvh] min-h-[300px] w-full flex-none rounded-b-[28px] bg-accent-50 object-cover object-[center_28%] md:hidden" />
    <div className="flex flex-1 flex-col px-6 pb-6 pt-6 md:px-0 md:pt-0">
      <p className="text-xs font-bold tracking-[.15em] text-accent">CLÍNICA MODELO</p>
      <h1 className="mt-2 text-xxl font-bold leading-tight">Hola, te damos la bienvenida</h1>
      <p className="mt-3 text-sm leading-relaxed text-texto-suave">Sacá turno, avisá que llegaste sin hacer fila y mirá tus resultados. Estamos para cuidarte.</p>
      <Pie>
        <Boton to={ruta("ingresar")}>Empezar</Boton>
        <p className="text-center text-xs text-texto-suave">¿Ya tenés cuenta? <Link to={ruta("ingresar")} className="font-semibold text-accent hover:underline">Ingresar</Link></p>
        <p className="pt-3 text-center text-micro text-texto-suave">Demo de HEN con datos ficticios · <Link to="/" className="font-semibold text-accent hover:underline">Conocé HEN</Link></p>
      </Pie>
    </div>
  </>;
}

/** 1b · Ingresar con DNI. Teclado numérico y puntos de miles al escribir. */
export function Dni() {
  const { ingreso, acciones } = useApp();
  const [dni, setDni] = useState(ingreso?.dni || "");
  const navigate = useNavigate();
  const continuar = (e) => {
    e.preventDefault();
    if (dni.length < 7) return;
    acciones.empezarIngreso(dni);
    navigate(ruta(dni === pacienteConocida().dni ? "ingresar/codigo" : "ingresar/celular"));
  };
  return <Pantalla><Cabecera titulo="Ingresar" atras={ruta()} />
    <form onSubmit={continuar} className="flex flex-1 flex-col">
      <h2 className="text-xl font-bold">¿Cuál es tu DNI?</h2>
      <p className="mt-2 text-sm text-texto-suave">Con tu DNI buscamos si ya te atendiste en la clínica.</p>
      <Campo etiqueta="Número de documento">
        <input autoFocus inputMode="numeric" autoComplete="off" value={formatoDni(dni)} onChange={(e) => setDni(soloDigitos(e.target.value).slice(0, 8))} placeholder="Ej.: 34.521.521" className={`${CLASE_CAMPO} text-base`} />
      </Campo>
      <Pie><Boton type="submit" disabled={dni.length < 7}>Continuar</Boton></Pie>
    </form>
  </Pantalla>;
}

/** Paciente nueva sin celular en el padrón: se pide uno antes de mandar el código (nota de 1c). */
export function Celular() {
  const { ingreso, acciones } = useApp();
  const navigate = useNavigate();
  const [celular, setCelular] = useState(ingreso?.celular || "");
  if (!ingreso) return <Navigate to={ruta("ingresar")} replace />;
  if (ingreso.conocida) return <Navigate to={ruta("ingresar/codigo")} replace />;
  const valido = soloDigitos(celular).length >= 8;
  const continuar = (e) => { e.preventDefault(); if (!valido) return; acciones.guardarCelular(celular); navigate(ruta("ingresar/codigo")); };
  return <Pantalla><Cabecera titulo="Ingresar" atras={ruta("ingresar")} />
    <form onSubmit={continuar} className="flex flex-1 flex-col">
      <h2 className="text-xl font-bold">¿A qué celular te mandamos el código?</h2>
      <p className="mt-2 text-sm text-texto-suave">No encontramos un celular registrado con tu DNI. Te mandamos un código por SMS para confirmar que es tuyo.</p>
      <Campo etiqueta="Celular">
        <input autoFocus inputMode="tel" autoComplete="tel" value={celular} onChange={(e) => setCelular(e.target.value)} placeholder="11 5555-4521" className={`${CLASE_CAMPO} text-base`} />
      </Campo>
      <Pie><Boton type="submit" disabled={!valido}>Continuar</Boton></Pie>
    </form>
  </Pantalla>;
}

/**
 * Casillas del código. Hay un solo <input> real, transparente y encima de las
 * casillas: así funcionan pegar, el autocompletado del SMS y el lector de pantalla.
 */
function CasillasCodigo({ valor, onCambiar }) {
  const [foco, setFoco] = useState(true);
  return <div className="relative mt-6">
    <input autoFocus inputMode="numeric" autoComplete="one-time-code" aria-label={`Código de ${LARGO_CODIGO} dígitos`} value={valor}
      onChange={(e) => onCambiar(soloDigitos(e.target.value).slice(0, LARGO_CODIGO))} onFocus={() => setFoco(true)} onBlur={() => setFoco(false)}
      className="absolute inset-0 z-10 size-full cursor-text opacity-0" />
    <div aria-hidden="true" className="flex gap-2">
      {Array.from({ length: LARGO_CODIGO }, (_, i) => {
        const actual = foco && i === Math.min(valor.length, LARGO_CODIGO - 1);
        return <span key={i} className={`flex h-14 flex-1 items-center justify-center rounded-md border bg-superficie text-xl font-bold ${valor[i] || actual ? "border-accent" : "border-campo-borde"} ${actual ? "ring-2 ring-accent-100" : ""}`}>{valor[i] || ""}</span>;
      })}
    </div>
  </div>;
}

/** 1c · Código por SMS. */
export function Codigo() {
  const { ingreso, acciones } = useApp();
  const navigate = useNavigate();
  const [codigo, setCodigo] = useState("");
  if (!ingreso) return <Navigate to={ruta("ingresar")} replace />;
  if (!ingreso.conocida && !ingreso.celular) return <Navigate to={ruta("ingresar/celular")} replace />;
  const celular = ingreso.conocida ? pacienteConocida().celular : ingreso.celular;
  const continuar = (e) => {
    e.preventDefault();
    if (codigo.length !== LARGO_CODIGO) return;
    acciones.verificarCodigo();
    navigate(ruta(ingreso.conocida ? "ingresar/confirmar" : "ingresar/datos"), { replace: true });
  };
  const [turnos] = CLINICA.telefonos;
  return <Pantalla><Cabecera titulo="Ingresar" atras={ruta(ingreso.conocida ? "ingresar" : "ingresar/celular")} />
    <form onSubmit={continuar} className="flex flex-1 flex-col">
      <h2 className="text-xl font-bold">Te enviamos un código</h2>
      <p className="mt-2 text-sm text-texto-suave">Lo mandamos al celular que termina en {ultimos4(celular)}. Vence en 5 minutos.</p>
      <CasillasCodigo valor={codigo} onCambiar={setCodigo} />
      <p className="mt-4 text-xs text-texto-suave">
        {ingreso.conocida
          ? <>¿Cambiaste de número? Llamá a la clínica al <a href={`tel:${turnos.tel}`} className="font-semibold text-accent hover:underline">{turnos.texto}</a>.</>
          : <>¿Te equivocaste de número? <Link to={ruta("ingresar/celular")} className="font-semibold text-accent hover:underline">Cambialo</Link>.</>}
      </p>
      <Pie><Boton type="submit" disabled={codigo.length !== LARGO_CODIGO}>Continuar</Boton></Pie>
    </form>
  </Pantalla>;
}

/** Paciente conocida: reemplaza a 1d con «¿Sos …?» y su cobertura para confirmar (nota de 1d). */
export function ConfirmarIdentidad() {
  const { ingreso, acciones, avisar } = useApp();
  const navigate = useNavigate();
  if (!ingreso?.verificado || !ingreso.conocida) return <Navigate to={ruta("ingresar")} replace />;
  const p = pacienteConocida();
  const c = cobertura(p.cobertura);
  const soyYo = () => { acciones.confirmarIdentidad(); navigate(ruta("inicio"), { replace: true }); };
  const noSoyYo = () => { acciones.salir(); avisar("Revisá el DNI. Si los datos no son tuyos, avisá en la recepción de la clínica."); navigate(ruta("ingresar"), { replace: true }); };
  return <Pantalla><Cabecera titulo="Tus datos" atras={ruta("ingresar")} />
    <h2 className="text-xl font-bold">¿Sos {p.nombre}?</h2>
    <p className="mt-2 text-sm text-texto-suave">Encontramos tus datos en el padrón de la clínica. Confirmá que sos vos para entrar.</p>
    <Tarjeta className="mt-5 space-y-4 p-4">
      {[["DNI", formatoDni(p.dni)], ["Fecha de nacimiento", fechaConAnio(p.nacimiento)], ["Cobertura", `${c.nombre} · credencial ${p.credencial}`]]
        .map(([k, v]) => <div key={k}><p className="text-xs text-texto-suave">{k}</p><strong className="mt-0.5 block text-sm">{v}</strong></div>)}
    </Tarjeta>
    <p className="mt-4 text-xs text-texto-suave">Si cambió algún dato, lo actualizás en la recepción.</p>
    <Pie>
      <Boton onClick={soyYo}>Sí, soy yo</Boton>
      <Boton variante="texto" onClick={noSoyYo}>No soy yo</Boton>
    </Pie>
  </Pantalla>;
}

/** 1d · Completar datos (paciente nueva). Solo tres datos obligatorios; el resto se completa en la clínica. */
export function Datos() {
  const { ingreso, acciones } = useApp();
  const navigate = useNavigate();
  const [datos, setDatos] = useState({ nombre: "", nacimiento: "", celular: ingreso?.celular || "", cobertura: "particular" });
  if (!ingreso?.verificado || ingreso.conocida) return <Navigate to={ruta("ingresar")} replace />;
  const cambiar = (clave) => (e) => setDatos((d) => ({ ...d, [clave]: e.target.value }));
  const completo = datos.nombre.trim().length > 2 && datos.nacimiento && soloDigitos(datos.celular).length >= 8;
  const guardar = (e) => { e.preventDefault(); if (!completo) return; acciones.registrar(datos); navigate(ruta("inicio"), { replace: true }); };
  const obligatorio = (texto) => <>{texto} <span className="text-accent">*</span></>;
  return <Pantalla><Cabecera titulo="Tus datos" atras={ruta("ingresar")} />
    <form onSubmit={guardar} className="flex flex-1 flex-col">
      <h2 className="text-xl font-bold">Es tu primera vez en la clínica</h2>
      <p className="mt-2 text-sm text-texto-suave">Completá estos datos una sola vez.</p>
      <Campo etiqueta={obligatorio("Nombre y apellido")}><input autoFocus autoComplete="name" aria-label="Nombre y apellido" value={datos.nombre} onChange={cambiar("nombre")} className={CLASE_CAMPO} /></Campo>
      <Campo etiqueta={obligatorio("Fecha de nacimiento")}><input type="date" autoComplete="bday" aria-label="Fecha de nacimiento" max={new Date().toISOString().slice(0, 10)} value={datos.nacimiento} onChange={cambiar("nacimiento")} className={CLASE_CAMPO} /></Campo>
      <Campo etiqueta={obligatorio("Celular")}><input inputMode="tel" autoComplete="tel" aria-label="Celular" value={datos.celular} onChange={cambiar("celular")} className={CLASE_CAMPO} /></Campo>
      <Campo etiqueta={<>Cobertura <span className="font-normal text-texto-suave">(opcional)</span></>} ayuda="Si tenés obra social o prepaga, te mostramos cuánto cubre.">
        <select aria-label="Cobertura" value={datos.cobertura} onChange={cambiar("cobertura")} className={CLASE_CAMPO}>{COBERTURAS.map((c) => <option key={c.id} value={c.id}>{c.copago === null ? "Sin cobertura" : c.nombre}</option>)}</select>
      </Campo>
      <Pie><Boton type="submit" disabled={!completo}>Guardar y continuar</Boton></Pie>
    </form>
  </Pantalla>;
}
