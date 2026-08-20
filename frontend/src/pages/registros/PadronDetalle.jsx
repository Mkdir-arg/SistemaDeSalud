import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { api } from "@/api/client";
import { useAccion, useDetalle, useLista } from "@/api/queries";
import { useInstitucion } from "@/auth/InstitutionContext";
import { Icon } from "@/components/icons";
import { Avatar, Badge, Button, Card, Field, Input, Modal, Mono, Select, Spinner, Textarea } from "@/components/ui";
import { EstadoError } from "@/components/ui/estados";
import { useToast } from "@/components/ui/toast";
import { fechaHora } from "@/lib/format";

function fecha(iso) {
  if (!iso) return "-";
  const m = String(iso).match(/^(\d{4})-(\d{2})-(\d{2})/);
  return m ? `${m[3]}/${m[2]}/${m[1]}` : String(iso);
}

function nombreCompleto(c) {
  return `${c?.nombre || ""} ${c?.apellido || ""}`.trim();
}

function Dato({ label, children }) {
  return (
    <div>
      <div className="text-sm font-semibold uppercase tracking-wider text-texto-tenue">{label}</div>
      <div className="mt-1 min-h-6 text-md font-semibold text-texto-suave">{children || "-"}</div>
    </div>
  );
}

export default function PadronDetalle() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { puedeVer } = useInstitucion();
  const paciente = useDetalle("ciudadanos", id);
  const [editando, setEditando] = useState(false);

  if (paciente.isLoading) return <Spinner label="Cargando ficha..." />;
  if (paciente.error) return <EstadoError error={paciente.error} onReintentar={paciente.refetch} />;

  const c = paciente.data;
  const nombre = nombreCompleto(c);

  return (
    <div className="px-lg py-[22px] sm:px-[30px]">
      <div className="mb-lg flex items-center gap-2.5">
        <button
          onClick={() => navigate("/padron")}
          aria-label="Volver al padrón"
          className="flex size-8 items-center justify-center rounded-md border border-borde bg-superficie text-texto-debil hover:bg-superficie-2"
        >
          <Icon name="back" size={15} />
        </button>
        <div className="text-md text-texto-debil">
          Padrón de pacientes · <strong className="text-texto-suave">{nombre || "Paciente"}</strong>
        </div>
      </div>

      <Card className="mb-[18px] flex flex-wrap items-center gap-lg px-6 py-5">
        <Avatar nombre={nombre} i={c.id} size={52} />
        <div className="min-w-0 flex-1">
          <h1 className="text-xxl font-extrabold tracking-tight">{nombre || "Sin nombre"}</h1>
          <div className="flex flex-wrap items-center gap-x-2 text-base text-texto-debil">
            <span>{c.documento ? `DNI ${c.documento}` : c.codigo || "Sin documento"}</span>
            {c.fecha_nacimiento && <span>- {fecha(c.fecha_nacimiento)}</span>}
            {c.obra_social && <span>- {c.obra_social}</span>}
          </div>
        </div>
        <div className="flex w-full flex-wrap gap-2 sm:w-auto">
          <Button variant="secondary" onClick={() => setEditando(true)}>
            <Icon name="edit" size={15} /> Editar datos
          </Button>
          {puedeVer("historia_clinica") && (
            <Button onClick={() => navigate(`/historia/${c.id}`)}>
              <Icon name="clipboard" size={15} /> Abrir historia
            </Button>
          )}
        </div>
      </Card>

      <div className="grid items-start gap-5 lg:grid-cols-[1fr_22rem]">
        <Card className="p-5">
          <h2 className="mb-4 text-xs font-bold uppercase tracking-wider text-texto-debil">
            Datos administrativos
          </h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <Dato label="Documento">{c.documento || "Sin documento"}</Dato>
            <Dato label="Código">{c.codigo ? <Mono>{c.codigo}</Mono> : "-"}</Dato>
            <Dato label="Fecha de nacimiento">{fecha(c.fecha_nacimiento)}</Dato>
            <Dato label="Cobertura">{c.obra_social || "-"}</Dato>
            <Dato label="Domicilio">{c.domicilio || "-"}</Dato>
            <Dato label="Alta en padrón">{fechaHora(c.creado)}</Dato>
          </div>
        </Card>

        <div className="flex flex-col gap-3.5">
          <Consentimiento ciudadanoId={id} estado={c.consentimiento} />
          <Card className="p-4 text-sm text-texto-debil">
            Esta ficha no muestra evolución, alergias, estudios ni recetas. Para consultar datos clínicos se requiere permiso de historia clínica.
          </Card>
        </div>
      </div>

      {editando && (
        <EditarPacienteModal
          paciente={c}
          onClose={() => setEditando(false)}
          onListo={() => { setEditando(false); paciente.refetch(); }}
        />
      )}
    </div>
  );
}

