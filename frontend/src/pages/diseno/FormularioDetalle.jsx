import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { api } from "@/api/client";
import { useAccion, useDetalle } from "@/api/queries";
import { Icon } from "@/components/icons";
import { Badge, Button, Card, ConfirmDialog, Field, Input, Modal, Select, Textarea } from "@/components/ui";
import { EstadoError, EstadoVacio, Skeleton } from "@/components/ui/estados";
import { useToast } from "@/components/ui/toast";
import { plural } from "@/lib/format";

// Color del punto por tipo de campo. Sale de la paleta de nodos porque ya está en
// tokens y tiene variante oscura; acá es sólo un punto de 9px, nunca texto.
const TIPO_PUNTO = {
  texto_corto: "bg-nodo-form-sol",
  texto_largo: "bg-nodo-inicio-sol",
  fecha: "bg-nodo-derivar-sol",
  seleccion_unica: "bg-nodo-decision-sol",
  archivo: "bg-nodo-atencion-sol",
};

const ORIGEN = {
  historia_clinica: { label: "Historia clínica", tone: "info" },
  legajo_ciudadano: { label: "Legajo ciudadano", tone: "green" },
};

const TIPOS = [
  { value: "texto_corto", label: "Texto corto" },
  { value: "texto_largo", label: "Texto largo" },
  { value: "fecha", label: "Fecha" },
  { value: "seleccion_unica", label: "Selección única" },
  { value: "archivo", label: "Archivo adjunto" },
];

