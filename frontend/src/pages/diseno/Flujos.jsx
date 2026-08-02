import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { api } from "@/api/client";
import { useAccion, useLista } from "@/api/queries";
import { useInstitucion } from "@/auth/InstitutionContext";
import { Icon } from "@/components/icons";
import { PageHeader } from "@/components/Shell";
import { Badge, Button, Field, Input, Modal, Mono, Select, Tabs } from "@/components/ui";
import { Buscador, FiltroSelect, useBusquedaUrl, useFiltroUrl } from "@/components/ui/filtros";
import { TablaRecurso } from "@/components/ui/tabla";
import { useToast } from "@/components/ui/toast";
import { estadoVersion } from "@/lib/dominio";
import { plural } from "@/lib/format";

const TABS = [
  { key: "todos", label: "Todos" },
  { key: "publicada", label: "Publicado" },
  { key: "borrador", label: "Borrador" },
  { key: "archivada", label: "Archivado" },
];

// Plantillas de arranque: en vez de un lienzo en blanco, el flujo nuevo puede
// nacer con un esqueleto de nodos+conexiones listo para editar. Las claves `k`
// se remapean a los ids reales tras crear cada nodo.
const PLANTILLAS = [
  { key: "vacio", nombre: "En blanco", desc: "Solo el nodo Inicio.", nodos: [{ k: "ini", tipo: "inicio", titulo: "Inicio", x: 80, y: 220 }], conexiones: [] },
  {
    key: "ingreso", nombre: "Ingreso de paciente", desc: "Inicio → Formulario de datos → Cierre.",
    nodos: [
      { k: "ini", tipo: "inicio", titulo: "Inicio", x: 80, y: 220 },
      { k: "form", tipo: "form", titulo: "Datos del paciente", x: 360, y: 220 },
      { k: "fin", tipo: "fin", titulo: "Cierre", x: 640, y: 220 },
    ],
    conexiones: [["ini", "form"], ["form", "fin"]],
  },
  {
    key: "derivacion", nombre: "Derivación a especialidad", desc: "Inicio → Evaluación → Decisión → Derivar / Cierre.",
    nodos: [
      { k: "ini", tipo: "inicio", titulo: "Inicio", x: 60, y: 260 },
      { k: "form", tipo: "form", titulo: "Evaluación", x: 320, y: 260 },
      { k: "dec", tipo: "decision", titulo: "¿Requiere especialista?", x: 580, y: 260 },
      { k: "der", tipo: "derivar", titulo: "Derivar a especialidad", x: 860, y: 160 },
      { k: "fin", tipo: "fin", titulo: "Cierre", x: 860, y: 360 },
    ],
    conexiones: [["ini", "form"], ["form", "dec"], ["dec", "der"], ["dec", "fin"]],
  },
  {
    key: "fila", nombre: "Atención con fila de espera", desc: "Inicio → Atención (con fila) → Cierre.",
    nodos: [
      { k: "ini", tipo: "inicio", titulo: "Inicio", x: 80, y: 220 },
      { k: "at", tipo: "atencion", titulo: "Atención", x: 360, y: 220 },
      { k: "fin", tipo: "fin", titulo: "Cierre", x: 640, y: 220 },
    ],
    conexiones: [["ini", "at"], ["at", "fin"]],
  },
];

/** Versión que representa al flujo: la publicada, o la última si no hay ninguna. */
const versionVigente = (f) =>
  (f.versiones || []).find((v) => v.estado === "publicada") || (f.versiones || [])[0];

