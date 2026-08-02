import { useEffect, useMemo, useState } from "react";

import { api } from "@/api/client";
import { useAccion, useLista } from "@/api/queries";
import { useInstitucion } from "@/auth/InstitutionContext";
import { Icon } from "@/components/icons";
import {
  Avatar, Badge, Button, Card, ConfirmDialog, Field, Input, Modal, Mono, Select, Tabs, Textarea,
} from "@/components/ui";
import { EstadoError, EstadoVacio, Skeleton } from "@/components/ui/estados";
import { TablaRecurso } from "@/components/ui/tabla";
import { useToast } from "@/components/ui/toast";
import { plural } from "@/lib/format";

/** Funciones operativas que se pueden asignar a un área. */
const FUNCIONES = [
  { value: "jefe_area", label: "Jefe / Supervisor de área" },
  { value: "administrativo", label: "Administrativo" },
  { value: "enfermeria", label: "Enfermería" },
  { value: "medico", label: "Médico / profesional" },
];

// Estructura organizativa: tabla de áreas + ficha en panel lateral.
export default function Areas() {
  const { institucion } = useInstitucion();
  const toast = useToast();
  const [nuevoArea, setNuevoArea] = useState(false);
  const [selId, setSelId] = useState(null); // área abierta en el panel lateral
  const [editar, setEditar] = useState(false);
  const [aBorrar, setABorrar] = useState(null);

  const areas = useLista(
    "areas",
    { institucion: institucion?.id, pageSize: 100 },
    { enabled: !!institucion },
  );
  // Se busca por id y no se guarda el objeto: así el panel refleja los cambios
  // (renombrar, sumar sub-áreas) sin quedarse con una copia vieja en el estado.
  const sel = areas.filas.find((a) => a.id === selId) || null;

  const borrarArea = useAccion((a) => api.del(`/areas/${a.id}/`), {
    onSuccess: () => { toast.ok("Área eliminada."); setABorrar(null); setSelId(null); },
    onError: (e) => toast.deError(e, "No se pudo eliminar. Puede tener elementos asociados."),
  });

  return (
    <div className="px-lg py-[26px] sm:px-[30px]">
      <div className="mb-[18px] flex flex-wrap items-center justify-between gap-lg">
        <div>
          <h1 className="text-cifra-lg font-extrabold tracking-tight">Áreas</h1>
          <div className="mt-0.5 text-base text-texto-debil">
            {plural(areas.total, "área", "áreas")} · {institucion?.nombre}
          </div>
        </div>
        <Button onClick={() => setNuevoArea(true)} className="flex items-center gap-2">
          <Icon name="plus" size={15} /> Nueva área
        </Button>
      </div>

      <TablaRecurso
        clave="areas"
        recurso="areas"
        params={{ institucion: institucion?.id }}
        ordenInicial="nombre"
        onRowClick={(a) => setSelId(a.id)}
        vacio={{
          titulo: "No hay áreas",
          detalle: "Creá la primera para poder armar flujos, grupos y boxes.",
          accion: <Button onClick={() => setNuevoArea(true)}>Nueva área</Button>,
        }}
        columnas={[
          {
            key: "nombre", label: "Área", orden: "nombre", truncar: true,
            render: (a) => (
              <div className="flex items-center gap-2.5">
                <span className="flex size-9 flex-none items-center justify-center rounded-md bg-accent-50 text-accent">
                  <Icon name="cube" size={17} />
                </span>
                <span className="truncate font-semibold">{a.nombre}</span>
              </div>
            ),
          },
          {
            key: "responsable", label: "Responsable",
            render: (a) => (
              <span className={a.responsable ? "text-texto-medio" : "text-texto-tenue"}>
                {a.responsable || "—"}
              </span>
            ),
          },
          { key: "staff", label: "Staff", render: (a) => <Mono>{a.staff}</Mono> },
          { key: "sub", label: "Sub-áreas", render: (a) => <Mono>{a.subareas?.length || 0}</Mono> },
          {
            key: "acc", label: "", className: "text-right",
            render: (a) => (
              <button
                onClick={(e) => { e.stopPropagation(); setABorrar(a); }}
                title={`Eliminar ${a.nombre}`}
                aria-label={`Eliminar ${a.nombre}`}
                className="inline-flex rounded-md p-1 text-texto-debil hover:bg-badge-error-bg hover:text-danger"
              >
                <Icon name="trash" size={15} />
              </button>
            ),
          },
        ]}
      />

      {sel && (
        <PanelLateral titulo={sel.nombre} onCerrar={() => setSelId(null)}>
          <FichaArea
            key={sel.id}
            area={sel}
            institucionNombre={institucion?.nombre}
            onEditar={() => setEditar(true)}
            onChange={areas.refetch}
          />
        </PanelLateral>
      )}

      {nuevoArea && <AreaModal institucionId={institucion?.id} onClose={() => setNuevoArea(false)} />}
      {editar && sel && (
        <AreaModal area={sel} institucionId={institucion?.id} onClose={() => setEditar(false)} />
      )}

      {aBorrar && (
        <ConfirmDialog
          title="Eliminar área"
          confirmar="Eliminar"
          peligroso
          cargando={borrarArea.isPending}
          onConfirmar={() => borrarArea.mutate(aBorrar)}
          onClose={() => setABorrar(null)}
        >
          ¿Seguro que querés eliminar <strong>{aBorrar.nombre}</strong>? Se eliminarán
          también sus sub-áreas. Esta acción no se puede deshacer.
        </ConfirmDialog>
      )}
    </div>
  );
}

