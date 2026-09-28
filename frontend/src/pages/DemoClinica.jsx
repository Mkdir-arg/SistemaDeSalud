import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

// Maqueta pública para la demo: datos de ejemplo, sin solicitudes a la API.
const PANTALLAS = [
  ["bienvenida", "Bienvenida"], ["dni", "Ingreso · DNI"], ["codigo", "Ingreso · código"],
  ["datos", "Ingreso · datos"], ["inicio", "Inicio sin turnos"], ["inicio-turno", "Inicio con turno"],
  ["especialidad", "Sacar turno · especialidad"], ["horario", "Sacar turno · horario"],
  ["confirmar", "Sacar turno · confirmar"], ["confirmado", "Turno confirmado"],
  ["turnos", "Mis turnos"], ["turno", "Detalle del turno"], ["cancelar", "Cancelar turno"],
  ["llegada", "Dar presente"], ["fila", "En la fila"], ["llamado", "Llamado"],
  ["resultados", "Resultados"], ["resultado", "Detalle del resultado"], ["clinica", "La clínica"],
];
const VALIDAS = new Set(PANTALLAS.map(([id]) => id));
const PROFESIONALES = {
  "Clínica médica": ["Dra. Paula Ríos", "Dr. Hernán Ruiz"],
  "Pediatría": ["Dra. Laura Molina", "Dr. Tomás Gil"],
  "Cardiología": ["Dr. Martín Díaz", "Dra. Carla Vega"],
  "Ginecología": ["Dra. Julia Pérez", "Dra. Ana Ledesma"],
  "Traumatología": ["Dr. Diego Rivas", "Dra. Sofía Gómez"],
};
const FECHAS = Array.from({ length: 10 }, (_, i) => {
  const fecha = new Date();
  fecha.setDate(fecha.getDate() + i + 1);
  return fecha;
}).filter((fecha) => fecha.getDay() !== 0 && fecha.getDay() !== 6).slice(0, 5);
const claveFecha = (fecha) => `${fecha.getFullYear()}-${String(fecha.getMonth() + 1).padStart(2, "0")}-${String(fecha.getDate()).padStart(2, "0")}`;
const fechaLegible = (dia) => new Date(`${dia}T12:00:00`).toLocaleDateString("es-AR", { day: "numeric", month: "long" });
const fechaCorta = (dia) => new Date(`${dia}T12:00:00`).toLocaleDateString("es-AR", { day: "2-digit", month: "2-digit" });

