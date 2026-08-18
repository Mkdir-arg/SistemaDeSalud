import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/api/client";
import { useInstitucion } from "@/auth/InstitutionContext";
import { Icon } from "@/components/icons";
import { PageHeader } from "@/components/Shell";
import { Badge, Card } from "@/components/ui";
import { EstadoError, EstadoVacio, Skeleton } from "@/components/ui/estados";
import { useFiltroUrl } from "@/components/ui/filtros";
import { antiguedad, casoId } from "@/lib/format";
import { cn } from "@/lib/cn";
import { estadoCaso, estadoVersion, nombreNodo } from "@/lib/dominio";

/**
 * Tablero del hospital: números, tiempos por área y evolución de ingresos.
 * Los gráficos son SVG a mano, sin librería.
 */
const REFRESCO_MS = 60_000;

const RANGOS = [
  { dias: 7, label: "7 días" },
  { dias: 30, label: "30 días" },
  { dias: 90, label: "90 días" },
];
// Techo del rango que acepta el servidor (`MAX_DIAS_RANGO` en
// apps/instituciones/views.py). Acá sirve para que el calendario no ofrezca lo
// que el backend va a recortar sin que se note.
const MAX_DIAS_RANGO = 366;

// Fecha LOCAL, no UTC: `toISOString()` pasa a UTC antes de recortar y Buenos
// Aires es UTC-3 fijo, así que de 21:00 a medianoche devolvía la fecha de
// MAÑANA. El rango se corría un día entero —perdía el más viejo en silencio
// mientras el rótulo seguía diciendo «30 días»— y la serie terminaba en un
// bucket futuro que vale 0, que es justo el punto que la línea dibuja más grande
// porque es «hoy»: el turno noche leía que dejaron de entrar pacientes. Es el
// mismo helper que ya usa Agenda.jsx.
const isoLocal = (d) => new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
const isoHoy = () => isoLocal(new Date());
const isoHace = (dias) => {
  const x = new Date();
  x.setDate(x.getDate() - (dias - 1));
  return isoLocal(x);
};
// "2026-08-15" → "15/08/2026", para poder mostrar el rango que contestó el servidor.
const fechaCorta = (iso) => (iso ? `${iso.slice(8, 10)}/${iso.slice(5, 7)}/${iso.slice(0, 4)}` : "—");

// Color por estado, tomado de los tonos de badge: son los mismos estados, así
// que la dona y las píldoras dicen lo mismo con el mismo color — y siguen al
// tema, cosa que los hex sueltos que había antes no hacían.
const ESTADO_VAR = {
  // «Recibido» es la excepción y no toma el gris de su badge: el gris del badge
  // neutral (#475467) y el del badge gray de «Cerrado» (#5F6879) dan 1,37:1
  // entre sí, o sea que en la dona los dos arcos se funden en uno. Adentro del
  // SVG el color es lo único que separa un estado del otro, y son justo los dos
  // que hay que separar: el arco gris gigante se leía como «casi todo cerrado»
  // con un 8 % de gente que entró y nadie tocó todavía escondida adentro.
  recibido: "var(--color-nodo-cama-sol)",
  en_evaluacion: "var(--color-badge-info-fg)",
  en_espera: "var(--color-badge-amber-fg)",
  derivado: "var(--color-nodo-derivar-sol)",
  atendido: "var(--color-badge-green-fg)",
  cerrado: "var(--color-badge-gray-fg)",
};

/** Semáforo de la espera promedio. Devuelve una variable CSS, no un hex. */
function varEspera(min) {
  // `null` = el backend dice «no hay ninguna medición», y lo manda así a
  // propósito. Sin este caso, `null >= 30` y `null >= 15` son ambos false en JS
  // y la ausencia de dato salía pintada del VERDE de «acá no se espera»: un área
  // sin fila —toda internación lo es— quedaba primera en la comparativa y se le
  // sacaba gente para mandarla a Guardia.
  if (min == null) return "var(--color-texto-tenue)";
  if (min >= 30) return "var(--color-danger)";
  if (min >= 15) return "var(--color-badge-amber-fg)";
  return "var(--color-badge-green-fg)";
}

/** Un número de minutos que puede no existir: "—" y sin unidad, nunca 0. */
const espera = (min) => (min == null ? { v: "—", u: null } : { v: min, u: "min" });

export default function Dashboard() {
  const { institucion } = useInstitucion();
  const navigate = useNavigate();
  const [desde, setDesde] = useFiltroUrl("desde", isoHace(30));
  const [hasta, setHasta] = useFiltroUrl("hasta", isoHoy());
  const [tab, setTab] = useFiltroUrl("area", "general");

  const q = useQuery({
    queryKey: ["tablero", institucion?.id, desde, hasta],
    queryFn: () => api.get(`/instituciones/${institucion.id}/tablero/?desde=${desde}&hasta=${hasta}`),
    enabled: !!institucion,
    refetchInterval: REFRESCO_MS,
    refetchIntervalInBackground: false,
  });

  if (q.isLoading) return <CargandoTablero />;
  if (q.error) {
    return <div className="p-8"><EstadoError error={q.error} titulo="No pudimos cargar el tablero" onReintentar={q.refetch} /></div>;
  }
  const d = q.data;

  return (
    <>
      <PageHeader
        subtitle="Estado general del hospital: carga, tiempos por área y evolución de ingresos."
        right={<span className="text-sm text-texto-tenue">{q.isFetching ? "Actualizando…" : "Se actualiza solo cada 60 s"}</span>}
      />

      <div className="flex flex-col gap-[22px] px-lg pb-8 pt-[22px] sm:px-8">
        <ProcesosDetenidos />
        <RangoFechas desde={desde} hasta={hasta} setDesde={setDesde} setHasta={setHasta} periodo={d.periodo} />
        <SolapasArea areas={d.por_area} tab={tab} setTab={setTab} />

        {tab === "general"
          ? <TableroGeneral d={d} navigate={navigate} />
          : <TableroArea key={tab} areaId={tab} desde={desde} hasta={hasta} navigate={navigate} />}
      </div>
    </>
  );
}