/**
 * Panel lateral con la ficha del área.
 *
 * Es un diálogo: se anuncia como tal, cierra con Escape y bloquea el scroll de
 * atrás. Antes sólo cerraba con clic afuera, así que con el teclado se quedaba
 * atrapado sin salida.
 */
function PanelLateral({ titulo, onCerrar, children }) {
  useEffect(() => {
    const alTecla = (e) => { if (e.key === "Escape") onCerrar(); };
    document.addEventListener("keydown", alTecla);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", alTecla);
      document.body.style.overflow = overflow;
    };
  }, [onCerrar]);

  return (
    <div
      onMouseDown={onCerrar}
      className="fixed inset-0 z-40 flex justify-end bg-ink/35 animate-[fadeIn_.12s_ease]"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={`Área ${titulo}`}
        onMouseDown={(e) => e.stopPropagation()}
        className="h-full w-full max-w-[37.5rem] overflow-y-auto bg-superficie shadow-modal"
      >
        <div className="flex justify-end px-lg pt-3.5">
          <button
            onClick={onCerrar}
            aria-label="Cerrar panel"
            className="flex rounded-md p-1 text-texto-debil hover:bg-superficie-2 hover:text-texto-medio"
          >
            <Icon name="x" size={18} />
          </button>
        </div>
        <div className="px-7 pb-7">{children}</div>
      </div>
    </div>
  );
}

function FichaArea({ area, institucionNombre, onEditar, onChange }) {
  const [tab, setTab] = useState("datos");
  const [asignar, setAsignar] = useState(false);
  const [crearSub, setCrearSub] = useState(false);
  const [crearGrupo, setCrearGrupo] = useState(false);
  const [crearBox, setCrearBox] = useState(false);

  const TABS = [
    { key: "datos", label: "Datos" },
    { key: "staff", label: "Staff" },
    { key: "grupos", label: "Grupos" },
    { key: "boxes", label: "Boxes" },
    { key: "subareas", label: "Sub-áreas" },
  ];

  // Botón de acción contextual: cambia según la solapa activa.
  const accion = {
    staff: { label: "Asignar profesional", on: () => setAsignar(true) },
    grupos: { label: "Crear grupo", on: () => setCrearGrupo(true) },
    boxes: { label: "Crear box", on: () => setCrearBox(true) },
    subareas: { label: "Crear sub-área", on: () => setCrearSub(true) },
  }[tab];

  return (
    <div>
      <div className="mb-1 flex items-center gap-2.5">
        <h2 className="text-cifra font-extrabold tracking-tight">{area.nombre}</h2>
        <Badge tone="info">Área</Badge>
      </div>
      <div className="mb-lg text-md text-texto-debil">
        Responsable: <strong className="text-texto-medio">{area.responsable || "—"}</strong>
      </div>

      <div className="mb-[22px] flex flex-wrap gap-2.5">
        <Button variant="secondary" onClick={onEditar}>Editar</Button>
        {accion && (
          <Button onClick={accion.on} className="flex items-center gap-1.5">
            <Icon name="plus" size={15} /> {accion.label}
          </Button>
        )}
      </div>

      <Tabs tabs={TABS} valor={tab} onChange={setTab} className="mb-5" />

      {tab === "datos" && (
        <Card className="p-[22px]">
          <div className="grid gap-lg sm:grid-cols-2">
            <Dato k="Nombre" v={area.nombre} />
            <Dato k="Responsable / jefe" v={area.responsable || "—"} />
            <Dato k="Estado" v={area.activa ? "Activa" : "Inactiva"} />
            <Dato k="Pertenece a" v={institucionNombre} />
            <div className="sm:col-span-2"><Dato k="Descripción" v={area.descripcion || "—"} /></div>
          </div>
        </Card>
      )}
      {tab === "staff" && <StaffTab area={area} />}
      {tab === "grupos" && <GruposTab area={area} />}
      {tab === "boxes" && <BoxesTab area={area} />}
      {tab === "subareas" && <SubareasTab area={area} onChange={onChange} />}

      {asignar && <AsignarModal area={area} onClose={() => setAsignar(false)} />}
      {crearSub && <NuevaSubareaModal area={area} onClose={() => setCrearSub(false)} onSaved={onChange} />}
      {crearGrupo && <GrupoModal area={area} onClose={() => setCrearGrupo(false)} />}
      {crearBox && <BoxModal area={area} onClose={() => setCrearBox(false)} />}
    </div>
  );
}