function descargarTurno(demo) {
  const [hora, minuto] = demo.hora.split(":").map(Number);
  const formato = (fecha) => fecha.toISOString().replace(/[-:]/g, "").slice(0, 15);
  const [anio, mes, dia] = demo.dia.split("-").map(Number);
  const inicio = new Date(Date.UTC(anio, mes - 1, dia, hora, minuto));
  const fin = new Date(inicio.getTime() + 20 * 60_000);
  const evento = [
    "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//HEN//Demo clinica//ES",
    "BEGIN:VEVENT", `UID:${crypto.randomUUID()}@hen.demo`,
    `DTSTART:${formato(inicio)}`, `DTEND:${formato(fin)}`,
    `SUMMARY:Turno de ejemplo - ${demo.especialidad}`,
    `DESCRIPTION:Simulacion de la app clinica de HEN. ${demo.profesional}. No es una reserva real.`,
    "END:VEVENT", "END:VCALENDAR",
  ].join("\r\n");
  const url = URL.createObjectURL(new Blob([evento], { type: "text/calendar;charset=utf-8" }));
  const enlace = document.createElement("a");
  enlace.href = url;
  enlace.download = "turno-hen-demo.ics";
  enlace.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function Boton({ children, onClick, secundario = false, peligro = false, disabled = false }) {
  return <button type="button" onClick={onClick} disabled={disabled}
    className={`flex min-h-11 w-full items-center justify-center rounded-md px-4 text-sm font-medium focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:cursor-not-allowed disabled:opacity-50 ${peligro ? "bg-danger-fuerte text-white" : secundario ? "border border-borde bg-superficie text-texto-medio hover:bg-accent-50" : "hen-cta text-white"}`}>
    {children}
  </button>;
}

function Cabecera({ titulo, volver }) {
  return <div className="mb-7 flex items-center gap-3 text-sm font-semibold">
    <button type="button" onClick={volver} aria-label="Volver" className="-ml-2 flex size-8 items-center justify-center rounded-md hover:bg-accent-50">‹</button>
    <span>{titulo}</span>
  </div>;
}

function Tarjeta({ children, className = "" }) {
  return <div className={`rounded-lg border border-borde bg-superficie ${className}`}>{children}</div>;
}

function Fila({ titulo, detalle, onClick, badge, ultimo = false }) {
  const clase = `flex w-full items-center justify-between gap-3 px-4 py-4 text-left ${ultimo ? "" : "border-b border-borde"}`;
  const contenido = <>
    <span className="min-w-0"><strong className="block text-sm font-medium">{titulo}</strong>{detalle && <span className="mt-1 block text-xs text-texto-suave">{detalle}</span>}</span>
    <span className="flex shrink-0 items-center gap-2 text-xs text-accent">{badge && <span className={`rounded-sm px-1.5 py-0.5 ${badge === "Listo" ? "bg-badge-green-bg text-badge-green-fg" : "bg-accent-50 text-accent"}`}>{badge}</span>}{onClick && "›"}</span>
  </>;
  return onClick ? <button type="button" onClick={onClick} className={`${clase} hover:bg-accent-50 focus-visible:outline-2 focus-visible:outline-accent`}>{contenido}</button> : <div className={clase}>{contenido}</div>;
}

function Pie({ children }) { return <div className="mt-auto space-y-3 pt-8">{children}</div>; }

export default function DemoClinica() {
  const [parametros, setParametros] = useSearchParams();
  const [demo, setDemo] = useState({ dni: "", codigo: "", nombre: "Martina Sosa", celular: "", especialidad: "Clínica médica", dia: claveFecha(FECHAS[0]), hora: "11:40", profesional: "Dra. Paula Ríos", reservado: false, presente: false });
  const actual = VALIDAS.has(parametros.get("pantalla")) ? parametros.get("pantalla") : "bienvenida";
  const ir = (pantalla) => { cambiar("aviso", ""); setParametros({ pantalla }); };
  const cambiar = (clave, valor) => setDemo((estado) => ({ ...estado, [clave]: valor }));
  const reservar = () => { setDemo((estado) => ({ ...estado, reservado: true, presente: false })); ir("confirmado"); };
  const cancelar = () => { setDemo((estado) => ({ ...estado, reservado: false, presente: false })); ir("inicio"); };
  const presente = () => { setDemo((estado) => ({ ...estado, presente: true })); ir("fila"); };
  const volver = () => ir(({ dni: "bienvenida", codigo: "dni", datos: "codigo", especialidad: "inicio", horario: "especialidad", confirmar: "horario", confirmado: "confirmar", turno: "turnos", cancelar: "turno", llegada: "inicio-turno", fila: "llegada", llamado: "fila", resultado: "resultados" })[actual] || "inicio-turno");
  const vista = contenido(actual, ir, volver, demo, cambiar, { reservar, cancelar, presente });

  return <div className="clinica-demo min-h-screen bg-fondo p-3 text-texto sm:p-6">
    <div className="mx-auto mb-4 max-w-[390px] rounded-lg border border-borde bg-superficie px-4 py-3 text-xs shadow-card">
      <div className="flex items-center justify-between gap-2"><strong>App clínica · demo interactiva</strong><Link to="/presentacion" className="font-semibold text-accent hover:underline">Volver a HEN</Link></div>
      <p className="mt-1 text-texto-suave">Datos ficticios. Probá el recorrido; nada se envía al sistema.</p>
      <details className="mt-2"><summary className="cursor-pointer font-medium text-accent">Explorar pantallas de Figma</summary>
        <label className="mt-2 flex items-center gap-2">Pantalla
          <select aria-label="Elegir pantalla de la maqueta" value={actual} onChange={(e) => ir(e.target.value)} className="min-w-0 flex-1 rounded-md border border-campo-borde bg-superficie px-2 py-1">
            {PANTALLAS.map(([id, nombre]) => <option key={id} value={id}>{nombre}</option>)}
          </select>
        </label>
      </details>
    </div>
    <div className={`clinica-phone mx-auto flex flex-col overflow-hidden rounded-[28px] border border-borde bg-fondo shadow-float ${actual === "llamado" ? "clinica-llamado" : ""}`}>
      {actual === "bienvenida" ? vista : <>
        <div className="flex justify-between px-5 pb-3 pt-4 text-xs font-semibold"><span>9:41</span><span>5G&nbsp; 100 %</span></div>
        <div className="flex min-h-0 flex-1 flex-col px-5 pb-5">{vista}</div>
      </>}
      {demo.aviso && <p role="status" className="mx-5 mb-4 rounded-md border border-accent-100 bg-superficie p-3 text-xs text-texto-medio">{demo.aviso}</p>}
    </div>
  </div>;
}

function contenido(p, ir, volver, demo, cambiar, acciones) {
  if (p === "bienvenida") return <>
    <img src="/demo-clinica-bienvenida.png" alt="Ilustración de una clínica y un turno confirmado" className="h-[490px] w-full flex-none object-cover object-center" />
    <div className="flex flex-1 flex-col px-6 pb-6 pt-5">
      <p className="text-xs font-bold tracking-[.15em] text-accent">CLÍNICA MODELO</p>
      <h1 className="mt-3 text-xxl font-bold leading-tight">¡Qué bueno verte! Te damos la bienvenida</h1>
      <p className="mt-3 text-sm leading-relaxed text-texto-suave">Sacá turno, avisá que llegaste sin hacer fila y mirá tus resultados. Estamos para cuidarte.</p>
      <Pie><div className="flex gap-1"><span className="h-1.5 w-6 rounded-pill bg-accent-fuerte" /><span className="size-1.5 rounded-pill bg-accent-100" /><span className="size-1.5 rounded-pill bg-accent-100" /></div>
        <Boton onClick={() => ir("dni")}>Empezar</Boton>
        <p className="text-center text-xs text-texto-suave">¿Ya tenés cuenta? <button type="button" onClick={() => ir("dni")} className="font-semibold text-accent">Ingresar</button></p>
      </Pie>
    </div>
  </>;

  if (p === "dni") return <><Cabecera titulo="Ingresar" volver={volver} />
    <h2 className="text-xl font-bold">¿Cuál es tu DNI?</h2><p className="mt-2 text-sm text-texto-suave">Con tu DNI buscamos si ya te atendiste en la clínica.</p>
    <label className="mt-6 text-xs font-medium">Número de documento<input inputMode="numeric" autoComplete="off" value={demo.dni} onChange={(e) => cambiar("dni", e.target.value.replace(/\D/g, "").slice(0, 8))} placeholder="Ej.: 34521521" className="mt-2 h-11 w-full rounded-md border border-accent bg-superficie px-3 text-sm" /></label>
    <Pie><Boton disabled={demo.dni.length < 7} onClick={() => ir("codigo")}>Continuar</Boton></Pie></>;

  if (p === "codigo") return <><Cabecera titulo="Ingresar" volver={volver} />
    <h2 className="text-xl font-bold">Ingresá el código</h2><p className="mt-2 text-sm text-texto-suave">En esta simulación, el código de prueba es <strong>4819</strong>. No enviamos mensajes.</p>
    <label className="mt-6 text-xs font-medium">Código de cuatro dígitos<input inputMode="numeric" autoComplete="one-time-code" value={demo.codigo} onChange={(e) => cambiar("codigo", e.target.value.replace(/\D/g, "").slice(0, 4))} placeholder="4819" className="mt-2 h-12 w-full rounded-md border border-accent bg-superficie px-3 text-center text-lg font-bold tracking-[.4em]" /></label>
    {demo.codigo.length === 4 && demo.codigo !== "4819" && <p role="alert" className="mt-2 text-xs text-danger">El código de esta demo es 4819.</p>}
    <p className="mt-4 text-xs text-texto-suave">¿Cambiaste de número? Comunicate con la clínica.</p>
    <Pie><Boton disabled={demo.codigo !== "4819"} onClick={() => ir("datos")}>Continuar</Boton></Pie></>;

  if (p === "datos") return <><Cabecera titulo="Tus datos" volver={volver} />
    <h2 className="text-xl font-bold">Es tu primera vez en la clínica</h2><p className="mt-2 text-sm text-texto-suave">Completá estos datos una sola vez.</p>
    <label className="mt-5 block text-xs font-medium">Nombre y apellido *<input value={demo.nombre} onChange={(e) => cambiar("nombre", e.target.value)} className="mt-2 h-11 w-full rounded-md border border-borde bg-superficie px-3 text-sm" /></label>
    <label className="mt-5 block text-xs font-medium">Fecha de nacimiento *<input type="date" value={demo.nacimiento || ""} onChange={(e) => cambiar("nacimiento", e.target.value)} className="mt-2 h-11 w-full rounded-md border border-borde bg-superficie px-3 text-sm" /></label>
    <label className="mt-5 block text-xs font-medium">Celular *<input inputMode="tel" value={demo.celular} onChange={(e) => cambiar("celular", e.target.value)} placeholder="11 5555-4521" className="mt-2 h-11 w-full rounded-md border border-borde bg-superficie px-3 text-sm" /></label>
    <label className="mt-5 block text-xs font-medium">Cobertura (opcional)<select value={demo.cobertura || "sin"} onChange={(e) => cambiar("cobertura", e.target.value)} className="mt-2 h-11 w-full rounded-md border border-borde bg-superficie px-3 text-sm"><option value="sin">Sin cobertura</option><option value="osde">OSDE 210 (ejemplo)</option><option value="swiss">Swiss Medical (ejemplo)</option></select></label>
    <p className="mt-3 text-xs text-texto-suave">Si tenés obra social o prepaga, te mostramos cuánto cubre.</p>
    <Pie><Boton disabled={!demo.nombre.trim() || !demo.nacimiento || !demo.celular.trim()} onClick={() => ir(demo.reservado ? "inicio-turno" : "inicio")}>Ver inicio</Boton></Pie></>;

  if (p === "inicio" || p === "inicio-turno") return <>
    <div className="mb-5 flex items-center gap-3"><span className="flex size-9 items-center justify-center rounded-md bg-superficie text-[10px] text-texto-suave">Logo</span><div><p className="text-xs text-texto-suave">Clínica Modelo</p><h1 className="text-xl font-bold">Hola, {demo.nombre.trim().split(/\s+/)[0] || "Martina"}</h1></div></div>
    <div className="rounded-lg bg-gradient-to-tr from-[#7031C7] via-[#315BA0] to-[#007A70] p-5 text-white">
      {p === "inicio" ? <><h2 className="text-lg font-bold">¿Necesitás atenderte?</h2><p className="mt-2 text-sm">Elegí especialidad, día y horario. Te mostramos cuánto vas a pagar antes de confirmar.</p><div className="mt-4"><Boton secundario onClick={() => ir("especialidad")}>Sacar turno</Boton></div></>
        : <><p className="text-xs">Tu próximo turno · simulación</p><h2 className="mt-2 text-xl font-bold">{demo.hora} · {demo.especialidad}</h2><p className="mt-2 text-sm">{demo.profesional} · consultorio 4, planta baja</p><div className="mt-4 flex gap-2"><Boton secundario onClick={() => ir(demo.presente ? "fila" : "llegada")}>{demo.presente ? "Ver fila" : "Dar presente"}</Boton><Boton secundario onClick={() => ir("clinica")}>Cómo llegar</Boton></div><p className="mt-3 text-xs">En la app real se habilita a menos de 500 m.</p></>}
    </div>
    {p === "inicio-turno" && <div className="mt-4"><Boton secundario onClick={() => ir("especialidad")}>Sacar otro turno</Boton></div>}
    <Tarjeta className="mt-4 overflow-hidden"><Fila titulo="Mis turnos" detalle={p === "inicio" && !demo.reservado ? "Sin turnos próximos" : "1 próximo"} onClick={() => ir("turnos")} /><Fila titulo="Resultados" detalle="1 nuevo" badge="Nuevo" onClick={() => ir("resultados")} /><Fila titulo="La clínica" detalle="Dirección, horarios y teléfonos" onClick={() => ir("clinica")} ultimo /></Tarjeta>
  </>;

  if (p === "especialidad") return <><Cabecera titulo="Sacar turno" volver={volver} /><Paso numero={1} />
    <h2 className="mt-5 text-xl font-bold">¿Con qué especialidad?</h2><input value={demo.busqueda || ""} onChange={(e) => cambiar("busqueda", e.target.value)} aria-label="Buscar especialidad o profesional" placeholder="Buscá especialidad o profesional" className="mt-4 h-11 w-full rounded-md border border-borde bg-superficie px-3 text-sm" />
    {(!demo.busqueda || "Dra. Paula Ríos".toLowerCase().includes(demo.busqueda.toLowerCase())) && <><h3 className="mt-6 text-sm font-bold">Volver con</h3><Tarjeta className="mt-3"><Fila titulo="Dra. Paula Ríos" detalle="Clínica médica · última vez 07/08" onClick={() => { cambiar("especialidad", "Clínica médica"); cambiar("profesional", "Dra. Paula Ríos"); ir("horario"); }} ultimo /></Tarjeta></>}
    <h3 className="mt-6 text-sm font-bold">Especialidades de la clínica</h3><Tarjeta className="mt-3 overflow-hidden">{[["Clínica médica",6],["Pediatría",3],["Cardiología",2],["Ginecología",2],["Traumatología",2]].filter(([nombre]) => nombre.toLowerCase().includes((demo.busqueda || "").toLowerCase())).map(([nombre,n],i, lista) => <Fila key={nombre} titulo={nombre} detalle={`${n} profesionales`} onClick={() => { cambiar("especialidad", nombre); cambiar("profesional", PROFESIONALES[nombre][0]); ir("horario"); }} ultimo={i===lista.length-1} />)}</Tarjeta></>;

  if (p === "horario") return <><Cabecera titulo={demo.especialidad} volver={volver} /><Paso numero={2} />
    <div className="mt-6 flex gap-1.5">{FECHAS.map((fecha) => { const dia = claveFecha(fecha); return <button type="button" key={dia} aria-pressed={demo.dia === dia} onClick={() => cambiar("dia", dia)} className={`flex h-16 flex-1 flex-col items-center justify-center rounded-md border text-xs ${demo.dia === dia ? "border-accent bg-accent-fuerte text-white" : "border-borde bg-superficie"}`}>{fecha.toLocaleDateString("es-AR", { weekday: "short" }).replace(".", "").toUpperCase()}<strong className="text-lg">{fecha.getDate()}</strong></button>; })}</div>
    {(PROFESIONALES[demo.especialidad] || PROFESIONALES["Clínica médica"]).map((nombre, indice) => <Tarjeta key={nombre} className="mt-4 p-4"><h3 className="text-sm font-semibold">{nombre}</h3><div className="mt-3 flex flex-wrap gap-2">{(indice === 0 ? ["11:40","12:00","12:40"] : ["15:00","15:20","16:40","17:00"]).map((hora) => <button type="button" key={hora} aria-pressed={demo.hora === hora && demo.profesional === nombre} onClick={() => { cambiar("hora", hora); cambiar("profesional", nombre); }} className={`rounded-pill border px-3 py-2 text-xs ${demo.hora === hora && demo.profesional === nombre ? "border-accent bg-accent-fuerte text-white" : "border-borde hover:border-accent"}`}>{hora}</button>)}</div></Tarjeta>)}
    <Pie><Boton onClick={() => ir("confirmar")}>Continuar con {demo.hora}</Boton></Pie></>;

  if (p === "confirmar") return <><Cabecera titulo="Confirmá tu turno" volver={volver} /><Paso numero={3} />
    <Tarjeta className="mt-5 space-y-4 p-4">{[["Cuándo",`${fechaCorta(demo.dia)} · ${demo.hora}`],["Con quién",`${demo.profesional} · ${demo.especialidad}`],["Dónde","Consultorio 4, planta baja"],["Cobertura",demo.cobertura === "osde" ? "OSDE 210 (ejemplo)" : demo.cobertura === "swiss" ? "Swiss Medical (ejemplo)" : "Sin cobertura"]].map(([k,v]) => <div key={k}><p className="text-xs text-texto-suave">{k}</p><strong className="mt-1 block text-sm">{v}</strong></div>)}</Tarjeta>
    <p className="mt-4 rounded-md border border-badge-amber-fg bg-badge-amber-bg p-3 text-xs text-badge-amber-fg">Si tu plan tuviera copago, acá verías cuánto pagarías en la caja de la clínica.</p>
    <label className="mt-5 flex items-center gap-2 text-sm"><input type="checkbox" checked={demo.recordatorio !== false} onChange={(e) => cambiar("recordatorio", e.target.checked)} /> Recordarme 2 horas antes</label><Pie><Boton onClick={acciones.reservar}>Confirmar turno de ejemplo</Boton></Pie></>;

  if (p === "confirmado") return <div className="flex flex-1 flex-col items-center justify-center text-center"><span className="flex size-20 items-center justify-center rounded-full bg-badge-green-bg text-[40px] text-badge-green-fg">✓</span><h1 className="mt-5 text-xl font-bold">¡Listo! Tu turno quedó confirmado</h1><p className="mt-4 text-sm text-texto-suave">El {fechaLegible(demo.dia)} a las {demo.hora} con {demo.profesional}, consultorio 4. {demo.recordatorio !== false ? "Te recordamos 2 horas antes." : "Sin recordatorio."}</p><div className="mt-8 w-full space-y-3"><Boton secundario onClick={() => descargarTurno(demo)}>Agregar al calendario</Boton><Boton onClick={() => ir("inicio-turno")}>Volver al inicio</Boton></div></div>;

  if (p === "turnos") return <><Cabecera titulo="Mis turnos" volver={() => ir(demo.reservado ? "inicio-turno" : "inicio")} /><div className="mb-4 flex rounded-md border border-borde p-1 text-xs"><span className="flex-1 rounded-sm bg-superficie py-2 text-center font-semibold">Próximos</span><span className="flex-1 py-2 text-center text-texto-suave">Anteriores</span></div>
    {demo.reservado ? <button type="button" onClick={() => ir("turno")} className="mb-3 flex w-full items-center gap-3 rounded-lg border border-borde bg-superficie p-3 text-left"><span className="rounded-md bg-accent-50 px-2 py-1 text-center text-xs text-accent">{fechaCorta(demo.dia)}<strong className="block text-lg">{demo.hora}</strong></span><span><strong className="block text-sm">{demo.especialidad}</strong><span className="text-xs text-texto-suave">{demo.profesional} · consultorio 4</span></span><span className="ml-auto text-accent">›</span></button> : <Tarjeta className="p-4 text-sm text-texto-suave">Todavía no reservaste un turno en esta demo.</Tarjeta>}
    <Pie><Boton onClick={() => ir("especialidad")}>Sacar un turno</Boton></Pie></>;

  if (p === "turno") return <><Cabecera titulo="Tu turno" volver={volver} /><div className="rounded-lg bg-gradient-to-tr from-[#7031C7] to-[#007A70] p-4 text-white"><p className="text-xs">{fechaLegible(demo.dia)} · ejemplo</p><h2 className="mt-1 text-xl font-bold">{demo.hora} · {demo.especialidad}</h2><p className="mt-2 text-sm">{demo.profesional} · consultorio 4, planta baja</p></div>
    <Tarjeta className="mt-4 overflow-hidden"><Fila titulo="Cobertura" detalle={demo.cobertura === "osde" ? "OSDE 210 (ejemplo)" : demo.cobertura === "swiss" ? "Swiss Medical (ejemplo)" : "Sin cobertura"} /><Fila titulo="Qué llevar" detalle="DNI, credencial y estudios anteriores" /><Fila titulo="Cómo llegar" detalle="Av. Siempre Viva 742" onClick={() => ir("clinica")} ultimo /></Tarjeta>
    <Pie><Boton secundario onClick={() => ir("horario")}>Cambiar día u horario</Boton><button type="button" onClick={() => ir("cancelar")} className="w-full py-2 text-sm">Cancelar turno</button></Pie></>;

  if (p === "cancelar") return <><Cabecera titulo="Mis turnos" volver={volver} /><div className="flex-1" /><div className="-mx-5 rounded-t-[24px] bg-superficie p-5 shadow-float"><h2 className="text-lg font-bold">¿Cancelar tu turno de {demo.especialidad}?</h2><p className="mt-4 text-sm text-texto-suave">{fechaCorta(demo.dia)}, {demo.hora} con {demo.profesional}. En esta demo, el turno desaparecerá de «Mis turnos».</p><div className="mt-5"><Boton peligro onClick={acciones.cancelar}>Cancelar turno de ejemplo</Boton></div><button type="button" onClick={() => ir("turno")} className="mt-4 w-full py-2 text-sm">Mantener turno</button></div></>;

  if (p === "llegada") return <><Cabecera titulo="Llegada" volver={volver} /><div className="rounded-lg bg-[#E9F8FA] px-4 py-12 text-center"><span className="mx-auto flex size-12 items-center justify-center rounded-full bg-accent-fuerte text-xxl text-white">⌾</span><strong className="mt-4 block text-sm">Estás a 350 m de la clínica</strong></div><h2 className="mt-5 text-xl font-bold">Ya podés avisar que llegaste</h2><p className="mt-2 text-sm text-texto-suave">Te sumamos a la fila de {demo.especialidad}. No hace falta pasar por la recepción.</p><Tarjeta className="mt-5 p-4 text-sm"><strong>{fechaCorta(demo.dia)}, {demo.hora} · {demo.profesional}</strong><p className="mt-1 text-xs text-texto-suave">Consultorio 4, planta baja</p></Tarjeta><Pie><Boton onClick={acciones.presente}>Simular presente</Boton><button type="button" onClick={acciones.presente} className="w-full py-2 text-sm">Ver alternativa con QR</button></Pie></>;

  if (p === "fila") return <><Cabecera titulo={demo.especialidad} volver={volver} /><div className="rounded-lg bg-gradient-to-tr from-[#7031C7] to-[#007A70] p-5 text-white"><p className="text-sm">Estás en la fila</p><strong className="mt-2 block text-[48px]">3.º</strong><p className="mt-2 text-sm font-semibold">Te atienden en unos 15 minutos</p></div><Tarjeta className="mt-4 overflow-hidden"><Fila titulo="Diste presente" detalle="11:12" badge="Listo" /><Fila titulo="Esperando" detalle="Sala de espera, planta baja" badge="Ahora" /><Fila titulo="Te llaman al consultorio 4" detalle="Te avisamos con una notificación" onClick={() => ir("llamado")} ultimo /></Tarjeta><p className="mt-5 text-xs text-texto-suave">Podés esperar cerca: te avisamos 5 minutos antes.</p><Pie><Boton secundario onClick={() => ir("cancelar")}>No voy a poder quedarme</Boton><Boton secundario onClick={() => ir("llamado")}>Ver llamado de ejemplo</Boton></Pie></>;

  if (p === "llamado") return <div className="flex flex-1 flex-col items-center justify-center text-center text-white"><span className="flex size-20 items-center justify-center rounded-full bg-white text-[40px] text-accent">♧</span><h1 className="mt-6 text-xxl font-bold">Te están llamando</h1><h2 className="mt-4 text-lg font-semibold">Consultorio 4 · planta baja</h2><p className="mt-4 text-sm">{demo.profesional} te espera.</p><div className="mt-8 w-full"><Boton secundario onClick={() => ir("inicio-turno")}>Voy para allá</Boton></div></div>;

  if (p === "resultados") return <><Cabecera titulo="Resultados" volver={() => ir("inicio-turno")} /><Tarjeta className="overflow-hidden"><Fila titulo="Análisis de sangre completo" detalle="Laboratorio · 22/09" badge="Listo" onClick={() => ir("resultado")} /><Fila titulo="Radiografía de tórax" detalle="Imágenes · 16/06" badge="Listo" onClick={() => ir("resultado")} /><Fila titulo="Ecocardiograma" detalle="Cardiología · 21/09" badge="En proceso" onClick={() => ir("resultado")} ultimo /></Tarjeta><p className="mt-5 text-xs text-texto-suave">Te avisamos cuando un resultado esté listo.</p></>;

  if (p === "resultado") return <><Cabecera titulo="Análisis de sangre" volver={volver} /><p className="mb-4 text-xs text-texto-suave">22 de septiembre · pedido por la Dra. Ríos</p><p className="rounded-md border border-badge-amber-fg bg-badge-amber-bg p-3 text-xs text-badge-amber-fg">2 valores fuera del rango de referencia. Consultalo con tu médica.</p><Tarjeta className="mt-4 overflow-hidden">{[["Glucemia","Referencia 70 a 110","Alto · 126 mg/dl"],["Colesterol total","Referencia menor a 200","Alto · 238 mg/dl"],["Hemoglobina","Referencia 12 a 16","13,8 g/dl"]].map(([titulo,ref,v]) => <div key={titulo} className="flex items-center justify-between gap-2 border-b border-borde p-4"><span><strong className="block text-sm">{titulo}</strong><span className="text-xs text-texto-suave">{ref}</span></span><strong className="text-xs">{v}</strong></div>)}</Tarjeta><Pie><Boton secundario onClick={() => cambiar("aviso", "El informe es ilustrativo; esta demo no tiene un PDF clínico para descargar.")}>Descargar informe (PDF)</Boton><Boton onClick={() => { cambiar("especialidad", "Clínica médica"); cambiar("profesional", "Dra. Paula Ríos"); ir("horario"); }}>Sacar turno con la Dra. Ríos</Boton></Pie></>;

  return <><Cabecera titulo="La clínica" volver={() => ir("inicio-turno")} /><div className="flex items-center gap-3"><span className="flex size-14 items-center justify-center rounded-md bg-superficie text-xs text-texto-suave">Logo</span><div><h2 className="text-lg font-bold">Clínica Modelo</h2><p className="text-xs text-texto-suave">Av. Siempre Viva 742, CABA</p></div></div><div className="mt-5 flex gap-2"><Boton secundario onClick={() => cambiar("aviso", "Dirección de ejemplo: Av. Siempre Viva 742, CABA.")}>Cómo llegar</Boton><Boton secundario onClick={() => cambiar("aviso", "Teléfono de ejemplo para turnos: 011 4555-0000. No se inicia una llamada.")}>Llamar</Boton></div><Tarjeta className="mt-5 overflow-hidden"><Fila titulo="Consultorios" detalle="Lunes a viernes, 8 a 20 h · sábados, 8 a 13 h" /><Fila titulo="Guardia" detalle="Todos los días, las 24 h" /><Fila titulo="Laboratorio (extracciones)" detalle="Lunes a sábado, 7 a 10 h, sin turno" ultimo /></Tarjeta><Tarjeta className="mt-4 overflow-hidden"><Fila titulo="Turnos y consultas" detalle="011 4555-0000 (ejemplo)" /><Fila titulo="Guardia" detalle="011 4555-0911 (ejemplo)" ultimo /></Tarjeta></>;
}

function Paso({ numero }) {
  return <div><p className="text-xs font-semibold text-accent">Paso {numero} de 3</p><div className="mt-3 flex gap-1">{[1,2,3].map((n) => <span key={n} className={`h-1 flex-1 rounded-pill ${n <= numero ? "bg-accent-fuerte" : "bg-accent-100"}`} />)}</div></div>;
}
