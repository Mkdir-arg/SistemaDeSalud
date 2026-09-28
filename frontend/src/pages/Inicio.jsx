import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { api } from "@/api/client";
import { useInstitucion } from "@/auth/InstitutionContext";
import { Badge, Card, Spinner } from "@/components/ui";
import { EstadoError } from "@/components/ui/estados";

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

  if (!institucion) return <Spinner />;

  const enConfiguracion = institucion.estado === "en_alta";
  const pendientes = puesta.data ? PASOS.filter(([clave]) => !puesta.data[clave]) : [];
  const metricas = [
    { valor: data?.staff, titulo: "Personal activo", criterio: "Con acceso a esta institución" },
    { valor: data?.areas, titulo: "Áreas", criterio: "Estructura institucional" },
    { valor: data?.casos_activos, titulo: "Casos activos", criterio: "Sin cerrar ni cancelar" },
    { valor: data?.subareas, titulo: "Subáreas", criterio: "Dentro de las áreas" },
  ];
  const accesos = [
    { titulo: "Bandeja", detalle: "Casos en curso y sin asignar", ruta: "/bandeja", cap: "casos_operar" },
    { titulo: "Turnos de hoy", detalle: "Agenda de profesionales y recursos", ruta: "/agenda", cap: "turnos" },
    { titulo: "Padrón de pacientes", detalle: "Buscar, registrar o actualizar pacientes", ruta: "/padron", cap: "padron_admision" },
  ].filter(({ cap }) => puedeVer(cap));

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

    {enConfiguracion && puedeVer("config_institucional") && <Card className="mb-5 p-4" aria-label="Puesta en marcha">
      <h3 className="text-lg font-bold">Puesta en marcha</h3>
      <p className="mt-1 text-sm text-texto-suave">Completá estos pasos para empezar a operar. Las agendas de recurso no requieren profesional.</p>
      {puesta.isLoading ? <p className="mt-3 text-sm">Comprobando configuración…</p> : puesta.error ? <EstadoError error={puesta.error} onReintentar={puesta.refetch} titulo="No se pudo comprobar la configuración" /> : <ul className="mt-4 grid gap-2 sm:grid-cols-2">
        {PASOS.map(([clave, titulo, ruta, detalle]) => <li key={clave} className="rounded-md border border-division p-3">
          <div className="flex items-center gap-2"><Badge tone={puesta.data?.[clave] ? "green" : "amber"}>{puesta.data?.[clave] ? "Listo" : "Pendiente"}</Badge><strong className="text-sm">{titulo}</strong></div>
          {!puesta.data?.[clave] && <p className="mt-2 text-sm text-texto-suave">{detalle} {(clave !== "flujo_operativo" || puedeVer("diseno_flujos")) && <Link to={ruta} className="font-semibold text-accent underline">Ir a la sección</Link>}</p>}
        </li>)}
      </ul>}
    </Card>}

    {error ? <Card className="mb-5 p-4"><EstadoError error={error} onReintentar={refetch} titulo="No se pudieron cargar las métricas" /></Card> :
      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {metricas.map((metrica) => <Card key={metrica.titulo} className="p-4">
          <h3 className="text-xs text-texto-suave">{metrica.titulo}</h3>
          <p className="mt-2 text-xxl font-bold tabular-nums">{isLoading ? "…" : metrica.valor ?? "—"}</p>
          <p className="mt-1 text-xs text-texto-suave">{metrica.criterio}</p>
        </Card>)}
      </div>}

    <div className="grid gap-3 lg:grid-cols-[minmax(0,1.6fr)_minmax(260px,1fr)]">
      <Card className="overflow-hidden">
        <div className="border-b border-division px-4 py-3"><h3 className="text-md font-bold">Requiere atención</h3><p className="mt-1 text-xs text-texto-suave">Pendientes de configuración que podés resolver desde tu rol.</p></div>
        {puesta.isLoading ? <p className="p-4 text-sm text-texto-suave">Comprobando pendientes…</p> : puesta.error ? <div className="p-4"><EstadoError error={puesta.error} onReintentar={puesta.refetch} titulo="No se pudieron consultar los pendientes" /></div> : !puesta.data ? <p className="p-4 text-sm text-texto-suave">No hay información de configuración para este rol.</p> : pendientes.length ? <ul className="divide-y divide-division">
          {pendientes.map(([clave, titulo, ruta, detalle]) => <li key={clave} className="flex flex-wrap items-center justify-between gap-2 px-4 py-3"><div><strong className="text-sm">{titulo}</strong><p className="text-xs text-texto-suave">{detalle}</p></div>{(clave !== "flujo_operativo" || puedeVer("diseno_flujos")) && <Link to={ruta} className="rounded-md border border-borde px-3 py-1.5 text-xs text-accent hover:bg-accent-50">Revisar</Link>}</li>)}
        </ul> : <p className="p-4 text-sm text-texto-suave">No hay pendientes de configuración.</p>}
      </Card>
      <div className="space-y-3">
        {accesos.map(({ titulo, detalle, ruta }) => <Link key={ruta} to={ruta} data-tour={`inicio-${ruta.slice(1)}`} className="flex items-center justify-between rounded-lg border border-borde bg-superficie px-4 py-4 hover:border-accent-100 hover:shadow-card"><span><strong className="text-sm">{titulo}</strong><span className="mt-1 block text-xs text-texto-suave">{detalle}</span></span><span className="text-accent" aria-hidden="true">›</span></Link>)}
      </div>
    </div>
  </div>;
}
