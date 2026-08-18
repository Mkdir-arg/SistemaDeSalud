import { useMemo, useRef, useState } from "react";

import { api } from "@/api/client";
import { useAccion, useLista } from "@/api/queries";
import { Icon } from "@/components/icons";
import { Button, Field, Input, Modal, Select } from "@/components/ui";
import { EstadoError, Skeleton } from "@/components/ui/estados";
import { useToast } from "@/components/ui/toast";
import { cn } from "@/lib/cn";

/*
 * Editor gráfico del horario semanal de una agenda.
 *
 * El formulario que había —día, desde, hasta— alcanzaba para una agenda de un
 * solo bloque y se volvía impracticable con la agenda real de un profesional:
 * lunes de 10 a 12 con turnos de 30 minutos, lunes de 13 a 17 con turnos de 20,
 * miércoles igual que el lunes, y el jueves sólo la tarde. Escrito como lista de
 * filas, nadie ve si quedó un hueco, si dos franjas se pisan, ni cuántos turnos
 * ofrece la semana; dibujado sobre una semana, las cuatro cosas se ven de un
 * vistazo.
 *
 * Lo que se edita es la REGLA semanal, no las fechas: los horarios concretos los
 * calcula el backend al consultar cada día. Por eso la rejilla no tiene fechas
 * —dice «lunes», no «17 de agosto»—.
 */

const DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"];
const DIAS_CORTO = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"];

// Alto de una hora en la rejilla. Con menos, una franja de 30 minutos queda más
// baja que su propio texto y no se puede ni agarrar con el mouse.
const PX_HORA = 44;
// El arrastre engancha a la media hora: es cómo se cargan los horarios de un
// hospital, y sin enganche salen franjas de 10:07 a 12:23.
const PASO_ARRASTRE = 30;

