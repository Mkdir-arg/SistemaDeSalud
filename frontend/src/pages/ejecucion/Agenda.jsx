import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/api/client";
import { useAccion, useLista } from "@/api/queries";
import { useInstitucion } from "@/auth/InstitutionContext";
import { Icon } from "@/components/icons";
import { Badge, Button, ConfirmDialog, Field, Input } from "@/components/ui";
import { EstadoError, EstadoVacio, Skeleton } from "@/components/ui/estados";
import { Buscador, useBusquedaUrl } from "@/components/ui/filtros";
import { BuscadorPaciente } from "@/components/ui/paciente";
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
// Los tonos son los que define Badge (neutral, info, amber, green, gray,
// error). Un tono inventado NO falla: cae en neutro sin avisar, y ahí
// «Confirmado» quedaba con el mismo gris que «Cancelado» —dos estados
// opuestos, idénticos de lejos—, que es justo lo que rompe el barrido visual
// con el que se lee una agenda de doce renglones.
const ESTADOS = {
  reservado: { label: "Reservado", tone: "info" },
  confirmado: { label: "Confirmado", tone: "green" },
  presente: { label: "Se presentó", tone: "green" },
  ausente: { label: "No vino", tone: "error" },
  cancelado: { label: "Cancelado", tone: "neutral" },
};

// 24 horas: es cómo se escriben los horarios en un hospital, y además «02:15
// p. m.» no entra en la columna y parte el renglón en dos líneas.
const hhmm = (iso) =>
  new Date(iso).toLocaleTimeString("es-AR", { hour: "2-digit", minute: "2-digit", hour12: false });

const ddmm = (iso) =>
  new Date(iso).toLocaleDateString("es-AR", { weekday: "short", day: "2-digit", month: "2-digit" });

// Fecha LOCAL, no UTC: `toISOString()` pasa a UTC antes de recortar y Buenos
// Aires es UTC-3 fijo, así que de 21:00 a medianoche devolvía la fecha de
// mañana. El turno de tarde y el cierre del día caen justo ahí: la pantalla
// abría en la grilla de mañana —vacía de desenlaces— y «Hoy» volvía a poner el
// mismo valor equivocado, así que apretarlo no corregía nada. Marcar «No vino»
// o «Llegó» en esa grilla se lo hace a un paciente de mañana.
const iso = (d) =>
  new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);

const mismoInstante = (a, b) => new Date(a).getTime() === new Date(b).getTime();

