import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";

import { api } from "@/api/client";
import { useAccion, useDetalle, useLista } from "@/api/queries";
import { Icon } from "@/components/icons";
import { Badge, Button, Card, ConfirmDialog, Field, IconButton, Input, Modal, Mono, Select, Textarea } from "@/components/ui";
import { EstadoError, EstadoVacio, Skeleton } from "@/components/ui/estados";
import { useToast } from "@/components/ui/toast";
import { plural } from "@/lib/format";

import { BorrarFormularioDialog } from "./Formularios";

/*
 * Chip de tipo de campo.
 *
 * Antes el tipo era un punto de 9px y, aparte, texto gris de 11px: o sea, el dato
 * que distingue un campo de otro era lo más chico de la fila. Ahora es un chip
 * con la etiqueta legible y el color de su categoría. Los colores salen de la
 * paleta de nodos porque ya están en tokens y tienen variante oscura, y porque
 * son los MISMOS con los que el diseñador de flujos pinta cada tipo de paso.
 */
const TIPO_CHIP = {
  texto_corto: "bg-nodo-form-tint text-nodo-form-sol",
  texto_largo: "bg-nodo-inicio-tint text-nodo-inicio-sol",
  numero: "bg-nodo-cama-tint text-nodo-cama-sol",
  fecha: "bg-nodo-derivar-tint text-nodo-derivar-sol",
  seleccion_unica: "bg-nodo-decision-tint text-nodo-decision-sol",
  archivo: "bg-nodo-atencion-tint text-nodo-atencion-sol",
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
  { value: "numero", label: "Número" },
  { value: "fecha", label: "Fecha" },
  { value: "seleccion_unica", label: "Selección única" },
  { value: "archivo", label: "Archivo adjunto" },
];

const ESTADO_VERSION = {
  publicada: { label: "Publicada", tone: "green" },
  borrador: { label: "Borrador", tone: "amber" },
  reemplazada: { label: "Reemplazada", tone: "gray" },
};