function EditarPacienteModal({ paciente, onClose, onListo }) {
  const toast = useToast();
  const [f, setF] = useState({
    nombre: paciente.nombre || "",
    apellido: paciente.apellido || "",
    documento: paciente.documento || "",
    fecha_nacimiento: paciente.fecha_nacimiento || "",
    obra_social: paciente.obra_social || "",
    domicilio: paciente.domicilio || "",
  });
  const set = (k, v) => setF((p) => ({ ...p, [k]: v }));

  const guardar = useAccion(
    () => api.patch(`/ciudadanos/${paciente.id}/`, {
      ...f,
      fecha_nacimiento: f.fecha_nacimiento || null,
    }),
    {
      invalida: ["lista", "detalle"],
      onSuccess: () => { toast.ok("Datos actualizados."); onListo(); },
      onError: (e) => toast.deError(e, "No se pudo actualizar el padrón."),
    },
  );

  return (
    <Modal
      title="Editar datos administrativos"
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancelar</Button>
          <Button disabled={guardar.isPending || !f.nombre.trim()} onClick={() => guardar.mutate()}>
            {guardar.isPending ? "Guardando..." : "Guardar"}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3.5">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Nombre *"><Input value={f.nombre} onChange={(e) => set("nombre", e.target.value)} autoFocus /></Field>
          <Field label="Apellido"><Input value={f.apellido} onChange={(e) => set("apellido", e.target.value)} /></Field>
        </div>
        <Field label="Documento"><Input value={f.documento} onChange={(e) => set("documento", e.target.value)} /></Field>
        <Field label="Fecha de nacimiento"><Input type="date" value={f.fecha_nacimiento || ""} onChange={(e) => set("fecha_nacimiento", e.target.value)} /></Field>
        <Field label="Obra social"><Input value={f.obra_social} onChange={(e) => set("obra_social", e.target.value)} /></Field>
        <Field label="Domicilio"><Input value={f.domicilio} onChange={(e) => set("domicilio", e.target.value)} /></Field>
      </div>
    </Modal>
  );
}

const MODO = { escrito: "Escrito", verbal: "Verbal", digital: "Digital" };