/*
 * Aviso de proceso periódico detenido.
 *
 * Sólo aparece cuando hay algo detenido, y ése es el punto: un cartel verde
 * permanente que dice «todo bien» se vuelve parte del fondo en una semana y
 * nadie lo mira el día que cambia. Lo que tiene que llamar la atención es la
 * excepción.
 *
 * Importa que esté acá y no sólo en la API. Si el reloj del motor se muere, la
 * aplicación sigue respondiendo y las pantallas cargan: lo único que pasa es que
 * los pacientes en espera por tiempo dejan de volver y los avisos de demora no
 * salen. Nadie lo descubre hasta que alguien pregunta por un caso parado hace
 * tres días.
 */
const QUE_SE_ROMPE = {
  correr_tiempos:
    "Los pacientes en espera por tiempo no vuelven al circuito y los avisos de demora no salen.",
  recordar_turnos: "No se están avisando los turnos por confirmar del día siguiente.",
  alertar_saturacion: "No se avisa cuando un establecimiento de la red se satura.",
  respaldar: "Hace más de un día que no se guarda —ni se verifica— un respaldo de la base.",
};

const NOMBRE_PROCESO = {
  correr_tiempos: "Reloj del motor",
  recordar_turnos: "Recordatorios de turno",
  alertar_saturacion: "Alertas de saturación",
  respaldar: "Respaldo de la base",
};

function ProcesosDetenidos() {
  const q = useQuery({
    queryKey: ["estado-procesos"],
    queryFn: () => api.get("/estado/"),
    refetchInterval: REFRESCO_MS,
    refetchIntervalInBackground: false,
    // El endpoint contesta 503 cuando hay algo atrasado: es una respuesta
    // válida con el dato adentro, no un fallo del que haya que reintentar.
    retry: false,
  });

  const datos = q.data || q.error?.data;
  const atrasados = datos?.atrasados || [];
  if (!atrasados.length) return null;

  return (
    <Card className="border-danger-fuerte bg-badge-error-bg p-lg">
      <div className="flex items-start gap-3">
        <Icon name="alert" size={18} className="mt-0.5 shrink-0 text-danger" />
        <div className="min-w-0">
          <h2 className="text-md font-bold text-danger">
            {atrasados.length === 1
              ? "Un proceso del sistema dejó de correr"
              : `${atrasados.length} procesos del sistema dejaron de correr`}
          </h2>
          <ul className="mt-2 flex flex-col gap-1.5">
            {atrasados.map((s) => (
              <li key={s} className="text-md text-texto-medio">
                <strong>{NOMBRE_PROCESO[s] || s}</strong>
                {/* Qué se rompe, no sólo qué se detuvo: «correr_tiempos está
                    atrasado» no le dice nada a quien dirige un hospital. */}
                {QUE_SE_ROMPE[s] ? ` — ${QUE_SE_ROMPE[s]}` : ""}
                {datos.servicios?.[s]?.hace_segundos != null && (
                  <span className="text-texto-debil">
                    {/* En minutos, un respaldo caído hace dos días decía «hace
                        3167 min», que no se lee. La misma escala que el resto
                        del sistema usa para antigüedades. */}
                    {" "}(último: hace {antiguedad(
                      new Date(Date.now() - datos.servicios[s].hace_segundos * 1000).toISOString(),
                    )})
                  </span>
                )}
              </li>
            ))}
          </ul>
          <div className="mt-2.5 text-sm text-texto-debil">
            Avisale a quien administra los servidores: el sistema web anda, lo que
            se detuvo son las tareas que corren solas.
          </div>
        </div>
      </div>
    </Card>
  );
}

// --------------------------------------------------------------------------- //
// Controles
// --------------------------------------------------------------------------- //
function SolapasArea({ areas, tab, setTab }) {
  const items = [{ id: "general", nombre: "General" }, ...(areas || []).map((a) => ({ id: String(a.area_id), nombre: a.nombre }))];
  return (
    <div role="tablist" className="flex flex-wrap gap-0.5 border-b border-borde">
      {items.map((it) => {
        const activo = String(tab) === it.id;
        return (
          <button
            key={it.id}
            role="tab"
            aria-selected={activo}
            onClick={() => setTab(it.id)}
            className={cn(
              "-mb-px border-b-2 px-4 py-2.5 font-display text-md transition-colors",
              activo
                ? "border-accent font-bold text-accent"
                : "border-transparent font-semibold text-texto-debil hover:text-texto-suave",
            )}
          >
            {it.nombre}
          </button>
        );
      })}
    </div>
  );
}

function RangoFechas({ desde, hasta, setDesde, setHasta, periodo }) {
  const hoy = isoHoy();
  const tope = isoHace(MAX_DIAS_RANGO);
  // El servidor recorta lo que exceda el tope y devuelve en `periodo` el rango
  // que usó de verdad. Si no se dice, los números cambian igual al mover el
  // selector y la pantalla no parece rota: parece que funcionó. Dirección pide
  // «desde 2020», lee un total y se lo lleva a una decisión de presupuesto
  // creyendo que son seis años de historia cuando es el último año.
  const recortado = periodo && (periodo.desde !== desde || periodo.hasta !== hasta);
  const campo = "h-9 rounded-md border border-campo-borde bg-superficie px-2.5 text-md text-texto outline-none focus:border-accent";
  return (
    <div className="flex flex-wrap items-center gap-2.5">
      <div className="flex gap-0.5 rounded-md border border-borde bg-superficie-2 p-0.5">
        {RANGOS.map((rg) => {
          const activo = desde === isoHace(rg.dias) && hasta === hoy;
          return (
            <button
              key={rg.dias}
              onClick={() => { setDesde(isoHace(rg.dias)); setHasta(hoy); }}
              className={cn(
                "rounded-sm px-3 py-1.5 text-base font-semibold",
                activo ? "bg-superficie text-accent shadow-card" : "text-texto-debil hover:text-texto-suave",
              )}
            >
              {rg.label}
            </button>
          );
        })}
      </div>
      <span className="text-base text-texto-tenue">o</span>
      <input type="date" value={desde} min={tope} max={hasta} onChange={(e) => e.target.value && setDesde(e.target.value)} className={campo} aria-label="Desde" />
      <span className="text-texto-tenue">→</span>
      <input type="date" value={hasta} min={desde} max={hoy} onChange={(e) => e.target.value && setHasta(e.target.value)} className={campo} aria-label="Hasta" />
      {recortado && (
        <span className="text-base text-texto-medio">
          Se muestran del <strong>{fechaCorta(periodo.desde)}</strong> al <strong>{fechaCorta(periodo.hasta)}</strong>
          {" "}({periodo.dias} días): es todo lo que devuelve el tablero.
        </span>
      )}
    </div>
  );
}

