import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/api/client";
import { useAccion, useLista } from "@/api/queries";
import { useInstitucion } from "@/auth/InstitutionContext";
import { Avatar, Badge, Button, Card, Field, Input, Modal, Mono, Select } from "@/components/ui";
import { EstadoError, EstadoVacio, Skeleton, SkeletonTabla } from "@/components/ui/estados";
import { useToast } from "@/components/ui/toast";
import { casoId, fechaHora } from "@/lib/format";

export default function Legajo() {
  const { institucion } = useInstitucion();
  const navigate = useNavigate();
  const [sel, setSel] = useState("");
  const [editar, setEditar] = useState(false);

  /*
   * El staff sale de las membresías, sin cruzar con /usuarios/.
   *
   * Antes se pedían las tres listas y se cruzaban acá: `/usuarios/` devuelve 25
   * por página, así que el desplegable de profesionales se cortaba en 25 sin
   * decir nada. La membresía ya trae `usuario_nombre`, que es justamente para
   * evitar ese cruce.
   */
  const membresias = useLista(
    "membresias",
    { institucion: institucion?.id, activo: true, pageSize: 200 },
    { enabled: !!institucion },
  );
  const areas = useLista("areas", { institucion: institucion?.id, pageSize: 100 }, { enabled: !!institucion });

  const staff = useMemo(() => {
    const nombreArea = Object.fromEntries(areas.filas.map((a) => [a.id, a.nombre]));
    const por = new Map();
    for (const m of membresias.filas) {
      if (!por.has(m.usuario)) {
        por.set(m.usuario, { id: m.usuario, nombre: m.usuario_nombre || m.usuario_email, areas: new Set() });
      }
      (m.areas || []).forEach((aid) => nombreArea[aid] && por.get(m.usuario).areas.add(nombreArea[aid]));
    }
    return [...por.values()]
      .map((x) => ({ ...x, areas: [...x.areas] }))
      .sort((a, b) => a.nombre.localeCompare(b.nombre, "es"));
  }, [membresias.filas, areas.filas]);

  // Al llegar la lista se elige al primero, salvo que ya haya alguien elegido.
  useEffect(() => {
    if (!sel && staff.length) setSel(String(staff[0].id));
  }, [staff, sel]);

  const q = useQuery({
    queryKey: ["legajo", sel, institucion?.id],
    queryFn: () => api.get(`/usuarios/${sel}/legajo/?institucion=${institucion.id}`),
    enabled: !!sel && !!institucion?.id,
  });
  const legajo = q.data;

  if (membresias.error) return <EstadoError error={membresias.error} onReintentar={membresias.refetch} />;
  if (membresias.isLoading) return <div className="p-[30px]"><SkeletonTabla filas={4} columnas={4} /></div>;
  if (!staff.length) {
    return (
      <EstadoVacio
        titulo="No hay profesionales en esta institución"
        detalle="Asigná membresías desde Administración para que aparezcan acá."
        icono="users"
      />
    );
  }

  const prof = staff.find((s) => String(s.id) === String(sel));
  const u = legajo?.usuario;
  const metricas = [
    { n: legajo?.casos_atendidos, l: "Casos atendidos" },
    { n: legajo?.pacientes_vistos, l: "Pacientes distintos" },
    { n: legajo?.llamados_fila, l: "Llamados de fila" },
  ];

  return (
    <div className="px-lg py-[22px] sm:px-[30px]">
      <header className="mb-lg flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold">Legajo profesional</h2>
          <p className="text-sm text-texto-debil">Actividad clínica y datos de matrícula de cada profesional.</p>
        </div>
        <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto">
          <label htmlFor="profesional" className="sr-only">Profesional</label>
          <Select id="profesional" value={sel} onChange={(e) => setSel(e.target.value)} className="min-w-48 flex-1 sm:w-56 sm:flex-none">
            {staff.map((s) => <option key={s.id} value={s.id}>{s.nombre}</option>)}
          </Select>
          <Button size="sm" variant="secondary" onClick={() => setEditar(true)} disabled={!u}>Editar legajo</Button>
        </div>
      </header>

      {membresias.total > membresias.filas.length && (
        <p className="mb-3 rounded-md bg-badge-amber-bg px-3 py-2 text-sm text-badge-amber-fg">
          Se muestran {membresias.filas.length} de {membresias.total} membresías. Algunos profesionales pueden faltar en el selector.
        </p>
      )}

      <Card className="mb-[18px] px-5 py-lg">
        <div className="mb-4 flex flex-wrap items-center gap-2.5">
          <Avatar nombre={prof?.nombre} i={prof?.id || 0} size={40} />
          <h3 className="text-lg font-bold">{prof?.nombre}</h3>
          {u?.matricula ? <Badge tone="green">Matrícula cargada</Badge> : <Badge tone="gray">Sin matrícula</Badge>}
        </div>
        <dl className="grid gap-4 text-sm sm:grid-cols-2 xl:grid-cols-4">
          {[
            ["Matrícula", u?.matricula || "—"],
            ["Especialidad", u?.especialidad || "—"],
            ["Áreas", prof?.areas?.join(", ") || "—"],
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
