import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { api } from "@/api/client";
import { useAccion, useLista } from "@/api/queries";
import { useInstitucion } from "@/auth/InstitutionContext";
import { Icon } from "@/components/icons";
import { Badge, Button, ConfirmDialog, Field, IconButton, Input, Modal, Mono, Select, Textarea } from "@/components/ui";
import { Buscador, FiltroSelect, useBusquedaUrl, useFiltroUrl } from "@/components/ui/filtros";
import { TablaRecurso } from "@/components/ui/tabla";
import { useToast } from "@/components/ui/toast";
import { plural } from "@/lib/format";

// Lista de formularios. El constructor vive en /formularios/:id.
export default function Formularios() {
  const { institucion } = useInstitucion();
  const navigate = useNavigate();
  const toast = useToast();
  const [texto, setTexto, busqueda] = useBusquedaUrl("q");
  // El área vive en la URL y se resuelve en el SERVIDOR (`filter_fields`): una
  // institución grande tiene un formulario por área y la lista sola no alcanza.
  const [area, setArea] = useFiltroUrl("area");
  const [nuevo, setNuevo] = useState(false);
  const [aBorrar, setABorrar] = useState(null);

  const areas = useLista("areas", { institucion: institucion?.id, pageSize: 100 }, { enabled: !!institucion });

  /*
   * Duplicar es del SERVIDOR, que copia el formulario con todos sus campos.
   *
   * «Admisión adultos» y «Admisión pediatría» comparten diez de doce campos, y
   * sin esto había que recrearlos de a uno: cada campo recreado a mano es una
   * etiqueta nueva que las Decisiones ya escritas no pueden reusar.
   */
  const duplicar = useAccion((f) => api.post(`/formularios/${f.id}/duplicar/`, {}), {
    onSuccess: (nf) => { toast.ok(`Se duplicó como «${nf.titulo}».`); navigate(`/formularios/${nf.id}`); },
    onError: (e) => toast.deError(e, "No se pudo duplicar el formulario."),
  });

  /*
   * Borrar el formulario que se creó por error o que dejó de usarse.
   *
   * El servidor lo rechaza si algún paso de algún flujo vigente todavía lo pide
   * (`Nodo.formulario` es SET_NULL: el paso quedaría «sin formulario» y el caso
   * que llegue no tiene con qué avanzar) o si sus campos tienen datos cargados
   * (CASCADE hasta `ValorCampo`). Acá se avisa antes de mandar el pedido.
   */
  const borrar = useAccion((f) => api.del(`/formularios/${f.id}/`), {
    onSuccess: () => { toast.ok("Formulario eliminado."); setABorrar(null); },
    onError: (e) => toast.deError(e, "No se pudo eliminar el formulario."),
  });

  return (
    <div className="px-lg py-[26px] sm:px-[30px]">
      <div className="mb-[18px] flex flex-wrap items-center justify-between gap-lg">
        <div>
          <h1 className="text-cifra-lg font-extrabold tracking-tight">Formularios</h1>
          <div className="mt-0.5 text-base text-texto-debil">
            Definí los campos que los flujos piden en cada paso.
          </div>
        </div>
        <div className="flex items-center gap-2.5">
          <Buscador valor={texto} onChange={setTexto} placeholder="Buscar formulario…" className="w-64" aria-label="Buscar formulario" />
          <Button onClick={() => setNuevo(true)} className="flex items-center gap-2 whitespace-nowrap">
            <Icon name="plus" size={15} /> Nuevo formulario
          </Button>
        </div>
      </div>

      <TablaRecurso
        clave="forms"
        recurso="formularios"
        params={{ institucion: institucion?.id, area: area || undefined, search: busqueda || undefined }}
        ordenInicial="titulo"
        onRowClick={(f) => navigate(`/formularios/${f.id}`)}
        barra={
          <FiltroSelect
            valor={area}
            onChange={setArea}
            etiqueta="Filtrar por área"
            todos="Todas las áreas"
            opciones={areas.filas.map((a) => ({ value: String(a.id), label: a.nombre }))}
          />
        }
        vacio={{
          titulo: busqueda || area ? "Ningún formulario coincide" : "No hay formularios",
          detalle: busqueda || area ? "Probá con otro título o quitá el filtro de área." : "Creá el primero para que los flujos tengan qué pedir.",
          accion: !busqueda && !area && <Button onClick={() => setNuevo(true)}>Nuevo formulario</Button>,
        }}
        columnas={[
          {
            key: "titulo", label: "Formulario", orden: "titulo", truncar: true,
            render: (f) => (
              <div className="flex items-center gap-2.5">
                <span className="flex size-9 flex-none items-center justify-center rounded-md bg-accent-50 text-accent">
                  <Icon name="form" size={17} />
                </span>
                <span className="truncate font-semibold">{f.titulo}</span>
              </div>
            ),
          },
          { key: "area", label: "Ámbito", render: (f) => <Badge tone="info">{f.area_nombre}</Badge> },
          { key: "campos", label: "Campos", render: (f) => <Mono>{f.campos?.length || 0}</Mono> },
          {
            // Reemplaza a la columna «Vinculados», que sólo podía dar 0: la
            // precarga desde historia clínica o legajo no está implementada en
            // ninguna parte y el alta de campo tampoco dejaba elegir el origen,
            // así que la columna contaba una función que no existe. Cuántos
            // campos son obligatorios sí dice algo del formulario: es lo que
            // traba a un caso cuando falta cargarlos.
            key: "requeridos", label: "Requeridos",
            render: (f) => <Mono>{(f.campos || []).filter((c) => c.requerido).length}</Mono>,
          },
          {
            // En cuántos flujos se pide. Es lo primero que hay que saber antes de
            // tocarle un campo o de borrarlo, y hasta ahora la única forma de
            // averiguarlo era abrir los flujos de a uno en el diseñador.
            key: "usos", label: "Se usa en",
            render: (f) =>
              f.usos_n > 0
                ? <span className="text-texto-suave">{plural(f.usos_n, "flujo", "flujos")}</span>
                : <span className="text-texto-tenue" title="Ningún paso de ningún flujo vigente lo pide">sin uso</span>,
          },
          {
            key: "descripcion", label: "Descripción", truncar: true,
            render: (f) => <span className="text-texto-debil">{f.descripcion || "—"}</span>,
          },
          {
            key: "acciones", label: "", className: "text-right",
            render: (f) => (
              // Corta la propagación: la fila entera abre el constructor y sin
              // esto duplicar abriría además el formulario original.
              <div className="flex justify-end gap-1" onClick={(e) => e.stopPropagation()}>
                <IconButton icon="copy" label="Duplicar" size="sm" disabled={duplicar.isPending} onClick={() => duplicar.mutate(f)} />
                <IconButton icon="trash" label="Eliminar formulario" size="sm" onClick={() => setABorrar(f)} />
              </div>
            ),
          },
        ]}
      />

      {nuevo && (
        <NuevoFormModal
          institucionId={institucion?.id}
          areas={areas.filas}
          onClose={() => setNuevo(false)}
          onCreated={(id) => navigate(`/formularios/${id}`)}
        />
      )}

      {aBorrar && (
        <BorrarFormularioDialog
          formulario={aBorrar}
          cargando={borrar.isPending}
          onConfirmar={() => borrar.mutate(aBorrar)}
          onClose={() => setABorrar(null)}
        />
      )}
    </div>
  );
}

