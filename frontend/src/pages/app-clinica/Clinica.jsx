import { Link, useNavigate } from "react-router-dom";

import { CLINICA, cobertura, fechaConAnio } from "./datos";
import { useApp } from "./estado";
import { Avatar, Boton, Cabecera, Fila, MarcaClinica, ruta, Tarjeta } from "./ui";

export function Clinica() {
  const [turnos] = CLINICA.telefonos;
  return <>
    <Cabecera titulo="La clínica" />
    <div className="flex items-center gap-3"><MarcaClinica size={52} /><div><h2 className="text-lg font-bold">{CLINICA.nombre}</h2><p className="text-xs text-texto-suave">{CLINICA.direccion}</p></div></div>
    <a href={CLINICA.mapa} target="_blank" rel="noreferrer" aria-label="Ver la clínica en Google Maps" className="relative mt-5 block h-36 overflow-hidden rounded-lg border border-borde bg-[#E9F8FA] focus-visible:outline-2 focus-visible:outline-accent">
      <svg aria-hidden="true" className="absolute inset-0 size-full" preserveAspectRatio="xMidYMid slice" viewBox="0 0 400 144">
        <path d="M0 40h400M0 104h400M90 0v144M250 0v144" stroke="#fff" strokeWidth="14" />
        <path d="M0 144 400 10" stroke="#fff" strokeWidth="8" />
        <rect x="110" y="56" width="120" height="30" rx="4" fill="#CDEFE9" /><rect x="270" y="56" width="110" height="30" rx="4" fill="#DCE9F7" />
      </svg>
      <span className="absolute left-1/2 top-1/2 flex -translate-x-1/2 -translate-y-full flex-col items-center"><MarcaClinica size={30} /><span className="mt-1 size-2 rounded-full bg-[#7031C7]" /></span>
      <span className="absolute bottom-2 right-2 rounded-sm bg-superficie px-2 py-1 text-micro font-semibold text-accent shadow-card">Abrir en Google Maps</span>
    </a>
    <div className="mt-4 flex gap-2">
      <Boton variante="secundario" icono="map" href={CLINICA.mapa}>Cómo llegar</Boton>
      <Boton variante="secundario" href={`tel:${turnos.tel}`}>Llamar</Boton>
    </div>
    <h3 className="mt-6 text-sm font-bold">Horarios</h3>
    <Tarjeta className="mt-3 overflow-hidden">{CLINICA.horarios.map((h, i) => <Fila key={h.titulo} titulo={h.titulo} detalle={h.detalle} ultimo={i === CLINICA.horarios.length - 1} />)}</Tarjeta>
    <h3 className="mt-6 text-sm font-bold">Teléfonos</h3>
    <Tarjeta className="mt-3 overflow-hidden">{CLINICA.telefonos.map((t, i) => <Fila key={t.titulo} titulo={t.titulo} detalle={t.texto} href={`tel:${t.tel}`} ultimo={i === CLINICA.telefonos.length - 1} />)}</Tarjeta>
  </>;
}

function Interruptor({ titulo, detalle, activo, onCambiar, ultimo }) {
  return <div className={`flex items-center gap-3 px-4 py-3.5 ${ultimo ? "" : "border-b border-borde"}`}>
    <span className="min-w-0 flex-1"><strong className="block text-sm font-medium">{titulo}</strong><span className="mt-0.5 block text-xs text-texto-suave">{detalle}</span></span>
    <button type="button" role="switch" aria-checked={activo} aria-label={titulo} onClick={() => onCambiar(!activo)}
      className={`relative h-6 w-11 flex-none rounded-pill transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent ${activo ? "bg-accent-fuerte" : "bg-borde"}`}>
      <span className={`absolute left-0.5 top-0.5 size-5 rounded-full bg-white shadow-card transition-transform ${activo ? "translate-x-5" : "translate-x-0"}`} />
    </button>
  </div>;
}

export function Perfil() {
  const { paciente, preferencias, acciones } = useApp();
  const navigate = useNavigate();
  const c = cobertura(paciente.cobertura);
  const salir = () => { acciones.salir(); navigate(ruta(), { replace: true }); };
  return <>
    <Cabecera titulo="Mi perfil" />
    <div className="flex items-center gap-4"><Avatar nombre={paciente.nombre} size={60} /><div><h2 className="text-lg font-bold">{paciente.nombre}</h2><p className="text-xs text-texto-suave">Paciente de {CLINICA.nombre} desde {paciente.desde}</p></div></div>
    <h3 className="mt-6 text-sm font-bold">Mis datos</h3>
    <Tarjeta className="mt-3 overflow-hidden">
      <Fila titulo="DNI" detalle={Number(paciente.dni).toLocaleString("es-AR")} />
      <Fila titulo="Fecha de nacimiento" detalle={fechaConAnio(paciente.nacimiento)} />
      <Fila titulo="Celular" detalle={paciente.celular} ultimo />
    </Tarjeta>
    <h3 className="mt-6 text-sm font-bold">Cobertura</h3>
    <Tarjeta className="mt-3 overflow-hidden"><Fila icono="idCard" titulo={c.nombre} detalle={paciente.credencial ? `Credencial ${paciente.credencial}` : c.copago === null ? "Te atendés de forma particular" : "Sin número de credencial cargado"} ultimo /></Tarjeta>
    <h3 className="mt-6 text-sm font-bold">Avisos</h3>
    <Tarjeta className="mt-3 overflow-hidden">
      <Interruptor titulo="Recordatorio de turnos" detalle="2 horas antes, por notificación" activo={preferencias.recordatorios} onCambiar={(v) => acciones.preferencia("recordatorios", v)} />
      <Interruptor titulo="Resultados listos" detalle="Cuando la clínica carga un estudio" activo={preferencias.resultados} onCambiar={(v) => acciones.preferencia("resultados", v)} ultimo />
    </Tarjeta>
    <Tarjeta className="mt-4 overflow-hidden"><Fila icono="help" titulo="Ayuda y contacto" detalle="Teléfonos y horarios de la clínica" to={ruta("clinica")} ultimo /></Tarjeta>
    <div className="mt-6"><Boton variante="secundario" icono="enter" onClick={salir}>Cerrar sesión</Boton></div>
    <p className="mt-6 text-center text-xs text-texto-suave">App de pacientes de HEN, con datos ficticios: nada de lo que hagas acá llega a un sistema real. <Link to="/" className="font-semibold text-accent hover:underline">Conocé HEN</Link></p>
  </>;
}
