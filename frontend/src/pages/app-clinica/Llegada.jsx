import { useEffect } from "react";
import { Navigate, useNavigate, useParams } from "react-router-dom";

import { Icon } from "@/components/icons";

import { hoy } from "./datos";
import { etapa, LUGAR_INICIAL, useAhora, useApp } from "./estado";
import { GRADIENTE } from "./Turnos";
import { Boton, Cabecera, Insignia, MarcaClinica, Pie, ruta, Tarjeta } from "./ui";

const hhmm = (ms) => new Date(ms).toLocaleTimeString("es-AR", { hour: "2-digit", minute: "2-digit", hour12: false });

/** Turno de la ruta si está en la etapa pedida; si no, a dónde corresponde ir. */
function useTurnoEn(etapas) {
  const { id } = useParams();
  const { turnos } = useApp();
  const t = turnos.find((x) => x.id === id);
  const ahora = useAhora(t?.estado === "presente");
  if (!t) return { salto: ruta("turnos") };
  const e = etapa(t, ahora);
  if (etapas.includes(e.tipo)) return { t, e, ahora };
  if (e.tipo === "en-fila") return { salto: ruta(`turnos/${t.id}/fila`) };
  if (e.tipo === "llamado") return { salto: ruta(`turnos/${t.id}/llamado`) };
  return { salto: ruta(`turnos/${t.id}`) };
}

function ResumenTurno({ t }) {
  return <Tarjeta className="mt-5 p-4 text-sm"><strong>Hoy, {t.hora} · {t.profesional}</strong><p className="mt-1 text-xs text-texto-suave">{t.especialidad} · consultorio {t.consultorio}, planta baja</p></Tarjeta>;
}

export function Llegada() {
  const { t, salto } = useTurnoEn(["confirmado"]);
  const { acciones } = useApp();
  const navigate = useNavigate();
  if (salto) return <Navigate to={salto} replace />;
  if (t.dia !== hoy()) return <Navigate to={ruta(`turnos/${t.id}`)} replace />;
  const presente = () => { acciones.darPresente(t.id); navigate(ruta(`turnos/${t.id}/fila`), { replace: true }); };
  return <>
    <Cabecera titulo="Llegada" atras={ruta(`turnos/${t.id}`)} />
    <div className="relative overflow-hidden rounded-lg border border-borde bg-[#E9F8FA] px-4 py-10 text-center">
      <svg aria-hidden="true" className="absolute inset-0 size-full text-[#007A70]/15" preserveAspectRatio="none" viewBox="0 0 100 60"><path d="M0 18h100M0 44h100M22 0v60M64 0v60M0 60 100 0" stroke="currentColor" strokeWidth="3" fill="none" /></svg>
      <span className="relative mx-auto flex size-14 items-center justify-center rounded-full bg-accent-fuerte text-white shadow-float"><Icon name="map" size={24} /></span>
      <strong className="relative mt-4 block text-sm">Estás a 350 m de la clínica</strong>
      <span className="relative text-xs text-texto-suave">Ubicación confirmada hace instantes</span>
    </div>
    <h2 className="mt-5 text-xl font-bold">Ya podés avisar que llegaste</h2>
    <p className="mt-2 text-sm text-texto-suave">Te sumamos a la fila de {t.especialidad}. No hace falta pasar por la recepción.</p>
    <ResumenTurno t={t} />
    <Pie>
      <Boton onClick={presente}>Dar presente</Boton>
      <Boton variante="texto" to={ruta(`turnos/${t.id}/qr`)}>Usar el QR de la entrada</Boton>
    </Pie>
  </>;
}

/** Un QR de muestra: tiene la forma de uno real, pero no codifica nada. */
function QrMuestra({ semilla }) {
  const n = 25;
  let s = [...semilla].reduce((a, c) => (a * 31 + c.charCodeAt(0)) >>> 0, 7);
  const azar = () => { s = (s * 1103515245 + 12345) >>> 0; return (s >>> 16) & 1; };
  const enBuscador = (x, y) => [[0, 0], [n - 7, 0], [0, n - 7]].some(([bx, by]) => x >= bx - 1 && x <= bx + 7 && y >= by - 1 && y <= by + 7);
  const celdas = [];
  for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) if (!enBuscador(x, y) && azar()) celdas.push(<rect key={`${x}-${y}`} x={x} y={y} width="1" height="1" />);
  const buscador = (x, y) => <g key={`b${x}${y}`}><rect x={x} y={y} width="7" height="7" /><rect x={x + 1} y={y + 1} width="5" height="5" fill="#fff" /><rect x={x + 2} y={y + 2} width="3" height="3" /></g>;
  return <svg viewBox={`-2 -2 ${n + 4} ${n + 4}`} role="img" aria-label="Código QR de presente" className="size-56" shapeRendering="crispEdges">
    <rect x="-2" y="-2" width={n + 4} height={n + 4} fill="#fff" />
    <g fill="#1D1930">{celdas}{buscador(0, 0)}{buscador(n - 7, 0)}{buscador(0, n - 7)}</g>
  </svg>;
}

