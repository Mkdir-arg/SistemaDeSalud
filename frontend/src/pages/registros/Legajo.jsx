import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/api/client";
import { useAccion, useLista } from "@/api/queries";
import { useAuth } from "@/auth/AuthContext";
import { useInstitucion } from "@/auth/InstitutionContext";
import { Avatar, Badge, Button, Card, Field, Input, Modal, Mono } from "@/components/ui";
import { EstadoError, EstadoVacio, Skeleton, SkeletonTabla } from "@/components/ui/estados";
import { Buscador, FiltroSelect, LimpiarFiltros, useBusquedaUrl, useFiltroUrl } from "@/components/ui/filtros";
import { TablaRecurso } from "@/components/ui/tabla";
import { useToast } from "@/components/ui/toast";
import { casoId, fechaHora } from "@/lib/format";

const ROLES = [
  { value: "plataforma", label: "Autoridad estatal / plataforma" },
  { value: "auditor", label: "Auditor estatal" },
  { value: "reportes", label: "Reportes / solo lectura" },
  { value: "admin", label: "Admin de institución" },
  { value: "configurador", label: "Configurador" },
  { value: "jefe_area", label: "Jefe / Supervisor de área" },
  { value: "administrativo", label: "Administrativo" },
  { value: "enfermeria", label: "Enfermería" },
  { value: "medico", label: "Médico / profesional" },
];

