import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { api } from "@/api/client";
import { useAccion, useLista } from "@/api/queries";
import { useInstitucion } from "@/auth/InstitutionContext";
import { PageHeader } from "@/components/Shell";
import { Badge, Button, ConfirmDialog, Field, Modal, Select, Textarea } from "@/components/ui";
import { TablaRecurso } from "@/components/ui/tabla";
import { useToast } from "@/components/ui/toast";
import { antiguedad } from "@/lib/format";
import { estadoCaso } from "@/lib/dominio";

const PRIORIDADES = [
  { value: "normal", label: "Normal" },
  { value: "alta", label: "Alta" },
  { value: "urgente", label: "Urgente" },
];

/**
 * Vista del jefe/supervisor de área: los casos activos de su área, con las
 * acciones de supervisión. Gateada por la capacidad «supervision».
 *
 * El filtrado lo hace el servidor (`?supervisables=true`). Antes esta pantalla
 * pedía TODOS los casos de la institución y descartaba en el cliente los que no
 * podía supervisar: con 531 casos eso significaba filtrar sobre los primeros 25
 * que devolvía la API y mostrar un puñado arbitrario.
 */
export default function Supervision() {
  const { institucion } = useInstitucion();
  const navigate = useNavigate();
  const toast = useToast();
  const [reasignar, setReasignar] = useState(null);
  const [cancelar, setCancelar] = useState(null);

  const priorizar = useAccion(
    ({ caso, prioridad }) => api.post(`/casos/${caso.id}/priorizar/`, { prioridad }),
    { onError: (e) => toast.deError(e, "No se pudo cambiar la prioridad.") },
  );

  const columnas = [
    {
      key: "ciudadano_nombre", label: "Paciente", orden: "ciudadano__apellido", truncar: true,
      className: "max-w-48",
      render: (c) => (
        <span>
          <span className="block font-semibold">{c.ciudadano_nombre || "Sin paciente"}</span>
          <span className="block text-xs text-texto-tenue">{c.area_nombre || "—"}</span>
        </span>
      ),
    },
    {
      key: "paso_actual", label: "Paso / flujo", orden: "nodo_actual__titulo", truncar: true,
      className: "max-w-52",
      render: (c) => (
        <span>
          <span className="block text-texto-suave">{c.paso_actual || "—"}</span>
          <span className="block text-xs text-texto-tenue">{c.flujo_titulo}</span>
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
    {
      key: "prioridad", label: "Prioridad", orden: "prioridad", className: "w-32",
      render: (c) => (
        <Select
          size="sm"
          aria-label={`Prioridad de ${c.ciudadano_nombre || "el caso"}`}
          value={c.prioridad}
          disabled={priorizar.isPending}
          // La fila abre el caso al hacer clic: sin esto, tocar el selector
          // navegaría en vez de desplegarlo.
          onClick={(e) => e.stopPropagation()}
          onChange={(e) => {
            e.stopPropagation();
            priorizar.mutate({ caso: c, prioridad: e.target.value });
          }}
        >
          {PRIORIDADES.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
        </Select>
      ),
    },
    {
      key: "asignado_nombre", label: "Asignado", orden: "asignado_a__apellido",
      render: (c) => c.asignado_nombre
        ? <span className="text-texto-suave">{c.asignado_nombre}</span>
        : <span className="text-texto-tenue">—</span>,
    },
    {
      key: "creado", label: "Espera", orden: "creado", className: "w-24 tabular-nums",
      render: (c) => <span className="text-texto-debil">{antiguedad(c.creado)}</span>,
    },
    {
      key: "acciones", label: "", className: "w-52 text-right",
      render: (c) => (
        <span className="flex justify-end gap-2" onClick={(e) => e.stopPropagation()}>
          <Button size="sm" variant="secondary" onClick={() => setReasignar(c)}>Reasignar</Button>
          <Button size="sm" variant="danger" onClick={() => setCancelar(c)}>Cancelar</Button>
        </span>
      ),
    },
  ];

  return (
    <>
      <PageHeader subtitle="Todos los casos activos de tu área. Reasigná, cambiá la prioridad o cancelá." />
      <div className="px-8 pb-8 pt-[22px]">
        <TablaRecurso
          clave="sup"
          recurso="casos"
          ordenInicial="-creado"
          params={{ institucion: institucion?.id, supervisables: true }}
          columnas={columnas}
          onRowClick={(c) => navigate(`/casos/${c.id}`)}
          vacio={{
            titulo: "No hay casos activos en tu área",
            detalle: "Cuando ingresen casos, vas a poder supervisarlos desde acá.",
          }}
        />
      </div>

      {reasignar && (
        <ReasignarModal
          caso={reasignar}
          onClose={() => setReasignar(null)}
          onDone={(nombre) => { setReasignar(null); toast.ok(`Caso reasignado a ${nombre}`); }}
        />
      )}
      {cancelar && (
        <CancelarModal
          caso={cancelar}
          onClose={() => setCancelar(null)}
          onDone={() => { setCancelar(null); toast.ok("Caso cancelado"); }}
        />
      )}
    </>
  );
}

export function ReasignarModal({ caso, onClose, onDone }) {
  const toast = useToast();
  const [usuarioId, setUsuarioId] = useState("");

  // Candidatos: staff con membresía en el área del caso. Lo resuelve la API con
  // el filtro por área en vez de traer todas las membresías y cruzarlas acá.
  const membresias = useLista("membresias", { institucion: caso.institucion, areas: caso.area_actual, pageSize: 200 });
  const candidatos = [];
  const vistos = new Set();
  for (const m of membresias.filas) {
    if (m.usuario && !vistos.has(m.usuario)) {
      vistos.add(m.usuario);
      candidatos.push({ id: m.usuario, nombre: m.usuario_nombre || m.usuario_email || `Usuario ${m.usuario}` });
    }
  }

  const asignar = useAccion(
    (id) => api.post(`/casos/${caso.id}/asignar/`, { usuario_id: Number(id) }),
    { onError: (e) => toast.deError(e, "No se pudo reasignar el caso.") },
  );

  const elegido = usuarioId || (candidatos[0] ? String(candidatos[0].id) : "");

  return (
    <Modal
      title={`Reasignar caso de ${caso.ciudadano_nombre || "—"}`}
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Volver</Button>
          <Button
            disabled={!elegido || asignar.isPending}
            onClick={() => asignar.mutate(elegido, {
              onSuccess: () => onDone(candidatos.find((c) => String(c.id) === elegido)?.nombre || "—"),
            })}
          >
            {asignar.isPending ? "Reasignando…" : "Reasignar"}
          </Button>
        </>
      }
    >
      {membresias.isLoading ? (
        <div className="text-md text-texto-tenue">Cargando staff…</div>
      ) : candidatos.length === 0 ? (
        <div className="text-md text-texto-tenue">No hay staff asignado a esta área.</div>
      ) : (
        <Field label="Asignar a">
          <Select value={elegido} onChange={(e) => setUsuarioId(e.target.value)}>
            {candidatos.map((u) => <option key={u.id} value={u.id}>{u.nombre}</option>)}
          </Select>
        </Field>
      )}
    </Modal>
  );
}

export function CancelarModal({ caso, onClose, onDone }) {
  const toast = useToast();
  const [motivo, setMotivo] = useState("");
  const cancelar = useAccion(
    () => api.post(`/casos/${caso.id}/cancelar/`, { motivo: motivo.trim() }),
    { onError: (e) => toast.deError(e, "No se pudo cancelar el caso.") },
  );

  return (
    <ConfirmDialog
      title={`Cancelar caso de ${caso.ciudadano_nombre || "—"}`}
      peligroso
      // Dice qué hace, no «Aceptar»: en un diálogo de cancelación un botón que
      // diga «Cancelar» es ambiguo hasta el absurdo.
      confirmar="Cancelar el caso"
      volver="No, volver"
      cargando={cancelar.isPending}
      onConfirmar={() => cancelar.mutate(undefined, { onSuccess: onDone })}
      onClose={onClose}
    >
      <p className="mb-md">
        El caso saldrá de las colas y quedará cerrado como <strong>cancelado</strong>.
        Esta acción no se revierte.
      </p>
      <Field label="Motivo (opcional)">
        <Textarea
          value={motivo}
          onChange={(e) => setMotivo(e.target.value)}
          placeholder="Ej.: duplicado, paciente se retiró…"
        />
      </Field>
    </ConfirmDialog>
  );
}