export function CodigoQr() {
  const { t, salto } = useTurnoEn(["confirmado"]);
  const { acciones } = useApp();
  const navigate = useNavigate();
  if (salto) return <Navigate to={salto} replace />;
  const escaneado = () => { acciones.darPresente(t.id); navigate(ruta(`turnos/${t.id}/fila`), { replace: true }); };
  return <>
    <Cabecera titulo="Código de presente" atras={ruta(`turnos/${t.id}/llegada`)} />
    <h2 className="text-xl font-bold">Mostrá este código en el tótem de la entrada</h2>
    <p className="mt-2 text-sm text-texto-suave">Acercalo al lector. Si tu celular no tiene ubicación, es la forma más rápida de avisar que llegaste.</p>
    <div className="mt-6 flex flex-col items-center rounded-lg border border-borde bg-superficie p-6">
      <QrMuestra semilla={t.id} />
      <p className="mt-3 font-mono text-sm font-semibold tracking-widest text-texto-medio">{t.id.slice(-6).toUpperCase()}</p>
    </div>
    <ResumenTurno t={t} />
    <Pie><Boton onClick={escaneado}>Listo, ya lo escaneé</Boton></Pie>
  </>;
}

export function EnFila() {
  const { t, e, salto } = useTurnoEn(["en-fila"]);
  if (salto) return <Navigate to={salto} replace />;
  const progreso = ((LUGAR_INICIAL - e.lugar + 1) / (LUGAR_INICIAL + 1)) * 100;
  return <>
    <Cabecera titulo={t.especialidad} atras={ruta("inicio")} />
    <div className={`rounded-lg p-5 ${GRADIENTE}`}>
      <p className="text-sm text-white/90">Estás en la fila</p>
      <strong aria-live="polite" className="mt-1 block text-[56px] leading-none">{e.lugar}.º</strong>
      <p className="mt-2 text-sm font-semibold">Te atienden en unos {e.lugar * 5} minutos</p>
      <div className="mt-4 h-1.5 overflow-hidden rounded-pill bg-white/25"><div className="h-full rounded-pill bg-white transition-[width] duration-700" style={{ width: `${progreso}%` }} /></div>
    </div>
    <Tarjeta className="mt-4 overflow-hidden">
      {[
        ["Diste presente", hhmm(t.presenteDesde), <Insignia key="l" tono="verde">Listo</Insignia>],
        ["Esperando", "Sala de espera, planta baja", <Insignia key="a">Ahora</Insignia>],
        [`Te llaman al consultorio ${t.consultorio}`, "Te avisamos en esta pantalla y con una notificación", null],
      ].map(([titulo, detalle, insignia], i) => <div key={titulo} className={`flex items-center gap-3 px-4 py-3.5 ${i < 2 ? "border-b border-borde" : ""}`}>
        <span className="min-w-0 flex-1"><strong className="block text-sm font-medium">{titulo}</strong><span className="mt-0.5 block text-xs text-texto-suave">{detalle}</span></span>{insignia}
      </div>)}
    </Tarjeta>
    <p className="mt-5 text-xs text-texto-suave">Podés esperar cerca: te avisamos cuando falten 5 minutos.</p>
    <Pie>
      <Boton variante="secundario" to={ruta("inicio")}>Volver al inicio</Boton>
      <Boton variante="texto" to={ruta(`turnos/${t.id}/cancelar`)}>No voy a poder quedarme</Boton>
    </Pie>
  </>;
}

export function Llamado() {
  const { paciente, acciones } = useApp();
  const { t, salto } = useTurnoEn(["llamado"]);
  const navigate = useNavigate();
  useEffect(() => { if (t) navigator.vibrate?.([200, 100, 200]); }, [t]);
  if (!paciente) return <Navigate to={ruta()} replace />;
  if (salto) return <Navigate to={salto} replace />;
  const voy = () => { acciones.entrarAConsulta(t.id); navigate(ruta("inicio"), { replace: true }); };
  return <div role="alertdialog" aria-labelledby="titulo-llamado" className={`flex min-h-dvh flex-col items-center justify-center px-6 text-center ${GRADIENTE}`}>
    <div className="flex w-full max-w-[24rem] flex-1 flex-col items-center justify-center">
      <span className="relative flex size-24 items-center justify-center">
        <span className="absolute inset-0 animate-ping rounded-full bg-white/30" />
        <span className="relative flex size-20 items-center justify-center rounded-full bg-white text-accent"><Icon name="bell" size={36} strokeWidth={2} /></span>
      </span>
      <h1 id="titulo-llamado" className="mt-8 text-cifra-lg font-bold">Te están llamando</h1>
      <p className="mt-4 text-lg font-semibold">Consultorio {t.consultorio} · planta baja</p>
      <p className="mt-2 text-sm text-white/90">{t.profesional} te espera.</p>
    </div>
    <div className="w-full max-w-[24rem] pb-8">
      <Boton variante="claro" onClick={voy}>Voy para allá</Boton>
      <p className="mt-6 flex items-center justify-center gap-2 text-xs text-white/80"><MarcaClinica size={18} /> Clínica Modelo</p>
    </div>
  </div>;
}