export default function Agenda() {
  const { institucion } = useInstitucion();
  const toast = useToast();
  const [agendaSel, setAgendaSel] = useState(null);
  const [fecha, setFecha] = useState(() => iso(new Date()));
  const [soloSinConfirmar, setSoloSinConfirmar] = useState(false);
  const [verProximos, setVerProximos] = useState(false);
  // Horario que hay que abrir con el formulario de alta ya desplegado: es a
  // dónde deja parado el salto desde «Próximos libres».
  const [abrir, setAbrir] = useState(null);

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

  const proximos = useQuery({
    queryKey: ["agenda-proximos", agenda?.id, fecha],
    queryFn: () => api.get(`/agendas/${agenda.id}/proximos-libres/?cuantos=10&desde=${fecha}`),
    enabled: verProximos && agenda?.id != null,
  });

  const recargar = () => { dia.refetch(); turnos.refetch(); if (verProximos) proximos.refetch(); };

  const ocupados = horarios.filter((h) => h.ocupado).length;
  // Sale de la grilla del día y no de la consulta de turnos: si esa falla, el
  // resumen tiene que seguir siendo el de verdad y no un cero tranquilizador.
  const sobreturnos = horarios.reduce((n, h) => n + (h.sobreturnos || 0), 0);
  // El máximo del día manda sobre el de la lista de agendas: si alguien lo
  // cambió mientras esta pantalla está abierta, lo que la grilla ofrece y lo que
  // el encabezado dice tienen que salir del mismo lado.
  const sobreturnosMax = dia.data?.agenda?.sobreturnos_max ?? agenda?.sobreturnos_max;
  const sinConfirmar = (turnos.data?.results || []).filter((t) => t.estado === "reservado").length;
  const irAFecha = (f) => { setFecha(f); setAbrir(null); };
  const mover = (dias) => {
    const d = new Date(fecha + "T12:00:00");
    d.setDate(d.getDate() + dias);
    irAFecha(iso(d));
  };
  const irA = (inicio) => {
    setFecha(iso(new Date(inicio)));
    setAbrir(inicio);
    setVerProximos(false);
  };

  const visibles = soloSinConfirmar
    ? horarios.filter((h) =>
        (porHorario.get(new Date(h.inicio).getTime()) || []).some((t) => t.estado === "reservado"))
    : horarios;
  const enGrilla = visibles.filter((h) => !h.fuera_de_grilla);
  const sueltos = visibles.filter((h) => h.fuera_de_grilla);

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

  const renglon = (h) => (
    <Renglon
      key={h.inicio}
      horario={h}
      agenda={agenda}
      sobreturnosMax={sobreturnosMax}
      turnos={porHorario.get(new Date(h.inicio).getTime()) || []}
      turnosListos={!turnos.isLoading && !turnos.error}
      abierto={abrir != null && mismoInstante(abrir, h.inicio)}
      onCambio={recargar}
      toast={toast}
    />
  );

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
          {/* Una agenda sin flujo es un estado real y previsto, pero registrar
              la llegada ahí no abre ningún caso: si no se dice acá, el
              administrativo manda al paciente a esperar que lo llamen y no hay
              nada en ninguna cola. */}
          {agenda && !agenda.flujo && (
            <p className="text-sm text-texto-tenue">
              Esta agenda no tiene flujo: registrar la llegada no abre ningún caso.
            </p>
          )}
          {/* Un renglón sin «+» no distingue «esta agenda no toma sobreturnos»
              de «ya se usaron los cupos de ese horario». Dicho una vez acá, la
              respuesta a «¿me da un sobreturno a las 10?» deja de ser un tanteo. */}
          {sobreturnosMax === 0 && (
            <p className="text-sm text-texto-tenue">Esta agenda no toma sobreturnos.</p>
          )}
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
          {/* El sobreturno no ocupa un renglón propio de la grilla, así que sin
              esta línea un día con 12 horarios llenos y 5 sobreturnos se resume
              «12/12 dados» — y ése es el número con el que se contesta «¿cuánta
              gente tiene hoy la doctora?» y se decide si se acepta uno más. */}
          <div className="text-xs text-texto-tenue">
            dados{sobreturnos > 0 && ` · ${sobreturnos} sobreturno${sobreturnos === 1 ? "" : "s"}`}
          </div>
        </div>
      </section>

      <BuscarTurnos institucionId={institucion?.id} onCambio={recargar} toast={toast} />

      {/* Navegación por día */}
      <section className="flex flex-wrap items-center gap-2 rounded-lg border border-borde bg-superficie px-xl py-3">
        <Button size="sm" variant="secondary" onClick={() => mover(-1)}>
          <Icon name="chevronLeft" size={14} /> Día anterior
        </Button>
        <Button size="sm" variant="secondary" onClick={() => irAFecha(iso(new Date()))}>Hoy</Button>
        <Button size="sm" variant="secondary" onClick={() => mover(1)}>
          Día siguiente <Icon name="chevronRight" size={14} />
        </Button>
        {/* «¿Para cuándo tiene?» es la pregunta que más se hace en un mostrador
            de turnos programados. Sin esto había que apretar «Día siguiente»
            veinte o treinta veces, con dos consultas por salto y el paciente en
            el teléfono. */}
        <Button size="sm" variant={verProximos ? "primary" : "secondary"}
                onClick={() => setVerProximos(!verProximos)}>
          <Icon name="search" size={14} /> Próximos libres
        </Button>
        <Button
          size="sm"
          variant={soloSinConfirmar ? "primary" : "secondary"}
          onClick={() => setSoloSinConfirmar(!soloSinConfirmar)}
          title="Los que todavía no avisaron que vienen: es la lista de llamados"
        >
          <Icon name="filter" size={14} /> Sin confirmar ({sinConfirmar})
        </Button>
        <Input
          type="date"
          value={fecha}
          onChange={(e) => irAFecha(e.target.value)}
          aria-label="Fecha de la agenda"
          className="ml-auto w-auto"
        />
      </section>

      {verProximos && (
        <ProximosLibres consulta={proximos} onElegir={irA} />
      )}

      <section className="overflow-hidden rounded-lg border border-borde bg-superficie">
        {dia.isLoading ? (
          <div className="p-xl"><Skeleton className="h-64" /></div>
        ) : dia.error ? (
          /* Sin esto, un 500 o un wifi caído caían en el estado vacío de abajo:
             la pantalla decía «La agenda no atiende este día» con doce personas
             citadas, y mandaba a tocar la configuración de una franja que
             existe. Nadie se enteraba de que había fallado el servidor. */
          <EstadoError error={dia.error} onReintentar={recargar} />
        ) : horarios.length === 0 ? (
          /* Que no haya horarios no es un error: la agenda no atiende ese día.
             Decirlo evita que alguien crea que el sistema falló. */
          <EstadoVacio
            titulo="La agenda no atiende este día"
            detalle="Elegí otra fecha, o cargá una franja de atención desde Estructura organizativa."
            icono="calendar"
          />
        ) : (
          <>
            {/* La grilla se arma con dos consultas. Si falla la de turnos, los
                horarios ocupados quedan sin paciente y sin acciones: hay que
                decirlo, porque callarlo dibujaba doce horarios «libres» encima
                de doce turnos dados. */}
            {turnos.error && (
              <div role="alert"
                   className="flex flex-wrap items-center gap-2 border-b border-division bg-badge-error-bg px-xl py-2.5 text-base text-badge-error-fg">
                <Icon name="alert" size={15} />
                <span className="flex-1">
                  No se pudieron traer los turnos de este día: los horarios ocupados se
                  muestran sin paciente y sin acciones.
                </span>
                <button onClick={recargar} className="font-semibold underline">Reintentar</button>
              </div>
            )}
            {enGrilla.length > 0 && (
              <ul className="divide-y divide-division">{enGrilla.map(renglon)}</ul>
            )}
            {enGrilla.length === 0 && sueltos.length === 0 && (
              /* Sólo se llega acá con el filtro puesto: el día tiene horarios,
                 pero ninguno quedó sin confirmar. */
              <EstadoVacio
                titulo="Ningún turno sin confirmar"
                detalle="Todos los turnos de este día ya avisaron que vienen, o ya se resolvieron."
                icono="calendar"
              />
            )}
            {/* Turnos cuyo horario ya no existe en la agenda: se le cambió la
                franja, se la desactivó o se le puso fecha de fin. El paciente
                tiene el papel en la mano, así que no puede desaparecer de la
                pantalla por un cambio de configuración. */}
            {sueltos.length > 0 && (
              <>
                <div className="border-y border-division bg-badge-amber-bg px-xl py-2.5 text-base font-semibold text-badge-amber-fg">
                  Turnos fuera de la grilla actual · el horario que tienen dado ya no
                  existe en la agenda
                </div>
                <ul className="divide-y divide-division">{sueltos.map(renglon)}</ul>
              </>
            )}
          </>
        )}
      </section>
    </div>
  );
}

