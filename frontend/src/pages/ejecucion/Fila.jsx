import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { api } from "@/api/client";
import { useAccion, useLista } from "@/api/queries";
import { useAuth } from "@/auth/AuthContext";
import { Icon } from "@/components/icons";
import { Badge } from "@/components/ui";
import { EstadoError, EstadoVacio, Skeleton } from "@/components/ui/estados";
import { useToast } from "@/components/ui/toast";
import { antiguedad, casoId } from "@/lib/format";
import { cn } from "@/lib/cn";

const hora = (iso) =>
  new Date(iso).toLocaleTimeString("es-AR", { hour: "2-digit", minute: "2-digit" });

// Cada cuánto se refresca la cola. Corto a propósito: es la pantalla del box y
// lo que muestra decide a quién se llama. Medio minuto de desfasaje ya alcanza
// para que dos boxes llamen a la misma persona.
const REFRESCO_MS = 20_000;

/**
 * Fila de espera de un área. Pantalla piloto de la migración: es la primera
 * hecha entera con la fundación nueva (tokens, componentes, TanStack Query,
 * responsive, estados y toasts) y sirve de patrón para las otras.
 */
export default function Fila() {
  const navigate = useNavigate();
  const toast = useToast();
  const { user } = useAuth();
  const [areaSel, setAreaSel] = useState(null);

  // `box: "null"` como texto a propósito: `query()` descarta los valores null
  // (para no ensuciar la URL), así que el filtro «sin box asignado» hay que
  // pedirlo con la palabra, que es lo que el backend traduce a IS NULL.
  // Se pide al servidor y no se descarta en el cliente: los ya llamados ocupaban
  // lugar de las 200 filas del pedido y podían dejar afuera a gente que espera.
  //
  // `refetchInterval`: esta pantalla queda abierta en el monitor del box durante
  // todo el turno y era la única viva de la app sin refresco. Congelada mostraba
  // gente que ya había llamado otro —de ahí que «Llamar siguiente» disparara un
  // llamado duplicado— y no mostraba a los que llegaron después: un paciente que
  // el triage marcó ROJO hace diez minutos no subía al tope de la lista de nadie.
  const q = useLista(
    "items-fila",
    { atendido: false, box: "null", pageSize: 200 },
    { refetchInterval: REFRESCO_MS, refetchIntervalInBackground: false },
  );

  // Quién está adentro de cada box. Es una lista corta —a lo sumo uno por box—
  // y va aparte de la cola para no mezclarla: la de arriba son los que ESPERAN.
  const enBox = useLista(
    "items-fila",
    { atendido: false, pageSize: 200 },
    { refetchInterval: REFRESCO_MS, refetchIntervalInBackground: false },
  );
  const ocupacion = useMemo(() => {
    const m = new Map();
    for (const it of enBox.filas) if (it.box) m.set(it.box, it);
    return m;
  }, [enBox.filas]);

  // El orden viene del servidor y NO se vuelve a ordenar acá.
  //
  // Esta pantalla ordenaba por `urgente` y `orden`, y «Mi trabajo» por la
  // prioridad del caso: eran dos reglas distintas y «el siguiente» resultaba ser
  // una persona en cada una. La enfermera adelantaba a alguien que empeoró
  // esperando y el médico, llamando desde la otra pantalla, llamaba a otro.
  const items = q.filas;

  /*
   * Áreas donde esta persona realmente trabaja.
   *
   * La fila muestra TODAS las áreas con gente esperando —un jefe quiere ver el
   * panorama—, pero arrancar en una donde no se puede llamar es una trampa: el
   * médico de guardia entraba, apretaba «Llamar siguiente» y recibía «No integrás
   * ningún grupo responsable de este paso». La acción principal de la pantalla
   * fallaba de entrada, y sólo lo decía después del clic.
   */
  const misMembresias = useLista(
    "membresias",
    { usuario: user?.id, activo: true, pageSize: 50 },
    { enabled: !!user?.id },
  );
  const misAreas = useMemo(
    () => new Set(misMembresias.filas.flatMap((m) => m.areas || [])),
    [misMembresias.filas],
  );

  /*
   * Las áreas del selector: las que tienen cola MÁS las propias.
   *
   * Salían sólo de los ítems en espera, y por eso una cola vacía —de madrugada,
   * entre picos, que es un estado normal y frecuente— dejaba la lista en cero:
   * desaparecía el selector, no se elegía ninguna área, y la pantalla terminaba
   * afirmando que el área no tiene consultorios cargados. Alguien con permisos
   * se iba a Estructura a «arreglar» boxes que ya existían.
   *
   * Peor todavía: si tu área estaba vacía y otra tenía gente, el selector te
   * dejaba mirando la cola ajena sin forma de volver a la tuya.
   */
  const areas = useMemo(() => {
    const m = new Map();
    for (const it of items) if (it.area) m.set(it.area, it.area_nombre || `Área ${it.area}`);
    for (const mem of misMembresias.filas) {
      for (const id of mem.areas || []) {
        if (!m.has(id)) m.set(id, mem.areas_nombres?.[String(id)] || `Área ${id}`);
      }
    }
    return [...m].map(([id, nombre]) => ({ id, nombre }));
  }, [items, misMembresias.filas]);

  useEffect(() => {
    if (!areas.length) return;
    if (areas.some((a) => a.id === areaSel)) return; // ya hay una elegida y válida
    // Se espera a saber cuáles son suyas antes de elegir. Sin esto, la primera
    // pasada elegía `areas[0]` con las membresías todavía en vuelo, y la pasada
    // siguiente ya veía un área válida elegida y no corregía nunca: el efecto
    // decidía antes de tener el dato que informa la decisión.
    if (misMembresias.isLoading) return;
    // Se prefiere un área propia; si ninguna tiene cola, se cae a la primera.
    setAreaSel((areas.find((a) => misAreas.has(a.id)) || areas[0]).id);
  }, [areas, areaSel, misAreas, misMembresias.isLoading]);

  // Sólo se avisa cuando ya se sabe a qué áreas pertenece: mientras carga, decir
  // que no puede llamar sería mentirle por un instante.
  const areaAjena = misMembresias.isSuccess && areaSel != null && !misAreas.has(areaSel);

  const boxes = useLista("boxes", { area: areaSel, activo: true, pageSize: 50 }, { enabled: areaSel != null });

  /*
   * Los que se dieron por ausente.
   *
   * `marcar_ausente` los saca de la cola (`atendido=True`) y desaparecían de
   * TODAS las pantallas: el paciente que salió a fumar y vuelve a los diez
   * minutos no tenía cómo volver a la cola sin ir a buscar su caso a mano por
   * otro lado. Aparecen acá, aparte de la fila —no están esperando— y con la
   * acción que los reencola al final.
   */
  const ausentes = useLista(
    "items-fila",
    { ausente: true, pageSize: 50 },
    { refetchInterval: REFRESCO_MS, refetchIntervalInBackground: false },
  );
  const misAusentes = ausentes.filas.filter((it) => it.area === areaSel);

  const reencolar = useAccion((caso) => api.post(`/casos/${caso}/devolver/`, {}), {
    onSuccess: () => toast.ok("Vuelve a la cola, al final"),
    onError: (e) => toast.deError(e, "No se pudo devolver a la cola."),
  });

  const fila = items.filter((it) => it.area === areaSel);
  const todosOcupados = boxes.filas.length > 0 && boxes.filas.every((b) => ocupacion.has(b.id));
  const areaNombre = areas.find((a) => a.id === areaSel)?.nombre || "Sala de espera";
  const siguiente = fila[0];

  const llamar = useAccion(({ caso, box }) => api.post(`/casos/${caso}/llamar/`, box ? { box_id: box.id } : {}), {
    onError: (e) => toast.deError(e, "No se pudo llamar al paciente."),
  });

  // Adelantar a alguien que empeoró esperando. El backend renumera la cola
  // entera, así que se relee en vez de mover el ítem en el cliente.
  const mover = useAccion(({ id, posicion }) => api.post(`/items-fila/${id}/mover/`, { posicion }), {
    onSuccess: (_, { quien }) => toast.ok(`${quien || "El paciente"} se adelantó un lugar`),
    onError: (e) => toast.deError(e, "No se pudo cambiar el orden de la fila."),
  });

  function alLlamar(box) {
    if (!siguiente) return;
    const caso = siguiente.caso;
    const quien = siguiente.persona || casoId(caso);
    llamar.mutate(
      { caso, box },
      {
        onSuccess: () => {
          toast.ok(`Llamaste a ${quien}`, { detalle: box ? `Pasá a ${box.nombre}` : undefined });
          // El profesional pasa directo a atender al paciente que llamó.
          navigate(`/casos/${caso}`);
        },
      },
    );
  }

  if (q.isLoading) return <CargandoFila />;
  if (q.error) return <div className="p-[30px]"><EstadoError error={q.error} onReintentar={q.refetch} /></div>;

  return (
    <div className="flex flex-col gap-lg p-lg sm:p-[26px] lg:px-[30px]">
      {/* Cabecera */}
      <section className="flex flex-wrap items-center gap-lg rounded-lg border border-borde bg-superficie px-xl py-lg">
        <span className="flex size-11 shrink-0 items-center justify-center rounded-md bg-nodo-espera-tint text-nodo-espera-sol">
          <Icon name="list" size={22} />
        </span>
        <div className="min-w-40 flex-1">
          <h2 className="text-xl font-bold">Fila de espera</h2>
          <p className="text-base text-texto-debil">FIFO + urgencia · se llama desde cada box</p>
        </div>
        {areas.length > 1 && (
          <select
            aria-label="Área de la fila"
            value={areaSel ?? ""}
            onChange={(e) => setAreaSel(Number(e.target.value))}
            className="h-9 rounded-md border border-campo-borde bg-superficie px-2 text-md outline-none focus:border-accent"
          >
            {areas.map((a) => <option key={a.id} value={a.id}>{a.nombre}</option>)}
          </select>
        )}
        <div className="text-right">
          <div className="text-cifra font-extrabold leading-none tabular-nums">{fila.length}</div>
          <div className="text-xs text-texto-tenue">en {areaNombre}</div>
        </div>
      </section>

      {/* Boxes: cada uno llama al siguiente de la cola */}
      <section className="rounded-lg border border-borde bg-superficie px-xl py-lg">
        <h3 className="mb-md text-sm font-bold text-texto-suave">Consultorios</h3>

        {areaAjena && (
          <div className="mb-md flex items-start gap-2 rounded-md bg-badge-amber-bg px-3 py-2 text-base text-badge-amber-fg">
            <Icon name="alert" size={15} className="mt-px flex-none" />
            <span>
              Estás mirando la cola de <strong>{areaNombre}</strong>, que no es tuya.
              Podés verla, pero llamar a un paciente lo tiene que hacer alguien del
              área.
            </span>
          </div>
        )}

        {boxes.isLoading ? (
          <div className="grid grid-cols-[repeat(auto-fill,minmax(11rem,1fr))] gap-2.5">
            {[0, 1].map((i) => <Skeleton key={i} className="h-[86px]" />)}
          </div>
        ) : boxes.filas.length === 0 ? (
          <div className="flex flex-wrap items-center justify-between gap-md">
            {/* Sólo se afirma que faltan boxes cuando de verdad se preguntó por
                ellos. Con `areaSel` en null la consulta ni sale, y la pantalla
                acusaba de mala configuración a un área que está bien. */}
            <span className="text-base text-texto-tenue">
              {areaSel == null
                ? "Elegí un área para ver sus consultorios."
                : "Esta área no tiene boxes configurados. Cargalos en Estructura → área → Boxes."}
            </span>
            <BotonLlamar
              label="Llamar al siguiente"
              disabled={!siguiente || llamar.isPending}
              cargando={llamar.isPending}
              onClick={() => alLlamar(null)}
            />
          </div>
        ) : (
          <>
            {/* Todos ocupados: la pantalla se quedaba sin una sola acción y sin
                decir por qué. Con siete personas esperando y ningún botón, lo
                razonable es pensar que el sistema se rompió. */}
            {todosOcupados && (
              <div className="mb-md flex items-start gap-2 rounded-md bg-superficie-2 px-3 py-2 text-base text-texto-medio">
                <Icon name="alert" size={15} className="mt-px flex-none text-texto-debil" />
                <span>
                  Los {boxes.filas.length} consultorios están ocupados. Va a haber uno
                  libre cuando alguien termine su atención o salga del box.
                </span>
              </div>
            )}
          <div className="grid grid-cols-[repeat(auto-fill,minmax(11rem,1fr))] gap-2.5">
            {boxes.filas.map((b) => {
              /*
               * Un box con alguien adentro no se puede usar para llamar.
               *
               * Las tarjetas están una al lado de la otra y ninguna decía cuál
               * estaba ocupada: el médico del Box 2 apretaba la del Box 1, el
               * televisor de la sala anunciaba «JUAN PÉREZ → Box 1» y Juan
               * entraba al consultorio donde otro estaba revisando a alguien.
               * Interrumpe una consulta y expone al que está adentro.
               */
              const dentro = ocupacion.get(b.id);
              return (
                <div key={b.id} className="flex flex-col gap-2.5 rounded-md border border-borde p-3">
                  <div className="flex items-center gap-2 text-md font-bold">
                    <Icon name="enter" size={15} className="text-nodo-espera-sol" /> {b.nombre}
                  </div>
                  {dentro ? (
                    <div className="text-sm text-texto-debil">
                      Ocupado
                      {dentro.persona ? <> · <span className="text-texto-medio">{dentro.persona}</span></> : null}
                    </div>
                  ) : (
                    <BotonLlamar
                      label="Llamar siguiente"
                      disabled={!siguiente || llamar.isPending}
                      cargando={llamar.isPending && llamar.variables?.box?.id === b.id}
                      onClick={() => alLlamar(b)}
                    />
                  )}
                </div>
              );
            })}
          </div>
          </>
        )}
      </section>

      {/* Dados por ausente: fuera de la cola, pero recuperables */}
      {misAusentes.length > 0 && (
        <section className="overflow-hidden rounded-lg border border-borde bg-superficie">
          <h3 className="px-xl py-lg text-lg font-bold">
            No se presentaron
            <span className="ml-2 text-base font-semibold text-texto-tenue">
              {misAusentes.length}
            </span>
          </h3>
          <ul className="border-t border-division">
            {misAusentes.map((it) => (
              <li key={it.id} className="flex flex-wrap items-center gap-md border-t border-division px-xl py-3 first:border-t-0">
                <span className="min-w-40 flex-1 font-semibold">{it.persona || casoId(it.caso)}</span>
                <span className="text-sm text-texto-debil">
                  llamado {it.veces_llamado > 1 ? `${it.veces_llamado} veces` : "1 vez"}
                </span>
                <button
                  type="button"
                  disabled={reencolar.isPending}
                  onClick={() => reencolar.mutate(it.caso)}
                  className="rounded-md border border-borde px-3 py-1.5 text-base font-semibold text-texto-medio hover:bg-superficie-2 disabled:opacity-50"
                >
                  Volver a la cola
                </button>
              </li>
            ))}
          </ul>
          {/* Va al final a propósito, y se dice: perdió el turno, pero el que
              esperó todo el tiempo no tiene por qué pagarlo. */}
          <div className="px-xl pb-lg text-sm text-texto-debil">
            Vuelven al final de la cola: ya perdieron su turno.
          </div>
        </section>
      )}

      {/* Cola */}
      <section className="overflow-hidden rounded-lg border border-borde bg-superficie">
        <h3 className="px-xl py-lg text-lg font-bold">En espera</h3>
        {fila.length === 0 ? (
          <EstadoVacio
            titulo="La fila está vacía"
            detalle={`No hay pacientes esperando en ${areaNombre}.`}
            icono="list"
          />
        ) : (
          <ul className="border-t border-division">
            {/* Encabezado solo en pantallas anchas: en angosto cada fila se lee
                como una ficha y los rótulos de columna sobran. */}
            <li className="hidden bg-superficie-2 py-2.5 pl-xl pr-2.5 text-micro font-bold tracking-wide text-texto-tenue sm:grid sm:grid-cols-[2.75rem_5.5rem_1fr_5.5rem_5.5rem_2rem] sm:gap-md">
              <span /><span>TICKET</span><span>PERSONA</span><span>INGRESO</span><span>ESPERA</span><span />
            </li>
            {fila.map((it, i) => (
              <li
                key={it.id}
                className={cn(
                  "flex items-center border-t border-division pr-2.5 first:border-t-0",
                  i === 0 ? "bg-accent-50 shadow-[inset_3px_0_0_var(--color-accent)]" : "hover:bg-superficie-2",
                )}
              >
                <button
                  onClick={() => navigate(`/casos/${it.caso}`)}
                  className={cn(
                    "flex min-w-0 flex-1 flex-wrap items-center gap-x-md gap-y-1 py-3.5 pl-xl text-left",
                    "sm:grid sm:grid-cols-[2.75rem_5.5rem_1fr_5.5rem_5.5rem] sm:gap-md",
                  )}
                >
                  <span
                    className={cn(
                      "flex size-6.5 shrink-0 items-center justify-center rounded-pill text-sm font-bold",
                      // Relleno + su color de texto: `accent` a secas es claro en
                      // tema oscuro (para usarse como texto) y el blanco encima
                      // caía a 2,7:1.
                      // `texto-suave` y no `texto-debil`: medido, sobre el gris de
                      // `division` el débil daba 4,36:1, justo por debajo de AA.
                      i === 0 ? "bg-accent-fuerte text-sobre-accent" : "bg-division text-texto-suave",
                    )}
                  >
                    {i + 1}
                  </span>
                  <span className="font-mono font-bold">{it.ticket || casoId(it.caso)}</span>
                  <span className="flex min-w-0 items-center gap-2">
                    <span className="truncate text-md text-texto-medio">{it.persona || casoId(it.caso)}</span>
                    {it.urgente && <Badge tone="error">urgente</Badge>}
                  </span>
                  {/* Sobre la fila destacada (tinte índigo) el `texto-debil`
                      quedaba en 4,31:1. Un paso más oscuro y pasa en ambos fondos. */}
                  <span className="text-base text-texto-suave">{hora(it.ingreso)}</span>
                  <span className="text-base tabular-nums text-texto-suave">{antiguedad(it.ingreso)}</span>
                </button>
                {/* Adelantar a alguien que empeoró esperando, sin llegar a
                    marcarlo urgente (que lo saltea todo). Fuera del botón de la
                    fila: anidar botones no es HTML válido y el clic caería en el
                    de afuera, que navega al caso.

                    Se apaga cuando arriba hay alguien de otra urgencia: los
                    urgentes van primero siempre, así que ahí el clic no movería
                    nada. Estaba habilitado y el toast avisaba «se adelantó un
                    lugar» sin que la fila cambiara. */}
                <button
                  onClick={() => mover.mutate({ id: it.id, posicion: i - 1, quien: it.persona })}
                  disabled={!puedeSubir(fila, i) || mover.isPending}
                  title={
                    i > 0 && !puedeSubir(fila, i)
                      ? "Los urgentes se atienden primero"
                      : "Adelantar un lugar"
                  }
                  aria-label={`Adelantar un lugar a ${it.persona || casoId(it.caso)}`}
                  className={cn(
                    "flex size-8 flex-none items-center justify-center rounded-md transition-colors",
                    !puedeSubir(fila, i)
                      ? "cursor-not-allowed text-transparent"
                      : "text-texto-tenue hover:bg-division hover:text-texto-medio",
                  )}
                >
                  <Icon name="arrowUp" size={15} />
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

/**
 * ¿Tiene sentido ofrecer «adelantar un lugar»?
 *
 * No para el primero, ni para quien tiene arriba a alguien de otra urgencia: la
 * cola ordena los urgentes primero, así que ese movimiento se deshace solo.
 */
/*
 * ¿Adelantar a esta persona cambiaría algo?
 *
 * Se compara el `rango` que manda el servidor —el mismo escalón con el que
 * ordena la cola— y no `urgente` a mano. Con `urgente` la pantalla y el servidor
 * usaban reglas distintas: la flecha quedaba habilitada entre dos personas de
 * prioridad distinta, el toast decía «se adelantó un lugar» y la fila no se
 * movía. Un control que promete algo y no lo cumple es peor que uno apagado.
 */
function puedeSubir(fila, i) {
  if (i <= 0) return false;
  const a = fila[i].rango, b = fila[i - 1].rango;
  if (a == null || b == null) return !!fila[i].urgente === !!fila[i - 1].urgente;
  return a === b;
}

function CargandoFila() {
  return (
    <div className="flex flex-col gap-lg p-lg sm:p-[26px] lg:px-[30px]" role="status" aria-label="Cargando fila…">
      <Skeleton className="h-[78px]" />
      <Skeleton className="h-[130px]" />
      <Skeleton className="h-80" />
    </div>
  );
}

function BotonLlamar({ label, disabled, cargando, onClick }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={cn(
        "flex h-9 items-center justify-center gap-1.5 rounded-md px-3.5 text-base font-semibold transition-colors",
        disabled
          ? "cursor-not-allowed bg-division text-texto-tenue"
          // Antes era el teal de la categoría con texto blanco: medido, daba 2,57:1
        // en los dos temas (defecto que ya venía del diseño original). Llamar al
        // siguiente paciente es LA acción primaria de la pantalla, así que usa el
        // relleno de marca; el teal queda como color de categoría en el icono.
        : "bg-accent-fuerte text-sobre-accent hover:bg-accent-hover",
      )}
    >
      <Icon name="enter" size={14} /> {cargando ? "Llamando…" : label}
    </button>
  );
}