export default function Legajo() {
  const { institucion } = useInstitucion();
  const { user } = useAuth();
  const [params, setParams] = useSearchParams();
  const [texto, setTexto, busqueda] = useBusquedaUrl("q");
  const [rol, setRol] = useFiltroUrl("rol");
  const [area, setArea] = useFiltroUrl("area");
  const [sel, setSel] = useFiltroUrl("profesional");
  const institucionAnterior = useRef(institucion?.id);
  const detalleRef = useRef(null);
  const areas = useLista("areas", { institucion: institucion?.id, pageSize: 200 }, {
    enabled: !!institucion?.id, placeholderData: undefined,
  });

  // Los filtros y la selección pertenecen a la institución, no a la sesión global.
  useEffect(() => {
    if (institucionAnterior.current && institucionAnterior.current !== institucion?.id) {
      const p = new URLSearchParams(params);
      ["q", "rol", "area", "profesional", "legajo_pag"].forEach((clave) => p.delete(clave));
      setParams(p, { replace: true });
    }
    institucionAnterior.current = institucion?.id;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [institucion?.id]);

  const activos = [busqueda, rol, area].filter(Boolean).length;
  const limpiar = () => {
    const p = new URLSearchParams(params);
    ["q", "rol", "area", "legajo_pag"].forEach((clave) => p.delete(clave));
    setParams(p, { replace: true });
    setTexto("");
  };
  const columnas = [{
    key: "nombre_completo", label: "Persona", orden: "apellido",
    render: (persona) => (
      <div className="flex min-w-0 items-center gap-2.5">
        <Avatar nombre={persona.nombre_completo || persona.email} i={persona.id} size={32} />
        <div className="min-w-0">
          <div className="truncate font-semibold">{persona.nombre_completo || persona.email}</div>
          <div className="truncate text-sm text-texto-debil">{persona.email}</div>
        </div>
      </div>
    ),
  }];

  return (
    <div className="px-lg py-[22px] sm:px-[30px]">
      <div className="mb-lg">
        <h2 className="text-xl font-extrabold">Legajos del equipo</h2>
        <p className="text-sm text-texto-debil">Buscá una persona con membresía activa en {institucion?.nombre} para consultar su legajo.</p>
      </div>
      <div className="grid items-start gap-lg xl:grid-cols-[minmax(20rem,26rem)_minmax(0,1fr)]">
        <TablaRecurso
          key={`${user?.id}:${institucion?.id}`}
          clave="legajo"
          recurso="usuarios"
          params={{
            institucion: institucion?.id,
            search: busqueda || undefined,
            rol: rol || undefined,
            areas: area || undefined,
          }}
          ambitoConsulta={[user?.id, institucion?.id]}
          opcionesConsulta={{ enabled: !!institucion?.id, gcTime: 0, placeholderData: undefined }}
          ordenInicial="apellido"
          columnas={columnas}
          onRowClick={(persona) => {
            setSel(String(persona.id));
            if (!window.matchMedia("(min-width: 1280px)").matches) {
              requestAnimationFrame(() => detalleRef.current?.scrollIntoView({ block: "start" }));
            }
          }}
          vacio={{
            titulo: activos ? "Nadie coincide con la búsqueda" : "No hay personas en esta institución",
            detalle: activos ? "Probá quitar algún filtro." : "Asigná membresías desde Administración para que aparezcan acá.",
          }}
          barra={
            <>
              <Buscador valor={texto} onChange={setTexto} placeholder="Nombre o correo…" aria-label="Buscar persona" className="w-full" />
              <FiltroSelect etiqueta="Filtrar por rol" valor={rol} onChange={setRol} opciones={ROLES} todos="Todos los roles" />
              <FiltroSelect
                etiqueta="Filtrar por área" valor={area} onChange={setArea}
                opciones={areas.filas.map((a) => ({ value: String(a.id), label: a.nombre }))}
                todos="Todas las áreas"
              />
              <LimpiarFiltros activos={activos} onLimpiar={limpiar} />
            </>
          }
        />
        <section ref={detalleRef} className="min-w-0" aria-label="Detalle del legajo">
          {sel
            ? <LegajoDetalle key={`${institucion?.id}:${sel}`} institucionId={institucion?.id} usuarioId={sel} />
            : <Card><EstadoVacio titulo="Elegí una persona" detalle="Seleccioná alguien del listado para ver su legajo y actividad reciente." icono="users" /></Card>}
        </section>
      </div>
    </div>
  );
}

function LegajoDetalle({ institucionId, usuarioId }) {
  const navigate = useNavigate();
  const [editar, setEditar] = useState(false);
  const idValido = /^\d+$/.test(usuarioId);
  const membresias = useLista("membresias", {
    institucion: institucionId, usuario: usuarioId, activo: true, pageSize: 20,
  }, { enabled: !!institucionId && idValido, placeholderData: undefined, gcTime: 0 });
  const pertenece = idValido && !membresias.isFetching && !membresias.error && membresias.total > 0;

  const q = useQuery({
    queryKey: ["legajo", institucionId, usuarioId],
    queryFn: () => api.get(`/usuarios/${usuarioId}/legajo/?institucion=${institucionId}`),
    enabled: pertenece,
  });
  const legajo = q.data;
  const u = legajo?.usuario;
  const prof = membresias.filas[0];
  const nombresArea = [...new Set(membresias.filas.flatMap((m) => Object.values(m.areas_nombres || {})))];
  const metricas = [
    { n: legajo?.casos_atendidos, l: "Casos atendidos" },
    { n: legajo?.pacientes_vistos, l: "Pacientes distintos" },
    { n: legajo?.llamados_fila, l: "Llamados de fila" },
  ];

  if (!idValido) {
    return <Card><EstadoVacio titulo="Enlace de legajo inválido" detalle="Elegí una persona del listado." /></Card>;
  }
  if (membresias.error) {
    return <Card><EstadoError error={membresias.error} onReintentar={membresias.refetch} /></Card>;
  }
  if (membresias.isFetching || membresias.isLoading) {
    return <Card><SkeletonTabla filas={4} columnas={2} /></Card>;
  }
  if (!membresias.total) {
    return <Card><EstadoVacio titulo="Legajo no disponible en esta institución" detalle="Elegí una persona del listado actual." /></Card>;
  }

  return (
    <div className="min-w-0">
      <Card className="mb-[18px] flex flex-wrap items-center gap-lg px-6 py-[22px]">
        <Avatar nombre={prof?.usuario_nombre || u?.nombre} i={Number(usuarioId)} size={52} />
        <div className="min-w-0 flex-1">
          <h2 className="text-xl font-extrabold tracking-tight">{prof?.usuario_nombre || u?.nombre}</h2>
          <div className="text-base text-texto-debil">
            Integrante del equipo
            {u?.especialidad ? ` · ${u.especialidad}` : ""}
            {nombresArea.length ? ` · ${nombresArea.join(" · ")}` : ""}
          </div>
          {u?.matricula && <Mono className="mt-1.5 block text-base font-semibold">M.N. {u.matricula}</Mono>}
        </div>
        <div className="flex flex-col items-end gap-2">
          {/* La matrícula es la que habilita a firmar una atención (regla del
              motor), así que su estado se muestra con palabras, no sólo color. */}
          {u?.matricula ? <Badge tone="green">Matrícula cargada</Badge> : <Badge tone="gray">Sin matrícula</Badge>}
          <button
            onClick={() => setEditar(true)}
            disabled={!u}
            className="text-sm font-semibold text-accent hover:underline disabled:opacity-50"
          >
            Editar legajo
          </button>
        </div>
        <dl className="grid gap-4 text-sm sm:grid-cols-2 xl:grid-cols-4">
          {[
            ["Matrícula", u?.matricula || "—"],
            ["Especialidad", u?.especialidad || "—"],
            ["Áreas", nombresArea.join(", ") || "—"],
            ["Última actividad", legajo?.ultima_actividad ? fechaHora(legajo.ultima_actividad) : "—"],
          ].map(([etiqueta, valor]) => (
            <div key={etiqueta}>
              <dt className="text-texto-tenue">{etiqueta}</dt>
              <dd className="mt-1 font-medium text-texto-fuerte">{valor}</dd>
            </div>
          ))}
        </dl>
      </Card>

      {q.error ? (
        <EstadoError error={q.error} onReintentar={q.refetch} titulo="No se pudo cargar el legajo" />
      ) : (
        <>
          <div className="mb-[22px] grid gap-3.5 sm:grid-cols-3">
            {metricas.map((m) => (
              <Card key={m.l} className="p-[18px]">
                <div className="text-sm text-texto-debil">{m.l}</div>
                <div className="mt-1.5 text-cifra font-bold leading-none">
                  {q.isLoading ? <Skeleton className="h-6 w-12" /> : (m.n ?? "—")}
                </div>
              </Card>
            ))}
          </div>

          <Card className="overflow-hidden">
            {q.isLoading ? (
              <SkeletonTabla filas={5} columnas={4} />
            ) : !legajo?.actividad?.length ? (
              <div className="px-5 py-[22px] text-base text-texto-tenue">Sin actividad registrada.</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full border-collapse text-md">
                  <thead className="bg-superficie-2">
                    <tr>
                      {["Fecha", "Paciente", "Caso", "Entrada en la historia"].map((h) => (
                        <th key={h} scope="col" className="whitespace-nowrap border-t border-division px-5 py-2.5 text-left text-sm font-semibold text-texto-debil">
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {legajo.actividad.map((a, i) => (
                      <tr
                        key={i}
                        onClick={() => navigate(`/casos/${a.caso}`)}
                        tabIndex={0}
                        onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); navigate(`/casos/${a.caso}`); } }}
                        className="cursor-pointer border-t border-division hover:bg-superficie-2 focus-visible:bg-superficie-2"
                      >
                        <td className="whitespace-nowrap px-5 py-3 text-texto-debil">{fechaHora(a.fecha)}</td>
                        <td className="px-5 py-3 font-semibold">{a.paciente || "—"}</td>
                        <td className="px-5 py-3"><Mono>{casoId(a.caso)}</Mono></td>
                        <td className="px-5 py-3 text-texto-medio">{a.accion}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </>
      )}

      {editar && u && <EditarLegajoModal usuario={u} onClose={() => setEditar(false)} />}
    </div>
  );
}

function EditarLegajoModal({ usuario, onClose }) {
  const toast = useToast();
  const [especialidad, setEspecialidad] = useState(usuario.especialidad || "");
  const [matricula, setMatricula] = useState(usuario.matricula || "");

  const guardar = useAccion(
    async () => {
      // El legajo puede no existir todavía: se busca antes de decidir si es alta
      // o edición.
      const d = await api.get(`/legajos/?usuario=${usuario.id}`);
      const existente = (d.results || d)[0];
      return existente
        ? api.patch(`/legajos/${existente.id}/`, { especialidad, matricula })
        : api.post("/legajos/", { usuario: usuario.id, especialidad, matricula });
    },
    {
      // El legajo se lee por `/usuarios/:id/legajo/`, que es una consulta aparte:
      // sin invalidarla la tarjeta seguiría mostrando la matrícula vieja.
      invalida: ["lista", "detalle", "legajo"],
      onSuccess: () => { toast.ok("Legajo actualizado."); onClose(); },
      onError: (e) => toast.deError(e, "No se pudo guardar el legajo."),
    },
  );

  return (
    <Modal
      title={`Legajo · ${usuario.nombre_completo || usuario.nombre}`}
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
      <div className="flex flex-col gap-3.5">
        <Field label="Especialidad">
          <Input value={especialidad} onChange={(e) => setEspecialidad(e.target.value)} autoFocus />
        </Field>
        <Field label="Matrícula">
          <Input value={matricula} onChange={(e) => setMatricula(e.target.value)} placeholder="98.214" />
        </Field>
      </div>
    </Modal>
  );
}