/*
 * Buscar el turno de una persona sin saber la agenda ni el día.
 *
 * Es la pantalla que atiende al que llama para cancelar: «tengo turno con la
 * doctora, no puedo ir», sin acordarse de la fecha y sin saber si es Suárez o
 * Gómez. Con la grilla sola había que ir agenda por agenda y día por día, con
 * otra persona esperando en el mostrador, así que se cortaba el teléfono sin
 * cancelar: el horario quedaba tomado, no se reasignaba a nadie de la lista de
 * espera y el turno terminaba contado como «no vino». Ese ausentismo falso es
 * justo el indicador con el que después se decide cuánto sobreturnear.
 */
function BuscarTurnos({ institucionId, onCambio, toast }) {
  const navigate = useNavigate();
  const [texto, setTexto, busqueda] = useBusquedaUrl("paciente");
  const termino = busqueda.trim();

  // De hoy en adelante y en TODAS las agendas: quien llama pregunta por su
  // turno, no por la agenda. Un turno de la semana pasada no se puede cancelar
  // ni confirmar, y mezclado tapa los que sí.
  const q = useLista(
    "turnos",
    {
      search: termino || undefined,
      desde: iso(new Date()),
      agenda__institucion: institucionId,
      ordering: "inicio",
      pageSize: 20,
    },
    { enabled: termino.length > 0 && institucionId != null },
  );

  return (
    <section className="flex flex-col gap-3 rounded-lg border border-borde bg-superficie px-xl py-lg">
      <Field label="Buscar el turno de un paciente" hint="En todas las agendas, de hoy en adelante.">
        <Buscador
          valor={texto}
          onChange={setTexto}
          placeholder="Nombre, apellido o documento…"
          autoFocus={false}
        />
      </Field>

      {termino.length > 0 && (
        q.isLoading ? (
          <Skeleton className="h-10" />
        ) : q.error ? (
          <EstadoError error={q.error} onReintentar={q.refetch} />
        ) : q.filas.length === 0 ? (
          <p className="text-base text-texto-debil">
            Sin turnos de hoy en adelante para «{termino}».
          </p>
        ) : (
          <>
            <ul aria-label="Turnos encontrados"
                className="divide-y divide-division overflow-hidden rounded-md border border-borde">
              {q.filas.map((t) => (
                <li key={t.id} className="flex flex-wrap items-center gap-x-md gap-y-2 px-3.5 py-2.5">
                  {/* La fecha y la agenda son la mitad de la respuesta: quien
                      llama no las sabe, y sin ellas no hay forma de confirmarle
                      que se está cancelando el turno que él tiene en la mano. */}
                  <span className="w-40 shrink-0">
                    <span className="block text-base font-semibold">
                      {ddmm(t.inicio)}{" "}
                      <span className="font-mono tabular-nums">{hhmm(t.inicio)}</span>
                    </span>
                    <span className="block truncate text-sm text-texto-tenue">
                      {t.agenda_nombre}
                      {t.documento ? ` · doc. ${t.documento}` : ""}
                    </span>
                  </span>
                  <FichaTurno
                    turno={t}
                    porTelefono
                    onCambio={onCambio}
                    toast={toast}
                    navigate={navigate}
                  />
                </li>
              ))}
            </ul>
            {/* Callar que hay más es peor que no buscar: se cancela el turno que
                aparece, que puede no ser el que la persona tiene. */}
            {q.total > q.filas.length && (
              <p className="text-sm text-texto-tenue">
                Se muestran los primeros {q.filas.length} de {q.total}. Agregá el apellido o
                el documento para achicar la lista.
              </p>
            )}
          </>
        )
      )}
    </section>
  );
}

