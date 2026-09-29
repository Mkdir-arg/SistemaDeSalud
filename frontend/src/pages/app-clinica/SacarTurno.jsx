import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";

import { aPagar, cobertura, diaSemana, diasDisponibles, ESPECIALIDADES, fechaCorta, fechaLarga, horariosLibres, hoy, numeroDia, pesos, profesional, profesionalesDe, PROFESIONALES } from "./datos";
import { useApp } from "./estado";
import { Boton, Cabecera, CLASE_CAMPO, Fila, Paso, Pie, ruta, Tarjeta } from "./ui";

const normalizar = (s) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

export function Especialidad() {
  const { turnos, borrador, acciones } = useApp();
  const [busqueda, setBusqueda] = useState("");
  const q = normalizar(busqueda.trim());
  // "Volver con": profesionales con quienes ya se atendió, el más reciente primero.
  const recientes = [...turnos].filter((t) => t.estado === "atendido").sort((a, b) => b.dia.localeCompare(a.dia))
    .filter((t, i, lista) => lista.findIndex((x) => x.profesionalId === t.profesionalId) === i);
  const conservar = borrador?.reprograma ? { reprograma: borrador.reprograma } : {};
  const especialidades = ESPECIALIDADES.filter((e) => normalizar(e).includes(q));
  const profesionales = q ? PROFESIONALES.filter((p) => normalizar(p.nombre).includes(q)) : [];
  return <>
    <Cabecera titulo="Sacar turno" atras={ruta("inicio")} />
    <Paso numero={1} />
    <h2 className="mt-5 text-xl font-bold">¿Con qué especialidad?</h2>
    <input type="search" value={busqueda} onChange={(e) => setBusqueda(e.target.value)} aria-label="Buscar especialidad o profesional" placeholder="Buscá especialidad o profesional" className={`${CLASE_CAMPO} mt-4`} />
    {!q && recientes.length > 0 && <>
      <h3 className="mt-6 text-sm font-bold">Volver con</h3>
      <Tarjeta className="mt-3 overflow-hidden">{recientes.map((t, i) => <Fila key={t.profesionalId} titulo={t.profesional} detalle={`${t.especialidad} · última vez ${fechaCorta(t.dia)}`} to={ruta("sacar-turno/horario")} onClick={() => acciones.empezarTurno({ ...conservar, especialidad: t.especialidad, profesionalId: t.profesionalId })} ultimo={i === recientes.length - 1} />)}</Tarjeta>
    </>}
    {profesionales.length > 0 && <>
      <h3 className="mt-6 text-sm font-bold">Profesionales</h3>
      <Tarjeta className="mt-3 overflow-hidden">{profesionales.map((p, i) => <Fila key={p.id} titulo={p.nombre} detalle={p.especialidad} to={ruta("sacar-turno/horario")} onClick={() => acciones.empezarTurno({ ...conservar, especialidad: p.especialidad, profesionalId: p.id })} ultimo={i === profesionales.length - 1} />)}</Tarjeta>
    </>}
    {especialidades.length > 0 && <>
      <h3 className="mt-6 text-sm font-bold">Especialidades de la clínica</h3>
      <Tarjeta className="mt-3 overflow-hidden">{especialidades.map((e, i) => <Fila key={e} titulo={e} detalle={`${profesionalesDe(e).length} profesionales`} to={ruta("sacar-turno/horario")} onClick={() => acciones.empezarTurno({ ...conservar, especialidad: e })} ultimo={i === especialidades.length - 1} />)}</Tarjeta>
    </>}
    {q && !especialidades.length && !profesionales.length && <p className="mt-6 text-sm text-texto-suave">No encontramos «{busqueda}». Probá con otra especialidad o el apellido del profesional.</p>}
  </>;
}

