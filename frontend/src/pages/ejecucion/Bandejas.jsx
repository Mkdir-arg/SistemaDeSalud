import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { api } from "@/api/client";
import { useAccion, useLista } from "@/api/queries";
import { useAuth } from "@/auth/AuthContext";
import { useInstitucion } from "@/auth/InstitutionContext";
import { Badge, Button, Field, Modal, Select } from "@/components/ui";
import { Buscador, FiltroSelect, useBusquedaUrl, useFiltroUrl } from "@/components/ui/filtros";
import { BuscadorPaciente, PacienteElegido } from "@/components/ui/paciente";
import { TablaRecurso } from "@/components/ui/tabla";
import { useToast } from "@/components/ui/toast";
import { antiguedad, casoId, fechaHora } from "@/lib/format";

const PRIORIDADES = [
  { value: "urgente", label: "Urgente" },
  { value: "alta", label: "Alta" },
  { value: "normal", label: "Normal" },
];

export default function Bandejas() {
  const { user } = useAuth();
  const { institucion, puedeVer } = useInstitucion();
  const navigate = useNavigate();
  const toast = useToast();
  const [tab, setTab] = useFiltroUrl("bandeja", "mios");
  const [texto, setTexto, busqueda] = useBusquedaUrl("q");
  const [prioridad, setPrioridad] = useFiltroUrl("prioridad");
  const [flujo, setFlujo] = useFiltroUrl("flujo");
  const [nuevo, setNuevo] = useState(false);

  // Cada pestaña es un filtro DEL SERVIDOR. Antes la pantalla traía todos los
  // casos de la institución y separaba las bandejas en el navegador, así que con
  // volumen real repartía los primeros 25 que devolvía la API.
  const params = {
    institucion: institucion?.id,
    ...(tab === "mios" ? { asignado_a: user?.id, grupo_estado: "activos" }
      : tab === "sin" ? { tomables: true } : { grupo_estado: "activos" }),
    search: busqueda || undefined,
    prioridad: prioridad || undefined,
    flujo: flujo || undefined,
  };

  // Las cuentas de las pestañas piden una sola fila: lo único que interesa es el
  // `count` que devuelve la API igual.
  const nMios = useLista("casos", { institucion: institucion?.id, asignado_a: user?.id, grupo_estado: "activos", pageSize: 1 });
  const nSin = useLista("casos", { institucion: institucion?.id, tomables: true, pageSize: 1 });
  const nTodos = useLista("casos", { institucion: institucion?.id, grupo_estado: "activos", pageSize: 1 });
  const flujos = useLista("flujos", { institucion: institucion?.id, pageSize: 200 }, { enabled: !!institucion?.id });

  const tomar = useAccion((caso) => api.post(`/casos/${caso}/tomar/`), {
    onError: (e) => toast.deError(e, "No se pudo tomar el caso."),
  });

  const columnas = [
    {
      key: "id", label: "Caso", orden: "id", className: "w-24",
      render: (c) => <span className="font-mono font-bold">{casoId(c.id)}</span>,
    },
    {
      key: "ciudadano_nombre", label: "Paciente", orden: "ciudadano__apellido", className: "min-w-36",
      render: (c) => (
        <span><strong className="block font-semibold">{c.ciudadano_nombre || "Sin paciente"}</strong>
          {c.documento_resumen && <span className="block text-sm text-texto-debil">DNI {c.documento_resumen}</span>}</span>
      ),
    },
    {
      key: "paso_actual", label: "Flujo y etapa", orden: "nodo_actual__titulo", className: "min-w-40",
      render: (c) => <span><strong className="block font-semibold">{c.flujo_titulo || "—"}</strong><span className="block text-sm text-texto-debil">{c.paso_actual || "Sin paso actual"}</span></span>,
    },
    { key: "prioridad", label: "Prioridad", orden: "prioridad_rank", render: (c) => <Badge tone={c.prioridad === "urgente" ? "error" : c.prioridad === "alta" ? "amber" : "neutral"}>{c.prioridad_display || c.prioridad}</Badge> },
    {
      key: "paso_desde", label: "Espera", orden: "paso_desde", className: "w-24 tabular-nums",
      render: (c) => <span className="text-texto-debil">{antiguedad(c.paso_desde || c.creado)}</span>,
    },
    { key: "creado", label: "Ingreso", orden: "creado", className: "min-w-28", render: (c) => <span className="text-texto-debil">{fechaHora(c.creado)}</span> },
    {
      key: "accion", label: "Acciones", fija: true, className: "w-32 min-w-32 text-right",
      render: (c) => (
        <span onClick={(e) => e.stopPropagation()} onKeyDown={(e) => e.stopPropagation()}>
          {c.asignado_a === user?.id ? (
            <Button size="sm" onClick={() => navigate(`/casos/${c.id}`)}>Continuar</Button>
          ) : !c.asignado_a && c.puede_tomar && !c.en_fila ? (
            <Button
              size="sm"
              variant="secondary"
              disabled={tomar.isPending}
              onClick={() => tomar.mutate(c.id, {
                onSuccess: () => { toast.ok("Caso tomado"); navigate(`/casos/${c.id}`); },
              })}
            >
              {tomar.isPending ? "…" : "Tomar"}
            </Button>
          ) : <Button size="sm" variant="secondary" onClick={() => navigate(`/casos/${c.id}`)}>Ver</Button>}
        </span>
      ),
    },
  ];

  return (
    <>
      <div className="px-lg pb-8 pt-[26px] sm:px-[30px] xl:px-10">
        <header className="mb-4 flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-bold">Bandeja</h2>
            <p className="mt-1 text-sm text-texto-debil">Casos en curso. Tomá uno sin asignar o continuá los tuyos.</p>
          </div>
          <Button onClick={() => setNuevo(true)}>Nuevo caso</Button>
        </header>
        <nav aria-label="Bandejas de casos" className="mb-4 flex gap-1 overflow-x-auto border-b border-division">
          {[
            { key: "mios", label: "Mis casos", consulta: nMios },
            { key: "sin", label: "Sin asignar", consulta: nSin },
            { key: "todos", label: "Todos", consulta: nTodos },
          ].map((item) => (
            <button key={item.key} type="button" onClick={() => setTab(item.key)} aria-current={tab === item.key ? "page" : undefined}
              title={item.key === "todos" ? "Todos los casos activos de la institución" : undefined}
              aria-label={item.key === "todos" ? `Todos los casos activos de la institución (${item.consulta.error ? "sin dato" : item.consulta.isLoading ? "cargando" : item.consulta.total})` : undefined}
              className={`whitespace-nowrap border-b-2 px-3 pb-2.5 pt-2 text-sm font-semibold ${tab === item.key ? "border-accent text-accent" : "border-transparent text-texto-debil hover:text-texto-suave"}`}>
              {item.label} ({item.consulta.error ? "—" : item.consulta.isLoading ? "…" : item.consulta.total})
            </button>
          ))}
        </nav>

        {flujos.error && <p role="alert" className="mb-3 text-sm text-badge-error-fg">No se pudieron cargar los flujos del filtro. <button type="button" className="font-semibold underline" onClick={() => flujos.refetch()}>Reintentar</button></p>}
        {flujos.total > flujos.filas.length && <p className="mb-3 text-sm text-badge-amber-fg">El filtro muestra los primeros 200 flujos de la institución.</p>}

        <TablaRecurso
          // La clave incluye la pestaña para que cada bandeja recuerde su propia
          // página y su propio orden.
          clave={`band-${tab}`}
          recurso="casos"
          ordenInicial="-creado"
          params={params}
          columnas={columnas}
          onRowClick={(c) => navigate(`/casos/${c.id}`)}
          barra={<>
            <Buscador valor={texto} onChange={setTexto} placeholder="Paciente, DNI o flujo…" className="w-full sm:w-64" aria-label="Buscar en la bandeja" />
            <FiltroSelect etiqueta="Filtrar por prioridad" valor={prioridad} onChange={setPrioridad} opciones={PRIORIDADES} todos="Todas las prioridades" />
            <FiltroSelect etiqueta="Filtrar por flujo" valor={flujo} onChange={setFlujo}
              opciones={flujos.filas.map((f) => ({ value: String(f.id), label: f.titulo }))} todos="Todos los flujos" />
          </>}
          vacio={
            tab === "mios"
              ? { titulo: "No tenés casos asignados", detalle: "Tomá uno de «Sin asignar» para empezar." }
              : tab === "sin"
                ? { titulo: "No hay casos para tomar", detalle: "Los casos encolados se operan desde Filas de espera." }
                : { titulo: "No hay casos activos", detalle: "Los casos aparecen al iniciarse desde un flujo publicado." }
          }
        />
      </div>

      {nuevo && (
        <NuevoCasoModal
          key={institucion?.id}
          institucionId={institucion?.id}
          permitirCrearPaciente={puedeVer("padron_admision")}
          onClose={() => setNuevo(false)}
          onCreated={(id) => { toast.ok("Caso creado e iniciado"); navigate(`/casos/${id}`); }}
        />
      )}
    </>
  );
}

