import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { api } from "@/api/client";
import { useAccion, useLista } from "@/api/queries";
import { useInstitucion } from "@/auth/InstitutionContext";
import { Icon } from "@/components/icons";
import {
  Avatar, Badge, Button, Card, ConfirmDialog, Field, IconButton, Input, Modal, Select, Textarea,
} from "@/components/ui";
import { EstadoError, EstadoVacio, Skeleton } from "@/components/ui/estados";
import { HorariosModal } from "./HorariosAgenda";
import { Buscador } from "@/components/ui/filtros";
import { useToast } from "@/components/ui/toast";
import { plural } from "@/lib/format";

/** Funciones operativas que se pueden asignar a un área. */
const FUNCIONES = [
  { value: "jefe_area", label: "Jefe / Supervisor de área" },
  { value: "administrativo", label: "Administrativo" },
  { value: "enfermeria", label: "Enfermería" },
  { value: "medico", label: "Médico / profesional" },
];

/** Secciones de la ficha, en el orden en que se apilan. */
const SECCIONES = [
  { key: "datos", label: "Datos", icono: "list" },
  { key: "staff", label: "Staff", icono: "users", accion: "Asignar profesional" },
  { key: "grupos", label: "Grupos", icono: "users", accion: "Crear grupo" },
  { key: "boxes", label: "Boxes", icono: "enter", accion: "Crear box" },
  { key: "agendas", label: "Agendas", icono: "calendar", accion: "Crear agenda" },
  { key: "subareas", label: "Sub-áreas", icono: "cube", accion: "Crear sub-área" },
];

const CLAVES = SECCIONES.map((s) => s.key);

/**
 * Estructura organizativa: árbol de áreas a la izquierda, ficha a la derecha.
 *
 * Antes era una tabla que abría un panel lateral de 600 px con seis solapas, y
 * adentro modales: tres capas apiladas para editar un horario. Ahora el árbol
 * queda siempre visible —configurar ocho áreas seguidas era abrir y cerrar ocho
 * veces— y cada sección del área es su propia página.
 *
 * Que sean páginas y no solapas de estado importa: «mandame el staff de
 * Guardia» es un link, el back del navegador vuelve a la sección anterior, y
 * recargar deja donde estaba. Lo que sí se conserva de la vista de resumen son
 * los contadores, que viven en Datos: qué falta configurar se ve sin recorrer
 * las seis.
 */
