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

/*
 * El badge «Historia clínica / Legajo ciudadano» NO se dibuja más.
 *
 * `Campo.origen` existe en el modelo y en el serializer, pero NINGÚN código lo
 * lee: la precarga que el badge prometía no está implementada en ninguna parte,
 * y el alta de campo tampoco permitía elegir el origen, así que el badge no
 * podía aparecer nunca. Una etiqueta que anuncia una función inexistente hace
 * que el configurador la busque hasta convencerse de que la pantalla está rota.
 * Vuelve el día que la precarga exista (hay que implementarla en el motor, al
 * abrir el nodo Formulario, con la misma regla que ya usa el padrón FHIR: nunca
 * pisar un dato ya cargado).
 */

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
  const [aEditar, setAEditar] = useState(null);
  const [aBorrar, setABorrar] = useState(null);

  const q = useDetalle("formularios", id);
  const form = q.data;
  const campos = form?.campos || [];

  const borrar = useAccion((campo) => api.del(`/campos/${campo.id}/`), {
    invalida: ["lista", "detalle"],
    onSuccess: () => { toast.ok("Campo eliminado."); setABorrar(null); },
    onError: (e) => toast.deError(e, "No se pudo eliminar el campo."),
  });

  /*
   * Mover un campo de lugar.
   *
   * Se reescriben TODOS los `orden` a su índice en vez de intercambiar dos
   * números: el alta usaba `campos.length`, así que los formularios viejos
   * tienen órdenes repetidos y con huecos, y ahí un intercambio no cambia nada
   * en la pantalla. El orden es el de la pantalla que completa el administrativo.
   */
  const mover = useAccion(async ({ desde, hacia }) => {
    const lista = [...campos];
    const [movido] = lista.splice(desde, 1);
    lista.splice(hacia, 0, movido);
    for (const [i, c] of lista.entries()) {
      if (c.orden !== i) await api.patch(`/campos/${c.id}/`, { orden: i });
    }
  }, {
    invalida: ["lista", "detalle"],
    onError: (e) => toast.deError(e, "No se pudo cambiar el orden de los campos."),
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
              {campos.map((c, i) => (
                <li key={c.id} className="flex items-center gap-2.5 rounded-lg border border-borde px-3 py-2.5">
                  <span className={`size-2.5 flex-none rounded-sm ${TIPO_PUNTO[c.tipo] || "bg-texto-tenue"}`} aria-hidden="true" />
                  <div className="min-w-0 flex-1">
                    <div className="text-md font-semibold">
                      {c.label} {c.requerido && <span className="text-danger" title="Requerido">*</span>}
                    </div>
                    <div className="mt-0.5 flex items-center gap-1.5 text-xs text-texto-debil">
                      {c.tipo_display}
                      {/* Que el campo tenga datos cargados cambia lo que se
                          puede hacer con él, así que se dice acá y no recién
                          cuando el servidor rechaza el borrado. */}
                      {c.valores_cargados > 0 && (
                        <Badge tone="info">{plural(c.valores_cargados, "dato", "datos")}</Badge>
                      )}
                    </div>
                  </div>
                  <div className="flex flex-none items-center gap-0.5">
                    <BotonFila
                      title="Subir"
                      icono="arrowUp"
                      disabled={i === 0 || mover.isPending}
                      onClick={() => mover.mutate({ desde: i, hacia: i - 1 })}
                    />
                    <BotonFila
                      title="Bajar"
                      icono="arrowDown"
                      disabled={i === campos.length - 1 || mover.isPending}
                      onClick={() => mover.mutate({ desde: i, hacia: i + 1 })}
                    />
                    <button
                      onClick={() => setAEditar(c)}
                      className="rounded-md px-2 py-1 text-xs font-semibold text-accent hover:bg-accent-50"
                    >
                      editar
                    </button>
                    <button
                      onClick={() => setABorrar(c)}
                      className="rounded-md px-2 py-1 text-xs font-semibold text-danger hover:bg-badge-error-bg"
                    >
                      quitar
                    </button>
                  </div>
                </li>
              ))}
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
                    {/* La ayuda se muestra igual que en la pantalla real
                        (CasoDetalle la pinta como hint del campo). */}
                    {c.ayuda && <div className="mt-1 text-sm text-texto-tenue">{c.ayuda}</div>}
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

      {aEditar && (
        <CampoModal
          formularioId={form.id}
          campo={aEditar}
          onClose={() => setAEditar(null)}
        />
      )}

      {/* Quitar un campo es irreversible y se perdía sin preguntar nada. */}
      {aBorrar && (
        <ConfirmDialog
          title={aBorrar.valores_cargados > 0
            ? `«${aBorrar.label}» no se puede quitar`
            : `¿Quitar «${aBorrar.label}»?`}
          // Con datos cargados el servidor lo rechaza, así que el botón lleva a
          // lo que sí resuelve el problema: es lo mismo que dice su mensaje
          // («editá la etiqueta o las opciones en vez de rehacer el campo»).
          confirmar={aBorrar.valores_cargados > 0 ? "Editar el campo" : "Quitar campo"}
          peligroso={!aBorrar.valores_cargados}
          cargando={borrar.isPending}
          onConfirmar={() => {
            if (aBorrar.valores_cargados > 0) { setAEditar(aBorrar); setABorrar(null); }
            else borrar.mutate(aBorrar);
          }}
          onClose={() => setABorrar(null)}
        >
          {aBorrar.valores_cargados > 0 ? (
            /*
             * El diálogo prometía «los datos ya cargados no se borran» y el
             * servidor responde 409 diciendo lo contrario: `ValorCampo.campo` es
             * CASCADE, así que el borrado se llevaría el motivo de consulta, el
             * nivel de triage o la tensión arterial de cada caso que pasó por
             * acá, y el evento del historial sólo guarda «5 campos cargados».
             */
            <>
              Este campo <strong>no se puede quitar</strong>: tiene{" "}
              {plural(aBorrar.valores_cargados, "dato cargado", "datos cargados")} en casos
              reales y borrarlo se los llevaría a todos, sin forma de recuperarlos. Si lo
              que querés es corregirlo, usá «editar»: la etiqueta, la ayuda, las opciones y
              el orden se pueden cambiar sin tocar los datos.
            </>
          ) : (
            <>
              El campo deja de pedirse en los flujos que usan este formulario. Todavía no
              tiene ningún dato cargado, así que no se pierde nada de lo ya registrado.
            </>
          )}
        </ConfirmDialog>
      )}
    </div>
  );
}