function TituloGrafico({ titulo, sub }) {
  return (
    <div className="mb-3.5 flex items-baseline gap-2">
      <h3 className="font-display text-lg font-bold tracking-tight">{titulo}</h3>
      {sub && <span className="text-sm text-texto-tenue">{sub}</span>}
    </div>
  );
}

function Kpis({ kpis }) {
  return (
    <div className="grid grid-cols-[repeat(auto-fit,minmax(10.5rem,1fr))] gap-3.5">
      {kpis.map((k) => (
        <Card
          key={k.l}
          className={cn(
            "flex flex-col gap-3 p-lg",
            k.destacado && "border-danger-fuerte bg-badge-error-bg",
          )}
        >
          <div className="flex items-center justify-between gap-2">
            <span className="text-base font-semibold text-texto-debil">{k.l}</span>
            <span
              className="flex size-8 shrink-0 items-center justify-center rounded-md"
              // Fondo del icono: el mismo color al 12% sobre la superficie, así
              // funciona igual en claro y en oscuro.
              style={{ background: `color-mix(in srgb, ${k.c} 12%, var(--color-superficie))`, color: k.c }}
            >
              <Icon name={k.icon} size={16} />
            </span>
          </div>
          <div className="font-display text-cifra-xl font-extrabold leading-none tracking-tight tabular-nums" style={{ color: k.c }}>
            {k.v}
            {k.u && <span className="ml-1 text-md font-bold text-texto-tenue">{k.u}</span>}
          </div>
          {/* Un porcentaje sin denominador no se puede auditar: quien decide
              sobreturno necesita saber sobre cuántos turnos se calculó. */}
          {k.sub && <div className="-mt-1 text-sm text-texto-tenue">{k.sub}</div>}
        </Card>
      ))}
    </div>
  );
}

function GrupoMetricas({ titulo, subtitulo, children }) {
  return (
    <section className="flex flex-col gap-3.5">
      <div>
        <h2 className="text-base font-bold uppercase tracking-[.04em] text-texto-debil">{titulo}</h2>
        {subtitulo && <p className="mt-1 text-sm text-texto-tenue">{subtitulo}</p>}
      </div>
      {children}
    </section>
  );
}

// --------------------------------------------------------------------------- //
// Solapa general
// --------------------------------------------------------------------------- //
function TableroGeneral({ d, navigate }) {
  const r = d.resumen;
  // Denominador del ausentismo: los turnos que tuvieron desenlace. El backend
  // deja afuera a los sin registrar a propósito —si no, el indicador se movería
  // con la prolijidad administrativa y no con cuánta gente faltó—, así que el
  // porcentaje no se puede leer sin saber sobre cuántos turnos se calculó.
  const resueltos = (r.turnos_presentes || 0) + (r.turnos_ausentes || 0);
  const requiereAtencion = [
    ...(r.urgentes > 0
      ? [{ l: "Urgentes", v: r.urgentes, icon: "activity", c: "var(--color-danger)", destacado: true }]
      : []),
    ...(r.espera_prom_min >= 30
      ? [{ l: "Espera prom.", ...espera(r.espera_prom_min), icon: "refresh", c: "var(--color-danger)", destacado: true }]
      : []),
    ...(r.turnos_sin_registrar
      ? [{
          l: "Turnos sin registrar",
          v: r.turnos_sin_registrar,
          icon: "calendar",
          c: "var(--color-badge-amber-fg)",
          sub: (
            <button onClick={() => navigate("/agenda")} className="font-semibold text-accent hover:underline">
              Cerrarlos en la agenda
            </button>
          ),
        }]
      : []),
  ];
  const kpis = [
    { l: "Casos activos", v: r.casos_activos, icon: "fileText", c: "var(--color-accent)" },
    // Ámbar y no el teal de la categoría «espera de fila»: ese teal es un color
    // de nodo, pensado para un borde en el lienzo, y como texto da 2,6:1. El
    // ámbar además coincide con el badge «En espera», así que dice lo mismo.
    { l: "En cola ahora", v: r.en_cola, icon: "list", c: "var(--color-badge-amber-fg)" },
    { l: "Urgentes", v: r.urgentes, icon: "activity", c: r.urgentes > 0 ? "var(--color-danger)" : "var(--color-texto-tenue)" },
    { l: "Ingresos", v: r.ingresos, icon: "enter", c: "var(--color-nodo-derivar-sol)" },
    { l: "Cerrados", v: r.cerrados, icon: "clipboard", c: "var(--color-badge-green-fg)" },
    { l: "Espera prom.", ...espera(r.espera_prom_min), icon: "refresh", c: varEspera(r.espera_prom_min) },
    { l: "Atención prom.", v: r.atencion_prom_min ?? 0, u: "min", icon: "users", c: "var(--color-nodo-atencion-sol)" },
    { l: "Resolución prom.", v: r.resolucion_prom_h, u: "h", icon: "map", c: "var(--color-texto-suave)" },
    // Sólo si hay turnos en el período: en un servicio sin agenda un «0 %»
    // ocupa lugar y hace dudar de si está roto.
    ...(r.turnos_periodo
      ? [{
          l: "Ausentismo",
          v: r.ausentismo,
          u: "%",
          icon: "calendar",
          sub: `${r.turnos_ausentes} de ${resueltos} turnos resueltos`,
          // Un consultorio pierde entre el 10 y el 20 % de sus turnos; arriba de
          // 25 hay algo que revisar y de reojo tiene que notarse.
          c: r.ausentismo >= 25
            ? "var(--color-danger)"
            : r.ausentismo >= 15
              ? "var(--color-badge-amber-fg)"
              : "var(--color-nodo-espera-sol)",
        }]
      : []),
    // Los turnos que ya pasaron y siguen abiertos. El backend los cuenta aparte
    // con el comentario «que se vean es la forma de que alguien los cierre», y
    // hasta ahora no se veían en ninguna pantalla que un jefe mire: con 281 de
    // 649 turnos sin resolver, el ausentismo se calcula sobre la mitad de la
    // agenda y nadie sabe que le falta la otra mitad.
    ...(r.turnos_sin_registrar
      ? [{
          l: "Turnos sin registrar",
          v: r.turnos_sin_registrar,
          icon: "calendar",
          c: "var(--color-badge-amber-fg)",
          sub: (
            <button onClick={() => navigate("/agenda")} className="font-semibold text-accent hover:underline">
              Cerrarlos en la agenda
            </button>
          ),
        }]
      : []),
    // Sólo si la institución tiene camas: en un centro ambulatorio un «0 %» de
    // ocupación no dice nada, ocupa lugar y hace dudar de si está roto.
    ...(r.camas_total
      ? [{
          l: "Ocupación camas",
          v: r.ocupacion_camas,
          u: "%",
          icon: "bed",
          // Los mismos umbrales que el tablero de internación: al 90 % es una
          // decisión distinta que al 60 %, y de reojo tiene que notarse.
          c: r.ocupacion_camas >= 90
            ? "var(--color-danger)"
            : r.ocupacion_camas >= 75
              ? "var(--color-badge-amber-fg)"
              : "var(--color-nodo-atencion-sol)",
        }]
      : []),
  ];
  return (
    <>
      {requiereAtencion.length > 0 && (
        <GrupoMetricas titulo="Requiere atención" subtitulo="Indicadores que conviene resolver antes de mirar el análisis.">
          <Kpis kpis={requiereAtencion} />
        </GrupoMetricas>
      )}

      <GrupoMetricas titulo="Pulso operativo" subtitulo="Carga actual y producción del período seleccionado.">
        <Kpis kpis={kpis} />
      </GrupoMetricas>

      {/* Debajo de `lg` las dos columnas se apilan: un gráfico aplastado no
          informa nada. */}
      <div className="grid items-stretch gap-lg lg:grid-cols-[1.6fr_1fr]">
        <Card className="min-w-0 p-xl">
          <TituloGrafico titulo="Ingresos de casos" sub={d.periodo?.agrupacion === "semana" ? "por semana" : "por día"} />
          <LineaIngresos serie={d.serie_ingresos} />
        </Card>
        <Card className="min-w-0 p-xl">
          <TituloGrafico titulo="Distribución por estado" sub="casos no cancelados" />
          <DonaEstados data={d.por_estado} />
        </Card>
      </div>

      <div className="grid items-start gap-lg lg:grid-cols-[1.5fr_1fr]">
        <Card className="min-w-0 p-xl"><Comparativa areas={d.por_area} /></Card>
        <Card className="min-w-0 overflow-hidden p-0">
          <div className="px-xl pb-1 pt-lg">
            <TituloGrafico titulo="Top de demoras" sub="quién espera más ahora" />
          </div>
          <TopDemoras items={d.top_demoras} onAbrir={(id) => navigate(`/casos/${id}`)} />
        </Card>
      </div>

      <Card className="overflow-hidden p-0">
        <div className="px-xl pb-3.5 pt-lg">
          <TituloGrafico titulo="Carga y tiempos por área" sub="ordenado por casos activos" />
        </div>
        <TablaAreas areas={d.por_area} />
      </Card>
    </>
  );
}

