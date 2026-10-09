import { useCallback, useEffect, useRef, useState } from "react";
import { Link, Navigate, useLocation, useNavigate, useParams, useSearchParams } from "react-router-dom";

import { Icon } from "@/components/icons";
import { mensajePortal, useAccionTurno, useTurnosPortal } from "@/api/portal";

import { Alerta, Consulta, Exito, Vacio } from "./comun";
import { agregarAlCalendario, diaDeLaCaja, esHoy, esProximo, estadoTurno, fechaLarga, hora, quienYDonde, tituloTurno } from "./datos";
import { Boton, Cabecera, Fila, Insignia, Pie, RADIO, TAMANO, Tarjeta, TEXTO } from "./ui";

export function EstadoTurno({ turno }) {
  const [texto, tono] = estadoTurno(turno);
  return <Insignia tono={tono}>{texto}</Insignia>;
}

export function ItemTurno({ turno }) {
  return <Link to={`/mi/turnos/${turno.id}`} className={`flex w-full items-center gap-3.5 ${RADIO.tarjeta} border border-borde bg-superficie p-4 text-left hover:border-accent-100 focus-visible:outline-2 focus-visible:outline-accent`}>
    <span className="flex w-16 flex-none flex-col items-center rounded-md bg-accent-50 px-2.5 py-2 text-accent">
      <span className="text-xs font-semibold uppercase leading-[18px]">{diaDeLaCaja(turno.inicio)}</span>
      <strong className={`${TAMANO.t17} font-bold`}>{hora(turno.inicio)}</strong>
    </span>
    <span className="min-w-0 flex-1">
      <strong className={`block truncate ${TAMANO.t15} font-semibold`}>{tituloTurno(turno)}</strong>
      <span className={`block truncate ${TEXTO.filaDetalle}`}>{quienYDonde(turno)}</span>
      {turno.estado !== "reservado" && <span className="mt-1 block"><EstadoTurno turno={turno} /></span>}
    </span>
    <Icon name="chevronRight" size={16} className="flex-none text-texto-suave" />
  </Link>;
}

export function MisTurnos() {
  const turnos = useTurnosPortal();
  const { state } = useLocation();
  const [parametros] = useSearchParams();
  const anteriores = parametros.get("ver") === "anteriores";
  const pestana = (activa) => `flex flex-1 justify-center ${RADIO.pestana} border px-3 py-2 text-sm leading-[21px] ${activa ? "border-borde bg-superficie font-semibold text-texto" : "border-transparent font-medium text-texto-suave"}`;
  return <>
    <Cabecera titulo="Mis turnos" atras="/mi/inicio" />
    {state?.aviso && <div className="-mt-2 mb-4"><Exito>{state.aviso}</Exito></div>}
    <div role="tablist" className={`mb-4 flex gap-1 ${RADIO.selector} border border-borde bg-fondo p-1`}>
      <Link role="tab" aria-selected={!anteriores} to="/mi/turnos" replace className={pestana(!anteriores)}>Próximos</Link>
      <Link role="tab" aria-selected={anteriores} to="/mi/turnos?ver=anteriores" replace className={pestana(anteriores)}>Anteriores</Link>
    </div>
    <Consulta consulta={turnos} cargando="Cargando tus turnos…" error="No pudimos cargar tus turnos.">
      {(lista) => {
        const visibles = anteriores ? lista.filter((t) => !esProximo(t)).reverse() : lista.filter(esProximo);
        if (!visibles.length) return <Vacio icono="calendar" titulo={anteriores ? "No tenés turnos en los últimos 90 días" : "No tenés turnos próximos"}>
          {anteriores ? null : "Cuando una institución de la red te dé un turno, lo vas a ver acá."}
        </Vacio>;
        return <div className="space-y-4">{visibles.map((t) => <ItemTurno key={t.id} turno={t} />)}</div>;
      }}
    </Consulta>
  </>;
}

/** Detalle del turno con sus acciones. `?cancelar` abre la confirmación encima. */
export function DetalleTurno() {
  const { id } = useParams();
  const turnos = useTurnosPortal();
  return <Consulta consulta={turnos} cargando="Cargando tu turno…" error="No pudimos cargar tu turno.">
    {(lista) => {
      const turno = lista.find((t) => String(t.id) === id);
      return turno ? <Turno turno={turno} /> : <Navigate to="/mi/turnos" replace />;
    }}
  </Consulta>;
}