function Consentimiento({ ciudadanoId, estado }) {
  const toast = useToast();
  const [pidiendo, setPidiendo] = useState(null);
  const [historial, setHistorial] = useState(false);
  const sinRegistro = estado == null;

  return (
    <Card className="p-[18px]">
      <h2 className="mb-3 text-xs font-bold uppercase tracking-wider text-texto-debil">
        Consentimiento de datos
      </h2>

      {sinRegistro ? (
        <div className="text-md text-texto-debil">Sin registro de consentimiento.</div>
      ) : (
        <>
          <Badge tone={estado.otorgado ? "green" : "amber"}>
            {estado.otorgado ? "Otorgado" : "Revocado"}
          </Badge>
          <div className="mt-2 text-sm text-texto-debil">
            {fechaHora(estado.momento)}
            {estado.modo ? ` - ${MODO[estado.modo] || estado.modo}` : ""}
          </div>
          {estado.alcance && (
            <div className="mt-1 text-sm text-texto-medio">
              <span className="text-texto-debil">{estado.otorgado ? "Alcance: " : "Motivo: "}</span>
              {estado.alcance}
            </div>
          )}
          <button
            onClick={() => setHistorial((v) => !v)}
            className="mt-2 text-sm font-semibold text-accent hover:underline"
          >
            {historial ? "Ocultar historial" : "Ver historial"}
          </button>
          {historial && <HistorialConsentimientos ciudadanoId={ciudadanoId} />}
        </>
      )}

      <div className="mt-3.5 flex flex-wrap gap-2">
        {(sinRegistro || !estado.otorgado) && (
          <Button className="text-sm" onClick={() => setPidiendo("otorgar")}>Registrar consentimiento</Button>
        )}
        {!sinRegistro && estado.otorgado && (
          <Button variant="secondary" className="text-sm" onClick={() => setPidiendo("revocar")}>
            Registrar revocación
          </Button>
        )}
      </div>

      {pidiendo && (
        <ConsentimientoModal
          ciudadanoId={ciudadanoId}
          otorgar={pidiendo === "otorgar"}
          onClose={() => setPidiendo(null)}
          onListo={() => { toast.ok("Consentimiento registrado."); setPidiendo(null); }}
        />
      )}
    </Card>
  );
}

function HistorialConsentimientos({ ciudadanoId }) {
  const q = useLista("consentimientos", { ciudadano: ciudadanoId, pageSize: 50 });

  if (q.isLoading) return <div className="mt-2 text-sm text-texto-debil">Buscando historial...</div>;
  if (q.error) return <div className="mt-2 text-sm text-danger">No se pudo traer el historial.</div>;
  if (!q.filas.length) return <div className="mt-2 text-sm text-texto-debil">Sin registros.</div>;

  return (
    <ol className="mt-2.5 flex flex-col gap-2.5 border-t border-division pt-2.5">
      {q.filas.map((c) => (
        <li key={c.id} className="text-sm">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={c.otorgado ? "green" : "amber"}>{c.otorgado ? "Otorgado" : "Revocado"}</Badge>
            <span className="text-texto-debil">{fechaHora(c.momento)}</span>
          </div>
          <div className="mt-0.5 text-texto-debil">
            {c.modo_display || MODO[c.modo] || c.modo}
            {c.tomado_por_nombre ? ` - lo tomo ${c.tomado_por_nombre}` : ""}
          </div>
          {c.alcance && <div className="text-texto-medio">{c.otorgado ? "Alcance: " : "Motivo: "}{c.alcance}</div>}
        </li>
      ))}
    </ol>
  );
}

function ConsentimientoModal({ ciudadanoId, otorgar, onClose, onListo }) {
  const toast = useToast();
  const [modo, setModo] = useState("escrito");
  const [alcance, setAlcance] = useState("");

  const guardar = useAccion(
    () => api.post("/consentimientos/", { ciudadano: ciudadanoId, otorgado: otorgar, modo, alcance }),
    {
      invalida: ["lista", "detalle"],
      onSuccess: onListo,
      onError: (e) => toast.deError(e, "No se pudo registrar el consentimiento."),
    },
  );

  return (
    <Modal
      title={otorgar ? "Registrar consentimiento" : "Registrar revocación"}
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancelar</Button>
          <Button disabled={guardar.isPending} onClick={() => guardar.mutate()}>
            {guardar.isPending ? "Registrando..." : "Registrar"}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3.5">
        <Field label="Cómo se tomó">
          <Select value={modo} onChange={(e) => setModo(e.target.value)}>
            {Object.entries(MODO).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </Select>
        </Field>
        <Field label="Alcance / observaciones">
          <Textarea
            value={alcance}
            onChange={(e) => setAlcance(e.target.value)}
            placeholder={otorgar ? "Atención y tratamiento de datos de salud" : "Motivo de la revocación"}
          />
        </Field>
      </div>
    </Modal>
  );
}