export default function Flujos() {
  const navigate = useNavigate();
  const toast = useToast();
  const { institucion } = useInstitucion();

  // Los tres filtros viven en la URL y se resuelven en el SERVIDOR. Antes se
  // aplicaban sobre los flujos ya traídos, o sea sobre la primera página.
  const [estado, setEstado] = useFiltroUrl("estado", "todos");
  const [area, setArea] = useFiltroUrl("area");
  const [texto, setTexto, busqueda] = useBusquedaUrl("q");
  const [nuevo, setNuevo] = useState(false);

  const areas = useLista("areas", { institucion: institucion?.id, pageSize: 100 }, { enabled: !!institucion });

  const duplicar = useAccion(async (flujo) => {
    const nf = await api.post("/flujos/", {
      institucion: flujo.institucion, area: flujo.area, subarea: flujo.subarea,
      titulo: `${flujo.titulo} (copia)`,
    });
    const ver = await api.post("/versiones-flujo/", { flujo: nf.id, numero: 1, estado: "borrador" });
    await api.post("/nodos/", { version: ver.id, tipo: "inicio", titulo: "Inicio", x: 80, y: 220 });
    return nf;
  }, {
    onSuccess: (nf) => toast.ok(`Se duplicó como «${nf.titulo}».`),
    onError: (e) => toast.deError(e, "No se pudo duplicar el flujo."),
  });

  return (
    <>
      <PageHeader subtitle="Diseñá un proceso como diagrama. La misma definición se ejecuta." />

      <div className="px-lg pb-8 pt-[18px] sm:px-[30px]">
        <div className="mb-[18px] flex flex-wrap items-center gap-lg">
          <Tabs tabs={TABS} valor={estado} onChange={setEstado} />
          <div className="flex-1" />
          <Buscador valor={texto} onChange={setTexto} placeholder="Buscar flujo…" className="w-64" aria-label="Buscar flujo" />
          <Button onClick={() => setNuevo(true)} className="flex items-center gap-2 whitespace-nowrap">
            <Icon name="plus" size={15} /> Nuevo flujo
          </Button>
        </div>

        <TablaRecurso
          clave="flujos"
          recurso="flujos"
          params={{
            institucion: institucion?.id,
            estado: estado === "todos" ? undefined : estado,
            area: area || undefined,
            search: busqueda || undefined,
          }}
          ordenInicial="titulo"
          onRowClick={(f) => navigate(`/flujos/${f.id}`)}
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
            titulo: "No hay flujos",
            detalle: "Creá el primero o cambiá los filtros.",
            accion: <Button onClick={() => setNuevo(true)}>Nuevo flujo</Button>,
          }}
          columnas={[
            {
              key: "titulo", label: "Flujo", orden: "titulo", truncar: true,
              render: (f) => (
                <div className="flex items-center gap-2.5">
                  <span className="flex size-8 flex-none items-center justify-center rounded-md bg-accent-50 text-accent">
                    <Icon name="workflow" size={16} />
                  </span>
                  <span className="truncate font-semibold">{f.titulo}</span>
                </div>
              ),
            },
            {
              key: "area", label: "Área",
              render: (f) => (
                <span className="inline-flex min-w-0 items-center gap-1.5" title={f.ambito_label}>
                  <Badge tone="info">{f.area_nombre}</Badge>
                  {f.subarea_nombre && (
                    <span className="truncate text-sm text-texto-debil">› {f.subarea_nombre}</span>
                  )}
                </span>
              ),
            },
            {
              key: "estado", label: "Estado",
              render: (f) => {
                const e = estadoVersion[versionVigente(f)?.estado] || estadoVersion.borrador;
                return <Badge tone={e.tone}>{e.label}</Badge>;
              },
            },
            { key: "version", label: "Ver.", render: (f) => <Mono>{versionVigente(f)?.etiqueta || "—"}</Mono> },
            {
              key: "casos_activos", label: "Casos",
              render: (f) => (f.casos_activos > 0 ? plural(f.casos_activos, "activo", "activos") : "—"),
            },
            {
              key: "creada", label: "Últ. edición", orden: "creado",
              render: (f) => {
                const v = versionVigente(f);
                return v ? new Date(v.creada).toLocaleDateString("es-AR") : "—";
              },
            },
            {
              key: "acciones", label: "", className: "text-right",
              render: (f) => (
                // Corta la propagación: la fila entera navega al diseñador y sin
                // esto duplicar también abriría el flujo original.
                <div className="flex justify-end gap-1" onClick={(e) => e.stopPropagation()}>
                  <IconBtn title="Abrir en diseñador" name="edit" onClick={() => navigate(`/flujos/${f.id}`)} />
                  <IconBtn
                    title="Duplicar"
                    name="copy"
                    disabled={duplicar.isPending}
                    onClick={() => duplicar.mutate(f)}
                  />
                </div>
              ),
            },
          ]}
        />
      </div>

      {nuevo && (
        <NuevoFlujoModal
          institucionId={institucion?.id}
          onClose={() => setNuevo(false)}
          onCreated={(id) => navigate(`/flujos/${id}`)}
        />
      )}
    </>
  );
}