function NuevoCasoModal({ institucionId, permitirCrearPaciente, onClose, onCreated }) {
  const toast = useToast();
  const [flujoId, setFlujoId] = useState("");
  const [prioridad, setPrioridad] = useState("normal");
  const [paciente, setPaciente] = useState(null);

  const flujosQ = useLista("flujos", { institucion: institucionId, pageSize: 100 });
  // Solo publicados y de alta manual: los «solo por derivación» no se crean acá.
  const flujos = flujosQ.filas
    .map((f) => ({ ...f, pub: (f.versiones || []).find((v) => v.estado === "publicada") }))
    .filter((f) => f.pub && f.origen_inicio !== "derivado");

  const crear = useAccion(async () => {
    const flujo = flujos.find((f) => String(f.id) === String(flujoId));
    const caso = await api.post("/casos/", {
      institucion: flujo.institucion,
      version: flujo.pub.id,
      ciudadano: paciente.id,
      prioridad,
    });
    await api.post(`/casos/${caso.id}/iniciar/`);
    return caso;
  }, { onError: (e) => toast.deError(e, "No se pudo crear el caso.") });

  const puedeCrear = !crear.isPending && flujoId && paciente;

  return (
    <Modal
      title="Nuevo caso"
      onClose={onClose}
      width={520}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancelar</Button>
          <Button disabled={!puedeCrear} onClick={() => crear.mutate(undefined, { onSuccess: (c) => onCreated(c.id) })}>
            {crear.isPending ? "Creando…" : "Crear e iniciar"}
          </Button>
        </>
      }
    >
      {flujosQ.isLoading ? (
        <div className="text-md text-texto-tenue">Cargando flujos…</div>
      ) : flujos.length === 0 ? (
        <div className="text-md text-texto-debil">
          No hay flujos publicados con alta manual. Publicá uno desde Flujos.
        </div>
      ) : (
        <div className="flex flex-col gap-3.5">
          <Field label="Flujo *">
            <Select value={flujoId} onChange={(e) => setFlujoId(e.target.value)}>
              <option value="">Elegí un flujo publicado…</option>
              {flujos.map((f) => <option key={f.id} value={f.id}>{f.titulo} ({f.pub.etiqueta})</option>)}
            </Select>
          </Field>

          {paciente
            ? <PacienteElegido paciente={paciente} onCambiar={() => setPaciente(null)} />
            : <BuscadorPaciente institucionId={institucionId} onElegir={setPaciente} permitirCrear={permitirCrearPaciente} />}

          <Field label="Prioridad">
            <Select value={prioridad} onChange={(e) => setPrioridad(e.target.value)}>
              <option value="normal">Normal</option>
              <option value="alta">Alta</option>
              <option value="urgente">Urgente</option>
            </Select>
          </Field>
        </div>
      )}
    </Modal>
  );
}
