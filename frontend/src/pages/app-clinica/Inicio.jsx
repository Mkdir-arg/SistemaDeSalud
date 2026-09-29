import { CLINICA, fechaLarga, hoy } from "./datos";
import { etapa, proximoTurno, useAhora, useApp } from "./estado";
import { destinoTurno, GRADIENTE } from "./Turnos";
import { Boton, Fila, Insignia, primerNombre, ruta, Tarjeta } from "./ui";

function TarjetaTurno({ turno, ahora }) {
  const e = etapa(turno, ahora);
  const esHoy = turno.dia === hoy();
  const lugar = `Consultorio ${turno.consultorio}, planta baja`;
  const textos = {
    confirmado: [esHoy ? "Tu turno de hoy" : `Tu próximo turno · ${fechaLarga(turno.dia)}`, `${turno.hora} · ${turno.especialidad}`, `${turno.profesional} · ${lugar}`],
    "en-fila": ["Diste presente", `Sos ${e.lugar}.º en la fila`, `Te atienden en unos ${e.lugar * 5} minutos · ${lugar}`],
    llamado: ["Te están llamando", `Consultorio ${turno.consultorio}`, `${turno.profesional} te espera en planta baja`],
    "en-consulta": ["En consulta", `${turno.hora} · ${turno.especialidad}`, `${turno.profesional} · ${lugar}`],
  }[e.tipo];
  return <section aria-label="Próximo turno" className={`rounded-lg p-5 ${GRADIENTE}`}>
    <p className="text-xs text-white/85">{textos[0]}</p>
    <h2 className="mt-1.5 text-xl font-bold">{textos[1]}</h2>
    <p className="mt-1 text-sm text-white/90">{textos[2]}</p>
    <div className="mt-4 flex gap-2">
      {e.tipo === "confirmado" && esHoy && <Boton variante="claro" to={ruta(`turnos/${turno.id}/llegada`)}>Dar presente</Boton>}
      {e.tipo === "confirmado" && !esHoy && <Boton variante="claro" to={ruta(`turnos/${turno.id}`)}>Ver turno</Boton>}
      {(e.tipo === "en-fila" || e.tipo === "llamado") && <Boton variante="claro" to={destinoTurno(turno, ahora)}>{e.tipo === "llamado" ? "Ver llamado" : "Ver mi lugar"}</Boton>}
      {e.tipo === "en-consulta" && <Boton variante="claro" to={ruta(`turnos/${turno.id}`)}>Ver turno</Boton>}
      {e.tipo === "confirmado" && <Boton variante="claro" href={CLINICA.mapa} icono="map">Cómo llegar</Boton>}
    </div>
    {e.tipo === "confirmado" && <p className="mt-3 text-xs text-white/85">{esHoy ? "Al llegar, avisá desde acá y te sumamos a la fila sin pasar por recepción." : "El día del turno vas a poder avisar que llegaste desde acá."}</p>}
  </section>;
}

export default function Inicio() {
  const { paciente, turnos, resultados, acciones } = useApp();
  const proximo = proximoTurno(turnos);
  const ahora = useAhora(proximo?.estado === "presente");
  const activos = turnos.filter((t) => ["confirmado", "presente"].includes(t.estado)).length;
  const nuevos = resultados.filter((r) => r.nuevo && r.estado === "listo");
  const hoyTexto = new Date().toLocaleDateString("es-AR", { weekday: "long", day: "numeric", month: "long" });
  return <>
    <div className="mb-5">
      <p className="text-xs text-texto-suave first-letter:uppercase">{hoyTexto}</p>
      <h1 className="text-xxl font-bold">Hola, {primerNombre(paciente.nombre)}</h1>
    </div>
    {proximo ? <TarjetaTurno turno={proximo} ahora={ahora} /> : <section className={`rounded-lg p-5 ${GRADIENTE}`}>
      <h2 className="text-lg font-bold">¿Necesitás atenderte?</h2>
      <p className="mt-2 text-sm text-white/90">Elegí especialidad, día y horario. Te mostramos cuánto vas a pagar antes de confirmar.</p>
      <div className="mt-4"><Boton variante="claro" to={ruta("sacar-turno")} onClick={() => acciones.empezarTurno()}>Sacar turno</Boton></div>
    </section>}
    {proximo && <div className="mt-3"><Boton variante="secundario" icono="plus" to={ruta("sacar-turno")} onClick={() => acciones.empezarTurno()}>Sacar otro turno</Boton></div>}
    {nuevos.length > 0 && <Tarjeta className="mt-4 overflow-hidden border-accent-100"><Fila icono="flask" titulo={`Ya está listo: ${nuevos[0].titulo.toLowerCase()}`} detalle={`${nuevos[0].area} · pedido por ${nuevos[0].pedidoPor}`} insignia={<Insignia>Nuevo</Insignia>} to={ruta(`resultados/${nuevos[0].id}`)} ultimo /></Tarjeta>}
    <Tarjeta className="mt-4 overflow-hidden">
      <Fila icono="calendar" titulo="Mis turnos" detalle={activos ? `${activos} ${activos === 1 ? "próximo" : "próximos"}` : "Sin turnos próximos"} to={ruta("turnos")} />
      <Fila icono="flask" titulo="Resultados" detalle={resultados.length ? `${resultados.length} estudios` : "Todavía no tenés estudios"} insignia={nuevos.length > 0 && <Insignia>{nuevos.length} {nuevos.length === 1 ? "nuevo" : "nuevos"}</Insignia>} to={ruta("resultados")} />
      <Fila icono="building" titulo="La clínica" detalle="Dirección, horarios y teléfonos" to={ruta("clinica")} ultimo />
    </Tarjeta>
  </>;
}