export function Horario() {
  const { borrador, acciones } = useApp();
  const navigate = useNavigate();
  if (!borrador?.especialidad) return <Navigate to={ruta("sacar-turno")} replace />;
  const dias = diasDisponibles();
  // El profesional elegido va primero; el resto de la especialidad, como alternativa.
  const lista = profesionalesDe(borrador.especialidad).sort((a, b) => (b.id === borrador.profesionalId) - (a.id === borrador.profesionalId));
  const hayHorarios = (dia) => lista.some((p) => horariosLibres(p.id, dia).length);
  const dia = borrador.dia || dias.find(hayHorarios) || dias[0];
  const atras = borrador.reprograma ? ruta(`turnos/${borrador.reprograma}`) : ruta("sacar-turno");
  const elegido = borrador.dia === dia && borrador.hora;
  return <>
    <Cabecera titulo={borrador.reprograma ? "Cambiar turno" : borrador.especialidad} atras={atras} />
    <Paso numero={2} />
    <h2 className="mt-5 text-xl font-bold">Elegí día y horario</h2>
    <div role="radiogroup" aria-label="Día" className="mt-4 grid grid-cols-6 gap-1.5">
      {dias.map((d) => <button type="button" role="radio" key={d} aria-checked={d === dia} aria-label={fechaLarga(d)} disabled={!hayHorarios(d)} onClick={() => acciones.elegir({ dia: d, hora: null })}
        className={`flex h-16 flex-col items-center justify-center rounded-md border text-micro font-semibold disabled:opacity-40 ${d === dia ? "border-accent bg-accent-fuerte text-white" : "border-borde bg-superficie hover:border-accent"}`}>
        {d === hoy() ? "HOY" : diaSemana(d)}<strong className="text-lg">{numeroDia(d)}</strong>
      </button>)}
    </div>
    {lista.map((p) => {
      const horas = horariosLibres(p.id, dia);
      return <Tarjeta key={p.id} className="mt-4 p-4">
        <h3 className="text-sm font-semibold">{p.nombre}</h3>
        <p className="text-xs text-texto-suave">Consultorio {p.consultorio}</p>
        {horas.length ? <div className="mt-3 flex flex-wrap gap-2">{horas.map((hora) => {
          const activa = elegido && borrador.hora === hora && borrador.profesionalId === p.id;
          return <button type="button" key={hora} aria-pressed={activa} onClick={() => acciones.elegir({ dia, hora, profesionalId: p.id })}
            className={`rounded-pill border px-3.5 py-2 text-xs font-semibold ${activa ? "border-accent bg-accent-fuerte text-white" : "border-borde hover:border-accent"}`}>{hora}</button>;
        })}</div> : <p className="mt-3 text-xs text-texto-suave">Sin horarios libres este día.</p>}
      </Tarjeta>;
    })}
    <Pie><Boton disabled={!elegido} onClick={() => navigate(ruta("sacar-turno/confirmar"))}>{elegido ? `Continuar con ${fechaLarga(dia).toLowerCase()} a las ${borrador.hora}` : "Elegí un horario"}</Boton></Pie>
  </>;
}

export function Confirmar() {
  const { borrador, paciente, acciones } = useApp();
  const navigate = useNavigate();
  if (!borrador?.hora) return <Navigate to={ruta("sacar-turno/horario")} replace />;
  const p = profesional(borrador.profesionalId);
  const pago = aPagar(paciente.cobertura);
  const confirmar = () => {
    const cambio = Boolean(borrador.reprograma);
    const id = acciones.reservar();
    navigate(ruta(`turnos/${id}/confirmado${cambio ? "?cambio" : ""}`), { replace: true });
  };
  return <>
    <Cabecera titulo={borrador.reprograma ? "Confirmá el cambio" : "Confirmá tu turno"} atras={ruta("sacar-turno/horario")} />
    <Paso numero={3} />
    <Tarjeta className="mt-5 space-y-4 p-4">
      {[["Cuándo", `${fechaLarga(borrador.dia)} · ${borrador.hora}`], ["Con quién", `${p.nombre} · ${p.especialidad}`], ["Dónde", `Consultorio ${p.consultorio}, planta baja`], ["Cobertura", cobertura(paciente.cobertura).nombre]]
        .map(([k, v]) => <div key={k}><p className="text-xs text-texto-suave">{k}</p><strong className="mt-0.5 block text-sm">{v}</strong></div>)}
    </Tarjeta>
    <div className="mt-4 flex items-center justify-between gap-3 rounded-md border border-accent-100 bg-accent-50 p-4">
      <span><span className="block text-xs text-texto-suave">A pagar en la clínica</span><span className="text-xs text-texto-medio">{pago.detalle}</span></span>
      <strong className="text-lg text-accent">{pago.monto ? pesos(pago.monto) : "Sin cargo"}</strong>
    </div>
    <label className="mt-5 flex items-center gap-3 text-sm"><input type="checkbox" className="size-4 accent-[#7031C7]" checked={borrador.recordatorio !== false} onChange={(e) => acciones.elegir({ recordatorio: e.target.checked })} /> Recordarme 2 horas antes</label>
    <Pie><Boton onClick={confirmar}>{borrador.reprograma ? "Confirmar cambio" : "Confirmar turno"}</Boton></Pie>
  </>;
}