export default function Areas() {
  const { institucion } = useInstitucion();
  const navigate = useNavigate();
  const toast = useToast();
  const { areaId, seccion, subId } = useParams();
  const [nuevoArea, setNuevoArea] = useState(false);
  const [editar, setEditar] = useState(false);
  const [aBorrar, setABorrar] = useState(null);

  const areas = useLista(
    "areas",
    { institucion: institucion?.id, pageSize: 100 },
    { enabled: !!institucion },
  );
  // Se busca por id y no se guarda el objeto: así la ficha refleja los cambios
  // (renombrar, sumar sub-áreas) sin quedarse con una copia vieja en el estado.
  const sel = areas.filas.find((a) => String(a.id) === areaId) || null;
  const sub = sel?.subareas?.find((s) => String(s.id) === subId) || null;
  const activa = CLAVES.includes(seccion) ? seccion : "datos";

  const abrirArea = (a) => navigate(`/estructura/${a.id}/datos`);
  const abrirSub = (a, s) => navigate(`/estructura/${a.id}/sub/${s.id}`);
  const abrirSeccion = (k) => navigate(`/estructura/${areaId}/${k}`);

  // Rutas que no llevan a ninguna parte: un área o una sub-área que ya no están
  // (las borró otro, o son de otra institución) y una sección inventada a mano
  // en la barra de direcciones. Sin esto las dos primeras dejan la ficha en
  // blanco sin explicación —o la rompen— y la tercera no muestra sección alguna.
  const listo = !areas.isLoading && !areas.error && areas.filas.length > 0;
  useEffect(() => {
    if (!listo || !areaId) return;
    if (!sel) navigate("/estructura", { replace: true });
    else if (subId && !sub) navigate(`/estructura/${areaId}/subareas`, { replace: true });
    else if (!subId && seccion !== activa) navigate(`/estructura/${areaId}/${activa}`, { replace: true });
  }, [listo, areaId, sel, subId, sub, seccion, activa, navigate]);

  const borrarArea = useAccion((a) => api.del(`/areas/${a.id}/`), {
    onSuccess: () => {
      toast.ok("Área eliminada.");
      setABorrar(null);
      navigate("/estructura", { replace: true });
    },
    onError: (e) => toast.deError(e, "No se pudo eliminar. Puede tener elementos asociados."),
  });

  return (
    <div className="flex h-full min-h-0">
      <ArbolAreas
        areas={areas}
        institucion={institucion}
        areaId={areaId}
        subId={subId}
        onArea={abrirArea}
        onSub={abrirSub}
        onNueva={() => setNuevoArea(true)}
      />

      <div className="min-w-0 flex-1">
        {!sel ? (
          <SinSeleccion
            cargando={areas.isLoading}
            error={areas.error}
            onReintentar={areas.refetch}
            total={areas.total}
            onNueva={() => setNuevoArea(true)}
          />
        ) : sub ? (
          <FichaSubarea
            key={sub.id}
            area={sel}
            sub={sub}
            onVolver={() => navigate(`/estructura/${sel.id}/subareas`)}
            onChange={areas.refetch}
          />
        ) : (
          <FichaArea
            key={sel.id}
            area={sel}
            seccion={activa}
            institucionNombre={institucion?.nombre}
            onSeccion={abrirSeccion}
            onEditar={() => setEditar(true)}
            onBorrar={() => setABorrar(sel)}
            onAbrirSub={(s) => abrirSub(sel, s)}
            onChange={areas.refetch}
          />
        )}
      </div>

      {nuevoArea && (
        <AreaModal
          institucionId={institucion?.id}
          onClose={() => setNuevoArea(false)}
          onSaved={(a) => { areas.refetch(); if (a?.id) navigate(`/estructura/${a.id}/datos`); }}
        />
      )}
      {editar && sel && (
        <AreaModal
          area={sel}
          institucionId={institucion?.id}
          onClose={() => setEditar(false)}
          onSaved={areas.refetch}
        />
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
 * Árbol de áreas y sub-áreas.
 *
 * El filtro es en memoria y no contra el servidor: son 100 áreas como mucho, ya
 * están cargadas, y filtrar acá también encuentra sub-áreas —que el backend no
 * busca— además de responder mientras se escribe.
 */
function ArbolAreas({ areas, institucion, areaId, subId, onArea, onSub, onNueva }) {
  const [q, setQ] = useState("");

  const filtradas = useMemo(() => {
    const t = q.trim().toLowerCase();
    if (!t) return areas.filas;
    return areas.filas.filter(
      (a) =>
        a.nombre.toLowerCase().includes(t) ||
        (a.subareas || []).some((s) => s.nombre.toLowerCase().includes(t)),
    );
  }, [areas.filas, q]);

  return (
    <nav
      aria-label="Áreas de la institución"
      className="flex w-64 flex-none flex-col border-r border-borde bg-superficie"
    >
      <div className="border-b border-division px-3.5 pb-2.5 pt-3.5">
        <div className="flex items-baseline justify-between gap-2">
          <h1 className="text-lg font-extrabold tracking-tight">Áreas</h1>
          <span className="text-xs tabular-nums text-texto-tenue">{areas.total}</span>
        </div>
        <Buscador
          valor={q}
          onChange={setQ}
          placeholder="Buscar área o sub-área…"
          aria-label="Buscar área o sub-área"
          className="mt-2.5"
        />
      </div>

      <div className="flex-1 overflow-y-auto px-2 pb-3 pt-1.5">
        {areas.isLoading && <Skeleton className="m-1 h-40" />}
        {!areas.isLoading && !filtradas.length && (
          <p className="px-2 py-6 text-center text-base text-texto-debil">
            {q ? "Ninguna área coincide." : "Todavía no hay áreas."}
          </p>
        )}
        <ul>
          {filtradas.map((a) => {
            const activa = String(a.id) === areaId;
            const subs = a.subareas || [];
            return (
              <li key={a.id}>
                <NodoArbol
                  activo={activa && !subId}
                  seleccionado={activa}
                  chevron={subs.length ? (activa ? "down" : "right") : null}
                  nombre={a.nombre}
                  cuenta={a.staff}
                  tituloCuenta={plural(a.staff || 0, "persona", "personas")}
                  onClick={() => onArea(a)}
                />
                {activa && subs.length > 0 && (
                  <ul>
                    {subs.map((s) => (
                      <li key={s.id}>
                        <NodoArbol
                          hijo
                          activo={String(s.id) === subId}
                          nombre={s.nombre}
                          onClick={() => onSub(a, s)}
                        />
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            );
          })}
        </ul>
      </div>

      <div className="border-t border-division p-2.5">
        <button
          data-tour="estructura-nueva-area"
          onClick={onNueva}
          disabled={!institucion}
          className="flex w-full items-center justify-center gap-1.5 rounded-md border border-dashed border-borde px-3 py-2 text-base font-semibold text-texto-suave hover:border-accent-100 hover:text-accent disabled:opacity-40"
        >
          <Icon name="plus" size={14} /> Nueva área
        </button>
      </div>
    </nav>
  );
}

function NodoArbol({ hijo, activo, seleccionado, chevron, nombre, cuenta, tituloCuenta, onClick }) {
  return (
    <button
      onClick={onClick}
      aria-current={activo ? "page" : undefined}
      className={[
        "flex w-full items-center gap-2 rounded-md py-1.5 pr-2.5 text-left",
        hijo ? "pl-8" : "pl-2.5",
        activo
          ? "bg-accent-50 text-accent"
          : seleccionado
            ? "text-texto-medio"
            : "text-texto-medio hover:bg-superficie-2",
      ].join(" ")}
    >
      {!hijo && (
        <span className={activo ? "w-3 text-accent" : "w-3 text-texto-tenue"}>
          {chevron && (
            <Icon name="back" size={11} className={chevron === "down" ? "-rotate-90" : "rotate-180"} />
          )}
        </span>
      )}
      <span
        className={[
          "min-w-0 flex-1 truncate",
          hijo ? "text-base" : "text-md",
          activo ? "font-bold" : hijo ? "font-medium text-texto-suave" : "font-semibold",
        ].join(" ")}
      >
        {nombre}
      </span>
      {cuenta != null && (
        <span
          title={tituloCuenta}
          className={activo ? "text-xs tabular-nums text-accent" : "text-xs tabular-nums text-texto-tenue"}
        >
          {cuenta}
        </span>
      )}
    </button>
  );
}

/** Panel derecho cuando todavía no se eligió un área. */
function SinSeleccion({ cargando, error, onReintentar, total, onNueva }) {
  if (error) {
    return (
      <div className="p-8">
        <EstadoError error={error} onReintentar={onReintentar} />
      </div>
    );
  }
  if (cargando) {
    return (
      <div className="p-8">
        <Skeleton className="h-64" />
      </div>
    );
  }
  return (
    <div className="grid h-full place-items-center p-8">
      <div className="max-w-[24rem] text-center">
        <span className="mx-auto mb-3.5 flex size-12 items-center justify-center rounded-lg bg-accent-50 text-accent">
          <Icon name="cube" size={22} />
        </span>
        <h2 className="text-xl font-extrabold tracking-tight">
          {total ? "Elegí un área" : "No hay áreas todavía"}
        </h2>
        <p className="mt-1.5 text-md text-texto-debil">
          {total
            ? "En la lista de la izquierda. Se abre su staff, grupos, boxes, agendas y sub-áreas."
            : "Creá la primera para poder armar flujos, grupos y boxes."}
        </p>
        {!total && (
          <Button data-tour="estructura-nueva-area-vacia" onClick={onNueva} className="mt-lg">
            Nueva área
          </Button>
        )}
      </div>
    </div>
  );
}

/**
 * Ficha del área: contadores arriba, secciones apiladas abajo.
 *
 * Las consultas viven acá y no en cada sección porque los contadores necesitan
 * los totales antes de que el usuario baje: pedirlos dos veces sería pedir lo
 * mismo dos veces.
 */
function FichaArea({
  area, seccion, institucionNombre, onSeccion, onEditar, onBorrar, onAbrirSub, onChange,
}) {
  const [asignar, setAsignar] = useState(false);
  const [crearSub, setCrearSub] = useState(false);
  const [crearGrupo, setCrearGrupo] = useState(false);
  const [crearBox, setCrearBox] = useState(false);
  const [crearAgenda, setCrearAgenda] = useState(false);

  const staff = useStaffDeArea(area);
  const grupos = useLista("grupos", { area: area.id, pageSize: 100 });
  const boxes = useLista("boxes", { area: area.id, pageSize: 100 });
  const agendas = useLista("agendas", { area: area.id, pageSize: 100 });
  const subareas = area.subareas || [];

  // Una agenda sin flujo da turnos que no abren nada. Se cuenta acá para poder
  // avisarlo en el resumen, sin obligar a entrar a la sección.
  const sinFlujo = agendas.filas.filter((a) => !a.flujo).length;

  const cuentas = {
    staff: staff.isLoading ? null : staff.total,
    grupos: grupos.isLoading ? null : grupos.total,
    boxes: boxes.isLoading ? null : boxes.total,
    agendas: agendas.isLoading ? null : agendas.total,
    subareas: subareas.length,
  };

  const paginas = {
    datos: (
      <div className="flex flex-col gap-lg">
        {/* Los contadores viven acá, la sección de entrada, y no repetidos en
            todas: son el panorama del área, no un encabezado. */}
        <div className="grid grid-cols-[repeat(auto-fit,minmax(8.5rem,1fr))] gap-2.5">
          {SECCIONES.filter((s) => s.key !== "datos").map((s) => (
            <Contador
              key={s.key}
              icono={s.icono}
              label={s.label}
              valor={cuentas[s.key]}
              aviso={s.key === "agendas" && sinFlujo > 0 ? `${sinFlujo} sin flujo` : null}
              onClick={() => onSeccion(s.key)}
            />
          ))}
        </div>
        <Seccion titulo="Datos" icono="list">
          <div className="grid gap-lg sm:grid-cols-2">
            <Dato k="Nombre" v={area.nombre} />
            <Dato k="Responsable / jefe" v={area.responsable || "—"} />
            <Dato k="Estado" v={area.activa ? "Activa" : "Inactiva"} />
            <Dato k="Pertenece a" v={institucionNombre} />
            <div className="sm:col-span-2"><Dato k="Descripción" v={area.descripcion || "—"} /></div>
          </div>
        </Seccion>
      </div>
    ),
    staff: (
      <Seccion titulo="Staff" icono="users" cuenta={cuentas.staff}
        accion="Asignar profesional" onAccion={() => setAsignar(true)}>
        <StaffTab area={area} staff={staff} grupos={grupos} />
      </Seccion>
    ),
    grupos: (
      <Seccion titulo="Grupos" icono="users" cuenta={cuentas.grupos}
        accion="Crear grupo" onAccion={() => setCrearGrupo(true)}>
        <GruposTab area={area} grupos={grupos} staff={staff} />
      </Seccion>
    ),
    boxes: (
      <Seccion titulo="Boxes" icono="enter" cuenta={cuentas.boxes}
        accion="Crear box" onAccion={() => setCrearBox(true)}>
        <BoxesTab boxes={boxes} />
      </Seccion>
    ),
    agendas: (
      <Seccion titulo="Agendas" icono="calendar" cuenta={cuentas.agendas}
        accion="Crear agenda" onAccion={() => setCrearAgenda(true)}>
        <AgendasTab agendas={agendas} />
      </Seccion>
    ),
    subareas: (
      <Seccion titulo="Sub-áreas" icono="cube" cuenta={cuentas.subareas}
        accion="Crear sub-área" onAccion={() => setCrearSub(true)}>
        <SubareasLista area={area} onAbrir={onAbrirSub} />
      </Seccion>
    ),
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="flex-none border-b border-borde bg-superficie px-6 pb-0 pt-lg">
        <div className="mb-1.5 text-xs text-texto-tenue">
          {institucionNombre} · <span className="font-semibold text-texto-suave">Estructura</span>
        </div>
        <div className="flex flex-wrap items-center gap-2.5">
          <h2 className="text-cifra font-extrabold tracking-tight">{area.nombre}</h2>
          <Badge tone="info">Área</Badge>
          <Badge tone={area.activa ? "green" : "gray"}>{area.activa ? "Activa" : "Inactiva"}</Badge>
          <div className="ml-auto flex gap-2">
            <Button variant="secondary" onClick={onEditar}>Editar</Button>
            <IconButton
              icon="trash"
              label={`Eliminar ${area.nombre}`}
              onClick={onBorrar}
              className="hover:bg-badge-error-bg hover:text-danger"
            />
          </div>
        </div>
        <div className="mt-0.5 text-base text-texto-debil">
          Responsable: <strong className="text-texto-medio">{area.responsable || "—"}</strong>
        </div>
        <SolapasArea activa={seccion} cuentas={cuentas} onSeccion={onSeccion} />
      </header>

      {/* El scroll es de la sección, no de la ficha: cambiar de solapa no puede
          dejarte a mitad de camino de la anterior. */}
      <div key={seccion} className="min-h-0 flex-1 overflow-y-auto px-6 pb-10 pt-lg">
        {paginas[seccion]}
      </div>

      {asignar && <AsignarModal area={area} onClose={() => setAsignar(false)} />}
      {crearSub && <NuevaSubareaModal area={area} onClose={() => setCrearSub(false)} onSaved={onChange} />}
      {crearGrupo && <GrupoModal area={area} onClose={() => setCrearGrupo(false)} />}
      {crearBox && <BoxModal area={area} onClose={() => setCrearBox(false)} />}
      {crearAgenda && <AgendaModal area={area} onClose={() => setCrearAgenda(false)} />}
    </div>
  );
}

/**
 * Solapas de la ficha. Cada una es una página, así que son navegación y no un
 * conmutador: se anuncian como tal y la activa lleva `aria-current`.
 *
 * Van pegadas al borde de abajo del encabezado —sin separación— porque la
 * pestaña activa se apoya sobre el contenido: es lo que dice que lo de abajo es
 * la solapa, y no otra sección más de la misma página.
 */
function SolapasArea({ activa, cuentas, onSeccion }) {
  function alTeclado(e) {
    const i = CLAVES.indexOf(activa);
    if (e.key === "ArrowRight") onSeccion(CLAVES[(i + 1) % CLAVES.length]);
    if (e.key === "ArrowLeft") onSeccion(CLAVES[(i - 1 + CLAVES.length) % CLAVES.length]);
  }

  return (
    <div
      role="navigation"
      aria-label="Secciones del área"
      onKeyDown={alTeclado}
      className="-mx-1 mt-3 flex gap-0.5 overflow-x-auto"
    >
      {SECCIONES.map((s) => {
        const on = s.key === activa;
        return (
          <button
            key={s.key}
            onClick={() => onSeccion(s.key)}
            aria-current={on ? "page" : undefined}
            tabIndex={on ? 0 : -1}
            className={[
              "flex items-center gap-1.5 whitespace-nowrap border-b-2 px-3 pb-2.5 pt-1.5 text-md font-semibold",
              on
                ? "border-accent text-accent"
                : "border-transparent text-texto-debil hover:text-texto-suave",
            ].join(" ")}
          >
            {s.label}
            {/* El hueco se reserva aunque el número todavía no esté: entrando
                directo a una sección los cuatro contadores llegan juntos, y sin
                esto la barra entera se reacomoda debajo del cursor. */}
            {s.key in cuentas && (
              <span className={on ? "text-xs tabular-nums text-accent" : "text-xs tabular-nums text-texto-tenue"}>
                {cuentas[s.key] ?? "·"}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

/** Tarjeta-contador: resumen y atajo a la sección, en el mismo gesto. */
function Contador({ icono, label, valor, aviso, onClick }) {
  return (
    <button
      onClick={onClick}
      className={[
        "flex flex-col items-start gap-0.5 rounded-md border bg-superficie px-3.5 py-2.5 text-left shadow-card transition-colors",
        aviso ? "border-badge-amber-fg/40" : "border-borde",
        "hover:border-accent-100",
      ].join(" ")}
    >
      <Icon name={icono} size={15} className="mb-0.5 text-accent" />
      <span className={valor ? "text-cifra font-extrabold tabular-nums leading-tight" : "text-cifra font-extrabold tabular-nums leading-tight text-texto-tenue"}>
        {valor ?? "—"}
      </span>
      <span className="text-xs font-semibold text-texto-debil">{label}</span>
      {aviso && <span className="text-micro font-bold text-badge-amber-fg">{aviso}</span>}
    </button>
  );
}

/** Una sección de la ficha, con su contador y su propio botón de crear. */
function Seccion({ titulo, icono, cuenta, accion, onAccion, children }) {
  return (
    <section aria-labelledby={`titulo-${titulo}`}>
      <Card className="overflow-hidden">
        <div className="flex flex-wrap items-center gap-2.5 border-b border-division px-lg py-2.5">
          <Icon name={icono} size={16} className="text-accent" />
          <h3 id={`titulo-${titulo}`} className="text-md font-bold">{titulo}</h3>
          {cuenta != null && (
            <span className="rounded-pill bg-badge-neutral-bg px-2 text-xs font-bold tabular-nums text-badge-neutral-fg">
              {cuenta}
            </span>
          )}
          {accion && (
            <Button size="sm" variant="secondary" onClick={onAccion} className="ml-auto flex items-center gap-1.5">
              <Icon name="plus" size={13} /> {accion}
            </Button>
          )}
        </div>
        <div className="p-lg">{children}</div>
      </Card>
    </section>
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

/** Aviso corto dentro de una sección de la ficha (sin datos todavía). */
function Aviso({ children }) {
  return (
    <p className="rounded-md border border-dashed border-borde px-lg py-3.5 text-md text-texto-debil">
      {children}
    </p>
  );
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

function StaffTab({ area, staff, grupos }) {
  const toast = useToast();

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

function GruposTab({ area, grupos, staff }) {
  const toast = useToast();
  const [gestion, setGestion] = useState(null);
  const [aBorrar, setABorrar] = useState(null);

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

function BoxesTab({ boxes }) {
  const toast = useToast();
  const [aBorrar, setABorrar] = useState(null);

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

/**
 * Sub-áreas del área, como lista.
 *
 * Antes esta lista abría la ficha de la sub-área acá adentro, con su propio
 * botón «volver»: navegación dentro de un panel dentro de una tabla. Ahora sólo
 * lleva al nodo del árbol, que es donde el usuario ya las busca.
 */
function SubareasLista({ area, onAbrir }) {
  const flujos = useLista("flujos", { institucion: area.institucion, pageSize: 200 });

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
              onClick={() => onAbrir(s)}
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

/**
 * Ficha de una sub-área: ocupa el panel derecho, igual que la del área.
 *
 * Es deliberadamente flaca —nombre y flujos vinculados— porque una sub-área no
 * tiene staff, boxes ni agendas propios: los hereda del área. Darle la misma
 * estructura de secciones sugeriría lo contrario.
 */
function FichaSubarea({ area, sub, onVolver, onChange }) {
  const toast = useToast();
  const [editando, setEditando] = useState(false);
  const [nombre, setNombre] = useState(sub.nombre);
  const [confirmar, setConfirmar] = useState(false);

  const todos = useLista("flujos", { institucion: area.institucion, pageSize: 200 });
  const flujos = todos.filas.filter((f) => f.subarea === sub.id);

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
    <div className="h-full overflow-y-auto">
      <header className="sticky top-0 z-10 border-b border-borde bg-superficie px-6 pb-3.5 pt-lg">
        <div className="mb-1.5 text-xs text-texto-tenue">
          <button onClick={onVolver} className="font-semibold text-texto-suave hover:text-accent hover:underline">
            {area.nombre}
          </button>{" "}
          · Sub-área
        </div>
        <div className="flex flex-wrap items-center gap-2.5">
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
              <h2 className="text-cifra font-extrabold tracking-tight">{sub.nombre}</h2>
              <Badge tone="neutral">Sub-área</Badge>
              <div className="ml-auto flex gap-2">
                <Button variant="secondary" onClick={() => setEditando(true)}>Renombrar</Button>
                <IconButton
                  icon="trash"
                  label={`Eliminar ${sub.nombre}`}
                  onClick={() => setConfirmar(true)}
                  className="hover:bg-badge-error-bg hover:text-danger"
                />
              </div>
            </>
          )}
        </div>
      </header>

      <div className="px-6 pb-10 pt-lg">
        <Seccion titulo="Flujos vinculados" icono="workflow" cuenta={todos.isLoading ? null : flujos.length}>
          {todos.isLoading ? (
            <Skeleton className="h-16" />
          ) : flujos.length === 0 ? (
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
        </Seccion>
      </div>

      {confirmar && (
        <ConfirmDialog
          title="Eliminar sub-área"
          confirmar="Eliminar"
          peligroso
          cargando={eliminar.isPending}
          onConfirmar={() => eliminar.mutate()}
          onClose={() => setConfirmar(false)}
        >
          ¿Seguro que querés eliminar <strong>{sub.nombre}</strong>?
          {flujos.length > 0 && ` La usan ${plural(flujos.length, "flujo", "flujos")}.`}
        </ConfirmDialog>
      )}
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

function AreaModal({ area, institucionId, onClose, onSaved }) {
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
      onSuccess: (creada) => {
        toast.ok(esNuevo ? "Área creada." : "Área actualizada.");
        onSaved?.(creada);
        onClose();
      },
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

  // Sólo el padrón de ESTA institución: asignar a un área a alguien de otro
  // hospital no significa nada, y listar el padrón entero de la plataforma le
  // mostraba a este admin nombre y email de gente ajena.
  //
  // Se piden 100 y sin superusuarios: con los 25 de la primera página el
  // desplegable ocultaba gente sin decirlo.
  const usuarios = useLista("usuarios", {
    institucion: area.institucion, is_superuser: false, pageSize: 100, ordering: "apellido",
  });
  // Sin preselección: con el primero de la lista ya elegido, un clic distraído en
  // «Asignar» le daba acceso al área a quien quedó arriba por orden alfabético.
  const elegido = usuarioId;

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
          titulo="Esta institución todavía no tiene personas"
          detalle="Creá usuarios en Estructura → Usuarios y después asignalos al área."
          icono="users"
        />
      ) : (
        <div className="flex flex-col gap-3.5">
          <Field label="Persona">
            <Select value={elegido} onChange={(e) => setUsuarioId(e.target.value)}>
              <option value="">— Elegí una persona —</option>
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

const DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"];
const hhmm = (t) => (t || "").slice(0, 5);

/**
 * Agendas del área: quién o qué se puede reservar, y en qué franjas.
 *
 * Las franjas se editan acá y no en una pantalla aparte porque son inseparables
 * de la agenda: una agenda sin horarios no da ningún turno, y crearla sin poder
 * cargarlos en el mismo lugar deja el trabajo a medias.
 */
function AgendasTab({ agendas }) {
  const toast = useToast();
  const [aBorrar, setABorrar] = useState(null);
  const [franjas, setFranjas] = useState(null); // agenda cuyas franjas se editan
  const [aEditar, setAEditar] = useState(null); // agenda que se está editando

  const borrar = useAccion((a) => api.del(`/agendas/${a.id}/`), {
    onSuccess: () => { toast.ok("Agenda eliminada."); setABorrar(null); },
    onError: (e) => toast.deError(e, "No se pudo eliminar la agenda."),
  });

  if (agendas.error) return <EstadoError error={agendas.error} onReintentar={agendas.refetch} />;
  if (agendas.isLoading) return <Skeleton className="h-24" />;
  if (!agendas.filas.length) {
    return (
      <Aviso>
        Sin agendas. Usá «Crear agenda» para definir a quién o a qué se le pueden dar
        turnos: un profesional, o un recurso como un tomógrafo.
      </Aviso>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      {agendas.filas.map((a) => (
        <Card key={a.id} className="px-lg py-3">
          <div className="flex flex-wrap items-center gap-3">
            <span className="flex size-8 flex-none items-center justify-center rounded-md bg-accent-50 text-accent">
              <Icon name="calendar" size={16} />
            </span>
            <div className="min-w-40 flex-1">
              <div className="text-md font-semibold">{a.nombre}</div>
              <div className="text-sm text-texto-tenue">
                turnos de {a.duracion_min} min
                {a.sobreturnos_max > 0 && ` · hasta ${a.sobreturnos_max} sobreturnos`}
                {a.flujo_titulo ? ` · abre «${a.flujo_titulo}»` : " · sin flujo"}
              </div>
            </div>
            {/* La modalidad se muestra siempre, incluso «presencial»: en una
                institución donde algunas agendas atienden por video, un renglón
                sin nada al lado se lee igual que uno sin configurar. */}
            <Badge tone={a.modalidad === "presencial" ? "gray" : "info"}>
              {a.modalidad_display || "Presencial"}
            </Badge>
            <Badge tone={a.tipo === "recurso" ? "gray" : "info"}>{a.tipo_display}</Badge>
            {!a.activa && <Badge tone="gray">inactiva</Badge>}
            <Button size="sm" variant="secondary" onClick={() => setFranjas(a)}>
              Horarios ({a.disponibilidades?.length || 0})
            </Button>
            <button
              onClick={() => setAEditar(a)}
              title={`Editar ${a.nombre}`}
              aria-label={`Editar ${a.nombre}`}
              className="inline-flex rounded-md p-1 text-texto-debil hover:bg-division hover:text-texto-medio"
            >
              <Icon name="edit" size={15} />
            </button>
            <button
              onClick={() => setABorrar(a)}
              title={`Eliminar ${a.nombre}`}
              aria-label={`Eliminar ${a.nombre}`}
              className="inline-flex rounded-md p-1 text-texto-debil hover:bg-badge-error-bg hover:text-danger"
            >
              <Icon name="trash" size={15} />
            </button>
          </div>

          {/* Sin flujo la agenda da turnos pero presentarse no abre nada, y el
              turno queda siendo una anotación. Se avisa acá y no al crear:
              también se puede llegar a este estado editando. */}
          {!a.flujo && (
            <div className="mt-2 flex items-start gap-2 rounded-md bg-badge-amber-bg px-3 py-2 text-sm text-badge-amber-fg">
              <Icon name="alert" size={14} className="mt-0.5 flex-none" />
              <span>
                Sin flujo asignado: se pueden dar turnos, pero registrar la llegada no
                va a abrir ningún caso.
              </span>
            </div>
          )}

          {/* Una agenda que atiende por video sin sala cargada da turnos
              virtuales sin enlace: el paciente no viene y espera una llamada que
              nadie sabe por dónde entra. Se puede poner el enlace turno por
              turno, así que se avisa sin bloquear. */}
          {a.modalidad !== "presencial" && !a.enlace_virtual && (
            <div className="mt-2 flex items-start gap-2 rounded-md bg-badge-amber-bg px-3 py-2 text-sm text-badge-amber-fg">
              <Icon name="alert" size={14} className="mt-0.5 flex-none" />
              <span>
                Sin enlace de sala: cada turno virtual va a salir sin link, y hay que
                cargarlo a mano uno por uno.
              </span>
            </div>
          )}

          {(a.disponibilidades || []).length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5 pl-11">
              {/* La duración se dice sólo cuando la franja pisa la de la agenda,
                  y los cupos sólo cuando hay más de uno: repetidos en cada chip
                  tapan lo único que se lee de un vistazo, que son los días. */}
              {a.disponibilidades.map((d) => (
                <span key={d.id} className="rounded-pill bg-division px-2 py-px text-xs font-medium text-texto-suave">
                  {DIAS[d.dia_semana]} {hhmm(d.desde)}–{hhmm(d.hasta)}
                  {d.duracion_min ? ` · ${d.duracion_min}′` : ""}
                  {d.cupos > 1 ? ` · ×${d.cupos}` : ""}
                </span>
              ))}
            </div>
          )}
        </Card>
      ))}

      {aEditar && (
        <AgendaModal
          area={{ id: aEditar.area, institucion: aEditar.institucion, nombre: aEditar.area_nombre }}
          agenda={aEditar}
          onClose={() => setAEditar(null)}
        />
      )}

      {franjas && (
        <HorariosModal
          agenda={franjas}
          onClose={() => { setFranjas(null); agendas.refetch(); }}
        />
      )}

      {aBorrar && (
        <ConfirmDialog
          title="Eliminar agenda"
          confirmar="Eliminar"
          peligroso
          cargando={borrar.isPending}
          onConfirmar={() => borrar.mutate(aBorrar)}
          onClose={() => setABorrar(null)}
        >
          ¿Seguro que querés eliminar <strong>{aBorrar.nombre}</strong>? Se van a borrar
          también sus horarios y los turnos dados.
        </ConfirmDialog>
      )}
    </div>
  );
}

/**
 * Alta y edición de una agenda.
 *
 * Edita además de crear porque la configuración de una agenda cambia sola con
 * el tiempo —el profesional pasa a atender por video, se le suma un flujo— y
 * sin esto la única salida era borrarla y volver a crearla, que se lleva
 * puestos los turnos ya dados.
 */
function AgendaModal({ area, agenda, onClose }) {
  const toast = useToast();
  const esNuevo = !agenda;
  const [nombre, setNombre] = useState(agenda?.nombre || "");
  const [tipo, setTipo] = useState(agenda?.tipo || "profesional");
  const [profesional, setProfesional] = useState(agenda?.profesional || "");
  const [flujo, setFlujo] = useState(agenda?.flujo || "");
  const [duracion, setDuracion] = useState(agenda?.duracion_min ?? 20);
  const [sobreturnos, setSobreturnos] = useState(agenda?.sobreturnos_max ?? 2);
  const [modalidad, setModalidad] = useState(agenda?.modalidad || "presencial");
  const [enlace, setEnlace] = useState(agenda?.enlace_virtual || "");

  const staff = useLista("membresias", { areas: area.id, activo: true, pageSize: 100 });
  const flujos = useLista("flujos", { area: area.id, pageSize: 100 });

  const cuerpo = () => ({
    institucion: area.institucion,
    area: area.id,
    nombre: nombre.trim(),
    tipo,
    // Una agenda de recurso no lleva profesional: el backend lo rechaza y
    // mandarlo igual sería un 400 que la persona no entiende.
    profesional: tipo === "profesional" && profesional ? Number(profesional) : null,
    flujo: flujo ? Number(flujo) : null,
    duracion_min: Number(duracion) || 20,
    sobreturnos_max: Number(sobreturnos) || 0,
    modalidad,
    // La sala sólo viaja si la agenda atiende por video: en una presencial el
    // backend la vacía igual, y un link colgando ahí lo hereda sin querer la
    // próxima persona que cambie la modalidad.
    enlace_virtual: modalidad === "presencial" ? "" : enlace.trim(),
  });

  const guardar = useAccion(
    () => (esNuevo
      ? api.post("/agendas/", cuerpo())
      : api.patch(`/agendas/${agenda.id}/`, cuerpo())),
    {
      onSuccess: () => {
        toast.ok(esNuevo ? "Agenda creada." : "Agenda actualizada.");
        onClose();
      },
      onError: (e) => toast.deError(e, "No se pudo guardar la agenda."),
    },
  );

  return (
    <Modal
      title={esNuevo ? `Nueva agenda · ${area.nombre}` : `Editar agenda · ${agenda.nombre}`}
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancelar</Button>
          <Button disabled={guardar.isPending || !nombre.trim()} onClick={() => guardar.mutate()}>
            {guardar.isPending ? "…" : esNuevo ? "Crear" : "Guardar"}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3.5">
        <Field label="Nombre">
          <Input value={nombre} onChange={(e) => setNombre(e.target.value)}
                 placeholder="Dra. Suárez, o Tomógrafo" autoFocus />
        </Field>
        <Field label="Tipo">
          <Select value={tipo} onChange={(e) => { setTipo(e.target.value); setProfesional(""); }}>
            <option value="profesional">Profesional</option>
            <option value="recurso">Recurso (equipo, consultorio)</option>
          </Select>
        </Field>
        {tipo === "profesional" && (
          <Field label="Profesional">
            <Select value={profesional} onChange={(e) => setProfesional(e.target.value)}>
              <option value="">Sin asignar</option>
              {staff.filas.map((m) => (
                <option key={m.id} value={m.usuario}>{m.usuario_nombre || m.usuario_email}</option>
              ))}
            </Select>
          </Field>
        )}
        {/* Presencial, virtual o las dos. «Las dos» no es una agenda a medio
            configurar: es la del profesional que ve pacientes en el consultorio
            y hace controles por video. Partirla en dos agendas dejaría que las
            dos den turno a la misma hora. */}
        <Field
          label="Modalidad de los turnos"
          hint={modalidad === "mixta"
            ? "Quien da el turno elige, uno por uno, si es presencial o virtual."
            : modalidad === "virtual"
              ? "Todos los turnos de esta agenda salen como videollamada."
              : "Todos los turnos de esta agenda son en el lugar."}
        >
          <Select value={modalidad} onChange={(e) => setModalidad(e.target.value)}>
            <option value="presencial">Presencial</option>
            <option value="virtual">Virtual (videollamada)</option>
            <option value="mixta">Presencial o virtual (se elige en cada turno)</option>
          </Select>
        </Field>
        {modalidad !== "presencial" && (
          <Field
            label="Enlace de la sala"
            hint="Se copia a cada turno virtual. Sin esto hay que pegar el link turno por turno."
          >
            <Input value={enlace} onChange={(e) => setEnlace(e.target.value)}
                   placeholder="https://meet.example.com/dra-suarez" />
          </Field>
        )}
        <Field
          label="Flujo que se abre al presentarse"
          hint="Sin flujo se pueden dar turnos, pero la llegada no abre ningún caso."
        >
          <Select value={flujo} onChange={(e) => setFlujo(e.target.value)}>
            <option value="">Ninguno</option>
            {flujos.filas.map((f) => <option key={f.id} value={f.id}>{f.titulo}</option>)}
          </Select>
        </Field>
        <div className="grid gap-3.5 sm:grid-cols-2">
          <Field label="Duración del turno (min)">
            <Input type="number" min="5" step="5" value={duracion}
                   onChange={(e) => setDuracion(e.target.value)} />
          </Field>
          <Field label="Sobreturnos por horario">
            <Input type="number" min="0" value={sobreturnos}
                   onChange={(e) => setSobreturnos(e.target.value)} />
          </Field>
        </div>
      </div>
    </Modal>
  );
}

