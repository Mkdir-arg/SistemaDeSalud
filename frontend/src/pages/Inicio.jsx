import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { api } from "@/api/client";
import { useInstitucion } from "@/auth/InstitutionContext";
import { Ayuda, Badge, Card, Spinner } from "@/components/ui";
import { EstadoError } from "@/components/ui/estados";
import { BarrasIngresos, KpiDireccion, ResumenDireccion, alertasOperacion, isoHace, isoHoy } from "@/components/tablero";
import { duracionMinutos } from "@/lib/format";

const PASOS = [
  ["areas", "Áreas activas", "/estructura", "Creá o activá un área."],
  ["usuarios", "Usuarios activos", "/administracion", "Dale acceso a una persona de la institución."],
  ["asignaciones", "Personal asignado a un área", "/administracion", "Asigná una persona activa a un área activa."],
  ["agenda_profesional", "Agenda profesional con horarios", "/estructura", "Asigná un profesional y cargá horarios."],
  ["agenda_recurso", "Agenda de recurso con horarios", "/estructura", "Creá una agenda de recurso con horarios."],
  ["flujo_operativo", "Flujo publicado", "/flujos", "Publicá un flujo para iniciar nuevas atenciones."],
];

export default function Inicio() {
  const { institucion, puedeVer } = useInstitucion();
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["metricas-institucion", institucion?.id],
    queryFn: () => api.get(`/instituciones/${institucion.id}/metricas/`),
    enabled: institucion?.id != null,
  });
  const puesta = useQuery({
    queryKey: ["puesta-en-marcha", institucion?.id],
    queryFn: () => api.get(`/instituciones/${institucion.id}/puesta-en-marcha/`),
    enabled: institucion?.id != null && (puedeVer("config_institucional") || puedeVer("casos_operar")),
  });
  const supervision = puedeVer("supervision");
  const desde = isoHace(7);
  const hasta = isoHoy();
  const tablero = useQuery({
    queryKey: ["tablero", institucion?.id, desde, hasta],
    queryFn: () => api.get(`/instituciones/${institucion.id}/tablero/?desde=${desde}&hasta=${hasta}`),
    enabled: institucion?.id != null && supervision,
  });

  if (!institucion) return <Spinner />;

  const enConfiguracion = institucion.estado === "en_alta";
  const guiaActiva = enConfiguracion && puedeVer("config_institucional");
  const pendientes = puesta.data ? PASOS.filter(([clave]) => !puesta.data[clave]) : [];
  const completados = PASOS.length - pendientes.length;
  const primerPendiente = pendientes[0]?.[0];
  const metricas = [
    { valor: data?.staff, titulo: "Personal activo", criterio: "Con acceso a esta institución" },
    { valor: data?.areas, titulo: "Áreas", criterio: "Estructura institucional" },
    { valor: data?.casos_activos, titulo: "Casos activos", criterio: "Sin cerrar ni cancelar" },
    { valor: data?.turnos_hoy, titulo: "Turnos de hoy", criterio: "No cancelados del día" },
  ];
  const accesos = [
    { titulo: "Bandeja", detalle: "Casos en curso y sin asignar", ruta: "/bandeja", cap: "casos_operar" },
    { titulo: "Turnos de hoy", detalle: "Agenda de profesionales y recursos", ruta: "/agenda", cap: "turnos" },
    { titulo: "Pacientes", detalle: "Buscar, registrar o consultar pacientes", ruta: "/pacientes", cap: "padron_admision" },
  ].filter(({ cap }) => puedeVer(cap));
  const accesosRapidos = accesos.map(({ titulo, detalle, ruta }) => <Link key={ruta} to={ruta} data-tour={`inicio-${ruta.slice(1)}`} className="flex items-center justify-between rounded-lg border border-borde bg-superficie px-4 py-4 hover:border-accent-100 hover:shadow-card"><span><strong className="text-sm">{titulo}</strong><span className="mt-1 block text-xs text-texto-suave">{detalle}</span></span><span className="text-accent" aria-hidden="true">›</span></Link>);
  const resumen = tablero.data?.resumen;
  const alertas = supervision ? alertasOperacion(resumen) : [];
  const areas = [...(tablero.data?.por_area || [])].sort((a, b) => b.activos - a.activos).slice(0, 5);
  const maxActivosArea = Math.max(1, ...areas.map((area) => area.activos));

  return <div className="mx-auto max-w-[1500px] px-lg py-6 sm:px-6">
    <div data-tour="inicio-institucion" className="mb-5 flex flex-wrap items-start justify-between gap-3">
      <div><h2 className="text-xl font-bold tracking-tight">{institucion.nombre}</h2>
        <p className="mt-1 text-sm text-texto-suave">{institucion.tipo || "Institución"} · Datos actuales</p></div>
      <Badge tone={institucion.activa === false ? "gray" : enConfiguracion ? "amber" : "green"}>
        {institucion.activa === false ? "Inactiva" : enConfiguracion ? "En configuración" : "Activa"}
      </Badge>
    </div>

    {puedeVer("casos_operar") && puesta.data && !puesta.data.flujo_operativo && !enConfiguracion &&
      <Card className="mb-4 border-badge-amber-fg/25 bg-badge-amber-bg p-4 text-badge-amber-fg" role="status">
        <strong>Todavía no hay un flujo operativo publicado.</strong>
        <p className="mt-1 text-sm">Podés revisar casos existentes en la Bandeja. Para iniciar nuevas atenciones, {puedeVer("diseno_flujos") ? <Link to="/flujos" className="font-semibold underline">publicá un flujo</Link> : "pedile a un configurador que publique un flujo"}.</p>
      </Card>}

    {guiaActiva && <div className="mb-5 grid items-start gap-4 lg:grid-cols-[minmax(0,1.8fr)_minmax(250px,0.8fr)]">
      <Card className="overflow-hidden" aria-label="Puesta en marcha">
        <div className="border-b border-division p-4">
          <h3 className="text-lg font-bold">Puesta en marcha</h3>
          <p className="mt-1 text-sm text-texto-suave">Completá estos pasos para empezar a operar. Cada paso te lleva a su sección.</p>
          {puesta.data && <div className="mt-4 flex items-center gap-3 text-xs text-texto-suave">
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-superficie-2" role="progressbar" aria-valuenow={completados} aria-valuemin={0} aria-valuemax={PASOS.length} aria-label="Avance de la puesta en marcha">
              <div className="h-full rounded-full bg-accent-fuerte" style={{ width: `${completados / PASOS.length * 100}%` }} />
            </div>
            <span className="whitespace-nowrap">{completados} de {PASOS.length} pasos</span>
          </div>}
        </div>
        {puesta.isLoading ? <p className="p-4 text-sm">Comprobando configuración…</p> : puesta.error ? <div className="p-4"><EstadoError error={puesta.error} onReintentar={puesta.refetch} titulo="No se pudo comprobar la configuración" /></div> : <ol className="divide-y divide-division">
          {PASOS.map(([clave, titulo, ruta, detalle], indice) => {
            const listo = puesta.data?.[clave];
            const actual = clave === primerPendiente;
            return <li key={clave} className={`flex items-center gap-3 px-4 py-3 ${actual ? "bg-accent-50" : ""}`}>
              <span aria-hidden="true" className={`flex size-7 shrink-0 items-center justify-center rounded-full border text-xs font-bold ${listo ? "border-badge-green-fg/30 bg-badge-green-bg text-badge-green-fg" : actual ? "border-accent bg-accent-fuerte text-sobre-accent" : "border-borde bg-superficie-2 text-texto-suave"}`}>{listo ? "✓" : indice + 1}</span>
              <div className="min-w-0 flex-1"><strong className="block text-sm">{titulo}</strong><p className="mt-0.5 text-xs text-texto-suave">{detalle}{clave === "agenda_recurso" && " No requiere profesional."}</p></div>
              {(clave !== "flujo_operativo" || puedeVer("diseno_flujos")) && <Link to={ruta} className={`shrink-0 rounded-md border px-3 py-1.5 text-xs font-semibold ${actual ? "hen-cta border-transparent text-sobre-accent" : "border-borde bg-superficie text-accent hover:border-accent"}`}>
                {listo ? "Ver" : actual ? "Continuar" : "Ir"}
              </Link>}
            </li>;
          })}
        </ol>}
      </Card>
      <aside className="space-y-3">
        <Card className="p-4"><h3 className="text-sm font-bold">¿Necesitás ayuda?</h3><p className="mt-2 text-xs text-texto-suave">Cada paso tiene un enlace directo a la sección donde se completa.</p></Card>
        <Card className="p-4"><h3 className="text-sm font-bold">Estado de la institución</h3><p className="mt-2 text-xs text-texto-suave">La institución permanece en configuración mientras se completan los pasos. Las agendas de recurso no requieren profesional.</p></Card>
      </aside>
    </div>}

    <details key={String(guiaActiva)} open={!guiaActiva} className={guiaActiva ? "mb-4 rounded-lg border border-borde bg-superficie p-3 text-sm" : ""}>
      <summary className={guiaActiva ? "cursor-pointer font-semibold text-accent" : "hidden"}>Ver métricas y accesos de la institución</summary>
      {guiaActiva && <p className="mb-3 mt-2 text-xs text-texto-suave">Estas cifras y accesos siguen disponibles durante la configuración.</p>}

    {supervision ? tablero.error ? <Card className="mb-5 p-4"><EstadoError error={tablero.error} onReintentar={tablero.refetch} titulo="No se pudo cargar el resumen del tablero" /></Card> : tablero.isLoading ? <Card className="mb-5 p-4" role="status">Cargando resumen de los últimos 7 días…</Card> : resumen ? <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
      <KpiDireccion titulo="Casos activos" valor={resumen.casos_activos} detalle={`${resumen.urgentes} urgentes · ${resumen.en_cola} en cola`} />
      <KpiDireccion titulo="Espera promedio" valor={resumen.espera_prom_min == null ? "—" : duracionMinutos(resumen.espera_prom_min)} detalle={resumen.en_cola ? `${resumen.en_cola} en cola ahora` : "Sin fila actual"} />
      <KpiDireccion titulo="Turnos del período" valor={resumen.turnos_periodo} detalle={`${resumen.turnos_ausentes} ausentes · ${resumen.turnos_sin_registrar} sin registrar`} />
      <KpiDireccion titulo="Casos cerrados" valor={resumen.cerrados} detalle="En los últimos 7 días" />
      {!!resumen.camas_total && <KpiDireccion titulo="Ocupación de camas" valor={resumen.camas_operativas ? `${resumen.ocupacion_camas} %` : "—"} detalle={resumen.camas_operativas ? `${resumen.camas_ocupadas} de ${resumen.camas_operativas} operativas` : "Sin camas operativas"} />}
    </div> : <Card className="mb-5 p-4 text-sm text-texto-suave">No hay datos del tablero para este período.</Card> : error ? <Card className="mb-5 p-4"><EstadoError error={error} onReintentar={refetch} titulo="No se pudieron cargar las métricas" /></Card> :
      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {metricas.map((metrica) => <Card key={metrica.titulo} className="p-4">
          <h3 className="text-xs text-texto-suave">{metrica.titulo}</h3>
          <p className="mt-2 text-xxl font-bold tabular-nums">{isLoading ? "…" : metrica.valor ?? "—"}</p>
          <p className="mt-1 text-xs text-texto-suave">{metrica.criterio}</p>
        </Card>)}
      </div>}

    <div className="grid gap-3 lg:grid-cols-[minmax(0,1.6fr)_minmax(260px,1fr)]">
      {supervision && <Card className="min-w-0 p-4"><div className="flex justify-between gap-2"><h3 className="text-sm font-bold">Ingresos de casos</h3><span className="text-xs text-texto-suave">Últimos 7 días · {resumen?.ingresos ?? "—"} ingresos</span></div>
        {tablero.isLoading ? <p className="mt-4 text-sm text-texto-suave">Cargando ingresos…</p> : tablero.error ? <EstadoError error={tablero.error} onReintentar={tablero.refetch} titulo="No se pudieron cargar los ingresos" /> : <BarrasIngresos serie={tablero.data?.serie_ingresos || []} />}
      </Card>}
      <Card className="overflow-hidden">
        <div className="border-b border-division px-4 py-3"><div className="flex items-center gap-2"><h3 className="text-md font-bold">Requiere atención</h3><Ayuda etiqueta="Ayuda sobre Requiere atención"><strong>Configuración:</strong> pasos de puesta en marcha sin completar. <strong>Operación:</strong> casos urgentes activos, espera promedio de 30 minutos o más y turnos pasados sin presente ni ausente registrado.</Ayuda></div><p className="mt-1 text-xs text-texto-suave">Pendientes de configuración{supervision ? " y operación" : ""} que podés revisar desde tu rol.</p></div>
        <h4 className="px-4 pt-3 text-xs font-bold uppercase text-texto-suave">Configuración</h4>
        {puesta.isLoading ? <p className="p-4 text-sm text-texto-suave">Comprobando pendientes…</p> : puesta.error ? <div className="p-4"><EstadoError error={puesta.error} onReintentar={puesta.refetch} titulo="No se pudieron consultar los pendientes" /></div> : !puesta.data ? <p className="p-4 text-sm text-texto-suave">No hay información de configuración para este rol.</p> : pendientes.length ? <ul className="divide-y divide-division">
          {pendientes.map(([clave, titulo, ruta, detalle]) => <li key={clave} className="flex flex-wrap items-center justify-between gap-2 px-4 py-3"><div><strong className="text-sm">{titulo}</strong><p className="text-xs text-texto-suave">{detalle}</p></div>{(clave !== "flujo_operativo" || puedeVer("diseno_flujos")) && <Link to={ruta} className="rounded-md border border-borde px-3 py-1.5 text-xs text-accent hover:bg-accent-50">Revisar</Link>}</li>)}
        </ul> : <p className="p-4 text-sm text-texto-suave">No hay pendientes de configuración.</p>}
        {supervision && <><h4 className="border-t border-division px-4 pt-3 text-xs font-bold uppercase text-texto-suave">Operación</h4>
          {tablero.isLoading ? <p className="p-4 text-sm text-texto-suave">Comprobando operación…</p> : tablero.error ? <div className="p-4"><EstadoError error={tablero.error} onReintentar={tablero.refetch} titulo="No se pudieron consultar las alertas" /></div> : alertas.length ? <ul className="divide-y divide-division">{alertas.map((alerta) => <li key={alerta.l} className="flex justify-between gap-3 px-4 py-3 text-sm"><strong>{alerta.l}</strong><span>{alerta.v}{alerta.u ? ` ${alerta.u}` : ""}</span></li>)}</ul> : <p className="p-4 text-sm text-texto-suave">Sin urgencias, esperas altas ni turnos pendientes de cierre.</p>}
        </>}
      </Card>
      {!supervision && <div className="space-y-3">{accesosRapidos}</div>}
    </div>
    {supervision && <div className="mt-3">{tablero.isLoading ? <Card className="p-4 text-sm text-texto-suave">Cargando áreas…</Card> : tablero.error ? <Card className="p-4"><EstadoError error={tablero.error} onReintentar={tablero.refetch} titulo="No se pudieron cargar las áreas" /></Card> : <ResumenDireccion titulo="Carga por área" filas={areas.map((area) => ({ nombre: area.nombre, valor: area.activos, total: maxActivosArea, detalle: `${area.en_cola} en cola` }))} vacio="Sin áreas con casos activos" limite={5} />}</div>}
    {supervision && <div className="mt-3 space-y-3">
        <Link to="/dashboard" className="flex items-center justify-between rounded-lg border border-borde bg-superficie px-4 py-3 text-sm font-semibold text-accent hover:border-accent-100">Ver tablero completo <span aria-hidden="true">›</span></Link>
        {accesosRapidos}
    </div>}
    </details>
  </div>;
}
