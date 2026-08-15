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
      // `prioridad_rank` y no `prioridad`: el CharField ordena alfabético (alta <
      // normal < urgente), así que el primer clic dejaba los 16 urgentes al final
      // y el segundo mandaba los 26 casos en Alta a la página 17 de 18, detrás de
      // 407 normales. El jefe toca esta columna para hacer triage, ve los
      // urgentes arriba, da la lista por revisada — y los pacientes que alguien
      // decidió que no podían seguir en la cola normal no los mira nadie.
      key: "prioridad", label: "Prioridad", orden: "prioridad_rank", className: "w-32",
      render: (c) => (
        <Select
          size="sm"
          aria-label={`Prioridad de ${c.ciudadano_nombre || "el caso"}`}
          value={c.prioridad}
          disabled={priorizar.isPending}
          // La fila abre el caso al hacer clic: sin esto, tocar el selector
          // navegaría en vez de desplegarlo.
          onClick={(e) => e.stopPropagation()}
          // Y sin esto el Enter del teclado burbujea a la fila, que hace
          // `preventDefault()` y navega: quien opera sin mouse no puede tocar
          // este control y encima termina en otra pantalla.
          onKeyDown={(e) => e.stopPropagation()}
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
      // El reloj del PASO (`paso_desde`), no la edad del caso. `creado` es el
      // ingreso del paciente al hospital: en Internación todas las filas decían
      // «12 d» y la columna dejaba de discriminar, y el ranking contradecía a los
      // avisos de demora, que el motor dispara sobre `paso_desde`. El jefe entra
      // a buscar el caso que le avisaron y lo encuentra en el medio de la lista.
      key: "paso_desde", label: "Espera", orden: "paso_desde", className: "w-24 tabular-nums",
      // El fallback a `creado` es para los casos que todavía no entraron a ningún
      // paso (y para mientras el serializer no exponga el campo).
      render: (c) => <span className="text-texto-debil">{antiguedad(c.paso_desde || c.creado)}</span>,
    },
    {
      key: "acciones", label: "", className: "w-52 text-right",
      render: (c) => (
        // La fila navega al caso con clic y con Enter. Frenar sólo el clic dejaba
        // a quien opera por teclado sin poder reasignar ni cancelar: el keydown
        // burbujeaba, la fila hacía `preventDefault()` —que cancela la activación
        // del botón— y encima lo mandaba al detalle del caso.
        <span
          className="flex justify-end gap-2"
          onClick={(e) => e.stopPropagation()}
          onKeyDown={(e) => e.stopPropagation()}
        >
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

  // Candidatos: los que el backend va a ACEPTAR, no los que comparten área.
  //
  // `asignar` exige membresía ACTIVA en la institución y, si el paso declara
  // grupos responsables, integrar alguno (`motor.usuario_puede_tomar`); si no,
  // devuelve 400. El modal ofrecía todo el staff del área —el administrativo
  // incluido—, con el primero de la lista ya preseleccionado, así que el jefe
  // elegía, le rebotaba, elegía otro y le rebotaba, sin que la pantalla le dijera
  // nunca cuál iba a andar. En un turno de noche eso es tiempo del paciente.
  const responsables = caso.responsables || [];
  const membresias = useLista("membresias", {
    institucion: caso.institucion,
    // Con grupos responsables el área no acota nada: el grupo puede ser de otra
    // área que el caso ya recorrió. Sin grupos, el paso está abierto a cualquiera
    // y «staff del área» es el conjunto que tiene sentido ofrecer.
    ...(responsables.length ? {} : { areas: caso.area_actual }),
    activo: true,
    pageSize: 200,
  });
  const grupos = useLista(
    "grupos",
    { area__institucion: caso.institucion, activo: true, pageSize: 200 },
    { enabled: responsables.length > 0 },
  );

  // Usuario → nombre, sólo los de membresía activa (el residente que terminó la
  // rotación sigue en el grupo y el backend lo rechaza).
  const activos = new Map();
  for (const m of membresias.filas) {
    if (m.usuario && !activos.has(m.usuario)) {
      activos.set(m.usuario, m.usuario_nombre || m.usuario_email || `Usuario ${m.usuario}`);
    }
  }

  const candidatos = [];
  const vistos = new Set();
  if (responsables.length) {
    const responsablesIds = new Set(responsables.map((g) => g.id));
    for (const g of grupos.filas) {
      if (!responsablesIds.has(g.id)) continue;
      for (const u of g.integrantes || []) {
        if (vistos.has(u.id) || !activos.has(u.id)) continue;
        vistos.add(u.id);
        candidatos.push({ id: u.id, nombre: u.nombre || activos.get(u.id) });
      }
    }
  } else {
    for (const [id, nombre] of activos) candidatos.push({ id, nombre });
  }

  const cargando = membresias.isLoading || (responsables.length > 0 && grupos.isLoading);
  const grupoNombres = responsables.map((g) => g.nombre).join(", ");

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
      {cargando ? (
        <div className="text-md text-texto-tenue">Cargando staff…</div>
      ) : candidatos.length === 0 ? (
        // Decirlo ANTES de que el jefe pruebe, y decir por dónde sale: si no, el
        // único camino es tocar «Reasignar» hasta que rebote con todos.
        <div className="text-md text-texto-tenue">
          {responsables.length
            ? <>
                Este paso sólo lo puede tomar quien integre <strong>{grupoNombres}</strong>, y ahí
                no hay nadie con membresía activa. Cambiá el grupo responsable del paso en el
                flujo, o dejá el caso sin asignar para que lo tome quien corresponda.
              </>
            : "No hay staff con membresía activa en esta área."}
        </div>
      ) : (
        <Field
          label="Asignar a"
          // Que se lea de dónde sale la lista: es la diferencia entre «faltan
          // personas» y «el paso sólo lo puede tomar este grupo».
          hint={responsables.length ? `Sólo los que integran el grupo responsable del paso: ${grupoNombres}.` : undefined}
        >
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
