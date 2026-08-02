import { useNavigate } from "react-router-dom";

import { useLista } from "@/api/queries";
import { useInstitucion } from "@/auth/InstitutionContext";
import { PageHeader } from "@/components/Shell";
import { Badge } from "@/components/ui";
import { Buscador, FiltroSelect, LimpiarFiltros, useBusquedaUrl, useFiltroUrl } from "@/components/ui/filtros";
import { TablaRecurso } from "@/components/ui/tabla";
import { antiguedad } from "@/lib/format";
import { casoId } from "@/lib/format";
import { estadoCaso } from "@/lib/dominio";

const ESTADOS = Object.entries(estadoCaso).map(([value, e]) => ({ value, label: e.label }));
const PRIORIDADES = [
  { value: "urgente", label: "Urgente" },
  { value: "alta", label: "Alta" },
  { value: "normal", label: "Normal" },
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

  // Las áreas de la institución alimentan el selector.
  const areas = useLista("areas", { institucion: institucion?.id, pageSize: 200 });

  const activos = [busqueda, estado, prioridad, area].filter(Boolean).length;
  const limpiar = () => { setTexto(""); setEstado(""); setPrioridad(""); setArea(""); };

  const columnas = [
    {
      key: "id", label: "Caso", orden: "id", className: "w-24",
      render: (c) => <span className="font-mono font-bold">{casoId(c.id)}</span>,
    },
    // Las dos columnas de texto largo se truncan con tooltip en vez de partir en
    // dos líneas: así todas las filas miden lo mismo y la tabla se barre de un vistazo.
    { key: "flujo_titulo", label: "Flujo", orden: "version__flujo__titulo", truncar: true, className: "max-w-56" },
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
      key: "area_nombre", label: "Área", orden: "area_actual__nombre",
      render: (c) => c.area_nombre || "—",
    },
    {
      key: "asignacion", label: "Asignación", orden: "asignado_a__apellido",
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
      <PageHeader subtitle="Consultá y auditá todos los casos del sistema. Hacé clic en un caso para ver su trazabilidad." />
      <div className="px-[30px] pb-[30px] pt-[18px]">
        <TablaRecurso
          clave="casos"
          recurso="casos"
          ordenInicial="-creado"
          params={{
            institucion: institucion?.id,
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
                placeholder="Paciente, documento o flujo…"
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