function Dato({ k, v }) {
  return (
    <div>
      <div className="mb-0.5 text-sm text-texto-debil">{k}</div>
      <div className="text-md font-semibold">{v}</div>
    </div>
  );
}

/** Aviso corto dentro de una pestaña de la ficha (sin datos todavía). */
function Aviso({ children }) {
  return <Card className="p-6 text-md text-texto-debil">{children}</Card>;
}

/**
 * Membresías de ESTA área, filtradas por el servidor.
 *
 * `?areas=<id>` filtra por la M2M y existe en el backend desde hace rato; esta
 * pantalla igual se traía TODAS las membresías de la institución y TODOS los
 * usuarios para cruzarlos en memoria. Con `/usuarios/` paginando de a 25, quien
 * no entrara en esa página aparecía como «—» aunque estuviera asignado.
 */
function useStaffDeArea(area) {
  return useLista("membresias", { areas: area.id, pageSize: 200 });
}

function StaffTab({ area }) {
  const toast = useToast();
  const staff = useStaffDeArea(area);
  const grupos = useLista("grupos", { area: area.id, pageSize: 100 });

  // usuario_id → nombres de los grupos del área que integra.
  const gruposPorUsuario = useMemo(() => {
    const m = {};
    grupos.filas.forEach((g) => {
      (g.integrantes || []).forEach((p) => { (m[p.id] = m[p.id] || []).push(g.nombre); });
    });
    return m;
  }, [grupos.filas]);

  // Quitar a alguien de esta área: si su membresía cubre otras, sólo se le saca
  // esta; si era la única, se elimina la membresía completa.
  const quitar = useAccion(
    (m) => {
      const resto = (m.areas || []).filter((a) => a !== area.id);
      return resto.length
        ? api.patch(`/membresias/${m.id}/`, { areas: resto })
        : api.del(`/membresias/${m.id}/`);
    },
    {
      onSuccess: () => toast.ok("Se quitó del área."),
      onError: (e) => toast.deError(e, "No se pudo quitar del área."),
    },
  );

  if (staff.error) return <EstadoError error={staff.error} onReintentar={staff.refetch} />;
  if (staff.isLoading) return <Skeleton className="h-24" />;
  if (!staff.filas.length) return <Aviso>Sin profesionales asignados a esta área.</Aviso>;

  return (
    <ul className="flex flex-col gap-2">
      {staff.filas.map((m) => {
        const enGrupos = gruposPorUsuario[m.usuario] || [];
        return (
          <li key={m.id}>
            <Card className="flex flex-wrap items-center gap-3 px-lg py-3">
              <Avatar nombre={m.usuario_nombre || m.usuario_email} i={m.usuario} size={32} />
              <div className="min-w-0 flex-1">
                <div className="truncate text-md font-semibold">{m.usuario_nombre || "—"}</div>
                <div className="truncate text-sm text-texto-debil">{m.usuario_email}</div>
              </div>
              {enGrupos.length > 0 && (
                <Badge tone="info" className="cursor-default">
                  <span title={`En ${enGrupos.length === 1 ? "el grupo" : "los grupos"}: ${enGrupos.join(", ")}`}>
                    {enGrupos.length === 1 ? enGrupos[0] : plural(enGrupos.length, "grupo", "grupos")}
                  </span>
                </Badge>
              )}
              <Badge tone="neutral">{m.rol_display}</Badge>
              <button
                onClick={() => quitar.mutate(m)}
                disabled={quitar.isPending}
                title="Quitar de esta área"
                className="rounded-md px-1.5 py-1 text-sm text-texto-debil hover:bg-badge-error-bg hover:text-danger disabled:opacity-40"
              >
                quitar
              </button>
            </Card>
          </li>
        );
      })}
    </ul>
  );
}