export default function FormularioDetalle() {
  const { id } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const [agregar, setAgregar] = useState(false);
  const [aBorrar, setABorrar] = useState(null);

  const q = useDetalle("formularios", id);
  const form = q.data;
  const campos = form?.campos || [];

  const borrar = useAccion((campo) => api.del(`/campos/${campo.id}/`), {
    invalida: ["lista", "detalle"],
    onSuccess: () => { toast.ok("Campo eliminado."); setABorrar(null); },
    onError: (e) => toast.deError(e, "No se pudo eliminar el campo."),
  });

  if (q.error) return <EstadoError error={q.error} onReintentar={q.refetch} />;

  return (
    <div className="px-lg py-[22px] sm:px-[30px]">
      <div className="mb-lg flex items-center gap-2.5">
        <button
          onClick={() => navigate("/formularios")}
          aria-label="Volver a formularios"
          className="flex size-8 items-center justify-center rounded-md border border-borde bg-superficie text-texto-debil hover:bg-superficie-2"
        >
          <Icon name="back" size={15} />
        </button>
        <div className="text-md text-texto-debil">
          Formularios · <strong className="text-texto-suave">{form?.titulo || "…"}</strong>
        </div>
      </div>

      <div className="mb-5 flex items-center gap-3">
        <div className="flex size-11 flex-none items-center justify-center rounded-lg bg-accent-50 text-accent">
          <Icon name="form" size={22} />
        </div>
        <div>
          <h1 className="text-xxl font-extrabold tracking-tight">
            {form ? form.titulo : <Skeleton className="h-6 w-56" />}
          </h1>
          <div className="text-sm text-texto-debil">
            Formulario de la institución · {plural(campos.length, "campo", "campos")}
          </div>
        </div>
      </div>

      {/* Una columna hasta `lg`: a 1024px dos columnas dejan la vista previa
          demasiado angosta para parecerse a lo que verá el administrativo. */}
      <div className="grid items-start gap-5 lg:grid-cols-2">
        <Card className="p-lg">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-md font-bold">
              Campos <span className="font-medium text-texto-tenue">· {campos.length}</span>
            </h2>
            <Button variant="secondary" onClick={() => setAgregar(true)} className="h-8 px-3">
              + Agregar
            </Button>
          </div>

          {q.isLoading ? (
            <div className="flex flex-col gap-2">
              {[0, 1, 2].map((i) => <Skeleton key={i} className="h-14" />)}
            </div>
          ) : campos.length === 0 ? (
            <EstadoVacio titulo="Sin campos" detalle="Agregá el primero para que el formulario pida algo." />
          ) : (
            <ul className="flex flex-col gap-2">
              {campos.map((c) => {
                const o = ORIGEN[c.origen];
                return (
                  <li key={c.id} className="flex items-center gap-2.5 rounded-lg border border-borde px-3 py-2.5">
                    <span className={`size-2.5 flex-none rounded-sm ${TIPO_PUNTO[c.tipo] || "bg-texto-tenue"}`} aria-hidden="true" />
                    <div className="min-w-0 flex-1">
                      <div className="text-md font-semibold">
                        {c.label} {c.requerido && <span className="text-danger" title="Requerido">*</span>}
                      </div>
                      <div className="mt-0.5 flex items-center gap-1.5 text-xs text-texto-debil">
                        {c.tipo_display}
                        {o && <Badge tone={o.tone}>{o.label}</Badge>}
                      </div>
                    </div>
                    <button
                      onClick={() => setABorrar(c)}
                      className="rounded-md px-2 py-1 text-xs font-semibold text-danger hover:bg-badge-error-bg"
                    >
                      quitar
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </Card>

        {/* Vista previa en vivo */}
        <div>
          <div className="mb-3 flex items-baseline gap-2">
            <span className="size-2 rounded-full bg-nodo-inicio-sol" aria-hidden="true" />
            <h2 className="text-md font-bold">Vista previa en vivo</h2>
            <span className="text-sm text-texto-debil">así lo verá el administrativo</span>
          </div>
          <Card className="p-[22px]">
            <div className="text-lg font-bold">{form?.titulo}</div>
            <div className="mb-lg text-base text-texto-debil">Completá los campos para continuar.</div>
            {campos.length === 0 ? (
              <div className="text-base text-texto-tenue">Sin campos para previsualizar.</div>
            ) : (
              <div className="flex flex-col gap-3.5">
                {campos.map((c) => (
                  <div key={c.id}>
                    <div className="mb-1.5 text-base font-semibold text-texto-medio">
                      {c.label} {c.requerido && <span className="text-danger">*</span>}
                    </div>
                    <PreviewInput campo={c} />
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      </div>

      {agregar && (
        <CampoModal
          formularioId={form.id}
          orden={campos.length}
          onClose={() => setAgregar(false)}
        />
      )}

      {/* Quitar un campo es irreversible y se perdía sin preguntar nada. */}
      {aBorrar && (
        <ConfirmDialog
          title={`¿Quitar «${aBorrar.label}»?`}
          confirmar="Quitar campo"
          peligroso
          cargando={borrar.isPending}
          onConfirmar={() => borrar.mutate(aBorrar)}
          onClose={() => setABorrar(null)}
        >
          El campo deja de pedirse en los flujos que usan este formulario. Los datos
          ya cargados no se borran.
        </ConfirmDialog>
      )}
    </div>
  );
}

function PreviewInput({ campo }) {
  // `inert` en vez de `pointerEvents:none`: la vista previa tampoco tiene que
  // recibir foco con Tab, si no se navega por un formulario que no hace nada.
  const props = { readOnly: true, tabIndex: -1, className: "bg-superficie-2" };
  if (campo.tipo === "texto_largo") return <Textarea placeholder="Escribí aquí…" {...props} />;
  if (campo.tipo === "fecha") return <Input type="date" {...props} />;
  if (campo.tipo === "seleccion_unica")
    return (
      <Select disabled {...props}>
        <option>Seleccionar…</option>
        {(campo.opciones || []).map((o) => <option key={o}>{o}</option>)}
      </Select>
    );
  if (campo.tipo === "archivo") return <Input placeholder="Adjuntar archivo…" {...props} />;
  return <Input placeholder="Ingresá el dato" {...props} />;
}

function CampoModal({ formularioId, orden, onClose }) {
  const toast = useToast();
  const [f, setF] = useState({ label: "", tipo: "texto_corto", requerido: false, opciones: "" });
  const set = (k, v) => setF((p) => ({ ...p, [k]: v }));

  const guardar = useAccion(
    () =>
      api.post("/campos/", {
        formulario: formularioId,
        label: f.label,
        tipo: f.tipo,
        requerido: f.requerido,
        opciones:
          f.tipo === "seleccion_unica"
            ? f.opciones.split(",").map((s) => s.trim()).filter(Boolean)
            : [],
        orden,
      }),
    {
      invalida: ["lista", "detalle"],
      onSuccess: () => { toast.ok("Campo agregado."); onClose(); },
      onError: (e) => toast.deError(e, "No se pudo agregar el campo."),
    },
  );

  // Una selección única sin opciones es un desplegable vacío.
  const faltanOpciones = f.tipo === "seleccion_unica" && !f.opciones.trim();

  return (
    <Modal
      title="Nuevo campo"
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancelar</Button>
          <Button disabled={guardar.isPending || !f.label || faltanOpciones} onClick={() => guardar.mutate()}>
            {guardar.isPending ? "…" : "Agregar"}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3.5">
        <Field label="Etiqueta *">
          <Input value={f.label} onChange={(e) => set("label", e.target.value)} autoFocus placeholder="Nombre, Obra social…" />
        </Field>
        <Field label="Tipo">
          <Select value={f.tipo} onChange={(e) => set("tipo", e.target.value)}>
            {TIPOS.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
          </Select>
        </Field>
        {f.tipo === "seleccion_unica" && (
          <Field label="Opciones (separadas por coma) *">
            <Input value={f.opciones} onChange={(e) => set("opciones", e.target.value)} placeholder="OSDE, PAMI, Particular" />
          </Field>
        )}
        <label className="flex items-center gap-2.5 text-md">
          <input type="checkbox" checked={f.requerido} onChange={(e) => set("requerido", e.target.checked)} /> Requerido
        </label>
      </div>
    </Modal>
  );
}