export default function FormularioDetalle() {
  const { id } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const [agregar, setAgregar] = useState(false);
  const [aEditar, setAEditar] = useState(null);
  const [aBorrar, setABorrar] = useState(null);
  const [editarForm, setEditarForm] = useState(false);
  const [borrarForm, setBorrarForm] = useState(false);

  const q = useDetalle("formularios", id);
  const form = q.data;
  const campos = form?.campos || [];

  /*
   * Dónde se usa el formulario: qué pasos de qué flujos lo piden y qué ramas de
   * Decisión leen sus campos.
   *
   * Sin esto el constructor era una pantalla a ciegas sobre datos en producción:
   * marcar un campo como requerido TRABA en el acto los casos parados en ese
   * paso (el motor no los deja avanzar sin cargarlo) y quitar un campo rompe las
   * Decisiones que lo comparan por id, con lo que los casos se van por la rama
   * que no era. La clave arranca con «detalle» a propósito: así la invalidación
   * que ya hacen las mutaciones (`invalida: ["lista", "detalle"]`) la alcanza.
   */
  const usosQ = useQuery({
    queryKey: ["detalle", "formulario-usos", id],
    queryFn: () => api.get(`/formularios/${id}/usos/`),
    enabled: id != null,
  });
  const usos = usosQ.data?.usos || [];
  const condiciones = usosQ.data?.condiciones || [];
  // Casos parados justo en un paso que pide este formulario: son los que un
  // campo requerido nuevo deja sin poder avanzar.
  const casosParados = usos.reduce((n, u) => n + (u.casos_activos || 0), 0);
  const enPublicado = usos.some((u) => u.version_estado === "publicada");
  const condicionesDe = (campoId) => condiciones.filter((c) => c.campo_id === campoId);

  const borrar = useAccion((campo) => api.del(`/campos/${campo.id}/`), {
    invalida: ["lista", "detalle"],
    onSuccess: () => { toast.ok("Campo eliminado."); setABorrar(null); },
    onError: (e) => toast.deError(e, "No se pudo eliminar el campo."),
  });

  const borrarFormulario = useAccion(() => api.del(`/formularios/${id}/`), {
    onSuccess: () => { toast.ok("Formulario eliminado."); navigate("/formularios"); },
    onError: (e) => toast.deError(e, "No se pudo eliminar el formulario."),
  });

  const duplicar = useAccion(() => api.post(`/formularios/${id}/duplicar/`, {}), {
    onSuccess: (nf) => { toast.ok(`Se duplicó como «${nf.titulo}».`); navigate(`/formularios/${nf.id}`); },
    onError: (e) => toast.deError(e, "No se pudo duplicar el formulario."),
  });

  /*
   * Mover un campo de lugar: UN pedido con el orden completo.
   *
   * Antes era un PATCH por campo, en serie: mover el último de doce eran doce
   * pedidos encadenados y, si el quinto fallaba, el formulario quedaba con la
   * mitad del orden nuevo y la mitad del viejo. El endpoint `reordenar/` lo hace
   * en una transacción y reescribe TODOS los `orden` a su índice, que además es
   * lo que arregla a los formularios viejos con órdenes repetidos —ahí un
   * intercambio de dos números no cambiaba nada en pantalla.
   *
   * `ordenLocal` es el orden optimista: la fila se ve en su lugar nuevo desde
   * que se suelta, sin esperar el ida y vuelta.
   */
  const [ordenLocal, setOrdenLocal] = useState(null);
  const mover = useAccion((ids) => api.post(`/formularios/${id}/reordenar/`, { campos: ids }), {
    invalida: ["lista", "detalle"],
    onError: (e) => toast.deError(e, "No se pudo cambiar el orden de los campos."),
    onSettled: () => setOrdenLocal(null),
  });
  const reordenar = (desde, hacia) => {
    if (hacia < 0 || hacia >= campos.length || desde === hacia) return;
    const ids = campos.map((c) => c.id);
    const [movido] = ids.splice(desde, 1);
    ids.splice(hacia, 0, movido);
    setOrdenLocal(ids);
    mover.mutate(ids);
  };

  // Con un reordenamiento en vuelo se muestra el orden pedido, no el que todavía
  // devuelve el servidor.
  const enPantalla = ordenLocal
    ? ordenLocal.map((cid) => campos.find((c) => c.id === cid)).filter(Boolean)
    : campos;

  // Los números de la tira de la cabecera. Todos salen de lo que ya vino.
  const requeridos = campos.filter((c) => c.requerido).length;
  // Cuántas veces se completó el formulario: el MÁXIMO de valores por campo, no
  // la suma. Sumar los siete campos del triage daba 2296, un número que no
  // contesta ninguna pregunta —y que se lee como si hubiera 2296 casos—.
  const vecesCompletado = campos.reduce((n, c) => Math.max(n, c.valores_cargados || 0), 0);
  // El nombre del paso que lo pide, para el marco de la vista previa: es el
  // título que el administrativo va a tener arriba cuando lo complete.
  const pasoQueLoPide = usos[0]?.nodo_titulo;

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

      {/*
        * Cabecera del formulario, con la tira de datos.
        *
        * Antes el título, el ámbito, la cuenta de campos y la descripción se
        * apilaban con el mismo peso al lado de un icono suelto, y el resto de lo
        * que hay que saber del formulario —cuántos campos son obligatorios,
        * cuántos datos cargados hay en juego, en cuántos pasos se pide— estaba
        * repartido por la pantalla o directamente no estaba. Son números que la
        * API ya devuelve: juntos y arriba, contestan de un vistazo «¿qué puedo
        * tocar acá sin romper nada?».
        */}
      <Card className="mb-lg shadow-card">
        <div className="flex flex-wrap items-start gap-3.5 p-lg">
          <div className="flex size-[42px] flex-none items-center justify-center rounded-md border border-accent-100 bg-accent-50 text-accent">
            <Icon name="form" size={21} />
          </div>
          <div className="min-w-0 flex-1">
            <h1 className="mb-1 font-display text-cifra font-bold leading-tight tracking-tight text-texto-fuerte">
              {form ? form.titulo : <Skeleton className="h-6 w-56" />}
            </h1>
            {/* La descripción no se podía cargar ni ver desde ninguna pantalla:
                la columna del listado sólo podía decir «—». Vacía, el hueco
                invita a llenarla en vez de no decir nada. */}
            {form?.descripcion ? (
              <p className="max-w-prose text-md text-texto-suave">{form.descripcion}</p>
            ) : form ? (
              <button
                onClick={() => setEditarForm(true)}
                className="border-b border-dashed border-accent-100 text-md text-accent"
              >
                Agregá una descripción
              </button>
            ) : null}
          </div>
          {form && (
            <div className="flex flex-none items-center gap-1.5">
              <Button variant="secondary" onClick={() => setEditarForm(true)} className="flex h-8 items-center gap-1.5 px-3">
                <Icon name="edit" size={14} /> Editar
              </Button>
              <IconButton icon="copy" label="Duplicar formulario" size="sm" disabled={duplicar.isPending} onClick={() => duplicar.mutate()} />
              <IconButton icon="trash" label="Eliminar formulario" size="sm" onClick={() => setBorrarForm(true)} />
            </div>
          )}
        </div>

        <dl className="grid grid-cols-2 border-t border-division bg-superficie-2 sm:grid-cols-4">
          <TiraDato titulo="Ámbito" texto={form?.area_nombre} />
          <TiraDato
            titulo="Campos"
            cifra={q.isLoading ? null : campos.length}
            texto={q.isLoading ? null : `· ${requeridos} ${requeridos === 1 ? "obligatorio" : "obligatorios"}`}
          />
          <TiraDato
            titulo="Completado"
            cifra={q.isLoading ? null : vecesCompletado}
            // La consecuencia concreta del número de al lado: con datos cargados,
            // el tipo de esos campos ya no se puede cambiar.
            texto={
              q.isLoading ? null
                : vecesCompletado === 0 ? "nunca · los tipos se pueden cambiar"
                  : "veces · los tipos quedan fijos"
            }
            apagada={vecesCompletado === 0}
          />
          <TiraDato
            titulo="Se pide en"
            // Sin usos no va cifra: «0 ningún paso» es peor que decirlo con
            // palabras, y es justamente el caso en el que se puede tocar todo.
            cifra={usosQ.isLoading || usosQ.error || usos.length === 0 ? null : usos.length}
            texto={
              usosQ.isLoading || usosQ.error ? null
                : usos.length === 0 ? "ningún paso todavía"
                  : (usos.length === 1 ? "paso" : "pasos")
                    + (casosParados > 0 ? ` · ${plural(casosParados, "caso parado ahí", "casos parados ahí")}` : "")
            }
            apagada={usos.length === 0}
          />
        </dl>
      </Card>

      {/* Una columna hasta `lg`: a 1024px dos columnas dejan la vista previa
          demasiado angosta para parecerse a lo que verá el administrativo. */}
      <div className="grid items-start gap-lg lg:grid-cols-[minmax(0,1.12fr)_minmax(0,0.88fr)]">
        <div className="flex flex-col gap-lg">
          <Card className="shadow-card">
            <div className="flex items-center gap-2.5 border-b border-division px-lg py-3.5">
              <h2 className="text-md font-bold">Campos</h2>
              {/* La cuenta sólo cuando se sabe: mientras carga, «0» es la
                  respuesta opuesta a la que va a dar un segundo después. */}
              {!q.isLoading && (
                <Mono className="rounded-pill bg-badge-gray-bg px-2 py-0.5 text-xs font-semibold tabular-nums text-badge-gray-fg">
                  {campos.length}
                </Mono>
              )}
              {/* Deshabilitado mientras el formulario no llegó: el modal necesita
                  su id, y abrirlo antes dejaba la pantalla EN BLANCO —el
                  `form.id` de un `form` todavía undefined tira y React desmonta
                  el árbol entero. Con la red del hospital, hacer clic apenas se
                  abre la pantalla es lo normal. */}
              <Button
                variant="secondary"
                disabled={!form}
                onClick={() => setAgregar(true)}
                className="ml-auto h-8 px-3"
              >
                + Agregar campo
              </Button>
            </div>

            {q.isLoading ? (
              <div className="flex flex-col gap-2 p-lg">
                {[0, 1, 2].map((i) => <Skeleton key={i} className="h-12" />)}
              </div>
            ) : campos.length === 0 ? (
              <div className="p-lg">
                <EstadoVacio titulo="Sin campos" detalle="Agregá el primero para que el formulario pida algo." />
              </div>
            ) : (
              <>
                <ListaCampos
                  campos={enPantalla}
                  ocupado={mover.isPending}
                  condicionesDe={condicionesDe}
                  onReordenar={reordenar}
                  onEditar={setAEditar}
                  onQuitar={setABorrar}
                />
                {/* El segundo «Agregar» va al final de la lista: es donde está la
                    mano y la vista cuando se acabó de revisar los campos. */}
                <div className="px-1.5 pb-1.5 pl-[46px]">
                  <button
                    onClick={() => setAgregar(true)}
                    className="w-full rounded-sm border border-dashed border-accent-100 px-3 py-2 text-left text-md font-semibold text-accent hover:bg-accent-50"
                  >
                    + Agregar un campo al final
                  </button>
                </div>
              </>
            )}
          </Card>

          <PanelUsos q={usosQ} usos={usos} onIrAlFlujo={(u) => navigate(`/flujos/${u.flujo_id}`)} />
        </div>

        {/*
          * Vista previa en vivo.
          *
          * Es lo ÚNICO de esta pantalla que no se configura, y se veía igual que
          * las tarjetas que sí: misma caja, mismo borde. Ahora lleva el marco del
          * paso —con el nombre del paso que la pide y un número de caso de
          * ejemplo— y termina con el botón real apagado, que es lo que la vuelve
          * reconocible como «la pantalla del administrativo». Y queda `sticky`:
          * con siete campos, la lista de la izquierda es más larga y la previa se
          * iba de cuadro justo cuando se la estaba comparando.
          */}
        <div className="lg:sticky lg:top-[18px]">
          <div className="mb-2.5 flex items-center gap-2">
            <span className="size-[7px] flex-none rounded-full bg-nodo-inicio-sol" aria-hidden="true" />
            <h2 className="text-sm font-bold uppercase tracking-wide text-texto-tenue">Vista previa en vivo</h2>
            <span className="text-sm normal-case text-texto-debil">así lo verá el administrativo</span>
          </div>
          <Card className="overflow-hidden shadow-card">
            <div className="flex items-center gap-2 border-b border-borde bg-superficie-2 px-3.5 py-2 text-xs text-texto-debil">
              <span className="flex items-center gap-1.5 font-semibold text-texto-suave">
                <span className="size-[7px] rounded-sm bg-nodo-form-sol" aria-hidden="true" />
                {pasoQueLoPide ? `Paso «${pasoQueLoPide}»` : "Paso de formulario"}
              </span>
              <Mono className="ml-auto text-micro">CASO-0000</Mono>
            </div>
            <div className="p-lg">
              <div className="font-display text-lg font-bold">{form?.titulo}</div>
              <div className="mb-lg text-base text-texto-debil">Completá los campos para continuar.</div>
              {/* Mientras carga, esqueletos y no «Sin campos»: es afirmar que el
                  formulario está vacío cuando todavía no llegó. */}
              {q.isLoading ? (
                <div className="flex flex-col gap-3.5">
                  {[0, 1, 2].map((i) => <Skeleton key={i} className="h-14" />)}
                </div>
              ) : campos.length === 0 ? (
                <div className="text-base text-texto-tenue">Sin campos para previsualizar.</div>
              ) : (
                <>
                  <div className="flex flex-col gap-3.5">
                    {enPantalla.map((c) => (
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
                  <div className="mt-lg flex items-center gap-2.5 border-t border-division pt-3.5">
                    {/*
                      * Apagado a propósito: la previa no ejecuta nada. Está porque
                      * sin él la previa no se parece a la pantalla que imita.
                      *
                      * Apagado con la variante suave del acento y NO con `opacity`:
                      * el blanco sobre el acento al 60% daba 2.7:1 de contraste, o
                      * sea texto que hay que adivinar. Así se sigue leyendo como
                      * «el botón, inactivo» y se lee de verdad.
                      */}
                    <span className="rounded-sm border border-accent-100 bg-accent-50 px-3.5 py-2 text-base font-semibold text-accent">
                      Completar y avanzar
                    </span>
                    <span className="text-sm text-texto-tenue">
                      {requeridos === 0
                        ? "Ningún campo es obligatorio."
                        : `${plural(requeridos, "campo obligatorio", "campos obligatorios")} para poder avanzar.`}
                    </span>
                  </div>
                </>
              )}
            </div>
          </Card>
        </div>
      </div>

      {agregar && form && (
        <CampoModal
          formularioId={form.id}
          // Uno más que el último, no `campos.length`: después de quitar un campo
          // del medio la cantidad ya no es la última posición, y el campo nuevo
          // nacía con el `orden` de otro —que es de dónde vienen los órdenes
          // repetidos de los formularios viejos.
          orden={campos.length ? Math.max(...campos.map((c) => c.orden)) + 1 : 0}
          casosParados={casosParados}
          enPublicado={enPublicado}
          onClose={() => setAgregar(false)}
        />
      )}

      {aEditar && form && (
        <CampoModal
          formularioId={form.id}
          campo={aEditar}
          casosParados={casosParados}
          enPublicado={enPublicado}
          onClose={() => setAEditar(null)}
        />
      )}

      {editarForm && (
        <EditarFormularioModal formulario={form} onClose={() => setEditarForm(false)} />
      )}

      {borrarForm && (
        <BorrarFormularioDialog
          formulario={form}
          cargando={borrarFormulario.isPending}
          onConfirmar={() => borrarFormulario.mutate()}
          onClose={() => setBorrarForm(false)}
        />
      )}

      {/* Quitar un campo es irreversible y se perdía sin preguntar nada. */}
      {aBorrar && (
        <QuitarCampoDialog
          campo={aBorrar}
          condiciones={condicionesDe(aBorrar.id)}
          cargando={borrar.isPending}
          onEditar={() => { setAEditar(aBorrar); setABorrar(null); }}
          onConfirmar={() => borrar.mutate(aBorrar)}
          onClose={() => setABorrar(null)}
        />
      )}
    </div>
  );
}

/**
 * Lista de campos reordenable.
 *
 * Se arrastra Y se mueve con los botones: el arrastre es lo natural con doce
 * campos, pero por sí solo no se puede usar con teclado ni con lector de
 * pantalla, así que subir/bajar se quedan (y hacen exactamente lo mismo).
 */
function ListaCampos({ campos, ocupado, condicionesDe, onReordenar, onEditar, onQuitar }) {
  const [arrastrado, setArrastrado] = useState(null);
  const [sobre, setSobre] = useState(null);

  const soltar = (i) => {
    if (arrastrado != null && arrastrado !== i) onReordenar(arrastrado, i);
    setArrastrado(null);
    setSobre(null);
  };

  return (
    // Nombrada: la pantalla tiene otras listas (los pasos que usan el
    // formulario), y sin nombre «la primera fila de la lista» es ambigua tanto
    // para un lector de pantalla como para los tests.
    <ul className="flex flex-col p-1.5" aria-label="Campos del formulario">
      {campos.map((c, i) => {
        const reglas = condicionesDe(c.id);
        const objetivo = sobre === i && arrastrado != null && arrastrado !== i;
        return (
          <li
            key={c.id}
            draggable={!ocupado}
            onDragStart={() => setArrastrado(i)}
            // `preventDefault` es lo que habilita el drop: sin él el navegador
            // rechaza la zona y el arrastre no termina nunca.
            onDragOver={(e) => { e.preventDefault(); setSobre(i); }}
            onDragEnd={() => { setArrastrado(null); setSobre(null); }}
            onDrop={(e) => { e.preventDefault(); soltar(i); }}
            className={[
              // `group` para que el riel y los controles reaccionen al hover de
              // la fila entera, no cada uno al suyo.
              "group grid grid-cols-[26px_minmax(0,1fr)_auto] items-center gap-3 rounded-md py-2.5 pl-1 pr-2.5 transition-colors",
              // Separadores entre filas en vez de un borde por fila: doce cajas
              // con borde propio son doce rectángulos, no una lista.
              i > 0 ? "border-t border-division" : "",
              arrastrado === i ? "opacity-40" : "",
              objetivo ? "border-transparent bg-accent-50 ring-1 ring-accent" : "hover:bg-superficie-2",
            ].join(" ")}
          >
            {/*
              * Riel de orden: el número ES información —es el orden en que el
              * administrativo va a ver los campos— y al pasar el mouse se
              * convierte en el asa de arrastre, que es justo lo que se hace con
              * ese orden. Antes el número no estaba en ninguna parte.
              */}
            <span
              className="flex h-[26px] items-center justify-center rounded-sm font-mono text-xs font-semibold tabular-nums text-texto-tenue group-hover:cursor-grab group-hover:bg-division group-hover:text-texto-suave"
              title="Arrastrar para reordenar"
            >
              <span className="group-hover:hidden">{i + 1}</span>
              <span className="hidden group-hover:block" aria-hidden="true">
                <Icon name="grip" size={13} strokeWidth={2.4} />
              </span>
            </span>

            <div className="min-w-0">
              <div className="truncate text-md font-semibold text-texto-fuerte">
                {c.label} {c.requerido && <span className="text-danger" title="Requerido">*</span>}
              </div>
              <div className="mt-1 flex flex-wrap items-center gap-1.5">
                <span
                  className={`inline-flex items-center gap-1.5 rounded-pill py-0.5 pl-1.5 pr-2 text-xs font-semibold ${
                    TIPO_CHIP[c.tipo] || "bg-badge-gray-bg text-badge-gray-fg"
                  }`}
                >
                  <span className="size-1.5 rounded-[2px] bg-current" aria-hidden="true" />
                  {c.tipo_display}
                </span>
                {c.tipo === "numero" && <RangoCampo campo={c} />}
                {c.tipo === "seleccion_unica" && (c.opciones || []).length > 0 && (
                  // Recortadas con tope de ancho: los niveles de triage son cinco
                  // etiquetas largas («Rojo - Emergencia», «Naranja - Muy
                  // urgente»…) y sin tope empujaban la fila a dos líneas, que es
                  // lo que desalinea el riel de orden de toda la lista. El
                  // detalle completo queda en el title.
                  <span
                    className="max-w-[200px] truncate font-mono text-xs text-texto-debil"
                    title={c.opciones.join(", ")}
                  >
                    {plural(c.opciones.length, "opción", "opciones")} · {c.opciones.join(", ")}
                  </span>
                )}
                {/* Que el campo tenga datos cargados cambia lo que se
                    puede hacer con él, así que se dice acá y no recién
                    cuando el servidor rechaza el borrado. */}
                {c.valores_cargados > 0 && (
                  <span className="rounded-pill bg-badge-gray-bg px-2 py-0.5 text-xs font-semibold text-badge-gray-fg">
                    {plural(c.valores_cargados, "dato", "datos")}
                  </span>
                )}
                {/* Un campo que una Decisión compara no se puede quitar sin
                    romper esa rama: se avisa en la fila, no recién en el
                    diálogo de borrado. */}
                {reglas.length > 0 && (
                  <Badge tone="amber">
                    {reglas.length === 1 ? "1 regla lo compara" : `${reglas.length} reglas lo comparan`}
                  </Badge>
                )}
              </div>
            </div>

            {/*
              * Controles de la fila.
              *
              * Iconos y no los enlaces «editar»/«quitar»: en minúscula y con
              * color competían con la etiqueta del campo, que es lo que hay que
              * leer primero. Atenuados hasta que se pasa por la fila, pero SIEMPRE
              * en el DOM y enfocables —`focus-within` los enciende— para que se
              * puedan usar con teclado.
              */}
            <div className="flex flex-none items-center gap-0.5 opacity-30 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100">
              <BotonFila
                title="Subir"
                icono="arrowUp"
                disabled={i === 0 || ocupado}
                onClick={() => onReordenar(i, i - 1)}
              />
              <BotonFila
                title="Bajar"
                icono="arrowDown"
                disabled={i === campos.length - 1 || ocupado}
                onClick={() => onReordenar(i, i + 1)}
              />
              <BotonFila title="Editar campo" icono="edit" onClick={() => onEditar(c)} />
              <BotonFila title="Quitar campo" icono="trash" peligroso onClick={() => onQuitar(c)} />
            </div>
          </li>
        );
      })}
    </ul>
  );
}

// «36 – 42 °C». El rango es lo que el motor va a exigir al cargar el dato, así
// que verlo en la fila evita definir un límite que después traba una guardia.
function RangoCampo({ campo }) {
  const { minimo, maximo, unidad } = campo;
  if (minimo == null && maximo == null)
    return unidad ? <Mono className="text-xs text-texto-debil">{unidad}</Mono> : null;
  const rango =
    minimo != null && maximo != null ? `${minimo} – ${maximo}`
      : minimo != null ? `desde ${minimo}`
        : `hasta ${maximo}`;
  return <Mono className="text-xs text-texto-debil">{rango}{unidad ? ` ${unidad}` : ""}</Mono>;
}

/**
 * «Dónde se usa»: los pasos de flujos que piden este formulario.
 *
 * Es la información que faltaba para poder tocar el formulario con criterio: si
 * ningún flujo lo pide, cambiarlo no afecta a nadie; si lo pide un flujo
 * publicado con casos parados en ese paso, cada campo requerido que se agregue
 * los deja sin poder avanzar hasta que alguien los complete.
 */
function PanelUsos({ q, usos, onIrAlFlujo }) {
  return (
    <Card className="p-lg">
      <h2 className="mb-3 text-md font-bold">
        Dónde se usa{" "}
        {/* El número sólo cuando se sabe: mientras carga decía «· 0», que es la
            respuesta opuesta a la que va a dar un segundo después. */}
        {!q.isLoading && !q.error && (
          <span className="font-medium text-texto-tenue">· {plural(usos.length, "paso", "pasos")}</span>
        )}
      </h2>

      {q.isLoading ? (
        <div className="flex flex-col gap-2">{[0, 1].map((i) => <Skeleton key={i} className="h-12" />)}</div>
      ) : q.error ? (
        <div className="text-base text-texto-debil">No se pudo averiguar en qué flujos se usa.</div>
      ) : usos.length === 0 ? (
        <p className="text-base text-texto-debil">
          Ningún paso de ningún flujo vigente lo pide todavía. Podés cambiar sus campos con
          libertad: asignalo a un paso «Formulario» desde el diseñador de flujos.
        </p>
      ) : (
        <ul className="flex flex-col gap-2">
          {usos.map((u) => {
            const e = ESTADO_VERSION[u.version_estado] || ESTADO_VERSION.borrador;
            return (
              <li key={`${u.version_id}-${u.nodo_id}`}>
                <button
                  onClick={() => onIrAlFlujo(u)}
                  className="flex w-full items-center gap-2.5 rounded-lg border border-borde px-3 py-2.5 text-left hover:bg-superficie-2"
                >
                  <span className="flex size-8 flex-none items-center justify-center rounded-md bg-accent-50 text-accent">
                    <Icon name="workflow" size={15} />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-md font-semibold">{u.flujo}</span>
                    <span className="mt-0.5 block truncate text-xs text-texto-debil">
                      paso «{u.nodo_titulo}» · v{u.version_numero}
                    </span>
                  </span>
                  <Badge tone={e.tone}>{e.label}</Badge>
                  {u.casos_activos > 0 && (
                    <Badge tone="amber" className="flex-none">
                      {plural(u.casos_activos, "caso ahí", "casos ahí")}
                    </Badge>
                  )}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}

// Aviso de impacto sobre datos en producción. Amber y no rojo: no es un error,
// es una consecuencia que hay que conocer antes de guardar.
function AvisoImpacto({ children }) {
  return (
    <div className="flex gap-2 rounded-md bg-badge-amber-bg px-3 py-2.5 text-base text-badge-amber-fg">
      <Icon name="alert" size={15} className="mt-0.5 flex-none" />
      <div>{children}</div>
    </div>
  );
}

// Botón chico de la fila de un campo (subir / bajar / editar / quitar).
function BotonFila({ title, icono, onClick, disabled, peligroso = false }) {
  return (
    <button
      type="button"
      title={title}
      aria-label={title}
      onClick={onClick}
      disabled={disabled}
      className={[
        "flex size-7 items-center justify-center rounded-sm text-texto-debil disabled:opacity-30",
        peligroso ? "hover:bg-badge-error-bg hover:text-danger" : "hover:bg-division hover:text-texto-medio",
      ].join(" ")}
    >
      <Icon name={icono} size={14} />
    </button>
  );
}

/**
 * Una celda de la tira de datos de la cabecera.
 *
 * La cifra en mono y tabular para que las cuatro se lean como una fila de
 * números y no como cuatro textos; `null` mientras el dato no llegó, que es
 * distinto de cero.
 */
function TiraDato({ titulo, cifra, texto, apagada = false }) {
  return (
    <div className="border-l border-division px-lg py-2.5 first:border-l-0 [&:nth-child(3)]:border-l-0 sm:[&:nth-child(3)]:border-l">
      <dt className="mb-0.5 text-micro font-bold uppercase tracking-wider text-texto-tenue">{titulo}</dt>
      <dd className="flex items-baseline gap-1.5">
        {cifra != null && (
          <Mono className={`text-lg font-semibold tabular-nums ${apagada ? "text-texto-tenue" : "text-texto-fuerte"}`}>
            {cifra}
          </Mono>
        )}
        {texto ? (
          <span className="truncate text-sm text-texto-debil">{texto}</span>
        ) : cifra == null ? (
          <Skeleton className="h-4 w-16" />
        ) : null}
      </dd>
    </div>
  );
}

function PreviewInput({ campo }) {
  // `inert` en vez de `pointerEvents:none`: la vista previa tampoco tiene que
  // recibir foco con Tab, si no se navega por un formulario que no hace nada.
  const props = { readOnly: true, tabIndex: -1, className: "bg-superficie-2" };
  if (campo.tipo === "texto_largo") return <Textarea placeholder="Escribí aquí…" {...props} />;
  if (campo.tipo === "fecha") return <Input type="date" {...props} />;
  if (campo.tipo === "numero") {
    // La unidad se muestra al lado y no dentro del valor: dentro dejaría de ser
    // un número comparable para las Decisiones.
    return (
      <div className="flex items-center gap-2">
        {/* El placeholder NO es el mínimo: puesto ahí se lee como un valor ya
            cargado, y el administrativo pasa de largo creyendo que el dato está. */}
        <Input type="number" placeholder="Ingresá el número" {...props} />
        {campo.unidad && <span className="flex-none text-base text-texto-debil">{campo.unidad}</span>}
      </div>
    );
  }
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
 * Título, descripción y área del formulario.
 *
 * No existía ninguna forma de cambiarlos: el alta pedía sólo el título y después
 * quedaba fijo para siempre. Un «Admision de pacinetes» mal tipeado se ve en cada
 * paso de cada flujo que lo usa y la única salida era el admin de Django —o sea,
 * sacar del sistema al usuario al que el producto le prometió configurar sin
 * programar—. La descripción y el área directamente no se podían cargar, así que
 * la columna «Descripción» del listado sólo podía decir «—» y el filtro por área
 * no podía encontrar nada.
 */
function EditarFormularioModal({ formulario, onClose }) {
  const toast = useToast();
  const [f, setF] = useState(() => ({
    titulo: formulario.titulo || "",
    descripcion: formulario.descripcion || "",
    area: formulario.area || "",
  }));
  const set = (k, v) => setF((p) => ({ ...p, [k]: v }));

  const areas = useLista(
    "areas",
    { institucion: formulario.institucion, pageSize: 100 },
    { enabled: !!formulario.institucion },
  );

  const guardar = useAccion(
    () => api.patch(`/formularios/${formulario.id}/`, {
      titulo: f.titulo,
      descripcion: f.descripcion,
      area: f.area || null,
    }),
    {
      invalida: ["lista", "detalle"],
      onSuccess: () => { toast.ok("Formulario actualizado."); onClose(); },
      onError: (e) => toast.deError(e, "No se pudo guardar el formulario."),
    },
  );

  return (
    <Modal
      title="Editar formulario"
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancelar</Button>
          <Button disabled={guardar.isPending || !f.titulo} onClick={() => guardar.mutate()}>
            {guardar.isPending ? "…" : "Guardar"}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3.5">
        <Field label="Título *" hint="Es el nombre que se ve en cada paso que lo usa.">
          <Input value={f.titulo} onChange={(e) => set("titulo", e.target.value)} autoFocus />
        </Field>
        <Field label="Área" hint="Sin área queda disponible para toda la institución.">
          <Select value={f.area || ""} onChange={(e) => set("area", e.target.value)}>
            <option value="">Toda la institución</option>
            {areas.filas.map((a) => <option key={a.id} value={a.id}>{a.nombre}</option>)}
          </Select>
        </Field>
        <Field label="Descripción" hint="Para qué sirve. Se ve en el listado y al elegirlo en un paso.">
          <Textarea rows={3} value={f.descripcion} onChange={(e) => set("descripcion", e.target.value)} />
        </Field>
      </div>
    </Modal>
  );
}

/**
 * Confirmación de quitar un campo.
 *
 * Dos motivos distintos por los que no conviene (o no se puede): que tenga datos
 * cargados —el servidor lo rechaza con 409, porque `ValorCampo.campo` es CASCADE
 * y se llevaría el registro asistencial— y que alguna Decisión lo compare, que
 * el servidor NO puede rechazar porque no rompe ninguna FK: la condición se
 * queda apuntando a un id que ya no existe, `_valor_de_campo` devuelve None y la
 * rama nunca se cumple. El caso se va por la otra rama sin un solo aviso.
 */
function QuitarCampoDialog({ campo, condiciones, cargando, onEditar, onConfirmar, onClose }) {
  const conDatos = campo.valores_cargados > 0;

  return (
    <ConfirmDialog
      title={conDatos ? `«${campo.label}» no se puede quitar` : `¿Quitar «${campo.label}»?`}
      // Con datos cargados el servidor lo rechaza, así que el botón lleva a
      // lo que sí resuelve el problema: es lo mismo que dice su mensaje
      // («editá la etiqueta o las opciones en vez de rehacer el campo»).
      confirmar={conDatos ? "Editar el campo" : "Quitar campo"}
      peligroso={!conDatos}
      cargando={cargando}
      onConfirmar={conDatos ? onEditar : onConfirmar}
      onClose={onClose}
    >
      <div className="flex flex-col gap-3">
        {conDatos ? (
          <div>
            Este campo <strong>no se puede quitar</strong>: tiene{" "}
            {plural(campo.valores_cargados, "dato cargado", "datos cargados")} en casos
            reales y borrarlo se los llevaría a todos, sin forma de recuperarlos. Si lo
            que querés es corregirlo, usá «editar»: la etiqueta, la ayuda, las opciones y
            el orden se pueden cambiar sin tocar los datos.
          </div>
        ) : (
          <div>
            El campo deja de pedirse en los flujos que usan este formulario. Todavía no
            tiene ningún dato cargado, así que no se pierde nada de lo ya registrado.
          </div>
        )}

        {condiciones.length > 0 && (
          <AvisoImpacto>
            {condiciones.length === 1 ? "Una rama compara este campo" : `${condiciones.length} ramas comparan este campo`}
            {" "}y va a dejar de cumplirse nunca, así que los casos se irán por la otra:
            <ul className="mt-1.5 flex flex-col gap-0.5">
              {condiciones.map((c, i) => (
                <li key={i}>
                  · «{c.etiqueta}» ({c.desde} → {c.hasta}) en <strong>{c.flujo}</strong>
                </li>
              ))}
            </ul>
            <div className="mt-1.5">Corregí esas condiciones en el diseñador antes de quitarlo.</div>
          </AvisoImpacto>
        )}
      </div>
    </ConfirmDialog>
  );
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
function CampoModal({ formularioId, orden, campo, casosParados, enPublicado, onClose }) {
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
    unidad: campo?.unidad || "",
    minimo: campo?.minimo ?? "",
    maximo: campo?.maximo ?? "",
  }));
  const set = (k, v) => setF((p) => ({ ...p, [k]: v }));
  const esNumero = f.tipo === "numero";

  const guardar = useAccion(
    () => {
      const num = (v) => (String(v).trim() === "" ? null : Number(String(v).replace(",", ".")));
      const datos = {
        label: f.label,
        tipo: f.tipo,
        requerido: f.requerido,
        ayuda: f.ayuda,
        opciones:
          f.tipo === "seleccion_unica"
            ? f.opciones.split(",").map((s) => s.trim()).filter(Boolean)
            : [],
        // Unidad y rango sólo viajan en un campo numérico; en cualquier otro el
        // servidor los limpia, y mandarlos con valor sería pedir una validación
        // que después nadie aplica.
        unidad: esNumero ? f.unidad : "",
        minimo: esNumero ? num(f.minimo) : null,
        maximo: esNumero ? num(f.maximo) : null,
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
  const rangoInvertido =
    esNumero && f.minimo !== "" && f.maximo !== "" && Number(f.minimo) > Number(f.maximo);
  // Volver obligatorio un campo es lo único de esta pantalla que puede TRABAR
  // casos que están corriendo ahora mismo: el motor no los deja avanzar hasta
  // que el dato esté cargado, y el que ya está parado en ese paso no lo tiene.
  const vuelveObligatorio = f.requerido && !campo?.requerido;

  return (
    <Modal
      title={editando ? `Editar «${campo.label}»` : "Nuevo campo"}
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancelar</Button>
          <Button
            disabled={guardar.isPending || !f.label || faltanOpciones || rangoInvertido}
            onClick={() => guardar.mutate()}
          >
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

        {/*
         * Unidad y rango del campo numérico.
         *
         * El tipo Número no existía y todo entraba como texto libre: «Temperatura»
         * podía quedar con «treinta y ocho» o con «386» por un punto que no se
         * tipeó, y eso no falla al guardarse —falla después, en la Decisión «> 38»,
         * que sobre texto no comparable da False en silencio y manda al paciente
         * febril por el circuito del paciente sin fiebre. Con el tipo puesto, el
         * motor exige un número y lo guarda normalizado (36,8 → 36.8).
         */}
        {esNumero && (
          <>
            <Field label="Unidad" hint="Se muestra al lado del casillero: °C, kg, mmHg, mg.">
              <Input value={f.unidad} onChange={(e) => set("unidad", e.target.value)} placeholder="°C" />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Mínimo">
                <Input
                  type="number"
                  step="any"
                  value={f.minimo}
                  onChange={(e) => set("minimo", e.target.value)}
                  placeholder="sin mínimo"
                />
              </Field>
              <Field
                label="Máximo"
                hint={rangoInvertido ? "El máximo no puede ser menor que el mínimo." : undefined}
              >
                <Input
                  type="number"
                  step="any"
                  value={f.maximo}
                  onChange={(e) => set("maximo", e.target.value)}
                  placeholder="sin máximo"
                />
              </Field>
            </div>
            <p className="-mt-1 text-sm text-texto-tenue">
              El rango se valida al cargar el dato: un valor fuera de él no se guarda. Dejalo
              vacío si no querés limitarlo.
            </p>
          </>
        )}

        <Field label="Texto de ayuda" hint="Se muestra debajo del campo cuando alguien lo completa.">
          <Input value={f.ayuda} onChange={(e) => set("ayuda", e.target.value)} placeholder="Como figura en el carnet" />
        </Field>
        <label className="flex items-center gap-2.5 text-md">
          <input type="checkbox" checked={f.requerido} onChange={(e) => set("requerido", e.target.checked)} /> Requerido
        </label>

        {vuelveObligatorio && casosParados > 0 && (
          <AvisoImpacto>
            Hay {plural(casosParados, "caso parado", "casos parados")} en un paso que pide este
            formulario. Con el campo obligatorio no van a poder avanzar hasta que alguien lo
            complete: si es un dato que en esos casos no se tomó, va a haber que cargarlo a mano.
          </AvisoImpacto>
        )}
        {vuelveObligatorio && casosParados === 0 && enPublicado && (
          <AvisoImpacto>
            Este formulario se pide en un flujo <strong>publicado</strong>: desde que se guarde,
            ningún caso podrá pasar ese paso sin completar el campo.
          </AvisoImpacto>
        )}
      </div>
    </Modal>
  );
}