function GruposTab({ area }) {
  const toast = useToast();
  const [gestion, setGestion] = useState(null);
  const [aBorrar, setABorrar] = useState(null);

  const grupos = useLista("grupos", { area: area.id, pageSize: 100 });
  const staff = useStaffDeArea(area);

  const borrar = useAccion((g) => api.del(`/grupos/${g.id}/`), {
    onSuccess: () => { toast.ok("Grupo eliminado."); setABorrar(null); },
    onError: (e) => toast.deError(e, "No se pudo eliminar el grupo."),
  });

  if (grupos.error) return <EstadoError error={grupos.error} onReintentar={grupos.refetch} />;
  if (grupos.isLoading) return <Skeleton className="h-24" />;
  if (!grupos.filas.length) {
    return (
      <Aviso>
        Sin grupos. Usá «Crear grupo» para armar equipos con personas del área; después
        se usan en los flujos.
      </Aviso>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      {grupos.filas.map((g) => (
        <Card key={g.id} className="px-lg py-3.5">
          <div className="flex flex-wrap items-center gap-3">
            <span className="flex size-9 flex-none items-center justify-center rounded-md bg-accent-50 text-accent">
              <Icon name="users" size={17} />
            </span>
            <div className="min-w-0 flex-1">
              <div className="truncate text-md font-semibold">{g.nombre}</div>
              {g.descripcion && <div className="truncate text-sm text-texto-debil">{g.descripcion}</div>}
            </div>
            <span className="text-sm text-texto-debil">
              {plural(g.integrantes.length, "integrante", "integrantes")}
            </span>
            <Button variant="secondary" onClick={() => setGestion(g)}>Gestionar</Button>
            <button
              onClick={() => setABorrar(g)}
              title={`Eliminar grupo ${g.nombre}`}
              aria-label={`Eliminar grupo ${g.nombre}`}
              className="inline-flex rounded-md p-1 text-texto-debil hover:bg-badge-error-bg hover:text-danger"
            >
              <Icon name="trash" size={15} />
            </button>
          </div>

          {g.integrantes.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {g.integrantes.map((p) => (
                <span
                  key={p.id}
                  className="inline-flex items-center gap-1.5 rounded-pill border border-borde bg-superficie-2 py-0.5 pl-0.5 pr-2.5 text-sm"
                >
                  <Avatar nombre={p.nombre || p.email} i={p.id} size={22} /> {p.nombre || p.email}
                </span>
              ))}
            </div>
          )}
        </Card>
      ))}

      {gestion && (
        <MiembrosModal
          grupo={gestion}
          staff={staff}
          grupos={grupos.filas}
          onClose={() => setGestion(null)}
        />
      )}

      {aBorrar && (
        <ConfirmDialog
          title="Eliminar grupo"
          confirmar="Eliminar"
          peligroso
          cargando={borrar.isPending}
          onConfirmar={() => borrar.mutate(aBorrar)}
          onClose={() => setABorrar(null)}
        >
          ¿Seguro que querés eliminar el grupo <strong>{aBorrar.nombre}</strong>? Los flujos
          que lo usen quedan sin destinatario. Esta acción no se puede deshacer.
        </ConfirmDialog>
      )}
    </div>
  );
}