// --------------------------------------------------------------------------- //
// Solapa de un área
// --------------------------------------------------------------------------- //
function TableroArea({ areaId, desde, hasta, navigate }) {
  const q = useQuery({
    queryKey: ["tablero-area", areaId, desde, hasta],
    queryFn: () => api.get(`/areas/${areaId}/tablero/?desde=${desde}&hasta=${hasta}`),
  });

  if (q.isLoading) return <CargandoTablero />;
  if (q.error) return <EstadoError error={q.error} titulo="No se pudo cargar el área" onReintentar={q.refetch} />;

  const a = q.data;
  const r = a.resumen;
  const kpis = [
    { l: "Casos activos", v: r.activos, icon: "fileText", c: "var(--color-accent)" },
    // Ámbar y no el teal de la categoría «espera de fila»: ese teal es un color
    // de nodo, pensado para un borde en el lienzo, y como texto da 2,6:1. El
    // ámbar además coincide con el badge «En espera», así que dice lo mismo.
    { l: "En cola ahora", v: r.en_cola, icon: "list", c: "var(--color-badge-amber-fg)" },
    { l: "Ingresos", v: r.ingresos, icon: "enter", c: "var(--color-nodo-derivar-sol)" },
    // `cerrados` y no `atendidos`: `atendido` es un estado de PASO que el motor
    // pisa con `cerrado` en cuanto el caso llega al nodo Fin, así que contaba
    // sólo a los que están parados en ese instante entre la atención y el cierre.
    // Al lado de «Ingresos», que es del período, Guardia leía «Ingresos 106 /
    // Atendidos 1» sobre treinta días en las que cerró 66: el número con el que
    // se discute dotación decía que el servicio no resuelve nada.
    { l: "Cerrados", v: r.cerrados, icon: "clipboard", c: "var(--color-badge-green-fg)" },
    { l: "Espera prom.", ...espera(r.espera_prom_min), icon: "refresh", c: varEspera(r.espera_prom_min) },
    { l: "Atención prom.", v: r.atencion_prom_min ?? 0, u: "min", icon: "users", c: "var(--color-nodo-atencion-sol)" },
    { l: "Resolución prom.", v: r.resolucion_prom_h, u: "h", icon: "map", c: "var(--color-texto-suave)" },
  ];

  return (
    <>
      <Kpis kpis={kpis} />

      {a.flujos?.length > 0 ? (
        <Card className="min-w-0 p-xl"><MapaFlujo key={a.area?.id} flujos={a.flujos} /></Card>
      ) : (
        <Card>
          <EstadoVacio
            titulo="Esta área todavía no tiene un flujo"
            detalle="Asigná un flujo a esta área para ver su mapa y la carga por paso."
            icono="workflow"
          />
        </Card>
      )}

      <div className="grid items-stretch gap-lg lg:grid-cols-[1.6fr_1fr]">
        <Card className="min-w-0 p-xl">
          <TituloGrafico titulo="Ingresos del área" sub={a.periodo?.agrupacion === "semana" ? "por semana" : "por día"} />
          <LineaIngresos serie={a.serie_ingresos} />
        </Card>
        <Card className="min-w-0 p-xl">
          <TituloGrafico titulo="Distribución por estado" sub="casos del área" />
          <DonaEstados data={a.por_estado} />
        </Card>
      </div>

      <div className="grid items-start gap-lg lg:grid-cols-[1.5fr_1fr]">
        <Card className="min-w-0 p-xl">
          <TituloGrafico titulo="Casos por paso del flujo" sub="dónde están los casos ahora" />
          <PorPaso pasos={a.por_paso} />
        </Card>
        <Card className="min-w-0 overflow-hidden p-0">
          <div className="px-xl pb-1 pt-lg">
            <TituloGrafico titulo="Top de demoras" sub="del área, en vivo" />
          </div>
          <TopDemoras items={a.top_demoras} onAbrir={(id) => navigate(`/casos/${id}`)} />
        </Card>
      </div>

      <Card className="overflow-hidden p-0">
        <div className="px-xl pb-3.5 pt-lg">
          <TituloGrafico titulo="Casos activos del área" sub="urgentes primero · clic para abrir" />
        </div>
        <CasosArea casos={a.casos} onAbrir={(id) => navigate(`/casos/${id}`)} />
      </Card>
    </>
  );
}

