import { useEffect, useState } from "react";
import { Navigate, useParams } from "react-router-dom";

import { Icon } from "@/components/icons";

import { fechaConAnio, fechaCorta, fechaLarga, PROFESIONALES } from "./datos";
import { ACTIVOS, useApp } from "./estado";
import { Boton, Cabecera, Fila, Insignia, Pie, ruta, Tarjeta } from "./ui";

function EstadoResultado({ r }) {
  if (r.estado !== "listo") return <Insignia tono="ambar">En proceso</Insignia>;
  return r.nuevo ? <Insignia>Nuevo</Insignia> : <Insignia tono="verde">Listo</Insignia>;
}

export function Resultados() {
  const { resultados, preferencias } = useApp();
  const lista = [...resultados].sort((a, b) => b.dia.localeCompare(a.dia));
  return <>
    <Cabecera titulo="Resultados" />
    {lista.length ? <Tarjeta className="overflow-hidden">
      {lista.map((r, i) => <Fila key={r.id} icono={r.valores ? "flask" : "fileText"} titulo={r.titulo} detalle={`${r.area} · ${fechaCorta(r.dia)}`} insignia={<EstadoResultado r={r} />} to={ruta(`resultados/${r.id}`)} ultimo={i === lista.length - 1} />)}
    </Tarjeta> : <Tarjeta className="p-5 text-center text-sm text-texto-suave">Todavía no tenés estudios en la clínica.</Tarjeta>}
    <p className="mt-5 text-xs text-texto-suave">{preferencias.resultados ? "Te avisamos con una notificación cuando un resultado esté listo." : "Tenés desactivados los avisos de resultados. Podés activarlos desde tu perfil."}</p>
  </>;
}

export function DetalleResultado() {
  const { id } = useParams();
  const { resultados, turnos, paciente, acciones, avisar } = useApp();
  const [descargando, setDescargando] = useState(false);
  const r = resultados.find((x) => x.id === id);
  useEffect(() => { if (r?.nuevo) acciones.verResultado(r.id); }, [r, acciones]);
  if (!r) return <Navigate to={ruta("resultados")} replace />;

  const medico = PROFESIONALES.find((p) => p.nombre === r.pedidoPor);
  const turnoConMedico = turnos.find((t) => t.profesionalId === medico?.id && ACTIVOS.has(t.estado));
  const descargar = async () => {
    setDescargando(true);
    try {
      const { descargarInforme } = await import("./informePdf");
      descargarInforme(r, paciente);
      avisar("Descargaste el informe en PDF.");
    } catch {
      avisar("No pudimos generar el PDF. Probá de nuevo.");
    } finally {
      setDescargando(false);
    }
  };

  return <>
    <Cabecera titulo={r.titulo} atras={ruta("resultados")} />
    <p className="-mt-3 mb-4 text-xs text-texto-suave">{r.area} · {fechaConAnio(r.dia)} · pedido por {r.pedidoPor}</p>
    {r.estado !== "listo" ? <Tarjeta className="flex flex-col items-center p-6 text-center">
      <span className="flex size-12 items-center justify-center rounded-full bg-badge-amber-bg text-badge-amber-fg"><Icon name="reloj" size={24} /></span>
      <h2 className="mt-4 text-base font-bold">Todavía lo estamos procesando</h2>
      <p className="mt-2 text-sm text-texto-suave">Suele estar listo en 3 a 5 días hábiles. Te avisamos con una notificación en cuanto puedas verlo.</p>
    </Tarjeta> : <>
      {r.aviso && <p className="flex gap-2 rounded-md border border-badge-amber-fg/30 bg-badge-amber-bg p-3 text-xs text-badge-amber-fg"><Icon name="alert" size={16} />{r.aviso}</p>}
      {r.valores && <Tarjeta className="mt-4 overflow-hidden">
        {r.valores.map((v, i) => <div key={v.nombre} className={`flex items-center justify-between gap-3 p-4 ${i < r.valores.length - 1 ? "border-b border-borde" : ""}`}>
          <span><strong className="block text-sm font-medium">{v.nombre}</strong><span className="text-xs text-texto-suave">Referencia: {v.referencia}</span></span>
          <span className="text-right"><strong className={`block text-sm ${v.fuera ? "text-danger" : ""}`}>{v.valor}</strong>{v.fuera && <span className="text-micro font-semibold text-danger">Fuera de rango</span>}</span>
        </div>)}
      </Tarjeta>}
      {r.informe && <Tarjeta className="p-4"><h2 className="text-xs font-semibold text-texto-suave">Informe</h2><p className="mt-2 text-sm leading-relaxed">{r.informe}</p></Tarjeta>}
    </>}
    <Pie>
      {r.estado === "listo" && <Boton variante="secundario" icono="download" onClick={descargar} disabled={descargando}>{descargando ? "Generando PDF…" : "Descargar informe (PDF)"}</Boton>}
      {medico && (turnoConMedico
        ? <Boton to={ruta(`turnos/${turnoConMedico.id}`)}>Ver tu turno con {medico.nombre} · {fechaLarga(turnoConMedico.dia).toLowerCase()} {turnoConMedico.hora}</Boton>
        : <Boton to={ruta("sacar-turno/horario")} onClick={() => acciones.empezarTurno({ especialidad: medico.especialidad, profesionalId: medico.id })}>Sacar turno con {medico.nombre}</Boton>)}
    </Pie>
  </>;
}
