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
    queryKey: ["legajo", sel],
    queryFn: () => api.get(`/usuarios/${sel}/legajo/`),
    enabled: !!sel,
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
    { n: legajo?.casos_atendidos, l: "casos atendidos" },
    { n: legajo?.pacientes_vistos, l: "pacientes vistos" },
    { n: legajo?.llamados_fila, l: "llamados de fila" },
    {
      n: legajo?.ultima_actividad ? fechaHora(legajo.ultima_actividad).split(" · ")[0] : "—",
      l: "última actividad",
    },
  ];

  return (
    <div className="px-lg py-[22px] sm:px-[30px]">
      <div className="mb-lg flex max-w-[24rem] items-center gap-2.5">
        <label htmlFor="profesional" className="whitespace-nowrap text-sm text-texto-debil">
          Profesional:
        </label>
        <Select id="profesional" value={sel} onChange={(e) => setSel(e.target.value)}>
          {staff.map((s) => <option key={s.id} value={s.id}>{s.nombre}</option>)}
        </Select>
      </div>

      <Card className="mb-[18px] flex flex-wrap items-center gap-lg px-6 py-[22px]">
        <Avatar nombre={prof?.nombre} i={prof?.id || 0} size={52} />
        <div className="min-w-0 flex-1">
          <h1 className="text-xl font-extrabold tracking-tight">{prof?.nombre}</h1>
          <div className="text-base text-texto-debil">
            Profesional
            {u?.especialidad ? ` · ${u.especialidad}` : ""}
            {prof?.areas?.length ? ` · ${prof.areas.join(" · ")}` : ""}
          </div>
          {u?.matricula && <Mono className="mt-1.5 block text-base font-semibold">M.N. {u.matricula}</Mono>}
        </div>
        <div className="flex flex-col items-end gap-2">
          {/* La matrícula es la que habilita a firmar una atención (regla del
              motor), así que su estado se muestra con palabras, no sólo color. */}
          {u?.matricula ? <Badge tone="green">✓ Vigente</Badge> : <Badge tone="gray">Sin matrícula</Badge>}
          <button
            onClick={() => setEditar(true)}
            className="text-sm font-semibold text-accent hover:underline"
          >
            Editar legajo
          </button>
        </div>
      </Card>

      {q.error ? (
        <EstadoError error={q.error} onReintentar={q.refetch} titulo="No se pudo cargar el legajo" />
      ) : (
        <>
          <div className="mb-[22px] grid grid-cols-2 gap-3.5 sm:grid-cols-4">
            {metricas.map((m) => (
              <Card key={m.l} className="p-[18px]">
                <div className="text-cifra-lg font-extrabold leading-none">
                  {q.isLoading ? <Skeleton className="h-6 w-12" /> : (m.n ?? "—")}
                </div>
                <div className="mt-1.5 text-sm text-texto-debil">{m.l}</div>
              </Card>
            ))}
          </div>

          <Card className="overflow-hidden">
            <div className="px-5 py-lg">
              <h2 className="text-lg font-bold">Actividad reciente</h2>
              <div className="text-sm text-texto-debil">
                Cada Atención que genera enlaza con una entrada en la Historia clínica del paciente.
              </div>
            </div>

            {q.isLoading ? (
              <SkeletonTabla filas={5} columnas={4} />
            ) : !legajo?.actividad?.length ? (
              <div className="px-5 pb-[22px] text-base text-texto-tenue">Sin actividad registrada.</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full border-collapse text-md">
                  <thead className="bg-superficie-2">
                    <tr>
                      {["Fecha", "Paciente", "Acción", "Caso"].map((h) => (
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
                        <td className="px-5 py-3 text-texto-medio">{a.accion}</td>
                        <td className="px-5 py-3"><Mono>{casoId(a.caso)}</Mono></td>
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
