import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/api/client";
import { useAccion, useLista } from "@/api/queries";
import { useInstitucion } from "@/auth/InstitutionContext";
import { Icon } from "@/components/icons";
import { Badge, Button, Input } from "@/components/ui";
import { EstadoError, EstadoVacio, Skeleton } from "@/components/ui/estados";
import { useToast } from "@/components/ui/toast";
import { cn } from "@/lib/cn";

/*
 * Grilla del día de una agenda.
 *
 * Se muestran TODOS los horarios, ocupados incluidos. Quien atiende el
 * mostrador necesita la grilla completa para poder decir «a las 10 está con
 * otro paciente, ¿le sirve 10:20?»; con una lista de huecos libres esa
 * conversación no se puede tener.
 */
const ESTADOS = {
  reservado: { label: "Reservado", tone: "info" },
  confirmado: { label: "Confirmado", tone: "success" },
  presente: { label: "Se presentó", tone: "success" },
  ausente: { label: "No vino", tone: "error" },
  cancelado: { label: "Cancelado", tone: "neutral" },
};

// 24 horas: es cómo se escriben los horarios en un hospital, y además «02:15
// p. m.» no entra en la columna y parte el renglón en dos líneas.
const hhmm = (iso) =>
  new Date(iso).toLocaleTimeString("es-AR", { hour: "2-digit", minute: "2-digit", hour12: false });

const iso = (d) => d.toISOString().slice(0, 10);

