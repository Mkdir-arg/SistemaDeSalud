import { useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/api/client";
import { useAccion, useLista } from "@/api/queries";
import { Icon } from "@/components/icons";
import { Badge, Button, Field, Input, Modal } from "@/components/ui";
import { EstadoError, Skeleton } from "@/components/ui/estados";
import { useToast } from "@/components/ui/toast";
import { cn } from "@/lib/cn";

/*
 * La semana de una agenda: ver y bloquear.
 *
 * La grilla del día contesta «¿qué tiene la doctora hoy?»; la pregunta que
 * quedaba sin pantalla es la otra —«¿para cuándo tiene?», «¿cómo viene la
 * semana?»—, y con la vista de un día se contestaba apretando «Día siguiente»
 * siete veces.
 *
 * Acá NO se opera turno por turno a propósito: registrar una llegada o marcar un
 * ausente se hace parado en el día, con el paciente enfrente, y esas dos
 * acciones no se pueden deshacer. Un clic en un horario salta al día, que es
 * donde están los botones. Lo que sí vive acá es el bloqueo —vacaciones, un
 * feriado, el equipo en mantenimiento—, porque se piensa en rangos de días y no
 * en horarios sueltos.
 */

const DIAS_CORTO = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"];
const PX_HORA = 40;
const PASO_ARRASTRE = 30;

const minDe = (iso) => {
  const d = new Date(iso);
  return d.getHours() * 60 + d.getMinutes();
};
const aHHMM = (min) => {
  const m = Math.max(0, Math.min(24 * 60, Math.round(min)));
  return `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
};
const enganchar = (min, paso = PASO_ARRASTRE) => Math.round(min / paso) * paso;
const hhmm = (iso) =>
  new Date(iso).toLocaleTimeString("es-AR", { hour: "2-digit", minute: "2-digit", hour12: false });
const soloFecha = (d) =>
  new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
// Momento local → ISO con zona, que es lo que espera el backend para un bloqueo.
const momento = (fecha, min) => new Date(`${fecha}T${aHHMM(min)}:00`).toISOString();

/** El lunes de la semana que contiene esa fecha (ISO `YYYY-MM-DD`). */
export function lunesDe(fechaIso) {
  const d = new Date(`${fechaIso}T12:00:00`);
  d.setDate(d.getDate() - ((d.getDay() + 6) % 7));
  return soloFecha(d);
}

export function SemanaAgenda({ agenda, desde, onIrAlDia, toast: toastPadre }) {
  // El hook va siempre —llamarlo condicionalmente rompe el orden de hooks—; el
  // del padre gana para que los avisos salgan por el mismo lugar que los de la
  // grilla del día.
  const propio = useToast();
  const toast = toastPadre || propio;
  const [bloqueando, setBloqueando] = useState(null); // { fecha, desde, hasta }
  const [fantasma, setFantasma] = useState(null);

  const semana = useQuery({
    queryKey: ["agenda-semana", agenda?.id, desde],
    queryFn: () => api.get(`/agendas/${agenda.id}/semana/?desde=${desde}`),
    enabled: agenda?.id != null,
  });
  const dias = semana.data?.dias || [];
  const hasta = useMemo(() => {
    const d = new Date(`${desde}T12:00:00`);
    d.setDate(d.getDate() + 6);
    return soloFecha(d);
  }, [desde]);

  // Los bloqueos de la semana: se dibujan encima de la grilla porque un horario
  // bloqueado con turnos dados sigue apareciendo —esos pacientes tienen hora y
  // hay que llamarlos—, y sin la banda no se distingue del que está libre.
  const bloqueos = useLista(
    "bloqueos-agenda",
    { agenda: agenda?.id, desde, hasta, pageSize: 100 },
    { enabled: agenda?.id != null },
  );

  const recargar = () => { semana.refetch(); bloqueos.refetch(); };

  const [desdeVista, hastaVista] = useMemo(() => {
    let min = 8 * 60, max = 20 * 60;
    for (const d of dias) {
      for (const h of d.horarios) {
        min = Math.min(min, minDe(h.inicio) - 30);
        max = Math.max(max, minDe(h.inicio) + (h.duracion_min || 20) + 30);
      }
    }
    for (const b of bloqueos.filas) {
      // Sólo la parte del bloqueo que cae en un día de la semana mirada; los
      // bloqueos de varios días arrancan a las 00:00 y estirarían la rejilla
      // entera a 24 horas por nada.
      if (b.desde.slice(0, 10) >= desde && b.desde.slice(0, 10) <= hasta) {
        min = Math.min(min, Math.max(6 * 60, minDe(b.desde)));
      }
    }
    return [Math.max(0, enganchar(min, 60)), Math.min(24 * 60, enganchar(max, 60))];
  }, [dias, bloqueos.filas, desde, hasta]);
  const minutosVista = Math.max(60, hastaVista - desdeVista);
  const alto = (minutosVista / 60) * PX_HORA;
  const arriba = (min) => ((min - desdeVista) / minutosVista) * alto;

  const horas = [];
  for (let m = enganchar(desdeVista, 60); m <= desdeVista + minutosVista; m += 60) horas.push(m);

  if (semana.error) {
    return <EstadoError error={semana.error} onReintentar={semana.refetch} />;
  }

  return (
    <section className="rounded-lg border border-borde bg-superficie px-xl py-lg">
      <div className="mb-2 flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h3 className="text-md font-bold">Semana</h3>
        <span className="text-sm text-texto-tenue">
          Clic en un horario para ir a ese día · arrastrá sobre un día para bloquear un rango
        </span>
      </div>

      {semana.isLoading ? (
        <Skeleton className="h-72" />
      ) : (
        <div className="overflow-x-auto">
          <div className="min-w-[620px]">
            <div className="flex">
              <div className="w-12 flex-none" />
              {dias.map((d, i) => (
                <button
                  key={d.fecha}
                  onClick={() => onIrAlDia(d.fecha)}
                  className="flex-1 px-1 pb-1 text-left hover:text-accent"
                >
                  <span className="block text-sm font-semibold text-texto-suave">
                    {DIAS_CORTO[i]} {d.fecha.slice(8, 10)}/{d.fecha.slice(5, 7)}
                  </span>
                  <span className="block text-xs text-texto-tenue">
                    {resumenDia(d.horarios)}
                  </span>
                </button>
              ))}
            </div>

            <div className="flex">
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

              {dias.map((d) => (
                <ColumnaDia
                  key={d.fecha}
                  dia={d}
                  bloqueos={bloqueos.filas}
                  alto={alto}
                  desdeVista={desdeVista}
                  minutosVista={minutosVista}
                  horas={horas}
                  arriba={arriba}
                  fantasma={fantasma?.fecha === d.fecha ? fantasma : null}
                  onFantasma={setFantasma}
                  onBloquear={(rango) => setBloqueando(rango)}
                  onIrAlDia={onIrAlDia}
                />
              ))}
            </div>
          </div>
        </div>
      )}

      <Referencias />

      {bloqueos.filas.length > 0 && (
        <ListaBloqueos lista={bloqueos} toast={toast} onCambio={recargar} />
      )}

      {bloqueando && (
        <BloquearRango
          agenda={agenda}
          rango={bloqueando}
          toast={toast}
          onListo={() => { setBloqueando(null); recargar(); }}
          onClose={() => setBloqueando(null)}
        />
      )}
    </section>
  );
}

/** «6 dados · 4 libres», que es lo que se busca al mirar la semana de reojo. */
function resumenDia(horarios) {
  const enGrilla = horarios.filter((h) => !h.fuera_de_grilla);
  if (enGrilla.length === 0) return "no atiende";
  const dados = enGrilla.reduce((n, h) => n + (h.titulares || 0) + (h.sobreturnos || 0), 0);
  const libres = enGrilla.reduce((n, h) => n + (h.bloqueado ? 0 : (h.libres ?? 0)), 0);
  return `${dados} dados · ${libres} libres`;
}

function ColumnaDia({
  dia, bloqueos, alto, desdeVista, minutosVista, horas, arriba,
  fantasma, onFantasma, onBloquear, onIrAlDia,
}) {
  const arrastre = useRef(null);

  const minutosDe = (clientY, caja) => {
    const y = clientY - caja.top;
    return desdeVista + Math.max(0, Math.min(minutosVista, (y / alto) * minutosVista));
  };

  const empezar = (e) => {
    if (e.button !== 0 || e.target.closest("[data-horario]")) return;
    const caja = e.currentTarget.getBoundingClientRect();
    const min = enganchar(minutosDe(e.clientY, caja));
    arrastre.current = { caja, ancla: min };
    e.currentTarget.setPointerCapture?.(e.pointerId);
    onFantasma({ fecha: dia.fecha, desde: min, hasta: min + PASO_ARRASTRE });
  };
  const mover = (e) => {
    const a = arrastre.current;
    if (!a) return;
    const min = enganchar(minutosDe(e.clientY, a.caja));
    const d = Math.min(a.ancla, min);
    const h = Math.max(a.ancla, min);
    onFantasma({ fecha: dia.fecha, desde: d, hasta: h === d ? d + PASO_ARRASTRE : h });
  };
  const soltar = () => {
    const a = arrastre.current;
    arrastre.current = null;
    if (!a || !fantasma) { onFantasma(null); return; }
    const rango = fantasma;
    onFantasma(null);
    if (rango.hasta > rango.desde) onBloquear(rango);
  };

  // Los bloqueos que tocan este día, recortados al día: el que va del viernes al
  // martes tapa el lunes entero y tiene que dibujarse de arriba a abajo.
  const bandas = bloqueos
    .map((b) => {
      const d1 = b.desde.slice(0, 10), d2 = b.hasta.slice(0, 10);
      if (dia.fecha < d1 || dia.fecha > d2) return null;
      return {
        id: b.id,
        motivo: b.motivo,
        desde: dia.fecha === d1 ? minDe(b.desde) : desdeVista,
        hasta: dia.fecha === d2 ? minDe(b.hasta) : desdeVista + minutosVista,
      };
    })
    .filter(Boolean);

  return (
    <div
      onPointerDown={empezar}
      onPointerMove={mover}
      onPointerUp={soltar}
      onPointerCancel={soltar}
      className="relative flex-1 touch-none border-l border-division bg-superficie-2/40 last:border-r"
      style={{ height: alto }}
      aria-label={`${dia.fecha}: arrastrá para bloquear un rango`}
    >
      {horas.map((m) => (
        <div
          key={m}
          className="pointer-events-none absolute inset-x-0 border-t border-division"
          style={{ top: arriba(m) }}
        />
      ))}

      {bandas.map((b) => (
        <div
          key={b.id}
          title={b.motivo || "Bloqueado"}
          className="pointer-events-none absolute inset-x-0 border-y border-danger/40 bg-badge-error-bg/60"
          style={{ top: arriba(b.desde), height: Math.max(2, arriba(b.hasta) - arriba(b.desde)) }}
        />
      ))}

      {dia.horarios.filter((h) => !h.fuera_de_grilla).map((h) => (
        <BloqueHorario
          key={h.inicio}
          horario={h}
          top={arriba(minDe(h.inicio))}
          alto={((h.duracion_min || 20) / minutosVista) * alto}
          onClic={() => onIrAlDia(dia.fecha)}
        />
      ))}

      {fantasma && (
        <div
          className="pointer-events-none absolute inset-x-1 rounded-md border-2 border-dashed border-danger bg-badge-error-bg/70"
          style={{
            top: arriba(fantasma.desde),
            height: ((fantasma.hasta - fantasma.desde) / minutosVista) * alto,
          }}
        >
          <span className="px-1 font-mono text-xs tabular-nums text-danger">
            {aHHMM(fantasma.desde)}–{aHHMM(fantasma.hasta)}
          </span>
        </div>
      )}
    </div>
  );
}

function BloqueHorario({ horario: h, top, alto, onClic }) {
  const cupos = h.cupos ?? 1;
  const libres = h.libres ?? (h.ocupado ? 0 : 1);
  const dados = (h.titulares || 0) + (h.sobreturnos || 0);
  const etiqueta =
    h.bloqueado ? "bloqueado"
      : libres === 0 ? "completo"
        : cupos > 1 ? `${libres} de ${cupos} libres`
          : "libre";

  return (
    <button
      data-horario={h.inicio}
      onClick={onClic}
      style={{ top, height: Math.max(alto, 14) }}
      aria-label={`${hhmm(h.inicio)} · ${etiqueta}${dados ? ` · ${dados} dados` : ""} · ir a este día`}
      className={cn(
        "absolute inset-x-1 overflow-hidden rounded-sm border px-1 text-left text-xs leading-tight transition-colors",
        h.bloqueado
          ? "border-danger/40 bg-badge-error-bg text-danger"
          : libres === 0
            ? "border-accent-100 bg-accent-50 text-accent hover:bg-accent-100"
            : "border-division bg-superficie text-texto-tenue hover:border-accent-100",
      )}
    >
      <span className="font-mono tabular-nums">{hhmm(h.inicio)}</span>
      {h.sobreturnos > 0 && <span className="ml-1 font-bold">+{h.sobreturnos}</span>}
      {cupos > 1 && !h.bloqueado && <span className="ml-1">{dados}/{cupos}</span>}
    </button>
  );
}

function Referencias() {
  return (
    <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-texto-tenue">
      <span className="inline-flex items-center gap-1">
        <span className="size-2.5 rounded-sm border border-division bg-superficie" /> con lugar
      </span>
      <span className="inline-flex items-center gap-1">
        <span className="size-2.5 rounded-sm border border-accent-100 bg-accent-50" /> completo
      </span>
      <span className="inline-flex items-center gap-1">
        <span className="size-2.5 rounded-sm border border-danger/40 bg-badge-error-bg" /> bloqueado
      </span>
      <span>+N: sobreturnos dados en ese horario</span>
    </div>
  );
}

/**
 * Bloquear un rango.
 *
 * Bloquear NO cancela los turnos: los que ya estaban dados siguen dados, y el
 * backend devuelve la lista para poder llamar a esa gente. Sin mostrarla, el
 * bloqueo de las 7 de la mañana pisa doce turnos y esos doce pacientes viajan al
 * hospital para nada.
 */
function BloquearRango({ agenda, rango, toast, onListo, onClose }) {
  const [motivo, setMotivo] = useState("");
  const [afectados, setAfectados] = useState(null);

  const bloquear = useAccion(
    () => api.post("/bloqueos-agenda/", {
      agenda: agenda.id,
      desde: momento(rango.fecha, rango.desde),
      hasta: momento(rango.fecha, rango.hasta),
      motivo: motivo.trim(),
    }),
    {
      onSuccess: (r) => {
        const lista = r?.turnos_afectados || [];
        toast.ok(
          lista.length
            ? `Bloqueado · ${lista.length} turno${lista.length === 1 ? "" : "s"} adentro del rango`
            : "Bloqueado",
        );
        // Con turnos adentro el diálogo no se cierra: la lista de a quién llamar
        // es el motivo por el que el backend la devuelve, y cerrando se pierde.
        if (lista.length) setAfectados(lista);
        else onListo();
      },
      onError: (e) => toast.deError(e, "No se pudo bloquear."),
    },
  );

  if (afectados) {
    return (
      <Modal
        title="Bloqueado · hay que llamar a estos pacientes"
        onClose={onListo}
        width={520}
        footer={<Button onClick={onListo}>Listo</Button>}
      >
        <div className="flex flex-col gap-2">
          <p className="text-base text-texto-suave">
            El bloqueo no cancela nada: estos turnos siguen dados. Hay que llamar y
            reprogramarlos, o cancelarlos desde la grilla del día.
          </p>
          <ul className="divide-y divide-division overflow-hidden rounded-md border border-borde">
            {afectados.map((t) => (
              <li key={t.id} className="flex items-center gap-2 px-3 py-2 text-base">
                <span className="font-mono tabular-nums">{hhmm(t.inicio)}</span>
                <span className="min-w-0 flex-1 truncate font-semibold">{t.paciente}</span>
                {t.documento && <span className="text-sm text-texto-tenue">doc. {t.documento}</span>}
                <Badge tone={t.estado === "confirmado" ? "green" : "info"}>{t.estado_display}</Badge>
              </li>
            ))}
          </ul>
        </div>
      </Modal>
    );
  }

  return (
    <Modal
      title="Bloquear un rango"
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancelar</Button>
          <Button disabled={bloquear.isPending} onClick={() => bloquear.mutate()}>
            {bloquear.isPending ? "…" : "Bloquear"}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3">
        <p className="text-base text-texto-suave">
          {rango.fecha.slice(8, 10)}/{rango.fecha.slice(5, 7)} de{" "}
          <strong>{aHHMM(rango.desde)}</strong> a <strong>{aHHMM(rango.hasta)}</strong>. La agenda
          no va a ofrecer esos horarios; los turnos ya dados siguen dados.
        </p>
        <Field label="Motivo" hint="Aparece en la banda del bloqueo: vacaciones, feriado, mantenimiento…">
          <Input value={motivo} onChange={(e) => setMotivo(e.target.value)}
                 placeholder="Congreso" autoFocus />
        </Field>
      </div>
    </Modal>
  );
}

function ListaBloqueos({ lista, toast, onCambio }) {
  const quitar = useAccion((b) => api.del(`/bloqueos-agenda/${b.id}/`), {
    onSuccess: () => { toast.ok("Bloqueo quitado."); onCambio(); },
    onError: (e) => toast.deError(e, "No se pudo quitar el bloqueo."),
  });

  return (
    <div className="mt-3 border-t border-division pt-2.5">
      <div className="mb-1.5 text-sm font-semibold text-texto-suave">Bloqueos de esta semana</div>
      <ul className="flex flex-col gap-1">
        {lista.filas.map((b) => (
          <li key={b.id} className="flex items-center gap-2 text-base">
            <Icon name="alert" size={13} className="flex-none text-danger" />
            <span className="font-mono text-sm tabular-nums">
              {b.desde.slice(8, 10)}/{b.desde.slice(5, 7)} {hhmm(b.desde)}–{hhmm(b.hasta)}
            </span>
            <span className="min-w-0 flex-1 truncate text-texto-suave">{b.motivo || "sin motivo"}</span>
            <button
              onClick={() => quitar.mutate(b)}
              disabled={quitar.isPending}
              title="Quitar el bloqueo"
              aria-label={`Quitar el bloqueo del ${b.desde.slice(8, 10)}/${b.desde.slice(5, 7)}`}
              className="inline-flex rounded-md p-1 text-texto-debil hover:bg-badge-error-bg hover:text-danger"
            >
              <Icon name="trash" size={14} />
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