function GrupoModal({ area, onClose }) {
  const toast = useToast();
  const [f, setF] = useState({ nombre: "", descripcion: "" });
  const set = (k, v) => setF((p) => ({ ...p, [k]: v }));

  const crear = useAccion(
    () => api.post("/grupos/", { area: area.id, nombre: f.nombre.trim(), descripcion: f.descripcion }),
    {
      onSuccess: () => { toast.ok("Grupo creado."); onClose(); },
      onError: (e) => toast.deError(e, "No se pudo crear el grupo."),
    },
  );

  return (
    <Modal
      title={`Nuevo grupo · ${area.nombre}`}
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancelar</Button>
          <Button disabled={crear.isPending || !f.nombre.trim()} onClick={() => crear.mutate()}>
            {crear.isPending ? "…" : "Crear"}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3.5">
        <Field label="Nombre del grupo *">
          <Input value={f.nombre} onChange={(e) => set("nombre", e.target.value)} autoFocus placeholder="Guardia mañana" />
        </Field>
        <Field label="Descripción">
          <Textarea value={f.descripcion} onChange={(e) => set("descripcion", e.target.value)} placeholder="Para qué se usa este grupo…" />
        </Field>
      </div>
    </Modal>
  );
}

function MiembrosModal({ grupo, staff, grupos = [], onClose }) {
  const toast = useToast();
  const [sel, setSel] = useState(() => new Set(grupo.integrantes.map((p) => p.id)));

  // usuario_id → nombres de OTROS grupos del área que ya integra.
  const otrosGrupos = useMemo(() => {
    const m = {};
    grupos.filter((g) => g.id !== grupo.id).forEach((g) => {
      (g.integrantes || []).forEach((p) => { (m[p.id] = m[p.id] || []).push(g.nombre); });
    });
    return m;
  }, [grupos, grupo.id]);

  const guardar = useAccion(() => api.patch(`/grupos/${grupo.id}/`, { miembros: [...sel] }), {
    onSuccess: () => { toast.ok("Integrantes actualizados."); onClose(); },
    onError: (e) => toast.deError(e, "No se pudieron guardar los cambios."),
  });

  function alternar(id) {
    setSel((prev) => {
      const n = new Set(prev);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });
  }

  return (
    <Modal
      title={`Integrantes · ${grupo.nombre}`}
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancelar</Button>
          <Button disabled={guardar.isPending} onClick={() => guardar.mutate()}>
            {guardar.isPending ? "…" : "Guardar"}
          </Button>
        </>
      }
    >
      {staff.isLoading ? (
        <Skeleton className="h-40" />
      ) : staff.filas.length === 0 ? (
        <div className="text-md text-texto-debil">
          No hay personas asignadas al área. Primero asigná profesionales en la pestaña «Staff».
        </div>
      ) : (
        <div className="flex max-h-[22.5rem] flex-col gap-1 overflow-auto">
          {staff.filas.map((m) => {
            const marcado = sel.has(m.usuario);
            const enOtros = otrosGrupos[m.usuario] || [];
            return (
              <label
                key={m.usuario}
                className={
                  "flex cursor-pointer items-center gap-2.5 rounded-md px-2.5 py-2 " +
                  (marcado ? "bg-accent-50" : "hover:bg-superficie-2")
                }
              >
                <input type="checkbox" checked={marcado} onChange={() => alternar(m.usuario)} />
                <Avatar nombre={m.usuario_nombre || m.usuario_email} i={m.usuario} size={30} />
                <div className="min-w-0 flex-1">
                  <div className="truncate text-md font-semibold">{m.usuario_nombre || "—"}</div>
                  <div className="truncate text-sm text-texto-debil">{m.usuario_email}</div>
                </div>
                {enOtros.length > 0 && (
                  <Badge tone="amber" className="cursor-pointer">
                    <span title={`Ya está en: ${enOtros.join(", ")}`}>
                      {enOtros.length === 1 ? "En otro grupo" : `En ${enOtros.length} grupos`}
                    </span>
                  </Badge>
                )}
              </label>
            );
          })}
        </div>
      )}
    </Modal>
  );
}