// Botón chico de la fila de un campo (subir / bajar).
function BotonFila({ title, icono, onClick, disabled }) {
  return (
    <button
      type="button"
      title={title}
      aria-label={title}
      onClick={onClick}
      disabled={disabled}
      className="flex size-7 items-center justify-center rounded-sm text-texto-debil hover:bg-division hover:text-texto-medio disabled:opacity-30"
    >
      <Icon name={icono} size={14} />
    </button>
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

/**
 * Alta y EDICIÓN de un campo, en el mismo modal.
 *
 * Editar no existía: creado el campo, no se podía cambiar la etiqueta, el tipo,
 * las opciones, el «requerido», la ayuda ni el orden. Los formularios de un
 * hospital cambian solos —entra una obra social nueva, el triage suma una
 * categoría, alguien tipeó «Tensión artrial»—, así que las salidas eran crear un
 * campo duplicado («Obra social 2»), con lo cual las Decisiones que apuntan al
 * campo viejo dejan de encontrar el dato y los casos se van por la rama que no
 * era, o entrar por el admin de Django: sacar del sistema al usuario al que el
 * producto le prometió que iba a poder configurar sin programar.
 */
function CampoModal({ formularioId, orden, campo, onClose }) {
  const toast = useToast();
  const editando = !!campo;
  // El tipo es lo único que puede invalidar datos ya cargados: los valores se
  // guardan como texto, y pasar «Nivel de triage» a fecha los deja sin sentido.
  const tipoBloqueado = editando && campo.valores_cargados > 0;
  const [f, setF] = useState(() => ({
    label: campo?.label || "",
    tipo: campo?.tipo || "texto_corto",
    requerido: campo?.requerido || false,
    ayuda: campo?.ayuda || "",
    opciones: (campo?.opciones || []).join(", "),
  }));
  const set = (k, v) => setF((p) => ({ ...p, [k]: v }));

  const guardar = useAccion(
    () => {
      const datos = {
        label: f.label,
        tipo: f.tipo,
        requerido: f.requerido,
        ayuda: f.ayuda,
        opciones:
          f.tipo === "seleccion_unica"
            ? f.opciones.split(",").map((s) => s.trim()).filter(Boolean)
            : [],
      };
      return editando
        ? api.patch(`/campos/${campo.id}/`, datos)
        : api.post("/campos/", { ...datos, formulario: formularioId, orden });
    },
    {
      invalida: ["lista", "detalle"],
      onSuccess: () => { toast.ok(editando ? "Campo actualizado." : "Campo agregado."); onClose(); },
      onError: (e) => toast.deError(e, editando ? "No se pudo guardar el campo." : "No se pudo agregar el campo."),
    },
  );

  // Una selección única sin opciones es un desplegable vacío.
  const faltanOpciones = f.tipo === "seleccion_unica" && !f.opciones.trim();

  return (
    <Modal
      title={editando ? `Editar «${campo.label}»` : "Nuevo campo"}
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancelar</Button>
          <Button disabled={guardar.isPending || !f.label || faltanOpciones} onClick={() => guardar.mutate()}>
            {guardar.isPending ? "…" : editando ? "Guardar" : "Agregar"}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3.5">
        <Field label="Etiqueta *">
          <Input value={f.label} onChange={(e) => set("label", e.target.value)} autoFocus placeholder="Nombre, Obra social…" />
        </Field>
        <Field
          label="Tipo"
          hint={tipoBloqueado
            ? `Ya tiene ${plural(campo.valores_cargados, "dato cargado", "datos cargados")}: cambiar el tipo los dejaría sin sentido.`
            : undefined}
        >
          <Select value={f.tipo} disabled={tipoBloqueado} onChange={(e) => set("tipo", e.target.value)}>
            {TIPOS.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
          </Select>
        </Field>
        {f.tipo === "seleccion_unica" && (
          <Field
            label="Opciones (separadas por coma) *"
            hint="Agregar o corregir una opción no toca los datos ya cargados."
          >
            <Input value={f.opciones} onChange={(e) => set("opciones", e.target.value)} placeholder="OSDE, PAMI, Particular" />
          </Field>
        )}
        <Field label="Texto de ayuda" hint="Se muestra debajo del campo cuando alguien lo completa.">
          <Input value={f.ayuda} onChange={(e) => set("ayuda", e.target.value)} placeholder="Como figura en el carnet" />
        </Field>
        <label className="flex items-center gap-2.5 text-md">
          <input type="checkbox" checked={f.requerido} onChange={(e) => set("requerido", e.target.checked)} /> Requerido
        </label>
      </div>
    </Modal>
  );
}