function IconBtn({ title, onClick, name, disabled }) {
  return (
    <button
      type="button"
      title={title}
      aria-label={title}
      onClick={onClick}
      disabled={disabled}
      className="flex size-8 items-center justify-center rounded-sm text-texto-debil hover:bg-division hover:text-texto-medio disabled:opacity-40"
    >
      <Icon name={name} size={15} />
    </button>
  );
}

function NuevoFlujoModal({ institucionId, onClose, onCreated }) {
  const toast = useToast();
  const [form, setForm] = useState({ area: "", subarea: "", titulo: "" });
  const [plantilla, setPlantilla] = useState("vacio");
  const set = (k, v) => setForm((p) => ({ ...p, [k]: v }));

  const areas = useLista("areas", { institucion: institucionId, pageSize: 100 }, { enabled: !!institucionId });
  const areaSel = areas.filas.find((a) => String(a.id) === String(form.area));
  const subareas = areaSel?.subareas || [];
  const plantillaSel = PLANTILLAS.find((p) => p.key === plantilla) || PLANTILLAS[0];

  // Crea flujo + versión + nodos/conexiones de la plantilla.
  const crear = useAccion(async () => {
    const flujo = await api.post("/flujos/", {
      institucion: institucionId,
      area: form.area || null,
      subarea: form.subarea || null,
      titulo: form.titulo,
    });
    const ver = await api.post("/versiones-flujo/", { flujo: flujo.id, numero: 1, estado: "borrador" });
    const idMap = {};
    for (const n of plantillaSel.nodos) {
      const creado = await api.post("/nodos/", { version: ver.id, tipo: n.tipo, titulo: n.titulo, x: n.x, y: n.y });
      idMap[n.k] = creado.id;
    }
    for (const [o, d] of plantillaSel.conexiones) {
      await api.post("/conexiones/", { version: ver.id, origen: idMap[o], destino: idMap[d] });
    }
    return flujo;
  }, {
    onSuccess: (flujo) => onCreated(flujo.id),
    onError: (e) => toast.deError(e, "No se pudo crear el flujo. Revisá los datos e intentá de nuevo."),
  });

  return (
    <Modal
      title="Nuevo flujo"
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancelar</Button>
          <Button disabled={crear.isPending || !form.titulo} onClick={() => crear.mutate()}>
            {crear.isPending ? "Creando…" : "Crear y diseñar"}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3.5">
        <Field label="Título *">
          <Input value={form.titulo} onChange={(e) => set("titulo", e.target.value)} autoFocus placeholder="Ingreso de paciente" />
        </Field>
        <Field label="Plantilla">
          <Select value={plantilla} onChange={(e) => setPlantilla(e.target.value)}>
            {PLANTILLAS.map((p) => <option key={p.key} value={p.key}>{p.nombre}</option>)}
          </Select>
          <div className="mt-1.5 text-xs text-texto-debil">{plantillaSel.desc}</div>
        </Field>
        <Field label="Área">
          {/* Al cambiar de área se resetea la sub-área elegida. */}
          <Select value={form.area} onChange={(e) => setForm((p) => ({ ...p, area: e.target.value, subarea: "" }))}>
            <option value="">— Toda la institución —</option>
            {areas.filas.map((a) => <option key={a.id} value={a.id}>{a.nombre}</option>)}
          </Select>
        </Field>
        {areaSel && subareas.length > 0 && (
          <Field label="Sub-área (proceso específico)">
            <Select value={form.subarea} onChange={(e) => set("subarea", e.target.value)}>
              <option value="">— Proceso general del área —</option>
              {subareas.map((s) => <option key={s.id} value={s.id}>{s.nombre}</option>)}
            </Select>
          </Field>
        )}
        <div className="text-sm text-texto-debil">
          {form.subarea
            ? "Proceso específico de la sub-área."
            : form.area
              ? "Proceso general del área."
              : "Proceso de toda la institución."}
        </div>
      </div>
    </Modal>
  );
}