function ProximosLibres({ consulta, onElegir }) {
  const libres = consulta.data?.horarios || [];
  return (
    <section className="rounded-lg border border-borde bg-superficie px-xl py-lg">
      <div className="mb-2 text-md font-bold">Próximos horarios libres</div>
      {consulta.isLoading ? (
        <Skeleton className="h-10" />
      ) : consulta.error ? (
        <EstadoError error={consulta.error} onReintentar={consulta.refetch} />
      ) : libres.length === 0 ? (
        <p className="text-base text-texto-debil">
          No queda ningún horario libre en los próximos 30 días.
        </p>
      ) : (
        <div className="flex flex-wrap gap-2">
          {libres.map((h) => (
            <button
              key={h.inicio}
              onClick={() => onElegir(h.inicio)}
              className="rounded-md border border-division bg-superficie-2 px-2.5 py-1.5 text-base hover:border-accent-100 hover:bg-accent-50"
            >
              <span className="font-semibold">{ddmm(h.inicio)}</span>{" "}
              <span className="font-mono tabular-nums">{hhmm(h.inicio)}</span>
            </button>
          ))}
        </div>
      )}
    </section>
  );
}

function Renglon({ horario, agenda, sobreturnosMax, turnos, turnosListos, abierto, onCambio, toast }) {
  const navigate = useNavigate();
  const [dando, setDando] = useState(!!abierto);
  // El turno «titular» del horario y los sobreturnos que cuelgan de él.
  const titulares = turnos.filter((t) => !t.sobreturno);
  const extras = turnos.filter((t) => t.sobreturno);
  const titular = titulares[0];
  // El día dice que está ocupado pero el turno todavía no llegó (o no llegó
  // nunca). Dibujarlo como «libre» con su botón «Dar turno» era operable: se
  // daba un turno encima de uno existente, y ninguno de los pacientes que
  // llegaba se podía marcar como presente porque «Llegó» no estaba en ningún
  // renglón.
  const ocupadoSinFicha = horario.ocupado && !titular;
  const est = ESTADOS[horario.estado] || { label: horario.estado, tone: "neutral" };

  return (
    <li className={cn(
      "px-xl py-3",
      horario.bloqueado ? "bg-badge-error-bg/25" : horario.ocupado ? "" : "bg-superficie-2/40",
    )}>
      <div className="flex flex-wrap items-center gap-x-md gap-y-2">
        <span className="w-14 shrink-0 font-mono text-md font-bold tabular-nums">
          {hhmm(horario.inicio)}
        </span>
        {horario.bloqueado && <Badge tone="error">bloqueado</Badge>}
        {titular ? (
          <FichaTurno turno={titular} onCambio={onCambio} toast={toast} navigate={navigate} />
        ) : ocupadoSinFicha ? (
          <>
            <span className="min-w-0 flex-1 truncate text-md font-semibold">
              {horario.paciente || "Ocupado"}
            </span>
            <Badge tone={est.tone}>{est.label}</Badge>
            <span className="text-sm text-texto-tenue">
              {turnosListos ? "sin ficha del turno" : "cargando el turno…"}
            </span>
          </>
        ) : (
          <>
            <span className="flex-1 text-base text-texto-tenue">
              {horario.bloqueado ? "bloqueado" : extras.length ? "sin titular" : "libre"}
            </span>
            {!horario.bloqueado && (
              <Button size="sm" variant="secondary" onClick={() => setDando(!dando)}>
                {dando ? "Cerrar" : "Dar turno"}
              </Button>
            )}
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
        {/* Agotados los cupos, el lugar del «+» no puede quedar vacío: un
            horario sin botón se lee igual que una agenda que no toma
            sobreturnos, y ahí la respuesta al mostrador sale a tanteo. */}
        {horario.ocupado && !horario.admite_sobreturno && !horario.bloqueado
          && !horario.fuera_de_grilla && sobreturnosMax > 0 && (
          <span className="flex-none text-sm text-texto-tenue">
            {horario.sobreturnos}/{sobreturnosMax} sobreturnos
          </span>
        )}
      </div>

      {/* Dos titulares en el mismo horario no deberían existir. Si existen, el
          segundo paciente tiene el turno impreso: mostrarlo es la diferencia
          entre poder explicarle qué pasó y no tener nada. */}
      {titulares.slice(1).map((t) => (
        <div key={t.id} className="mt-2 flex flex-wrap items-center gap-x-md gap-y-2 pl-14">
          <Badge tone="error">turno duplicado</Badge>
          <FichaTurno turno={t} onCambio={onCambio} toast={toast} navigate={navigate} />
        </div>
      ))}

      {extras.map((t) => (
        <div key={t.id} className="mt-2 flex flex-wrap items-center gap-x-md gap-y-2 pl-14">
          <Badge tone="amber">sobreturno</Badge>
          <FichaTurno turno={t} onCambio={onCambio} toast={toast} navigate={navigate} />
        </div>
      ))}

      {dando && (
        <DarTurno
          agenda={agenda}
          inicio={horario.inicio}
          sobreturno={!!titular}
          onListo={() => { setDando(false); onCambio(); }}
          onCerrar={() => setDando(false)}
          toast={toast}
        />
      )}
    </li>
  );
}

function FichaTurno({ turno, onCambio, toast, navigate, porTelefono = false }) {
  const est = ESTADOS[turno.estado] || { label: turno.estado, tone: "neutral" };
  // Las dos acciones irreversibles se confirman antes de disparar. En el
  // mostrador se opera con alguien enfrente y apurado: un clic corrido una
  // columna sobre «No vino» congela el turno como ausente —al paciente que está
  // parado ahí ya no se le puede registrar la llegada— y uno sobre «Cancelar»
  // libera el horario, que con teléfono y mostrador dando turnos a la vez puede
  // estar tomado en menos de un minuto.
  const [confirmando, setConfirmando] = useState(null);
  const accion = useAccion(({ nombre }) => api.post(`/turnos/${turno.id}/${nombre}/`), {
    onSuccess: (resp, { ok }) => {
      toast.ok(typeof ok === "function" ? ok(resp) : ok);
      setConfirmando(null);
      onCambio();
    },
    onError: (e) => { setConfirmando(null); toast.deError(e); },
  });
  const pendiente = ["reservado", "confirmado"].includes(turno.estado);
  // Desde el buscador el turno puede ser de cualquier día: preguntar «¿cancelo
  // el de las 10:20?» a secas deja cancelar el de la semana equivocada, y de eso
  // nadie se entera hasta que el paciente se presenta.
  const hora = porTelefono ? `${ddmm(turno.inicio)} ${hhmm(turno.inicio)}` : hhmm(turno.inicio);

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
        <div className="flex flex-wrap items-center gap-1.5">
          {/* «Llegó» es la acción principal: es la que abre el caso y arranca la
              atención. El resto son excepciones.

              En el buscador no va, y «No vino» tampoco: las dos dependen de
              estar parado en el día del turno con el paciente enfrente. Sobre un
              turno de la semana que viene, «Llegó» deja un caso abierto que
              llaman por altavoz y nadie contesta, y «No vino» le carga un
              ausentismo a alguien que justamente está llamando para avisar. */}
          {!porTelefono && (
          <Button size="sm" disabled={accion.isPending}
                  onClick={() => accion.mutate({
                    nombre: "llegada",
                    // El mensaje sale de la RESPUESTA: si la agenda no tiene
                    // flujo el backend deja el turno presente y no abre ningún
                    // caso, y decir «caso abierto» igual manda al paciente a
                    // esperar un llamado que no va a existir.
                    ok: (t) => t?.caso
                      ? `${turno.paciente} llegó · caso abierto`
                      : `${turno.paciente} llegó · esta agenda no abre caso automáticamente`,
                  })}>
            Llegó
          </Button>
          )}
          {/* El circuito de recordatorios se cierra acá: el comando arma la
              lista de llamados, la persona llama y el paciente dice «sí, voy».
              Sin este botón no había dónde anotarlo, así que el estado
              «confirmado» no existía nunca en datos reales y el mostrador no
              podía distinguir al que avisó del que ni contestó. */}
          {turno.estado === "reservado" && (
            <Button size="sm" variant="secondary" disabled={accion.isPending}
                    onClick={() => accion.mutate({
                      nombre: "confirmar",
                      ok: `${turno.paciente} confirmó que viene`,
                    })}>
              Confirmó
            </Button>
          )}
          {/* Separadas del primario: son las dos que no se pueden deshacer. */}
          <span className="mx-0.5 h-5 w-px bg-division" aria-hidden="true" />
          {!porTelefono && (
          <Button size="sm" variant="secondary" disabled={accion.isPending}
                  onClick={() => setConfirmando({
                    nombre: "ausente",
                    titulo: "Marcar que no vino",
                    boton: "Marcar que no vino",
                    texto: `¿Marcar que ${turno.paciente} (${hora}) no vino? No se puede deshacer: después no se le va a poder registrar la llegada, y le queda contado un ausentismo.`,
                    ok: "Marcado como ausente",
                  })}>
            No vino
          </Button>
          )}
          <Button size="sm" variant="secondary" disabled={accion.isPending}
                  onClick={() => setConfirmando({
                    nombre: "cancelar",
                    titulo: "Cancelar el turno",
                    boton: "Cancelar el turno",
                    texto: `¿Cancelar el turno de ${turno.paciente} (${hora})? Libera el horario, y con el teléfono y el mostrador dando turnos a la vez se lo puede llevar otra persona en minutos.`,
                    ok: "Turno cancelado · horario liberado",
                  })}>
            Cancelar
          </Button>
        </div>
      )}
      {confirmando && (
        <ConfirmDialog
          title={confirmando.titulo}
          confirmar={confirmando.boton}
          volver="Volver"
          peligroso
          cargando={accion.isPending}
          onClose={() => setConfirmando(null)}
          onConfirmar={() => accion.mutate(confirmando)}
        >
          {confirmando.texto}
        </ConfirmDialog>
      )}
    </>
  );
}

function DarTurno({ agenda, inicio, sobreturno, onListo, onCerrar, toast }) {
  const { institucion } = useInstitucion();
  const [motivo, setMotivo] = useState("");

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
      <Input value={motivo} onChange={(e) => setMotivo(e.target.value)}
             placeholder="Motivo (opcional)" aria-label="Motivo del turno" />
      {/* El buscador compartido en vez de uno propio: busca desde el primer
          caracter, filtra por institución —sin eso, en una red aparecen
          homónimos de otro hospital— y ante «sin coincidencias» ofrece crear al
          paciente en el momento. Quien saca turno para el martes muchas veces
          nunca fue atendido acá; antes había que irse a Registros y volver a
          navegar hasta este horario, que para entonces se lo podía haber
          llevado otro operador. */}
      <BuscadorPaciente
        institucionId={institucion?.id}
        onElegir={(c) => reservar.mutate(c.id)}
      />
      <Button size="sm" variant="secondary" onClick={onCerrar}>Cerrar</Button>
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