function BoxesTab({ area }) {
  const toast = useToast();
  const [aBorrar, setABorrar] = useState(null);
  const boxes = useLista("boxes", { area: area.id, pageSize: 100 });

  const borrar = useAccion((b) => api.del(`/boxes/${b.id}/`), {
    onSuccess: () => { toast.ok("Box eliminado."); setABorrar(null); },
    onError: (e) => toast.deError(e, "No se pudo eliminar el box."),
  });

  if (boxes.error) return <EstadoError error={boxes.error} onReintentar={boxes.refetch} />;
  if (boxes.isLoading) return <Skeleton className="h-24" />;
  if (!boxes.filas.length) {
    return (
      <Aviso>
        Sin boxes. Usá «Crear box» para definir los consultorios; desde ellos se llama a
        la fila de espera.
      </Aviso>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      {boxes.filas.map((b) => (
        <Card key={b.id} className="flex items-center gap-3 px-lg py-3">
          <span className="flex size-8 flex-none items-center justify-center rounded-md bg-accent-50 text-accent">
            <Icon name="enter" size={16} />
          </span>
          <div className="flex-1 text-md font-semibold">{b.nombre}</div>
          {!b.activo && <Badge tone="gray">inactivo</Badge>}
          <button
            onClick={() => setABorrar(b)}
            title={`Eliminar ${b.nombre}`}
            aria-label={`Eliminar ${b.nombre}`}
            className="inline-flex rounded-md p-1 text-texto-debil hover:bg-badge-error-bg hover:text-danger"
          >
            <Icon name="trash" size={15} />
          </button>
        </Card>
      ))}

      {aBorrar && (
        <ConfirmDialog
          title="Eliminar box"
          confirmar="Eliminar"
          peligroso
          cargando={borrar.isPending}
          onConfirmar={() => borrar.mutate(aBorrar)}
          onClose={() => setABorrar(null)}
        >
          ¿Seguro que querés eliminar <strong>{aBorrar.nombre}</strong>?
        </ConfirmDialog>
      )}
    </div>
  );
}

function BoxModal({ area, onClose }) {
  const toast = useToast();
  const [nombre, setNombre] = useState("");

  const crear = useAccion(() => api.post("/boxes/", { area: area.id, nombre: nombre.trim() }), {
    onSuccess: () => { toast.ok("Box creado."); onClose(); },
    onError: (e) => toast.deError(e, "No se pudo crear el box."),
  });

  return (
    <Modal
      title={`Nuevo box · ${area.nombre}`}
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancelar</Button>
          <Button disabled={crear.isPending || !nombre.trim()} onClick={() => crear.mutate()}>
            {crear.isPending ? "…" : "Crear"}
          </Button>
        </>
      }
    >
      <Field label="Nombre del box *">
        <Input value={nombre} onChange={(e) => setNombre(e.target.value)} autoFocus placeholder="Box 1" />
      </Field>
    </Modal>
  );
}

function SubareasTab({ area, onChange }) {
  const [selId, setSelId] = useState(null);
  const flujos = useLista("flujos", { institucion: area.institucion, pageSize: 200 });

  const sub = (area.subareas || []).find((s) => s.id === selId);
  if (sub) {
    return (
      <SubareaFicha
        sub={sub}
        flujos={flujos.filas.filter((f) => f.subarea === sub.id)}
        onVolver={() => setSelId(null)}
        onChange={onChange}
      />
    );
  }

  if (!area.subareas?.length) {
    return <Aviso>Sin sub-áreas. Usá «Crear sub-área». (Una sub-área no contiene sub-áreas.)</Aviso>;
  }

  return (
    <ul className="flex flex-col gap-2">
      {area.subareas.map((s) => {
        const n = flujos.filas.filter((f) => f.subarea === s.id).length;
        return (
          <li key={s.id}>
            <button
              onClick={() => setSelId(s.id)}
              className="flex w-full items-center gap-3 rounded-lg border border-borde bg-superficie px-lg py-3 text-left hover:border-accent-100"
            >
              <span className="flex size-8 flex-none items-center justify-center rounded-md bg-superficie-2 text-texto-debil">
                <Icon name="cube" size={15} />
              </span>
              <span className="flex-1 truncate text-md font-semibold">{s.nombre}</span>
              <span className="text-sm text-texto-debil">{plural(n, "flujo", "flujos")}</span>
              <Icon name="back" size={14} className="rotate-180 text-texto-debil" />
            </button>
          </li>
        );
      })}
    </ul>
  );
}