// --------------------------------------------------------------------------- //
// Tablas
// --------------------------------------------------------------------------- //
const PRIORIDAD_TONO = { urgente: "error", alta: "amber" };

function CasosArea({ casos, onAbrir }) {
  if (!casos?.length) {
    return <EstadoVacio titulo="Sin casos activos" detalle="No hay casos en curso en esta área ahora mismo." />;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[48rem] border-collapse text-md">
        <thead className="bg-superficie-2 text-left">
          <tr>
            {["Paciente", "Estado", "Prioridad", "Paso", "Asignado", "Espera"].map((h) => (
              <th key={h} className="whitespace-nowrap border-t border-division px-xl py-2.5 text-micro font-bold tracking-wide text-texto-tenue">
                {h.toUpperCase()}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {casos.map((c) => {
            const est = estadoCaso[c.estado] || { label: c.estado, tone: "neutral" };
            return (
              <tr key={c.id} onClick={() => onAbrir(c.id)} className="cursor-pointer border-t border-division hover:bg-superficie-2">
                <td className="max-w-48 truncate px-xl py-3 font-semibold">{c.paciente || "Sin paciente"}</td>
                <td className="px-xl py-3"><Badge tone={est.tone}>{est.label}</Badge></td>
                <td className="px-xl py-3">
                  {PRIORIDAD_TONO[c.prioridad]
                    ? <Badge tone={PRIORIDAD_TONO[c.prioridad]}>{c.prioridad}</Badge>
                    : <span className="text-base text-texto-tenue">normal</span>}
                </td>
                <td className="max-w-40 truncate px-xl py-3 text-texto-suave">{c.paso || "—"}</td>
                <td className={cn("max-w-36 truncate px-xl py-3", c.asignado ? "text-texto-suave" : "text-texto-tenue")}>
                  {c.asignado || "—"}
                </td>
                <td className="whitespace-nowrap px-xl py-3 tabular-nums text-texto-debil">{antiguedad(c.creado)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function TablaAreas({ areas }) {
  if (!areas?.length) {
    return <EstadoVacio titulo="Sin áreas con datos" detalle="Cuando haya casos en las áreas, vas a ver su carga y tiempos acá." />;
  }
  const maxAct = Math.max(1, ...areas.map((a) => a.activos));
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[46rem] border-collapse text-md">
        <thead className="bg-superficie-2 text-left">
          <tr>
            {["Área", "Casos activos", "En cola", "Espera prom.", "Atención", "Resolución"].map((h) => (
              <th key={h} className="whitespace-nowrap border-t border-division px-xl py-2.5 text-micro font-bold tracking-wide text-texto-tenue">
                {h.toUpperCase()}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {areas.map((a) => (
            <tr key={a.area_id} className="border-t border-division">
              <td className="max-w-48 truncate px-xl py-3.5 font-semibold">{a.nombre}</td>
              <td className="px-xl py-3.5">
                <span className="flex items-center gap-2.5">
                  <span className="h-2 min-w-10 flex-1 overflow-hidden rounded-sm bg-division">
                    <span className="block h-full rounded-sm bg-accent" style={{ width: `${(a.activos / maxAct) * 100}%` }} />
                  </span>
                  <span className="w-7 text-right font-bold tabular-nums">{a.activos}</span>
                </span>
              </td>
              <td className={cn("px-xl py-3.5 tabular-nums", a.en_cola > 0 ? "text-texto-medio" : "text-texto-tenue")}>{a.en_cola}</td>
              <td className="whitespace-nowrap px-xl py-3.5 font-bold tabular-nums" style={{ color: varEspera(a.espera_prom_min) }}>
                {/* Sin dato es "—", como las dos columnas de al lado. Con `null`
                    React no imprime nada y la celda quedaba como « min» en
                    verde: el área sin medición mostraba el mejor color de la
                    tabla en vez de decir que no midió nada. */}
                {a.espera_prom_min == null
                  ? <span className="font-medium text-texto-tenue">—</span>
                  : <>{a.espera_prom_min} <span className="font-medium text-texto-tenue">min</span></>}
              </td>
              <td className="whitespace-nowrap px-xl py-3.5 tabular-nums text-texto-suave">
                {a.atencion_prom_min ? <>{a.atencion_prom_min} <span className="text-texto-tenue">min</span></> : <span className="text-texto-tenue">—</span>}
              </td>
              <td className="whitespace-nowrap px-xl py-3.5 tabular-nums text-texto-suave">
                {a.resolucion_prom_h ? <>{a.resolucion_prom_h} <span className="text-texto-tenue">h</span></> : <span className="text-texto-tenue">—</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TopDemoras({ items, onAbrir }) {
  if (!items?.length) {
    return <EstadoVacio titulo="Sin demoras" detalle="No hay nadie esperando en cola ahora mismo." icono="activity" />;
  }
  // Cuántas veces está cada paciente en este top. Con el mismo nombre repetido y
  // nada más que los minutos para diferenciar, el jefe cree que hay ocho
  // pacientes demorados cuando hay cuatro personas con ocho casos —y no sabe
  // cuál de las tres filas de «Silvia Castro» abrir—.
  const repetidos = new Map();
  for (const it of items) {
    if (it.paciente) repetidos.set(it.paciente, (repetidos.get(it.paciente) || 0) + 1);
  }
  return (
    <ul>
      {items.map((it, i) => (
        <li key={`${it.caso_id}-${i}`}>
          <button
            onClick={() => onAbrir(it.caso_id)}
            className="flex w-full items-center gap-2.5 border-t border-division px-xl py-2.5 text-left hover:bg-superficie-2"
          >
            <span className={cn(
              "flex size-6 shrink-0 items-center justify-center rounded-pill text-xs font-bold",
              // `texto-suave` y no `texto-debil`: sobre el gris de `division`
              // el débil queda en 4,36:1. `division` es un gris de separador,
              // no una superficie pensada para llevar texto encima.
              i === 0 ? "bg-badge-error-bg text-badge-error-fg" : "bg-division text-texto-suave",
            )}>
              {i + 1}
            </span>
            <span className="min-w-0 flex-1">
              <span className="flex items-center gap-2 truncate text-md font-semibold">
                {it.paciente || "Sin paciente"}
                {it.urgente && <Badge tone="error">urgente</Badge>}
                {repetidos.get(it.paciente) > 1 && (
                  <Badge tone="amber">{repetidos.get(it.paciente)} casos en cola</Badge>
                )}
              </span>
              {/* El código del caso primero: es lo único que distingue dos filas
                  del mismo paciente, que de otro modo salen idénticas salvo por
                  los minutos. */}
              <span className="block truncate text-xs text-texto-tenue">
                {[casoId(it.caso_id), it.area, it.nodo].filter(Boolean).join(" · ")}
              </span>
            </span>
            <span className="shrink-0 font-bold tabular-nums" style={{ color: varEspera(it.espera_min) }}>
              {it.espera_min} <span className="font-medium text-texto-tenue">min</span>
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}

// --------------------------------------------------------------------------- //
// Gráficos
// --------------------------------------------------------------------------- //
const METRICAS = [
  { k: "activos", label: "Activos", get: (a) => a.activos, unit: "" },
  { k: "espera", label: "Espera", get: (a) => a.espera_prom_min, unit: "min", severidad: true },
  { k: "atencion", label: "Atención", get: (a) => a.atencion_prom_min, unit: "min" },
  { k: "resolucion", label: "Resolución", get: (a) => a.resolucion_prom_h, unit: "h" },
];

function Comparativa({ areas }) {
  const [m, setM] = useState("activos");
  const met = METRICAS.find((x) => x.k === m);
  // Sin dato NO es cero. Con `|| 0`, Internación —que al no tener fila nunca
  // tiene medición de espera— salía con la barra en «0 min» y en verde: el mejor
  // número del gráfico que se mira para decidir a qué área se le saca gente. Las
  // áreas sin medición se nombran abajo en vez de competir con un cero.
  const datos = (areas || [])
    .map((a) => ({ nombre: a.nombre, v: met.get(a) }))
    .filter((dd) => dd.v != null)
    .sort((x, y) => y.v - x.v);
  const sinDato = (areas || []).filter((a) => met.get(a) == null).map((a) => a.nombre);
  const max = Math.max(1, ...datos.map((dd) => dd.v));

  return (
    <>
      <div className="mb-lg flex flex-wrap items-center justify-between gap-3">
        <h3 className="font-display text-lg font-bold tracking-tight">Comparativa por área</h3>
        <div className="flex gap-0.5 rounded-md border border-borde bg-superficie-2 p-0.5">
          {METRICAS.map((x) => (
            <button
              key={x.k}
              onClick={() => setM(x.k)}
              className={cn(
                "rounded-sm px-2.5 py-1 text-sm font-semibold",
                m === x.k ? "bg-superficie text-accent shadow-card" : "text-texto-debil hover:text-texto-suave",
              )}
            >
              {x.label}
            </button>
          ))}
        </div>
      </div>
      {datos.length === 0 ? (
        <p className="py-5 text-center text-md text-texto-tenue">Sin áreas con datos.</p>
      ) : (
        <div className="flex flex-col gap-2.5">
          {datos.map((dd) => {
            const c = met.severidad ? varEspera(dd.v) : "var(--color-accent)";
            return (
              <div key={dd.nombre} className="flex items-center gap-3">
                <span className="w-30 shrink-0 truncate text-base text-texto-suave" title={dd.nombre}>{dd.nombre}</span>
                <span className="h-4.5 min-w-8 flex-1 overflow-hidden rounded-sm bg-division">
                  <span className="block h-full rounded-sm transition-[width] duration-300" style={{ width: `${(dd.v / max) * 100}%`, background: c }} />
                </span>
                <span
                  className={cn("w-14 shrink-0 text-right text-base font-bold tabular-nums", !met.severidad && "text-texto-medio")}
                  style={met.severidad ? { color: c } : undefined}
                >
                  {dd.v}{met.unit && <span className="font-medium text-texto-tenue"> {met.unit}</span>}
                </span>
              </div>
            );
          })}
        </div>
      )}
      {sinDato.length > 0 && (
        // Nombrarlas: si desaparecen sin decirlo, el jefe compara siete áreas
        // creyendo que están las ocho.
        <p className="mt-3.5 text-sm text-texto-tenue">
          Sin medición en el período: {sinDato.join(", ")}.
        </p>
      )}
    </>
  );
}

const TIPO_PASO = {
  inicio: "Inicio", formulario: "Formulario", decision: "Decisión", atencion: "Atención",
  espera_fila: "Espera de fila", espera_tiempo: "Espera por tiempo", derivar: "Derivar", estado: "Estado", fin: "Fin",
};

function PorPaso({ pasos }) {
  if (!pasos?.length) {
    return <p className="py-6 text-center text-md text-texto-tenue">No hay casos activos en el flujo de esta área.</p>;
  }
  const max = Math.max(1, ...pasos.map((p) => p.casos));
  return (
    <div className="flex flex-col gap-3">
      {pasos.map((p) => (
        <div key={p.nodo_id} className="flex items-center gap-3">
          <div className="w-36 shrink-0">
            <div className="truncate text-base font-semibold" title={p.titulo}>{p.titulo}</div>
            <div className="text-xs text-texto-tenue">
              {TIPO_PASO[p.tipo] || p.tipo}{p.en_cola ? ` · ${p.en_cola} en cola` : ""}
            </div>
          </div>
          <span className="h-4.5 min-w-8 flex-1 overflow-hidden rounded-sm bg-division">
            <span className="block h-full rounded-sm bg-accent" style={{ width: `${(p.casos / max) * 100}%` }} />
          </span>
          <span className="w-8 shrink-0 text-right font-bold tabular-nums">{p.casos}</span>
        </div>
      ))}
    </div>
  );
}

function LineaIngresos({ serie }) {
  const W = 1000, H = 230, padX = 20, padT = 16, padB = 30;
  const n = serie.length;
  const max = Math.max(1, ...serie.map((s) => s.casos));
  const x = (i) => padX + (i * (W - 2 * padX)) / Math.max(1, n - 1);
  const y = (v) => padT + (1 - v / max) * (H - padT - padB);
  const pts = serie.map((s, i) => [x(i), y(s.casos)]);
  const linea = pts.map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(" ");
  const area = `${linea} L${x(n - 1).toFixed(1)},${H - padB} L${padX},${H - padB} Z`;
  const guias = [3, 2, 1, 0].map((g) => padT + (g / 3) * (H - padT - padB));
  const etiqueta = (f) => `${f.slice(8, 10)}/${f.slice(5, 7)}`;
  const idxLabels = [0, Math.floor((n - 1) / 2), n - 1];

  // El alto va por CSS (`h-auto`) y no como atributo: «auto» no es una longitud
  // SVG válida y el navegador lo venía rechazando en consola desde siempre.
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" className="block h-auto" role="img"
      aria-label={`Ingresos de casos, ${n} puntos, máximo ${max}`}>
      <defs>
        <linearGradient id="grad-ing" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--color-accent)" stopOpacity="0.20" />
          <stop offset="100%" stopColor="var(--color-accent)" stopOpacity="0" />
        </linearGradient>
      </defs>
      {guias.map((ty, i) => (
        <line key={i} x1={padX} y1={ty} x2={W - padX} y2={ty} className="stroke-division" strokeWidth="1" />
      ))}
      <path d={area} fill="url(#grad-ing)" />
      <path d={linea} fill="none" className="stroke-accent" strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
      {pts.map((p, i) => (
        <circle key={i} cx={p[0]} cy={p[1]} r={i === n - 1 ? 4.5 : 2.5}
          className={cn("stroke-accent", i === n - 1 ? "fill-accent" : "fill-superficie")} strokeWidth="1.6" />
      ))}
      {idxLabels.map((i) => (
        <text key={i} x={x(i)} y={H - 8} textAnchor={i === 0 ? "start" : i === n - 1 ? "end" : "middle"}
          fontSize="13" className="fill-texto-tenue">
          {etiqueta(serie[i].fecha)}
        </text>
      ))}
    </svg>
  );
}

function DonaEstados({ data }) {
  const entries = Object.entries(data || {}).filter(([, n]) => n > 0).sort((a, b) => b[1] - a[1]);
  const total = entries.reduce((s, [, n]) => s + n, 0);
  if (!total) return <p className="py-8 text-center text-md text-texto-tenue">Sin casos para mostrar.</p>;

  const r = 56, sw = 18, C = 2 * Math.PI * r;
  let acc = 0;
  const segs = entries.map(([estado, n]) => {
    const frac = n / total;
    const seg = { estado, n, dash: frac * C, offset: -acc * C, c: ESTADO_VAR[estado] || "var(--color-texto-tenue)" };
    acc += frac;
    return seg;
  });

  return (
    <div className="flex flex-wrap items-center gap-lg">
      <svg width="150" height="150" viewBox="0 0 150 150" role="img" aria-label={`Distribución de ${total} casos por estado`}>
        <g transform="rotate(-90 75 75)">
          <circle cx="75" cy="75" r={r} fill="none" className="stroke-division" strokeWidth={sw} />
          {segs.map((s) => (
            // Un `<title>` por arco: al pasar el mouse y en un lector de
            // pantalla el segmento se nombra solo, así que el color deja de ser
            // el único portador de sentido adentro del SVG.
            <circle key={s.estado} cx="75" cy="75" r={r} fill="none" stroke={s.c} strokeWidth={sw}
              strokeDasharray={`${s.dash} ${C - s.dash}`} strokeDashoffset={s.offset}>
              <title>{`${estadoCaso[s.estado]?.label || s.estado}: ${s.n} (${Math.round((s.n / total) * 100)}%)`}</title>
            </circle>
          ))}
        </g>
        <text x="75" y="71" textAnchor="middle" fontSize="26" fontWeight="800" className="fill-texto font-display">{total}</text>
        <text x="75" y="90" textAnchor="middle" fontSize="11" className="fill-texto-tenue">casos</text>
      </svg>
      <ul className="flex min-w-32 flex-1 flex-col gap-2">
        {segs.map((s) => (
          <li key={s.estado} className="flex items-center gap-2.5 text-base">
            <span className="size-2.5 shrink-0 rounded-sm" style={{ background: s.c }} />
            <span className="flex-1 text-texto-suave">{estadoCaso[s.estado]?.label || s.estado}</span>
            <span className="font-bold tabular-nums">{s.n}</span>
            <span className="w-10 text-right tabular-nums text-texto-tenue">{Math.round((s.n / total) * 100)}%</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Mapa del flujo del área
// --------------------------------------------------------------------------- //
function MapaFlujo({ flujos }) {
  const [sel, setSel] = useState(flujos.length === 1 ? 0 : null);

  if (sel === null) {
    return (
      <>
        <TituloGrafico titulo="Flujos del área" sub={`${flujos.length} flujos · tocá uno para ver su mapa`} />
        <div className="grid grid-cols-[repeat(auto-fill,minmax(15rem,1fr))] gap-3">
          {flujos.map((f, i) => {
            const casos = (f.nodos || []).reduce((s, n) => s + (n.casos || 0), 0);
            const est = estadoVersion[f.estado] || { label: "Borrador", tone: "neutral" };
            return (
              <button
                key={f.flujo_id}
                onClick={() => setSel(i)}
                className="flex flex-col gap-3 rounded-lg border border-borde bg-superficie p-lg text-left transition-shadow hover:border-accent-100 hover:shadow-float"
              >
                <span className="flex min-w-0 items-center gap-2.5">
                  <span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-accent-50 text-accent">
                    <Icon name="workflow" size={16} />
                  </span>
                  <span className="min-w-0 truncate text-md font-bold" title={f.titulo}>{f.titulo}</span>
                </span>
                <span className="flex flex-wrap items-center gap-2">
                  <Badge tone={f.relacion === "deriva" ? "amber" : "info"}>{f.relacion === "deriva" ? "Deriva aquí" : "Propio"}</Badge>
                  <Badge tone={est.tone}>{est.label}</Badge>
                  <span className="text-xs text-texto-tenue">v{f.version} · {(f.nodos || []).length} pasos</span>
                </span>
                <span className={cn("text-base", casos > 0 ? "text-texto-suave" : "text-texto-tenue")}>
                  {casos > 0 ? `${casos} caso${casos === 1 ? "" : "s"} en curso` : "Sin casos en curso"}
                </span>
              </button>
            );
          })}
        </div>
      </>
    );
  }

  const flujo = flujos[sel];
  return (
    <>
      <div className="mb-3.5 flex flex-wrap items-center gap-3">
        {flujos.length > 1 && (
          <button
            onClick={() => setSel(null)}
            className="flex h-8 items-center gap-1.5 rounded-md border border-borde bg-superficie px-2.5 text-base font-semibold text-texto-suave hover:bg-superficie-2"
          >
            <Icon name="back" size={14} /> Flujos
          </button>
        )}
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <span className="truncate font-display text-lg font-bold tracking-tight">{flujo.titulo}</span>
          <Badge tone={flujo.relacion === "deriva" ? "amber" : "info"}>{flujo.relacion === "deriva" ? "Deriva aquí" : "Propio"}</Badge>
          <span className="text-sm text-texto-tenue">
            v{flujo.version} · {flujo.relacion === "deriva" ? "el paso resaltado deriva a esta área" : "casos parados en cada paso"}
          </span>
        </div>
      </div>
      <MiniMapaFlujo flujo={flujo} />
    </>
  );
}

function MiniMapaFlujo({ flujo }) {
  const nodos = flujo.nodos || [];
  const conexiones = flujo.conexiones || [];
  if (!nodos.length) return <p className="py-6 text-center text-md text-texto-tenue">El flujo no tiene nodos para dibujar.</p>;

  const W = 168, H = 60, pad = 36;
  const xs = nodos.map((n) => n.x), ys = nodos.map((n) => n.y);
  const minX = Math.min(...xs), minY = Math.min(...ys);
  const vbW = Math.max(...xs) + W - minX + 2 * pad;
  const vbH = Math.max(...ys) + H - minY + 2 * pad;
  const tx = (x) => x - minX + pad;
  const ty = (y) => y - minY + pad;
  const cx = (n) => tx(n.x) + W / 2;
  const cy = (n) => ty(n.y) + H / 2;
  const byId = Object.fromEntries(nodos.map((n) => [n.id, n]));
  const corta = (s, n = 22) => (s && s.length > n ? s.slice(0, n - 1) + "…" : s || "");

  return (
    <div className="max-h-[34rem] overflow-auto rounded-lg border border-division bg-superficie-2">
      <svg viewBox={`0 0 ${vbW} ${vbH}`} width="100%" className="block h-auto"
        style={{ minWidth: Math.min(vbW, 520) }} role="img" aria-label={`Mapa del flujo ${flujo.titulo}`}>
        <defs>
          <marker id="flecha" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M0 0 L10 5 L0 10 z" className="fill-texto-tenue" />
          </marker>
        </defs>
        {conexiones.map((c, i) => {
          const o = byId[c.origen], dn = byId[c.destino];
          if (!o || !dn) return null;
          return <line key={i} x1={cx(o)} y1={cy(o)} x2={cx(dn)} y2={cy(dn)} className="stroke-borde" strokeWidth="1.6" markerEnd="url(#flecha)" />;
        })}
        {nodos.map((n) => {
          const cat = nombreNodo(n.tipo);
          const activo = n.casos > 0;
          return (
            <g key={n.id} transform={`translate(${tx(n.x)} ${ty(n.y)})`}>
              {n.destino && (
                <rect x={-5} y={-5} width={W + 10} height={H + 10} rx="15" fill="none"
                  className="stroke-accent" strokeWidth="1.6" strokeDasharray="5 4" opacity=".7" />
              )}
              <rect width={W} height={H} rx="12"
                fill={activo ? `var(--color-nodo-${n.tipo}-tint)` : "var(--color-superficie)"}
                stroke={n.destino ? "var(--color-accent)" : `var(--color-nodo-${n.tipo}-sol)`}
                strokeWidth={n.destino ? 2.6 : activo ? 2 : 1.3} />
              <rect width="5" height={H} rx="2.5" fill={`var(--color-nodo-${n.tipo}-sol)`} />
              <text x="16" y="24" fontSize="13" fontWeight="700" className="fill-texto">{corta(n.titulo)}</text>
              <text x="16" y="42" fontSize="11.5" fill={`var(--color-nodo-${n.tipo}-sol)`}>{cat}</text>
              {activo && (
                <g transform={`translate(${W - 18} 18)`}>
                  <circle r="14" className="fill-accent-fuerte" />
                  <text textAnchor="middle" y="4.5" fontSize="13" fontWeight="800" className="fill-sobre-accent font-display">{n.casos}</text>
                </g>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function CargandoTablero() {
  return (
    <div className="flex flex-col gap-[22px] px-lg pb-8 pt-[22px] sm:px-8" role="status" aria-label="Cargando tablero…">
      <div className="grid grid-cols-[repeat(auto-fit,minmax(10.5rem,1fr))] gap-3.5">
        {[0, 1, 2, 3, 4, 5, 6, 7].map((i) => <Skeleton key={i} className="h-[104px]" />)}
      </div>
      <div className="grid gap-lg lg:grid-cols-[1.6fr_1fr]">
        <Skeleton className="h-72" />
        <Skeleton className="h-72" />
      </div>
    </div>
  );
}
