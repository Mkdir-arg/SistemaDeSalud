import { Link, Navigate, useNavigate, useParams, useSearchParams } from "react-router-dom";

import { Icon } from "@/components/icons";

import { aPagar, CLINICA, cobertura, fechaCorta, fechaLarga, hoy, pesos } from "./datos";
import { ACTIVOS, etapa, useAhora, useApp } from "./estado";
import { Boton, Cabecera, Fila, Insignia, Pie, ruta, Tarjeta } from "./ui";

export const GRADIENTE = "bg-gradient-to-tr from-[#7031C7] via-[#315BA0] to-[#007A70] text-white";

/** Descarga el turno como evento de calendario (.ics), con aviso 2 horas antes si se pidió. */
export function agregarAlCalendario(t) {
  const hora = t.hora.replace(":", "");
  const fin = (() => { const [h, m] = t.hora.split(":").map(Number); const total = h * 60 + m + 20; return `${String(Math.floor(total / 60) % 24).padStart(2, "0")}${String(total % 60).padStart(2, "0")}`; })();
  const dia = t.dia.replaceAll("-", "");
  const evento = [
    "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//HEN//App clinica//ES",
    "BEGIN:VEVENT", `UID:${t.id}@clinica-modelo.hen`,
    `DTSTAMP:${new Date().toISOString().replace(/[-:]/g, "").slice(0, 15)}Z`,
    `DTSTART:${dia}T${hora}00`, `DTEND:${dia}T${fin}00`,
    `SUMMARY:Turno de ${t.especialidad} · ${CLINICA.nombre}`,
    `LOCATION:${CLINICA.direccion.replaceAll(",", "\\,")}`,
    `DESCRIPTION:${t.profesional}. Consultorio ${t.consultorio}\\, planta baja. Turno de demostración de HEN: no es una reserva real.`,
    ...(t.recordatorio ? ["BEGIN:VALARM", "ACTION:DISPLAY", "DESCRIPTION:Turno en Clínica Modelo", "TRIGGER:-PT2H", "END:VALARM"] : []),
    "END:VEVENT", "END:VCALENDAR",
  ].join("\r\n");
  const url = URL.createObjectURL(new Blob([evento], { type: "text/calendar;charset=utf-8" }));
  const enlace = document.createElement("a");
  enlace.href = url;
  enlace.download = `turno-${t.especialidad.toLowerCase().replace(/\s+/g, "-")}-${t.dia}.ics`;
  enlace.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

const ETIQUETAS = {
  confirmado: ["Confirmado", "verde"], "en-fila": ["En la fila", "acento"], llamado: ["Te llaman", "acento"],
  "en-consulta": ["En consulta", "acento"], atendido: ["Atendido", "gris"], cancelado: ["Cancelado", "rojo"],
};
export function EstadoTurno({ turno, ahora }) {
  const e = etapa(turno, ahora);
  const [texto, tono] = ETIQUETAS[e.tipo];
  return <Insignia tono={tono}>{e.tipo === "en-fila" ? `${e.lugar}.º en la fila` : texto}</Insignia>;
}

/** Adónde lleva la acción principal de un turno según en qué etapa está. */
export function destinoTurno(turno, ahora) {
  const e = etapa(turno, ahora).tipo;
  if (e === "en-fila") return ruta(`turnos/${turno.id}/fila`);
  if (e === "llamado") return ruta(`turnos/${turno.id}/llamado`);
  return ruta(`turnos/${turno.id}`);
}

function ItemTurno({ turno, ahora }) {
  return <Link to={destinoTurno(turno, ahora)} className="mb-3 flex w-full items-center gap-3 rounded-lg border border-borde bg-superficie p-3 text-left hover:border-accent focus-visible:outline-2 focus-visible:outline-accent">
    <span className="flex w-16 flex-none flex-col items-center rounded-md bg-accent-50 py-1.5 text-xs text-accent">{turno.dia === hoy() ? "Hoy" : fechaCorta(turno.dia)}<strong className="text-lg leading-tight">{turno.hora}</strong></span>
    <span className="min-w-0 flex-1"><strong className="block text-sm">{turno.especialidad}</strong><span className="block truncate text-xs text-texto-suave">{turno.profesional} · consultorio {turno.consultorio}</span><span className="mt-1.5 block"><EstadoTurno turno={turno} ahora={ahora} /></span></span>
    <Icon name="chevronRight" size={16} className="text-texto-suave" />
  </Link>;
}

const orden = (a, b) => `${a.dia}${a.hora}`.localeCompare(`${b.dia}${b.hora}`);

export function MisTurnos() {
  const { turnos, acciones } = useApp();
  const [parametros] = useSearchParams();
  const anteriores = parametros.get("ver") === "anteriores";
  const ahora = useAhora(turnos.some((t) => t.estado === "presente"));
  const lista = anteriores ? turnos.filter((t) => !ACTIVOS.has(t.estado)).sort(orden).reverse() : turnos.filter((t) => ACTIVOS.has(t.estado)).sort(orden);
  const pestana = (activa) => `flex-1 rounded-sm py-2 text-center text-xs font-semibold ${activa ? "bg-superficie text-texto shadow-card" : "text-texto-suave"}`;
  return <>
    <Cabecera titulo="Mis turnos" />
    <div role="tablist" className="mb-5 flex rounded-md bg-accent-50 p-1">
      <Link role="tab" aria-selected={!anteriores} to={ruta("turnos")} replace className={pestana(!anteriores)}>Próximos</Link>
      <Link role="tab" aria-selected={anteriores} to={`${ruta("turnos")}?ver=anteriores`} replace className={pestana(anteriores)}>Anteriores</Link>
    </div>
    {lista.map((t) => <ItemTurno key={t.id} turno={t} ahora={ahora} />)}
    {lista.length === 0 && <Tarjeta className="p-5 text-center text-sm text-texto-suave">{anteriores ? "Todavía no tenés turnos anteriores en la clínica." : "No tenés turnos próximos."}</Tarjeta>}
    {!anteriores && <Pie><Boton to={ruta("sacar-turno")} onClick={() => acciones.empezarTurno()} icono="plus">Sacar un turno</Boton></Pie>}
  </>;
}

export function DetalleTurno() {
  const { id } = useParams();
  const { turnos, paciente, acciones } = useApp();
  const ahora = useAhora(turnos.some((t) => t.id === id && t.estado === "presente"));
  const t = turnos.find((x) => x.id === id);
  if (!t) return <Navigate to={ruta("turnos")} replace />;
  const e = etapa(t, ahora).tipo;
  const activo = ACTIVOS.has(t.estado);
  const pago = aPagar(paciente.cobertura);
  const reprogramar = () => acciones.empezarTurno({ reprograma: t.id, especialidad: t.especialidad, profesionalId: t.profesionalId });
  return <>
    <Cabecera titulo="Tu turno" atras={ruta(activo ? "turnos" : "turnos?ver=anteriores")} />
    <div className={`rounded-lg p-5 ${activo ? GRADIENTE : "border border-borde bg-superficie"}`}>
      <p className={`text-xs ${activo ? "text-white/85" : "text-texto-suave"}`}>{fechaLarga(t.dia)}</p>
      <h2 className="mt-1 text-xl font-bold">{t.hora} · {t.especialidad}</h2>
      <p className={`mt-1 text-sm ${activo ? "text-white/90" : "text-texto-medio"}`}>{t.profesional} · consultorio {t.consultorio}, planta baja</p>
      {!activo && <p className="mt-3"><EstadoTurno turno={t} ahora={ahora} /></p>}
    </div>
    <Tarjeta className="mt-4 overflow-hidden">
      <Fila icono="wallet" titulo={cobertura(paciente.cobertura).nombre} detalle={pago.monto ? `A pagar en la clínica: ${pesos(pago.monto)}` : "Sin cargo"} />
      <Fila icono="idCard" titulo="Qué llevar" detalle="DNI, credencial de la cobertura y estudios anteriores" />
      <Fila icono="map" titulo="Cómo llegar" detalle={CLINICA.direccion} href={CLINICA.mapa} />
      {activo && <Fila icono="bell" titulo="Recordatorio" detalle={t.recordatorio ? "Te avisamos 2 horas antes" : "Sin recordatorio"} ultimo />}
    </Tarjeta>
    <Pie>
      {e === "confirmado" && t.dia === hoy() && <Boton to={ruta(`turnos/${t.id}/llegada`)}>Dar presente</Boton>}
      {(e === "en-fila" || e === "llamado") && <Boton to={destinoTurno(t, ahora)}>Ver mi lugar en la fila</Boton>}
      {e === "confirmado" && <>
        <Boton variante="secundario" icono="calendar" onClick={() => agregarAlCalendario(t)}>Agregar al calendario</Boton>
        <Boton variante="secundario" to={ruta("sacar-turno/horario")} onClick={reprogramar}>Cambiar día u horario</Boton>
      </>}
      {activo && e !== "en-consulta" && <Boton variante="texto" to={ruta(`turnos/${t.id}/cancelar`)}>{e === "confirmado" ? "Cancelar turno" : "No voy a poder quedarme"}</Boton>}
      {!activo && <Boton to={ruta("sacar-turno/horario")} onClick={() => acciones.empezarTurno({ especialidad: t.especialidad, profesionalId: t.profesionalId })}>Sacar otro turno con {t.profesional}</Boton>}
    </Pie>
  </>;
}

export function CancelarTurno() {
  const { id } = useParams();
  const { turnos, acciones, avisar } = useApp();
  const navigate = useNavigate();
  const t = turnos.find((x) => x.id === id);
  if (!t || !ACTIVOS.has(t.estado)) return <Navigate to={ruta("turnos")} replace />;
  const enFila = t.estado === "presente";
  const confirmar = () => { acciones.cancelar(t.id); avisar(enFila ? "Liberaste tu lugar en la fila." : "Cancelaste tu turno."); navigate(ruta("turnos"), { replace: true }); };
  return <>
    <DetalleTurno />
    <div className="fixed inset-0 z-40 flex items-end justify-center bg-[#1D1930]/50 md:items-center md:p-4">
      <div role="dialog" aria-modal="true" aria-labelledby="titulo-cancelar" className="w-full max-w-md rounded-t-[24px] bg-superficie p-6 shadow-modal md:rounded-lg">
        <h2 id="titulo-cancelar" className="text-lg font-bold">{enFila ? "¿Liberar tu lugar en la fila?" : `¿Cancelar tu turno de ${t.especialidad}?`}</h2>
        <p className="mt-3 text-sm text-texto-suave">{fechaLarga(t.dia)}, {t.hora} con {t.profesional}. {enFila ? "Le avisamos a la recepción y pasa la siguiente persona." : "El horario queda libre para otra persona."}</p>
        <div className="mt-6 space-y-2">
          <Boton variante="peligro" onClick={confirmar}>{enFila ? "Sí, liberar mi lugar" : "Sí, cancelar turno"}</Boton>
          <Boton variante="texto" to={enFila ? ruta(`turnos/${t.id}/fila`) : ruta(`turnos/${t.id}`)} replace>{enFila ? "Me quedo" : "Mantener turno"}</Boton>
        </div>
      </div>
    </div>
  </>;
}

export function TurnoConfirmado() {
  const { id } = useParams();
  const [parametros] = useSearchParams();
  const { turnos } = useApp();
  const t = turnos.find((x) => x.id === id);
  if (!t) return <Navigate to={ruta("turnos")} replace />;
  const cambio = parametros.has("cambio");
  return <div className="flex flex-1 flex-col items-center justify-center py-8 text-center">
    <span className="flex size-20 items-center justify-center rounded-full bg-badge-green-bg text-badge-green-fg"><svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M5 12.5 10 17 19 7" /></svg></span>
    <h1 className="mt-5 text-xl font-bold">{cambio ? "Listo, cambiamos tu turno" : "¡Listo! Tu turno quedó confirmado"}</h1>
    <p className="mt-3 max-w-xs text-sm text-texto-suave">{fechaLarga(t.dia)} a las {t.hora} con {t.profesional}, consultorio {t.consultorio}. {t.recordatorio ? "Te recordamos 2 horas antes." : ""}</p>
    <div className="mt-8 w-full space-y-3">
      <Boton variante="secundario" icono="calendar" onClick={() => agregarAlCalendario(t)}>Agregar al calendario</Boton>
      <Boton to={ruta("inicio")} replace>Volver al inicio</Boton>
      <Boton variante="texto" to={ruta(`turnos/${t.id}`)} replace>Ver el turno</Boton>
    </div>
  </div>;
}