function SubareaFicha({ sub, flujos, onVolver, onChange }) {
  const toast = useToast();
  const [editando, setEditando] = useState(false);
  const [nombre, setNombre] = useState(sub.nombre);
  const [confirmar, setConfirmar] = useState(false);

  const renombrar = useAccion(() => api.patch(`/subareas/${sub.id}/`, { nombre: nombre.trim() }), {
    onSuccess: () => { toast.ok("Sub-área renombrada."); setEditando(false); onChange(); },
    onError: (e) => toast.deError(e, "No se pudo renombrar."),
  });

  const eliminar = useAccion(() => api.del(`/subareas/${sub.id}/`), {
    onSuccess: () => { toast.ok("Sub-área eliminada."); onVolver(); onChange(); },
    onError: (e) => toast.deError(e, "No se pudo eliminar la sub-área."),
  });

  function guardarNombre() {
    if (!nombre.trim() || nombre.trim() === sub.nombre) { setEditando(false); return; }
    renombrar.mutate();
  }

  return (
    <div>
      <button
        onClick={onVolver}
        className="mb-3.5 flex items-center gap-1.5 text-base text-texto-debil hover:text-texto-medio"
      >
        <Icon name="back" size={14} /> Sub-áreas
      </button>

      <div className="mb-lg flex flex-wrap items-center gap-2.5">
        {editando ? (
          <>
            <Input
              value={nombre}
              onChange={(e) => setNombre(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") guardarNombre(); }}
              autoFocus
              className="max-w-70"
              aria-label="Nombre de la sub-área"
            />
            <Button disabled={renombrar.isPending} onClick={guardarNombre}>Guardar</Button>
            <Button variant="secondary" onClick={() => { setNombre(sub.nombre); setEditando(false); }}>
              Cancelar
            </Button>
          </>
        ) : (
          <>
            <h3 className="text-xl font-extrabold tracking-tight">{sub.nombre}</h3>
            <Badge tone="neutral">Sub-área</Badge>
            <button onClick={() => setEditando(true)} className="text-base font-semibold text-accent hover:underline">
              Renombrar
            </button>
          </>
        )}
      </div>

      <h4 className="mb-2.5 text-base font-bold text-texto-medio">
        Flujos vinculados <span className="font-medium text-texto-debil">· {flujos.length}</span>
      </h4>
      {flujos.length === 0 ? (
        <Aviso>Ningún flujo usa esta sub-área todavía.</Aviso>
      ) : (
        <div className="flex flex-col gap-2">
          {flujos.map((f) => (
            <Card key={f.id} className="flex items-center gap-2.5 px-3.5 py-2.5">
              <Icon name="workflow" size={15} className="text-accent" />
              <span className="text-md font-semibold">{f.titulo}</span>
            </Card>
          ))}
        </div>
      )}

      <div className="mt-[22px] border-t border-borde pt-lg">
        {confirmar ? (
          <div className="flex flex-wrap items-center gap-2.5">
            <span className="text-base text-texto-medio">¿Eliminar «{sub.nombre}»?</span>
            <Button variant="danger" disabled={eliminar.isPending} onClick={() => eliminar.mutate()}>
              {eliminar.isPending ? "…" : "Sí, eliminar"}
            </Button>
            <Button variant="secondary" onClick={() => setConfirmar(false)}>No</Button>
          </div>
        ) : (
          <button onClick={() => setConfirmar(true)} className="text-base font-semibold text-danger hover:underline">
            Eliminar sub-área
          </button>
        )}
      </div>
    </div>
  );
}

function NuevaSubareaModal({ area, onClose, onSaved }) {
  const toast = useToast();
  const [nombre, setNombre] = useState("");

  const crear = useAccion(() => api.post("/subareas/", { area: area.id, nombre: nombre.trim() }), {
    onSuccess: () => { toast.ok("Sub-área creada."); onSaved(); onClose(); },
    onError: (e) => toast.deError(e, "No se pudo crear la sub-área."),
  });

  return (
    <Modal
      title={`Nueva sub-área · ${area.nombre}`}
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancelar</Button>
          <Button disabled={crear.isPending || !nombre.trim()} onClick={() => crear.mutate()}>
            {crear.isPending ? "…" : "Crear"}
          </Button>
        </>
      }
    >
      <Field label="Nombre de la sub-área *">
        <Input value={nombre} onChange={(e) => setNombre(e.target.value)} autoFocus placeholder="Hemodinamia" />
      </Field>
    </Modal>
  );
}

function AreaModal({ area, institucionId, onClose }) {
  const toast = useToast();
  const esNuevo = !area;
  const [f, setF] = useState({
    nombre: area?.nombre || "",
    responsable: area?.responsable || "",
    descripcion: area?.descripcion || "",
  });
  const set = (k, v) => setF((p) => ({ ...p, [k]: v }));

  const guardar = useAccion(
    () => (esNuevo
      ? api.post("/areas/", { institucion: institucionId, ...f })
      : api.patch(`/areas/${area.id}/`, f)),
    {
      onSuccess: () => { toast.ok(esNuevo ? "Área creada." : "Área actualizada."); onClose(); },
      onError: (e) => toast.deError(e, "No se pudo guardar el área."),
    },
  );

  return (
    <Modal
      title={esNuevo ? "Nueva área" : "Editar área"}
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancelar</Button>
          <Button disabled={guardar.isPending || !f.nombre} onClick={() => guardar.mutate()}>
            {guardar.isPending ? "…" : "Guardar"}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3.5">
        <Field label="Nombre *"><Input value={f.nombre} onChange={(e) => set("nombre", e.target.value)} autoFocus /></Field>
        <Field label="Responsable / jefe">
          <Input value={f.responsable} onChange={(e) => set("responsable", e.target.value)} placeholder="Dra. Laura Méndez" />
        </Field>
        <Field label="Descripción">
          <Textarea value={f.descripcion} onChange={(e) => set("descripcion", e.target.value)} />
        </Field>
      </div>
    </Modal>
  );
}

function AsignarModal({ area, onClose }) {
  const toast = useToast();
  const [usuarioId, setUsuarioId] = useState("");
  const [funcion, setFuncion] = useState("administrativo");

  // Se piden 100 y sin superusuarios: con los 25 de la primera página el
  // desplegable ocultaba gente sin decirlo.
  const usuarios = useLista("usuarios", { is_superuser: false, pageSize: 100, ordering: "apellido" });
  const elegido = usuarioId || String(usuarios.filas[0]?.id || "");

  const asignar = useAccion(
    async () => {
      // ¿Ya tiene una membresía con esa función en la institución? Se reusa en vez
      // de crear una segunda, que dejaría al mismo rol duplicado.
      const ms = await api.get(
        `/membresias/?usuario=${elegido}&institucion=${area.institucion}&rol=${funcion}`,
      );
      const existente = (ms.results || ms)[0];
      if (existente) {
        if ((existente.areas || []).includes(area.id)) return existente;
        return api.patch(`/membresias/${existente.id}/`, {
          areas: [...(existente.areas || []), area.id],
        });
      }
      return api.post("/membresias/", {
        usuario: Number(elegido), institucion: area.institucion, rol: funcion, areas: [area.id],
      });
    },
    {
      onSuccess: () => { toast.ok("Profesional asignado al área."); onClose(); },
      onError: (e) => toast.deError(e, "No se pudo asignar."),
    },
  );

  return (
    <Modal
      title={`Asignar profesional a ${area.nombre}`}
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancelar</Button>
          <Button disabled={asignar.isPending || !elegido} onClick={() => asignar.mutate()}>
            {asignar.isPending ? "…" : "Asignar"}
          </Button>
        </>
      }
    >
      {usuarios.isLoading ? (
        <Skeleton className="h-24" />
      ) : usuarios.filas.length === 0 ? (
        <EstadoVacio
          titulo="No hay usuarios para asignar"
          detalle="Creá usuarios desde el directorio de plataforma."
          icono="users"
        />
      ) : (
        <div className="flex flex-col gap-3.5">
          <Field label="Persona">
            <Select value={elegido} onChange={(e) => setUsuarioId(e.target.value)}>
              {usuarios.filas.map((u) => (
                <option key={u.id} value={u.id}>{u.nombre_completo || u.email}</option>
              ))}
            </Select>
          </Field>
          <Field label="Función en esta área">
            <Select value={funcion} onChange={(e) => setFuncion(e.target.value)}>
              {FUNCIONES.map((f) => <option key={f.value} value={f.value}>{f.label}</option>)}
            </Select>
          </Field>
          <div className="text-sm text-texto-debil">
            El médico podrá registrar atenciones (firmar en la historia clínica); el
            administrativo opera el resto del proceso.
          </div>
        </div>
      )}
    </Modal>
  );
}
