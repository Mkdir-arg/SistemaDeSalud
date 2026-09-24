import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { api } from "@/api/client";
import { useAccion, useLista } from "@/api/queries";
import { useAuth } from "@/auth/AuthContext";
import { useInstitucion } from "@/auth/InstitutionContext";
import { PageHeader } from "@/components/Shell";
import { Badge, Button, Field, Modal, Select, Tabs } from "@/components/ui";
import { useFiltroUrl } from "@/components/ui/filtros";
import { BuscadorPaciente, PacienteElegido } from "@/components/ui/paciente";
import { TablaRecurso } from "@/components/ui/tabla";
import { useToast } from "@/components/ui/toast";
import { antiguedad, casoId } from "@/lib/format";
import { estadoCaso } from "@/lib/dominio";

export default function Bandejas() {
  const { user } = useAuth();
  const { institucion, puedeVer } = useInstitucion();
  const navigate = useNavigate();
  const toast = useToast();
  const [tab, setTab] = useFiltroUrl("bandeja", "mios");
  const [nuevo, setNuevo] = useState(false);

  // Cada pestaña es un filtro DEL SERVIDOR. Antes la pantalla traía todos los
  // casos de la institución y separaba las bandejas en el navegador, así que con
  // volumen real repartía los primeros 25 que devolvía la API.
  const params = tab === "mios"
    ? { institucion: institucion?.id, asignado_a: user?.id }
    : { institucion: institucion?.id, tomables: true };

  // Las cuentas de las pestañas piden una sola fila: lo único que interesa es el
  // `count` que devuelve la API igual.
  const nMios = useLista("casos", { institucion: institucion?.id, asignado_a: user?.id, pageSize: 1 });
  const nSin = useLista("casos", { institucion: institucion?.id, tomables: true, pageSize: 1 });

  const tomar = useAccion((caso) => api.post(`/casos/${caso}/tomar/`), {
    onError: (e) => toast.deError(e, "No se pudo tomar el caso."),
  });

  const columnas = [
    {
      key: "id", label: "Caso", orden: "id", className: "w-36",
      render: (c) => (
        <span>
          <span className="block font-mono font-bold">{casoId(c.id)}</span>
          <span className="block text-sm text-texto-debil">{c.flujo_titulo}</span>
        </span>
      ),
    },
    {
      key: "paso_actual", label: "Paso actual", orden: "nodo_actual__titulo", truncar: true,
      className: "max-w-56",
      render: (c) => (
        <span>
          <span className="block text-texto-suave">{c.paso_actual || "—"}</span>
          {c.responsables?.length > 0 && (
            <span className="block text-xs text-texto-tenue">
              {c.responsables.map((g) => g.nombre).join(", ")}
            </span>
          )}
        </span>
      ),
    },
    {
      key: "estado", label: "Estado", orden: "estado",
      render: (c) => {
        const e = estadoCaso[c.estado] || { label: c.estado_display, tone: "neutral" };
        return <Badge tone={e.tone}>{e.label}</Badge>;
      },
    },
    { key: "area_nombre", label: "Área", orden: "area_actual__nombre", render: (c) => c.area_nombre || "—" },
    {
      key: "creado", label: "Antigüedad", orden: "creado", className: "w-28 tabular-nums",
      render: (c) => <span className="text-texto-debil">{antiguedad(c.creado)}</span>,
    },
    {
      key: "accion", label: "Acciones", fija: true, className: "w-32 min-w-32 text-right",
      render: (c) => (
        <span onClick={(e) => e.stopPropagation()} onKeyDown={(e) => e.stopPropagation()}>
          {c.asignado_a === user?.id ? (
            <Button size="sm" onClick={() => navigate(`/casos/${c.id}`)}>Continuar</Button>
          ) : !c.asignado_a ? (
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
          ) : null}
        </span>
      ),
    },
  ];

  return (
    <>
      <PageHeader
        subtitle="Casos en curso. Tomá uno sin asignar o continuá los tuyos."
        right={<Button onClick={() => setNuevo(true)}>+ Nuevo caso</Button>}
      />

      <div className="px-lg pb-8 pt-lg sm:px-8">
        <Tabs
          className="mb-lg"
          valor={tab}
          onChange={setTab}
          tabs={[
            { key: "mios", label: "Mis casos", cuenta: nMios.total },
            { key: "sin", label: "Sin asignar", cuenta: nSin.total },
          ]}
        />

        <TablaRecurso
          // La clave incluye la pestaña para que cada bandeja recuerde su propia
          // página y su propio orden.
          clave={`band-${tab}`}
          recurso="casos"
          ordenInicial="-creado"
          params={params}
          columnas={columnas}
          onRowClick={(c) => navigate(`/casos/${c.id}`)}
          vacio={
            tab === "mios"
              ? { titulo: "No tenés casos asignados", detalle: "Tomá uno de «Sin asignar» para empezar." }
              : { titulo: "No hay casos para tomar", detalle: "Los casos encolados se operan desde Filas de espera." }
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