function Turno({ turno: t }) {
  const [parametros, setParametros] = useSearchParams();
  const confirmar = useAccionTurno("confirmar");
  // Vive acá y no en la hoja: si el backend rechaza, la lista se relee y llega
  // `puede_cancelar=false`. La hoja tiene que seguir abierta para mostrar por
  // qué, y quien navega al terminar no puede ser un componente desmontado.
  const cancelar = useAccionTurno("cancelar");
  const navigate = useNavigate();
  const [aviso, setAviso] = useState("");
  const proximo = esProximo(t);
  const cancelando = parametros.has("cancelar") && (t.puede_cancelar || cancelar.isPending || cancelar.isError);
  const { reset } = cancelar;
  const cerrar = useCallback(() => {
    reset();
    setParametros({}, { replace: true });
  }, [reset, setParametros]);
  const alCancelar = () => cancelar.mutate(t.id, {
    onSuccess: () => navigate("/mi/turnos", { replace: true, state: { aviso: "Cancelaste tu turno. El horario quedó libre para otra persona." } }),
  });

  const alConfirmar = () => {
    setAviso("");
    confirmar.mutate(t.id, { onSuccess: () => setAviso("Listo: le avisamos a la institución que vas a ir.") });
  };

  return <>
    <Cabecera titulo="Tu turno" atras={proximo ? "/mi/turnos" : "/mi/turnos?ver=anteriores"} />
    <div className="flex flex-1 flex-col gap-4">
      <div className={`flex flex-col gap-1.5 ${RADIO.tarjeta} p-5 ${proximo ? "hen-cta text-white" : "border border-borde bg-superficie"}`}>
        <p className="text-sm font-medium leading-[21px] first-letter:uppercase">{fechaLarga(t.inicio)}</p>
        <h2 className="text-xxl font-bold leading-[30px]">{hora(t.inicio)} · {tituloTurno(t)}</h2>
        <p className={TAMANO.t15}>{quienYDonde(t)}</p>
      </div>
      <Tarjeta className="overflow-hidden">
        <Fila titulo="Estado" extremo={<EstadoTurno turno={t} />} />
        <Fila titulo="Dónde" detalle={[t.institucion?.nombre, t.area].filter(Boolean).join(" · ")} />
        {t.modalidad === "virtual"
          ? <Fila titulo="Consulta virtual" detalle={t.enlace ? "El enlace se abre en otra pestaña" : "La institución te va a pasar el enlace"} href={t.enlace || undefined} ultimo />
          : <Fila titulo="Qué llevar" detalle="DNI y la credencial de tu cobertura" ultimo />}
      </Tarjeta>
      {aviso && <Exito>{aviso}</Exito>}
      <Alerta>{confirmar.isError ? mensajePortal(confirmar.error, "No pudimos confirmar el turno.") : null}</Alerta>
      {proximo && !t.puede_cancelar && t.motivo_no_cancelable && ["reservado", "confirmado"].includes(t.estado) && <p className={TEXTO.nota}>{t.motivo_no_cancelable}</p>}
      <Pie>
        {t.puede_confirmar && <Boton onClick={alConfirmar} disabled={confirmar.isPending}>{confirmar.isPending ? "Confirmando…" : "Confirmar asistencia"}</Boton>}
        {proximo && <Boton variante="secundario" onClick={() => agregarAlCalendario(t)}>Agregar al calendario</Boton>}
        {proximo && esHoy(t.inicio) && <Boton variante="secundario" to="/mi/llamado">Ver si me llaman</Boton>}
        {t.puede_cancelar && <Boton variante="texto" onClick={() => setParametros({ cancelar: "" }, { replace: true })}>Cancelar turno</Boton>}
      </Pie>
    </div>
    {cancelando && <ConfirmarCancelacion turno={t} cancelar={cancelar} alCancelar={alCancelar} cerrar={cerrar} />}
  </>;
}

/** Hoja de abajo en el celular, diálogo centrado en la compu (Figma «4c · Cancelar turno»). */
function ConfirmarCancelacion({ turno: t, cancelar, alCancelar, cerrar }) {
  const dialogo = useRef(null);
  useEffect(() => {
    // El foco arranca en la opción que no hace nada: un Enter de más no cancela.
    [...(dialogo.current?.querySelectorAll("button") || [])].pop()?.focus();
  }, []);
  useEffect(() => {
    const tecla = (e) => { if (e.key === "Escape") cerrar(); };
    window.addEventListener("keydown", tecla);
    return () => window.removeEventListener("keydown", tecla);
  }, [cerrar]);
  return <div className="fixed inset-0 z-40 flex items-end justify-center bg-velo md:items-center md:p-4">
    <div ref={dialogo} role="dialog" aria-modal="true" aria-labelledby="titulo-cancelar" className={`flex w-full max-w-[28rem] flex-col gap-4 ${RADIO.hojaArribaMd} bg-superficie px-5 pb-[34px] pt-2.5 shadow-dropdown md:pt-6`}>
      <span aria-hidden="true" className={`mx-auto h-1 w-9 ${RADIO.asa} bg-borde md:hidden`} />
      <h2 id="titulo-cancelar" className="text-xl font-semibold leading-7">¿Cancelar tu turno de {tituloTurno(t)}?</h2>
      <p className={TEXTO.cuerpo}><span className="inline-block first-letter:uppercase">{fechaLarga(t.inicio)}</span>, {hora(t.inicio)}{t.profesional ? ` con ${t.profesional}` : ""}, en {t.institucion?.nombre}. El horario queda libre para otra persona.</p>
      <Alerta>{cancelar.isError ? mensajePortal(cancelar.error, "No pudimos cancelar el turno.") : null}</Alerta>
      <div className="space-y-2">
        {!cancelar.isError && <Boton variante="peligro" onClick={alCancelar} disabled={cancelar.isPending}>{cancelar.isPending ? "Cancelando…" : "Sí, cancelar turno"}</Boton>}
        <Boton variante={cancelar.isError ? "secundario" : "texto"} onClick={cerrar}>{cancelar.isError ? "Volver al turno" : "Mantener turno"}</Boton>
      </div>
    </div>
  </div>;
}