/**
 * Confirmación de borrado de un formulario, compartida con el constructor.
 *
 * Los dos motivos por los que el servidor lo rechaza se dicen ANTES: que un
 * flujo vigente lo pida y que sus campos tengan datos cargados. Con `usos_n > 0`
 * el diálogo no ofrece borrar, porque el pedido va a volver con 409.
 */
export function BorrarFormularioDialog({ formulario, cargando, onConfirmar, onClose }) {
  const enUso = formulario.usos_n > 0;
  const datos = (formulario.campos || []).reduce((n, c) => n + (c.valores_cargados || 0), 0);
  const bloqueado = enUso || datos > 0;

  return (
    <ConfirmDialog
      title={bloqueado ? `«${formulario.titulo}» no se puede eliminar` : `¿Eliminar «${formulario.titulo}»?`}
      confirmar={bloqueado ? "Entendido" : "Eliminar formulario"}
      peligroso={!bloqueado}
      cargando={cargando}
      onConfirmar={bloqueado ? onClose : onConfirmar}
      onClose={onClose}
    >
      {enUso ? (
        <>
          Se pide en {plural(formulario.usos_n, "flujo", "flujos")}. Si se elimina, esos pasos
          quedan <strong>sin formulario</strong> y el caso que llegue ahí no tiene con qué
          avanzar. Quitalo de esos pasos en el diseñador y volvé a intentar.
        </>
      ) : datos > 0 ? (
        <>
          Sus campos tienen {plural(datos, "dato cargado", "datos cargados")} en casos reales.
          Eliminar el formulario borra los campos y, con ellos, todos esos valores: motivo de
          consulta, triage, alergias. No hay de dónde recuperarlos.
        </>
      ) : (
        <>
          Ningún flujo lo pide y no tiene datos cargados, así que no se pierde nada de lo ya
          registrado. Se eliminan también sus campos.
        </>
      )}
    </ConfirmDialog>
  );
}

function NuevoFormModal({ institucionId, areas, onClose, onCreated }) {
  const toast = useToast();
  const [titulo, setTitulo] = useState("");
  // Descripción y área se piden acá porque hasta ahora no había NINGUNA forma de
  // cargarlas desde la app: la columna «Descripción» del listado sólo podía
  // decir «—» y el área quedaba siempre vacía aunque el modelo y el filtro por
  // área existan desde el principio.
  const [descripcion, setDescripcion] = useState("");
  const [area, setArea] = useState("");

  const crear = useAccion(
    () => api.post("/formularios/", {
      institucion: institucionId,
      titulo,
      descripcion,
      area: area || null,
    }),
    {
      onSuccess: (f) => onCreated(f.id),
      onError: (e) => toast.deError(e, "No se pudo crear el formulario."),
    },
  );

  return (
    <Modal
      title="Nuevo formulario"
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancelar</Button>
          <Button disabled={crear.isPending || !titulo} onClick={() => crear.mutate()}>
            {crear.isPending ? "…" : "Crear y diseñar"}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3.5">
        <Field label="Título *">
          <Input value={titulo} onChange={(e) => setTitulo(e.target.value)} autoFocus placeholder="Datos del paciente" />
        </Field>
        <Field label="Área" hint="Sin área queda disponible para toda la institución.">
          <Select value={area} onChange={(e) => setArea(e.target.value)}>
            <option value="">Toda la institución</option>
            {areas.map((a) => <option key={a.id} value={a.id}>{a.nombre}</option>)}
          </Select>
        </Field>
        <Field label="Descripción" hint="Para qué sirve. Se ve en el listado y al elegirlo en un paso.">
          <Textarea
            rows={2}
            value={descripcion}
            onChange={(e) => setDescripcion(e.target.value)}
            placeholder="Datos que se piden al ingresar al paciente por guardia."
          />
        </Field>
      </div>
    </Modal>
  );
}
