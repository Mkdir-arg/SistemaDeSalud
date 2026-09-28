import { useNavigate, useSearchParams } from "react-router-dom";

import { useLista } from "@/api/queries";
import { useInstitucion } from "@/auth/InstitutionContext";
import { Badge } from "@/components/ui";
import { Buscador, FiltroSelect, LimpiarFiltros, useBusquedaUrl, useFiltroUrl } from "@/components/ui/filtros";
import { TablaRecurso } from "@/components/ui/tabla";
import { antiguedad, casoId } from "@/lib/format";
import { estadoCaso } from "@/lib/dominio";

const ESTADOS = Object.entries(estadoCaso).map(([value, e]) => ({ value, label: e.label }));
const PRIORIDADES = [
  { value: "urgente", label: "Urgente" },
  { value: "alta", label: "Alta" },
  { value: "normal", label: "Normal" },
];
const GRUPOS = [
  { value: "activos", label: "Activos" },
  { value: "cerrados", label: "Cerrados" },
  { value: "cancelados", label: "Cancelados" },
  { value: "todos", label: "Todos" },
];

function asignacion(c) {
  if (c.asignado_nombre) return c.asignado_nombre;
  if (c.nodo_tipo === "espera") return "En fila";
  if (c.nodo_tipo === "tiempo") return "Dormido";
  return null;
}

export default function Casos() {
  const { institucion } = useInstitucion();
  const navigate = useNavigate();

  const [texto, setTexto, busqueda] = useBusquedaUrl("q");
  const [estado, setEstado] = useFiltroUrl("estado");
  const [prioridad, setPrioridad] = useFiltroUrl("prioridad");
  const [area, setArea] = useFiltroUrl("area");
  const [grupo, setGrupo] = useFiltroUrl("grupo_estado", "activos");
  const [params, setParams] = useSearchParams();

  // Las áreas de la institución alimentan el selector.
  const areas = useLista("areas", { institucion: institucion?.id, pageSize: 200 });
  const activosTotal = useLista("casos", {
    institucion: institucion?.id,
    grupo_estado: "activos",
    pageSize: 1,
  }, { enabled: !!institucion });

  const activos = [busqueda, estado, prioridad, area].filter(Boolean).length;
  const limpiar = () => {
    setTexto("");
    const siguientes = new URLSearchParams(params);
    ["q", "estado", "prioridad", "area"].forEach((clave) => siguientes.delete(clave));
    setParams(siguientes, { replace: true });
  };

  const columnas = [
    {
      key: "id", label: "Caso", orden: "id", className: "w-24",
      render: (c) => <span className="font-mono font-bold">{casoId(c.id)}</span>,
    },
    {
      key: "ciudadano_nombre", label: "Paciente y flujo", orden: "ciudadano__apellido", className: "min-w-44 max-w-64",
      render: (c) => <div className="min-w-0"><strong className="block truncate font-semibold" title={c.ciudadano_nombre || "Sin paciente"}>{c.ciudadano_nombre || "Sin paciente"}</strong><span className="block truncate text-sm text-texto-debil" title={c.flujo_titulo}>{c.flujo_titulo}</span></div>,
    },
    {
      key: "paso_actual", label: "Paso actual", orden: "nodo_actual__titulo",
      truncar: true, className: "max-w-48",
      render: (c) => <span className="text-texto-suave">{c.paso_actual || "—"}</span>,
    },
    {
      key: "estado", label: "Estado", orden: "estado",
      render: (c) => {
        const e = estadoCaso[c.estado] || { label: c.estado_display, tone: "neutral" };
        return <Badge tone={e.tone}>{e.label}</Badge>;
      },
    },
    {
      key: "prioridad", label: "Prioridad", orden: "prioridad_rank",
      render: (c) => <Badge tone={c.prioridad === "urgente" ? "error" : c.prioridad === "alta" ? "amber" : "neutral"}>{c.prioridad_display || c.prioridad}</Badge>,
    },
    {
      key: "area_nombre", label: "Área", orden: "area_actual__nombre",
      render: (c) => c.area_nombre || "—",
    },
    {
      key: "asignacion", label: "Asignado a", orden: "asignado_a__apellido",
      render: (c) => {
        const a = asignacion(c);
        return a ? <span className="text-texto-medio">{a}</span>
                 : <span className="text-texto-tenue">Sin asignar</span>;
      },
    },
    {
      // Columna nueva: para triar trabajo, cuánto lleva abierto importa más que
      // la fecha exacta de creación.
      key: "creado", label: "Antigüedad", orden: "creado", className: "w-28 tabular-nums",
      render: (c) => <span className="text-texto-suave">{antiguedad(c.creado)}</span>,
    },
  ];

  return (
    <>
      <div className="px-[30px] pb-[30px] pt-[24px]">
        <h2 className="text-xl font-bold">Casos</h2>
        <p className="mt-1 text-sm text-texto-debil">Todos los casos de la institución. Abrí uno para ver su trazabilidad.</p>
        <nav aria-label="Estado de los casos" className="mb-4 flex flex-wrap gap-1 border-b border-division">
          {GRUPOS.map(({ value, label }) => (
            <button key={value} type="button" onClick={() => setGrupo(value)} aria-current={grupo === value ? "page" : undefined}
              className={`border-b-2 px-3 pb-2.5 pt-2 text-sm font-semibold ${grupo === value ? "border-accent text-accent" : "border-transparent text-texto-debil hover:text-texto-suave"}`}>
              {label}{value === "activos" && !activosTotal.isLoading && !activosTotal.error ? ` (${activosTotal.total})` : ""}
            </button>
          ))}
        </nav>
        <TablaRecurso
          clave="casos"
          recurso="casos"
          exportable
          ordenInicial="-creado"
          params={{
            institucion: institucion?.id,
            grupo_estado: grupo === "todos" ? undefined : grupo,
            search: busqueda || undefined,
            estado: estado || undefined,
            prioridad: prioridad || undefined,
            area_actual: area || undefined,
          }}
          columnas={columnas}
          onRowClick={(c) => navigate(`/casos/${c.id}`)}
          vacio={{
            titulo: activos ? "Ningún caso coincide con los filtros" : "Todavía no hay casos",
            detalle: activos ? "Probá quitando alguno." : "Los casos aparecen acá al iniciarse desde una bandeja.",
          }}
          barra={
            <>
              <Buscador
                valor={texto}
                onChange={setTexto}
                placeholder="Paciente, DNI o flujo…"
                className="w-64"
              />
              <FiltroSelect etiqueta="Filtrar por estado" valor={estado} onChange={setEstado} opciones={ESTADOS} todos="Todos los estados" />
              <FiltroSelect etiqueta="Filtrar por prioridad" valor={prioridad} onChange={setPrioridad} opciones={PRIORIDADES} todos="Toda prioridad" />
              <FiltroSelect
                etiqueta="Filtrar por área"
                valor={area}
                onChange={setArea}
                opciones={areas.filas.map((a) => ({ value: String(a.id), label: a.nombre }))}
                todos="Todas las áreas"
              />
              <LimpiarFiltros activos={activos} onLimpiar={limpiar} />
            </>
          }
        />
      </div>
    </>
  );
}