export default function Agenda() {
  const { institucion } = useInstitucion();
  const toast = useToast();
  const [agendaSel, setAgendaSel] = useState(null);
  const [fecha, setFecha] = useState(() => iso(new Date()));

  const agendas = useLista(
    "agendas",
    { institucion: institucion?.id, activa: true, pageSize: 100 },
    { enabled: institucion?.id != null },
  );
  const lista = agendas.filas;
  const agenda = lista.find((a) => a.id === agendaSel) || lista[0];

  const dia = useQuery({
    queryKey: ["agenda-dia", agenda?.id, fecha],
    queryFn: () => api.get(`/agendas/${agenda.id}/dia/?fecha=${fecha}`),
    enabled: agenda?.id != null,
  });
  const horarios = dia.data?.horarios || [];

  // Los turnos del día, para poder mostrar los sobreturnos —que no ocupan un
  // renglón propio de la grilla: cuelgan del horario que sobreturnean—.
  const turnos = useQuery({
    queryKey: ["agenda-turnos", agenda?.id, fecha],
    queryFn: () => api.get(`/turnos/?agenda=${agenda.id}&desde=${fecha}&hasta=${fecha}&page_size=200`),
    enabled: agenda?.id != null,
  });
  const porHorario = useMemo(() => {
    const m = new Map();
    for (const t of turnos.data?.results || []) {
      if (t.estado === "cancelado") continue;
      const k = new Date(t.inicio).getTime();
      if (!m.has(k)) m.set(k, []);
      m.get(k).push(t);
    }
    return m;
  }, [turnos.data]);

  const recargar = () => { dia.refetch(); turnos.refetch(); };

  const ocupados = horarios.filter((h) => h.ocupado).length;
  const mover = (dias) => {
    const d = new Date(fecha + "T12:00:00");
    d.setDate(d.getDate() + dias);
    setFecha(iso(d));
  };

  if (agendas.isLoading) return <Cargando />;
  if (agendas.error) {
    return <div className="p-[30px]"><EstadoError error={agendas.error} onReintentar={agendas.refetch} /></div>;
  }
  if (lista.length === 0) {
    return (
      <div className="p-lg sm:p-[26px] lg:px-[30px]">
        <EstadoVacio
          titulo="No hay agendas cargadas"
          detalle="Creá una en Estructura organizativa para empezar a dar turnos."
          icono="calendar"
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-lg p-lg sm:p-[26px] lg:px-[30px]">
      <section className="flex flex-wrap items-center gap-lg rounded-lg border border-borde bg-superficie px-xl py-lg">
        <span className="flex size-11 shrink-0 items-center justify-center rounded-md bg-nodo-espera-tint text-nodo-espera-sol">
          <Icon name="calendar" size={22} />
        </span>
        <div className="min-w-40 flex-1">
          <h2 className="text-xl font-bold">Turnos programados</h2>
          <p className="text-base text-texto-debil">
            {agenda?.area_nombre}
            {agenda?.tipo === "recurso" && " · recurso"}
            {agenda?.duracion_min && ` · turnos de ${agenda.duracion_min} min`}
          </p>
        </div>
        {lista.length > 1 && (
          <select
            aria-label="Agenda"
            value={agenda?.id ?? ""}
            onChange={(e) => setAgendaSel(Number(e.target.value))}
            className="h-9 rounded-md border border-campo-borde bg-superficie px-2 text-md outline-none focus:border-accent"
          >
            {lista.map((a) => <option key={a.id} value={a.id}>{a.nombre}</option>)}
          </select>
        )}
        <div className="text-right">
          <div className="text-cifra font-extrabold leading-none tabular-nums">
            {ocupados}/{horarios.length}
          </div>
          <div className="text-xs text-texto-tenue">dados</div>
        </div>
      </section>

      {/* Navegación por día */}
      <section className="flex flex-wrap items-center gap-2 rounded-lg border border-borde bg-superficie px-xl py-3">
        <Button size="sm" variant="secondary" onClick={() => mover(-1)}>
          <Icon name="chevronLeft" size={14} /> Día anterior
        </Button>
        <Button size="sm" variant="secondary" onClick={() => setFecha(iso(new Date()))}>Hoy</Button>
        <Button size="sm" variant="secondary" onClick={() => mover(1)}>
          Día siguiente <Icon name="chevronRight" size={14} />
        </Button>
        <Input
          type="date"
          value={fecha}
          onChange={(e) => setFecha(e.target.value)}
          aria-label="Fecha de la agenda"
          className="ml-auto w-auto"
        />
      </section>

      <section className="overflow-hidden rounded-lg border border-borde bg-superficie">
        {dia.isLoading ? (
          <div className="p-xl"><Skeleton className="h-64" /></div>
        ) : horarios.length === 0 ? (
          /* Que no haya horarios no es un error: la agenda no atiende ese día.
             Decirlo evita que alguien crea que el sistema falló. */
          <EstadoVacio
            titulo="La agenda no atiende este día"
            detalle="Elegí otra fecha, o cargá una franja de atención desde Estructura organizativa."
            icono="calendar"
          />
        ) : (
          <ul className="divide-y divide-division">
            {horarios.map((h) => (
              <Renglon
                key={h.inicio}
                horario={h}
                agenda={agenda}
                turnos={porHorario.get(new Date(h.inicio).getTime()) || []}
                onCambio={recargar}
                toast={toast}
              />
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function Renglon({ horario, agenda, turnos, onCambio, toast }) {
  const navigate = useNavigate();
  const [dando, setDando] = useState(false);
  // El turno «titular» del horario y los sobreturnos que cuelgan de él.
  const titular = turnos.find((t) => !t.sobreturno);
  const extras = turnos.filter((t) => t.sobreturno);

  return (
    <li className={cn("px-xl py-3", horario.ocupado ? "" : "bg-superficie-2/40")}>
      <div className="flex flex-wrap items-center gap-x-md gap-y-2">
        <span className="w-14 shrink-0 font-mono text-md font-bold tabular-nums">
          {hhmm(horario.inicio)}
        </span>
        {titular ? (
          <FichaTurno turno={titular} onCambio={onCambio} toast={toast} navigate={navigate} />
        ) : (
          <>
            <span className="flex-1 text-base text-texto-tenue">libre</span>
            <Button size="sm" variant="secondary" onClick={() => setDando(!dando)}>
              {dando ? "Cancelar" : "Dar turno"}
            </Button>
          </>
        )}
        {/* El sobreturno se ofrece sólo donde tiene sentido —sobre un horario
            ocupado y mientras queden cupos— y sin peso visual: es excepcional, y
            repetido en cada renglón convertía la grilla en una pared de botones. */}
        {titular && horario.admite_sobreturno && (
          <button
            onClick={() => setDando(!dando)}
            title="Agregar un sobreturno en este horario"
            aria-label={`Agregar un sobreturno a las ${hhmm(horario.inicio)}`}
            className="flex size-7 flex-none items-center justify-center rounded-md text-texto-tenue transition-colors hover:bg-division hover:text-texto-medio"
          >
            <Icon name={dando ? "x" : "plus"} size={14} />
          </button>
        )}
      </div>

      {extras.map((t) => (
        <div key={t.id} className="mt-2 flex flex-wrap items-center gap-x-md gap-y-2 pl-14">
          <Badge tone="warning">sobreturno</Badge>
          <FichaTurno turno={t} onCambio={onCambio} toast={toast} navigate={navigate} />
        </div>
      ))}

      {dando && (
        <DarTurno
          agenda={agenda}
          inicio={horario.inicio}
          sobreturno={!!titular}
          onListo={() => { setDando(false); onCambio(); }}
          onCancelar={() => setDando(false)}
          toast={toast}
        />
      )}
    </li>
  );
}

function FichaTurno({ turno, onCambio, toast, navigate }) {
  const est = ESTADOS[turno.estado] || { label: turno.estado, tone: "neutral" };
  const accion = useAccion(({ nombre }) => api.post(`/turnos/${turno.id}/${nombre}/`), {
    onSuccess: (_, { ok }) => { toast.ok(ok); onCambio(); },
    onError: (e) => toast.deError(e),
  });
  const pendiente = ["reservado", "confirmado"].includes(turno.estado);

  return (
    <>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-md font-semibold">{turno.paciente}</span>
        {turno.motivo && (
          <span className="block truncate text-sm text-texto-tenue">{turno.motivo}</span>
        )}
      </span>
      <Badge tone={est.tone}>{est.label}</Badge>
      {turno.caso && (
        <Button size="sm" variant="secondary" onClick={() => navigate(`/casos/${turno.caso}`)}>
          Ver caso
        </Button>
      )}
      {pendiente && (
        <div className="flex flex-wrap gap-1.5">
          {/* «Llegó» es la acción principal: es la que abre el caso y arranca la
              atención. El resto son excepciones. */}
          <Button size="sm" disabled={accion.isPending}
                  onClick={() => accion.mutate({ nombre: "llegada", ok: `${turno.paciente} llegó · caso abierto` })}>
            Llegó
          </Button>
          <Button size="sm" variant="secondary" disabled={accion.isPending}
                  onClick={() => accion.mutate({ nombre: "ausente", ok: "Marcado como ausente" })}>
            No vino
          </Button>
          <Button size="sm" variant="secondary" disabled={accion.isPending}
                  onClick={() => accion.mutate({ nombre: "cancelar", ok: "Turno cancelado · horario liberado" })}>
            Cancelar
          </Button>
        </div>
      )}
    </>
  );
}

function DarTurno({ agenda, inicio, sobreturno, onListo, onCancelar, toast }) {
  const [busca, setBusca] = useState("");
  const [motivo, setMotivo] = useState("");
  const pacientes = useQuery({
    queryKey: ["pacientes-turno", busca],
    queryFn: () => api.get(`/ciudadanos/?search=${encodeURIComponent(busca)}&page_size=8`),
    enabled: busca.trim().length >= 3,
  });

  const reservar = useAccion(
    (ciudadano) => api.post("/turnos/", { agenda: agenda.id, ciudadano, inicio, motivo, sobreturno }),
    {
      onSuccess: () => { toast.ok(sobreturno ? "Sobreturno dado" : "Turno dado"); onListo(); },
      onError: (e) => toast.deError(e, "No se pudo dar el turno."),
    },
  );

  return (
    <div className="mt-3 flex flex-col gap-2 rounded-md border border-borde bg-superficie-2 p-3">
      <div className="text-sm font-semibold text-texto-suave">
        {sobreturno ? "Sobreturno" : "Dar turno"} · {hhmm(inicio)}
      </div>
      <Input
        autoFocus
        value={busca}
        onChange={(e) => setBusca(e.target.value)}
        /* El buscador de la barra superior usa ese mismo texto: con dos campos
           idénticos en pantalla no se sabe cuál es cuál. */
        placeholder="¿A quién le damos el turno? Nombre o documento…"
        aria-label="Buscar paciente"
      />
      <Input value={motivo} onChange={(e) => setMotivo(e.target.value)}
             placeholder="Motivo (opcional)" aria-label="Motivo del turno" />
      {busca.trim().length >= 3 && (
        pacientes.isLoading ? (
          <Skeleton className="h-16" />
        ) : (pacientes.data?.results || []).length === 0 ? (
          <p className="text-sm text-texto-tenue">Ningún paciente coincide.</p>
        ) : (
          <div className="flex flex-col gap-1">
            {pacientes.data.results.map((c) => (
              <button
                key={c.id}
                disabled={reservar.isPending}
                onClick={() => reservar.mutate(c.id)}
                className="flex items-baseline justify-between gap-2 rounded-md border border-division bg-superficie px-2.5 py-1.5 text-left hover:border-accent-100 hover:bg-accent-50"
              >
                <span className="truncate text-base font-semibold">{c.nombre} {c.apellido}</span>
                <span className="font-mono text-sm text-texto-tenue">{c.documento || "sin DNI"}</span>
              </button>
            ))}
          </div>
        )
      )}
      <Button size="sm" variant="secondary" onClick={onCancelar}>Cerrar</Button>
    </div>
  );
}

function Cargando() {
  return (
    <div className="flex flex-col gap-lg p-lg sm:p-[26px] lg:px-[30px]" role="status" aria-label="Cargando agenda…">
      <Skeleton className="h-[78px]" />
      <Skeleton className="h-12" />
      <Skeleton className="h-96" />
    </div>
  );
}
