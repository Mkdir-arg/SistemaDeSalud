import { useEffect, useState } from "react";
import { Link, Navigate, Outlet, useNavigate } from "react-router-dom";

import { CLINICA, COBERTURAS, pacienteConocida } from "./datos";
import { useApp } from "./estado";
import { Aviso } from "./Shell";
import { Boton, Cabecera, Campo, CLASE_CAMPO, MarcaClinica, Pie, ruta } from "./ui";

const ILUSTRACION = "/demo-clinica-bienvenida.png";

/** Marco del ingreso: en escritorio, la ilustración a la izquierda y el paso a la derecha. */
export function MarcoIngreso() {
  const { paciente } = useApp();
  if (paciente) return <Navigate to={ruta("inicio")} replace />;
  return <div className="flex min-h-dvh bg-fondo text-texto">
    <aside className="hidden flex-1 flex-col justify-between bg-gradient-to-tr from-[#7031C7] via-[#315BA0] to-[#007A70] p-10 text-white md:flex">
      <span className="flex items-center gap-3 text-sm font-bold"><span className="rounded-[12px] bg-white/15 p-1"><MarcaClinica size={34} /></span>{CLINICA.nombre}</span>
      <img src={ILUSTRACION} alt="" className="mx-auto w-full max-w-[28rem] rounded-[28px] shadow-modal" />
      <p className="max-w-[28rem] text-sm text-white/85">Tus turnos, tu lugar en la fila y tus resultados, en un solo lugar.</p>
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

export function Bienvenida() {
  return <>
    <img src={ILUSTRACION} alt="Ilustración de la clínica con un turno confirmado" className="w-full flex-none md:hidden" />
    <div className="flex flex-1 flex-col px-6 pb-6 pt-6 md:px-0 md:pt-0">
      <p className="flex items-center gap-2 text-xs font-bold tracking-[.15em] text-accent"><span className="md:hidden"><MarcaClinica size={22} /></span>CLÍNICA MODELO</p>
      <h1 className="mt-3 text-xxl font-bold leading-tight">¡Qué bueno verte! Te damos la bienvenida</h1>
      <p className="mt-3 text-sm leading-relaxed text-texto-suave">Sacá turno, avisá que llegaste sin hacer fila y mirá tus resultados. Estamos para cuidarte.</p>
      <Pie>
        <Boton to={ruta("ingresar")}>Ingresar con mi DNI</Boton>
        <p className="text-center text-xs text-texto-suave">¿Es tu primera vez? También empezás con tu DNI.</p>
        <p className="pt-4 text-center text-micro text-texto-suave">Demo de HEN con datos ficticios · <Link to="/" className="font-semibold text-accent hover:underline">Conocé HEN</Link></p>
      </Pie>
    </div>
  </>;
}

export function Dni() {
  const { ingreso, acciones } = useApp();
  const [dni, setDni] = useState(ingreso?.dni || "");
  const navigate = useNavigate();
  const continuar = (e) => {
    e.preventDefault();
    if (dni.length < 7) return;
    acciones.empezarIngreso(dni);
    navigate(ruta(dni === pacienteConocida().dni ? "ingresar/codigo" : "ingresar/datos"));
  };
  return <Pantalla><Cabecera titulo="Ingresar" atras={ruta()} />
    <form onSubmit={continuar} className="flex flex-1 flex-col">
      <h2 className="text-xl font-bold">¿Cuál es tu DNI?</h2>
      <p className="mt-2 text-sm text-texto-suave">Con tu DNI buscamos si ya te atendiste en la clínica.</p>
      <Campo etiqueta="Número de documento">
        <input autoFocus inputMode="numeric" autoComplete="off" value={dni} onChange={(e) => setDni(e.target.value.replace(/\D/g, "").slice(0, 8))} placeholder="Ej.: 34521521" className={`${CLASE_CAMPO} text-base tracking-wider`} />
      </Campo>
      <Pie><Boton type="submit" disabled={dni.length < 7}>Continuar</Boton></Pie>
    </form>
  </Pantalla>;
}

export function Datos() {
  const { ingreso, acciones } = useApp();
  const navigate = useNavigate();
  const [datos, setDatos] = useState(ingreso?.datos || { nombre: "", nacimiento: "", celular: "", cobertura: "particular", credencial: "" });
  if (!ingreso) return <Navigate to={ruta("ingresar")} replace />;
  if (ingreso.conocida) return <Navigate to={ruta("ingresar/codigo")} replace />;
  const cambiar = (clave) => (e) => setDatos((d) => ({ ...d, [clave]: e.target.value }));
  const completo = datos.nombre.trim().length > 2 && datos.nacimiento && datos.celular.replace(/\D/g, "").length >= 8;
  const continuar = (e) => { e.preventDefault(); if (!completo) return; acciones.guardarDatos(datos); navigate(ruta("ingresar/codigo")); };
  return <Pantalla><Cabecera titulo="Tus datos" atras={ruta("ingresar")} />
    <form onSubmit={continuar} className="flex flex-1 flex-col">
      <h2 className="text-xl font-bold">Es tu primera vez en la clínica</h2>
      <p className="mt-2 text-sm text-texto-suave">Completá estos datos una sola vez. DNI {Number(ingreso.dni).toLocaleString("es-AR")}.</p>
      <Campo etiqueta="Nombre y apellido"><input autoFocus autoComplete="name" value={datos.nombre} onChange={cambiar("nombre")} className={CLASE_CAMPO} /></Campo>
      <Campo etiqueta="Fecha de nacimiento"><input type="date" autoComplete="bday" max={new Date().toISOString().slice(0, 10)} value={datos.nacimiento} onChange={cambiar("nacimiento")} className={CLASE_CAMPO} /></Campo>
      <Campo etiqueta="Celular" ayuda="Te mandamos un código por SMS para confirmar que es tuyo."><input inputMode="tel" autoComplete="tel" value={datos.celular} onChange={cambiar("celular")} placeholder="11 5555-4521" className={CLASE_CAMPO} /></Campo>
      <Campo etiqueta="Cobertura" ayuda="Con tu obra social o prepaga te mostramos cuánto pagás antes de confirmar un turno.">
        <select value={datos.cobertura} onChange={cambiar("cobertura")} className={CLASE_CAMPO}>{COBERTURAS.map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}</select>
      </Campo>
      {datos.cobertura !== "particular" && <Campo etiqueta="Número de credencial (opcional)"><input inputMode="numeric" value={datos.credencial} onChange={cambiar("credencial")} className={CLASE_CAMPO} /></Campo>}
      <Pie><Boton type="submit" disabled={!completo}>Continuar</Boton></Pie>
    </form>
  </Pantalla>;
}

const ESPERA_REENVIO = 30;

export function Codigo() {
  const { ingreso, acciones, avisar } = useApp();
  const navigate = useNavigate();
  const [codigo, setCodigo] = useState("");
  const [espera, setEspera] = useState(ESPERA_REENVIO);
  useEffect(() => {
    if (espera <= 0) return undefined;
    const id = setTimeout(() => setEspera((s) => s - 1), 1000);
    return () => clearTimeout(id);
  }, [espera]);
  if (!ingreso) return <Navigate to={ruta("ingresar")} replace />;
  if (!ingreso.conocida && !ingreso.datos) return <Navigate to={ruta("ingresar/datos")} replace />;
  const celular = ingreso.conocida ? pacienteConocida().celular : ingreso.datos.celular;
  const continuar = (e) => { e.preventDefault(); if (codigo.length !== 4) return; acciones.confirmarCodigo(); navigate(ruta("inicio"), { replace: true }); };
  const reenviar = () => { setEspera(ESPERA_REENVIO); setCodigo(""); avisar(`Te enviamos un código nuevo al celular terminado en ${celular.replace(/\D/g, "").slice(-2)}.`); };
  return <Pantalla><Cabecera titulo="Ingresar" atras={ruta(ingreso.conocida ? "ingresar" : "ingresar/datos")} />
    <form onSubmit={continuar} className="flex flex-1 flex-col">
      <h2 className="text-xl font-bold">{ingreso.conocida ? "¡Hola de nuevo!" : "Confirmá tu celular"}</h2>
      <p className="mt-2 text-sm text-texto-suave">Te enviamos un SMS con un código de 4 dígitos al celular terminado en <strong className="text-texto">{celular.replace(/\D/g, "").slice(-2)}</strong>.</p>
      <Campo etiqueta="Código">
        <input autoFocus inputMode="numeric" autoComplete="one-time-code" aria-label="Código de 4 dígitos" value={codigo} onChange={(e) => setCodigo(e.target.value.replace(/\D/g, "").slice(0, 4))} placeholder="••••" className={`${CLASE_CAMPO} h-12 text-center text-lg font-bold tracking-[.5em]`} />
      </Campo>
      <p className="mt-4 text-xs text-texto-suave">
        {espera > 0 ? <>¿No te llegó? Podés pedir otro en 0:{String(espera).padStart(2, "0")}.</> : <button type="button" onClick={reenviar} className="font-semibold text-accent hover:underline">Reenviar código</button>}
      </p>
      <p className="mt-2 text-xs text-texto-suave">¿Cambiaste de número? Llamá a la clínica al <a href={`tel:${CLINICA.telefonos[0].tel}`} className="font-semibold text-accent hover:underline">{CLINICA.telefonos[0].texto}</a>.</p>
      <Pie><Boton type="submit" disabled={codigo.length !== 4}>Ingresar</Boton></Pie>
    </form>
  </Pantalla>;
}