const aMin = (hhmmss) => {
  const [h, m] = String(hhmmss || "0:0").split(":");
  return Number(h) * 60 + Number(m);
};
const aHHMM = (min) => {
  const m = Math.max(0, Math.min(24 * 60, Math.round(min)));
  return `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
};
const hhmm = (hhmmss) => String(hhmmss || "").slice(0, 5);
const enganchar = (min, paso = PASO_ARRASTRE) => Math.round(min / paso) * paso;

/**
 * Franjas de la agenda dibujadas sobre una semana.
 *
 * `onListo` se llama al cerrar para que la lista de agendas vuelva a leer sus
 * disponibilidades: la tarjeta muestra los días y las horas.
 */
export function HorariosModal({ agenda, onClose }) {
  const toast = useToast();
  const lista = useLista("disponibilidades", { agenda: agenda.id, pageSize: 100 });
  const franjas = lista.filas;
  const [sel, setSel] = useState(null); // id de la franja abierta en el panel
  const [fantasma, setFantasma] = useState(null); // { dia, desde, hasta } mientras se arrastra
  const [copiando, setCopiando] = useState(null); // día que se está copiando a otros

  // La rejilla arranca una hora antes de la franja más temprana y termina una
  // después de la más tardía, con 7 a 21 como piso: una agenda de 8 a 12 no
  // tiene por qué obligar a hacer scroll por la madrugada, pero una guardia que
  // atiende a las 6 tiene que poder verse.
  const [desdeVista, hastaVista] = useMemo(() => {
    let min = 7 * 60, max = 21 * 60;
    for (const f of franjas) {
      min = Math.min(min, aMin(f.desde) - 60);
      max = Math.max(max, aMin(f.hasta) + 60);
    }
    return [Math.max(0, enganchar(min, 60)), Math.min(24 * 60, enganchar(max, 60))];
  }, [franjas]);
  const minutosVista = hastaVista - desdeVista;
  const alto = (minutosVista / 60) * PX_HORA;

  const crear = useAccion(
    (cuerpo) => api.post("/disponibilidades/", { agenda: agenda.id, ...cuerpo }),
    {
      onSuccess: (nueva) => {
        toast.ok(`${DIAS[nueva.dia_semana]} de ${hhmm(nueva.desde)} a ${hhmm(nueva.hasta)}.`);
        setSel(nueva.id);
        lista.refetch();
      },
      // El error del backend es el que importa: casi siempre es «se pisa con la
      // franja de 13:00 a 17:00 del mismo día», y ese texto dice exactamente
      // qué corregir.
      onError: (e) => toast.deError(e, "No se pudo agregar la franja."),
    },
  );

  const guardar = useAccion(({ id, ...campos }) => api.patch(`/disponibilidades/${id}/`, campos), {
    onSuccess: () => { toast.ok("Franja actualizada."); lista.refetch(); },
    onError: (e) => toast.deError(e, "No se pudo guardar la franja."),
  });

  const quitar = useAccion((f) => api.del(`/disponibilidades/${f.id}/`), {
    onSuccess: () => { toast.ok("Franja quitada."); setSel(null); lista.refetch(); },
    onError: (e) => toast.deError(e, "No se pudo quitar la franja."),
  });

  const copiar = useAccion(
    async ({ origen, destinos }) => {
      const fuente = franjas.filter((f) => f.dia_semana === origen);
      // De a una y en serie: cada POST valida solapamiento contra lo que ya hay,
      // y en paralelo dos franjas de la misma tanda pueden pasar las dos.
      const hechas = [];
      for (const dia of destinos) {
        for (const f of fuente) {
          const r = await api.post("/disponibilidades/", {
            agenda: agenda.id, dia_semana: dia, desde: f.desde, hasta: f.hasta,
            duracion_min: f.duracion_min, cupos: f.cupos,
            sobreturnos_max: f.sobreturnos_max,
            vigente_desde: f.vigente_desde, vigente_hasta: f.vigente_hasta,
          });
          hechas.push(r);
        }
      }
      return hechas;
    },
    {
      onSuccess: (hechas) => {
        toast.ok(`${hechas.length} franja${hechas.length === 1 ? "" : "s"} copiada${hechas.length === 1 ? "" : "s"}.`);
        setCopiando(null);
        lista.refetch();
      },
      onError: (e) => { setCopiando(null); toast.deError(e, "No se pudieron copiar las franjas."); },
    },
  );

  // Franjas que se pisan: el backend ya las rechaza al guardar, pero las que
  // quedaron cargadas antes de esa regla siguen ahí y la agenda ofrece algo
  // distinto de lo que esta pantalla dibuja. Marcarlas es la única forma de que
  // alguien las arregle.
  const pisadas = useMemo(() => {
    const malas = new Set();
    for (const a of franjas) {
      for (const b of franjas) {
        if (a.id === b.id || a.dia_semana !== b.dia_semana) continue;
        if (aMin(a.desde) < aMin(b.hasta) && aMin(b.desde) < aMin(a.hasta)) {
          malas.add(a.id);
          malas.add(b.id);
        }
      }
    }
    return malas;
  }, [franjas]);

  const total = franjas.reduce((n, f) => n + (f.activa ? f.cuantos_turnos : 0), 0);
  const abierta = franjas.find((f) => f.id === sel) || null;

  return (
    <Modal
      title={`Horarios · ${agenda.nombre}`}
      onClose={onClose}
      width={1000}
      footer={
        <>
          <span className="mr-auto text-sm text-texto-tenue">
            {franjas.length === 0
              ? "Sin franjas: esta agenda todavía no genera ningún turno."
              : `${franjas.length} franja${franjas.length === 1 ? "" : "s"} · ${total} turnos por semana`}
          </span>
          <Button onClick={onClose}>Listo</Button>
        </>
      }
    >
      {lista.error ? (
        <EstadoError error={lista.error} onReintentar={lista.refetch} />
      ) : lista.isLoading ? (
        <Skeleton className="h-96" />
      ) : (
        <div className="flex flex-col gap-3.5">
          <p className="text-sm text-texto-tenue">
            Arrastrá sobre un día para crear una franja, o hacé clic en una para editarla.
            Los turnos de {agenda.duracion_min} min son el valor por defecto: cada franja
            puede tener el suyo.
          </p>

          {pisadas.size > 0 && (
            <div className="flex items-start gap-2 rounded-md bg-badge-error-bg px-3 py-2 text-sm text-danger">
              <Icon name="alert" size={14} className="mt-0.5 flex-none" />
              <span>
                Hay franjas que se pisan (marcadas en rojo). Donde dos franjas se solapan, la
                agenda usa una sola y la otra no da ningún turno: conviene corregir los
                horarios o quitar la que sobra.
              </span>
            </div>
          )}

          <div className="flex flex-col gap-3.5 lg:flex-row">
            <Rejilla
              franjas={franjas}
              pisadas={pisadas}
              sel={sel}
              fantasma={fantasma}
              desdeVista={desdeVista}
              minutosVista={minutosVista}
              alto={alto}
              onElegir={setSel}
              onFantasma={setFantasma}
              onCrear={(dia, desde, hasta) => crear.mutate({
                dia_semana: dia, desde: aHHMM(desde), hasta: aHHMM(hasta),
                duracion_min: null, cupos: 1,
              })}
              onCopiar={setCopiando}
            />

            <div className="lg:w-[290px] lg:flex-none">
              {abierta ? (
                <PanelFranja
                  key={abierta.id}
                  franja={abierta}
                  agenda={agenda}
                  guardando={guardar.isPending}
                  quitando={quitar.isPending}
                  onGuardar={(campos) => guardar.mutate({ id: abierta.id, ...campos })}
                  onQuitar={() => quitar.mutate(abierta)}
                  onCerrar={() => setSel(null)}
                />
              ) : (
                <AltaManual
                  agenda={agenda}
                  creando={crear.isPending}
                  onCrear={(cuerpo) => crear.mutate(cuerpo)}
                />
              )}
            </div>
          </div>
        </div>
      )}

      {copiando !== null && (
        <CopiarDia
          origen={copiando}
          cuantas={franjas.filter((f) => f.dia_semana === copiando).length}
          copiando={copiar.isPending}
          onCopiar={(destinos) => copiar.mutate({ origen: copiando, destinos })}
          onClose={() => setCopiando(null)}
        />
      )}
    </Modal>
  );
}

/** La semana dibujada: siete columnas, las franjas como bloques. */
function Rejilla({
  franjas, pisadas, sel, fantasma, desdeVista, minutosVista, alto,
  onElegir, onFantasma, onCrear, onCopiar,
}) {
  const cuerpo = useRef(null);
  const arrastre = useRef(null);

  const minutosDe = (clientY, caja) => {
    const y = clientY - caja.top;
    return desdeVista + Math.max(0, Math.min(minutosVista, (y / alto) * minutosVista));
  };

  const empezar = (dia) => (e) => {
    // Sólo botón principal, y sólo sobre el fondo: arrancando sobre un bloque el
    // clic es «editar esta franja», no «crear una encima».
    if (e.button !== 0 || e.target.closest("[data-franja]")) return;
    const caja = e.currentTarget.getBoundingClientRect();
    const min = enganchar(minutosDe(e.clientY, caja));
    arrastre.current = { dia, caja, ancla: min };
    e.currentTarget.setPointerCapture?.(e.pointerId);
    onFantasma({ dia, desde: min, hasta: min + PASO_ARRASTRE });
  };

  const mover = (e) => {
    const a = arrastre.current;
    if (!a) return;
    const min = enganchar(minutosDe(e.clientY, a.caja));
    const desde = Math.min(a.ancla, min);
    const hasta = Math.max(a.ancla, min);
    onFantasma({
      dia: a.dia,
      desde,
      // Un arrastre corto es un clic con la mano temblorosa: se toma como una
      // franja de un paso en vez de una de cero minutos, que el backend rechaza.
      hasta: hasta === desde ? desde + PASO_ARRASTRE : hasta,
    });
  };

  const soltar = () => {
    const a = arrastre.current;
    arrastre.current = null;
    if (!a || !fantasma) { onFantasma(null); return; }
    const { dia, desde, hasta } = fantasma;
    onFantasma(null);
    if (hasta > desde) onCrear(dia, desde, hasta);
  };

  const horas = [];
  for (let m = enganchar(desdeVista, 60); m <= desdeVista + minutosVista; m += 60) horas.push(m);

  const arriba = (min) => ((min - desdeVista) / minutosVista) * alto;

  return (
    <div className="min-w-0 flex-1 overflow-x-auto">
      <div className="min-w-[560px]">
        {/* Encabezado: el día y el botón de copiar su horario a otros días. */}
        <div className="flex">
          <div className="w-12 flex-none" />
          {DIAS.map((d, i) => (
            <div key={d} className="flex flex-1 items-center justify-between gap-1 px-1 pb-1">
              <span className="text-sm font-semibold text-texto-suave">{DIAS_CORTO[i]}</span>
              {/* Cargar el mismo horario cinco veces a mano es el trabajo que
                  hace que nadie configure bien la agenda: casi todas las semanas
                  reales repiten el día. */}
              {franjas.some((f) => f.dia_semana === i) && (
                <button
                  onClick={() => onCopiar(i)}
                  title={`Copiar el horario del ${d.toLowerCase()} a otros días`}
                  aria-label={`Copiar el horario del ${d.toLowerCase()} a otros días`}
                  className="inline-flex rounded-md p-0.5 text-texto-debil hover:bg-division hover:text-texto-medio"
                >
                  <Icon name="copy" size={13} />
                </button>
              )}
            </div>
          ))}
        </div>

        <div className="flex" ref={cuerpo}>
          {/* Regla de horas */}
          <div className="relative w-12 flex-none" style={{ height: alto }}>
            {horas.map((m) => (
              <span
                key={m}
                className="absolute right-1 -translate-y-1/2 font-mono text-xs tabular-nums text-texto-tenue"
                style={{ top: arriba(m) }}
              >
                {aHHMM(m)}
              </span>
            ))}
          </div>

          {/* Columnas de los días */}
          {DIAS.map((d, i) => (
            <div
              key={d}
              onPointerDown={empezar(i)}
              onPointerMove={mover}
              onPointerUp={soltar}
              onPointerCancel={soltar}
              className="relative flex-1 touch-none border-l border-division bg-superficie-2/40 last:border-r"
              style={{ height: alto }}
              aria-label={`${d}: arrastrá para crear una franja`}
            >
              {horas.map((m) => (
                <div
                  key={m}
                  className="pointer-events-none absolute inset-x-0 border-t border-division"
                  style={{ top: arriba(m) }}
                />
              ))}

              {franjas.filter((f) => f.dia_semana === i).map((f) => (
                <BloqueFranja
                  key={f.id}
                  franja={f}
                  seleccionada={f.id === sel}
                  pisada={pisadas.has(f.id)}
                  top={arriba(aMin(f.desde))}
                  alto={((aMin(f.hasta) - aMin(f.desde)) / minutosVista) * alto}
                  onElegir={() => onElegir(f.id)}
                />
              ))}

              {fantasma?.dia === i && (
                <div
                  className="pointer-events-none absolute inset-x-1 rounded-md border-2 border-dashed border-accent-100 bg-accent-50/70"
                  style={{
                    top: arriba(fantasma.desde),
                    height: ((fantasma.hasta - fantasma.desde) / minutosVista) * alto,
                  }}
                >
                  <span className="px-1 font-mono text-xs tabular-nums text-accent">
                    {aHHMM(fantasma.desde)}–{aHHMM(fantasma.hasta)}
                  </span>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function BloqueFranja({ franja: f, seleccionada, pisada, top, alto, onElegir }) {
  const detalle = `${f.paso_min} min${f.cupos > 1 ? ` · ${f.cupos} a la vez` : ""}`;
  return (
    <button
      data-franja={f.id}
      onClick={onElegir}
      style={{ top, height: Math.max(alto, 18) }}
      aria-label={
        `${DIAS[f.dia_semana]} de ${hhmm(f.desde)} a ${hhmm(f.hasta)}, ${detalle}, ` +
        `${f.cuantos_turnos} turnos${f.activa ? "" : " (inactiva)"}`
      }
      className={cn(
        "absolute inset-x-1 overflow-hidden rounded-md border px-1 py-0.5 text-left transition-colors",
        pisada
          ? "border-danger bg-badge-error-bg text-danger"
          : !f.activa
            ? "border-division bg-division text-texto-tenue"
            : "border-accent-100 bg-accent-50 text-accent hover:bg-accent-100",
        seleccionada && "ring-2 ring-accent",
      )}
    >
      <span className="block font-mono text-xs font-semibold tabular-nums">
        {hhmm(f.desde)}–{hhmm(f.hasta)}
      </span>
      {/* En una franja de media hora no entra la segunda línea, y recortada a la
          mitad se lee peor que ausente: el detalle completo está en el
          `aria-label` y en el panel. */}
      {alto >= 34 && <span className="block truncate text-xs">{detalle}</span>}
    </button>
  );
}

/** Panel de la franja abierta: lo que la rejilla no puede dibujar. */
function PanelFranja({ franja: f, agenda, guardando, quitando, onGuardar, onQuitar, onCerrar }) {
  const [desde, setDesde] = useState(hhmm(f.desde));
  const [hasta, setHasta] = useState(hhmm(f.hasta));
  const [duracion, setDuracion] = useState(f.duracion_min ?? "");
  const [cupos, setCupos] = useState(f.cupos ?? 1);
  const [sobre, setSobre] = useState(f.sobreturnos_max ?? "");
  const [vDesde, setVDesde] = useState(f.vigente_desde || "");
  const [vHasta, setVHasta] = useState(f.vigente_hasta || "");
  const [activa, setActiva] = useState(f.activa);

  const paso = Number(duracion) || agenda.duracion_min;
  const minutos = aMin(hasta) - aMin(desde);
  // El número que quiere ver quien carga la franja, calculado como lo calcula el
  // backend: horarios × personas por horario.
  const cuantos = minutos > 0 && paso > 0
    ? Math.floor(minutos / paso) * (Number(cupos) || 1)
    : 0;

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-borde bg-superficie-2 p-3">
      <div className="flex items-center justify-between gap-2">
        <span className="text-md font-bold">{DIAS[f.dia_semana]}</span>
        <button
          onClick={onCerrar}
          aria-label="Cerrar la franja"
          className="inline-flex rounded-md p-1 text-texto-debil hover:bg-division hover:text-texto-medio"
        >
          <Icon name="x" size={14} />
        </button>
      </div>

      <div className="grid grid-cols-2 gap-2.5">
        <Field label="Desde">
          <Input type="time" size="sm" value={desde} onChange={(e) => setDesde(e.target.value)} />
        </Field>
        <Field label="Hasta">
          <Input type="time" size="sm" value={hasta} onChange={(e) => setHasta(e.target.value)} />
        </Field>
      </div>

      <div className="grid grid-cols-2 gap-2.5">
        <Field label="Turno (min)" hint={`Vacío: ${agenda.duracion_min}`}>
          <Input type="number" min="5" step="5" size="sm" value={duracion}
                 placeholder={String(agenda.duracion_min)}
                 onChange={(e) => setDuracion(e.target.value)} />
        </Field>
        {/* Personas por horario: uno es el consultorio, más de uno es el
            vacunatorio o la sala de enfermería, donde tres puestos atienden a
            las 10 en paralelo. */}
        <Field label="Personas a la vez" hint="1 = un consultorio">
          <Input type="number" min="1" size="sm" value={cupos}
                 onChange={(e) => setCupos(e.target.value)} />
        </Field>
      </div>

      <Field label="Sobreturnos por horario" hint={`Vacío: los de la agenda (${agenda.sobreturnos_max})`}>
        <Input type="number" min="0" size="sm" value={sobre}
               placeholder={String(agenda.sobreturnos_max)}
               onChange={(e) => setSobre(e.target.value)} />
      </Field>

      {/* La vigencia es lo que permite cargar el horario nuevo sin borrar el
          viejo, y es lo que deja intactos los turnos ya dados con el anterior. */}
      <div className="grid grid-cols-2 gap-2.5">
        <Field label="Rige desde" hint="Opcional">
          <Input type="date" size="sm" value={vDesde} onChange={(e) => setVDesde(e.target.value)} />
        </Field>
        <Field label="Rige hasta" hint="Opcional">
          <Input type="date" size="sm" value={vHasta} onChange={(e) => setVHasta(e.target.value)} />
        </Field>
      </div>

      <label className="flex items-center gap-2 text-base">
        <input type="checkbox" checked={activa} onChange={(e) => setActiva(e.target.checked)} />
        Activa
      </label>

      <div className="rounded-md bg-superficie px-2.5 py-1.5 text-sm text-texto-suave">
        {minutos <= 0
          ? "La franja tiene que terminar después de empezar."
          : `${Math.floor(minutos / paso)} horario${Math.floor(minutos / paso) === 1 ? "" : "s"} de ${paso} min · ${cuantos} turnos`}
      </div>

      <div className="flex items-center gap-2">
        <Button
          size="sm"
          disabled={guardando || minutos <= 0}
          onClick={() => onGuardar({
            desde, hasta,
            duracion_min: duracion === "" ? null : Number(duracion),
            cupos: Number(cupos) || 1,
            sobreturnos_max: sobre === "" ? null : Number(sobre),
            vigente_desde: vDesde || null,
            vigente_hasta: vHasta || null,
            activa,
          })}
        >
          {guardando ? "…" : "Guardar"}
        </Button>
        <button
          onClick={onQuitar}
          disabled={quitando}
          title="Quitar la franja"
          aria-label={`Quitar ${DIAS[f.dia_semana]} de ${hhmm(f.desde)} a ${hhmm(f.hasta)}`}
          className="ml-auto inline-flex rounded-md p-1 text-texto-debil hover:bg-badge-error-bg hover:text-danger"
        >
          <Icon name="trash" size={15} />
        </button>
      </div>
    </div>
  );
}

/**
 * Alta escrita, para cuando no hay franja abierta.
 *
 * No es un duplicado del arrastre: es la vía de teclado —el arrastre no existe
 * para quien no usa mouse— y la forma de poner 07:45 exacto, que enganchado a la
 * media hora la rejilla no puede dar.
 */
function AltaManual({ agenda, creando, onCrear }) {
  const [dia, setDia] = useState(0);
  const [desde, setDesde] = useState("08:00");
  const [hasta, setHasta] = useState("12:00");
  const [duracion, setDuracion] = useState("");
  const [cupos, setCupos] = useState(1);

  const paso = Number(duracion) || agenda.duracion_min;
  const minutos = aMin(hasta) - aMin(desde);
  const cuantos = minutos > 0 && paso > 0
    ? Math.floor(minutos / paso) * (Number(cupos) || 1)
    : 0;

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-borde bg-superficie-2 p-3">
      <div className="text-md font-bold">Agregar una franja</div>
      <Field label="Día">
        <Select size="sm" value={dia} onChange={(e) => setDia(Number(e.target.value))}>
          {DIAS.map((d, i) => <option key={d} value={i}>{d}</option>)}
        </Select>
      </Field>
      <div className="grid grid-cols-2 gap-2.5">
        <Field label="Desde">
          <Input type="time" size="sm" value={desde} onChange={(e) => setDesde(e.target.value)} />
        </Field>
        <Field label="Hasta">
          <Input type="time" size="sm" value={hasta} onChange={(e) => setHasta(e.target.value)} />
        </Field>
      </div>
      <div className="grid grid-cols-2 gap-2.5">
        <Field label="Turno (min)" hint={`Vacío: ${agenda.duracion_min}`}>
          <Input type="number" min="5" step="5" size="sm" value={duracion}
                 placeholder={String(agenda.duracion_min)}
                 onChange={(e) => setDuracion(e.target.value)} />
        </Field>
        <Field label="Personas a la vez" hint="1 = un consultorio">
          <Input type="number" min="1" size="sm" value={cupos}
                 onChange={(e) => setCupos(e.target.value)} />
        </Field>
      </div>
      <div className="rounded-md bg-superficie px-2.5 py-1.5 text-sm text-texto-suave">
        {minutos > 0
          ? `Genera ${cuantos} turno${cuantos === 1 ? "" : "s"} de ${paso} min.`
          : "La franja tiene que terminar después de empezar."}
      </div>
      <Button
        size="sm"
        disabled={creando || cuantos === 0}
        onClick={() => onCrear({
          dia_semana: dia, desde, hasta,
          duracion_min: duracion === "" ? null : Number(duracion),
          cupos: Number(cupos) || 1,
        })}
      >
        {creando ? "…" : "Agregar"}
      </Button>
    </div>
  );
}

/** «Copiar el lunes a…»: los días destino, con lo que ya tienen a la vista. */
function CopiarDia({ origen, cuantas, copiando, onCopiar, onClose }) {
  const [sel, setSel] = useState(() => new Set());
  const alternar = (i) => setSel((p) => {
    const n = new Set(p);
    if (n.has(i)) n.delete(i); else n.add(i);
    return n;
  });

  return (
    <Modal
      title={`Copiar el ${DIAS[origen].toLowerCase()} a otros días`}
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancelar</Button>
          <Button disabled={copiando || sel.size === 0}
                  onClick={() => onCopiar([...sel].sort())}>
            {copiando ? "…" : `Copiar a ${sel.size} día${sel.size === 1 ? "" : "s"}`}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-2">
        <p className="text-base text-texto-suave">
          Se copian las {cuantas} franja{cuantas === 1 ? "" : "s"} del {DIAS[origen].toLowerCase()},
          con su duración, sus cupos y su vigencia. Si el día destino ya tiene una franja que
          se pisa con alguna, la copia se rechaza y no se cambia nada.
        </p>
        <div className="flex flex-wrap gap-1.5">
          {DIAS.map((d, i) => i !== origen && (
            <button
              key={d}
              onClick={() => alternar(i)}
              aria-pressed={sel.has(i)}
              className={cn(
                "rounded-md border px-2.5 py-1.5 text-base font-semibold transition-colors",
                sel.has(i)
                  ? "border-accent-100 bg-accent-50 text-accent"
                  : "border-division text-texto-suave hover:bg-superficie-2",
              )}
            >
              {d}
            </button>
          ))}
        </div>
      </div>
    </Modal>
  );
}
